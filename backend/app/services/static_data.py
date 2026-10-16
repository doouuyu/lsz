"""静态养生 / 慢病数据加载（预生成内容，避免实时调模型，省成本提速）"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load(name: str) -> dict:
    path = DATA_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# 启动即加载到内存
SEASONAL = _load("regimen_seasonal.json")
ORGAN = _load("regimen_organ.json")
CHRONIC = _load("chronic_diseases.json")
