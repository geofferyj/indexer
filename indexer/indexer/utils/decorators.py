import asyncio
import functools
import inspect
import time
from typing import Any, Callable, Tuple, TypeVar

from loguru import logger as logging

# Type variable for the return type of the decorated function
R = TypeVar("R")
C = TypeVar("C", bound=Callable[..., Any])


def log_execution(enabled: bool = True) -> Callable[[C], C]:
    """
    Decorator factory that logs the execution details of the decorated function or method.

    Args:
        enabled (bool): Flag to enable or disable logging.

    Returns:
        Callable: A decorator that wraps the target function or method.
    """

    def decorator(func: C) -> C:
        is_coroutine = asyncio.iscoroutinefunction(func)

        if is_coroutine:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    if enabled:
                        _log_execution_details(
                            func, start_time, end_time, args)

            return async_wrapper  # type: ignore

        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    end_time = time.perf_counter()
                    if enabled:
                        _log_execution_details(
                            func, start_time, end_time, args)

            return sync_wrapper  # type: ignore

    return decorator


def _log_execution_details(
    f: Callable[..., Any],
    start: float,
    end: float,
    args: Tuple[Any, ...],
) -> None:
    """
    Logs execution details of the function or method.

    Args:
        f (Callable): The function or method whose details are to be logged.
        start (float): Start time of the function execution.
        end (float): End time of the function execution.
        args (Tuple[Any, ...]): Arguments passed to the function/method, used to determine if it's a method.
    """
    func_name = f.__name__
    try:
        func_location = inspect.getfile(f)
        func_line = inspect.getsourcelines(f)[1]
    except (TypeError, OSError):
        func_location = "<unknown>"
        func_line = -1

    current_frame = inspect.currentframe()
    caller_frame = (
        current_frame.f_back.f_back if current_frame and current_frame.f_back else None
    )

    if caller_frame:
        caller_file = caller_frame.f_code.co_filename
        caller_line = caller_frame.f_lineno
        caller_func = caller_frame.f_code.co_name
    else:
        caller_file = "<unknown>"
        caller_line = -1
        caller_func = "<unknown>"

    # Determine if the first argument is a class or instance
    if args and hasattr(args[0], "__class__"):
        instance_info = f"on {args[0].__class__.__name__} instance"
    else:
        instance_info = ""

    execution_time = end - start

    logging.info(
        f"Executed {func_name} at {func_location}:{func_line} "
        f"called from {caller_file}:{caller_line} by {caller_func} "
        f"{instance_info} in {execution_time:f} seconds",
    )
