# marginalia — Claude Code Context

Source of truth for working in this repo. It supersedes any older convention found in commits or docs.
Follow the global rules:
- [[clean-code]] (`~/.claude/CLEAN_CODE.md`) — coding style.
- [[project-bootstrap]] (`~/.claude/PROJECT_BOOTSTRAP.md`) — GitHub, CI, security stack.
- [[token-savers]] (`~/.claude/TOKEN_SAVERS.md`) — RTK and token-saving tools.

Language: **everything in this repo is English** — code, identifiers, comments, docstrings, docs, UI text, commit messages, PRs. No exceptions.

Project-specific deltas are below.

---

## 1. Vision

marginalia transforms handwritten Kindle Scribe notebooks (PDF) into Markdown notes in Obsidian.
It combines ingest (synced folder or drag & drop) + OCR (local Qwen3-VL via Ollama/LM Studio, or cloud
Claude/Gemini) + a human image↔markdown review + an export that preserves the source folder hierarchy.
End-state: a local, all-in-one app, everything by buttons, zero terminal for daily use.

## 2. Tech stack

| Concern | Tool |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Validation | Pydantic v2 |
| Package manager | uv |
| Linter/formatter | Ruff (line-length 120) |
| Types | mypy (`backend/marginalia`) |
| Tests | pytest + pytest-asyncio |
| PDF → image | PyMuPDF (fitz) |
| Local OCR | Qwen3-VL via Ollama / LM Studio (OpenAI-compatible API) |
| Cloud OCR | Claude (`claude-agent-sdk`, subscription) · Gemini (OpenAI-compatible endpoint, free tier) |
| Export templates | Jinja2 |
| Frontend | Vite + React + TypeScript + Tailwind + GSAP |
| Streaming | SSE (FastAPI native `StreamingResponse`) |

## 3. Structure

```
backend/marginalia/{config,models_admin}.py
backend/marginalia/{ingest,ocr,jobs,structure,export,api}/
frontend/src/{steps,components,api,lib}/
docs/ARCHITECTURE.md   # decisions + data flow + full tree
```

The full tree with each module's responsibility is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 4. Git workflow

- **Trunk-based**: `main` is the only long-lived branch. Feature branches (`feat/`, `fix/`, `docs/`) come off main and PR back to main. No dev branch.
- **No squash**: release-please needs the individual commit history.
- **Conventional Commits**: imperative, English, and **no AI attribution** (hard rule — no `Co-Authored-By`, no "Generated with").
- CI must be green (`test` / `lint` / `typecheck` / `frontend-build`) before any merge. If CI fails on main, fix it; never `enforce_admins`.

## 5. Commands

Backend (from the repo root):
```bash
uv sync                                              # install deps
uv run uvicorn marginalia.api.main:app --reload      # dev API (:8000)
uv run pytest -q                                      # tests
uvx ruff check . && uvx ruff format --check .         # lint + format
uv run mypy backend/marginalia                        # types
```

Frontend (from `frontend/`):
```bash
npm ci
npm run dev          # :5173, proxy /api → :8000
npm run build        # → frontend/dist (FastAPI serves it in prod)
npm run lint && npm run typecheck
```

## 6. API ↔ frontend contract

- **Dev**: Vite `:5173` proxies `/api` → FastAPI `:8000`. **Prod/daily**: FastAPI serves `frontend/dist` + the API on `:8000` (one process, one URL).
- **Versioning**: `/api` prefix. **Errors**: `{ "detail": "..." }` with the right HTTP status.
- **Live OCR**: SSE at `GET /api/jobs/{id}/stream`. Events: `page_started`, `page_delta`, `page_done`, `job_done`, `error`.
- **Auth**: none (single-user local app). Claude's auth state is exposed as **data** (connected / not), not a login.
- **Contract types**: `frontend/src/api/client.ts` defines TypeScript interfaces (`Settings`, `ProviderStatus`, `JobState`, `PageState`, ...) that are **hand-maintained mirrors** of `backend/marginalia/api/schemas.py`, field-for-field, including their wire-format `snake_case` names (`job_id`, `rel_path`, `vault_path`, ...). This is a deliberate choice — no `openapi-typescript` codegen pipeline — so it only works if both sides move together: **when a Pydantic schema field is added, renamed, or retyped, update the matching `client.ts` interface in the same PR.** The §7 "camelCase in the frontend" rule governs local app code (component state, props, function names); it does not apply to these wire-format field names, which must stay `snake_case` to match the JSON the backend actually sends.

## 7. Code quality

Apply [[clean-code]]. Repo-specific:
- **Thin routers**: no business logic in routes — it goes to the `service.py` files.
- **Hard boundaries**: OCR engines know nothing about FastAPI/jobs/vault; the `StructureMapper` is a pure function; `ingest` knows nothing about OCR or the vault. Don't cross those lines.
- Module / class / public-function docstrings (global rule). snake_case in the backend, camelCase in the frontend. All identifiers and prose in English.
- Mark deliberate simplifications with a `# ponytail: ...` comment naming the ceiling and the upgrade path.

## 8. Workflow rules

- **Long-running work (OCR, build, `ollama pull`) — never just wait**: fire it, do something else, check and act.
- **Fire and check, never block**: poll once → act → move on. When green, merge.

## 9. Tooling notes

- uv only (no direct `pip`). `data/` and `providers.toml` are gitignored; `providers.example.toml` **is** committed.
- Local models: the app talks to Ollama (`:11434`) and LM Studio (`:1234`) over HTTP; it does **not** assume models are installed — it lists them from the runtime and allows `pull` via a button.
- UI screenshots: `frontend/scripts/shot.mjs` (Playwright) — see [[FRONTEND_VISUAL_VERIFICATION]].
- To touch `AgentSDKEngine` / subscription auth, consult the `claude-api` skill.

## 10. Recommended skills

| Skill | When |
|---|---|
| `frontend-design` + ui-skills.com | any visual decision (Import/Review/Export) |
| `refactor-fastapi` | backend cleanup (Pydantic v2, async I/O, DI) |
| `claude-api` | touching `AgentSDKEngine` / subscription auth |
| `code-review` → `simplify` | on every diff |
| `run` / `verify` | drive the app and confirm OCR→review→export |

## 11. Lessons learned

<!-- add new entries above this line -->

## 12. Related documents

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — architecture decisions, data flow, full tree.
- [README.md](README.md) — user-facing pitch.
- [BACKLOG.md](BACKLOG.md) — out-of-MVP ideas, parked.
- `providers.example.toml` — provider configuration template.
- `scripts/setup-github.sh` — applies branch protection + labels.
