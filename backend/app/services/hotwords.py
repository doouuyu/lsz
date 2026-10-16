"""从现有中医知识与静态数据生成可审查的 ASR 热词表。"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

_CHINESE_TERM = re.compile(r"^[\u4e00-\u9fffA-Za-z0-9·（）()]{2,15}$")
_IGNORED = {
    "患者",
    "治疗",
    "疾病",
    "症状",
    "可以",
    "注意",
    "建议",
    "相关",
    "常见",
    "出现",
    "进行",
}
_LOWER_WEIGHT = {"人参", "生姜", "甘草", "头痛", "发热"}
_KEYS = {
    "title",
    "subcategory",
    "herb",
    "name",
    "syndrome",
    "symptoms",
    "related_syndromes",
    "tags",
}


def _collect(value: Any, key: str = "") -> list[str]:
    if isinstance(value, dict):
        return [
            term
            for child_key, child in value.items()
            for term in _collect(child, child_key)
        ]
    if isinstance(value, list):
        return [term for child in value for term in _collect(child, key)]
    if key not in _KEYS or not isinstance(value, str):
        return []
    candidates = re.split(r"[\s、，,；;：:/]+", value)
    return [
        term.strip()
        for term in candidates
        if _CHINESE_TERM.fullmatch(term.strip())
        and term.strip() not in _IGNORED
    ]


def build_hotwords(data_files: list[Path], limit: int = 500) -> list[dict]:
    counts: Counter[str] = Counter()
    for path in data_files:
        if path.exists():
            counts.update(_collect(json.loads(path.read_text(encoding="utf-8"))))
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [
        {
            "text": term,
            "weight": 3 if term in _LOWER_WEIGHT else 4,
            "lang": "zh",
        }
        for term, _ in ranked[:limit]
    ]


def write_hotwords(data_files: list[Path], output: Path) -> list[dict]:
    words = build_hotwords(data_files)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(words, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return words

