"""辨证 / 问诊 接口"""

from fastapi import APIRouter

from app.models.schemas import (
    DiagnoseRequest,
    DiagnoseResponse,
    InquiryQuestion,
    InquiryRequest,
    InquiryResponse,
)
from app.services.diagnose import retrieve_context, run_diagnose, run_inquiry
from app.services.lab import read_findings
from app.services.session import session_store

router = APIRouter(prefix="/chat", tags=["辨证"])


@router.post("/inquiry", response_model=InquiryResponse)
async def inquiry(req: InquiryRequest) -> InquiryResponse:
    """仿真问诊：判断四诊信息是否充分，不足则返回追问。"""
    sess = session_store.get_or_create(req.session_id)
    history = [t.model_dump() for t in req.history]
    result = await run_inquiry(req.symptoms, history=history)
    return InquiryResponse(
        ready=result["ready"],
        questions=[InquiryQuestion(**q) for q in result["questions"]],
        session_id=sess.id,
    )


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose(req: DiagnoseRequest) -> DiagnoseResponse:
    """辨证主流程：问诊检查 → RAG 检索 → 8 步思维链。"""
    sess = session_store.get_or_create(req.session_id, role=req.role)
    sess.role = req.role
    sess.symptoms.append(req.symptoms)

    # 1. 问诊充分性
    if not req.skip_inquiry:
        inq = await run_inquiry(req.symptoms)
        if not inq["ready"] and inq["questions"]:
            return DiagnoseResponse(
                session_id=sess.id,
                need_more=True,
                questions=[q["question"] for q in inq["questions"]],
                role=req.role,
            )

    # 2. RAG 检索（合并本会话累计症状以提升召回）
    full_symptoms = "；".join(sess.symptoms)
    # 化验单（方案乙）：原图在决断时由视觉模型读成临床要点，注入辨证以增强论证。
    # 视觉模型不可用/识别失败时 read_findings 返回空串，不阻断主流程。
    lab_findings = ""
    if req.lab_image_ids:
        lab_findings = await read_findings(req.lab_image_ids)
        if lab_findings:
            full_symptoms = f"{full_symptoms}\n\n【化验单/检查报告要点】\n{lab_findings}"
    entries = retrieve_context(full_symptoms)

    # 3. 辨证思维链
    result = await run_diagnose(full_symptoms, req.role, entries)

    sess.last_result = result
    sess.sources = [e.model_dump() for e in entries]

    return DiagnoseResponse(
        session_id=sess.id,
        need_more=False,
        result=result,
        sources=entries,
        role=req.role,
        lab_findings=lab_findings,
    )
