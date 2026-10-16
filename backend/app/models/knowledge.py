"""知识库数据模型"""

from pydantic import BaseModel, Field
from typing import Optional


class HerbComposition(BaseModel):
    herb: str
    dosage: str = ""
    role: str = Field("", description="君/臣/佐/使")
    reason: str = ""


class Formula(BaseModel):
    name: str = ""
    composition: list[HerbComposition] = []


class Source(BaseModel):
    book: str = "《本草纲目》"
    volume: str = ""
    section: str = ""


class KnowledgeEntry(BaseModel):
    """知识库条目 - 对应开发文档1.1的Schema"""
    id: str = Field(..., description="唯一ID，如 LSZ-FANG-0001")
    category: str = Field(..., description="理/法/方/药/养生")
    subcategory: str = ""
    title: str
    source: Source = Source()
    original_text: str = Field("", description="原文摘录")
    plain_explanation: str = Field("", description="白话释义")
    related_diseases: list[str] = Field(default_factory=list, description="相关病证")
    related_syndromes: list[str] = Field(default_factory=list, description="相关证型")
    related_constitution: list[str] = Field(default_factory=list, description="相关体质")
    diagnosis_points: str = ""
    treatment_method: str = ""
    formula: Optional[Formula] = None
    contraindication: str = ""
    modern_mapping: str = ""
    tags: list[str] = Field(default_factory=list)
    verified: bool = False
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class GraphNode(BaseModel):
    id: str
    type: str  # disease / treatment / formula / herb / constitution
    label: str
    weight: int = 1


class GraphLink(BaseModel):
    source: str
    target: str
    relation: str  # 治法 / 代表方 / 组成 / 功效 / 相关体质


class KnowledgeGraph(BaseModel):
    nodes: list[GraphNode] = []
    links: list[GraphLink] = []
