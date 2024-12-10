import asyncio
from typing import Any, Dict

import aiohttp
from loguru import logger
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from consumer.models import Transaction
from consumer.utils.redis import RedisKeys


class Consumer:
    """
    Consumer class for reading and processing messages from a Redis stream.

    Attributes:
        block_timeout_ms (int): Max time (ms) to block waiting for messages.
        count (int): Max number of messages to read at once.
        session (aiohttp.ClientSession): HTTP session for sending webhooks.
        redis (Redis): Redis client instance.
    Methods:
        _ensure_consumer_group():
        _send_webhook(data):
        _should_ignore_transaction(tx):
        _process_message(message_id, data):
        run():
    """

    def __init__(
        self,
        redis: Redis,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        webhook_url: str,
        block_timeout_ms: int = 2000,
        count: int = 10,
    ) -> None:
        """
        Initialize the consumer with the given parameters.

        Args:
            redis_url (str): Redis server URL.
            stream_name (str): Name of the Redis stream to consume from.
            group_name (str): Name of the Redis consumer group.
            consumer_name (str): Name of this consumer.
            webhook_url (str): The URL to send transaction data to.
            block_timeout_ms (int, optional): Max time (ms) to block waiting for msgs.
            count (int, optional): Max number of messages to read at once.
        """
        self.redis = redis
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.webhook_url = webhook_url
        self.block_timeout_ms = block_timeout_ms
        self.count = count
        self.idle_ms = 10000

        self.session = aiohttp.ClientSession()

    async def _ensure_consumer_group(self) -> None:
        """
        Ensures that the consumer group exists for the specified stream.

        This method attempts to create a consumer group for the given stream name.
        If the group already exists, it ignores the "BUSYGROUP" error. Any other
        errors are raised.
        Raises:
            ResponseError: If an error occurs while creating the consumer group,
                        except for "BUSYGROUP" errors.
        """

        try:
            await self.redis.xgroup_create(
                self.stream_name, self.group_name, id="0", mkstream=True,
            )
        except ResponseError as e:
            # Ignore "BUSYGROUP" errors, which indicate the group already exists.
            if "BUSYGROUP" not in str(e):
                raise e

    async def _send_webhook(self, data: Dict[str, Any]) -> None:
        """
        Send webhook with the given data to the specified webhook URL.

        Args:
            data (dict): The transaction data to send.
        """
        try:
            async with self.session.post(self.webhook_url, json=data) as response:
                logger.info(
                    f"{self.consumer_name}: Webhook response status: {response.status}")
        except Exception as e:
            logger.error(f"{self.consumer_name}: Error sending webhook: {e}")

    async def _process_message(self, message_id: str, data: Dict[str, Any]) -> None:
        """
        Process a single message from the stream.

        For simplicity:
        - Extract 'tx' field from data and validate as a Transaction.
        - Check if it should be ignored.
        - If not ignored, send it to the webhook.
        - Acknowledge and delete from Redis.

        Args:
            message_id (str): The ID of the Redis stream message.
            data (dict): The message fields.
        """
        try:
            tx = Transaction.model_validate_json(data["tx"])
        except Exception as e:
            logger.error(
                f"{self.consumer_name}: Error validating transaction: {e}")

            logger.info(f"{self.consumer_name}: error in tx: {data}")
            await self.redis.xack(self.stream_name, self.group_name, message_id)
            await self.redis.xdel(self.stream_name, message_id)
            return

        # If not ignored, send to the webhook
        await self._send_webhook(tx.model_dump(mode="json"))

        # Acknowledge and delete the message after processing
        await self.redis.xack(self.stream_name, self.group_name, message_id)
        await self.redis.xdel(self.stream_name, message_id)

    async def _reclaim_pending_messages(self) -> None:
        """
        Reclaim pending messages that have been idle longer than `self.idle_ms`.

        Uses XAUTOCLAIM to claim pending messages back to the current consumer after
        they've been idle, and reprocesses them to ensure they are not stuck pending
        indefinitely.
        """
        # XAUTOCLAIM returns messages along with a new start ID for subsequent calls.
        start_id = "0-0"
        while True:
            # XAUTOCLAIM: Returns a tuple: (new_start_id, [ (message_id, {fields}),...])
            result = await self.redis.xautoclaim(
                self.stream_name,
                self.group_name,
                self.consumer_name,
                min_idle_time=self.idle_ms,
                start_id=start_id,
                count=self.count,
            )
            if not result:
                break

            new_start_id, messages = result[0], result[1]
            if not messages:
                break

            # Process each reclaimed message
            for message_id, msg_data in messages:
                await self._process_message(message_id, msg_data)

            # Update start_id for the next iteration in case there are more pending msgs
            start_id = new_start_id

    async def run(self) -> None:
        """
        Continuously read and process messages from the Redis stream.

        Steps:
        - Ensure consumer group exists.
        - Use XREADGROUP to read new messages.
        - Process each message.
        - If no messages, wait briefly and retry.
        """
        await self._ensure_consumer_group()

        logger.info(f"{self.consumer_name} started consuming...")

        try:
            while True:
                await self._reclaim_pending_messages()

                messages = await self.redis.xreadgroup(
                    groupname=self.group_name,
                    consumername=self.consumer_name,
                    streams={self.stream_name: ">"},
                    count=self.count,
                    block=self.block_timeout_ms,
                )

                if not messages:
                    # No new messages, wait a bit.
                    await asyncio.sleep(1)
                    continue

                for _, msg_list in messages:
                    for message_id, msg_data in msg_list:
                        await self._process_message(message_id, msg_data)

        except asyncio.CancelledError:
            logger.error(f"{self.consumer_name} consumer loop cancelled.")
        except Exception as e:
            logger.error(f"{self.consumer_name} consumer loop error: {e}")
        finally:
            await self.session.close()
