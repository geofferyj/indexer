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
        "chain_id": 8453,
        "rpc_endpoint": "https://base-rpc.publicnode.com/15910e46ff8445426dcd79da2258d906b4abf79f48cad5f3ebbce2842563a4bf",
        "block_time": 2,
        "start_block": 23647000
    },
    "response_channel": "indexer:response"
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
