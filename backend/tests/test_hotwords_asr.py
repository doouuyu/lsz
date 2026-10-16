from pathlib import Path

from app.api.v2.asr import _run_task, _upstream_connect_options
from app.services.hotwords import build_hotwords


def test_generated_hotwords_are_bounded_and_valid() -> None:
    root = Path(__file__).resolve().parent.parent / "data"
    words = build_hotwords(
        [root / "knowledge_base.json", root / "chronic_diseases.json"]
    )
    assert len(words) <= 500
    assert len({item["text"] for item in words}) == len(words)
    assert all(2 <= len(item["text"]) <= 15 for item in words)
    assert all(item["weight"] in {2, 3, 4} for item in words)


def test_asr_task_uses_fixed_snapshot_and_stream_format() -> None:
    payload = _run_task("a" * 32)["payload"]
    assert payload["model"] == "fun-asr-realtime-2026-02-28"
    assert payload["parameters"]["format"] == "mp3"
    assert payload["parameters"]["sample_rate"] == 16000


def test_asr_workspace_connection_does_not_inherit_local_proxy() -> None:
    assert _upstream_connect_options()["proxy"] is None
