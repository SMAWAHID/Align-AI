"""
AI service — Gemini primary, Jina AI + Groq free fallback.

Provider selection (automatic at startup):
  • GEMINI   → if GEMINI_API_KEY is set
  • FALLBACK → uses Jina AI (embeddings) + Groq (generation)
"""
import asyncio
import json
import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import NamedTuple

import httpx
import numpy as np
from fastapi import HTTPException

from ..config import get_settings
from ..schemas import GapAnalysisReport, SkillResource, SkillWithResources

logger   = logging.getLogger(__name__)
settings = get_settings()
_executor = ThreadPoolExecutor(max_workers=6)


# ─── Provider selection ───────────────────────────────────────────────────────

def _resolve_provider() -> str:
    explicit = getattr(settings, "ai_provider", "auto").lower()
    if explicit in ("gemini", "fallback"):
        return explicit
    return "gemini" if settings.gemini_api_key else "fallback"

_PROVIDER = _resolve_provider()
logger.info("AI provider: %s", _PROVIDER.upper())

if _PROVIDER == "gemini":
    import google.generativeai as _genai
    _genai.configure(api_key=settings.gemini_api_key)
    _GEMINI_EMBED_MODEL = "models/text-embedding-004"
    _GEMINI_GEN_MODEL   = "gemini-1.5-flash"

if _PROVIDER == "fallback":
    from groq import Groq as _Groq
    _groq_client  = _Groq(api_key=settings.groq_api_key)
    _JINA_API_URL = "https://api.jina.ai/v1/embeddings"
    _JINA_MODEL   = "jina-embeddings-v3"
    _GROQ_MODEL   = "llama-3.3-70b-versatile"


# ─── Result containers ────────────────────────────────────────────────────────

class EmbeddingPair(NamedTuple):
    resume: list[float]
    jd: list[float]

class HybridScore(NamedTuple):
    final: float
    semantic: float
    keyword: float
    missing_tokens: list[str]

_STOP_WORDS = frozenset({
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "by","from","up","about","into","through","during","is","are","was","were",
    "be","been","being","have","has","had","do","does","did","will","would",
    "could","should","may","might","shall","can","need","dare","ought","used",
    "this","that","these","those","i","we","you","he","she","it","they","what",
    "which","who","whom","when","where","why","how","all","both","each","few",
    "more","most","other","some","such","no","not","only","own","same","so",
    "than","too","very","just","also","our","their","your","his","her","its",
    "my","as","if","while","although","because","since","unless","until",
    "whether","experience","work","working","worked","responsible",
    "responsibilities","strong","excellent","good","including","include",
    "includes","ability","skills","skill","knowledge","understanding",
    "year","years","month","months",
})


# ─── Public API ───────────────────────────────────────────────────────────────

async def get_embeddings(resume_text: str, jd_text: str) -> EmbeddingPair:
    loop = asyncio.get_event_loop()
    if _PROVIDER == "gemini":
        r_fut = loop.run_in_executor(_executor, _gemini_embed, resume_text[:8000], "RETRIEVAL_DOCUMENT")
        j_fut = loop.run_in_executor(_executor, _gemini_embed, jd_text[:8000],     "RETRIEVAL_QUERY")
    else:
        r_fut = loop.run_in_executor(_executor, _jina_embed, resume_text[:8000], "retrieval.passage")
        j_fut = loop.run_in_executor(_executor, _jina_embed, jd_text[:8000],     "retrieval.query")
    try:
        resume_emb, jd_emb = await asyncio.gather(r_fut, j_fut)
    except Exception as exc:
        msg = (
            f"[{_PROVIDER}] Embedding error ({type(exc).__name__}): {exc}"
            if settings.is_development
            else "AI embedding service unavailable. Please try again."
        )
        raise HTTPException(status_code=503, detail={"code": "EMBEDDING_ERROR", "message": msg})
    return EmbeddingPair(resume=resume_emb, jd=jd_emb)


async def calculate_hybrid_score(resume_text: str, jd_text: str, embeddings: EmbeddingPair) -> HybridScore:
    sem_sim      = _cosine_similarity(embeddings.resume, embeddings.jd)
    semantic_pct = round(sem_sim * 100, 2)
    kw_pct, missing = _keyword_overlap(resume_text, jd_text)
    final = min(round(semantic_pct * settings.semantic_weight + kw_pct * settings.keyword_weight, 2), 100.0)
    return HybridScore(final=final, semantic=semantic_pct, keyword=round(kw_pct, 2), missing_tokens=missing)


async def analyse_gap(resume_text: str, jd_text: str, missing_tokens: list[str], final_score: float) -> GapAnalysisReport:
    prompt = _build_gap_prompt(resume_text, jd_text, missing_tokens, final_score)
    loop   = asyncio.get_event_loop()
    fn     = _gemini_generate if _PROVIDER == "gemini" else _groq_generate
    try:
        raw = await loop.run_in_executor(_executor, lambda: fn(prompt))
    except Exception as exc:
        msg = (
            f"[{_PROVIDER}] Reasoning error ({type(exc).__name__}): {exc}"
            if settings.is_development
            else "AI reasoning service unavailable. Please try again."
        )
        raise HTTPException(status_code=503, detail={"code": "REASONING_ERROR", "message": msg})
    return _parse_gap_response(raw)


async def find_skill_resources(missing_skills: list[str]) -> list[SkillWithResources]:
    """Return curated learning resource links for each missing skill."""
    if not missing_skills:
        return []
    skills = missing_skills[:15]
    loop   = asyncio.get_event_loop()
    fn     = _gemini_generate if _PROVIDER == "gemini" else _groq_generate
    prompt = _build_resources_prompt(skills)
    try:
        raw = await loop.run_in_executor(_executor, lambda: fn(prompt))
        return _parse_resources_response(raw, skills)
    except Exception as exc:
        logger.warning("Skill resources generation failed (%s): %s", type(exc).__name__, exc)
        return _fallback_resources(skills)


async def generate_text(prompt: str, max_tokens: int = 4096) -> str:
    """Generic text generation for resume builder."""
    loop = asyncio.get_event_loop()
    fn   = _gemini_generate if _PROVIDER == "gemini" else _groq_generate
    try:
        return await loop.run_in_executor(_executor, lambda: fn(prompt, max_tokens=max_tokens))
    except Exception as exc:
        msg = (
            f"[{_PROVIDER}] Generation error ({type(exc).__name__}): {exc}"
            if settings.is_development
            else "AI generation service unavailable. Please try again."
        )
        raise HTTPException(status_code=503, detail={"code": "GENERATION_ERROR", "message": msg})


# ─── Private: Gemini ─────────────────────────────────────────────────────────

def _gemini_embed(text: str, task_type: str) -> list[float]:
    try:
        result = _genai.embed_content(model=_GEMINI_EMBED_MODEL, content=text, task_type=task_type)
        return result["embedding"]
    except Exception as exc:
        logger.error("Gemini embed failed [task=%s]: %s", task_type, exc, exc_info=True)
        raise

def _gemini_generate(prompt: str, max_tokens: int = 2048) -> str:
    try:
        model = _genai.GenerativeModel(_GEMINI_GEN_MODEL)
        resp  = model.generate_content(prompt, generation_config=_genai.GenerationConfig(
            temperature=0.1, max_output_tokens=max_tokens, response_mime_type="application/json"))
        return resp.text
    except Exception as exc:
        logger.error("Gemini generate failed: %s", exc, exc_info=True)
        raise


# ─── Private: Jina ────────────────────────────────────────────────────────────

def _jina_embed(text: str, task: str) -> list[float]:
    try:
        resp = httpx.post(_JINA_API_URL, headers={"Authorization": f"Bearer {settings.jina_api_key}", "Content-Type": "application/json"},
            json={"model": _JINA_MODEL, "input": [{"text": text}], "task": task, "dimensions": 1024, "late_chunking": False, "embedding_type": "float"},
            timeout=30.0)
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]
    except Exception as exc:
        logger.error("Jina embed failed [task=%s]: %s", task, exc, exc_info=True)
        raise


# ─── Private: Groq ────────────────────────────────────────────────────────────

def _groq_generate(prompt: str, max_tokens: int = 2048) -> str:
    try:
        resp = _groq_client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a JSON-only API. Respond ONLY with a valid JSON object. No markdown fences, no preamble."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1, max_tokens=max_tokens)
        return resp.choices[0].message.content
    except Exception as exc:
        logger.error("Groq generate failed: %s", exc, exc_info=True)
        raise


# ─── Private: Scoring ─────────────────────────────────────────────────────────

def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a, b = np.array(vec_a, dtype=np.float32), np.array(vec_b, dtype=np.float32)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / norm) if norm > 0 else 0.0

def _tokenise(text: str) -> Counter:
    text    = text.lower()
    words   = re.findall(r"\b[a-z][a-z0-9+#.\-]{1,30}\b", text)
    tokens  = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens)-1)]
    return Counter(tokens + bigrams)

def _keyword_overlap(resume_text: str, jd_text: str) -> tuple[float, list[str]]:
    resume_tokens = set(_tokenise(resume_text).keys())
    jd_tokens     = _tokenise(jd_text)
    if not jd_tokens:
        return 100.0, []
    total_weight   = sum(jd_tokens.values())
    matched_weight = sum(count for tok, count in jd_tokens.items() if tok in resume_tokens)
    missing = [tok for tok, _ in jd_tokens.most_common(50) if tok not in resume_tokens and len(tok) > 3][:20]
    return round(min((matched_weight / total_weight) * 100 * 1.25, 100.0), 2), missing


# ─── Private: Gap analysis ────────────────────────────────────────────────────

def _build_gap_prompt(resume_text: str, jd_text: str, missing_tokens: list[str], score: float) -> str:
    token_hint = ", ".join(missing_tokens[:15]) if missing_tokens else "none detected"
    return f"""You are a senior technical recruiter performing a resume gap analysis.

MATCH SCORE: {score:.1f}% (target: 85%)
PRELIMINARY MISSING KEYWORDS: {token_hint}

RESUME:
---
{resume_text[:6000]}
---

JOB DESCRIPTION:
---
{jd_text[:4000]}
---

Return ONLY a valid JSON object:
{{
  "missing_skills": ["Specific skill/tool in JD but absent from resume (5-15 items)"],
  "improvements": ["Concrete, actionable improvement suggestion (5-10 items)"],
  "match_summary": "2-3 sentence plain-English summary."
}}"""

def _parse_gap_response(raw: str) -> GapAnalysisReport:
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw, flags=re.IGNORECASE).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        data = json.loads(m.group()) if m else {}
    try:
        return GapAnalysisReport.model_validate(data)
    except Exception:
        return GapAnalysisReport(
            missing_skills=_safe_list(data, "missing_skills"),
            improvements=_safe_list(data, "improvements"),
            match_summary=str(data.get("match_summary", ""))[:1000],
        )


# ─── Private: Skill resources ─────────────────────────────────────────────────

def _build_resources_prompt(skills: list[str]) -> str:
    skills_str = "\n".join(f"- {s}" for s in skills)
    return f"""For each skill below, provide 2-3 curated learning resources.
Use ONLY real URL patterns:
  - Official docs:   the real official site
  - YouTube search:  https://www.youtube.com/results?search_query=SKILL+tutorial
  - Coursera search: https://www.coursera.org/search?query=SKILL

Skills:
{skills_str}

Return ONLY valid JSON:
{{
  "resources": {{
    "EXACT_SKILL_NAME": [
      {{"title": "Resource title", "url": "https://...", "type": "docs|course|video|tutorial"}}
    ]
  }}
}}
2-3 resources per skill. Match EXACT_SKILL_NAME to the skill names provided."""

def _parse_resources_response(raw: str, skills: list[str]) -> list[SkillWithResources]:
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", raw, flags=re.IGNORECASE).strip()
    try:
        data = json.loads(cleaned)
        resources_map: dict = data.get("resources", {})
    except Exception:
        return _fallback_resources(skills)

    result: list[SkillWithResources] = []
    for skill in skills:
        entries = resources_map.get(skill) or next(
            (v for k, v in resources_map.items() if k.lower() == skill.lower()), [])
        parsed: list[SkillResource] = []
        if isinstance(entries, list):
            for e in entries[:4]:
                if isinstance(e, dict) and e.get("url") and e.get("title"):
                    parsed.append(SkillResource(title=str(e["title"])[:120], url=str(e["url"])[:500], type=e.get("type", "other")))  # type: ignore
        if not parsed:
            parsed = _make_fallback_resources(skill)
        result.append(SkillWithResources(skill=skill, resources=parsed))
    return result

def _fallback_resources(skills: list[str]) -> list[SkillWithResources]:
    return [SkillWithResources(skill=s, resources=_make_fallback_resources(s)) for s in skills]

def _make_fallback_resources(skill: str) -> list[SkillResource]:
    slug = skill.replace(" ", "+")
    return [
        SkillResource(title=f"{skill} Tutorial — YouTube", url=f"https://www.youtube.com/results?search_query={slug}+tutorial", type="video"),
        SkillResource(title=f"{skill} Course — Coursera", url=f"https://www.coursera.org/search?query={slug}", type="course"),
    ]

def _safe_list(data: dict, key: str) -> list[str]:
    val = data.get(key, [])
    return [str(v) for v in val if v][:30] if isinstance(val, list) else []
