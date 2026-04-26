"""
ATS Resume Builder + Enhancer + Format Converter.

Output formats:
  • md   — raw Markdown (no conversion needed)
  • txt  — strip Markdown syntax
  • pdf  — ReportLab Platypus (proper Unicode, paragraph flow)
  • docx — python-docx
"""
import asyncio
import io
import logging
import re
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

    result = await generate_text(prompt, max_tokens=4096)

    # 🔥 FORCE CLEAN OUTPUT TYPE
    result = _clean_md(result)

    # ❗ If AI returns JSON, convert it to markdown fallback
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            result = _json_to_markdown(parsed)
    except Exception:
        pass  # it's already markdown

    return result


# ─── Enhance existing resume ──────────────────────────────────────────────────

async def enhance_resume(
    current_resume: str,
    selected_skills: list[str],
    selected_improvements: list[str],
    job_description: str,
) -> str:
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
2. Add selected skills naturally into the Technical Skills section.
   If no plausible basis exists, add under "Familiar With" — never claim proficiency.
3. Apply each improvement to the relevant resume section.
4. Keep the same Markdown structure.
5. Return ONLY clean Markdown — no preamble, no fences, no commentary."""


# ─── TXT ─────────────────────────────────────────────────────────────────────

def _md_to_txt(md: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", md, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",   r"\1", text)
    text = re.sub(r"^[-*+]\s+",   "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    text = re.sub(r"^---+$", "-" * 50, text, flags=re.MULTILINE)
    return text.strip()


# ─── PDF via ReportLab Platypus ───────────────────────────────────────────────

def _md_to_pdf(md: str) -> bytes:
    """
    Converts Markdown resume to a professionally formatted PDF using
    ReportLab Platypus. Handles full Unicode, proper line wrapping,
    coloured section headers, and bullet indentation correctly.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable, ListFlowable, ListItem,
            Paragraph, SimpleDocTemplate, Spacer,
        )
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail={"code": "MISSING_DEP", "message": "reportlab not installed. Run: pip install reportlab"},
        )

    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    # ── Styles ────────────────────────────────────────────────────────────────
    ACCENT   = colors.HexColor("#2828B4")
    DARK     = colors.HexColor("#111111")
    BODY     = colors.HexColor("#333333")
    MUTED    = colors.HexColor("#555555")

    h1_style = ParagraphStyle(
        "H1", fontName="Helvetica-Bold", fontSize=20,
        textColor=DARK, spaceAfter=2 * mm, alignment=TA_LEFT,
    )
    h2_style = ParagraphStyle(
        "H2", fontName="Helvetica-Bold", fontSize=13,
        textColor=ACCENT, spaceBefore=5 * mm, spaceAfter=1 * mm,
    )
    h3_style = ParagraphStyle(
        "H3", fontName="Helvetica-Bold", fontSize=11,
        textColor=DARK, spaceBefore=3 * mm, spaceAfter=1 * mm,
    )
    body_style = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=10,
        textColor=BODY, leading=14, spaceAfter=1 * mm,
    )
    bullet_style = ParagraphStyle(
        "Bullet", fontName="Helvetica", fontSize=10,
        textColor=BODY, leading=14,
        leftIndent=10 * mm, firstLineIndent=-4 * mm,
        spaceAfter=0.8 * mm,
    )
    contact_style = ParagraphStyle(
        "Contact", fontName="Helvetica", fontSize=9,
        textColor=MUTED, spaceAfter=4 * mm,
    )

    # ── Parse Markdown lines → Flowables ─────────────────────────────────────
    story: list = []
    lines = md.split("\n")
    i = 0

    def escape(text: str) -> str:
        """Escape ReportLab XML special chars."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def inline(text: str) -> str:
        """Convert **bold** to <b>bold</b> for ReportLab paragraphs."""
        text = escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*",     r"<i>\1</i>", text)
        # Convert markdown links [label](url) → label (no hyperlinks in basic PDF)
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
        return text

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 2 * mm))
            i += 1
            continue

        # H1
        if stripped.startswith("# "):
            story.append(Paragraph(escape(stripped[2:].strip()), h1_style))
            i += 1
            # Next non-empty line after H1 is usually the contact line
            if i < len(lines) and lines[i].strip():
                story.append(Paragraph(inline(lines[i].strip()), contact_style))
                i += 1
            continue

        # H2
        if stripped.startswith("## "):
            story.append(Paragraph(escape(stripped[3:].strip()), h2_style))
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=ACCENT, spaceAfter=2 * mm,
            ))
            i += 1
            continue

        # H3
        if stripped.startswith("### "):
            story.append(Paragraph(escape(stripped[4:].strip()), h3_style))
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$", stripped):
            story.append(HRFlowable(width="100%", thickness=0.3, color=colors.lightgrey, spaceAfter=2 * mm))
            i += 1
            continue

        # Bullet list — collect consecutive bullets
        if stripped.startswith(("- ", "* ", "+ ")):
            bullets = []
            while i < len(lines) and lines[i].strip().startswith(("- ", "* ", "+ ")):
                content = re.sub(r"^[-*+]\s+", "", lines[i].strip())
                bullets.append(
                    ListItem(
                        Paragraph(inline(content), bullet_style),
                        bulletColor=ACCENT,
                        leftIndent=8 * mm,
                        bulletFontSize=10,
                    )
                )
                i += 1
            story.append(
                ListFlowable(
                    bullets,
                    bulletType="bullet",
                    bulletChar="\u2022",
                    leftIndent=6 * mm,
                    spaceAfter=1 * mm,
                )
            )
            continue

        # Normal paragraph
        story.append(Paragraph(inline(stripped), body_style))
        i += 1

    doc.build(story)
    return buf.getvalue()


# ─── DOCX ─────────────────────────────────────────────────────────────────────

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

def _json_to_markdown(data: dict) -> str:
    resume = data.get("resume", data)

    return f"""
# {resume.get("Full Name", "")}

## Professional Summary
{resume.get("Professional Summary", "")}

## Technical Skills
{resume.get("Technical Skills", "")}

## Projects
{resume.get("Projects", "")}
""".strip()
