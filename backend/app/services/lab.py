"""化验单 / 检查报告上传与识别

方案乙：用户上传化验单原图（或 PDF），不在客户端做 OCR/摘要。
辨证决断时，由视觉模型把原图读成临床要点文本，注入辨证链以增强论证
（主辨证模型为纯文本 DeepSeek，看不了图，故由视觉模型先读再转文本喂入）。

存储：内存字典 lab_id -> 预处理后的图片 data_url 列表 + 识别要点缓存。
隐私：首次识别完成后即丢弃原图，仅保留提取要点文本；带 TTL 惰性清理。
单进程内存——多 worker 部署需换 Redis（与 session_store / tongue 同约束）。
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF：PDF 栅格化成图
from PIL import Image, ImageOps

from app.config import settings
from app.prompts.system_prompts import LAB_REPORT_SYSTEM_PROMPT
from app.services.llm import vision_completion

logger = logging.getLogger(__name__)

_LAB_TTL = 1800.0  # 原图/要点保留 30 分钟，覆盖「上传→问诊→决断」的间隔


class LabImageError(ValueError):
    """上传内容既不是有效图片也不是有效 PDF"""


@dataclass
class LabDoc:
    id: str
    image_urls: list[str] = field(default_factory=list)  # 预处理后的图片 data_url（PDF 多页→多张）
    findings: Optional[str] = None  # 视觉模型提取的要点；识别后缓存，原图随即清空
    created_at: float = field(default_factory=time.monotonic)


class LabStore:
    def __init__(self) -> None:
        self._docs: dict[str, LabDoc] = {}

    def create(self, image_urls: list[str]) -> LabDoc:
        self._evict()
        lid = f"lab-{uuid.uuid4().hex[:12]}"
        doc = LabDoc(id=lid, image_urls=image_urls)
        self._docs[lid] = doc
        return doc

    def get(self, lab_id: str) -> Optional[LabDoc]:
        return self._docs.get(lab_id)

    def _evict(self) -> None:
        """惰性清理过期件，避免内存无界增长。"""
        now = time.monotonic()
        stale = [k for k, d in self._docs.items() if now - d.created_at > _LAB_TTL]
        for k in stale:
            self._docs.pop(k, None)


lab_store = LabStore()


def _img_to_data_url(img: Image.Image) -> str:
    """单张 PIL 图 → JPEG base64 data URL（EXIF 转正 + 限制最长边控 token）。"""
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    max_side = settings.LAB_IMAGE_MAX_SIDE
    w, h = img.size
    scale = max(w, h) / max_side
    if scale > 1:
        img = img.resize((max(1, round(w / scale)), max(1, round(h / scale))), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)  # 化验单数字小，质量略高于舌诊
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def _is_pdf(raw: bytes) -> bool:
    return raw[:5] == b"%PDF-"


def _pdf_to_data_urls(raw: bytes) -> list[str]:
    """PDF → 逐页栅格化成图片 data_url（最多 LAB_PDF_MAX_PAGES 页）。"""
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception as e:
        raise LabImageError(f"无法解析 PDF: {e}") from e
    try:
        n = min(doc.page_count, settings.LAB_PDF_MAX_PAGES)
        if n == 0:
            raise LabImageError("PDF 没有可识别的页面")
        # zoom 2.0 ≈ 144dpi：化验单数字看得清，又不至于把视觉 token 撑爆
        mat = fitz.Matrix(2.0, 2.0)
        urls: list[str] = []
        for i in range(n):
            pix = doc.load_page(i).get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            urls.append(_img_to_data_url(img))
        return urls
    finally:
        doc.close()


def preprocess_upload(raw: bytes) -> list[str]:
    """上传内容（图片或 PDF）→ 图片 data_url 列表。坏文件抛 LabImageError（路由转 400）。"""
    if _is_pdf(raw):
        return _pdf_to_data_urls(raw)
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as e:
        raise LabImageError(f"无法解码图片: {e}") from e
    return [_img_to_data_url(img)]


async def _read_one(image_url: str) -> str:
    text = await vision_completion(
        system=LAB_REPORT_SYSTEM_PROMPT,
        user_text="请阅读这张化验单/检查报告图片，按要求提取关键指标与异常项。",
        image_data_url=image_url,
        max_tokens=1500,
    )
    return (text or "").strip()


async def read_findings(lab_ids: list[str]) -> str:
    """把若干化验单识别成临床要点文本（辨证决断时调用）。

    - 视觉模型未配置 / 识别失败 → 跳过该件，绝不阻断辨证主流程。
    - 识别成功后缓存要点并清空原图（隐私 + 省内存）；重复辨证（如切角色）直接命中缓存。
    - 多件并发识别，单件多页（PDF）也并发。
    """
    docs = [d for lid in lab_ids if (d := lab_store.get(lid)) is not None]
    if not docs:
        return ""

    async def _doc_findings(doc: LabDoc) -> str:
        if doc.findings is not None:
            return doc.findings
        try:
            parts = await asyncio.gather(*[_read_one(u) for u in doc.image_urls])
            text = "\n".join(p for p in parts if p)
        except RuntimeError as e:  # 未配置 VL_API_KEY
            logger.warning("化验单识别不可用: %s", e)
            return ""
        except Exception as e:
            logger.error("化验单识别失败: %s", e)
            return ""
        doc.findings = text
        doc.image_urls = []  # 识别完即弃原图
        return text

    results = await asyncio.gather(*[_doc_findings(d) for d in docs])
    findings = [r for r in results if r]
    if not findings:
        return ""
    if len(findings) == 1:
        return findings[0]
    return "\n".join(f"（化验单{i + 1}）{f}" for i, f in enumerate(findings))
