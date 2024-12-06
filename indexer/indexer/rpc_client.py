import asyncio
import itertools
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

import aiohttp

from indexer.config import settings


class RPCClient:
    """RPCClient is an asynchronous JSON-RPC client for interacting with an Ethereum blockchain node."""  # noqa: E501

    def __init__(self, rpc_endpoint: str, chain_id: int) -> None:
        """
        Initialize the RPC client.

        Args:
            rpc_endpoint (str): The endpoint URL for the RPC server.
            chain_id (str): The blockchain chain ID.

        Attributes:
            rpc_endpoint (str): The endpoint URL for the RPC server.
            chain_id (str): The blockchain chain ID.
            session (aiohttp.ClientSession): The http session for making HTTP requests.
            rate_limit (asyncio.Semaphore): Semaphore to limit the rate of RPC requests.
            max_request_interval (float): Interval between requests based on the rate
                                          limit.
            _id_counter (itertools.count): Counter for generating unique request IDs.
            active_requests (Dict[int, Dict[str, Any]]): Dictionary to store active
                                                         request IDs and their details.
            lock (asyncio.Lock): Lock to ensure thread-safe updates to active requests.
        """
        self.rpc_endpoint = rpc_endpoint
        self.chain_id = chain_id
        self.session = aiohttp.ClientSession()
        self.rate_limiter = asyncio.Semaphore(settings.rpc_rate_limit)
        self.max_request_interval = 1 / settings.rpc_rate_limit

        # Request ID management
        # Incrementing counter for unique IDs
        self._id_counter = itertools.count(1)
        # Store active request ids
        self.active_requests: Dict[int, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()  # Ensure thread-safe updates

    async def close(self) -> None:
        """
        Asynchronously closes the session.

        This method should be called to properly close the session and release any
        resources associated with it.
        """
        await self.session.close()

    async def _generate_request_id(self, method: str) -> int:
        """
        Generate a unique request ID for a given method.

        Args:
            method (str): The name of the method for which the request ID is being
                          generated.

        Returns:
            int: A unique request ID.
        """
        async with self.lock:
            request_id = next(self._id_counter)
            self.active_requests[request_id] = {
                "method": method,
                "timestamp": datetime.now(UTC),
            }
            return request_id

    async def _remove_request_id(self, request_id: int) -> None:
        """
        Remove a request ID from the active requests.

        This method acquires a lock to ensure thread safety while removing the
        specified request ID from the active requests dictionary.

        Args:
            request_id (int): The ID of the request to be removed.

        Returns:
            None
        """
        async with self.lock:
            if request_id in self.active_requests:
                del self.active_requests[request_id]

    async def _call(
        self,
        method: str,
        params: Optional[List[Any]] = None,
        retries: int = settings.max_rpc_retries,
        backoff_factor: float = settings.rpc_backoff_factor,
    ) -> Any:
        """
        Makes an asynchronous JSON-RPC call with retries and exponential backoff.

        Args:
            method (str): The name of the RPC method to call.
            params (Optional[List[Any]]): The parameters to pass to the RPC method.
                                          Defaults to None.
            retries (int): The number of times to retry the call in case of failure.
                           Defaults to settings.max_rpc_retries.
            backoff_factor (float): The factor by which to multiply the delay between
                                    retries. Defaults to settings.rpc_backoff_factor.

        Returns:
            Any: The result of the RPC call.

        Raises:
            Exception: If the RPC call fails after the specified number of retries or
                       if there is an HTTP or JSON-RPC error.
        """
        request_id = await self._generate_request_id(method)  # Generate a unique ID
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or [],
        }
        attempt = 0

        while attempt < retries:
            try:
                async with self.rate_limiter, self.session.post(
                    self.rpc_endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:

                    # Check for HTTP errors
                    if response.status != 200:
                        raise Exception("RPC call failed with status")

                    data = await response.json()

                    # Check for JSON-RPC errors
                    if "error" in data:
                        raise Exception(f"RPC error: {data['error']}")

                    # await asyncio.sleep(self.max_request_interval)
                    return data["result"]

            except Exception as e:
                attempt += 1

                if attempt >= retries:
                    raise e

                # Exponential backoff
                delay = backoff_factor * (2**attempt)
                await asyncio.sleep(delay)
            finally:
                # Cleanup after each attempt
                await self._remove_request_id(request_id)

        raise Exception("Max retries exceeded")

    async def get_block_by_number(
        self,
        block_number: int,
        full_transactions: bool = True,
    ) -> Dict[str, Any]:
        """
        Asynchronously retrieves a block by its number.

        Args:
            block_number (int): The number of the block to retrieve.
            full_transactions (bool, optional): Whether to include full transaction
                                                objects or just transaction hashes.

        Returns:
            Dict[str, Any]: A dictionary containing the block information.
        """

        hex_block = hex(block_number)
        return await self._call(
            "eth_getBlockByNumber",
            [hex_block, full_transactions],
        )

    async def get_block_transactions(self, block_number: int) -> List[Dict[str, Any]]:
        """
        Asynchronously retrieves a list of transactions in a block.

        Args:
            block_number (int): The number of the block to retrieve transactions from.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing transaction details.
        """
        block = await self.get_block_by_number(block_number, full_transactions=True)
        return block["transactions"]

    async def get_block_receipts(self, block_number: int) -> List[Dict[str, Any]]:
        """
        Asynchronously retrieves a list of transaction receipts in a block.

        Args:
            block_number (int): The number of the block to retrieve transaction receipts
                                from.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing transaction receipt
                                  details.
        """
        hex_block = hex(block_number)
        return await self._call("eth_getBlockReceipts", [hex_block])

    async def get_latest_block_number(self) -> int:
        """
        Asynchronously retrieves the latest block number from the Ethereum blockchain.

        This method calls the "eth_blockNumber" RPC method to get the latest block
        number in hexadecimal format and converts it to an integer.

        Returns:
            int: The latest block number as an integer.
        """
        hex_block = await self._call("eth_blockNumber")
        return int(hex_block, 16)
