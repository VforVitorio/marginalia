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
- **Hand-rolled SSE (`StreamingResponse`)** — a heartbeat was added in v1.2.0 (#142); still hand-rolled.
  Add `sse-starlette` only if reconnect handling falls short.
- **On-disk workspace, no DB** — `list_jobs()` / `delete()` added in v1.2.0 (#143); still file-based.
  SQLite if querying many jobs is ever needed.
- **One note per notebook** (pages as sections) — split page-per-note if asked.

## Deferred infra (Phase 2, "once there's shippable code")
- Local `pre-commit` (ruff) — for now we rely on CI.

## Product roadmap (post-MVP)
- Process multiple notebooks at once (batch). The OCR runner was decoupled from the request in v1.2.0
  (#147), so this is now unblocked — what's left is the multi-select / queue UI.
- Custom export templates.
- Full-text search across exports.
- Scheduled pull from Google Drive.
- **Ingest Kindle `myClippings.txt`** (highlights/clippings → Markdown). Far future — Kindle makes
  getting the file out a pain; only worth it if the demand shows up.
- **Position against / complement the Scribe's native "Convert to text"** (2026 firmware 5.18.x+,
  regular Scribe + Colorsoft). The native feature emails a flat `.txt`; marginalia's edge is
  Obsidian folder-mirroring + wikilinks + Markdown (KaTeX/tables/callouts) + a human review loop,
  fully local. Possible feature: a fast path that ingests the Scribe's *own* converted text when present.
- **Non-dev packaging.** ✅ The one-command installer shipped (v1.2.0): `scripts/install.sh` / `install.ps1`
  (uv-based) + the `frontend-dist.zip` release asset — `curl | bash` / `irm | iex`, no Node needed. Still
  open: a true double-click packaged build (`.exe` / `.dmg` / AppImage) for total non-devs — would need a
  PyInstaller/Briefcase pipeline.

## Domain feature ideas (handwriting → Obsidian workflow, noted 2026-07-07)
Not built — noted per the golden rule. These come from the workflow's three truths: OCR of handwriting
has errors, sketches get lost, and the scan is the ground truth. Liked by the user; candidates for the
future features-planning session.

Top picks (differentiate from a plain `.txt`; cheap→medium, no big refactor):
- **Embed the source page image in the exported note** — write `![[page_n.png]]` beside the transcription
  (Obsidian attachment). For handwriting the scan IS the source of truth; keeps provenance so you can
  always check the Markdown against your own writing. The PNG is already on disk. Cheapest, strongest.
- **Low-confidence flagging in the review loop** — the model marks uncertain words/regions so review
  jumps to likely errors instead of re-reading everything. Feasibility depends on model confidence
  signal; approximate with a second "mark what's uncertain" pass on Claude/Qwen.
- **Custom vocabulary / glossary injected into the OCR prompt** — the user's names, jargon, course terms
  (per vault or per notebook). Biggest accuracy lever for the least effort (prompt injection, no fine-tune).

Second tier:
- **YAML frontmatter with provenance + date** — source notebook/Scribe folder, OCR model, extracted date →
  exports become queryable in Dataview and sortable (journaling/lecture use). Complements the planned
  `dataview` strategy. Date can often come from PDF metadata (below) instead of OCR.
- **Re-OCR a single page with another model** — recover one bad page with the cloud model without redoing
  the whole notebook. Reuses the decoupled runner (#147).
- **Re-import = update, not duplicate** — the Scribe notebook is a living document; re-exporting an edited
  notebook should update/merge the existing note, not create `Notes 2.md`. Related to the wikilinks
  overwrite fix (#137).
- **Non-text regions: Mermaid for diagrams, user's choice for freeform drawings** — structured
  diagrams/flowcharts/trees/tables always recreated as **Mermaid / Markdown tables / callouts**
  (editable, Obsidian-native, never an image crop). For freeform sketches the model can't faithfully
  emulate, detect them and **ask the user how to handle drawings** ("drawings detected — recreate or
  embed as an image crop?"), so they decide per notebook; default/fallback is an embedded `![[fig_n.png]]`
  crop. More ambitious; the thing a `.txt` can never do.

## Signal in the Scribe PDF (verified against a real export, 2026-07-07)
Scanned a real 11-page Scribe export (`S07.1-2026-07-07-17-01.pdf`) with PyMuPDF. Findings — some the
opposite of what was assumed:
- **PDF metadata is EMPTY.** `doc.metadata` title/author/creator/producer/**creationDate/modDate** all `''`.
  There is NO date/title to harvest from the PDF itself — the "date from metadata" idea is dead for this
  export style.
- **The filename is the real signal.** `S07.1-2026-07-07-17-01.pdf` = `<name>-<YYYY-MM-DD-HH-MM>.pdf`, i.e.
  notebook title + export date/time. Parse the filename for `created:` + a clean title (verify the pattern
  is the Scribe's, not just this user's naming, before relying on it).
- **The "text layer" is just page-number footers** ("1 de 11", ~7 chars/page), NOT a transcription. So a
  `get_text()`-non-empty check is a false positive for native convert-to-text — it must exclude the
  `N de M` footer. This export did not use native convert; it's pure handwriting (1 image per page).
- **Minor (quality, not speed):** each page is one embedded grayscale image at 1860×2480 px, while our
  200-DPI `get_pixmap` renders 1654×2339 — we downscale ~11% and re-encode. Feeding the OCR the native
  image (or simply raising the render DPI to ~230) gives a sharper input. OCR dominates wall-clock, so this
  changes nothing about throughput. Prefer a DPI bump over `get_images` (which adds colorspace / multi-image
  / mask handling for a marginal gain).
