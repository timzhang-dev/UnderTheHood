"""Vercel serverless entry point.

Vercel's Python runtime discovers functions under `api/`, so the FastAPI app has
to be re-exported from here; `app/main.py` stays the single definition and is
what `uvicorn app.main:app` still runs locally.

Filesystem routing would map this file to `/api` alone, and look for
`api/visualize.py` to serve `/api/visualize`. vercel.json rewrites every path
here instead, and Vercel preserves the original path, so FastAPI's own router
matches `/api/visualize` and `/api/health` as it does locally.
"""

from app.main import app

__all__ = ["app"]
