"""附件真实类型校验、图片规范化与 PDF 栅格化。"""

from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image, ImageOps, UnidentifiedImageError


ALLOWED_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


class AttachmentValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_declared_type(filename: str, mime_type: str, data: bytes) -> str:
    extension = Path(filename).suffix.lower()
    expected_mime = ALLOWED_TYPES.get(extension)
    if not expected_mime or mime_type != expected_mime:
        raise AttachmentValidationError(
            "UNSUPPORTED_ATTACHMENT_TYPE", "仅支持 JPEG、PNG、WebP 和 PDF"
        )
    if not data:
        raise AttachmentValidationError("INVALID_ATTACHMENT", "附件不能为空")
    signatures = {
        "image/jpeg": data.startswith(b"\xff\xd8\xff"),
        "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": len(data) >= 12
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP",
        "application/pdf": data.startswith(b"%PDF-"),
    }
    if not signatures[mime_type]:
        raise AttachmentValidationError(
            "INVALID_ATTACHMENT", "附件扩展名、MIME 与真实内容不一致"
        )
    return extension


def normalized_image(
    data: bytes, destination: Path, max_side: int = 4096
) -> None:
    try:
        source = Image.open(io.BytesIO(data))
        source.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AttachmentValidationError("INVALID_ATTACHMENT", "图片无法解码") from exc
    source = ImageOps.exif_transpose(source)
    if source.mode in {"RGBA", "LA"} or "transparency" in source.info:
        rgba = source.convert("RGBA")
        white = Image.new("RGBA", rgba.size, "white")
        source = Image.alpha_composite(white, rgba).convert("RGB")
    elif source.mode != "RGB":
        source = source.convert("RGB")
    source.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    source.save(destination, "JPEG", quality=90, optimize=True)


def render_pdf(
    data: bytes,
    destination_dir: Path,
    pdf_max_pages: int = 8,
    dpi: int = 200,
    max_side: int = 4096,
) -> list[Path]:
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except (fitz.FileDataError, RuntimeError, ValueError) as exc:
        raise AttachmentValidationError("INVALID_ATTACHMENT", "PDF 无法解码") from exc
    pages = document.page_count
    if pages < 1:
        document.close()
        raise AttachmentValidationError("INVALID_ATTACHMENT", "PDF 不能为空")
    if pages > pdf_max_pages:
        document.close()
        raise AttachmentValidationError(
            "PDF_TOO_MANY_PAGES", f"PDF 不能超过 {pdf_max_pages} 页"
        )
    output: list[Path] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    for page_number in range(pages):
        pixmap = document.load_page(page_number).get_pixmap(matrix=matrix, alpha=False)
        raw = pixmap.tobytes("jpeg", jpg_quality=90)
        path = destination_dir / f"page-{page_number + 1:02d}.jpg"
        normalized_image(raw, path, max_side)
        output.append(path)
    document.close()
    return output

