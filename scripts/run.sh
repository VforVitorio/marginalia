#!/usr/bin/env bash
# One command: install deps, build the UI, and serve everything on
# http://localhost:8000. For daily use after the first build, `uv run marginalia`.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Syncing Python dependencies (uv)"
uv sync

echo "==> Building the frontend"
( cd frontend && npm ci && npm run build )

echo "==> Starting marginalia on http://localhost:8000"
uv run marginalia
