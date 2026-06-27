# marginalia installer (Windows, PowerShell).
# Installs everything needed and starts the app — no Node required for end users.
#   irm https://raw.githubusercontent.com/VforVitorio/marginalia/main/scripts/install.ps1 | iex
#
# It: installs uv (which manages Python) -> gets the source -> downloads the
# prebuilt frontend from the latest release -> installs deps -> launches on :8000.
$ErrorActionPreference = "Stop"

$repo = "https://github.com/VforVitorio/marginalia.git"
$distUrl = "https://github.com/VforVitorio/marginalia/releases/latest/download/frontend-dist.zip"
$dir = if ($env:MARGINALIA_DIR) { $env:MARGINALIA_DIR } else { "$HOME\marginalia" }
function Say($m) { Write-Host "==> $m" -ForegroundColor DarkYellow }

# 1. uv (also brings a managed Python via `uv sync`)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Say "Installing uv"
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
  $env:Path = "$HOME\.local\bin;$env:Path"
}

# 2. Source: use the current checkout if we're in one, else clone/update $dir
if ((Test-Path pyproject.toml) -and (Select-String -Quiet -Path pyproject.toml -Pattern 'name = "marginalia"')) {
  $dir = (Get-Location).Path
} elseif (Test-Path "$dir\.git") {
  Say "Updating existing install in $dir"; git -C $dir pull --ff-only
} else {
  Say "Cloning marginalia into $dir"; git clone --depth 1 $repo $dir
}
Set-Location $dir

# 3. Config + prebuilt frontend (skip the Node build for end users)
if (-not (Test-Path providers.toml)) { Copy-Item providers.example.toml providers.toml }
if (-not (Test-Path frontend\dist)) {
  Say "Downloading the prebuilt frontend"
  New-Item -ItemType Directory -Force frontend | Out-Null
  Invoke-WebRequest $distUrl -OutFile "$env:TEMP\marginalia-dist.zip"
  Expand-Archive "$env:TEMP\marginalia-dist.zip" frontend -Force
}

# 4. Python deps + launch (opens the browser shortly after the server is up)
Say "Installing dependencies (uv manages Python)"
uv sync
Say "Starting marginalia on http://localhost:8000"
Start-Job { Start-Sleep 3; Start-Process "http://localhost:8000" } | Out-Null
uv run marginalia
