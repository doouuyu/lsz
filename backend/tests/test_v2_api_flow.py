from __future__ import annotations

import io
import time

from fastapi.testclient import TestClient
from PIL import Image

from app.api.v2.dependencies import (
    attachment_store,
    consultation_service,
    consultation_store,
    multimodal_gateway,
    task_store,
)
from app.main import app


def jpeg() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (20, 20), "pink").save(output, "JPEG")
    return output.getvalue()


def report() -> dict:
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
        "step6_formula": {
            "name": "测试方",
            "composition": [
                {"herb": "黄芪", "dosage": "10g", "role": "君", "reason": "测试"}
            ],
            "modification": "",
        },
        "step7_care": {
            "contraindication": "",
            "diet": "",
            "lifestyle": "",
            "exercise": "",
        },
        "step8_disclaimer": "本结果不替代执业医师面诊。",
    }


def poll(client: TestClient, task_id: str, headers: dict) -> dict:
    for _ in range(100):
        response = client.get(f"/api/v2/tasks/{task_id}", headers=headers)
        body = response.json()
        if body["status"] in {"succeeded", "failed"}:
            return body
        time.sleep(0.01)
    raise AssertionError("任务未完成")


def test_mock_end_to_end(monkeypatch) -> None:
    consultation_store._items.clear()
    task_store._items.clear()
    task_store._idempotency.clear()

    async def prepare(case, images):
        return {
            "attachments": [
                {
                    "attachment_id": attachment["attachment_id"],
                    "inferred_type": inferred_type,
                    "readable": True,
                    "findings": ["测试观察"],
                }
                for attachment, inferred_type in zip(
                    case["attachments"],
                    ["tongue", "lab_report", "prescription", "medical_record"],
                )
            ],
            "medical_keywords": ["乏力", "舌淡"],
            "next_question": {
                "key": "寒热",
                "question": "平时怕冷吗？",
                "type": "single",
                "options": [{"label": "怕冷", "value": "怕冷"}],
            },
        }

    async def inquiry(case):
        ready = case["completed_rounds"] >= 3
        return {
            "ready": ready,
            "next_question": None
            if ready
            else {
                "key": "睡眠",
                "question": "睡眠怎么样？",
                "type": "text",
                "options": [],
            },
        }

    async def retrieval(case):
        return {"queries": ["乏力 脾虚"]}

    async def final(case, images):
        return report()

    monkeypatch.setattr(multimodal_gateway, "prepare", prepare)
    monkeypatch.setattr(multimodal_gateway, "inquiry", inquiry)
    monkeypatch.setattr(multimodal_gateway, "retrieval_terms", retrieval)
    monkeypatch.setattr(multimodal_gateway, "final", final)
    monkeypatch.setattr(consultation_service, "_retrieve", lambda queries: [])

    with TestClient(app) as client:
        created = client.post(
            "/api/v2/consultations", json={"role": "patient"}
        ).json()
        consultation_id = created["consultation_id"]
        headers = {"X-Consultation-Token": created["consultation_token"]}
        for filename in [
            "tongue.jpg",
            "lab-report.jpg",
            "prescription.jpg",
            "medical-record.jpg",
        ]:
            upload = client.post(
                f"/api/v2/consultations/{consultation_id}/attachments",
                headers=headers,
                files={"file": (filename, jpeg(), "image/jpeg")},
            )
            assert upload.status_code == 201

        idem_headers = {**headers, "Idempotency-Key": "prepare-1"}
        accepted = client.post(
            f"/api/v2/consultations/{consultation_id}/prepare",
            headers=idem_headers,
            json={"chief_complaint": "最近乏力"},
        ).json()
        repeated = client.post(
            f"/api/v2/consultations/{consultation_id}/prepare",
            headers=idem_headers,
            json={"chief_complaint": "最近乏力"},
        ).json()
        assert repeated["task_id"] == accepted["task_id"]
        assert poll(client, accepted["task_id"], headers)["status"] == "succeeded"

        for index in range(3):
            answer_task = client.post(
                f"/api/v2/consultations/{consultation_id}/answers",
                headers={**headers, "Idempotency-Key": f"answer-{index}"},
                json={"answer": "一般", "skipped": index == 1},
            ).json()
            answer_result = poll(client, answer_task["task_id"], headers)
        assert answer_result["result"]["ready"] is True

        final_task = client.post(
            f"/api/v2/consultations/{consultation_id}/finalize",
            headers={**headers, "Idempotency-Key": "final-1"},
        ).json()
        final_result = poll(client, final_task["task_id"], headers)
        assert final_result["status"] == "succeeded"
        assert "step8_disclaimer" in final_result["result"]["report"]
        assert (
            final_result["result"]["report"]["step6_formula"]["composition"][0][
                "dosage"
            ]
            == ""
        )
        assert consultation_store.get(consultation_id).attachments == []
