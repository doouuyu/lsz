"""李时珍智能医师 - FastAPI 入口"""

import asyncio
import logging
from contextlib import asynccontextmanager
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.api.v2.dependencies import (
    V2Error,
    attachment_store,
    consultation_store,
    task_store,
)
from app.config import settings
from app.services.knowledge import knowledge_service
from app.services.multimodal_llm import multimodal_gateway

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _configure_consultation_log() -> None:
    log_dir = Path(settings.CONSULTATION_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    handler = TimedRotatingFileHandler(
        log_dir / "consultation-v2.log",
        when="midnight",
        backupCount=settings.TEXT_LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    (log_dir / "consultation-v2.log").chmod(0o600)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger = logging.getLogger("consultation_v2")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(handler)
    logger.propagate = False


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(60)
        for consultation in consultation_store.expired():
            attachment_store.delete_all(consultation)
            task_store.remove_for_consultation(consultation.id)
            consultation_store.remove(consultation.id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：加载知识库到内存
    knowledge_service.load()
    _configure_consultation_log()
    attachment_store.cleanup_orphans(set())
    cleanup_task = asyncio.create_task(_cleanup_loop())
    yield
    cleanup_task.cancel()


app = FastAPI(
    title="李时珍智能医师",
    description="基于检索增强生成的李时珍老年病智能辨证系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 业务 API
app.include_router(api_router)


@app.exception_handler(V2Error)
async def v2_error_handler(request: Request, exc: V2Error) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": exc.request_id,
            }
        },
    )

# 报告静态目录
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")


@app.get("/")
async def root():
    return {"message": "李时珍智能医师 API v1.0", "docs": "/docs"}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "knowledge": knowledge_service.stats(),
        "v2": {
            "multimodal_available": multimodal_gateway.available(),
            "asr_available": bool(
                settings.BAILIAN_API_KEY
                and settings.BAILIAN_WORKSPACE_ID
                and settings.ASR_MODEL == "fun-asr-realtime-2026-02-28"
            ),
            "asr_hotwords_loaded": bool(settings.ASR_VOCABULARY_ID),
        },
    }
