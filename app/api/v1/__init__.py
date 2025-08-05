from fastapi import APIRouter
from app.api.v1.endpoints import eval

api_router_v1 = APIRouter()
api_router_v1.include_router(eval.router, prefix="/project_eval")