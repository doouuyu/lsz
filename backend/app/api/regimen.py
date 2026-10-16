"""四时养生 / 五脏调养 接口（静态预生成内容）"""

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import RegimenResponse
from app.services.static_data import ORGAN, SEASONAL

router = APIRouter(prefix="/regimen", tags=["养生"])

_SEASON_ALIAS = {
    "spring": "春", "summer": "夏", "autumn": "秋", "fall": "秋", "winter": "冬",
}
_ORGAN_ALIAS = {
    "heart": "心", "liver": "肝", "spleen": "脾", "lung": "肺", "kidney": "肾",
}


@router.get("/seasonal", response_model=RegimenResponse)
async def seasonal(season: str = Query(..., description="春/夏/秋/冬 或 spring/...")) -> RegimenResponse:
    key = _SEASON_ALIAS.get(season.lower(), season)
    data = SEASONAL.get(key)
    if not data:
        raise HTTPException(status_code=404, detail=f"未找到季节 {season}")
    src = data.get("source")
    return RegimenResponse(
        key=key,
        title=data.get("title", key),
        data=data,
        sources=[src] if src else [],
    )


@router.get("/organ", response_model=RegimenResponse)
async def organ(organ: str = Query(..., description="心/肝/脾/肺/肾 或 heart/...")) -> RegimenResponse:
    key = _ORGAN_ALIAS.get(organ.lower(), organ)
    data = ORGAN.get(key)
    if not data:
        raise HTTPException(status_code=404, detail=f"未找到脏腑 {organ}")
    src = data.get("source")
    return RegimenResponse(
        key=key,
        title=data.get("title", key),
        data=data,
        sources=[src] if src else [],
    )
