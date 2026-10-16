"""V2 会话、附件及异步业务任务端点。"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from fastapi import APIRouter, Depends, File, Header, Response, UploadFile

from app.api.v2.dependencies import (
    V2Error,
    attachment_store,
    authenticate_consultation,
    consultation_service,
    consultation_store,
    task_store,
)
from app.models.consultation_v2 import (
    AnswerRequest,
    AttachmentResponse,
    Consultation,
    ConsultationStatus,
    CreateConsultationRequest,
    CreateConsultationResponse,
    PrepareRequest,
    TaskAcceptedResponse,
    TaskStatus,
)
from app.services.attachment_processor import AttachmentValidationError
from app.services.consultation_v2 import TaskTimeoutError

router = APIRouter(prefix="/consultations", tags=["V2 多模态问诊"])
_background: set[asyncio.Task] = set()


def _schedule(
    operation: Callable[[str, Consultation], Awaitable[None]],
    task_id: str,
    consultation: Consultation,
) -> None:
    async def runner() -> None:
        try:
            await asyncio.wait_for(
                operation(task_id, consultation),
                timeout=consultation_service.task_timeout(operation.__name__),
            )
        except asyncio.TimeoutError:
            consultation_service.fail_task(
                task_id, consultation, TaskTimeoutError("任务总超时")
            )
        except Exception as exc:
            consultation_service.fail_task(task_id, consultation, exc)

    item = asyncio.create_task(runner())
    _background.add(item)
    item.add_done_callback(_background.discard)


def _create_task(
    consultation: Consultation,
    task_type: str,
    idempotency_key: str,
) -> tuple[object, bool]:
    existing = task_store.find_idempotent(
        consultation.id, task_type, idempotency_key
    )
    if existing:
        return existing, True
    active = task_store.get(consultation.active_task_id or "")
    if active and active.status in {TaskStatus.QUEUED, TaskStatus.PROCESSING}:
        raise V2Error("INVALID_STATE", "当前已有任务正在处理", 409)
    task = task_store.create(consultation.id, task_type, idempotency_key or None)
    consultation.active_task_id = task.id
    return task, False


@router.post("", response_model=CreateConsultationResponse, status_code=201)
async def create_consultation(
    request: CreateConsultationRequest,
) -> CreateConsultationResponse:
    consultation, token = consultation_store.create(request.role)
    return CreateConsultationResponse(
        consultation_id=consultation.id,
        consultation_token=token,
        status=consultation.status,
        expires_in=consultation_store.ttl_seconds,
    )


@router.post(
    "/{consultation_id}/attachments",
    response_model=AttachmentResponse,
    status_code=201,
)
async def upload_attachment(
    file: UploadFile = File(...),
    consultation: Consultation = Depends(authenticate_consultation),
) -> AttachmentResponse:
    if consultation.status != ConsultationStatus.DRAFT:
        raise V2Error("INVALID_STATE", "问诊开始后不能修改附件", 409)
    data = await file.read(settings_limit := attachment_store.max_bytes + 1)
    if len(data) >= settings_limit:
        raise V2Error("ATTACHMENT_TOO_LARGE", "单个附件不能超过 10MB", 413)
    try:
        attachment = attachment_store.save(
            consultation,
            file.filename or "attachment",
            file.content_type or "",
            data,
        )
    except AttachmentValidationError as exc:
        raise V2Error(exc.code, exc.message, 400) from exc
    return AttachmentResponse(
        attachment_id=attachment.id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        size=attachment.size,
        pages=attachment.pages,
        status=attachment.status,
    )


@router.delete(
    "/{consultation_id}/attachments/{attachment_id}", status_code=204
)
async def delete_attachment(
    attachment_id: str,
    consultation: Consultation = Depends(authenticate_consultation),
) -> Response:
    if consultation.status != ConsultationStatus.DRAFT:
        raise V2Error("INVALID_STATE", "问诊开始后不能修改附件", 409)
    if not attachment_store.delete(consultation, attachment_id):
        raise V2Error("INVALID_ATTACHMENT", "附件不存在", 404)
    return Response(status_code=204)


@router.post(
    "/{consultation_id}/prepare", response_model=TaskAcceptedResponse, status_code=202
)
async def prepare(
    request: PrepareRequest,
    consultation: Consultation = Depends(authenticate_consultation),
    idempotency_key: str = Header("", alias="Idempotency-Key"),
) -> TaskAcceptedResponse:
    existing = task_store.find_idempotent(
        consultation.id, "prepare", idempotency_key
    )
    if existing:
        return TaskAcceptedResponse(task_id=existing.id, status=existing.status)
    if consultation.status != ConsultationStatus.DRAFT:
        raise V2Error("INVALID_STATE", "当前状态不能开始问诊", 409)
    task, reused = _create_task(consultation, "prepare", idempotency_key)
    if not reused:
        consultation.chief_complaint = request.chief_complaint.strip()
        _schedule(consultation_service.run_prepare, task.id, consultation)
    return TaskAcceptedResponse(task_id=task.id, status=task.status)


@router.post(
    "/{consultation_id}/answers", response_model=TaskAcceptedResponse, status_code=202
)
async def answer(
    request: AnswerRequest,
    consultation: Consultation = Depends(authenticate_consultation),
    idempotency_key: str = Header("", alias="Idempotency-Key"),
) -> TaskAcceptedResponse:
    existing = task_store.find_idempotent(
        consultation.id, "answer", idempotency_key
    )
    if existing:
        return TaskAcceptedResponse(task_id=existing.id, status=existing.status)
    if consultation.status != ConsultationStatus.INQUIRY:
        raise V2Error("INVALID_STATE", "当前没有可回答的问题", 409)
    task, reused = _create_task(consultation, "answer", idempotency_key)
    if not reused:
        consultation.history.append(
            {
                "question": consultation.current_question,
                "answer": request.answer,
                "skipped": request.skipped,
                "structured_answer": request.structured_answer,
            }
        )
        _schedule(consultation_service.run_answer, task.id, consultation)
    return TaskAcceptedResponse(task_id=task.id, status=task.status)


@router.post(
    "/{consultation_id}/finalize", response_model=TaskAcceptedResponse, status_code=202
)
async def finalize(
    consultation: Consultation = Depends(authenticate_consultation),
    idempotency_key: str = Header("", alias="Idempotency-Key"),
) -> TaskAcceptedResponse:
    existing = task_store.find_idempotent(
        consultation.id, "finalize", idempotency_key
    )
    if existing:
        return TaskAcceptedResponse(task_id=existing.id, status=existing.status)
    if consultation.status not in {
        ConsultationStatus.READY,
        ConsultationStatus.FAILED,
    }:
        raise V2Error("INVALID_STATE", "问诊尚未完成，不能生成报告", 409)
    task, reused = _create_task(consultation, "finalize", idempotency_key)
    if not reused:
        _schedule(consultation_service.run_finalize, task.id, consultation)
    return TaskAcceptedResponse(task_id=task.id, status=task.status)
