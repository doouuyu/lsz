"""V2 匿名会话的进程内存储。"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta
from threading import RLock
from typing import Optional

from app.models.consultation_v2 import (
    Consultation,
    ConsultationRole,
    ConsultationStatus,
    utc_now,
)


class ConsultationStore:
    def __init__(self, ttl_seconds: int = 1800) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, Consultation] = {}
        self._lock = RLock()

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(self, role: ConsultationRole) -> tuple[Consultation, str]:
        token = secrets.token_urlsafe(32)
        now = utc_now()
        consultation = Consultation(
            id=f"con_{secrets.token_hex(8)}",
            token_hash=self._hash_token(token),
            role=role,
            created_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )
        with self._lock:
            self._items[consultation.id] = consultation
        return consultation, token

    def get(self, consultation_id: str) -> Optional[Consultation]:
        with self._lock:
            consultation = self._items.get(consultation_id)
            if consultation and consultation.expires_at <= utc_now():
                consultation.status = ConsultationStatus.EXPIRED
            return consultation

    def authenticate(self, consultation_id: str, token: str) -> Optional[Consultation]:
        consultation = self.get(consultation_id)
        if not consultation or consultation.status == ConsultationStatus.EXPIRED:
            return None
        supplied = self._hash_token(token or "")
        if not hmac.compare_digest(consultation.token_hash, supplied):
            return None
        return consultation

    def remove(self, consultation_id: str) -> Optional[Consultation]:
        with self._lock:
            return self._items.pop(consultation_id, None)

    def touch(self, consultation: Consultation) -> None:
        with self._lock:
            consultation.expires_at = utc_now() + timedelta(seconds=self.ttl_seconds)

    def expired(self) -> list[Consultation]:
        now = utc_now()
        with self._lock:
            return [item for item in self._items.values() if item.expires_at <= now]

    def all(self) -> list[Consultation]:
        with self._lock:
            return list(self._items.values())
