"""固定百炼多模态模型客户端、重试和结构校验。"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import re
import time
from pathlib import Path
from typing import Any, Callable

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings
from app.prompts.consultation_v2_prompts import (
    FINAL_PROMPT,
    INQUIRY_PROMPT,
    PREPARE_PROMPT,
    RETRIEVAL_PROMPT,
)

logger = logging.getLogger("consultation_v2.model")
EXPECTED_MULTIMODAL_MODEL = "qwen3.7-plus-2026-05-26"


class ModelUnavailableError(RuntimeError):
    pass


class ModelOutputError(ValueError):
    pass


class LocationNatureContract(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    locations: list[str] = Field(alias="病位")
    natures: list[str] = Field(alias="病性")
    qi_blood_fluid: str = Field(alias="气血津液")


class SyndromeContract(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    primary: str = Field(alias="主证")
    concurrent: list[str] = Field(alias="兼证")
    confidence: float
    syndrome_candidates: list[dict[str, Any]]


class FormulaContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    composition: list[dict[str, Any]]
    modification: str


class CareContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    contraindication: str
    diet: str
    lifestyle: str
    exercise: str


class FinalReportContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    step1_symptom_summary: str
    step2_location_nature: LocationNatureContract
    step3_syndrome: SyndromeContract
    step4_classic_evidence: list[dict[str, Any]]
    step5_treatment: str
    step6_formula: FormulaContract
    step7_care: CareContract
    step8_disclaimer: str


def parse_json_object(text: str) -> dict[str, Any]:
    value = (text or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*([\s\S]*?)\s*```", value)
    if fenced:
        value = fenced.group(1)
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ModelOutputError("模型返回的 JSON 无效或被截断") from exc
    if not isinstance(data, dict):
        raise ModelOutputError("模型必须返回 JSON 对象")
    return data


def normalize_question(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or not str(raw.get("question") or "").strip():
        raise ModelOutputError("模型未返回有效问题")
    question_type = str(raw.get("type") or "text")
    if question_type not in {"single", "multi", "slider", "text"}:
        question_type = "text"
    options = []
    for option in raw.get("options") or []:
        label = (
            str(option.get("label") or option.get("value") or "").strip()
            if isinstance(option, dict)
            else str(option).strip()
        )
        if label and label not in [item["value"] for item in options]:
            options.append({"label": label, "value": label})
    return {
        "key": str(raw.get("key") or "其他")[:100],
        "question": str(raw["question"]).strip(),
        "type": question_type,
        "options": options[:8],
        "min": int(raw.get("min") or 0),
        "max": int(raw.get("max") or 10),
        "min_label": str(raw.get("min_label") or ""),
        "max_label": str(raw.get("max_label") or ""),
        "unit": str(raw.get("unit") or ""),
        "supplement": raw.get("supplement") is True,
    }


def validate_prepare_result(data: dict[str, Any]) -> dict[str, Any]:
    attachments = data.get("attachments")
    keywords = data.get("medical_keywords")
    if not isinstance(attachments, list) or not isinstance(keywords, list):
        raise ModelOutputError("首次附件观察结构无效")
    allowed = {
        "tongue",
        "lab_report",
        "prescription",
        "medical_record",
        "unknown",
    }
    for item in attachments:
        if (
            not isinstance(item, dict)
            or not str(item.get("attachment_id") or "")
            or item.get("inferred_type") not in allowed
            or not isinstance(item.get("readable"), bool)
        ):
            raise ModelOutputError("附件分类结构无效")
    data["attachments"] = attachments
    data["medical_keywords"] = [str(item) for item in keywords]
    data["ready"] = False
    data["next_question"] = normalize_question(data.get("next_question"))
    return data


def validate_inquiry_result(data: dict[str, Any]) -> dict[str, Any]:
    ready = data.get("ready") is True
    question = data.get("next_question")
    if not ready:
        question = normalize_question(question)
    elif question:
        question = normalize_question(question)
    return {"ready": ready, "next_question": question}


def validate_retrieval_terms(data: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "symptom_terms",
        "tcm_terms",
        "tongue_pulse_terms",
        "medicine_terms",
        "queries",
    ]
    if not isinstance(data.get("queries"), list):
        raise ModelOutputError("检索词结构无效")
    output = {}
    for key in keys:
        values = data.get(key)
        output[key] = [
            str(value).strip()
            for value in values
            if str(value).strip()
        ][:10] if isinstance(values, list) else []
    return output


def validate_final_report(data: dict[str, Any]) -> dict[str, Any]:
    try:
        validated = FinalReportContract.model_validate(data)
    except ValidationError as exc:
        raise ModelOutputError("八步报告结构无效") from exc
    if not validated.step8_disclaimer.strip():
        raise ModelOutputError("医疗免责声明不能为空")
    return validated.model_dump(by_alias=True)


def _image_block(path: str) -> dict[str, Any]:
    suffix = Path(path).suffix.lower()
    mime = mimetypes.types_map.get(suffix, "image/jpeg")
    encoded = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def _retryable(error: Exception) -> bool:
    return isinstance(
        error,
        (
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
            ModelOutputError,
        ),
    )


class MultimodalGateway:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    def available(self) -> bool:
        return bool(
            settings.BAILIAN_API_KEY
            and settings.BAILIAN_WORKSPACE_ID
            and settings.MULTIMODAL_MODEL == EXPECTED_MULTIMODAL_MODEL
        )

    def _get_client(self) -> AsyncOpenAI:
        if not self.available():
            raise ModelUnavailableError(
                "未配置百炼 API Key/Workspace ID，或 V2 模型不是固定快照 "
                f"{EXPECTED_MULTIMODAL_MODEL}"
            )
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.BAILIAN_API_KEY,
                base_url=settings.BAILIAN_BASE_URL,
                default_headers={"X-DashScope-WorkSpace": settings.BAILIAN_WORKSPACE_ID},
            )
        return self._client

    async def _call(
        self,
        system: str,
        case: dict[str, Any],
        image_paths: list[str],
        timeout: int,
        thinking: bool,
        validator: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": json.dumps(case, ensure_ascii=False)}
        ]
        content.extend(_image_block(path) for path in image_paths)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ]
        logger.info(
            "model input model=%s thinking=%s system=%s case=%s image_count=%d",
            settings.MULTIMODAL_MODEL,
            thinking,
            system,
            json.dumps(case, ensure_ascii=False),
            len(image_paths),
        )
        first_error: Exception | None = None
        attempts = min(max(settings.MODEL_MAX_RETRIES, 0), 1) + 1
        for attempt in range(attempts):
            if attempt:
                await asyncio.sleep(0.5)
            try:
                started_at = time.perf_counter()
                response = await self._get_client().chat.completions.create(
                    model=settings.MULTIMODAL_MODEL,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=8192,
                    response_format={"type": "json_object"},
                    extra_body={"enable_thinking": thinking},
                    timeout=timeout,
                )
                raw = response.choices[0].message.content or ""
                logger.info(
                    "model output model=%s request_id=%s elapsed_ms=%d usage=%s raw=%s",
                    settings.MULTIMODAL_MODEL,
                    getattr(response, "id", ""),
                    int((time.perf_counter() - started_at) * 1000),
                    getattr(response, "usage", None),
                    raw,
                )
                return validator(parse_json_object(raw))
            except Exception as exc:
                first_error = first_error or exc
                logger.warning(
                    "V2 模型调用失败 model=%s attempt=%d/%d error=%s",
                    settings.MULTIMODAL_MODEL,
                    attempt + 1,
                    attempts,
                    type(exc).__name__,
                )
                if isinstance(exc, ModelOutputError) and attempt == 0:
                    messages.append(
                        {
                            "role": "system",
                            "content": "上次输出 JSON 结构无效；仅修复 JSON 结构，不得改变原始病例事实。",
                        }
                    )
                if isinstance(exc, BadRequestError) or not _retryable(exc):
                    break
        if isinstance(first_error, ModelOutputError):
            raise first_error
        raise ModelUnavailableError("固定多模态模型调用失败") from first_error

    async def prepare(self, case: dict[str, Any], images: list[str]) -> dict[str, Any]:
        return await self._call(
            PREPARE_PROMPT,
            case,
            images,
            settings.PREPARE_MODEL_TIMEOUT_SECONDS,
            False,
            validate_prepare_result,
        )

    async def inquiry(self, case: dict[str, Any]) -> dict[str, Any]:
        return await self._call(
            INQUIRY_PROMPT,
            case,
            [],
            settings.INQUIRY_MODEL_TIMEOUT_SECONDS,
            False,
            validate_inquiry_result,
        )

    async def retrieval_terms(self, case: dict[str, Any]) -> dict[str, Any]:
        return await self._call(
            RETRIEVAL_PROMPT,
            case,
            [],
            settings.RETRIEVAL_MODEL_TIMEOUT_SECONDS,
            False,
            validate_retrieval_terms,
        )

    async def final(
        self, case: dict[str, Any], images: list[str]
    ) -> dict[str, Any]:
        return await self._call(
            FINAL_PROMPT,
            case,
            images,
            settings.FINAL_MODEL_TIMEOUT_SECONDS,
            True,
            validate_final_report,
        )


multimodal_gateway = MultimodalGateway()
