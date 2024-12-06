# service/main.py
import asyncio

from loguru import logger

from consumer.consumer.consumer import Consumer


async def main():
    consumer = Consumer(
        redis_host="localhost",
        redis_port=6379,
        stream_name="mystream",
        group_name="mygroup",
        consumer_name="consumer1",
        block_timeout_ms=2000,
        count=10,
        trim_len=10000,          # Adjust if you want a different max length
        delete_after_ack=True    # Set to False if you want to keep the history
    )

    await consumer.run()

if __name__ == "__main__":
    asyncio.run(main())
