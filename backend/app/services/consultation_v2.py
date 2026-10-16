"""V2 多模态问诊编排：初读、3～8 轮追问、RAG 与最终报告。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.models.consultation_v2 import (
    Consultation,
    ConsultationStatus,
    TaskStatus,
)
from app.models.knowledge import KnowledgeEntry
from app.services.attachment_store import AttachmentStore
from app.services.consultation_store import ConsultationStore
from app.services.knowledge import knowledge_service
from app.services.multimodal_llm import (
    ModelOutputError,
    ModelUnavailableError,
    MultimodalGateway,
)
from app.services.task_store import TaskStore

logger = logging.getLogger("consultation_v2")


FALLBACK_QUESTION = {
    "key": "补充",
    "question": "请再说说寒热、出汗、睡眠、饮食或二便方面最明显的一项变化。",
    "type": "text",
    "options": [],
    "min": 0,
    "max": 10,
    "min_label": "",
    "max_label": "",
    "unit": "",
    "supplement": True,
}


class TaskTimeoutError(TimeoutError):
    pass


def _entry_payload(entry: KnowledgeEntry) -> dict[str, Any]:
    source = entry.source
    source_text = (
        f"{source.book}{('·' + source.volume) if source.volume else ''}"
        f"{('·' + source.section) if source.section else ''}"
    )
    return {
        "entry_id": entry.id,
        "source": source_text,
        "original_text": entry.original_text,
        "plain_explanation": entry.plain_explanation,
    }


def enrich_evidence(
    report: dict[str, Any], entries: list[KnowledgeEntry]
) -> dict[str, Any]:
    allowed = {entry.id: entry for entry in entries}
    evidence = report.get("step4_classic_evidence")
    output: list[dict[str, Any]] = []
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            entry = allowed.get(str(item.get("entry_id") or ""))
            if not entry:
                continue
            payload = _entry_payload(entry)
            output.append(
                {
                    "entry_id": entry.id,
                    "text": entry.original_text or entry.plain_explanation,
                    "source": payload["source"],
                }
            )
    report["step4_classic_evidence"] = output
    return report


class ConsultationV2Service:
    def __init__(
        self,
        consultations: ConsultationStore,
        tasks: TaskStore,
        attachments: AttachmentStore,
        gateway: MultimodalGateway,
    ) -> None:
        self.consultations = consultations
        self.tasks = tasks
        self.attachments = attachments
        self.gateway = gateway

    @staticmethod
    def task_timeout(operation_name: str) -> int:
        attempts = min(max(settings.MODEL_MAX_RETRIES, 0), 1) + 1
        if operation_name == "run_prepare":
            return attempts * (
                settings.PREPARE_MODEL_TIMEOUT_SECONDS
                + settings.INQUIRY_MODEL_TIMEOUT_SECONDS
            ) + 30
        if operation_name == "run_answer":
            return attempts * settings.INQUIRY_MODEL_TIMEOUT_SECONDS + 30
        return attempts * (
            settings.RETRIEVAL_MODEL_TIMEOUT_SECONDS
            + settings.FINAL_MODEL_TIMEOUT_SECONDS
        ) + 60

    @staticmethod
    def _images(consultation: Consultation) -> list[str]:
        return [
            path
            for attachment in consultation.attachments
            for path in attachment.processed_paths
        ]

    @staticmethod
    def _image_sequence(consultation: Consultation) -> list[dict[str, Any]]:
        return [
            {
                "attachment_id": attachment.id,
                "page_number": page_number,
                "total_pages": attachment.pages,
            }
            for attachment in consultation.attachments
            for page_number, _ in enumerate(attachment.processed_paths, 1)
        ]

    @staticmethod
    def _base_case(consultation: Consultation) -> dict[str, Any]:
        return {
            "role": consultation.role.value,
            "chief_complaint": consultation.chief_complaint,
            "attachment_observations": consultation.observations,
            "history": consultation.history,
            "completed_rounds": len(consultation.history),
        }

    async def run_prepare(self, task_id: str, consultation: Consultation) -> None:
        self.tasks.update(task_id, TaskStatus.PROCESSING)
        self.consultations.touch(consultation)
        consultation.status = ConsultationStatus.PREPARING
        case = {
            "role": consultation.role.value,
            "chief_complaint": consultation.chief_complaint,
            "attachments": [
                {
                    "attachment_id": item.id,
                    "filename": item.filename,
                    "pages": item.pages,
                }
                for item in consultation.attachments
            ],
            "image_sequence": self._image_sequence(consultation),
        }
        logger.info("prepare input consultation=%s case=%s", consultation.id, case)
        degraded = False
        try:
            result = await self.gateway.prepare(case, self._images(consultation))
        except (ModelUnavailableError, ModelOutputError):
            degraded = True
            consultation.observations = {
                "attachments": [
                    {
                        "attachment_id": item.id,
                        "readable": False,
                        "quality_issues": ["首次识别失败"],
                    }
                    for item in consultation.attachments
                ],
                "medical_keywords": [],
            }
            result = await self.gateway.inquiry(self._base_case(consultation))
        consultation.observations = {
            "attachments": result.get(
                "attachments", consultation.observations.get("attachments", [])
            ),
            "medical_keywords": result.get(
                "medical_keywords",
                consultation.observations.get("medical_keywords", []),
            ),
        }
        question = result.get("next_question") or FALLBACK_QUESTION
        logger.info(
            "prepare output consultation=%s observations=%s question=%s",
            consultation.id,
            consultation.observations,
            question,
        )
        consultation.current_question = question
        consultation.status = ConsultationStatus.INQUIRY
        consultation.active_task_id = None
        self.tasks.update(
            task_id,
            TaskStatus.SUCCEEDED,
            {
                "ready": False,
                "next_question": question,
                "attachment_warning": degraded,
            },
        )

    async def run_answer(self, task_id: str, consultation: Consultation) -> None:
        self.tasks.update(task_id, TaskStatus.PROCESSING)
        self.consultations.touch(consultation)
        completed_rounds = len(consultation.history)
        logger.info(
            "inquiry input consultation=%s case=%s",
            consultation.id,
            self._base_case(consultation),
        )
        if completed_rounds >= 8:
            consultation.forced_finalize = True
            result = {"ready": True, "next_question": None}
        else:
            result = await self.gateway.inquiry(self._base_case(consultation))
            if completed_rounds < 3:
                result["ready"] = False
            if not result.get("ready") and not result.get("next_question"):
                result["next_question"] = FALLBACK_QUESTION
        if result.get("ready") or completed_rounds >= 8:
            consultation.status = ConsultationStatus.READY
            consultation.current_question = None
            result = {"ready": True, "next_question": None}
        else:
            consultation.status = ConsultationStatus.INQUIRY
            consultation.current_question = result["next_question"]
        consultation.active_task_id = None
        logger.info("inquiry output consultation=%s result=%s", consultation.id, result)
        self.tasks.update(task_id, TaskStatus.SUCCEEDED, result)

    def _retrieve(self, queries: list[str]) -> list[KnowledgeEntry]:
        entries: list[KnowledgeEntry] = []
        seen: set[str] = set()
        for query in queries[:5]:
            hits = knowledge_service.search(
                query, verified_only=True, top_k=5
            )
            if not hits:
                hits = knowledge_service.search(
                    query, verified_only=False, top_k=5
                )
            for entry in hits:
                if entry.id not in seen:
                    seen.add(entry.id)
                    entries.append(entry)
        return entries[:10]

    async def run_finalize(self, task_id: str, consultation: Consultation) -> None:
        self.tasks.update(task_id, TaskStatus.PROCESSING)
        self.consultations.touch(consultation)
        consultation.status = ConsultationStatus.FINALIZING
        case = self._base_case(consultation)
        try:
            terms = await self.gateway.retrieval_terms(case)
            queries = terms.get("queries") or []
        except (ModelUnavailableError, ModelOutputError):
            terms = {"queries": []}
            queries = []
        if not queries:
            answers = " ".join(
                str(turn.get("answer") or "") for turn in consultation.history
            )
            queries = [f"{consultation.chief_complaint} {answers}".strip()]
        entries = await asyncio.to_thread(self._retrieve, queries)
        final_case = {
            **case,
            "retrieval_terms": terms,
            "rag_entries": [_entry_payload(entry) for entry in entries],
            "correction_boundary": "不得改变否定、部位、时间、频率、数值、单位、药名剂量和过敏史",
            "image_sequence": self._image_sequence(consultation),
        }
        logger.info(
            "final input consultation=%s retrieval_terms=%s rag_entries=%s case=%s",
            consultation.id,
            terms,
            final_case["rag_entries"],
            case,
        )
        try:
            report = await self.gateway.final(final_case, self._images(consultation))
        except (ModelUnavailableError, ModelOutputError) as exc:
            consultation.status = ConsultationStatus.FAILED
            self.consultations.touch(consultation)
            consultation.active_task_id = None
            code = (
                "MODEL_OUTPUT_INVALID"
                if isinstance(exc, ModelOutputError)
                else "MODEL_UNAVAILABLE"
            )
            self.tasks.update(
                task_id,
                TaskStatus.FAILED,
                error={"code": code, "message": "报告生成失败，可在 30 分钟内重试"},
            )
            return
        report = enrich_evidence(report, entries)
        report["step8_disclaimer"] = (
            "本结果仅供中医健康咨询与辅助参考，不替代执业医师面诊、诊断和治疗。"
        )
        if consultation.role.value == "patient":
            formula = report.get("step6_formula")
            composition = formula.get("composition") if isinstance(formula, dict) else []
            for herb in composition if isinstance(composition, list) else []:
                if isinstance(herb, dict):
                    herb["dosage"] = ""
        if consultation.forced_finalize:
            summary = str(report.get("step1_symptom_summary") or "")
            report["step1_symptom_summary"] = (
                f"{summary}；已达到问诊轮次上限，仍可能有信息缺失。"
            ).strip("；")
            syndrome = report.get("step3_syndrome")
            if isinstance(syndrome, dict):
                confidence = float(syndrome.get("confidence") or 0)
                syndrome["confidence"] = min(confidence, 0.5)
        logger.info("final output consultation=%s report=%s", consultation.id, report)
        consultation.report = report
        consultation.status = ConsultationStatus.COMPLETED
        consultation.active_task_id = None
        self.attachments.delete_all(consultation)
        self.tasks.update(
            task_id,
            TaskStatus.SUCCEEDED,
            {"report": report, "sources": [_entry_payload(entry) for entry in entries]},
        )

    def fail_task(self, task_id: str, consultation: Consultation, exc: Exception) -> None:
        logger.error(
            "V2 task failed task=%s consultation=%s error=%s",
            task_id,
            consultation.id,
            type(exc).__name__,
        )
        task = self.tasks.get(task_id)
        if task and task.type == "answer":
            consultation.status = ConsultationStatus.INQUIRY
            if consultation.history:
                consultation.history.pop()
        elif task and task.type == "prepare":
            consultation.status = ConsultationStatus.DRAFT
        else:
            consultation.status = ConsultationStatus.FAILED
        consultation.active_task_id = None
        code = (
            "MODEL_TIMEOUT"
            if isinstance(exc, TaskTimeoutError)
            else (
                "MODEL_OUTPUT_INVALID"
                if isinstance(exc, ModelOutputError)
                else "MODEL_UNAVAILABLE"
            )
        )
        self.tasks.update(
            task_id,
            TaskStatus.FAILED,
            error={"code": code, "message": "模型任务失败，请重试"},
        )
