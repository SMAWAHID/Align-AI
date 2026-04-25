"""
ATS Resume Builder + Enhancer + Format Converter.

Functions:
  build_ats_resume()   — initial ATS resume from raw resume + JD
  enhance_resume()     — incorporate selected skills/improvements into existing resume
  convert_resume()     — convert Markdown resume to txt / md / pdf / docx bytes
"""
import asyncio
import io
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException

from ..config import get_settings
from .ai_service import _PROVIDER, generate_text

logger   = logging.getLogger(__name__)
settings = get_settings()
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
        raise HTTPException(status_code=503, detail={"code": "RESUME_BUILD_ERROR", "message": str(exc)})


# ─── Enhance existing resume with selected skills / improvements ──────────────

async def enhance_resume(
    current_resume: str,
    selected_skills: list[str],
    selected_improvements: list[str],
    job_description: str,
) -> str:
    """
    Takes the existing ATS resume and naturally weaves in:
      - selected missing skills (added to Technical Skills + woven into bullets)
      - selected improvements (applied to relevant sections)
    Returns enhanced Markdown.
    """
    if not selected_skills and not selected_improvements:
        return current_resume

    prompt = _build_enhance_prompt(current_resume, selected_skills, selected_improvements, job_description)
    try:
        result = await generate_text(prompt, max_tokens=4096)
        return _clean_md(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("enhance_resume failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail={"code": "ENHANCE_ERROR", "message": str(exc)})


# ─── Format conversion ────────────────────────────────────────────────────────

def convert_resume(markdown: str, fmt: str) -> tuple[bytes, str, str]:
    """
    Convert Markdown to the requested format.
    Returns (bytes, media_type, file_extension).
    """
    fmt = fmt.lower()
    if fmt == "md":
        return markdown.encode("utf-8"), "text/markdown", ".md"
    if fmt == "txt":
        return _md_to_txt(markdown).encode("utf-8"), "text/plain", ".txt"
    if fmt == "pdf":
        return _md_to_pdf(markdown), "application/pdf", ".pdf"
    if fmt in ("docx", "word"):
        return _md_to_docx(markdown), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"
    raise ValueError(f"Unsupported format: {fmt}")


# ─── Private: Prompts ─────────────────────────────────────────────────────────

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
3. Use strong action verbs (Architected, Spearheaded, Delivered, Optimised, etc.).
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
    skills_str = "\n".join(f"  - {s}" for s in selected_skills) if selected_skills else "  (none selected)"
    improv_str = "\n".join(f"  - {i}" for i in selected_improvements) if selected_improvements else "  (none selected)"
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
2. Add the selected skills naturally:
   - Add them to the Technical Skills section under the correct sub-category.
   - If the candidate plausibly has experience implied by existing roles, weave them into bullets.
   - If there is NO plausible basis, list them in a "Familiar With" or "Exposure to" sub-section — never claim proficiency.
3. Apply each improvement to the relevant resume section.
4. Keep the same Markdown structure. Do NOT restructure sections not being changed.
5. Return ONLY clean Markdown — no preamble, no fences, no commentary."""


# ─── Private: Converters ──────────────────────────────────────────────────────

def _md_to_txt(md: str) -> str:
    """Strip Markdown syntax, return plain text."""
    text = re.sub(r"^#{1,6}\s+", "", md, flags=re.MULTILINE)   # headings
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)               # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)                   # italic
    text = re.sub(r"`(.+?)`", r"\1", text)                     # inline code
    text = re.sub(r"^[-*+]\s+", "• ", text, flags=re.MULTILINE)# bullets
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)            # links
    text = re.sub(r"^---+$", "─" * 50, text, flags=re.MULTILINE)
    return text.strip()


def _md_to_pdf(md: str) -> bytes:
    """Convert Markdown to PDF using fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail={"code": "MISSING_DEP", "message": "fpdf2 not installed. Run: pip install fpdf2"},
        )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    for line in md.split("\n"):
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue

        if stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(15, 15, 15)
            pdf.multi_cell(0, 9, stripped[2:].strip())
            pdf.ln(2)
        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(50, 50, 200)
            pdf.multi_cell(0, 7, stripped[3:].strip())
            pdf.set_draw_color(50, 50, 200)
            pdf.set_line_width(0.3)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 170, pdf.get_y())
            pdf.ln(3)
        elif stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(0, 6, stripped[4:].strip())
        elif stripped.startswith(("- ", "• ")):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(50, 50, 50)
            content = stripped[2:]
            # strip bold markdown
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)
            pdf.multi_cell(0, 5, f"  \u2022  {content}")
        elif stripped.startswith("---"):
            pdf.set_draw_color(200, 200, 200)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(2)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(60, 60, 60)
            # handle **bold** inline
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            pdf.multi_cell(0, 5, content)

    return bytes(pdf.output())


def _md_to_docx(md: str) -> bytes:
    """Convert Markdown to DOCX using python-docx."""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail={"code": "MISSING_DEP", "message": "python-docx not installed. Run: pip install python-docx"},
        )

    doc = Document()

    # Page margins
    from docx.shared import Inches
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
            p.runs[0].font.size = Pt(18)
        elif stripped.startswith("## "):
            p = doc.add_heading(stripped[3:].strip(), level=2)
            for run in p.runs:
                run.font.color.rgb = RGBColor(0x23, 0x23, 0xC8)
                run.font.size = Pt(13)
        elif stripped.startswith("### "):
            p = doc.add_heading(stripped[4:].strip(), level=3)
            for run in p.runs:
                run.font.size = Pt(11)
        elif stripped.startswith(("- ", "• ")):
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped[2:])
            doc.add_paragraph(content, style="List Bullet")
        elif stripped.startswith("---"):
            doc.add_paragraph("─" * 60)
        else:
            p = doc.add_paragraph()
            # Handle **bold** inline
            parts = re.split(r"(\*\*.+?\*\*)", stripped)
            for part in parts:
                if part.startswith("**") and part.endswith("**"):
                    run = p.add_run(part[2:-2])
                    run.bold = True
                else:
                    p.add_run(part)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _clean_md(text: str) -> str:
    text = re.sub(r"^```(?:markdown)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text.strip(), flags=re.IGNORECASE)
    return text.strip()
