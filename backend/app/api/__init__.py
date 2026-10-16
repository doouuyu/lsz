"""API 路由聚合 - 统一挂载到 /api 前缀"""

from fastapi import APIRouter

from app.api import chat, knowledge, regimen, chronic, report, tongue, lab
from app.api.v2 import router as v2_router

api_router = APIRouter(prefix="/api")
api_router.include_router(chat.router)
api_router.include_router(knowledge.router)
api_router.include_router(regimen.router)
api_router.include_router(chronic.router)
api_router.include_router(report.router)
api_router.include_router(tongue.router)
api_router.include_router(lab.router)
api_router.include_router(v2_router)
