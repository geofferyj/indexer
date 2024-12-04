# sdk/models.py
from pydantic import BaseModel


class ChainConfig(BaseModel):
    """
    ChainConfig is a model representing the configuration for a blockchain.

    Attributes:
        chain_id (str): The unique identifier for the blockchain.
        rpc_endpoint (str): The RPC endpoint URL for connecting to the blockchain.
        block_time (int): The block time in seconds.
    """

    chain_id: str
    rpc_endpoint: str
    block_time: int  # Block time in seconds
