# service/main.py
import asyncio

from redis.asyncio import Redis

from consumer.config import settings
from consumer.consumer import Consumer
from consumer.utils.redis import RedisKeys


async def main() -> None:
    """
    Main entry point for running multiple consumers concurrently.

    This function initializes a Redis connection and creates a specified number
    of consumer instances, each with a unique consumer name. It then runs all
    consumers concurrently using asyncio.

    Args:
        None

    Returns:
        None

    Raises:
        Any exceptions raised by the consumers will propagate.
    """

    redis = Redis.from_url(str(settings.redis_url), decode_responses=True)

    consumers = []
    for i in range(settings.worker_count):
        c = Consumer(
            redis=redis,
            stream_name=RedisKeys.stream_key,
            group_name=settings.group_name,
            consumer_name=f"consumer_{i}",
            webhook_url=settings.webhook_url,
        )
        consumers.append(asyncio.create_task(c.run()))

    await asyncio.gather(*consumers)


if __name__ == "__main__":
    asyncio.run(main())
