"""Fun-ASR Realtime 的安全 WebSocket 代理；音频仅转发、不落盘。"""

from __future__ import annotations

import asyncio
import json
import uuid

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v2.dependencies import consultation_store
from app.config import settings

router = APIRouter(prefix="/asr", tags=["V2 实时语音"])
EXPECTED_ASR_MODEL = "fun-asr-realtime-2026-02-28"


def _upstream_url() -> str:
    if settings.BAILIAN_ASR_WS_URL:
        return settings.BAILIAN_ASR_WS_URL
    return (
        f"wss://{settings.BAILIAN_WORKSPACE_ID}."
        "cn-beijing.maas.aliyuncs.com/api-ws/v1/inference/"
    )


def _upstream_connect_options() -> dict[str, object]:
    return {
        # 百炼工作空间走固定 WSS 域名；不继承开发机上的 HTTP(S) 代理。
        "proxy": None,
        "ping_interval": 20,
        "ping_timeout": 20,
        "max_size": 4 * 1024 * 1024,
    }


def _run_task(task_id: str) -> dict:
    parameters: dict = {
        # 微信 RecorderManager 可稳定按帧输出 MP3；Fun-ASR 官方协议明确支持该流格式。
        "format": "mp3",
        "sample_rate": 16000,
        "language_hints": ["zh"],
        "semantic_punctuation_enabled": True,
    }
    if settings.ASR_VOCABULARY_ID:
        parameters["vocabulary_id"] = settings.ASR_VOCABULARY_ID
    return {
        "header": {
            "action": "run-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "asr",
            "function": "recognition",
            "model": settings.ASR_MODEL,
            "parameters": parameters,
            "input": {},
        },
    }


def _finish_task(task_id: str) -> dict:
    return {
        "header": {
            "action": "finish-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {"input": {}},
    }


async def _forward_event(client: WebSocket, raw: str) -> bool:
    event = json.loads(raw)
    header = event.get("header") or {}
    event_name = header.get("event")
    if event_name == "task-started":
        await client.send_json(
            {
                "type": "ready",
                "hotwords_loaded": bool(settings.ASR_VOCABULARY_ID),
            }
        )
    elif event_name == "result-generated":
        sentence = (
            ((event.get("payload") or {}).get("output") or {}).get("sentence")
            or {}
        )
        if not sentence.get("heartbeat"):
            await client.send_json(
                {
                    "type": "final" if sentence.get("sentence_end") else "partial",
                    "text": str(sentence.get("text") or ""),
                }
            )
    elif event_name == "task-finished":
        await client.send_json({"type": "finished"})
        return False
    elif event_name == "task-failed":
        await client.send_json(
            {
                "type": "error",
                "code": "ASR_UNAVAILABLE",
                "message": "语音识别失败，请重试或手动输入",
            }
        )
        return False
    return True


@router.websocket("/realtime")
async def realtime_asr(websocket: WebSocket) -> None:
    consultation_id = websocket.headers.get("x-consultation-id", "")
    token = websocket.headers.get("x-consultation-token", "")
    if not consultation_store.authenticate(consultation_id, token):
        await websocket.close(code=4401, reason="INVALID_CONSULTATION_TOKEN")
        return
    if (
        not settings.BAILIAN_API_KEY
        or not settings.BAILIAN_WORKSPACE_ID
        or settings.ASR_MODEL != EXPECTED_ASR_MODEL
    ):
        await websocket.close(code=1013, reason="ASR_UNAVAILABLE")
        return
    await websocket.accept()
    task_id = uuid.uuid4().hex
    headers = {
        "Authorization": f"Bearer {settings.BAILIAN_API_KEY}",
        "X-DashScope-WorkSpace": settings.BAILIAN_WORKSPACE_ID,
    }
    try:
        async with websockets.connect(
            _upstream_url(),
            additional_headers=headers,
            **_upstream_connect_options(),
        ) as upstream:
            await upstream.send(json.dumps(_run_task(task_id), ensure_ascii=False))
            running = await _forward_event(websocket, await upstream.recv())
            while running:
                client_receive = asyncio.create_task(websocket.receive())
                server_receive = asyncio.create_task(upstream.recv())
                done, pending = await asyncio.wait(
                    {client_receive, server_receive},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for pending_task in pending:
                    pending_task.cancel()
                if server_receive in done:
                    running = await _forward_event(
                        websocket, server_receive.result()
                    )
                if client_receive in done:
                    message = client_receive.result()
                    if message.get("bytes") is not None:
                        await upstream.send(message["bytes"])
                    elif message.get("text"):
                        command = json.loads(message["text"])
                        if command.get("type") == "finish":
                            await upstream.send(
                                json.dumps(_finish_task(task_id), ensure_ascii=False)
                            )
                        elif command.get("type") == "cancel":
                            break
                        elif command.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
    except (WebSocketDisconnect, websockets.ConnectionClosed):
        return
    except Exception:
        await websocket.send_json(
            {
                "type": "error",
                "code": "ASR_UNAVAILABLE",
                "message": "语音服务暂不可用，请手动输入",
            }
        )
