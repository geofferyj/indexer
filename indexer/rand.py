rpc = (
    "https://snowy-alpha-pine.bsc.quiknode.pro/7a05c5b4b5b47af309f10304f5d383e84ce39916"
)
chain_id = 56
block_time = 3
start_block = 44562017

payload = {
    "chain_id": chain_id,
    "rpc_endpoint": rpc,
    "block_time": block_time,
    "start_block": start_block,
}

command = {
    "command": "add_chain",
    "data": payload,
    "response_channel": "indexer:response",
}

add_chain = {
    "command": "add_chain",
    "data": {
        "chain_id": 1,
        "rpc_endpoint": "https://snowy-alpha-pine.quiknode.pro/7a05c5b4b5b47af309f10304f5d383e84ce39916",
        "block_time": 12,
        "start_block": 21325616,
    },
    "response_channel": "indexer:response",
}

remove_chain = {
    "command": "remove_chain",
    "data": {"chain_id": 1},
    "response_channel": "indexer:response",
}

list_chains = {
    "command": "list_chains",
    "data": {},
    "response_channel": "indexer:response",
}
