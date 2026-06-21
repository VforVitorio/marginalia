"""FastAPI app: mount the API routers and serve the built frontend in production.

Dev: Vite serves the UI on :5173 and proxies ``/api`` here. Prod/daily: ``frontend/dist`` is served
from this same process, so the whole app is one URL (docs/ARCHITECTURE.md §8).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from marginalia.api import jobs, providers

app = FastAPI(title="marginalia")
app.include_router(providers.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")

_FRONTEND_DIST = Path("frontend/dist")
if _FRONTEND_DIST.is_dir():  # present only after `npm run build`; in dev Vite owns the UI
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="spa")
