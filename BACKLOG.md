# BACKLOG

Ideas outside the MVP. Golden rule from the brief: when in doubt about adding a feature, **don't** — note
it here and move on. None of this is built without being asked for explicitly.

## Out of the MVP by the brief's decision
- Multi-device support (reMarkable, Boox, Apple/Samsung Notes).
- All 4 mapping strategies at once. The MVP ships `mirror` + `wikilinks`; `tags` and `dataview` go behind
  the same `StructureMapper` contract (adding one = one more function in `structure/strategies.py`).
- Accounts/users, login, multi-tenant.
- Model fine-tuning, distributed queues, mass batch.

## MVP simplifications to revisit
- **Background folder watcher** — the MVP uses scan-on-demand (a button). Live watching adds
  threading/debounce/background state. Upgrade path: a watcher thread (e.g. `watchfiles`) when the flow needs it.
- **Hand-rolled SSE (`StreamingResponse`)** — add `sse-starlette` only if heartbeats/reconnect fall short.
- **On-disk workspace, no DB** — SQLite if listing/querying many jobs is needed.
- **One note per notebook** (pages as sections) — split page-per-note if asked.

## Deferred infra (Phase 2, "once there's shippable code")
- Local `pre-commit` (ruff) — for now we rely on CI.

## Product roadmap (post-MVP)
- Process multiple notebooks at once (batch).
- Custom export templates.
- Full-text search across exports.
- Scheduled pull from Google Drive.
- **Ingest Kindle `myClippings.txt`** (highlights/clippings → Markdown). Far future — Kindle makes
  getting the file out a pain; only worth it if the demand shows up.
- **Position against / complement the Scribe's native "Convert to text"** (2026 firmware 5.18.x+,
  regular Scribe + Colorsoft). The native feature emails a flat `.txt`; marginalia's edge is
  Obsidian folder-mirroring + wikilinks + Markdown (KaTeX/tables/callouts) + a human review loop,
  fully local. Possible feature: a fast path that ingests the Scribe's *own* converted text when present.
- **Non-dev packaging / one-click launch.** Current launch is dev-shaped (FastAPI + Vite). Before a broad
  push to the Obsidian / Kindle Scribe communities (non-developers), ship a packaged installer or a
  single-command/single-binary start. Biggest adoption barrier for the non-dev audience.
