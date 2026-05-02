# AlignAI — Semantic Resume Matcher

> AI-powered resume–job description alignment engine using Google Gemini embeddings, hybrid scoring, and automated ATS resume generation.

![AlignAI Architecture](https://img.shields.io/badge/Stack-Next.js%2015%20%7C%20FastAPI%20%7C%20Gemini-6366f1?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.12%2B-3b82f6?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-10b981?style=flat-square)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Project Structure](#project-structure)
5. [Quick Start](#quick-start)
6. [Environment Variables](#environment-variables)
7. [API Contract](#api-contract)
8. [Scoring Algorithm](#scoring-algorithm)
9. [Security](#security)
10. [Data Flow](#data-flow)
11. [Frontend Components](#frontend-components)
12. [Development Guide](#development-guide)
13. [Deployment](#deployment)
14. [Troubleshooting](#troubleshooting)

---

## Overview

AlignAI takes a candidate's PDF resume and a job description, then:

1. **Extracts** resume text in-memory via PyMuPDF (zero disk I/O)
2. **Embeds** both texts with Google's `text-embedding-004` (768-dimensional vectors)
3. **Scores** alignment using a hybrid semantic + keyword model
4. **Analyses** skill gaps with `gemini-1.5-flash` (only when score < 85%)
5. **Generates** an ATS-optimised Markdown resume tailored to the specific JD
6. **Persists** all metadata to PostgreSQL
7. **Renders** a radial progress chart, accordion gap analysis, and resume viewer in the Next.js UI

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (Next.js 15)                     │
│  ┌──────────────┐  ┌─────────────────────┐  ┌───────────────┐  │
│  │  UploadForm  │  │  AnalysisDashboard  │  │ AtsResumeView │  │
│  │  (drag+drop) │  │  (tabs + radial)    │  │ (md + dl)     │  │
│  └──────┬───────┘  └──────────┬──────────┘  └───────────────┘  │
│         │   useAnalysis hook  │                                  │
│         └────────┬────────────┘                                  │
└──────────────────┼──────────────────────────────────────────────┘
                   │  FormData POST /api/v1/analyze (XHR + progress)
┌──────────────────▼──────────────────────────────────────────────┐
│                     FastAPI Backend                             │
│                                                                 │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────────┐  │
│  │ pdf_service │   │  ai_service  │   │   resume_builder    │  │
│  │  PyMuPDF    │   │ text-embed-  │   │  gemini-1.5-flash   │  │
│  │  in-memory  │   │ 004 + Flash  │   │  Markdown output    │  │
│  └──────┬──────┘   └──────┬───────┘   └─────────┬───────────┘  │
│         └─────────────────┴──────────────────────┘              │
│                           │                                     │
│                  ┌────────▼────────┐                            │
│                  │  SQLAlchemy 2.0 │                            │
│                  │  (asyncpg)      │                            │
│                  └────────┬────────┘                            │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                   ┌────────▼────────┐     ┌────────────────────┐
                   │   PostgreSQL    │     │   Google Gemini    │
                   │   (match_       │     │   text-embedding-  │
                   │    history)     │     │   004 + Flash      │
                   └─────────────────┘     └────────────────────┘
```

---

## Tech Stack

| Layer      | Technology                                | Version  |
|------------|-------------------------------------------|----------|
| Frontend   | Next.js (App Router)                      | 15.1.3   |
| UI         | Tailwind CSS + Radix UI primitives        | 3.4.x    |
| Language   | TypeScript                                | 5.7+     |
| Backend    | FastAPI                                   | 0.115.x  |
| ORM        | SQLAlchemy (asyncio)                      | 2.0.x    |
| Driver     | asyncpg (PostgreSQL)                      | 0.30.x   |
| PDF        | PyMuPDF (fitz)                            | 1.24.x   |
| AI         | Google Generative AI SDK                  | 0.8.x    |
| Embedding  | `text-embedding-004`                      | —        |
| Reasoning  | `gemini-1.5-flash`                        | —        |
| Numerics   | NumPy                                     | 2.2.x    |
| Rate Limit | SlowAPI                                   | 0.1.9    |
| Database   | PostgreSQL                                | 17       |
| Container  | Docker + Docker Compose                   | —        |

---

## Project Structure

```
alignai/
├── backend/
│   ├── main.py                  # FastAPI app, middleware, lifecycle
│   ├── config.py                # Pydantic-settings (env vars)
│   ├── database.py              # Async engine + session factory
│   ├── models.py                # SQLAlchemy ORM — MatchHistory table
│   ├── schemas.py               # Pydantic v2 API schemas
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── analysis.py          # POST /api/v1/analyze
│   │   └── history.py           # GET|DELETE /api/v1/history
│   └── services/
│       ├── __init__.py
│       ├── ai_service.py        # Gemini embeddings + gap analysis
│       ├── pdf_service.py       # In-memory PDF extraction
│       └── resume_builder.py    # ATS resume generation
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx           # Root layout + metadata
│   │   ├── page.tsx             # Main landing page
│   │   └── globals.css          # Design tokens, fonts, animations
│   ├── components/
│   │   ├── AnalysisDashboard.tsx  # Tabbed result viewer
│   │   ├── RadialScore.tsx        # SVG radial progress chart
│   │   ├── GapAnalysis.tsx        # Accordion gap report
│   │   ├── AtsResumeViewer.tsx    # Resume preview + download
│   │   ├── UploadForm.tsx         # Drag-drop PDF + JD textarea
│   │   ├── LoadingStepper.tsx     # Pipeline progress stepper
│   │   └── ErrorDisplay.tsx       # Structured error cards
│   ├── hooks/
│   │   └── useAnalysis.ts       # Core state machine hook
│   ├── lib/
│   │   ├── api-client.ts        # Typed XHR/fetch wrapper
│   │   └── utils.ts             # cn(), formatDate(), describeArc()…
│   ├── types/
│   │   └── api.ts               # TypeScript interfaces (mirrors schemas.py)
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   ├── Dockerfile
│   └── .env.local.example
│
├── docker-compose.yml
└── README.md
```

---

## Quick Start

### Prerequisites

- **Python** 3.12+
- **Node.js** 22+
- **PostgreSQL** 17 (or Docker)
- **Google Gemini API key** — [get one free at aistudio.google.com](https://aistudio.google.com/)

---

### Option A — Docker Compose (recommended)

```bash
# 1. Clone
git clone https://github.com/your-org/alignai.git
cd alignai

# 2. Configure backend
cp backend/.env.example backend/.env
# Edit backend/.env — add your GEMINI_API_KEY

# 3. Configure frontend
cp frontend/.env.local.example frontend/.env.local

# 4. Launch everything
docker compose up --build

# App: http://localhost:3000
# API docs: http://localhost:8000/docs
```

---

### Option B — Manual (development)

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Set DATABASE_URL and GEMINI_API_KEY in .env

# Run (tables auto-created on startup)
# go to alignai folder
cd .. 
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend

```bash
cd frontend

# Install
npm install

# Configure
cp .env.local.example .env.local

# Run
npm run dev
# → http://localhost:3000
```

#### PostgreSQL (local, no Docker)

```sql
CREATE USER alignai_user WITH PASSWORD 'your_password';
CREATE DATABASE alignai_db OWNER alignai_user;
GRANT ALL PRIVILEGES ON DATABASE alignai_db TO alignai_user;
```

Then set in `backend/.env`:
```
DATABASE_URL=postgresql+asyncpg://alignai_user:your_password@localhost:5432/alignai_db
```

---

## Environment Variables

### Backend (`backend/.env`)

| Variable                  | Required | Default         | Description                                                  |
|---------------------------|----------|-----------------|--------------------------------------------------------------|
| `DATABASE_URL`            | ✅        | —               | `postgresql+asyncpg://user:pass@host:5432/db`               |
| `GEMINI_API_KEY`          | ✅        | —               | Google AI Studio API key                                     |
| `ALLOWED_ORIGINS`         | —        | `http://localhost:3000` | Comma-separated CORS origins                        |
| `MAX_FILE_SIZE_MB`        | —        | `10`            | Maximum PDF upload size in MB                                |
| `MAX_RESUME_PAGES`        | —        | `50`            | Maximum pages in a PDF                                       |
| `MAX_JD_LENGTH`           | —        | `20000`         | Maximum characters in job description                        |
| `RATE_LIMIT_ANALYZE`      | —        | `10/minute`     | SlowAPI rate limit for `/analyze`                            |
| `RATE_LIMIT_HISTORY`      | —        | `30/minute`     | SlowAPI rate limit for `/history`                            |
| `SEMANTIC_WEIGHT`         | —        | `0.60`          | Weight for embedding cosine similarity in composite score    |
| `KEYWORD_WEIGHT`          | —        | `0.40`          | Weight for keyword overlap in composite score                |
| `GAP_ANALYSIS_THRESHOLD`  | —        | `85.0`          | Scores below this trigger Gemini gap analysis                |
| `ENVIRONMENT`             | —        | `development`   | `development` enables `/docs`, verbose errors                |
| `LOG_LEVEL`               | —        | `INFO`          | Python logging level                                         |

### Frontend (`frontend/.env.local`)

| Variable                       | Required | Default                   | Description                           |
|--------------------------------|----------|---------------------------|---------------------------------------|
| `NEXT_PUBLIC_API_URL`          | —        | `http://localhost:8000`   | FastAPI backend base URL              |
| `NEXT_PUBLIC_MAX_FILE_SIZE_MB` | —        | `10`                      | Client-side file size validation      |
| `NEXT_PUBLIC_SHOW_HISTORY`     | —        | `true`                    | Feature flag for history panel        |

---

## API Contract

All endpoints return `Content-Type: application/json`. Errors always use the `ErrorResponse` envelope.

### Base URL
```
http://localhost:8000/api/v1
```

---

### `POST /api/v1/analyze`

Analyse a resume against a job description.

**Request** — `multipart/form-data`

| Field             | Type     | Required | Constraints                     |
|-------------------|----------|----------|---------------------------------|
| `resume`          | `File`   | ✅        | PDF only, max 10 MB             |
| `job_description` | `string` | ✅        | min 50 chars, max 20,000 chars  |

**Response** `200 OK`

```jsonc
{
  "id": 42,
  "filename": "john_doe_resume.pdf",
  "score_breakdown": {
    "semantic": 74.3,    // Cosine similarity × 100 (0–100)
    "keyword": 61.8,     // TF-weighted keyword overlap (0–100)
    "final": 69.3        // semantic×0.60 + keyword×0.40
  },
  "gap_analysis": {
    // null if final >= 85.0
    "missing_skills": [
      "Apache Kafka",
      "dbt (data build tool)",
      "OWASP Top 10",
      "Kubernetes Helm charts"
    ],
    "improvements": [
      "Quantify the scale of your microservices migration — add team size and latency improvements",
      "Add metrics to the authentication system: active users, uptime SLA achieved",
      "Include your Terraform experience in the Technical Skills section explicitly"
    ],
    "match_summary": "Strong Python and API development background, but the role requires deeper data pipeline and MLOps experience. Closing the Kafka and dbt gaps would significantly improve alignment."
  },
  "ats_resume": "# John Doe\njohn@example.com | ...\n\n## Professional Summary\n...",
  // null only if generation failed — client should handle
  "created_at": "2025-01-15T10:32:47.123456+00:00"
}
```

**Error Responses**

| Status | Code                   | Cause                                          |
|--------|------------------------|------------------------------------------------|
| `400`  | `EMPTY_FILE`           | Zero-byte file uploaded                        |
| `400`  | `FILE_TOO_LARGE`       | PDF exceeds `MAX_FILE_SIZE_MB`                 |
| `400`  | `CORRUPT_PDF`          | PyMuPDF cannot open the file                   |
| `400`  | `ENCRYPTED_PDF`        | Password-protected PDF                         |
| `400`  | `EMPTY_PDF`            | PDF has zero pages                             |
| `400`  | `TOO_MANY_PAGES`       | Exceeds `MAX_RESUME_PAGES`                     |
| `415`  | `INVALID_CONTENT_TYPE` | File is not a PDF (MIME check)                 |
| `415`  | `INVALID_FILE_TYPE`    | File lacks `%PDF` magic bytes                  |
| `422`  | `EMPTY_CONTENT`        | Text extraction returned < 100 chars           |
| `422`  | `PARSE_ERROR`          | Unexpected PyMuPDF error                       |
| `422`  | `JD_TOO_SHORT`         | `job_description` < 50 chars                   |
| `429`  | `RATE_LIMIT`           | Too many requests (default: 10/minute)         |
| `503`  | `EMBEDDING_ERROR`      | Gemini embedding API unavailable               |
| `503`  | `REASONING_ERROR`      | Gemini Flash API unavailable                   |
| `503`  | `RESUME_BUILD_ERROR`   | Resume generation failed                       |

**Error envelope**

```jsonc
{
  "detail": {
    "code": "FILE_TOO_LARGE",
    "message": "File exceeds the 10 MB limit.",
    "field": "resume"           // optional — present for field-level errors
  }
}
```

---

### `GET /api/v1/history`

Paginated list of past analyses.

**Query Parameters**

| Param       | Type    | Default | Range   |
|-------------|---------|---------|---------|
| `page`      | integer | `1`     | ≥ 1     |
| `page_size` | integer | `10`    | 1–50    |

**Response** `200 OK`

```jsonc
{
  "items": [
    {
      "id": 42,
      "filename": "john_doe_resume.pdf",
      "job_description_snippet": "We are looking for a Senior Backend Engineer...",
      "match_score": 69.3,
      "created_at": "2025-01-15T10:32:47.123456+00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

---

### `GET /api/v1/history/{id}`

Full record including `gap_analysis` and `ats_resume`.

**Response** `200 OK` — same shape as `POST /api/v1/analyze` response.

**Errors**

| Status | Code        | Cause             |
|--------|-------------|-------------------|
| `404`  | `NOT_FOUND` | ID does not exist |

---

### `DELETE /api/v1/history/{id}`

Delete a record permanently.

**Response** `204 No Content`

**Errors** — same as GET above.

---

### `GET /health`

Health probe for container orchestration.

```jsonc
{ "status": "ok", "version": "1.0.0" }
```

---

## Scoring Algorithm

### 1. Semantic Score (60% weight)

Uses cosine similarity on Google `text-embedding-004` vectors (768 dimensions).

```
semantic_score = dot(embed_resume, embed_jd) / (||embed_resume|| × ||embed_jd||) × 100
```

- Resume is embedded with `RETRIEVAL_DOCUMENT` task type
- JD is embedded with `RETRIEVAL_QUERY` task type
- Both calls are issued concurrently via `asyncio.gather()`

### 2. Keyword Score (40% weight)

TF-weighted unigram + bigram overlap:

```python
# Tokenise → filter stopwords → extract bigrams
# Score = sum(jd_token_frequency for matched tokens) / total_jd_token_weight × 100 × 1.25
```

- Bigrams capture compound skills: `"machine learning"`, `"full stack"`, `"cloud native"`
- TF weighting means high-frequency JD terms count more
- `×1.25` normalisation corrects for exact-match strictness vs. fuzzy methods
- Result capped at 100

### 3. Composite (Final) Score

```
final = (semantic × 0.60) + (keyword × 0.40)
```

Both weights are configurable via `SEMANTIC_WEIGHT` / `KEYWORD_WEIGHT` env vars.

### 4. Gap Analysis Threshold

If `final < 85.0`, `gemini-1.5-flash` is called with a structured prompt that returns:
- `missing_skills` — technical tools/frameworks in JD but absent from resume
- `improvements` — actionable resume enhancement suggestions  
- `match_summary` — 2-3 sentence plain-English assessment

The model is instructed to respond with `response_mime_type: "application/json"` and the response is defensively parsed with a regex fallback.

---

## Security

| Layer               | Implementation                                                                 |
|---------------------|--------------------------------------------------------------------------------|
| **CORS**            | Strict allowlist from `ALLOWED_ORIGINS` env var                               |
| **Trusted Host**    | `TrustedHostMiddleware` in production (derived from `ALLOWED_ORIGINS`)         |
| **File Validation** | MIME type check + `%PDF` magic bytes + page count + size limits               |
| **Rate Limiting**   | SlowAPI per-IP rate limits on all mutation endpoints                           |
| **SQL Injection**   | SQLAlchemy ORM with parameterised queries — no raw SQL                         |
| **Error Leakage**   | Stack traces never returned in production (`ENVIRONMENT != development`)       |
| **API Key**         | `GEMINI_API_KEY` never exposed to frontend; server-side only                  |
| **Security Headers**| `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` on all responses|
| **Input Limits**    | JD max 20,000 chars; resume text truncated to 40,000 chars before embedding   |
| **Type Safety**     | Pydantic v2 with `extra = "forbid"` on all schemas                            |

---

## Data Flow

```
Browser                    FastAPI Router              Services              External
───────                    ─────────────              ────────              ────────
  │                              │                       │                     │
  │── POST /analyze ────────────▶│                       │                     │
  │   (PDF + JD, FormData)       │                       │                     │
  │                              │── read_bytes() ──────▶│                     │
  │                              │                       │── PyMuPDF ──────────│
  │                              │                       │   (in-memory)       │
  │                              │                       │◀── resume_text ─────│
  │                              │                       │                     │
  │                              │── get_embeddings() ──▶│                     │
  │                              │                       │── embed(resume) ────▶ Gemini
  │                              │                       │── embed(jd) ────────▶ text-embedding-004
  │                              │                       │◀── [768-dim, 768-dim]│
  │                              │                       │                     │
  │                              │── calculate_score() ─▶│                     │
  │                              │                       │── cosine_sim()      │
  │                              │                       │── keyword_overlap()  │
  │                              │                       │◀── HybridScore      │
  │                              │                       │                     │
  │                              │── [if score < 85] ───▶│                     │
  │                              │   analyse_gap()       │── Flash prompt ─────▶ Gemini
  │                              │                       │◀── JSON response ───│  1.5-flash
  │                              │                       │── parse_gap() ──────│
  │                              │                       │◀── GapAnalysisReport│
  │                              │                       │                     │
  │                              │── build_ats_resume() ▶│── Flash prompt ─────▶ Gemini
  │                              │                       │◀── Markdown ────────│  1.5-flash
  │                              │                       │                     │
  │                              │── db.add(MatchHistory)│                     │
  │                              │── db.flush() ─────────────────────────────▶ PostgreSQL
  │                              │                       │                     │
  │◀── AnalysisResponse ─────────│                       │                     │
  │    (id, scores, gap,         │                       │                     │
  │     ats_resume, timestamp)   │                       │                     │
```

---

## Frontend Components

### `useAnalysis` Hook

Central state machine with these possible statuses:

```
idle → uploading → embedding → scoring → reasoning → building_resume → saving → success
                                                                              ↘ error
```

The hook uses `XMLHttpRequest` (not `fetch`) for the upload to get real `ProgressEvent` callbacks for the upload progress bar. Intermediate step simulation runs client-side while the single server request is in-flight.

### `RadialScore`

Pure SVG implementation — no charting library. Two concentric arcs:
- **Outer arc** (r=95): composite final score, coloured by tier
- **Inner arc** (r=68): semantic similarity score (indigo)

All arcs animate from 0 on mount using `requestAnimationFrame` with cubic ease-out.

### `GapAnalysis`

Custom accordion (no Radix dependency needed) with:
- `match_summary` — always open by default
- `missing_skills` — count badge, amber accent  
- `improvements` — emerald accent

### `AtsResumeViewer`

Toggle between **preview** (simplified Markdown→HTML rendering) and **raw** (monospace `<pre>`). Download buttons for `.md` (Markdown) and `.txt` (plain text) using `URL.createObjectURL`.

---

## Development Guide

### Type Safety

The TypeScript types in `types/api.ts` are the single source of truth for the frontend and must be kept in sync with `schemas.py`. Key rules:

1. Any field added to a Pydantic model → add to the corresponding TS interface
2. Use `readonly` arrays and properties on all API response types
3. Use the provided type guards (`isApiError`, `hasGapAnalysis`, `hasAtsResume`) before accessing nullable fields
4. Never cast `as AnalysisResponse` without first validating shape

### Adding a New Endpoint

1. Create/extend a router in `backend/routers/`
2. Add Pydantic request/response schemas to `schemas.py`
3. Mirror the response type in `frontend/types/api.ts`
4. Add a typed function to `frontend/lib/api-client.ts`
5. Update this README's API Contract section

### Changing Scoring Weights

Edit `backend/.env`:
```
SEMANTIC_WEIGHT=0.70
KEYWORD_WEIGHT=0.30
```
Must sum to `1.0`. No code changes needed.

### Adding a New Gemini Model

Update `_REASONING_MODEL` or `_EMBEDDING_MODEL` constants in `services/ai_service.py`. Note that changing the embedding model dimension (768 for `text-embedding-004`) requires database migration if you're storing vectors.

---

## Deployment

### Production Checklist

- [ ] Set `ENVIRONMENT=production` to disable `/docs`, `/redoc`, `/openapi.json`
- [ ] Set `ALLOWED_ORIGINS` to your production frontend URL only
- [ ] Use a secrets manager (AWS Secrets Manager, GCP Secret Manager) for `GEMINI_API_KEY`
- [ ] Configure PostgreSQL with connection pooling (PgBouncer recommended for high traffic)
- [ ] Set up HTTPS (Nginx + Let's Encrypt or a cloud load balancer)
- [ ] Configure log aggregation (Cloud Logging, Datadog, etc.)
- [ ] Set `MAX_FILE_SIZE_MB` appropriately for your user base
- [ ] Add database backup strategy for `match_history`

### Recommended Production Stack

```
Cloudflare (CDN/WAF)
       ↓
Nginx (reverse proxy + TLS termination)
   ↙        ↘
Next.js    FastAPI (Gunicorn + Uvicorn workers)
             ↓
          PostgreSQL (RDS / Cloud SQL)
             ↓
          Google Gemini API
```

---

## Troubleshooting

### `EMPTY_CONTENT` error on valid PDF

The PDF is likely scanned (image-only). PyMuPDF can only extract embedded text, not OCR images. Solutions:
- Ask candidates to provide a text-based PDF export from Word/Google Docs
- Add Tesseract OCR as an optional fallback (not included by default to keep dependencies lean)

### Gemini API quota errors

`text-embedding-004` and `gemini-1.5-flash` have free-tier rate limits. If you hit them:
- The `503` error responses will retry gracefully in the UI
- Consider caching embeddings for identical resume text using a hash key
- Upgrade to a paid Gemini tier for production traffic

### Database connection pool exhausted

Increase `pool_size` and `max_overflow` in `database.py`, or add PgBouncer in front of PostgreSQL.

### CORS errors in the browser

Ensure `ALLOWED_ORIGINS` in `backend/.env` exactly matches the frontend origin including protocol and port (e.g., `http://localhost:3000`, not `localhost:3000`).

### Score seems too low / too high

Tune `SEMANTIC_WEIGHT` and `KEYWORD_WEIGHT`. A domain where keyword matching matters more (e.g., compliance roles) might benefit from `0.50/0.50`. Creative/research roles where semantic alignment matters more can go `0.70/0.30`.

---

## License

MIT © AlignAI Contributors
