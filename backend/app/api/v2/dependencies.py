"""V2 共享实例、鉴权与统一错误。"""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Header

from app.config import settings
from app.models.consultation_v2 import Consultation, ConsultationStatus
from app.services.attachment_store import AttachmentStore
from app.services.consultation_store import ConsultationStore
from app.services.consultation_v2 import ConsultationV2Service
from app.services.multimodal_llm import multimodal_gateway
from app.services.task_store import TaskStore


class V2Error(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = f"req_{secrets.token_hex(6)}"


consultation_store = ConsultationStore(settings.CONSULTATION_TTL_SECONDS)
task_store = TaskStore(settings.CONSULTATION_TTL_SECONDS)
attachment_store = AttachmentStore(
    Path(settings.CONSULTATION_TEMP_DIR),
    settings.ATTACHMENT_MAX_COUNT,
    settings.ATTACHMENT_MAX_BYTES,
    settings.ATTACHMENT_TOTAL_MAX_BYTES,
    settings.PDF_MAX_PAGES,
    settings.PDF_RENDER_DPI,
    settings.ATTACHMENT_IMAGE_MAX_SIDE,
)
consultation_service = ConsultationV2Service(
    consultation_store, task_store, attachment_store, multimodal_gateway
)


def authenticate_consultation(
    consultation_id: str,
    x_consultation_token: str = Header("", alias="X-Consultation-Token"),
) -> Consultation:
    consultation = consultation_store.get(consultation_id)
    if not consultation:
        raise V2Error("CONSULTATION_NOT_FOUND", "问诊会话不存在", 404)
    if consultation.status == ConsultationStatus.EXPIRED:
        raise V2Error("CONSULTATION_EXPIRED", "问诊会话已过期", 410)
    authenticated = consultation_store.authenticate(
        consultation_id, x_consultation_token
    )
    if not authenticated:
        raise V2Error("INVALID_CONSULTATION_TOKEN", "问诊令牌无效", 401)
    return authenticated

