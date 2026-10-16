#!/usr/bin/env python3
"""真实百炼 V2 冒烟：默认不进 CI，需要已启动且配置完成的后端。"""

from __future__ import annotations

import argparse
import mimetypes
import time
from pathlib import Path

import httpx


def wait(client: httpx.Client, base: str, task_id: str, headers: dict) -> dict:
    deadline = time.monotonic() + 20 * 60
    while time.monotonic() < deadline:
        response = client.get(f"{base}/api/v2/tasks/{task_id}", headers=headers)
        response.raise_for_status()
        task = response.json()
        if task["status"] == "succeeded":
            return task["result"]
        if task["status"] in {"failed", "expired"}:
            raise RuntimeError(str(task.get("error") or task["status"]))
        time.sleep(2)
    raise TimeoutError("V2 冒烟任务超时")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--attachment", type=Path)
    parser.add_argument("--chief", default="近一个月容易乏力，活动后气短")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    with httpx.Client(timeout=180) as client:
        created = client.post(
            f"{base}/api/v2/consultations", json={"role": "patient"}
        )
        created.raise_for_status()
        session = created.json()
        consultation_id = session["consultation_id"]
        headers = {"X-Consultation-Token": session["consultation_token"]}
        if args.attachment:
            mime = mimetypes.guess_type(args.attachment.name)[0] or "application/octet-stream"
            with args.attachment.open("rb") as stream:
                uploaded = client.post(
                    f"{base}/api/v2/consultations/{consultation_id}/attachments",
                    headers=headers,
                    files={"file": (args.attachment.name, stream, mime)},
                )
            uploaded.raise_for_status()
        prepare = client.post(
            f"{base}/api/v2/consultations/{consultation_id}/prepare",
            headers={**headers, "Idempotency-Key": "smoke-prepare"},
            json={"chief_complaint": args.chief},
        )
        prepare.raise_for_status()
        result = wait(client, base, prepare.json()["task_id"], headers)
        rounds = 0
        while not result.get("ready") and rounds < 8:
            rounds += 1
            answer = client.post(
                f"{base}/api/v2/consultations/{consultation_id}/answers",
                headers={**headers, "Idempotency-Key": f"smoke-answer-{rounds}"},
                json={"answer": "不太清楚", "skipped": True},
            )
            answer.raise_for_status()
            result = wait(client, base, answer.json()["task_id"], headers)
        final = client.post(
            f"{base}/api/v2/consultations/{consultation_id}/finalize",
            headers={**headers, "Idempotency-Key": "smoke-final"},
        )
        final.raise_for_status()
        report = wait(client, base, final.json()["task_id"], headers)["report"]
        required = [f"step{i}_" for i in range(1, 9)]
        if not all(any(key.startswith(prefix) for key in report) for prefix in required):
            raise AssertionError("真实接口未返回完整八步结构")
        print(f"真实百炼 V2 冒烟通过：{consultation_id}，问诊 {rounds} 轮")


if __name__ == "__main__":
    main()
