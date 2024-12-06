from fastapi.routing import APIRouter

from gamic_indexer.web.api import monitoring

api_router = APIRouter()
api_router.include_router(monitoring.router)
