import hashlib
from typing import Any, Dict, Optional

from eth_abi import decode
from eth_utils import keccak


def decode_input(
        input_data: str,
        function_abi: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Decodes Ethereum transaction input data using the exact function ABI.

    Parameters:
        input_data (str): The input data string from the transaction.
        function_abi (dict): The ABI of the specific function as a dictionary.

    Returns:
        dict: A dictionary with decoded function name and parameters if successful.
              Returns None if the input data does not match the function ABI.
    """

    # Decode parameters
    parameter_types = [param["type"] for param in function_abi["inputs"]]
    raw_data = bytes.fromhex(input_data[10:])  # Strip the selector

    try:
        decoded_params = decode(parameter_types, raw_data)
    except Exception as e:
        return {"error": f"Failed to decode parameters: {e}"}

    # Return decoded data
    return {
        "function": function_abi["name"],
        "params": {
            function_abi["inputs"][i]["name"]: decoded_params[i]
            for i in range(len(function_abi["inputs"]))
        },
    }


def decode_log(log_entry: Dict[str, Any], event_abi: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decodes an Ethereum log entry using the given event ABI.

    Parameters:
        log_entry (dict): A log entry dictionary with "topics" and "data".
        event_abi (dict): The ABI of the specific event as a dictionary.

    Returns:
        dict: A dictionary with decoded event name and parameters if successful.
              Returns an error if the log does not match the event ABI.
    """
    # Extract event name and parameter types
    event_name = event_abi["name"]
    inputs = event_abi["inputs"]

    # Compute the expected event signature hash
    signature = f"{event_name}({','.join(param['type'] for param in inputs)})"
    expected_hash = "0x" + keccak(text=signature.replace(" ", "")).hex()

    # Verify the event signature matches topics[0]
    if log_entry["topics"][0] != expected_hash:
        return {"error": "Event signature does not match the log entry"}

    # Separate indexed and non-indexed parameters
    indexed_params = [param for param in inputs if param.get("indexed", False)]
    non_indexed_params = [
        param for param in inputs if not param.get("indexed", False)]

    # Decode indexed parameters from topics
    decoded_indexed = {}
    for i, param in enumerate(indexed_params):
        param_type = param["type"]
        param_name = param["name"]
        topic_data = bytes.fromhex(log_entry["topics"][i + 1][2:])  # Skip '0x'
        decoded_indexed[param_name] = decode([param_type], topic_data)[0]

    # Decode non-indexed parameters from the data field
    decoded_non_indexed = {}
    if log_entry["data"] and non_indexed_params:
        param_types = [param["type"] for param in non_indexed_params]
        raw_data = bytes.fromhex(log_entry["data"][2:])  # Skip '0x'
        decoded_values = decode(param_types, raw_data)

        for i, param in enumerate(non_indexed_params):
            decoded_non_indexed[param["name"]] = decoded_values[i]

    # Combine decoded parameters
    decoded_params = {**decoded_indexed, **decoded_non_indexed}

    # Return the decoded event
    return {
        "event": event_name,
        "params": decoded_params,
    }
