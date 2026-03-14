"""
ATS Resume Builder — uses the active AI provider (Gemini or Groq).
Provider is resolved from the same settings as ai_service.py.
"""
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException

from ..config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

_REASONING_MODEL_GROQ   = "llama-3.3-70b-versatile"
_REASONING_MODEL_GEMINI = "gemini-1.5-flash"
_executor = ThreadPoolExecutor(max_workers=4)


# ─── Provider resolution (mirrors ai_service.py) ─────────────────────────────
def _resolve_provider() -> str:
    explicit = getattr(settings, "ai_provider", "auto").lower()
    if explicit in ("gemini", "fallback"):
        return explicit
    return "gemini" if settings.gemini_api_key else "fallback"

_PROVIDER = _resolve_provider()

if _PROVIDER == "gemini":
    import google.generativeai as _genai
    _genai.configure(api_key=settings.gemini_api_key)
else:
    from groq import Groq as _Groq
    _groq_client = _Groq(api_key=settings.groq_api_key)


# ─── Public ───────────────────────────────────────────────────────────────────

async def build_ats_resume(resume_text: str, jd_text: str, filename: str) -> str:
    """Generate a polished, ATS-optimised resume in Markdown."""
    prompt = _build_resume_prompt(resume_text, jd_text)
    loop   = asyncio.get_event_loop()
    fn     = _gemini_generate if _PROVIDER == "gemini" else _groq_generate
    try:
        result = await loop.run_in_executor(_executor, fn, prompt)
    except Exception as exc:
        logger.error("Resume builder failed [%s]: %s: %s", _PROVIDER, type(exc).__name__, exc, exc_info=True)
        msg = (
            f"[{_PROVIDER}] Resume builder error ({type(exc).__name__}): {exc}"
            if settings.is_development
            else "ATS resume generation failed. Please try again."
        )
        raise HTTPException(status_code=503, detail={"code": "RESUME_BUILD_ERROR", "message": msg})
    return _clean_output(result)


# ─── Private: Gemini ──────────────────────────────────────────────────────────

def _gemini_generate(prompt: str) -> str:
    try:
        model    = _genai.GenerativeModel(_REASONING_MODEL_GEMINI)
        response = model.generate_content(
            prompt,
            generation_config=_genai.GenerationConfig(temperature=0.2, max_output_tokens=4096),
        )
        return response.text
    except Exception as exc:
        logger.error("Gemini resume generate failed: %s: %s", type(exc).__name__, exc, exc_info=True)
        raise


# ─── Private: Groq ───────────────────────────────────────────────────────────

def _groq_generate(prompt: str) -> str:
    try:
        response = _groq_client.chat.completions.create(
            model=_REASONING_MODEL_GROQ,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an elite career consultant. "
                        "Return ONLY clean Markdown — no preamble, no code fences, no commentary."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("Groq resume generate failed: %s: %s", type(exc).__name__, exc, exc_info=True)
        raise


# ─── Private: Prompt & cleanup ────────────────────────────────────────────────

def _build_resume_prompt(resume_text: str, jd_text: str) -> str:
    return f"""You are an elite career consultant helping candidates land roles at top companies.
Rewrite the resume below into a flawlessly structured, ATS-optimised Markdown document
aligned to the given job description.

=== ORIGINAL RESUME ===
{resume_text[:8000]}
=== END RESUME ===

=== TARGET JOB DESCRIPTION ===
{jd_text[:4000]}
=== END JOB DESCRIPTION ===

STRICT RULES:
1. NEVER invent or fabricate any fact, company, date, role, metric, or skill.
2. Mirror JD keywords naturally — no keyword stuffing.
3. Use strong action verbs (Architected, Spearheaded, Delivered, etc.).
4. Follow Harvard resume format: reverse-chronological, clear hierarchy.

Return ONLY clean Markdown — no preamble, no fences, no commentary.

# [Full Name]
[Email] | [Phone] | [LinkedIn] | [GitHub] | [Location]

## Professional Summary
[3-4 impactful lines tailored to JD]

## Technical Skills
**Languages:** ...
**Frameworks & Libraries:** ...
**Cloud & Infrastructure:** ...
**Databases:** ...
**Tools & Methodologies:** ...

## Professional Experience
### [Job Title] — [Company] | [Location] | [Start] – [End]
- Impact-first quantified bullet

## Projects *(if present)*
## Education
## Certifications *(if present)*
## Publications / Research *(if present)*"""


def _clean_output(text: str) -> str:
    text = re.sub(r"^```(?:markdown)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text.strip(), flags=re.IGNORECASE)
    return text.strip()
