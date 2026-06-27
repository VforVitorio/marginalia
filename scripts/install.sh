#!/usr/bin/env bash
# marginalia installer (macOS / Linux).
# Installs everything needed and starts the app — no Node required for end users.
#   curl -fsSL https://raw.githubusercontent.com/VforVitorio/marginalia/main/scripts/install.sh | bash
#
# It: installs uv (which manages Python) → gets the source → downloads the
# prebuilt frontend from the latest release → installs deps → launches on :8000.
set -euo pipefail

REPO="https://github.com/VforVitorio/marginalia.git"
DIST_URL="https://github.com/VforVitorio/marginalia/releases/latest/download/frontend-dist.zip"
DIR="${MARGINALIA_DIR:-$HOME/marginalia}"

say() { printf "\033[1;38;5;173m==>\033[0m %s\n" "$1"; }

# 1. uv (also brings a managed Python via `uv sync`)
if ! command -v uv >/dev/null 2>&1; then
  say "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Source: use the current checkout if we're in one, else clone/update DIR
if [ -f pyproject.toml ] && grep -q 'name = "marginalia"' pyproject.toml 2>/dev/null; then
  DIR="$PWD"
elif [ -d "$DIR/.git" ]; then
  say "Updating existing install in $DIR"; git -C "$DIR" pull --ff-only || true
else
  say "Cloning marginalia into $DIR"; git clone --depth 1 "$REPO" "$DIR"
fi
cd "$DIR"

# 3. Config + prebuilt frontend (skip the Node build for end users)
[ -f providers.toml ] || cp providers.example.toml providers.toml
if [ ! -d frontend/dist ]; then
  say "Downloading the prebuilt frontend"
  curl -fsSL "$DIST_URL" -o /tmp/marginalia-dist.zip
  mkdir -p frontend && (cd frontend && unzip -oq /tmp/marginalia-dist.zip)
fi

# 4. Python deps + launch (opens the browser shortly after the server is up)
say "Installing dependencies (uv manages Python)"
uv sync
say "Starting marginalia on http://localhost:8000"
( sleep 3 && { xdg-open http://localhost:8000 || open http://localhost:8000; } >/dev/null 2>&1 & )
uv run marginalia
