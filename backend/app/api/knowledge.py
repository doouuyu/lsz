"""知识库检索 / 图谱 / 单条详情 接口"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models.knowledge import KnowledgeEntry
from app.models.schemas import KnowledgeGraphResponse, KnowledgeSearchResponse
from app.services.knowledge import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["知识库"])


@router.get("/search", response_model=KnowledgeSearchResponse)
async def search(
    q: str = Query("", description="检索词，可空（空则按筛选返回）"),
    category: Optional[str] = Query(None, description="理/法/方/药/养生"),
    disease: Optional[str] = Query(None, description="按病证过滤"),
    verified_only: bool = Query(False),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(10, ge=1, le=50, description="每页条数"),
) -> KnowledgeSearchResponse:
    # 小程序端 wx.request 可能把 undefined/null 序列化成同名字符串，
    # “全部”Tab 也可能原样透传，这些都视为不过滤
    if category in ("", "全部", "undefined", "null"):
        category = None
    total, items = knowledge_service.search_page(
        query=q,
        category=category,
        disease=disease,
        verified_only=verified_only,
        page=page,
        page_size=page_size,
    )
    pages = (total + page_size - 1) // page_size
    return KnowledgeSearchResponse(
        total=total, page=page, page_size=page_size, pages=pages, items=items
    )


@router.get("/graph", response_model=KnowledgeGraphResponse)
async def graph(
    disease: Optional[str] = Query(None, description="按病证过滤，空则返回全图"),
    max_entries: int = Query(200, ge=10, le=1000),
) -> KnowledgeGraphResponse:
    g = knowledge_service.build_graph(disease=disease, max_entries=max_entries)
    return KnowledgeGraphResponse(nodes=g.nodes, links=g.links)


@router.get("/list")
async def list_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None, description="理/法/方/药/养生"),
    disease: Optional[str] = Query(None, description="按病证过滤"),
    q: str = Query("", description="标题关键词过滤"),
) -> dict:
    """分页浏览全部条目。"""
    entries = knowledge_service.entries
    if not knowledge_service._loaded:
        knowledge_service.load()
        entries = knowledge_service.entries
    if category:
        entries = [e for e in entries if e.category == category]
    if disease:
        entries = [e for e in entries if disease in e.related_diseases or disease in e.modern_mapping]
    if q.strip():
        kw = q.strip().lower()
        entries = [e for e in entries if kw in e.title.lower() or kw in (e.plain_explanation or "").lower()]
    total = len(entries)
    start = (page - 1) * page_size
    page_items = entries[start:start + page_size]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [e.model_dump() for e in page_items],
    }


@router.get("/stats")
async def stats() -> dict:
    return knowledge_service.stats()


@router.get("/evaluation")
async def evaluation() -> dict:
    """知识库完整评估报告数据（含覆盖率、置信度、溯源率、检索准确性）。"""
    return knowledge_service.evaluation()


@router.get("/entry/{entry_id}", response_model=KnowledgeEntry)
async def entry(entry_id: str) -> KnowledgeEntry:
    e = knowledge_service.get_entry(entry_id)
    if not e:
        raise HTTPException(status_code=404, detail=f"未找到条目 {entry_id}")
    return e
