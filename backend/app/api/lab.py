"""化验单 / 检查报告上传接口（方案乙：原图直送辨证，不做客户端 OCR/摘要）

POST /lab/upload   同步校验 + 预处理（图片或 PDF）→ 入内存存储 → 回 lab_id
辨证决断时，/chat/diagnose 凭 lab_image_ids 取原图，由视觉模型读成要点注入辨证。

隐私：原图仅内存暂存，识别完即弃，带 TTL 清理，不落盘。
"""

import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import LabUploadResponse
from app.services.lab import LabImageError, lab_store, preprocess_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lab", tags=["化验单"])


@router.post("/upload", response_model=LabUploadResponse)
async def upload(
    file: UploadFile = File(..., description="化验单/检查报告（jpg/png/webp 或 pdf）"),
) -> LabUploadResponse:
    """上传一份化验单（图片或 PDF）。坏文件/超限当场 400，由前端提示重传。

    不校验 content_type（小程序上传常为 octet-stream）；图片解码交给 Pillow、
    PDF 解析交给 PyMuPDF，真校验在 preprocess_upload 里。
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空文件")
    if len(raw) > settings.LAB_MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="文件过大，请控制在12MB以内")
    try:
        image_urls = preprocess_upload(raw)
    except LabImageError:
        raise HTTPException(
            status_code=400, detail="文件无法识别，请上传清晰的化验单图片或 PDF"
        )
    doc = lab_store.create(image_urls)
    return LabUploadResponse(lab_id=doc.id)
