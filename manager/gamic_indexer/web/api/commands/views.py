from typing import Dict
from fastapi import APIRouter, Body, Depends
from redis.asyncio import ConnectionPool, Redis

from gamic_indexer.services.redis.dependency import get_redis_pool
from gamic_indexer.utils.models import Command
from gamic_indexer.settings import settings

router = APIRouter()


@router.post("/add-chain/")
async def add_chain(
    rpc_endpoint: str = Body(...),
    chain_id: int = Body(...),
    block_time: int = Body(...),
    start_block: int = Body(...),
    redis_pool: ConnectionPool = Depends(get_redis_pool),
) -> Dict[str, str]:
    async with Redis(connection_pool=redis_pool) as redis:
        command = Command(
            command="add_chain",
            data={
                "rpc_endpoint": rpc_endpoint,
                "chain_id": chain_id,
                "block_time": block_time,
                "start_block": start_block,
            },
            response_channel="indexer:responses:add_chain",
        )
        await redis.publish(settings.command_channel, command.model_dump_json())
    return {"message": "Chain added"}

@router.post("/remove-chain/")
async def remove_chain(
    chain_id: int = Body(...),
    redis_pool: ConnectionPool = Depends(get_redis_pool),
) -> Dict[str, str]:
    async with Redis(connection_pool=redis_pool) as redis:
        command = Command(
            command="remove_chain",
            data={"chain_id": chain_id},
            response_channel="indexer:responses:remove_chain",
        )
        await redis.publish(settings.command_channel, command.model_dump_json())
    return {"message": "Chain removed"}
