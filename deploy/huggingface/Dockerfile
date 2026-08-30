# AlignAI API — Hugging Face Spaces (Docker SDK, free CPU tier)
#
# Assembled into a Space repo by deploy/huggingface/sync.sh, which copies this
# file and README.md to the Space root alongside backend/.
FROM python:3.12-slim

# Spaces runs the container as UID 1000, not root. Creating that user at build
# time keeps file ownership and $HOME consistent with the runtime — otherwise
# the app starts with no writable home and pip's console scripts are not on PATH.
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER user
WORKDIR $HOME/app

COPY --chown=user:user backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r backend/requirements.txt

COPY --chown=user:user backend/ ./backend/

# Spaces publishes the port declared as `app_port` in README.md.
EXPOSE 7860

# backend/main.py uses package-relative imports (`from .config import ...`), so
# it only resolves as `backend.main:app` — never as a top-level `main:app`.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
