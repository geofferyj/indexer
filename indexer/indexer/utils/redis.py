from indexer.config import settings


class RedisKeys:
    """
    RedisKeys is a utility class for generating Redis keys used in the application.

    Attributes:
        APP_NAME (str): The name of the application, retrieved from settings.
        stream_key (str): The Redis key for the transaction stream.
        chains (str): The Redis key prefix for blockchain-related data.

    Methods:
        last_block(chain_id: int) -> str:

        chain_config(chain_id: int) -> str:
            Generate the Redis key for the configuration of a specific blockchain.
    """

    APP_NAME = settings.app_name
    stream_key = f"{APP_NAME}:transactions"
    chains = f"{APP_NAME}:chains"
    processed_blocks = f"{APP_NAME}:processed_blocks"

    @staticmethod
    def last_block(chain_id: int) -> str:
        """
        Generate the Redis key for the last processed block of a given blockchain.

        Args:
            chain_id (int): The ID of the blockchain.

        Returns:
            str: The Redis key for the last block of the specified blockchain.
        """
        return f"{RedisKeys.chains}:last_block:{chain_id}"

    @staticmethod
    def chain_config(chain_id: int) -> str:
        """
        Generates a Redis key for the configuration of a specific blockchain.

        Args:
            chain_id (int): The unique identifier of the blockchain.

        Returns:
            str: The Redis key for the blockchain configuration.
        """
        return f"{RedisKeys.chains}:config:{chain_id}"
