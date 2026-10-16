"""会话隔离的本地临时附件存储。"""

from __future__ import annotations

import secrets
import shutil
from pathlib import Path

from app.models.consultation_v2 import Attachment, Consultation
from app.services.attachment_processor import (
    AttachmentValidationError,
    normalized_image,
    render_pdf,
    validate_declared_type,
)


class AttachmentStore:
    def __init__(
        self,
        root: Path,
        max_count: int = 5,
        max_bytes: int = 10 * 1024 * 1024,
        total_max_bytes: int = 30 * 1024 * 1024,
        pdf_max_pages: int = 8,
        pdf_dpi: int = 200,
        image_max_side: int = 4096,
    ) -> None:
        self.root = Path(root)
        self.max_count = max_count
        self.max_bytes = max_bytes
        self.total_max_bytes = total_max_bytes
        self.pdf_max_pages = pdf_max_pages
        self.pdf_dpi = pdf_dpi
        self.image_max_side = image_max_side
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _session_dir(self, consultation: Consultation) -> Path:
        path = self.root / consultation.id
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        return path

    def save(
        self, consultation: Consultation, filename: str, mime_type: str, data: bytes
    ) -> Attachment:
        if len(consultation.attachments) >= self.max_count:
            raise AttachmentValidationError(
                "TOO_MANY_ATTACHMENTS", f"最多上传 {self.max_count} 个附件"
            )
        if len(data) > self.max_bytes:
            raise AttachmentValidationError(
                "ATTACHMENT_TOO_LARGE", "单个附件不能超过 10MB"
            )
        current_total = sum(item.size for item in consultation.attachments)
        if current_total + len(data) > self.total_max_bytes:
            raise AttachmentValidationError(
                "ATTACHMENT_TOTAL_TOO_LARGE", "全部附件不能超过 30MB"
            )
        extension = validate_declared_type(filename, mime_type, data)
        attachment_id = f"att_{secrets.token_hex(8)}"
        attachment_dir = self._session_dir(consultation) / attachment_id
        attachment_dir.mkdir(mode=0o700)
        original = attachment_dir / f"original{extension}"
        original.write_bytes(data)
        original.chmod(0o600)
        try:
            if mime_type == "application/pdf":
                processed = render_pdf(
                    data,
                    attachment_dir,
                    self.pdf_max_pages,
                    self.pdf_dpi,
                    self.image_max_side,
                )
            else:
                processed_path = attachment_dir / "image.jpg"
                normalized_image(data, processed_path, self.image_max_side)
                processed = [processed_path]
            for path in processed:
                path.chmod(0o600)
        except AttachmentValidationError:
            shutil.rmtree(attachment_dir, ignore_errors=True)
            raise
        attachment = Attachment(
            id=attachment_id,
            filename=Path(filename).name,
            mime_type=mime_type,
            size=len(data),
            pages=len(processed),
            original_path=str(original),
            processed_paths=[str(path) for path in processed],
        )
        consultation.attachments.append(attachment)
        return attachment

    def delete(self, consultation: Consultation, attachment_id: str) -> bool:
        attachment = next(
            (item for item in consultation.attachments if item.id == attachment_id),
            None,
        )
        if not attachment:
            return False
        shutil.rmtree(Path(attachment.original_path).parent, ignore_errors=True)
        consultation.attachments = [
            item for item in consultation.attachments if item.id != attachment_id
        ]
        return True

    def delete_all(self, consultation: Consultation) -> None:
        directory = self.root / consultation.id
        shutil.rmtree(directory, ignore_errors=True)
        consultation.attachments = []

    def cleanup_orphans(self, active_ids: set[str]) -> None:
        for child in self.root.iterdir():
            if child.is_dir() and child.name not in active_ids:
                shutil.rmtree(child, ignore_errors=True)
