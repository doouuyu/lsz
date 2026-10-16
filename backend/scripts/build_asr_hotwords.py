#!/usr/bin/env python3
"""生成热词 JSON；传 --sync 时在百炼创建或完整更新热词表。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.services.hotwords import write_hotwords


def sync(words: list[dict]) -> str:
    import dashscope
    from dashscope.audio.asr import VocabularyService

    if not settings.BAILIAN_API_KEY or not settings.BAILIAN_WORKSPACE_ID:
        raise RuntimeError("同步热词需要 BAILIAN_API_KEY 和 BAILIAN_WORKSPACE_ID")
    dashscope.api_key = settings.BAILIAN_API_KEY
    dashscope.base_http_api_url = (
        f"https://{settings.BAILIAN_WORKSPACE_ID}."
        "cn-beijing.maas.aliyuncs.com/api/v1"
    )
    service = VocabularyService(
        api_key=settings.BAILIAN_API_KEY,
        workspace=settings.BAILIAN_WORKSPACE_ID,
    )
    if settings.ASR_VOCABULARY_ID:
        service.update_vocabulary(settings.ASR_VOCABULARY_ID, words)
        return settings.ASR_VOCABULARY_ID
    return service.create_vocabulary(
        target_model=settings.ASR_MODEL,
        prefix="lsztcm",
        vocabulary=words,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data" / "asr_hotwords.json"
    )
    args = parser.parse_args()
    files = [
        ROOT / "data" / "knowledge_base.json",
        ROOT / "data" / "chronic_diseases.json",
        ROOT / "data" / "regimen_organ.json",
        ROOT / "data" / "regimen_seasonal.json",
    ]
    words = write_hotwords(files, args.output)
    print(json.dumps({"output": str(args.output), "count": len(words)}, ensure_ascii=False))
    if args.sync:
        vocabulary_id = sync(words)
        print(json.dumps({"vocabulary_id": vocabulary_id}, ensure_ascii=False))


if __name__ == "__main__":
    main()
