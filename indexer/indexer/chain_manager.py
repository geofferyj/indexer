import asyncio
import json
from typing import Any, Dict, List

from loguru import logger
from redis import RedisError
from redis.asyncio import Redis

from indexer.chain_worker import ChainWorker
from indexer.config import settings
from indexer.models import ChainConfig, Command
from indexer.utils.redis import RedisKeys


class ChainManager:
    """
    Manages a collection of ChainWorker instances and handles commands via Redis.

    ChainManager is a class responsible for managing multiple chain workers and handling
    commands via a Redis pub/sub channel. It provides methods to start and stop the
    service, add and remove chains, list chain configurations, and retrieve the status
    of all chains.

    Methods:
        __init__(redis_url: str) -> None:
            Initializes the ChainManager instance with the provided Redis URL.
        start() -> None:
            Asynchronously starts the chain manager service by initializing a Redis
            connection and creating a task to listen for commands.
        stop() -> None:
            Asynchronously stops the chain manager service by closing the Redis
            connection and stopping all chain workers.
        listen_for_commands() -> None:
            Asynchronously listens for commands on a Redis pub/sub channel and handles
            incoming messages.
        handle_command(message_data: str) -> None:
            Processes incoming command messages, invokes the corresponding method, and
            publishes the response to the specified response channel.
        add_chain(config: Dict[str, str]) -> Dict[str, str]:
            Adds a new chain to the chain manager using the provided configuration.
            Raises an exception if a chain with the same chain_id already exists.
        remove_chain(data: Dict[str, str]) -> None:
            Asynchronously removes a chain from the chain manager based on the provided
            chain_id. Returns the status of the operation.
        list_chains(_: Dict[str, str]) -> List[Dict[str, Any]]:
            Lists all chain configurations managed by the chain manager.
        _load_chains() -> None:
            Loads chain configurations from Redis and initializes ChainWorker instances
    """

    def __init__(self, redis_url: str) -> None:
        """
        Initializes the ChainManager instance.

        Args:
            redis_url (str): The URL of the Redis server.

        Attributes:
            chains (Dict[str, ChainWorker]): A dictionary to store chain workers.
            redis_url (str): The URL of the Redis server.
            lock (asyncio.Lock): An asyncio lock to manage concurrent access.
            redis: The Redis client instance (initialized as None).
        """
        self.chains: Dict[int, ChainWorker] = {}
        self.redis_url = redis_url
        self.lock = asyncio.Lock()

    async def start(self) -> None:
        """
        Asynchronously starts the chain manager service.

        This method initializes a Redis connection using the provided Redis URL
        and starts listening for commands by creating an asyncio task.

        Raises:
            RedisError: If there is an issue connecting to the Redis server.
        """
        self.redis = await Redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

        if await self.redis.ping():
            logger.info("Connected to Redis")
        else:
            raise RedisError("Could not connect to Redis")
        asyncio.create_task(self.listen_for_commands())  # noqa: RUF006
        await self._load_chains()

    async def stop(self) -> None:
        """
        Asynchronously stops the chain manager service.

        This method performs the following actions:
        1. Closes the Redis connection.
        2. Iterates through all chain workers and stops each one.

        Returns:
            None
        """
        await self.redis.close()
        for worker in self.chains.values():
            await worker.stop()

    async def listen_for_commands(self) -> None:
        """
        Asynchronously listens for commands on a Redis pub/sub channel.

        This method subscribes to the Redis pub/sub channel specified in the settings
        and listens for incoming messages. When a message of type "message" is received,
        it calls the handle_command method with the message data.

        Returns:
            None
        """
        logger.info("Starting command listener")
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(settings.command_channel)
        logger.info(f"Subscribed to {settings.command_channel}")
        logger.info("Commands listener started")
        async for message in pubsub.listen():
            logger.info(f"Received message: {message}")
            if message["type"] == "message":
                await self.handle_command(message["data"])

    async def handle_command(self, message_data: str) -> None:
        """
        Handle incoming command messages.

        This method processes a JSON-encoded message, extracts the command and data,
        and invokes the corresponding method on the instance. The response from the
        invoked method is then published to the specified response channel.
        Args:
            message_data (str): A JSON-encoded string containing the command, data,
                                and response channel.
        Raises:
            AttributeError: If the command does not correspond to any method on the
                            instance.
            Exception: If there is an error publishing the response.
        Example message_data format:
            {
                "command": "some_command",
                "data": {...},
                "response_channel": "some_channel"
            }
        """

        try:
            message = Command.model_validate_json(message_data)
        except Exception as exc:
            logger.error(f"Invalid message: {exc}")
            return

        command = message.command
        data = message.data
        response_channel = message.response_channel

        try:
            response = await getattr(self, command)(data)
        except AttributeError:
            logger.error(f"Unknown command: {command}")
            response = {"error": "Unknown command"}
        except Exception as exc:
            logger.error(f"Error processing command: {exc}")
            response = {"error": "Error processing command"}

        try:
            await self.redis.publish(response_channel, json.dumps(response))
        except Exception as exc:
            logger.error(f"Error publishing response: {exc}")
            return

    async def add_chain(self, config: Dict[str, Any]) -> Dict[str, str]:
        """
        Add a new chain to the chain manager.

        This method adds a new chain to the chain manager using the provided
        configuration.
        If a chain with the same chain_id already exists, an exception is raised.

        Args:
            config (Dict[str, str]): A dictionary containing the configuration for
            the new chain.
                The dictionary must include a "chain_id" key.

        Raises:
            Exception: If a chain with the same chain_id already exists.

        Returns:
            Dict[str, str]: A dictionary containing the status of the operation.
        """
        async with self.lock:
            _config = ChainConfig.model_validate(config)
            if _config.chain_id in self.chains:
                return {"error": "Chain already exists."}
            worker = ChainWorker(_config, self.redis)
            self.chains[config["chain_id"]] = worker
            asyncio.create_task(worker.start())  # noqa: RUF006

            await self.redis.sadd(RedisKeys.chains, config["chain_id"])
            await self.redis.set(
                RedisKeys.chain_config(_config.chain_id),
                json.dumps(config),
            )

        return {"status": "Chain added successfully."}

    async def remove_chain(self, data: Dict[str, str]) -> Dict[str, str]:
        """
        Asynchronously removes a chain from the chain manager.

        Args:
            data (Dict[str, str]): A dictionary containing the chain information.
                                   Must include the key "chain_id".

        Returns:
            Dict[str, str]: A dictionary with the status of the operation.
                            If the chain ID is not provided, returns an error message.
                            If the chain is successfully removed, returns success.

        Raises:
            Exception: If the chain with the given chain_id is not found.
        """

        if data.get("chain_id") is None:
            return {"error": "Chain ID not provided."}

        chain_id = int(data["chain_id"])
        async with self.lock:

            if chain_id not in self.chains:
                return {"error": "Chain not found."}
            worker = self.chains.pop(chain_id)
            await worker.stop()
            await self.redis.srem(RedisKeys.chains, chain_id)
            await self.redis.delete(RedisKeys.chain_config(chain_id))
        return {"status": "Chain removed successfully."}

    async def list_chains(self, _: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        List all chain configurations.

        Args:
            _ (Dict[str, str]): A dictionary parameter that is not used in this method.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing
                                  the configuration of a chain.
        """
        return [
            ChainConfig(
                chain_id=worker.config.chain_id,
                rpc_endpoint=worker.config.rpc_endpoint,
                block_time=worker.config.block_time,
                start_block=worker.config.start_block,
            ).model_dump()
            for worker in self.chains.values()
        ]

    async def _load_chains(self) -> None:
        """
        Load chain configurations from Redis.

        This method retrieves chain configurations from Redis and initializes
        ChainWorker instances for each chain. It is called when the ChainManager
        instance is created to restore the previous state.
        """
        logger.info("Loading chains from Redis")
        chain_ids = await self.redis.smembers(RedisKeys.chains)
        logger.info(f"Found chains: {chain_ids}")
        chain_configs = [
            await self.redis.get(RedisKeys.chain_config(chain_id))
            for chain_id in chain_ids
        ]
        for config in chain_configs:
            if config is None:
                continue
            await self.add_chain(json.loads(config))
        logger.info("Chains loaded")
