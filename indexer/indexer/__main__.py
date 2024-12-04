# service/main.py
import asyncio

from loguru import logger

from indexer.chain_manager import ChainManager
from indexer.config import settings


async def main() -> None:
    """
    Main entry point for the service.

    This function initializes the ChainManager with the provided redis_url from settings
    starts the ChainManager, and keeps the service running indefinitely by sleeping for
    one hour intervals. The service can be gracefully stopped with a KeyboardInterrupt.

    Returns:
        None
    """
    logger.info("Starting chain manager")
    chain_manager = ChainManager(redis_url=str(settings.redis_url))
    await chain_manager.start()
    logger.info("Chain manager started")
    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        await chain_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
