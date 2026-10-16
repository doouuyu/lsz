"""API 请求/响应模型 - 前后端数据契约

对应前端 frontend/src/api/index.ts 中的各接口。
所有面向 AI 输出的响应都带 disclaimer 字段（医疗合规红线）。
"""

from pydantic import BaseModel, Field
from typing import Any, Optional

from app.models.knowledge import KnowledgeEntry, GraphNode, GraphLink

DISCLAIMER = "本结果为学术研究与辅助参考，不替代执业医师面诊。"


# ===================== 辨证 / 问诊 =====================
class DiagnoseRequest(BaseModel):
    symptoms: str = Field(..., description="用户主诉 / 累计问诊信息")
    role: str = Field("patient", description="doctor / patient / researcher")
    session_id: Optional[str] = Field(None, description="会话ID，为空则新建")
    skip_inquiry: bool = Field(False, description="跳过问诊充分性检查，直接辨证")
    lab_image_ids: list[str] = Field(
        default_factory=list,
        description="化验单 lab_id 列表（来自 /lab/upload）；决断时由视觉模型读原图成要点注入辨证",
    )


class InquiryTurn(BaseModel):
    """单轮问诊对话。role=user 为患者主诉/回答，role=assistant 为系统已问出的问题。"""
    role: str = Field(..., description="user | assistant")
    content: str


class InquiryRequest(BaseModel):
    symptoms: str = Field(..., description="累计症状文本，用于检索兜底")
    history: list[InquiryTurn] = Field(
        default_factory=list,
        description="完整问答记录（主诉+历轮问与答），供模型连贯追问；为空则退回单轮",
    )
    session_id: Optional[str] = None


class InquiryOption(BaseModel):
    label: str
    value: str


class InquiryQuestion(BaseModel):
    """结构化问诊问题。type 决定前端控件：single 单选 / multi 多选 / slider 滑块 / text 纯补充。"""
    key: str = Field("", description="四诊维度，如 寒热/汗/二便/睡眠/情志/舌象/脉象/程度")
    question: str
    type: str = Field("single", description="single | multi | slider | text")
    options: list[InquiryOption] = Field(default_factory=list)
    min: int = 0
    max: int = 10
    min_label: str = ""
    max_label: str = ""
    unit: str = ""
    supplement: bool = Field(
        False,
        description="补充确认型问题（开放式收尾确认）：前端据此展示「没有要补充的」一键按钮",
    )


class InquiryResponse(BaseModel):
    ready: bool
    questions: list[InquiryQuestion] = Field(default_factory=list)
    session_id: Optional[str] = None


class DiagnoseResponse(BaseModel):
    """辨证主响应。

    need_more=True 时表示问诊信息不足，返回 questions；
    否则 result 为 8 步辨证思维链 JSON（结构见 system_prompts）。
    """
    session_id: str
    need_more: bool = False
    questions: list[str] = Field(default_factory=list)
    result: Optional[dict[str, Any]] = None
    sources: list[KnowledgeEntry] = Field(default_factory=list, description="RAG 引证条目")
    role: str = "patient"
    lab_findings: str = Field(
        "",
        description="本次辨证实际读取到的化验单/检查报告要点文本（视觉模型识别）；空串表示未带化验单或未能识别",
    )
    disclaimer: str = DISCLAIMER


# ===================== 知识库 =====================
class KnowledgeSearchResponse(BaseModel):
    total: int
    page: int = 1
    page_size: int = 10
    pages: int = 0
    items: list[KnowledgeEntry] = Field(default_factory=list)


class KnowledgeGraphResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    links: list[GraphLink] = Field(default_factory=list)


# ===================== 养生 =====================
class RegimenResponse(BaseModel):
    key: str
    title: str
    data: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


# ===================== 慢病一键辨证 =====================
class QuickDiagnoseRequest(BaseModel):
    disease: str
    symptoms: list[str] = Field(default_factory=list)
    role: str = "patient"


class QuickDiagnoseResponse(BaseModel):
    disease: str
    syndrome: str = ""
    treatment: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)
    sources: list[KnowledgeEntry] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


# ===================== 报告 =====================
class ReportRequest(BaseModel):
    session_id: str


class ReportResponse(BaseModel):
    report_id: str
    download_url: str
    disclaimer: str = DISCLAIMER


# ===================== 拍照舌诊 =====================
class TongueFeatures(BaseModel):
    """受控词表舌象特征（词表与 TONGUE_SYSTEM_PROMPT 一致）"""
    tongue_color: str = Field("", description="舌色：淡白/淡红/红/绛红/青紫")
    tongue_shape: list[str] = Field(default_factory=list, description="舌形：正常/胖大/瘦薄/齿痕/裂纹/点刺/瘀斑瘀点")
    coating_color: str = Field("", description="苔色：白/薄黄/黄/灰黑/无苔")
    coating_texture: list[str] = Field(default_factory=list, description="苔质：薄/厚/腻/燥/润/剥落/少苔")
    moisture: str = Field("", description="津液：润/偏干/偏湿")


class TongueAnalyzeResponse(BaseModel):
    """拍照舌诊响应。ok=False 时仅 reject_reason/retake_hint 有效。"""
    ok: bool = Field(..., description="门控通过且完成舌象分析")
    session_id: Optional[str] = Field(None, description="原样回传请求中的 session_id")
    reject_reason: str = Field("", description="not_tongue/partial/blurry/poor_lighting/vl_unavailable/parse_error")
    retake_hint: str = Field("", description="给用户的重拍/降级提示文案")
    features: Optional[TongueFeatures] = None
    tcm_text: str = Field("", description="中医术语舌象描述（移动端并入问诊主诉）")
    summary: str = Field("", description="面向用户的白话解读")
    confidence: float = 0.0
    disclaimer: str = DISCLAIMER


# ===================== 化验单 / 检查报告 =====================
class LabUploadResponse(BaseModel):
    """化验单上传响应：回 lab_id，辨证时随 /chat/diagnose 的 lab_image_ids 提交，
    由视觉模型读取原图成临床要点注入辨证（方案乙：原图直送，不做客户端 OCR/摘要）。"""
    lab_id: str = Field(..., description="化验单引用号")


class TongueSubmitResponse(BaseModel):
    """提交舌象 → 后台异步分析，立即返回任务号供轮询。"""
    task_id: str = Field(..., description="舌象识别任务号，凭此轮询 /tongue/result/{task_id}")


class TongueResultResponse(BaseModel):
    """轮询舌象识别结果。status=pending 时 result 为空。"""
    status: str = Field(..., description="pending | done")
    result: Optional[TongueAnalyzeResponse] = None
