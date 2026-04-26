"""
document_service.py — In-memory text extraction for multiple file types.

Supported input formats:
  • PDF  (.pdf)  — PyMuPDF
  • DOCX (.docx) — python-docx
  • TXT  (.txt)  — utf-8 / latin-1 decode
"""
import re

from fastapi import HTTPException

from ..config import get_settings

settings = get_settings()

_MAX_TEXT_LENGTH = 40_000   # ~10k tokens


# ─── Public dispatcher ────────────────────────────────────────────────────────

def extract_text(file_bytes: bytes, filename: str, content_type: str) -> str:
    """
    Detect file type and extract clean plain text.
    Raises HTTPException on any validation or parse failure.
    """
    name_lower = filename.lower()

    if name_lower.endswith(".pdf") or content_type == "application/pdf":
        return _extract_pdf(file_bytes, filename)

    if name_lower.endswith(".docx") or content_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    ) and name_lower.endswith(".docx"):
        return _extract_docx(file_bytes, filename)

    if name_lower.endswith(".txt") or content_type in ("text/plain",):
        return _extract_txt(file_bytes, filename)

    # Fallback: try PDF magic bytes, then DOCX zip header, then treat as text
    if file_bytes[:4] == b"%PDF":
        return _extract_pdf(file_bytes, filename)
    if file_bytes[:2] == b"PK":          # ZIP — likely DOCX
        return _extract_docx(file_bytes, filename)

    raise HTTPException(
        status_code=415,
        detail={
            "code": "UNSUPPORTED_FORMAT",
            "message": "Only PDF, DOCX, and TXT files are supported.",
            "field": "resume",
        },
    )


# ─── PDF ─────────────────────────────────────────────────────────────────────

def _extract_pdf(data: bytes, filename: str) -> str:
    import fitz  # PyMuPDF

    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=415,
            detail={"code": "INVALID_FILE_TYPE", "message": "File does not appear to be a valid PDF.", "field": "resume"},
        )

    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            if doc.is_encrypted:
                raise HTTPException(status_code=400, detail={"code": "ENCRYPTED_PDF", "message": "Password-protected PDFs are not supported.", "field": "resume"})
            if doc.page_count == 0:
                raise HTTPException(status_code=400, detail={"code": "EMPTY_PDF", "message": "The PDF contains no pages.", "field": "resume"})
            if doc.page_count > settings.max_resume_pages:
                raise HTTPException(status_code=400, detail={"code": "TOO_MANY_PAGES", "message": f"Resume has {doc.page_count} pages; max is {settings.max_resume_pages}.", "field": "resume"})

            pages = [page.get_text("text") for page in doc]

        text = _clean("\n\n".join(pages))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"code": "PARSE_ERROR", "message": f"Failed to process PDF: {exc}", "field": "resume"})

    return _validate_and_trim(text, "PDF")


# ─── DOCX ─────────────────────────────────────────────────────────────────────

def _extract_docx(data: bytes, filename: str) -> str:
    import io
    try:
        from docx import Document
    except ImportError:
        raise HTTPException(status_code=500, detail={"code": "MISSING_DEP", "message": "python-docx not installed."})

    try:
        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # Also grab text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text.strip())
        text = _clean("\n\n".join(paragraphs))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail={"code": "PARSE_ERROR", "message": f"Failed to process DOCX: {exc}", "field": "resume"})

    return _validate_and_trim(text, "DOCX")


# ─── TXT ─────────────────────────────────────────────────────────────────────

def _extract_txt(data: bytes, filename: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = data.decode(enc)
            return _validate_and_trim(_clean(text), "TXT")
        except (UnicodeDecodeError, ValueError):
            continue
    raise HTTPException(
        status_code=422,
        detail={"code": "DECODE_ERROR", "message": "Could not decode the text file. Please save it as UTF-8.", "field": "resume"},
    )


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _validate_and_trim(text: str, fmt: str) -> str:
    if len(text.strip()) < 100:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "EMPTY_CONTENT",
                "message": f"No readable text found in {fmt}. The file may be empty or image-only.",
                "field": "resume",
            },
        )
    return text[:_MAX_TEXT_LENGTH]
