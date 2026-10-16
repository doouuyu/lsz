"""辨证编排服务 - RAG 检索 + LLM 调用 + JSON 容错解析

对应开发文档 3.2 主流程：
  1. 问诊充分性检查（可选）
  2. 混合检索，仅取 verified 条目作为引证源
  3. 组装 prompt 调模型，强制 JSON
  4. 校验结构、回填真实出处
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from app.models.knowledge import KnowledgeEntry
from app.prompts.system_prompts import (
    DIAGNOSE_SYSTEM_PROMPT,
    INQUIRY_SYSTEM_PROMPT,
    RESEARCHER_STEP9_SCHEMA,
    ROLE_INSTRUCTIONS,
)
from app.services.knowledge import knowledge_service
from app.services.llm import chat_completion_json

logger = logging.getLogger(__name__)


def _parse_json_loose(text: str) -> Optional[dict]:
    """容错解析 LLM 返回的 JSON（文档第七部分提醒②）。"""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 提取首个 { ... } 块
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def _format_context(entries: list[KnowledgeEntry]) -> str:
    if not entries:
        return "（暂无检索到的相关条目，请基于中医通识谨慎辨证，step4 留空。）"
    lines = []
    for e in entries:
        src = e.source
        src_str = f"{src.book}{('·' + src.volume) if src.volume else ''}{('·' + src.section) if src.section else ''}"
        lines.append(
            f"- [id={e.id}] 出处：{src_str}\n"
            f"  原文：{e.original_text or '（无原文，见释义）'}\n"
            f"  释义：{e.plain_explanation}"
        )
    return "\n".join(lines)


def retrieve_context(symptoms: str, top_k: int = 5) -> list[KnowledgeEntry]:
    """RAG 检索：仅取 verified 条目作为可引证源。"""
    hits = knowledge_service.search(symptoms, verified_only=True, top_k=top_k)
    if not hits:  # 没有 verified 命中则放宽，至少给模型一些上下文
        hits = knowledge_service.search(symptoms, verified_only=False, top_k=top_k)
    return hits


# 四诊维度 → 规范化选项库（控件类型 + 选项由后端注入，避免 LLM 瞎编）
INQUIRY_OPTIONS: dict[str, dict] = {
    "寒热": {"type": "single", "options": ["怕冷明显", "怕热明显", "时冷时热", "寒热不明显"]},
    "汗": {"type": "multi", "options": ["白天易出汗（自汗）", "夜间盗汗", "几乎无汗", "动则大汗"]},
    "头身": {"type": "multi", "options": ["头晕", "头痛", "头重如裹", "肢体麻木", "周身乏力", "关节酸痛"]},
    "二便": {"type": "multi", "options": ["大便干结", "大便稀溏", "小便频多", "小便短黄", "夜尿偏多", "二便正常"]},
    "饮食口味": {"type": "multi", "options": ["口干多饮", "口苦", "口黏腻", "口淡无味", "食欲不振", "多食易饥"]},
    "睡眠": {"type": "single", "options": ["入睡困难", "多梦易醒", "早醒难再睡", "睡眠尚可"]},
    "情志": {"type": "single", "options": ["心烦易怒", "焦虑紧张", "情绪低落", "精神尚平稳"]},
    "舌象": {"type": "multi", "options": ["舌质偏红", "舌质淡白", "苔薄白", "苔黄腻", "少苔或无苔", "不清楚"]},
    "脉象": {"type": "single", "options": ["脉细数", "脉沉迟", "脉弦", "脉滑", "不清楚"]},
    "程度": {"type": "slider", "min": 0, "max": 10, "min_label": "很轻", "max_label": "很重", "unit": "分"},
}


def _match_dimension(key: str) -> Optional[str]:
    """把 LLM 给的 key 模糊匹配到选项库维度。"""
    key = (key or "").strip()
    if not key:
        return None
    for dim in INQUIRY_OPTIONS:
        if dim in key or key in dim:
            return dim
    return None


_VALID_TYPES = {"single", "multi", "slider", "text"}


def _norm_options(raw: Any) -> list[dict]:
    """归一化 LLM 给的选项为 [{label,value}]，去重、限长。"""
    out: list[dict] = []
    seen: set[str] = set()
    for o in raw or []:
        if isinstance(o, dict):
            label = (o.get("label") or o.get("value") or "").strip()
        else:
            label = str(o).strip()
        if label and label not in seen:
            seen.add(label)
            out.append({"label": label, "value": label})
        if len(out) >= 8:
            break
    return out


def _slider_from_lib_or_llm(key: str, item: dict, dim: Optional[str]) -> dict:
    cfg = INQUIRY_OPTIONS.get(dim or "", {})
    return {
        "key": dim or key, "question": (item.get("question") or "").strip(), "type": "slider", "options": [],
        "min": int(item.get("min", cfg.get("min", 0)) or 0),
        "max": int(item.get("max", cfg.get("max", 10)) or 10),
        "min_label": item.get("min_label") or cfg.get("min_label", "很轻"),
        "max_label": item.get("max_label") or cfg.get("max_label", "很重"),
        "unit": item.get("unit") or cfg.get("unit", "分"),
    }


_SUPPLEMENT_HINTS = ("补充", "其他不适", "还有什么", "还有没有", "其它不适")


def _is_supplement(item: dict, q_text: str, qtype: str) -> bool:
    """补充确认型识别：优先认模型显式标记，关键词兜底（防模型漏标）。
    仅 text 题型才可能是补充确认（有选项的问题不是开放式收尾）。"""
    if item.get("supplement") is True:
        return True
    return qtype == "text" and any(h in q_text for h in _SUPPLEMENT_HINTS)


def _build_question(item: Any) -> dict:
    """构成结构化问题。选项【优先用 LLM 自带】（与问题同源、必然对应），
    LLM 未给时才退回选项库按维度兜底，再不行退化为纯文本补充。"""
    if isinstance(item, str):
        return {"key": "其他", "question": item, "type": "text", "options": []}
    if not isinstance(item, dict):
        return {"key": "其他", "question": str(item), "type": "text", "options": []}

    q_text = (item.get("question") or "").strip()
    key = (item.get("key") or "").strip() or "其他"
    qtype = (item.get("type") or "").strip().lower()
    if qtype not in _VALID_TYPES:
        qtype = ""
    dim = _match_dimension(key)

    # 滑块
    if qtype == "slider" or (not qtype and dim and INQUIRY_OPTIONS[dim]["type"] == "slider"):
        return _slider_from_lib_or_llm(key, item, dim)

    # ① 优先：LLM 自带选项（保证与问题对应，杜绝错位）
    llm_opts = _norm_options(item.get("options"))
    if llm_opts:
        return {"key": key, "question": q_text, "type": qtype or "multi", "options": llm_opts}

    # ② 兜底：选项库按维度匹配
    if dim:
        cfg = INQUIRY_OPTIONS[dim]
        return {
            "key": dim, "question": q_text, "type": cfg["type"],
            "options": [{"label": o, "value": o} for o in cfg["options"]],
        }

    # ③ 无任何可用选项 → 纯文本补充
    return {
        "key": key, "question": q_text, "type": "text", "options": [],
        "supplement": _is_supplement(item, q_text, "text"),
    }


_INQUIRY_ROLES = {"user", "assistant"}


def _build_inquiry_messages(symptoms: str, history: Optional[list[dict]]) -> list[dict]:
    """组装多轮问诊对话：system + 完整问答记录。

    history 形如 [{"role":"user","content":主诉}, {"role":"assistant","content":问1},
    {"role":"user","content":答1}, ...]，按真实顺序排列，让模型据上下文连贯追问。
    无 history 时退回单轮（仅主诉），保持向后兼容。
    """
    convo: list[dict] = []
    for turn in history or []:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in _INQUIRY_ROLES and content:
            convo.append({"role": role, "content": content})
    if not convo:
        convo = [{"role": "user", "content": symptoms}]
    return [{"role": "system", "content": INQUIRY_SYSTEM_PROMPT}, *convo]


def _FALLBACK_INQUIRY_QUESTION() -> dict:
    """模型未就绪却没给出可用追问时的通用兜底问，确保不会空手误入辨证。"""
    return {
        "key": "补充",
        "question": "除了上面说的，还有哪些不适或细节可以补充？（如寒热、出汗、睡眠、二便、饮食、情志等）",
        "type": "text",
        "options": [],
        "supplement": True,
    }


async def run_inquiry(symptoms: str, history: Optional[list[dict]] = None) -> dict[str, Any]:
    """问诊充分性检查，返回【一个】结构化追问。LLM 不可用时降级放行。

    传入 history（完整问答记录）时，模型按多轮对话连贯追问：首问紧扣主诉，
    后续顺着上一条回答展开，已覆盖维度不再重复。
    """
    messages = _build_inquiry_messages(symptoms, history)
    try:
        raw = await chat_completion_json(messages)
        data = _parse_json_loose(raw) or {}
        raw_qs = data.get("questions") or []
        # 只取第一个，保持「一次一问」节奏
        questions = [_build_question(raw_qs[0])] if raw_qs else []

        # 已问答轮数（history 中的 assistant 提问数）：首轮只有主诉时为 0
        answered_turns = sum(
            1 for t in (history or [])
            if isinstance(t, dict) and t.get("role") == "assistant"
        )

        # 就绪判定（关键：绝不默认 True，避免四诊不足却误入辨证）：
        # · 模型给了追问 → 必未就绪（纠正模型漏标 ready=false 的常见情况）
        # · 首轮（尚未问过任何一问）→ 引导式至少问一次，绝不直接就绪
        # · 否则仅当模型显式 ready=true 才就绪
        if questions:
            ready = False
        elif answered_turns < 1:
            ready = False
        elif data.get("ready") is True:
            ready = True
        else:
            ready = False
        # 未就绪却没拿到可用问题 → 补一个通用追问，确保不会空手误入辨证
        if not ready and not questions:
            questions = [_FALLBACK_INQUIRY_QUESTION()]
        return {"ready": ready, "questions": questions}
    except Exception as e:
        # 硬故障（网络/超时等）才放行，避免问诊环卡死；辨证侧另有兜底
        logger.warning("问诊LLM调用失败，降级放行: %s", e)
        return {"ready": True, "questions": []}


def _enrich_evidence(result: dict, entries: list[KnowledgeEntry]) -> dict:
    """回填 step4 引证条目的真实出处（按 entry_id 匹配知识库）。"""
    by_id = {e.id: e for e in entries}
    evidence = result.get("step4_classic_evidence")
    if isinstance(evidence, list):
        for ev in evidence:
            if not isinstance(ev, dict):
                continue
            eid = ev.get("entry_id")
            entry = None
            if eid:
                entry = by_id.get(eid) or knowledge_service.get_entry(eid)
            if entry:
                s = entry.source
                ev["source"] = f"{s.book}{('·' + s.volume) if s.volume else ''}{('·' + s.section) if s.section else ''}"
                ev.setdefault("text", entry.original_text or entry.plain_explanation)
    return result


async def run_diagnose(symptoms: str, role: str, entries: list[KnowledgeEntry]) -> dict[str, Any]:
    """执行 8 步辨证思维链。按 role 切提示词，三套文风/侧重。LLM 不可用时返回结构化兜底结果。

    向后兼容：8 步字段对所有角色不变；仅 researcher 额外要求填 step9_research（理论溯源）。
    未知 role 退回 doctor 文风，保证总能出结果。
    """
    role = (role or "patient").strip().lower()
    role_instruction = ROLE_INSTRUCTIONS.get(role, ROLE_INSTRUCTIONS["doctor"])
    step9_schema = RESEARCHER_STEP9_SCHEMA if role == "researcher" else ""
    context = _format_context(entries)
    system = DIAGNOSE_SYSTEM_PROMPT.format(
        role_instruction=role_instruction,
        retrieved_context=context,
        step9_schema=step9_schema,
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"患者主诉与问诊信息：\n{symptoms}"},
    ]
    try:
        raw = await chat_completion_json(messages, max_tokens=4096)
        data = _parse_json_loose(raw)
        if not data:
            raise ValueError("辨证结果非合法JSON")
        return _enrich_evidence(data, entries)
    except Exception as e:
        logger.error("辨证LLM调用失败: %s", e)
        return _fallback_result(symptoms, str(e))


def _fallback_result(symptoms: str, error: str) -> dict[str, Any]:
    """LLM 不可用时的兜底，保持与 8 步结构一致，前端不至于崩。"""
    return {
        "step1_symptom_summary": f"已记录主诉：{symptoms}",
        "step2_location_nature": {"病位": [], "病性": [], "气血津液": "待辨"},
        "step3_syndrome": {
            "主证": "待辨证",
            "兼证": [],
            "confidence": 0.0,
            "syndrome_candidates": [],
        },
        "step4_classic_evidence": [],
        "step5_treatment": "",
        "step6_formula": {"name": "", "composition": [], "modification": ""},
        "step7_care": {"contraindication": "", "diet": "", "lifestyle": "", "exercise": ""},
        "step8_disclaimer": "本结果为学术研究与辅助参考，不替代执业医师面诊。",
        "_error": f"模型暂不可用：{error}",
    }
