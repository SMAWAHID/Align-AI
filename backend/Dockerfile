FROM python:3.12-slim

WORKDIR /app

# System deps for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app in as a PACKAGE named `backend` — main.py uses relative imports
# (`from .config import ...`), which only resolve when it is imported as
# `backend.main`, never as a top-level `main`.
COPY . ./backend/

EXPOSE 8000
# Shell form so ${PORT} expands; hosts like Render assign the port at runtime.
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
