#!/usr/bin/env pwsh
# One command: install deps, build the UI, and serve everything on
# http://localhost:8000. For daily use after the first build, `uv run marginalia`.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "==> Syncing Python dependencies (uv)"
uv sync

Write-Host "==> Building the frontend"
Push-Location frontend
npm ci
npm run build
Pop-Location

Write-Host "==> Starting marginalia on http://localhost:8000"
uv run marginalia
