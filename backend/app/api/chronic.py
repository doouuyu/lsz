"""基层慢病一键辨证 接口

策略：基于预置的「症状→证型」匹配规则给出调护方案（快速、零成本、可离线），
并用知识库检索补充文献依据。规则未命中时回退到默认证型。
"""

from fastapi import APIRouter, HTTPException

from app.models.schemas import QuickDiagnoseRequest, QuickDiagnoseResponse
from app.services.knowledge import knowledge_service
from app.services.static_data import CHRONIC

router = APIRouter(prefix="/chronic", tags=["慢病"])


def _best_syndrome(disease_cfg: dict, symptoms: list[str]) -> dict:
    """按症状与各证型 match 列表的重合数选最佳证型。"""
    sym_set = set(symptoms)
    best, best_score = None, -1
    for syn in disease_cfg.get("syndromes", []):
        score = len(sym_set & set(syn.get("match", [])))
        if score > best_score:
            best, best_score = syn, score
    if best is None or best_score == 0:
        # 回退默认
        default_name = disease_cfg.get("default_syndrome")
        for syn in disease_cfg.get("syndromes", []):
            if syn.get("syndrome") == default_name:
                return syn
        return disease_cfg.get("syndromes", [{}])[0]
    return best


@router.get("/diseases")
async def list_diseases() -> dict:
    """病种清单 + 症状勾选项（供前端渲染选择界面）。"""
    return {
        name: {
            "tcm_name": cfg.get("tcm_name", ""),
            "common_symptoms": cfg.get("common_symptoms", []),
        }
        for name, cfg in CHRONIC.items()
    }


@router.post("/quick-diagnose", response_model=QuickDiagnoseResponse)
async def quick_diagnose(req: QuickDiagnoseRequest) -> QuickDiagnoseResponse:
    cfg = CHRONIC.get(req.disease)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"暂不支持病种 {req.disease}")

    syn = _best_syndrome(cfg, req.symptoms)
    syndrome = syn.get("syndrome", cfg.get("default_syndrome", ""))

    # 文献依据：按病证 + 证型检索
    query = f"{req.disease} {syndrome} " + " ".join(req.symptoms)
    sources = knowledge_service.search(
        query, disease=cfg.get("tcm_name"), verified_only=True, top_k=3
    )

    return QuickDiagnoseResponse(
        disease=req.disease,
        syndrome=syndrome,
        treatment=syn.get("treatment", ""),
        plan=syn.get("plan", {}),
        sources=sources,
    )
