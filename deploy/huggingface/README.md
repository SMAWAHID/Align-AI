---
title: AlignAI API
emoji: 🎯
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: Semantic resume matcher API — FastAPI, Postgres, Groq + Jina
---

# AlignAI — API

FastAPI backend for [AlignAI](https://github.com/SMAWAHID/Align-AI), a semantic
resume matcher. Source of truth is the GitHub repo; this Space is a deployment
target assembled by `deploy/huggingface/sync.sh`.

- `GET /health` — liveness probe
- `GET /docs` — interactive API reference
- `POST /api/v1/analyze` — score a resume against a job description
- `WS /api/v1/ws/analyze` — the same pipeline with live per-step progress

Scoring is hybrid: cosine similarity over Jina embeddings, blended with keyword
overlap, then gap analysis from a Groq-hosted Llama model.

## Configuration

Set as Space secrets: `DATABASE_URL`, `JINA_API_KEY`, `GROQ_API_KEY`.
Set as Space variables: `ENVIRONMENT`, `AI_PROVIDER`, `ALLOWED_ORIGINS`,
`ALLOWED_HOSTS`, `ENABLE_DOCS`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`.
