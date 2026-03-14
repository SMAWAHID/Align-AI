"""
AI service — Gemini primary, Jina AI + Groq free fallback.

Provider selection (automatic at startup):
  • GEMINI  → if GEMINI_API_KEY is set in .env
  • FALLBACK → if GEMINI_API_KEY is absent/empty; uses:
               - Jina AI  (jina-embeddings-v3)  for embeddings
               - Groq     (llama-3.3-70b-versatile) for reasoning

To force a provider explicitly, set:
  AI_PROVIDER=gemini   or   AI_PROVIDER=fallback
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
from ..schemas import GapAnalysisReport

logger = logging.getLogger(__name__)
settings = get_settings()

_executor = ThreadPoolExecutor(max_workers=6)


# ─── Provider selection ───────────────────────────────────────────────────────

def _resolve_provider() -> str:
    """
    Return 'gemini' or 'fallback' based on config.
    'auto' (default) picks gemini if GEMINI_API_KEY is non-empty.
    """
    explicit = getattr(settings, "ai_provider", "auto").lower()
    if explicit in ("gemini", "fallback"):
        return explicit
    # auto
    return "gemini" if settings.gemini_api_key else "fallback"


_PROVIDER = _resolve_provider()
logger.info("AI provider: %s", _PROVIDER.upper())


# ─── Gemini setup (lazy — only if needed) ────────────────────────────────────
if _PROVIDER == "gemini":
    import google.generativeai as _genai
    _genai.configure(api_key=settings.gemini_api_key)
    _GEMINI_EMBED_MODEL = "models/text-embedding-004"
    _GEMINI_GEN_MODEL   = "gemini-1.5-flash"


# ─── Jina / Groq setup (lazy — only if needed) ───────────────────────────────
if _PROVIDER == "fallback":
    from groq import Groq as _Groq
    _groq_client   = _Groq(api_key=settings.groq_api_key)
    _JINA_API_URL  = "https://api.jina.ai/v1/embeddings"
    _JINA_MODEL    = "jina-embeddings-v3"
    _GROQ_MODEL    = "llama-3.3-70b-versatile"


# ─── Result containers ────────────────────────────────────────────────────────

class EmbeddingPair(NamedTuple):
    resume: list[float]
    jd: list[float]


class HybridScore(NamedTuple):
    final: float
    semantic: float
    keyword: float
    missing_tokens: list[str]


# ─── Stop words ───────────────────────────────────────────────────────────────
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "shall", "can", "need", "dare", "ought", "used", "this", "that", "these",
    "those", "i", "we", "you", "he", "she", "it", "they", "what", "which",
    "who", "whom", "when", "where", "why", "how", "all", "both", "each",
    "few", "more", "most", "other", "some", "such", "no", "not", "only",
    "own", "same", "so", "than", "too", "very", "just", "also", "our",
    "their", "your", "his", "her", "its", "my", "as", "if", "while",
    "although", "because", "since", "unless", "until", "whether",
    "experience", "work", "working", "worked", "responsible", "responsibilities",
    "strong", "excellent", "good", "including", "include", "includes",
    "ability", "skills", "skill", "knowledge", "understanding",
    "year", "years", "month", "months",
})


# ─── Public API ───────────────────────────────────────────────────────────────

async def get_embeddings(resume_text: str, jd_text: str) -> EmbeddingPair:
    """Fetch embedding vectors concurrently using the active provider."""
    loop = asyncio.get_event_loop()

    if _PROVIDER == "gemini":
        resume_fut = loop.run_in_executor(_executor, _gemini_embed, resume_text[:8000], "RETRIEVAL_DOCUMENT")
        jd_fut     = loop.run_in_executor(_executor, _gemini_embed, jd_text[:8000],     "RETRIEVAL_QUERY")
    else:
        # Jina uses "retrieval.passage" / "retrieval.query"
        resume_fut = loop.run_in_executor(_executor, _jina_embed, resume_text[:8000], "retrieval.passage")
        jd_fut     = loop.run_in_executor(_executor, _jina_embed, jd_text[:8000],     "retrieval.query")

    try:
        resume_emb, jd_emb = await asyncio.gather(resume_fut, jd_fut)
    except Exception as exc:
        msg = (
            f"[{_PROVIDER}] Embedding error ({type(exc).__name__}): {exc}"
            if settings.is_development
            else "AI embedding service unavailable. Please try again."
        )
        raise HTTPException(status_code=503, detail={"code": "EMBEDDING_ERROR", "message": msg})

    return EmbeddingPair(resume=resume_emb, jd=jd_emb)


async def calculate_hybrid_score(
    resume_text: str,
    jd_text: str,
    embeddings: EmbeddingPair,
) -> HybridScore:
    """Weighted composite: semantic (60%) + keyword overlap (40%)."""
    sem_sim      = _cosine_similarity(embeddings.resume, embeddings.jd)
    semantic_pct = round(sem_sim * 100, 2)
    kw_pct, missing = _keyword_overlap(resume_text, jd_text)
    final = min(
        round(semantic_pct * settings.semantic_weight + kw_pct * settings.keyword_weight, 2),
        100.0,
    )
    return HybridScore(final=final, semantic=semantic_pct, keyword=round(kw_pct, 2), missing_tokens=missing)


async def analyse_gap(
    resume_text: str,
    jd_text: str,
    missing_tokens: list[str],
    final_score: float,
) -> GapAnalysisReport:
    """Call the active provider's LLM for gap analysis."""
    prompt = _build_gap_prompt(resume_text, jd_text, missing_tokens, final_score)
    loop   = asyncio.get_event_loop()
    fn     = _gemini_generate if _PROVIDER == "gemini" else _groq_generate

    try:
        raw = await loop.run_in_executor(_executor, fn, prompt)
    except Exception as exc:
        msg = (
            f"[{_PROVIDER}] Reasoning error ({type(exc).__name__}): {exc}"
            if settings.is_development
            else "AI reasoning service unavailable. Please try again."
        )
        raise HTTPException(status_code=503, detail={"code": "REASONING_ERROR", "message": msg})

    return _parse_gap_response(raw)


# ─── Private: Gemini wrappers ────────────────────────────────────────────────

def _gemini_embed(text: str, task_type: str) -> list[float]:
    try:
        result = _genai.embed_content(
            model=_GEMINI_EMBED_MODEL,
            content=text,
            task_type=task_type,
        )
        return result["embedding"]
    except Exception as exc:
        logger.error("Gemini embed failed [task=%s]: %s: %s", task_type, type(exc).__name__, exc, exc_info=True)
        raise


def _gemini_generate(prompt: str) -> str:
    try:
        model    = _genai.GenerativeModel(_GEMINI_GEN_MODEL)
        response = model.generate_content(
            prompt,
            generation_config=_genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=2048,
                response_mime_type="application/json",
            ),
        )
        return response.text
    except Exception as exc:
        logger.error("Gemini generate failed: %s: %s", type(exc).__name__, exc, exc_info=True)
        raise


# ─── Private: Jina AI wrappers ────────────────────────────────────────────────

def _jina_embed(text: str, task: str) -> list[float]:
    """
    Jina AI embeddings — free tier: 1M tokens/month.
    task: "retrieval.passage"  (for resume)
          "retrieval.query"    (for job description)
    Docs: https://jina.ai/embeddings
    """
    try:
        response = httpx.post(
            _JINA_API_URL,
            headers={
                "Authorization": f"Bearer {settings.jina_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": _JINA_MODEL,
                "input": [{"text": text}],
                "task": task,
                "dimensions": 1024,
                "late_chunking": False,
                "embedding_type": "float",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    except Exception as exc:
        logger.error("Jina embed failed [task=%s]: %s: %s", task, type(exc).__name__, exc, exc_info=True)
        raise


# ─── Private: Groq wrappers ──────────────────────────────────────────────────

def _groq_generate(prompt: str) -> str:
    """
    Groq inference — free tier with generous rate limits.
    Uses llama-3.3-70b-versatile (fast + high quality).
    Docs: https://console.groq.com/docs/openai
    """
    try:
        # Groq doesn't support JSON mime type natively — instruct via system prompt
        system = (
            "You are a JSON-only API. Respond ONLY with a valid JSON object. "
            "No markdown, no explanation, no preamble."
        )
        response = _groq_client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("Groq generate failed: %s: %s", type(exc).__name__, exc, exc_info=True)
        raise


# ─── Private: Scoring helpers ─────────────────────────────────────────────────

def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a, b = np.array(vec_a, dtype=np.float32), np.array(vec_b, dtype=np.float32)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / norm) if norm > 0 else 0.0


def _tokenise(text: str) -> Counter:
    text   = text.lower()
    words  = re.findall(r"\b[a-z][a-z0-9+#.\-]{1,30}\b", text)
    tokens = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    bigrams = [f"{tokens[i]} {tokens[i+1]}" for i in range(len(tokens) - 1)]
    return Counter(tokens + bigrams)


def _keyword_overlap(resume_text: str, jd_text: str) -> tuple[float, list[str]]:
    resume_tokens = set(_tokenise(resume_text).keys())
    jd_tokens     = _tokenise(jd_text)
    if not jd_tokens:
        return 100.0, []
    total_weight   = sum(jd_tokens.values())
    matched_weight = sum(count for tok, count in jd_tokens.items() if tok in resume_tokens)
    missing = [
        tok for tok, _ in jd_tokens.most_common(50)
        if tok not in resume_tokens and len(tok) > 3
    ][:20]
    raw_score = (matched_weight / total_weight) * 100
    return round(min(raw_score * 1.25, 100.0), 2), missing


# ─── Private: Gap analysis helpers ───────────────────────────────────────────

def _build_gap_prompt(
    resume_text: str,
    jd_text: str,
    missing_tokens: list[str],
    score: float,
) -> str:
    token_hint = ", ".join(missing_tokens[:15]) if missing_tokens else "none detected"
    return f"""You are a senior technical recruiter performing a resume gap analysis.

MATCH SCORE: {score:.1f}% (target: 85%)
PRELIMINARY MISSING KEYWORDS: {token_hint}

RESUME (truncated):
---
{resume_text[:6000]}
---

JOB DESCRIPTION (truncated):
---
{jd_text[:4000]}
---

Return ONLY a valid JSON object — no markdown fences, no preamble:

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
        if m:
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                logger.warning("Could not parse gap JSON: %r", raw[:200])
                return _fallback_report()
        else:
            logger.warning("No JSON in gap response: %r", raw[:200])
            return _fallback_report()
    try:
        return GapAnalysisReport.model_validate(data)
    except Exception as exc:
        logger.warning("GapAnalysisReport validation failed: %s", exc)
        return GapAnalysisReport(
            missing_skills=_safe_list(data, "missing_skills"),
            improvements=_safe_list(data, "improvements"),
            match_summary=str(data.get("match_summary", ""))[:1000],
        )


def _safe_list(data: dict, key: str) -> list[str]:
    val = data.get(key, [])
    return [str(v) for v in val if v][:30] if isinstance(val, list) else []


def _fallback_report() -> GapAnalysisReport:
    return GapAnalysisReport(
        missing_skills=[],
        improvements=[],
        match_summary="Gap analysis could not be generated automatically. Please review the job description manually.",
    )
