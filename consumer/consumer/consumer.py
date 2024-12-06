import asyncio
import logging
from typing import Any, Dict

import redis.asyncio as aioredis

logging.basicConfig(level=logging.INFO)

class Consumer:
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        stream_name: str = "mystream",
        group_name: str = "mygroup",
        consumer_name: str = "consumer1",
        block_timeout_ms: int = 2000,
        count: int = 10,
        trim_len: int = 10000,
        delete_after_ack: bool = True,
    ):
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.block_timeout_ms = block_timeout_ms
        self.count = count
        self.trim_len = trim_len
        self.delete_after_ack = delete_after_ack

        # Connect to Redis
        self.redis = aioredis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    async def _ensure_consumer_group(self):
        # Create a consumer group if it doesn't exist.
        # MKSTREAM ensures the stream is created if it doesn't exist yet.
        try:
            await self.redis.xgroup_create(self.stream_name, self.group_name, id='0', mkstream=True)
            logging.info(f"Consumer group '{self.group_name}' created on stream '{self.stream_name}'")
        except aioredis.exceptions.ResponseError as e:
            # This happens if the group already exists - ignore this error
            if "BUSYGROUP" in str(e):
                logging.info(f"Consumer group '{self.group_name}' already exists.")
            else:
                raise e

    async def process(self, message_id: str, data: Dict[str, Any]) -> None:
        """
        Process a single message from the stream.

        message_id: str - The Redis stream message ID.
        data: dict     - The message content (field-value pairs).

        This method should be overridden or expanded to handle your message logic.
        """
        logging.info(f"Processing message_id={message_id}, data={data}")
        # ... your async business logic here ...
        # For example, decode the transaction, process it, update your database, etc.
        await asyncio.sleep(0.1)  # Simulate async processing

    async def run(self):
        """
        Continuously poll the Redis stream for new messages, process them, acknowledge,
        and optionally delete them. If needed, also trim the stream to prevent it from
        growing indefinitely.
        """
        await self._ensure_consumer_group()
        logging.info("Starting consumer loop...")
        while True:
            # Read messages via XREADGROUP
            # '>' means read only messages that were never delivered to another consumer in this group.
            messages = await self.redis.xreadgroup(
                groupname=self.group_name,
                consumername=self.consumer_name,
                streams={self.stream_name: '>'},
                count=self.count,
                block=self.block_timeout_ms
            )

            if not messages:
                # No new messages
                await asyncio.sleep(1)
                continue

            for (stream, msg_list) in messages:
                for message_id, data in msg_list:
                    try:
                        # Process the message
                        await self.process(message_id, data)
                        # Acknowledge the message so it's not considered pending
                        await self.redis.xack(self.stream_name, self.group_name, message_id)

                        # Optionally delete the message from the stream
                        if self.delete_after_ack:
                            await self.redis.xdel(self.stream_name, message_id)
                    except Exception as e:
                        # If processing fails, don't ack or delete the message.
                        # It will remain pending, and can be retried or claimed by another consumer.
                        logging.error(f"Error processing message {message_id}: {e}", exc_info=True)

            # Optionally trim the stream to keep it manageable
            # This removes older messages, retaining only the last `trim_len` entries
            if self.trim_len > 0:
                await self.redis.xtrim(self.stream_name, maxlen=self.trim_len, approximate=True)
