# Deploying AlignAI for free

Three free accounts, no credit card: **Neon** (Postgres) → **Render** (API) →
**Vercel** (frontend). Budget about 25 minutes. Do the steps in order — each
produces a value the next one needs.

| Piece | Host | Free tier limits |
|---|---|---|
| Postgres | [Neon](https://neon.tech) | 0.5 GB storage, no expiry |
| FastAPI API | [Render](https://render.com) | 750 instance-hours/month, sleeps after 15 min idle |
| Next.js frontend | [Vercel](https://vercel.com) | 100 GB bandwidth/month, always on |
| Embeddings + LLM | [Jina](https://jina.ai/embeddings) + [Groq](https://console.groq.com/keys) | 1M tokens/month · generous rate limits |

---

## 0. AI provider keys (do this first — both are free)

AlignAI runs on Gemini **or** a free Jina + Groq fallback. For a zero-cost deploy,
get the two free keys and leave `GEMINI_API_KEY` empty:

- **Jina** (embeddings) — <https://jina.ai/embeddings> → *Get API Key*. 1M tokens/month, no card.
- **Groq** (gap analysis LLM) — <https://console.groq.com/keys>. Free, no card.

With `AI_PROVIDER=auto` and no Gemini key, the app uses these automatically.

---

## 1. Database — Neon

1. Sign up at **neon.tech** with GitHub.
2. **Create project** → name it `alignai` → nearest region.
3. Copy the **Connection string**:

   ```
   postgresql://neondb_owner:npg_xxxx@ep-cool-bird-12345.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

   Paste it **exactly as Neon gives it**. `backend/database.py` rewrites the driver
   prefix to `postgresql+asyncpg://` and strips the libpq-only parameters itself.

> No migration step. The API calls `init_db()` on startup, which creates every
> table via SQLAlchemy metadata.

---

## 2. API — Render

1. Sign up at **render.com** with GitHub.
2. **New → Blueprint** → select the `Align-AI` repo → **Connect**.
   Render reads [`render.yaml`](render.yaml) and pre-fills everything but the secrets.
3. Fill in the values marked *sync: false*:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Neon string from step 1 |
   | `ALLOWED_ORIGINS` | `http://localhost:3000` for now — fixed in step 4 |
   | `JINA_API_KEY` | your Jina key |
   | `GROQ_API_KEY` | your Groq key |
   | `GEMINI_API_KEY` | leave **empty** to stay on the free path |

4. **Apply**. First build takes 4–6 minutes (PyMuPDF and numpy are large).
5. You get a URL like `https://alignai-api.onrender.com`. Verify **`/health`**
   returns `{"status":"ok"}` and **`/docs`** renders.

---

## 3. Frontend — Vercel

1. Sign up at **vercel.com** with GitHub.
2. **Add New → Project** → import `Align-AI`.
3. Set **Root Directory** to `frontend`. Vercel detects Next.js on its own.
4. Add the environment variable:

   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | your Render URL, e.g. `https://alignai-api.onrender.com` — **no trailing slash** |

   This one variable drives all three transports: REST calls, the WebSocket URL
   (`https://` → `wss://` automatically), and the wake-up probe. It is read at
   **build** time, so changing it later requires a redeploy, not just a restart.
5. **Deploy** → you get `https://align-ai.vercel.app` or similar.

---

## 4. Point the API back at the frontend

1. Render → `alignai-api` → **Environment**.
2. Set `ALLOWED_ORIGINS` to your Vercel URL, no trailing slash:

   ```
   https://align-ai.vercel.app
   ```

   Comma-separate to allow several.
3. Optionally tighten `ALLOWED_HOSTS` from `*` to your API hostname:
   `alignai-api.onrender.com`. Whatever you put there **must** include the API's
   own hostname or every request — including Render's health check — returns
   *400 Invalid host header*.
4. **Save changes** — Render redeploys (~3 min).

---

## What to expect from the free tier

**The API sleeps after 15 minutes of inactivity.** The first request afterwards
waits roughly 50 seconds for the container to restart. The frontend handles this
honestly: `useServerWakeup` pings `/health` as the page loads and the banner says
"Waking the server up" rather than leaving a dead spinner.

Render's free tier allows **750 instance-hours per month across the whole
account**, so keeping this API awake around the clock would spend the entire
monthly budget on one service.

**Analysis runs over a WebSocket** straight to Render, bypassing Vercel's proxy —
which matters, because a proxied request would hit Vercel's edge timeout while the
dyno wakes. If the socket fails, the client falls back to `POST /api/v1/analyze`.

**Neon suspends an idle database** after 5 minutes and resumes on the next query.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Every request returns *400 Invalid host header* | `ALLOWED_HOSTS` doesn't include the API's own hostname. Set it to `*` and re-narrow later. |
| Browser console: *blocked by CORS policy* | `ALLOWED_ORIGINS` doesn't exactly match the Vercel URL — no trailing slash, `https://` not `http://`. |
| WebSocket fails, analysis still works but without live steps | `NEXT_PUBLIC_API_URL` is `http://` (yields `ws://` on an HTTPS page, which browsers block) or is unset in the Vercel build. |
| *TypeError: connect() got an unexpected keyword argument 'sslmode'* | An older build without the DSN normaliser in `backend/database.py`. Redeploy from `main`. |
| *ModuleNotFoundError: No module named 'config'* | The API was started as `main:app`. It uses package-relative imports and must run as `backend.main:app` from the repo root. |
| Analysis returns an AI provider error | `JINA_API_KEY` / `GROQ_API_KEY` missing while `GEMINI_API_KEY` is also empty. |
