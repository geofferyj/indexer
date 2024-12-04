import asyncio
import time
from typing import Any, Dict, List, Optional

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
        self.last_processed_block = config.start_block
        self.latest_block: Optional[int] = None
        self.sub_workers: List[asyncio.Task] = []
        self.max_sub_workers = 10
        self.block_queue: asyncio.Queue[int] = asyncio.Queue(settings.max_backlog_size)
        self.stop_event = asyncio.Event()
        self.polling_interval = config.block_time
        self.chain_id = config.chain_id

        # logger.info(f"Initialized ChainWorker for chain {self.chain_id}")

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
        self.latest_block = await self.rpc_client.get_latest_block_number()
        # logger.info(f"Latest block at startup: {self.latest_block}")

        _ = asyncio.create_task(self.dispatch_blocks())  # noqa: RUF006
        for id in range(self.max_sub_workers):
            worker = asyncio.create_task(self.sub_worker(id))
            self.sub_workers.append(worker)

    async def update_config(self) -> None:
        """
        Asynchronously saves the last processed block number to Redis.

        This method stores the last processed block number for the current chain
        in a Redis key-value store. The key is formatted as "last_block:{chain_id}"
        and the value is the hex representation of the last processed block number.

        Returns:
            None
        """
        config = self.config
        config.start_block = self.last_processed_block
        await self.redis.set(
            RedisKeys.chain_config(self.chain_id),
            config.model_dump_json(),
        )

        # logger.info(f"Updated config for chain {self.chain_id}")

    async def dispatch_blocks(self) -> None:
        """
        Asynchronously dispatches blocks to be processed.

        This method continuously fetches the latest block number from the RPC client
        and queues block numbers for processing. It runs in a loop until the stop_event
        is set. If an error occurs, it waits for the polling interval before retrying.

        Attributes:
            latest_block (int): The latest block number fetched from the RPC client.
            last_processed_block (int): The last block number that was processed.
            stop_event (asyncio.Event): An event to signal when to stop the loop.
            rpc_client (RpcClient): The RPC client used to fetch the block data.
            block_queue (asyncio.Queue): The queue to which block numbers are added.
            polling_interval (int): The interval (in seconds) to wait between polling
                                    for the latest block number.
            chain_id (str): The identifier for the blockchain being processed.
        """
        while not self.stop_event.is_set():
            logger.info(f"Dispatching blocks for chain {self.chain_id}")
            logger.info(f"Last processed block: {self.last_processed_block}")
            logger.info(f"Latest block: {self.latest_block}")
            try:
                # Only fetch the latest block if we're caught up
                if (
                    self.latest_block is None
                    or self.last_processed_block >= self.latest_block
                ):  # noqa: E501
                    self.latest_block = await self.rpc_client.get_latest_block_number()

                    logger.info(f"Fetched latest block: {self.latest_block}")

                    logger.info(
                        f"Adding blocks {self.last_processed_block + 1} - {self.latest_block + 1} to queue"
                    )
                    # Process blocks up to the latest_block
                    if self.latest_block >= self.last_processed_block:
                        for block_number in range(
                            self.last_processed_block + 1,
                            self.latest_block + 1,
                        ):
                            await self.block_queue.put(block_number)

                logger.info(f"Queue size: {self.block_queue.qsize()}")

                await asyncio.sleep(self.polling_interval)
            except Exception as exc:

                logger.error(f"Error in dispatch_blocks for {self.chain_id}: {exc}")
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

                block_number = await self.block_queue.get()
                logger.info(f"{worker_id} got: {block_number}")
                await self.process_block(block_number, id)
                self.block_queue.task_done()
                logger.info(f"{worker_id} processed: {block_number}")
                self.last_processed_block = block_number
                await self.update_config()

            except asyncio.CancelledError:
                break
            except Exception as exc:
                # logger.error(f"Error in sub_worker: {exc}", exc_info=True)
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
        # logger.info(f"{worker_id} processing block: {block_number}")
        transactions = await self.rpc_client.get_block_transactions(block_number)
        # logger.info(f"{worker_id} got {len(transactions)} transactions for block {block_number}")
        receipts = await self.rpc_client.get_block_receipts(block_number)
        # logger.info(f"{worker_id} got {len(receipts)} receipts for block {block_number}")

        transactions_dict = {tx["hash"]: tx for tx in transactions}
        # logger.info(f"{worker_id} got transactions_dict block {block_number}")
        receipts_dict = {receipt["transactionHash"]: receipt for receipt in receipts}
        # logger.info(f"{worker_id} got receipts_dict block {block_number}")

        s_time = time.time()
        merged_transactions = self.merge_transactions_receipts(
            transactions_dict,
            receipts_dict,
        )
        e_time = time.time()
        # logger.info(f"Time taken to merge transactions: {e_time - s_time}")
        # logger.info(f"{worker_id} merged transactions for block {block_number}")

        # add each transaction in merged_transactions to redis stream
        for tx in merged_transactions:
            try:
                tx_dump = tx.model_dump_json(by_alias=True)

                # logger.info(f"{worker_id} adding transaction to stream: {tx.hash}")
                res = await self.redis.xadd(
                    RedisKeys.stream_key,
                    {"tx": tx_dump},  # type: ignore
                )
                # logger.info(f"{worker_id} added transaction to stream: {res}")
            except Exception as exc:
                logger.error(f"{worker_id} error adding transaction to stream: {exc}")
                pass

    async def _get_transactions(self, block_number: int) -> List[Dict[str, Any]]:
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
        return block.get("transactions", [])

    def merge_transactions_receipts(
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
            txs[hsh] | receipts[hsh] | {"chainId": hex(self.chain_id)} for hsh in txs
        ]
        # logger.info("Merged transactions and receipts")

        # logger.info("Validating transactions")
        validated_tx = []
        for tx in merged_txs:
            try:
                validated_tx.append(Transaction.model_validate(tx))
            except Exception as exc:
                _hash: Optional[str] = tx.get("hash") or tx.get("transactionHash")

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
        await self.update_config()
