"""V2 多模态问诊的 API 契约与进程内状态模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConsultationRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    RESEARCHER = "researcher"


class ConsultationStatus(str, Enum):
    DRAFT = "draft"
    PREPARING = "preparing"
    INQUIRY = "inquiry"
    READY = "ready"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class TaskStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class Attachment:
    id: str
    filename: str
    mime_type: str
    size: int
    pages: int
    original_path: str
    processed_paths: list[str]
    created_at: datetime = field(default_factory=utc_now)
    status: str = "ready"


@dataclass
class Consultation:
    id: str
    token_hash: str
    role: ConsultationRole
    created_at: datetime
    expires_at: datetime
    status: ConsultationStatus = ConsultationStatus.DRAFT
    attachments: list[Attachment] = field(default_factory=list)
    chief_complaint: str = ""
    observations: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    current_question: Optional[dict[str, Any]] = None
    report: Optional[dict[str, Any]] = None
    active_task_id: Optional[str] = None
    forced_finalize: bool = False


@dataclass
class Task:
    id: str
    consultation_id: str
    type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    idempotency_key: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None


class CreateConsultationRequest(BaseModel):
    role: ConsultationRole = ConsultationRole.PATIENT


class CreateConsultationResponse(BaseModel):
    consultation_id: str
    consultation_token: str
    status: ConsultationStatus
    expires_in: int


class PrepareRequest(BaseModel):
    chief_complaint: str = Field(..., min_length=1, max_length=4000)


class AnswerRequest(BaseModel):
    answer: str = Field("", max_length=4000)
    skipped: bool = False
    question_key: str = Field("", max_length=100)
    structured_answer: dict[str, Any] = Field(default_factory=dict)


class TaskAcceptedResponse(BaseModel):
    task_id: str
    status: TaskStatus


class TaskResponse(BaseModel):
    task_id: str
    type: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None


class AttachmentResponse(BaseModel):
    attachment_id: str
    filename: str
    mime_type: str
    size: int
    pages: int
    status: str
