"""拍照舌诊服务 - 图片预处理 + 视觉模型门控/舌象分析 + 受控词表归一化

流程（对应《拍照舌诊功能开发文档》）：
  1. Pillow 预处理：校验可解码、EXIF 转正、最长边缩至1024、转 JPEG、base64
  2. 视觉模型一次调用完成门控 + 舌象描述（不落盘，内存即弃）
  3. 容错解析 JSON，受控词表归一化，防模型自造词污染下游
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

from PIL import Image, ImageOps

from app.config import settings
from app.prompts.system_prompts import TONGUE_SYSTEM_PROMPT
from app.services.diagnose import _parse_json_loose
from app.services.llm import vision_completion

logger = logging.getLogger(__name__)

# 受控词表（必须与 TONGUE_SYSTEM_PROMPT 保持一致）
_TONGUE_COLORS = {"淡白", "淡红", "红", "绛红", "青紫"}
_TONGUE_SHAPES = {"正常", "胖大", "瘦薄", "齿痕", "裂纹", "点刺", "瘀斑瘀点"}
_COATING_COLORS = {"白", "薄黄", "黄", "灰黑", "无苔"}
_COATING_TEXTURES = {"薄", "厚", "腻", "燥", "润", "剥落", "少苔"}
_MOISTURES = {"润", "偏干", "偏湿"}
_GATES = {"ok", "not_tongue", "partial", "blurry", "poor_lighting"}

RETAKE_HINTS = {
    "not_tongue": "这张照片好像不是舌头，请对准舌头重新拍摄",
    "partial": "舌头露出不全，请自然伸舌、露出整个舌面再拍",
    "blurry": "照片有些模糊，请拿稳手机、对焦清晰后重拍",
    "poor_lighting": "光线不佳会影响舌色判断，请在自然光下重拍",
    "vl_unavailable": "舌象分析暂不可用，已保留照片，可先继续问诊",
    "parse_error": "舌象分析没能完成，请重新拍摄一张",
}


class TongueImageError(ValueError):
    """上传内容不是有效图片（解码失败）"""


def preprocess_image(raw: bytes) -> str:
    """预处理上传图片，返回 JPEG base64 data URL。

    - Pillow 解码校验（小程序上传的 content_type 不可靠，真校验在这里）
    - EXIF 转正（手机竖拍带旋转标记，不转正模型看到的是横躺的舌头）
    - 最长边缩至 TONGUE_IMAGE_MAX_SIDE，控制视觉 token 消耗
    """
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as e:
        raise TongueImageError(f"无法解码图片: {e}") from e

    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")

    max_side = settings.TONGUE_IMAGE_MAX_SIDE
    w, h = img.size
    scale = max(w, h) / max_side
    if scale > 1:
        # max(1,...)：防极端长宽比（如全景截图）缩出 0 像素边导致 resize 抛错
        img = img.resize((max(1, round(w / scale)), max(1, round(h / scale))), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def _pick(value: Any, allowed: set, default: str) -> str:
    v = str(value or "").strip()
    return v if v in allowed else default


def _pick_list(values: Any, allowed: set) -> list[str]:
    if not isinstance(values, list):
        values = [values] if values else []
    out: list[str] = []
    for v in values:
        v = str(v or "").strip()
        if v in allowed and v not in out:
            out.append(v)
    return out


def _features_to_text(f: dict) -> str:
    """模型未给 tcm_text 时，由特征拼一句兜底描述。"""
    return (
        f"舌{f['tongue_color']}，舌体{'、'.join(f['tongue_shape'])}，"
        f"苔{f['coating_color']}而{'、'.join(f['coating_texture'])}，津液{f['moisture']}"
    )


def _reject(reason: str) -> dict[str, Any]:
    return {"ok": False, "reject_reason": reason, "retake_hint": RETAKE_HINTS[reason]}


def _normalize(data: dict) -> dict[str, Any]:
    """模型输出 → 稳定结构。gate 非法按解析失败处理。"""
    gate = str(data.get("gate") or "").strip()
    if gate not in _GATES:
        return _reject("parse_error")
    if gate != "ok":
        return _reject(gate)

    f = data.get("features")
    if not isinstance(f, dict) or not f:
        # gate=ok 却没给特征：不能用默认值编造舌象，按解析失败拒绝
        return _reject("parse_error")
    features = {
        "tongue_color": _pick(f.get("tongue_color"), _TONGUE_COLORS, "淡红"),
        "tongue_shape": _pick_list(f.get("tongue_shape"), _TONGUE_SHAPES) or ["正常"],
        "coating_color": _pick(f.get("coating_color"), _COATING_COLORS, "白"),
        "coating_texture": _pick_list(f.get("coating_texture"), _COATING_TEXTURES) or ["薄"],
        "moisture": _pick(f.get("moisture"), _MOISTURES, "润"),
    }
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "ok": True,
        "features": features,
        "tcm_text": str(data.get("tcm_text") or "").strip() or _features_to_text(features),
        "summary": str(data.get("summary") or "").strip(),
        "confidence": confidence,
    }


async def analyze_image_url(image_url: str) -> dict[str, Any]:
    """对已预处理的 image_url 跑视觉模型门控/舌象分析（慢，约 5~15s）。

    模型故障降级为 vl_unavailable，不抛 500 —— 舌诊是增强项，不能阻断问诊主流程。
    供轮询接口的后台任务调用（提交阶段已做完同步预处理/校验）。
    """
    try:
        text = await vision_completion(
            system=TONGUE_SYSTEM_PROMPT,
            user_text="请按要求分析这张舌象照片，只输出JSON。",
            image_data_url=image_url,
        )
    except RuntimeError as e:  # 未配置 VL_API_KEY
        logger.warning("舌诊不可用: %s", e)
        return _reject("vl_unavailable")
    except Exception as e:
        logger.error("舌诊视觉模型调用失败: %s", e)
        return _reject("vl_unavailable")

    data = _parse_json_loose(text)
    if not data:
        logger.warning("舌诊JSON解析失败: %s", (text or "")[:200])
        return _reject("parse_error")
    return _normalize(data)


async def analyze_tongue(raw: bytes) -> dict[str, Any]:
    """舌诊主流程（同步等结果版，保留兼容）。返回字段与 TongueAnalyzeResponse 对齐。

    TongueImageError 向上抛，由路由层转 400。
    """
    image_url = preprocess_image(raw)
    return await analyze_image_url(image_url)
