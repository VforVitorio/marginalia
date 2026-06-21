# marginalia — Architecture

Architecture decisions, data flow, and module boundaries. For each decision: what is chosen, what is
rejected, and why. Working conventions live in [CLAUDE.md](../CLAUDE.md); the MVP scope and what's parked,
in [BACKLOG.md](../BACKLOG.md).

## 0. Summary

A **local** Kindle Scribe → Obsidian pipeline. Four stages: **ingest** (PDF from a synced folder or drag &
drop) → **OCR** (local Qwen3-VL, or cloud Claude/Gemini, streamed per page) → human **review** (image ↔
markdown) → **export** to the vault, preserving the source folder hierarchy. Everything by buttons; the
user never touches a terminal or edits config for daily use.

## 1. Data flow

```
                        synced folder ────────┐
                          (scan on demand)     │
                                               ▼
  drag & drop PDF ─────────────────────►  ingest/pdf.py ──► [Notebook: pages as PNG]
                                                                   │
                                                                   ▼
                                              jobs/service.py  (orchestrator)
                                                   │  per page:
                                                   │     ocr/<engine>.transcribe_page(png, prompt)
                                                   │     → stream text → persist page_n.md
                                                   ▼
                                          SSE: page_started/page_delta/page_done/job_done
                                                   │
                                                   ▼
                                       frontend Review (image ↔ markdown, editable)
                                                   │  PUT /api/jobs/{id}/pages/{n}
                                                   ▼
                                       export/service.py ──► structure/mapper.py
                                                   │            (mirror + wikilinks)
                                                   ▼
                                          Obsidian vault (.md with frontmatter)
```

A job's **live state** is its on-disk directory (`data/jobs/{id}/`): `job.json` + `page_n.png` +
`page_n.md`. There is no database (see §6).

## 2. Seam 1 — `OCREngine` (interchangeable OCR backends)

A `Protocol` with a single work method that **streams** a page's text:

```python
class OCREngine(Protocol):
    info: EngineInfo                       # id, display_name, kind=local|cloud, current_model
    def models(self) -> list[str]: ...     # models available on this backend
    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]: ...
```

The engine takes **one image and a prompt** and returns **text chunks**. It knows nothing about jobs,
SSE, the vault, or FastAPI. That ignorance is the boundary that makes it testable and swappable.

**Implementations:**

- **`OpenAICompatEngine`** — one adapter parameterized by `base_url` + `api_key` + `model`, speaking the
  OpenAI-compatible *chat completions* API (`POST {base_url}/chat/completions`, image as a data URL in a
  vision message, `stream=true`, delta parsing). The three backends differ only in those three params:
  - Ollama → `http://localhost:11434/v1`
  - LM Studio → `http://localhost:1234/v1`
  - Gemini → `https://generativelanguage.googleapis.com/v1beta/openai/` + the free-tier API key.
- **`AgentSDKEngine`** — Claude via `claude-agent-sdk`, authenticated by the Claude Code session
  (subscription, **no API key**). Behind the same `OCREngine`.

**Rejected:** a `transcribe_notebook(pdf)` method (puts rendering + orchestration + persistence inside the
engine → untestable and coupled). A non-streaming method (breaks live review). A client per provider
(triples the surface for a difference that is a URL). Claude over a paid API key (the brief wants the
subscription).

## 3. Seam 2 — `StructureMapper` (Scribe → Obsidian hierarchy)

A pure function `(notebooks, strategies, vault_root) -> list[ExportedNote]`. Strategies are **combinable**;
in the MVP `mirror` (always) + `wikilinks` (toggle):

- **`mirror`**: dest = `vault / <source relative path> / <notebook>.md`. One notebook = one note; pages are
  `## Page N` sections.
- **`wikilinks`**: also generates/updates a per-folder index note (`<folder>.md`) with one `[[notebook]]`
  per notebook in it. This materializes the structure as links, which is Obsidian's value.

**Where the hierarchy comes from:** the **source folder tree** (the synced folder), not from inside a PDF —
a Scribe export is a flat PDF per notebook. For a loose drag & drop there is no folder context → the user
picks a destination folder (or the vault root) in the export dialog. The mapper works on **file paths**,
not on PDF contents.

**Rejected:** all 4 strategies at once (the brief forbids it in the MVP; `tags`/`dataview` stay in the
backlog behind the same contract). One note per page (multiplies files, breaks the "one notebook = one
note" mental unit).

## 4. FastAPI backend + streaming

Per-page OCR is emitted over **SSE** from `GET /api/jobs/{id}/stream`, using a native `StreamingResponse`
(`text/event-stream`). Events: `page_started`, `page_delta`, `page_done`, `job_done`, `error`. Each page is
**persisted on completion**, so a dropped connection resumes from disk.

**SSE not WebSocket:** the flow is one-way server→client; SSE is simpler, auto-reconnects, and rides plain
HTTP. **Native `StreamingResponse` not `sse-starlette`:** it covers the case in ~10 lines; add
`sse-starlette` only if heartbeats/reconnect fall short.

## 5. Frontend — one interface, one flow

A SPA with a single `Import → Review → Export` flow. GSAP for the step transitions. Provider/model
selection and model management (incl. `ollama pull`) in a header panel, all by buttons. No nested routes,
no scattered panels. **Rejected:** a multi-page router (the product is linear).

## 6. Persistence — on-disk workspace, no database

Each job is `data/jobs/{id}/` with `job.json` (state, pages, paths) + `page_n.png` + `page_n.md`. The live
settings (vault path, active provider/model, strategies) live in `data/settings.json`, written by the UI.

**No DB:** the MVP is a short, single-user, local process; files survive restarts, are inspectable, and
`job.json` is trivial. SQLite would be infrastructure for cross-job queries the MVP doesn't make.
**Rejected:** SQLite/Postgres (YAGNI), in-memory-only state (lost on a restart mid-review).

## 7. Configuration

`providers.toml` (gitignored; `providers.example.toml` committed) = **provider catalogue + secrets**
(base_urls, Gemini API key). `data/settings.json` = **day-to-day choices** the UI sets (vault path, active
provider/model, strategies). This honors "the user never edits config for daily use": `providers.toml` is
seed/credentials, not touched to use the app.

## 8. Serving model

- **Dev:** Vite `:5173`, proxy `/api` → FastAPI `:8000`.
- **Daily/prod:** FastAPI serves `frontend/dist` **and** the API on `:8000` (one process, one URL).

## 9. Ingest — scan on demand (MVP)

A "Scan folder" button lists the PDFs in the configured folder (recursive, preserving relative path) +
drag & drop of loose PDFs. **No background watcher** in the MVP: live watching adds threading/debounce/
background state for a flow where the import is triggered by hand anyway. The background watcher is in
[BACKLOG.md](../BACKLOG.md).

## 10. File tree (responsibility per module)

```
backend/marginalia/
├── config.py            # load providers.toml + data/settings.json → Settings (Pydantic v2)
├── ingest/
│   ├── pdf.py           # PyMuPDF: PDF → per-page PNGs; Notebook/Page models
│   └── scan.py          # list PDFs under the root folder, preserving relative path
├── ocr/
│   ├── engine.py        # OCREngine Protocol + EngineInfo dataclass  (SEAM)
│   ├── openai_compat.py # OpenAICompatEngine (Ollama / LM Studio / Gemini)
│   ├── agent_sdk.py     # AgentSDKEngine (Claude via subscription)
│   ├── registry.py      # build the active engine from settings; list providers
│   └── prompts.py       # handwriting-OCR prompt(s)
├── models_admin.py      # list/pull/load models via the Ollama & LM Studio HTTP APIs
├── jobs/
│   ├── store.py         # on-disk workspace: job.json, PNGs, MDs  (single source of state)
│   └── service.py       # orchestrate ingest→OCR per page; emit SSE events; persist
├── structure/
│   ├── mapper.py        # StructureMapper: (notebooks, strategies, vault) → ExportedNote[]
│   └── strategies.py    # mirror, wikilinks (combinable)
├── export/
│   ├── service.py       # render with Jinja2 + write to the vault
│   └── templates/note.md.j2
└── api/
    ├── main.py          # FastAPI app; mount routers; serve frontend/dist in prod
    ├── deps.py          # DI: get_settings, get_engine, get_job_store
    ├── jobs.py          # POST /jobs, GET /jobs/{id}/stream (SSE), PUT pages, POST export
    ├── providers.py     # GET/POST providers; model-admin endpoints
    └── schemas.py       # Pydantic request/response models
```

**Boundaries (what each must NOT know):**
- `ocr/` knows nothing about jobs, SSE, the vault, or FastAPI. Image → text.
- `structure/` knows nothing about OCR, HTTP, or engines. Pure function.
- `ingest/` knows nothing about OCR or the vault. PDF → images / list of paths.
- `jobs/service.py` is the **only** place wiring ingest + ocr + persistence and emitting SSE.
- `export/` only knows `structure/` + vault writing + Jinja2.
- `api/` is thin: routers delegate, no business logic.
- `frontend/` talks only to `/api`.

## 11. Risks and mitigations

1. **Claude subscription auth (Agent SDK)** — a hard requirement (cloud "both guaranteed"). Outside the
   authenticated Claude Code environment there is no API key and calls fail. *Mitigation:* the backend
   probes auth at startup and exposes the state in the UI; the `OCREngine` seam lets Gemini/local cover the
   job; develop inside the authenticated environment. If auth won't cooperate, flag it before calling
   cloud-Claude done.
2. **Handwriting OCR quality** — hard handwriting or small local models transcribe poorly. *Mitigation:*
   the review UI is the safety net (edit before export) + a per-page "re-OCR in the cloud" button + a tuned
   prompt + high-DPI rendering.
3. **8 GB VRAM / local model availability** — the Qwen3-VL tag may not exist on Ollama or may not fit.
   *Mitigation:* verify the real tag at scaffold time; default to the 2B/4B that fits; LM Studio as an
   alternate runtime; cloud as a fallback; list whatever the runtime reports (`/api/tags`), don't hardcode.
4. **SSE drop on long pages** — the connection drops mid-OCR. *Mitigation:* persist each page on completion
   (resume from disk) + a periodic heartbeat.
