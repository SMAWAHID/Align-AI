"""
Vercel serverless entrypoint for the AlignAI API.

Vercel's Python runtime looks for an ASGI application named `app` here and
routes every request to it via vercel.json.
"""
import sys
from pathlib import Path

# backend/main.py uses package-relative imports (`from .config import ...`), so
# the REPO ROOT goes on sys.path and the app is imported as `backend.main`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import app  # noqa: E402,F401  (re-exported for the runtime)
