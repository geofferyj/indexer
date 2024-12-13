# service/models.py
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field



class ChainConfig(BaseModel):
    """
    Configuration model for a blockchain network.

    Attributes:
        chain_id (int): The unique identifier for the blockchain network.
        rpc_endpoint (str): The RPC endpoint URL for connecting to the blockchain.
        block_time (int): The average time in seconds between blocks on the blockchain.
        start_block (int): The block number to start indexing from.
    """

    chain_id: int
    rpc_endpoint: str
    block_time: int
    start_block: int


class Command(BaseModel):
    """
    Represents a command to be executed with associated data and response channel.

    Attributes:
        command (str): The command to be executed.
        data (dict): The data associated with the command.
        response_channel (str): The channel to send the response to.
    """

    command: str
    data: dict
    response_channel: str  # Channel to send the response

