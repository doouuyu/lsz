"""舌象识别任务存储 - 框架版用内存字典，后续可替换为 Redis

拍照舌诊改「提交 + 轮询」：提交接口同步校验图片后丢一个后台任务，立即回 task_id；
结果接口按 task_id 轮询 pending/done。避免视觉模型的 5~15s 耗时撑爆单个 HTTP 请求超时。

隐私红线：任务只保存分析结果（受控词表特征/文本），不保存任何图片。
单进程内存存储——多 worker 部署需换 Redis（与 session_store 同等约束）。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

_TASK_TTL = 300.0  # 结果保留 5 分钟，够前端轮询取走


@dataclass
class TongueTask:
    id: str
    status: str = "pending"  # pending | done
    result: Optional[dict[str, Any]] = None
    created_at: float = field(default_factory=time.monotonic)


class TongueTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, TongueTask] = {}

    def create(self) -> TongueTask:
        self._evict()
        tid = f"tg-{uuid.uuid4().hex[:12]}"
        task = TongueTask(id=tid)
        self._tasks[tid] = task
        return task

    def finish(self, task_id: str, result: dict[str, Any]) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task.result = result
            task.status = "done"

    def get(self, task_id: str) -> Optional[TongueTask]:
        return self._tasks.get(task_id)

    def _evict(self) -> None:
        """惰性清理过期任务，避免内存无界增长。"""
        now = time.monotonic()
        stale = [k for k, t in self._tasks.items() if now - t.created_at > _TASK_TTL]
        for k in stale:
            self._tasks.pop(k, None)


tongue_task_store = TongueTaskStore()
