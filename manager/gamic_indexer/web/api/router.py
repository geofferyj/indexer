from fastapi.routing import APIRouter

from gamic_indexer.web.api import commands, monitoring

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(commands.router)
