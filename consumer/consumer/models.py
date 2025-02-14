# service/models.py
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field

from consumer.utils import HexInt


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


class LogEntry(BaseModel):
    """
    LogEntry model representing a log entry in a blockchain transaction.

    Attributes:
        address (str): The address associated with the log entry.
        topics (List[str]): A list of topics related to the log entry.
        data (str): The data contained in the log entry.
        block_number (HexInt): The block number where the log entry is found.
        transaction_hash (str): The hash of the transaction containing the log entry.
        transaction_index (HexInt): The index of the transaction within the block.
        block_hash (str): The hash of the block containing the log entry.
        log_index (HexInt): The index of the log entry within the block.
        removed (bool): Indicates if the log entry has been removed.

    Properties:
        topic0 (Optional[str]): The first topic in the topics list.
    """

    address: str
    topics: List[str]
    data: str
    block_number: HexInt = Field(alias="blockNumber")
    transaction_hash: str = Field(alias="transactionHash")
    transaction_index: HexInt = Field(alias="transactionIndex")
    block_hash: str = Field(alias="blockHash")
    log_index: HexInt = Field(alias="logIndex")
    removed: bool
    args: Dict[str, Any] = {}  # Decoded log arguments
    event: Optional[str] = None  # Event name

    @computed_field  # type: ignore[misc]
    @property
    def topic0(self) -> Optional[str]:
        """
        Returns the first topic in the topics list if it exists.

        Returns:
            Optional[str]: The first topic in the topics list, or None if it is empty.
        """
        return self.topics[0] if self.topics else None


class Transaction(BaseModel):
    """
    TransactionReceipt represents the receipt of a transaction on the blockchain.

    Attributes:
        hash (str): The hash of the transaction.
        block_number (HexInt): The block number in which the transaction was included.
        from_address (str): The address from which the transaction was sent.
        gas (HexInt): The amount of gas provided by the sender.
        gas_price (HexInt): The price of gas for the transaction.
        input (str): The input data sent with the transaction.
        nonce (HexInt): The number of transactions sent from the sender's address.
        to (str): The address to which the transaction was sent.
        transaction_index (HexInt): The index position of the transaction in the block.
        value (HexInt): The value transferred in the transaction.
        type (HexInt): The type of the transaction.
        chain_id (HexInt): The chain ID of the blockchain.
        v (HexInt): The recovery id of the transaction.
        r (str): The r value of the transaction signature.
        s (str): The s value of the transaction signature.
        contract_address (Optional[str]): The address of the contract created, if any.
        cumulative_gas_used (HexInt): The total gas used upto this transaction.
        effective_gas_price (HexInt): The effective gas price for the transaction.
        gas_used (HexInt): The amount of gas used by the transaction.
        logs (List[LogEntry]): The logs generated by the transaction.
        logs_bloom (str): The bloom filter for the logs of the transaction.
        status (HexInt): The status of the transaction (1 for success, 0 for failure).
    """

    hash: str
    block_number: HexInt = Field(alias="blockNumber")
    from_address: str = Field(alias="from")
    gas: HexInt
    gas_price: HexInt = Field(alias="gasPrice")
    input: str
    decoded_input: Dict[str, Any] = {}  # Decoded input data
    nonce: HexInt
    to: Optional[str]
    # disable transaction_index: HexInt = Field(alias="transactionIndex")
    value: HexInt
    type: HexInt
    chain_id: HexInt = Field(alias="chainId")
    # disable v: HexInt
    # disable r: str
    # disable s: str
    contract_address: Optional[str] = Field(alias="contractAddress")
    cumulative_gas_used: HexInt = Field(alias="cumulativeGasUsed")
    effective_gas_price: HexInt = Field(alias="effectiveGasPrice")
    gas_used: HexInt = Field(alias="gasUsed")
    # disable l1_base_fee_scalar: HexInt = Field(alias="l1BaseFeeScalar")
    # disable l1_blob_base_fee: HexInt = Field(alias="l1BlobBaseFee")
    # disable l1_blob_base_fee_scalar: HexInt = Field(alias="l1BlobBaseFeeScalar")
    # disable l1_fee: HexInt = Field(alias="l1Fee")
    # disable l1_gas_price: HexInt = Field(alias="l1GasPrice")
    # disable l1_gas_used: HexInt = Field(alias="l1GasUsed")
    logs: List[LogEntry]
    # disable logs_bloom: str = Field(alias="logsBloom")
    status: HexInt
    timestamp: HexInt
