"""
PDF processing service — all operations are in-memory (no disk I/O).
Uses PyMuPDF (fitz) for high-performance PDF text extraction.
"""
import re

import fitz  # PyMuPDF
from fastapi import HTTPException

from ..config import get_settings

settings = get_settings()

# Hard cap to avoid token overflow in downstream Gemini API calls
_MAX_TEXT_LENGTH = 40_000  # ~10k tokens


def extract_text_from_bytes(pdf_bytes: bytes, filename: str = "file.pdf") -> str:
    """
    Extract and clean text from raw PDF bytes without any disk I/O.

    Raises HTTPException with appropriate status codes so FastAPI can
    return structured error responses directly to the client.
    """
    _validate_magic_bytes(pdf_bytes)

    try:
        # open() with stream= keeps everything in-memory
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            _validate_document(doc, filename)
            raw_pages = [page.get_text("text") for page in doc]

        full_text = "\n\n".join(raw_pages)
        cleaned = _clean_text(full_text)

        if len(cleaned.strip()) < 100:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "EMPTY_CONTENT",
                    "message": "No readable text found. The PDF may be scanned/image-only.",
                    "field": "resume",
                },
            )

        return cleaned[:_MAX_TEXT_LENGTH]

    except HTTPException:
        raise
    except fitz.FileDataError:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CORRUPT_PDF",
                "message": "The PDF file appears to be corrupted.",
                "field": "resume",
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PARSE_ERROR",
                "message": f"Failed to process PDF: {exc}",
                "field": "resume",
            },
        )


# ─── Private helpers ─────────────────────────────────────────────────────────

def _validate_magic_bytes(data: bytes) -> None:
    """Reject files that aren't PDFs by checking magic bytes."""
    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=415,
            detail={
                "code": "INVALID_FILE_TYPE",
                "message": "Uploaded file is not a valid PDF (missing %PDF header).",
                "field": "resume",
            },
        )


def _validate_document(doc: fitz.Document, filename: str) -> None:
    if doc.is_encrypted:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ENCRYPTED_PDF",
                "message": "Password-protected PDFs are not supported.",
                "field": "resume",
            },
        )
    if doc.page_count == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "EMPTY_PDF",
                "message": "The PDF contains no pages.",
                "field": "resume",
            },
        )
    if doc.page_count > settings.max_resume_pages:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TOO_MANY_PAGES",
                "message": (
                    f"Resume has {doc.page_count} pages; "
                    f"maximum allowed is {settings.max_resume_pages}."
                ),
                "field": "resume",
            },
        )


def _clean_text(text: str) -> str:
    """
    Normalise whitespace and strip non-ASCII artifacts from extracted text.
    Preserves paragraph structure for better embedding quality.
    """
    # Collapse 3+ blank lines → 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse horizontal whitespace runs
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Strip control characters except newlines/tabs
    text = re.sub(r"[^\x09\x0A\x20-\x7E]", " ", text)
    return text.strip()
