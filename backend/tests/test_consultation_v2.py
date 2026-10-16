from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image

from app.models.consultation_v2 import ConsultationRole, ConsultationStatus
from app.services.attachment_processor import AttachmentValidationError
from app.services.attachment_store import AttachmentStore
from app.services.consultation_store import ConsultationStore
from app.services.task_store import TaskStore


def image_bytes(fmt: str = "PNG", mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (16, 12), (255, 0, 0, 100) if mode == "RGBA" else "red").save(
        buffer, format=fmt
    )
    return buffer.getvalue()


def pdf_bytes(pages: int) -> bytes:
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    data = document.tobytes()
    document.close()
    return data


def test_token_is_random_and_must_match() -> None:
    store = ConsultationStore(ttl_seconds=1800)
    first, token = store.create(ConsultationRole.PATIENT)
    second, other_token = store.create(ConsultationRole.PATIENT)

    assert first.id != second.id
    assert token != other_token
    assert len(token) >= 32
    assert store.authenticate(first.id, token).id == first.id
    assert store.authenticate(first.id, other_token) is None


def test_idempotency_returns_same_task() -> None:
    store = TaskStore(ttl_seconds=1800)
    first = store.create("con_1", "prepare", "same-key")
    second = store.create("con_1", "prepare", "same-key")

    assert first.id == second.id
    assert len(store.all()) == 1


def test_image_signature_mime_and_extension_must_match(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    consultation = ConsultationStore().create(ConsultationRole.PATIENT)[0]

    try:
        store.save(consultation, "fake.png", "image/png", b"%PDF-1.7")
    except AttachmentValidationError as exc:
        assert exc.code == "INVALID_ATTACHMENT"
    else:
        raise AssertionError("伪造图片必须被拒绝")


def test_transparent_png_is_converted_to_rgb(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    consultation = ConsultationStore().create(ConsultationRole.PATIENT)[0]
    attachment = store.save(
        consultation, "alpha.png", "image/png", image_bytes(mode="RGBA")
    )

    with Image.open(attachment.processed_paths[0]) as processed:
        assert processed.mode == "RGB"
        assert processed.format == "JPEG"


def test_exif_orientation_is_applied(tmp_path: Path) -> None:
    buffer = io.BytesIO()
    source = Image.new("RGB", (10, 20), "white")
    exif = source.getexif()
    exif[274] = 6
    source.save(buffer, "JPEG", exif=exif)
    store = AttachmentStore(tmp_path)
    consultation = ConsultationStore().create(ConsultationRole.PATIENT)[0]
    attachment = store.save(
        consultation, "rotated.jpg", "image/jpeg", buffer.getvalue()
    )

    with Image.open(attachment.processed_paths[0]) as processed:
        assert processed.size == (20, 10)


def test_count_single_and_total_limits(tmp_path: Path) -> None:
    content = image_bytes("JPEG")
    consultation = ConsultationStore().create(ConsultationRole.PATIENT)[0]
    count_store = AttachmentStore(tmp_path / "count", max_count=1)
    count_store.save(consultation, "one.jpg", "image/jpeg", content)
    try:
        count_store.save(consultation, "two.jpg", "image/jpeg", content)
    except AttachmentValidationError as exc:
        assert exc.code == "TOO_MANY_ATTACHMENTS"
    else:
        raise AssertionError("附件数量超限必须失败")

    single = AttachmentStore(tmp_path / "single", max_bytes=len(content) - 1)
    other = ConsultationStore().create(ConsultationRole.PATIENT)[0]
    try:
        single.save(other, "large.jpg", "image/jpeg", content)
    except AttachmentValidationError as exc:
        assert exc.code == "ATTACHMENT_TOO_LARGE"
    else:
        raise AssertionError("单附件大小超限必须失败")

    total = AttachmentStore(
        tmp_path / "total", max_count=5, total_max_bytes=len(content) + 1
    )
    third = ConsultationStore().create(ConsultationRole.PATIENT)[0]
    total.save(third, "first.jpg", "image/jpeg", content)
    try:
        total.save(third, "second.jpg", "image/jpeg", content)
    except AttachmentValidationError as exc:
        assert exc.code == "ATTACHMENT_TOTAL_TOO_LARGE"
    else:
        raise AssertionError("附件总大小超限必须失败")


def test_pdf_page_limit(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path, pdf_max_pages=8)
    consultation = ConsultationStore().create(ConsultationRole.PATIENT)[0]
    accepted = store.save(
        consultation, "report.pdf", "application/pdf", pdf_bytes(8)
    )
    assert accepted.pages == 8

    try:
        store.save(consultation, "long.pdf", "application/pdf", pdf_bytes(9))
    except AttachmentValidationError as exc:
        assert exc.code == "PDF_TOO_MANY_PAGES"
    else:
        raise AssertionError("超过 8 页的 PDF 必须被拒绝")


def test_attachment_success_cleanup(tmp_path: Path) -> None:
    store = AttachmentStore(tmp_path)
    consultation = ConsultationStore().create(ConsultationRole.PATIENT)[0]
    attachment = store.save(
        consultation, "photo.jpg", "image/jpeg", image_bytes("JPEG")
    )
    assert Path(attachment.original_path).exists()

    store.delete_all(consultation)

    assert consultation.attachments == []
    assert not Path(attachment.original_path).exists()
    assert consultation.status == ConsultationStatus.DRAFT
