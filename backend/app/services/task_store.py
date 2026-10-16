"""V2 异步任务与幂等索引的进程内存储。"""

from __future__ import annotations

import secrets
from datetime import timedelta
from threading import RLock
from typing import Optional

from app.models.consultation_v2 import Task, TaskStatus, utc_now


class TaskStore:
    def __init__(self, ttl_seconds: int = 1800) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, Task] = {}
        self._idempotency: dict[tuple[str, str, str], str] = {}
        self._lock = RLock()

    def create(
        self,
        consultation_id: str,
        task_type: str,
        idempotency_key: Optional[str] = None,
    ) -> Task:
        index = (
            (consultation_id, task_type, idempotency_key)
            if idempotency_key
            else None
        )
        with self._lock:
            if index and index in self._idempotency:
                existing = self._items.get(self._idempotency[index])
                if existing:
                    return existing
            now = utc_now()
            task = Task(
                id=f"task_{secrets.token_hex(8)}",
                consultation_id=consultation_id,
                type=task_type,
                status=TaskStatus.QUEUED,
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(seconds=self.ttl_seconds),
                idempotency_key=idempotency_key,
            )
            self._items[task.id] = task
            if index:
                self._idempotency[index] = task.id
            return task

    def find_idempotent(
        self, consultation_id: str, task_type: str, idempotency_key: str
    ) -> Optional[Task]:
        if not idempotency_key:
            return None
        with self._lock:
            task_id = self._idempotency.get(
                (consultation_id, task_type, idempotency_key)
            )
            return self._items.get(task_id or "")

    def get(self, task_id: str) -> Optional[Task]:
        with self._lock:
            task = self._items.get(task_id)
            if task and task.expires_at <= utc_now():
                task.status = TaskStatus.EXPIRED
            return task

    def update(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        error: Optional[dict] = None,
    ) -> Optional[Task]:
        with self._lock:
            task = self._items.get(task_id)
            if not task:
                return None
            task.status = status
            task.result = result
            task.error = error
            task.updated_at = utc_now()
            return task

    def all(self) -> list[Task]:
        with self._lock:
            return list(self._items.values())

    def remove_for_consultation(self, consultation_id: str) -> None:
        with self._lock:
            doomed = [
                task_id
                for task_id, task in self._items.items()
                if task.consultation_id == consultation_id
            ]
            for task_id in doomed:
                self._items.pop(task_id, None)
            self._idempotency = {
                key: task_id
                for key, task_id in self._idempotency.items()
                if task_id not in doomed
            }
