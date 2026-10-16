"""V2 异步任务轮询。"""

from fastapi import APIRouter, Header

from app.api.v2.dependencies import V2Error, consultation_store, task_store
from app.models.consultation_v2 import ConsultationStatus, TaskResponse, TaskStatus

router = APIRouter(prefix="/tasks", tags=["V2 异步任务"])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    x_consultation_token: str = Header("", alias="X-Consultation-Token"),
) -> TaskResponse:
    task = task_store.get(task_id)
    if not task:
        raise V2Error("TASK_NOT_FOUND", "任务不存在", 404)
    if task.status == TaskStatus.EXPIRED:
        raise V2Error("TASK_EXPIRED", "任务已过期", 410)
    stored_consultation = consultation_store.get(task.consultation_id)
    if (
        stored_consultation
        and stored_consultation.status == ConsultationStatus.EXPIRED
    ):
        raise V2Error("CONSULTATION_EXPIRED", "问诊会话已过期", 410)
    consultation = consultation_store.authenticate(
        task.consultation_id, x_consultation_token
    )
    if not consultation:
        raise V2Error("INVALID_CONSULTATION_TOKEN", "问诊令牌无效", 401)
    return TaskResponse(
        task_id=task.id,
        type=task.type,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        result=task.result,
        error=task.error,
    )
