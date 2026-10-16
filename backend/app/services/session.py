"""会话存储 - 框架版用内存字典，后续可替换为 Redis

会话保存辨证上下文：累计症状、角色、最近一次辨证结果（供报告生成引用）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Session:
    id: str
    role: str = "patient"
    symptoms: list[str] = field(default_factory=list)
    last_result: Optional[dict[str, Any]] = None
    sources: list[dict[str, Any]] = field(default_factory=list)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: Optional[str], role: str = "patient") -> Session:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        sid = session_id or f"sess-{uuid.uuid4().hex[:12]}"
        sess = Session(id=sid, role=role)
        self._sessions[sid] = sess
        return sess

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)


session_store = SessionStore()
