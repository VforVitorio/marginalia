"""Console entry point for the marginalia server.

Serves the API and the built frontend (``frontend/dist``) on one local URL.
Run after the UI is built (``npm run build`` in ``frontend/``) — or just use
``scripts/run.sh`` / ``scripts/run.ps1``, which build it for you.

--- WHERE TO CHANGE IF HOST/PORT CHANGES ---
The Vite dev proxy (``frontend/vite.config.ts``) and the README both assume
:8000 — keep them in sync.
"""

from __future__ import annotations

import uvicorn

HOST = "127.0.0.1"
PORT = 8000


def main() -> None:
    """Launch the Uvicorn server hosting the API + the built SPA."""
    uvicorn.run("marginalia.api.main:app", host=HOST, port=PORT)


if __name__ == "__main__":
    main()
