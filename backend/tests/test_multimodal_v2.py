from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.config import settings
from app.prompts.consultation_v2_prompts import FINAL_PROMPT
from app.services.multimodal_llm import (
    MultimodalGateway,
    ModelOutputError,
    parse_json_object,
    validate_final_report,
    validate_inquiry_result,
)
from app.services.consultation_v2 import enrich_evidence
from app.services.consultation_v2 import ConsultationV2Service


def valid_report() -> dict:
    return {
        "step1_symptom_summary": "乏力",
        "step2_location_nature": {"病位": ["脾"], "病性": ["虚"], "气血津液": "气虚"},
        "step3_syndrome": {
            "主证": "脾气虚",
            "兼证": [],
            "confidence": 0.7,
            "syndrome_candidates": [],
        },
        "step4_classic_evidence": [],
        "step5_treatment": "健脾益气",
        "step6_formula": {"name": "", "composition": [], "modification": ""},
        "step7_care": {
            "contraindication": "",
            "diet": "",
            "lifestyle": "",
            "exercise": "",
        },
        "step8_disclaimer": "本结果不替代执业医师面诊。",
    }


def test_json_code_fence_is_accepted() -> None:
    assert parse_json_object('```json\n{"ready": false}\n```') == {"ready": False}


def test_truncated_json_is_rejected() -> None:
    try:
        parse_json_object('{"ready":')
    except ModelOutputError:
        pass
    else:
        raise AssertionError("截断 JSON 必须失败")


def test_inquiry_requires_one_valid_question_when_not_ready() -> None:
    try:
        validate_inquiry_result({"ready": False})
    except ModelOutputError:
        pass
    else:
        raise AssertionError("未就绪时必须返回一个问题")


def test_final_report_requires_all_eight_steps() -> None:
    report = valid_report()
    report.pop("step6_formula")
    try:
        validate_final_report(report)
    except ModelOutputError:
        pass
    else:
        raise AssertionError("八步报告缺字段必须失败")


def test_forged_evidence_id_is_removed() -> None:
    report = valid_report()
    report["step4_classic_evidence"] = [
        {"entry_id": "forged", "text": "伪造", "source": "伪造"}
    ]
    assert enrich_evidence(report, [])["step4_classic_evidence"] == []


def test_invalid_model_json_is_retried_only_once(monkeypatch) -> None:
    responses = ['{"ready":', '{"ready":true}']

    async def create(**kwargs):
        raw = responses.pop(0)
        return SimpleNamespace(
            id="mock",
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw))],
        )

    gateway = MultimodalGateway()
    gateway._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    monkeypatch.setattr(settings, "BAILIAN_API_KEY", "test")
    monkeypatch.setattr(settings, "BAILIAN_WORKSPACE_ID", "test")
    result = asyncio.run(gateway.inquiry({"completed_rounds": 3}))

    assert result["ready"] is True
    assert responses == []


def test_outer_task_timeout_covers_all_internal_attempts() -> None:
    assert ConsultationV2Service.task_timeout("run_answer") > 2 * 120
    assert ConsultationV2Service.task_timeout("run_prepare") > 2 * (180 + 120)
    assert ConsultationV2Service.task_timeout("run_finalize") > 2 * (180 + 600)


def test_final_prompt_exposes_nested_report_contract() -> None:
    required_fields = {
        '"病位"',
        '"主证"',
        '"syndrome_candidates"',
        '"entry_id"',
        '"composition"',
        '"contraindication"',
    }
    assert all(field in FINAL_PROMPT for field in required_fields)
