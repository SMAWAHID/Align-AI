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
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException

from ..config import get_settings
from .ai_service import generate_text

logger    = logging.getLogger(__name__)
settings  = get_settings()
# Used for running blocking PDF/DOCX generation off the async event loop
_executor = ThreadPoolExecutor(max_workers=4)


# ─── Build initial ATS resume ─────────────────────────────────────────────────

async def build_ats_resume(resume_text: str, jd_text: str, filename: str) -> str:
    prompt = _build_initial_prompt(resume_text, jd_text)
    result = await generate_text(prompt, max_tokens=4096)
    result = _clean_md(result)

    # If AI returns JSON despite instructions, convert it to markdown
    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            result = _json_to_markdown(parsed)
    except Exception:
        pass  # already markdown

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
    prompt = _build_enhance_prompt(
        current_resume, selected_skills, selected_improvements, job_description
    )
    try:
        result = await generate_text(prompt, max_tokens=4096)
        result = _clean_md(result)

        # If AI returns JSON despite instructions, convert it to markdown
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                result = _json_to_markdown(parsed)
        except Exception:
            pass  # already markdown

        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("enhance_resume failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={"code": "ENHANCE_ERROR", "message": str(exc)},
        )


# ─── Format conversion ────────────────────────────────────────────────────────

async def convert_resume_async(markdown: str, fmt: str) -> tuple[bytes, str, str]:
    """
    Async wrapper so blocking PDF/DOCX generation doesn't stall the event loop.
    """
    fmt = fmt.lower()
    if fmt == "md":
        return markdown.encode("utf-8"), "text/markdown", ".md"
    if fmt == "txt":
        return _md_to_txt(markdown).encode("utf-8"), "text/plain", ".txt"
    if fmt == "pdf":
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, _md_to_pdf, markdown)
        return data, "application/pdf", ".pdf"
    if fmt in ("docx", "word"):
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, _md_to_docx, markdown)
        return (
            data,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".docx",
        )
    raise ValueError(f"Unsupported format: {fmt}")


# Keep sync version for backward-compatibility with non-async callers
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


# ─── TXT ──────────────────────────────────────────────────────────────────────

def _md_to_txt(md: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", md, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # Convert bullet markers to unicode bullet (run AFTER italic strip)
    text = re.sub(r"^[-*+]\s+", "• ", text, flags=re.MULTILINE)
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
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable, ListFlowable, ListItem,
            Paragraph, SimpleDocTemplate, Spacer,
        )
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "MISSING_DEP",
                "message": "reportlab not installed. Run: pip install reportlab",
            },
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

    # ── Colour palette ─────────────────────────────────────────────────────
    ACCENT = colors.HexColor("#2828B4")
    DARK   = colors.HexColor("#111111")
    BODY   = colors.HexColor("#333333")
    MUTED  = colors.HexColor("#555555")

    # ── Paragraph styles ───────────────────────────────────────────────────
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

    # ── Helper: escape XML special chars in plain text segments only ────────
    def _escape(text: str) -> str:
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    # FIX #3: escape happens per-segment so bold/italic tags are never double-escaped
    def _inline(text: str) -> str:
        """
        Convert Markdown inline formatting to ReportLab XML.
        Escapes XML chars in plain-text segments only, so that
        special chars inside bold/italic (e.g. 'R&D') render correctly.
        """
        # Strip markdown links first (no hyperlinks in basic PDF)
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)

        # Split on **bold** and *italic* markers, process each segment
        parts = re.split(r"(\*\*.+?\*\*|\*.+?\*)", text)
        result = []
        for part in parts:
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                result.append(f"<b>{_escape(part[2:-2])}</b>")
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                result.append(f"<i>{_escape(part[1:-1])}</i>")
            else:
                result.append(_escape(part))
        return "".join(result)

    # ── Parse Markdown lines → Flowables ───────────────────────────────────
    story: list = []
    lines = md.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 2 * mm))
            i += 1
            continue

        # H1 — also consume the very next non-empty line as the contact row
        if stripped.startswith("# "):
            story.append(Paragraph(_escape(stripped[2:].strip()), h1_style))
            i += 1
            if i < len(lines) and lines[i].strip():
                story.append(Paragraph(_inline(lines[i].strip()), contact_style))
                i += 1
            continue

        # H3 must be checked before H2 to avoid a "## " prefix match on "### "
        if stripped.startswith("### "):
            story.append(Paragraph(_escape(stripped[4:].strip()), h3_style))
            i += 1
            continue

        # H2
        if stripped.startswith("## "):
            story.append(Paragraph(_escape(stripped[3:].strip()), h2_style))
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=ACCENT, spaceAfter=2 * mm,
            ))
            i += 1
            continue

        # Horizontal rule — must be checked BEFORE bullet check
        # because "---" starts with "-" but is not a bullet
        if re.match(r"^-{3,}$", stripped):
            story.append(HRFlowable(
                width="100%", thickness=0.3,
                color=colors.lightgrey, spaceAfter=2 * mm,
            ))
            i += 1
            continue

        # FIX #2: bullet list — guard against empty "- " lines causing infinite loop
        if stripped.startswith(("- ", "* ", "+ ")):
            bullets = []
            while i < len(lines):
                s = lines[i].strip()
                # Stop if line is not a bullet or has no content after the marker
                if not s.startswith(("- ", "* ", "+ ")) or len(s) <= 2:
                    break
                content = re.sub(r"^[-*+]\s+", "", s)
                bullets.append(
                    ListItem(
                        Paragraph(_inline(content), bullet_style),
                        bulletColor=ACCENT,
                        leftIndent=8 * mm,
                        bulletFontSize=10,
                    )
                )
                i += 1
            if bullets:
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
        story.append(Paragraph(_inline(stripped), body_style))
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
            detail={
                "code": "MISSING_DEP",
                "message": "python-docx not installed. Run: pip install python-docx",
            },
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

        elif stripped.startswith("### "):
            # FIX: check H3 before H2 to avoid mismatching "### " as "## "
            p = doc.add_heading(stripped[4:].strip(), level=3)
            if p.runs:
                p.runs[0].font.size = Pt(11)

        elif stripped.startswith("## "):
            p = doc.add_heading(stripped[3:].strip(), level=2)
            for run in p.runs:
                run.font.color.rgb = RGBColor(0x28, 0x28, 0xB4)
                run.font.size = Pt(13)

        elif re.match(r"^-{3,}$", stripped):
            # Horizontal rule — must be before bullet check
            doc.add_paragraph("─" * 60)

        elif stripped.startswith(("- ", "* ", "+ ")):
            # FIX #4: strip bold AND italic markers from bullet content
            content = re.sub(r"^[-*+]\s+", "", stripped)
            content = re.sub(r"\*\*(.+?)\*\*", r"\1", content)
            content = re.sub(r"\*(.+?)\*",     r"\1", content)
            doc.add_paragraph(content, style="List Bullet")

        else:
            # Normal paragraph — render **bold** and *italic* as formatted runs
            p = doc.add_paragraph()
            # Split on bold first, then italic within non-bold segments
            segments = re.split(r"(\*\*.+?\*\*)", stripped)
            for seg in segments:
                if seg.startswith("**") and seg.endswith("**") and len(seg) > 4:
                    run = p.add_run(seg[2:-2])
                    run.bold = True
                else:
                    # Handle italic within non-bold segment
                    sub_segs = re.split(r"(\*.+?\*)", seg)
                    for sub in sub_segs:
                        if sub.startswith("*") and sub.endswith("*") and len(sub) > 2:
                            run = p.add_run(sub[1:-1])
                            run.italic = True
                        elif sub:
                            p.add_run(sub)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clean_md(text: str) -> str:
    """
    Strip opening/closing markdown code fences of any language tag.
    Handles: ```markdown, ```md, ```text, ``` (bare), etc.
    FIX #1: strip once at start, apply both regexes, strip once at end.
    """
    text = text.strip()
    # Remove opening fence: ``` optionally followed by a language tag and newline
    text = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text, flags=re.IGNORECASE)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text, flags=re.IGNORECASE)
    return text.strip()


def _json_to_markdown(data: dict) -> str:
    """
    FIX #5: Now renders all standard resume sections, not just Skills & Projects.
    Handles common JSON key variants returned by different AI models.
    """
    resume = data.get("resume", data)

    # ── Name & contact ──────────────────────────────────────────────────────
    # Try multiple key variants for name
    name = (
        resume.get("# Full Name") or
        resume.get("fullName") or
        resume.get("name") or
        ""
    )
    
    # Contact can be nested object or flat keys
    contact_obj = resume.get("contact", {})
    if isinstance(contact_obj, dict):
        contact_parts = filter(None, [
            contact_obj.get("email", resume.get("email", "")),
            contact_obj.get("phone", resume.get("phone", "")),
            contact_obj.get("linkedin", resume.get("linkedin", "")),
            contact_obj.get("github", resume.get("github", "")),
            contact_obj.get("location", resume.get("location", "")),
        ])
    else:
        contact_parts = filter(None, [
            resume.get("email", ""),
            resume.get("phone", ""),
            resume.get("linkedin", ""),
            resume.get("github", ""),
            resume.get("location", ""),
        ])
    contact_line = " | ".join(contact_parts)

    # ── Summary ─────────────────────────────────────────────────────────────
    summary = resume.get(
        "professionalSummary",
        resume.get("summary", ""),
    )

    # ── Technical Skills ────────────────────────────────────────────────────
    skills = resume.get("technicalSkills", resume.get("skills", {}))
    skill_lines: list[str] = []
    if isinstance(skills, dict):
        for k, v in skills.items():
            val = ", ".join(v) if isinstance(v, list) else str(v)
            skill_lines.append(f"**{k}:** {val}")
    elif isinstance(skills, list):
        skill_lines = [f"- {s}" for s in skills]

    # ── Professional Experience ─────────────────────────────────────────────
    experience = resume.get(
        "professionalExperience",
        resume.get("experience", resume.get("workExperience", [])),
    )
    exp_lines: list[str] = []
    
    # Handle both string summaries and structured job lists
    if isinstance(experience, str):
        # If it's a string (summary), add it as a paragraph
        if experience.strip():
            exp_lines.append(experience.strip())
    elif isinstance(experience, list):
        # If it's a list of job objects
        for job in experience:
            title   = job.get("title",   job.get("role", ""))
            company = job.get("company", job.get("employer", ""))
            dates   = job.get("dates",   job.get("duration", ""))
            exp_lines.append(f"### {title} — {company} ({dates})")
            for bullet in job.get("responsibilities", job.get("achievements", [])):
                exp_lines.append(f"- {bullet}")
            exp_lines.append("")

    # ── Projects ────────────────────────────────────────────────────────────
    projects = resume.get("projects", [])
    project_lines: list[str] = []
    for p in projects:
        proj_name = p.get("name", "")
        proj_desc = p.get("description", "")
        # Handle both 'duration' and 'dates' keys, plus 'technologies' and 'tech'
        proj_duration = p.get("duration", p.get("dates", ""))
        proj_tech = p.get("technologies", p.get("tech", ""))
        if isinstance(proj_tech, list):
            proj_tech = ", ".join(proj_tech)
        line = f"- **{proj_name}** — {proj_desc}"
        if proj_duration:
            line += f" | {proj_duration}"
        if proj_tech:
            line += f" | *{proj_tech}*"
        project_lines.append(line)

    # ── Education ───────────────────────────────────────────────────────────
    education = resume.get("education", [])
    edu_lines: list[str] = []
    for e in education:
        degree      = e.get("degree",      "")
        institution = e.get("institution", e.get("school", ""))
        year        = e.get("year", e.get("duration", e.get("graduationYear", "")))
        line = f"- {degree}"
        if institution:
            line += f" — {institution}"
        if year:
            line += f" ({year})"
        edu_lines.append(line)

    # ── Certifications ──────────────────────────────────────────────────────
    certs = resume.get("certifications", [])
    cert_lines: list[str] = []
    for c in certs:
        if isinstance(c, str):
            cert_lines.append(f"- {c}")
        else:
            cert_name = c.get("name", "")
            cert_issuer = c.get("issuer", "")
            cert_year = c.get("year", c.get("date", ""))
            line = f"- {cert_name}"
            if cert_issuer:
                line += f" — {cert_issuer}"
            if cert_year:
                line += f" ({cert_year})"
            cert_lines.append(line)

    # ── Assemble ────────────────────────────────────────────────────────────
    sections: list[str] = [f"# {name}"]
    if contact_line:
        sections.append(contact_line)
    sections.append("")

    if summary:
        sections += ["## Professional Summary", summary, ""]

    if skill_lines:
        sections += ["## Technical Skills"] + skill_lines + [""]

    if exp_lines:
        sections += ["## Professional Experience"] + exp_lines

    if project_lines:
        sections += ["## Projects"] + project_lines + [""]

    if edu_lines:
        sections += ["## Education"] + edu_lines + [""]

    if cert_lines:
        sections += ["## Certifications"] + cert_lines + [""]

    return "\n".join(sections).strip()