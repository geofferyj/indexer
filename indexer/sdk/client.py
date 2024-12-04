import json
import uuid
from typing import Any, Dict

from redis.asyncio import Redis

from sdk.models import ChainConfig

response_channel_prefix = "indexer:responses:"
command_channel = "indexer:commands"


class IndexerClient:
    """
    A client for interacting with the indexer service via Redis.

    Attributes:
        redis_url (str): The URL of the Redis server.
        redis (Redis): The Redis connection instance.

    Methods:
        __init__(redis_url: str = settings.redis_url):
            Initializes the IndexerClient with the given Redis URL.

        connect():
            Establishes a connection to the Redis server.

        disconnect():
            Closes the connection to the Redis server.

        send_command(command: str, data: dict) -> dict:
            Sends a command to the indexer service and waits for a response.

        add_chain(config: ChainConfig) -> dict:
            Sends a command to add a new chain with the given configuration.

        remove_chain(chain_id: str) -> dict:
            Sends a command to remove a chain with the given chain ID.

        list_chains() -> dict:
            Sends a command to list all chains.

        get_status() -> dict:
            Sends a command to get the status of the indexer service.
    """

    def __init__(self, redis_url: str) -> None:
        """
        Initializes the client with the given Redis URL.

        Args:
            redis_url (str): The URL of the Redis server.
            Defaults to the value from settings.redis_url.
        """
        self.redis_url = redis_url

    async def connect(self) -> None:
        """
        Asynchronously connects to a Redis server using the provided Redis URL.

        This method initializes a Redis client instance with the specified URL,
        setting the encoding to "utf-8" and enabling response decoding.

        Raises:
            RedisError: If there is an issue connecting to the Redis server.
        """
        self.redis: Redis = await Redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )

    async def disconnect(self) -> None:
        """
        Asynchronously disconnects the client from the Redis server.

        This method closes the connection to the Redis server by calling the
        `close` method on the Redis client instance.

        Returns:
            None
        """
        await self.redis.close()

    async def send_command(self, command: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sends a command to the indexer service through Redis server.

        This method publishes a command and its associated data to a Redis channel,
        then listens for a response on a dynamically generated response channel.

        Args:
            command (str): The command to be sent.
            data (dict): The data associated with the command.

        Returns:
            Dict[str, Any]: The response received from the Redis server.

        Raises:
            Exception: If there is an issue with connecting to Redis
            or processing the response.
        """
        if self.redis is None:
            await self.connect()
        response_channel = f"{response_channel_prefix}{uuid.uuid4()}"
        message = {
            "command": command,
            "data": data,
            "response_channel": response_channel,
        }
        await self.redis.publish(command_channel, json.dumps(message))
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(response_channel)
        async for message in pubsub.listen():
            if message["type"] == "message":
                response = json.loads(message["data"])  # type: ignore
                await pubsub.unsubscribe(response_channel)
                break
        return response

    async def add_chain(self, config: ChainConfig) -> Dict[str, Any]:
        """
        Asynchronously adds a new chain configuration.

        Args:
            config (ChainConfig): The configuration object for the chain to be added.

        Returns:
            Dict[str, Any]: The response from the command execution.
        """
        return await self.send_command("add_chain", config.model_dump())

    async def remove_chain(self, chain_id: str) -> Dict[str, Any]:
        """
        Asynchronously removes a chain with the given chain ID.

        Args:
            chain_id (str): The ID of the chain to be removed.

        Returns:
            Dict[str, Any]: The response from the command indicating the result
                            of the removal.
        """
        return await self.send_command("remove_chain", {"chain_id": chain_id})

    async def list_chains(self) -> Dict[str, Any]:
        """
        Asynchronously lists all available chains.

        Returns:
            Dict[str, Any]: A dictionary containing the list of available chains.
        """
        return await self.send_command("list_chains", {})

    async def get_status(self) -> Dict[str, Any]:
        """
        Asynchronously retrieves the status from the server.

        Returns:
            Dict[str, Any]: A dictionary containing the status information.
        """
        return await self.send_command("get_status", {})
