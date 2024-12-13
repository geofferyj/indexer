import asyncio
from itertools import chain
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from redis.asyncio import Redis

from indexer.config import settings
from indexer.models import ChainConfig, Transaction
from indexer.rpc_client import RPCClient
from indexer.utils.redis import RedisKeys


class ChainWorker:
    """
    ChainWorker is responsible for managing the processing of blockchain data.

    config (ChainConfig): Configuration object for the chain worker.
    rpc_client (RPCClient): Client for interacting with the blockchain RPC endpoint.
    redis (Redis): Redis client for storing and retrieving data.
    latest_block (Optional[int]): The latest block number fetched from the blockchain.
    sub_workers (List[asyncio.Task]): List of asynchronous tasks for sub-workers.
    max_sub_workers (int): Maximum number of sub-worker tasks.
    block_queue (asyncio.Queue): Queue for storing block numbers to be processed.
    stop_event (asyncio.Event): Event to signal when to stop processing.
    polling_interval (int): Interval (in seconds) to wait between polling for the latest
                            block number.
    chain_id (str): Identifier for the blockchain being processed.

    Methods:
        start() -> None:
        update_config() -> None:
        dispatch_blocks() -> None:
        sub_worker() -> None:
        process_block(block_number: int) -> None:
        _get_transactions(block_number: int) -> List[Dict[str, Any]]:
        merge_transactions_receipts(tx: Dict, receipts: Dict) -> List[Transaction]:
        stop() -> None:
    """

    def __init__(self, config: ChainConfig, redis: Redis) -> None:
        self.config = config
        self.rpc_client = RPCClient(config.rpc_endpoint, config.chain_id)
        self.redis = redis
        self.last_queued_block = config.start_block
        self.sub_workers: List[asyncio.Task] = []
        self.max_sub_workers = 10
        self.stop_event = asyncio.Event()
        self.polling_interval = config.block_time
        self.chain_id = config.chain_id

        # Maximum number of blocks to process in a single range
        self.max_blocks_per_range = 100  # You can adjust this as needed

        # Queue holds (start_block, end_block) tuples
        self.block_queue: asyncio.Queue[Tuple[int, int]] = asyncio.Queue(
            settings.max_backlog_size)

        logger.info(f"Initialized ChainWorker for chain {self.chain_id}")

    async def start(self) -> None:
        """
        Asynchronously starts the chain worker service.

        This method performs the following tasks:
        1. Loads the last processed block.
        2. Fetches the latest block number at startup.
        3. Creates and dispatches a task to handle block dispatching.
        4. Creates and starts sub-worker tasks based on the `max_sub_workers` attribute.

        Returns:
            None
        """
        _ = asyncio.create_task(self.dispatch_blocks())  # noqa: RUF006
        for id in range(self.max_sub_workers):
            worker = asyncio.create_task(self.sub_worker(id))
            self.sub_workers.append(worker)

    async def update_config(self, block: int) -> None:
        """
        Asynchronously saves the last processed block number to Redis.

        This method stores the last processed block number for the current chain
        in a Redis key-value store. The key is formatted as "last_block:{chain_id}"
        and the value is the hex representation of the last processed block number.

        Returns:
            None
        """
        config = self.config
        config.start_block = block
        await self.redis.set(
            RedisKeys.chain_config(self.chain_id),
            config.model_dump_json(),
        )

    async def dispatch_blocks(self) -> None:
        """Asynchronously dispatches ranges of blocks to be processed."""

        while not self.stop_event.is_set():
            logger.info(f"Dispatching blocks for chain {self.chain_id}")
            try:
                latest_block = await self.rpc_client.get_latest_block_number()
                logger.info(f"Fetched latest block: {latest_block}")

                if latest_block <= self.last_queued_block:
                    await asyncio.sleep(self.polling_interval)
                    continue

                start = self.last_queued_block + 1
                end = latest_block
                total_new_blocks = end - start + 1

                logger.info(
                    f"Adding {total_new_blocks} blocks from {start} to {end}",
                )

                # Split into ranges of max_blocks_per_range
                current_start = start
                while current_start <= end:
                    current_end = min(
                        current_start + self.max_blocks_per_range - 1, end)
                    await self.block_queue.put((current_start, current_end))
                    current_start = current_end + 1

                self.last_queued_block = latest_block
                logger.info(f"Queue size: {self.block_queue.qsize()}")

                await asyncio.sleep(self.polling_interval)

            except Exception as exc:
                logger.error(
                    f"Error in dispatch_blocks for {self.chain_id}: {exc}", exc_info=True)  # noqa
                await asyncio.sleep(self.polling_interval)

    async def sub_worker(self, id: int) -> None:
        """
        Asynchronous worker method that processes blocks from a queue.

        This method runs in a loop until the `stop_event` is set. It retrieves block
        numbers from the `block_queue`, processes them, and updates the last processed
        block.

        Exceptions are handled to ensure the worker continues running unless explicitly
        cancelled.

        Raises:
            asyncio.CancelledError: If the worker is cancelled.
            Exception: For any other exceptions that occur during block processing.
        """
        worker_id = f"Worker {self.chain_id}-{id}"
        while not self.stop_event.is_set():
            try:

                start, stop = await self.block_queue.get()
                logger.info(f"{worker_id} got block range: {start} - {stop}")
                await self.process_blocks(start, stop, id)
                self.block_queue.task_done()
                logger.info(f"{worker_id} processed: {start} - {stop}")
                await self.update_config(stop)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Error in sub_worker: {exc}", exc_info=True)
                self.block_queue.task_done()

    async def process_block(self, block_number: int, id: int) -> None:
        """
        Processes a block by its block number.

        This method retrieves the transactions and receipts for the given block number,
        merges them, and then adds each merged transaction to a Redis stream.

        Args:
            block_number (int): The number of the block to process.

        Returns:
            None
        """

        worker_id = f"Worker {self.chain_id}-{id}"

        transactions, timestamp = await self._get_transactions(block_number)

        receipts = await self.rpc_client.get_block_receipts(block_number)

        transactions_dict = {tx["hash"]: tx for tx in transactions}

        receipts_dict = {
            receipt["transactionHash"]: receipt
            for receipt in receipts
        }

        merged_transactions = self._merge_transactions_receipts(
            transactions_dict,
            receipts_dict,
        )

        # add each transaction in merged_transactions to redis stream
        for tx in merged_transactions:
            try:
                tx_dump = tx.model_dump_json(by_alias=True)

                await self.redis.xadd(
                    RedisKeys.stream_key,
                    {"tx": tx_dump},
                )
            except Exception as exc:
                logger.error(
                    f"{worker_id} error adding transaction to stream: {exc}")

        await self.redis.rpush(
            RedisKeys.processed_blocks, block_number)  # type: ignore[misc]

    async def process_blocks(self, start: int, stop: int, id: int) -> None:
        """
        Processes a block by its block number.

        This method retrieves the transactions and receipts for the given block number,
        merges them, and then adds each merged transaction to a Redis stream.

        Args:
            block_number (int): The number of the block to process.

        Returns:
            None
        """

        worker_id = f"Worker {self.chain_id}-{id}"

        transactions = await self._get_transactions_batch(start, stop)
        receipts = await self._get_receipts_batch(start, stop)

        merged_transactions = self._merge_transactions_receipts(
            transactions,
            receipts,
        )

        # add each transaction in merged_transactions to redis stream
        for tx in merged_transactions:
            try:
                tx_dump = tx.model_dump_json(by_alias=True)

                await self.redis.xadd(
                    RedisKeys.stream_key,
                    {"tx": tx_dump},
                )
            except Exception as exc:
                logger.error(
                    f"{worker_id} error adding transaction to stream: {exc}")

        for block in range(start, stop + 1):
            await self.redis.rpush(
                RedisKeys.processed_blocks, block)  # type: ignore[misc]

    async def _get_transactions(
            self,
            block_number: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Asynchronously retrieves transactions for a given block number.

        Args:
            block_number (int): The block number to retrieve transactions for.

        Returns:
            List[Dict]: A list of transactions in the specified block.
                        Each transaction is represented as a dictionary.
        """
        block = await self.rpc_client.get_block_by_number(
            block_number,
            full_transactions=True,
        )
        return block.get("transactions", []), block.get("timestamp", 0)

    async def _get_transactions_batch(
            self,
            start: int,
            stop: int,
    ) -> Dict[str, Any]:
        """
        Asynchronously retrieves transactions for a given block number.

        Args:
            block_number (int): The block number to retrieve transactions for.

        Returns:
            List[Dict]: A list of transactions in the specified block.
                        Each transaction is represented as a dictionary.
        """
        blocks = await self.rpc_client.get_block_by_number_batch(
            start,
            stop,
            full_transactions=True,
        )

        txns = []
        for block in blocks:
            for tx in block.get("transactions", []):
                tx.update({"timestamp": block.get("timestamp", 0)})
            txns.extend(block.get("transactions", []))

        return {tx["hash"]: tx for tx in txns}

    async def _get_receipts_batch(
            self,
            start: int,
            stop: int,
    ) -> Dict[str, Any]:
        receipts = await self.rpc_client.get_block_receipts_batch(start, stop)

        return {tx["transactionHash"]: tx for tx in chain.from_iterable(receipts)}

    def _merge_transactions_receipts(
        self,
        txs: Dict[str, Dict[str, Any]],
        receipts: Dict[str, Dict[str, Any]],
    ) -> List[Transaction]:
        """
        Merges transaction data with their corresponding receipts and adds the chain ID.

        Args:
            tx (Dict[str, Dict[str, Any]]): A dictionary where the keys are transaction
                                            hashes and the values are dictionaries
                                            containing transaction data.
            receipts (Dict[str, Dict[str, Any]]): A dictionary where the keys are
                                                  transaction hashes and the values are
                                                  dictionaries containing receipt data.

        Returns:
            List[Transaction]: A list of dictionaries, each containing merged
                                  transaction and receipt data along with the chain ID.
        """
        # logger.info("Merging transactions and receipts")
        merged_txs = [
            txs[hsh]
            | receipts[hsh]
            | {"chainId": hex(self.chain_id)} for hsh in txs
        ]
        # logger.info("Merged transactions and receipts")

        # logger.info("Validating transactions")
        validated_tx = []
        for tx in merged_txs:
            try:
                validated_tx.append(Transaction.model_validate(tx))
            except Exception as exc:
                _hash = tx.get("hash") or tx.get("transactionHash")

                logger.error(f"Error validating transaction:  {_hash}: {exc}")
                # logger.error(f"Erroneous transaction merged: {tx}")
                # logger.error(f"Erroneous transaction: {txs.get(_hash)}")
                # logger.error(f"Erroneous receipt: {receipts.get(_hash)}")
                continue
        # logger.info("Validated transactions")

        return validated_tx

    async def stop(self) -> None:
        """
        Stops the chain worker and performs necessary cleanup operations.

        This method sets the stop event, waits for the block queue to be fully processed
        then cancels all sub-workers,  and gathers their results. It also closes the RPC
        client and Redis connections, and saves the last processed block.

        Returns:
            None
        """
        self.stop_event.set()
        await self.block_queue.join()
        for worker in self.sub_workers:
            worker.cancel()
        await asyncio.gather(*self.sub_workers, return_exceptions=True)
        await self.rpc_client.close()
