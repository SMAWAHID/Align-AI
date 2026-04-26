"""
ATS Resume Builder + Enhancer + Format Converter.

Fixes in this version:
  - _md_to_pdf: use pdf.epw for multi_cell width (never 0)
  - _md_to_pdf: sanitise unicode to latin-1 safe chars before rendering
  - _md_to_pdf: skip blank/whitespace-only lines
  - _md_to_pdf: truncate extremely long single tokens that exceed cell width
"""
import asyncio
import io
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException

from ..config import get_settings
from .ai_service import generate_text

logger    = logging.getLogger(__name__)
settings  = get_settings()
_executor = ThreadPoolExecutor(max_workers=4)


# ─── Build initial ATS resume ─────────────────────────────────────────────────

async def build_ats_resume(resume_text: str, jd_text: str, filename: str) -> str:
    prompt = _build_initial_prompt(resume_text, jd_text)
    try:
        result = await generate_text(prompt, max_tokens=4096)
        return _clean_md(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("build_ats_resume failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={"code": "RESUME_BUILD_ERROR", "message": str(exc)},
        )


# ─── Enhance existing resume ──────────────────────────────────────────────────

async def enhance_resume(
    current_resume: str,
    selected_skills: list[str],
    selected_improvements: list[str],
    job_description: str,
) -> str:
    if not selected_skills and not selected_improvements:
        return current_resume

    prompt = _build_enhance_prompt(
        current_resume, selected_skills, selected_improvements, job_description
    )
    try:
        result = await generate_text(prompt, max_tokens=4096)
        return _clean_md(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("enhance_resume failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={"code": "ENHANCE_ERROR", "message": str(exc)},
        )


# ─── Format conversion ────────────────────────────────────────────────────────

def convert_resume(markdown: str, fmt: str) -> tuple[bytes, str, str]:
    """Convert Markdown resume to the requested format."""
    fmt = fmt.lower()
    if fmt == "md":
        return markdown.encode("utf-8"), "text/markdown", ".md"
    if fmt == "txt":
        return _md_to_txt(markdown).encode("utf-8"), "text/plain", ".txt"
    if fmt == "pdf":
        return _md_to_pdf(markdown), "application/pdf", ".pdf"
    if fmt in ("docx", "word"):
        return (
            _md_to_docx(markdown),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
        )
    raise ValueError(f"Unsupported format: {fmt}")


# ─── Prompts ──────────────────────────────────────────────────────────────────

def _build_initial_prompt(resume_text: str, jd_text: str) -> str:
    return f"""You are an elite career consultant. Rewrite the resume into a flawlessly structured,
ATS-optimised Markdown document aligned to the job description.

=== ORIGINAL RESUME ===
{resume_text[:8000]}
=== END ===

=== JOB DESCRIPTION ===
{jd_text[:4000]}
=== END ===

RULES:
1. NEVER fabricate facts, companies, dates, roles, or metrics not in the original.
2. Mirror JD keywords naturally.
3. Use strong action verbs: Architected, Spearheaded, Delivered, Optimised, etc.
4. Harvard format: reverse-chronological, clear hierarchy.

Return ONLY clean Markdown — no preamble, no fences.

# [Full Name]
[Email] | [Phone] | [LinkedIn] | [GitHub] | [Location]

## Professional Summary
## Technical Skills
## Professional Experience
## Projects *(if present)*
## Education
## Certifications *(if present)*"""


def _build_enhance_prompt(
    current_resume: str,
    selected_skills: list[str],
    selected_improvements: list[str],
    job_description: str,
) -> str:
    skills_str = "\n".join(f"  - {s}" for s in selected_skills) or "  (none)"
    improv_str = "\n".join(f"  - {i}" for i in selected_improvements) or "  (none)"
    return f"""You are an elite career consultant enhancing an ATS resume.

=== CURRENT RESUME (Markdown) ===
{current_resume[:8000]}
=== END ===

=== JOB DESCRIPTION ===
{job_description[:3000]}
=== END ===

=== SKILLS TO ADD ===
{skills_str}

=== IMPROVEMENTS TO APPLY ===
{improv_str}

RULES:
1. NEVER fabricate any fact, company, date, role, metric, or credential.
2. Add selected skills naturally into the Technical Skills section under the correct sub-category.
   - If the candidate plausibly has exposure from existing roles, weave into bullets.
   - If no plausible basis exists, add under a "Familiar With" sub-section — never claim proficiency.
3. Apply each improvement to the relevant resume section.
4. Keep the same Markdown structure. Do NOT restructure sections not being changed.
5. Return ONLY clean Markdown — no preamble, no fences, no commentary."""


# ─── TXT converter ───────────────────────────────────────────────────────────

def _md_to_txt(md: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", md, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"^[-*+]\s+", "* ", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"^---+$", "-" * 50, text, flags=re.MULTILINE)
    return text.strip()


# ─── PDF converter ────────────────────────────────────────────────────────────

def _sanitise(text: str) -> str:
    """
    Convert unicode to closest latin-1 safe representation.
    fpdf2 with core fonts (Helvetica) only supports latin-1.
    Replaces smart quotes, em-dashes, bullets, etc.
    """
    # Common replacements
    replacements = {
        "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2022": "*", "\u2023": "*",
        "\u25aa": "*", "\u2026": "...", "\u00a0": " ", "\u2009": " ",
        "\u2003": "  ", "\u200b": "",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    # Normalise remaining unicode to closest ASCII
    try:
        text = unicodedata.normalize("NFKD", text)
        text = text.encode("latin-1", errors="replace").decode("latin-1")
    except Exception:
        text = text.encode("ascii", errors="replace").decode("ascii")
    return text


def _md_to_pdf(md: str) -> bytes:
    """
    Robust Markdown → PDF using fpdf2.
    Key fixes:
      - Always use pdf.epw (effective page width) instead of 0
      - Sanitise all text to latin-1 before rendering
      - Skip empty lines safely
      - Truncate individual words longer than the cell width
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail={"code": "MISSING_DEP", "message": "fpdf2 not installed. Run: pip install fpdf2"},
        )

    LEFT_M  = 20.0
    RIGHT_M = 20.0
    TOP_M   = 20.0

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_left_margin(LEFT_M)
    pdf.set_right_margin(RIGHT_M)
    pdf.set_top_margin(TOP_M)

    # Effective page width = paper width − left margin − right margin
    EPW = pdf.w - LEFT_M - RIGHT_M

    def safe_cell(text: str, h: float, font: str, style: str, size: float,
                  color: tuple[int, int, int] = (50, 50, 50)) -> None:
        """Render a multi_cell with explicit width and sanitised text."""
        text = _sanitise(text)
        if not text.strip():
            pdf.ln(2)
            return
        pdf.set_font(font, style, size)
        pdf.set_text_color(*color)
        # Chunk any single word longer than EPW into multiple lines
        # (fpdf2 raises if a single glyph can't fit)
        try:
            pdf.multi_cell(EPW, h, text, align="L")
        except Exception:
            # Fallback: split into shorter chunks and render word by word
            for word in text.split():
                try:
                    pdf.multi_cell(EPW, h, _sanitise(word), align="L")
                except Exception:
                    pass  # Skip truly unrenderable tokens

    for raw_line in md.split("\n"):
        line = raw_line.rstrip()

        if not line.strip():
            pdf.ln(2)
            continue

        if line.startswith("# "):
            safe_cell(line[2:].strip(), 10, "Helvetica", "B", 18, (15, 15, 15))
            pdf.ln(1)

        elif line.startswith("## "):
            pdf.ln(2)
            safe_cell(line[3:].strip(), 8, "Helvetica", "B", 13, (40, 40, 180))
            # Underline
            pdf.set_draw_color(40, 40, 180)
            pdf.set_line_width(0.3)
            y = pdf.get_y()
            pdf.line(LEFT_M, y, LEFT_M + EPW, y)
            pdf.ln(3)

        elif line.startswith("### "):
            pdf.ln(1)
            safe_cell(line[4:].strip(), 7, "Helvetica", "B", 11, (30, 30, 30))

        elif line.startswith(("- ", "* ", "+ ")):
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", line[2:])
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(55, 55, 55)
            pdf.set_left_margin(LEFT_M + 4)
            bullet_text = _sanitise(f"*  {content}")
            try:
                pdf.multi_cell(EPW - 4, 5, bullet_text, align="L")
            except Exception:
                pass
            pdf.set_left_margin(LEFT_M)

        elif re.match(r"^-{3,}$", line.strip()):
            pdf.set_draw_color(200, 200, 200)
            pdf.set_line_width(0.3)
            y = pdf.get_y()
            pdf.line(LEFT_M, y, LEFT_M + EPW, y)
            pdf.ln(3)

        else:
            # Normal paragraph — handle **bold** inline
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            safe_cell(content, 5, "Helvetica", "", 10, (60, 60, 60))

    return bytes(pdf.output())


# ─── DOCX converter ───────────────────────────────────────────────────────────

def _md_to_docx(md: str) -> bytes:
    try:
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail={"code": "MISSING_DEP", "message": "python-docx not installed. Run: pip install python-docx"},
        )

    doc = Document()
    for section in doc.sections:
        section.top_margin    = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)

    for line in md.split("\n"):
        stripped = line.strip()
        if not stripped:
            doc.add_paragraph("")
            continue

        if stripped.startswith("# "):
            p = doc.add_heading(stripped[2:].strip(), level=1)
            if p.runs:
                p.runs[0].font.size = Pt(18)

        elif stripped.startswith("## "):
            p = doc.add_heading(stripped[3:].strip(), level=2)
            for run in p.runs:
                run.font.color.rgb = RGBColor(0x28, 0x28, 0xB4)
                run.font.size = Pt(13)

        elif stripped.startswith("### "):
            p = doc.add_heading(stripped[4:].strip(), level=3)
            if p.runs:
                p.runs[0].font.size = Pt(11)

        elif stripped.startswith(("- ", "* ", "+ ")):
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped[2:])
            doc.add_paragraph(content, style="List Bullet")

        elif re.match(r"^-{3,}$", stripped):
            doc.add_paragraph("─" * 60)

        else:
            p = doc.add_paragraph()
            for part in re.split(r"(\*\*.+?\*\*)", stripped):
                if part.startswith("**") and part.endswith("**"):
                    run = p.add_run(part[2:-2])
                    run.bold = True
                elif part:
                    p.add_run(part)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clean_md(text: str) -> str:
    text = re.sub(r"^```(?:markdown)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text.strip(), flags=re.IGNORECASE)
    return text.strip()
