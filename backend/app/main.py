"""ExplainMyCode API.

Run from backend/:  uv run --env-file .env uvicorn app.main:app --reload
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.visualize import router as visualize_router

app = FastAPI(title="ExplainMyCode")

# The browser only lets the frontend call this API from an origin listed here.
# Defaults to the Next.js dev server; set CORS_ORIGINS (comma-separated) for a deploy.
origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

app.include_router(visualize_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
