"""V2 路由聚合。"""

from fastapi import APIRouter

from app.api.v2 import asr, consultations, tasks

router = APIRouter(prefix="/v2")
router.include_router(consultations.router)
router.include_router(tasks.router)
router.include_router(asr.router)

