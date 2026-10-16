"""拍照舌诊接口

舌象识别耗时长（视觉模型 5~15s），同步等结果易撑爆 HTTP/网关超时。
故主流程改「提交 + 轮询」：
  POST /tongue/submit        同步校验图片 → 起后台任务 → 秒回 task_id
  GET  /tongue/result/{id}   轮询 pending / done
保留 POST /tongue/analyze（同步版）以兼容旧调用。

隐私红线：照片仅内存处理，分析完即弃，不落盘；任务存储只保存分析结果，不保存图片。
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import (
    TongueAnalyzeResponse,
    TongueFeatures,
    TongueResultResponse,
    TongueSubmitResponse,
)
from app.services.tongue import (
    RETAKE_HINTS,
    TongueImageError,
    analyze_image_url,
    analyze_tongue,
    preprocess_image,
)
from app.services.tongue_tasks import tongue_task_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tongue", tags=["舌诊"])


def _to_response(result: dict, session_id: Optional[str] = None) -> TongueAnalyzeResponse:
    """分析结果 dict → 响应模型（统一组装，submit/analyze 复用）。"""
    return TongueAnalyzeResponse(
        ok=result.get("ok", False),
        session_id=session_id,
        reject_reason=result.get("reject_reason", ""),
        retake_hint=result.get("retake_hint", ""),
        features=TongueFeatures(**result["features"]) if result.get("features") else None,
        tcm_text=result.get("tcm_text", ""),
        summary=result.get("summary", ""),
        confidence=result.get("confidence", 0.0),
    )


def _read_validated(raw: bytes) -> str:
    """同步校验 + 预处理上传图片，返回 image_url。坏图/超限就地抛 400。"""
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > settings.TONGUE_MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片过大，请控制在8MB以内")
    try:
        return preprocess_image(raw)
    except TongueImageError:
        raise HTTPException(status_code=400, detail="文件不是有效图片，请重新拍摄")


async def _run_analysis(task_id: str, image_url: str) -> None:
    """后台任务：跑视觉模型，结果写回任务存储。异常兜底为 vl_unavailable，绝不漏写。"""
    try:
        result = await analyze_image_url(image_url)
    except Exception as e:  # 兜底：后台任务异常也要让轮询能收尾
        logger.error("舌诊后台分析失败: %s", e)
        result = {
            "ok": False,
            "reject_reason": "vl_unavailable",
            "retake_hint": RETAKE_HINTS["vl_unavailable"],
        }
    tongue_task_store.finish(task_id, result)


@router.post("/submit", response_model=TongueSubmitResponse)
async def submit(
    file: UploadFile = File(..., description="舌头照片（jpg/png/webp）"),
    session_id: Optional[str] = Form(None),
) -> TongueSubmitResponse:
    """提交舌象 → 同步校验后起后台分析任务，立即返回 task_id 供轮询。

    同步阶段只做 Pillow 解码/缩放（快），坏图当场 400；慢的视觉模型放后台。
    """
    raw = await file.read()
    image_url = _read_validated(raw)
    task = tongue_task_store.create()
    asyncio.create_task(_run_analysis(task.id, image_url))
    return TongueSubmitResponse(task_id=task.id)


@router.get("/result/{task_id}", response_model=TongueResultResponse)
async def result(task_id: str) -> TongueResultResponse:
    """轮询舌象识别结果。任务不存在/已过期 → 404，由前端降级保留照片。"""
    task = tongue_task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    if task.status != "done":
        return TongueResultResponse(status="pending")
    return TongueResultResponse(status="done", result=_to_response(task.result or {}))


@router.post("/analyze", response_model=TongueAnalyzeResponse)
async def analyze(
    file: UploadFile = File(..., description="舌头照片（jpg/png/webp）"),
    session_id: Optional[str] = Form(None),
) -> TongueAnalyzeResponse:
    """上传舌头照片 → 门控判断 + 舌象特征分析（同步等结果，兼容保留）。

    隐私红线：照片仅内存处理，分析完即弃，不落盘。
    不校验 content_type（小程序上传常为 octet-stream），解码校验交给 Pillow。
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > settings.TONGUE_MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片过大，请控制在8MB以内")

    try:
        result = await analyze_tongue(raw)
    except TongueImageError:
        raise HTTPException(status_code=400, detail="文件不是有效图片，请重新拍摄")

    return _to_response(result, session_id)
