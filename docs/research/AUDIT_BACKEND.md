# Backend Audit: Where marginalia's Backend Can Get Better

**Status: read-only audit report, 2026-07-07. Analysis only, no code changed.**
**Scope: everything under `backend/marginalia/` (v1.1.3, `main`, clean tree).**

marginalia's backend is small (~1,600 lines of source, 10 test files / 59 tests), deliberately
simple, and — with one glaring exception — correct. The architecture documented in
`docs/ARCHITECTURE.md` is genuinely reflected in the code: the `OCREngine` seam is clean, the
`StructureMapper` is pure, ingest knows nothing about OCR or the vault, and routers are thin-ish.
This audit found **1 P0 (a shipped feature calls an endpoint that does not exist), 6 P1s
(stream-lifecycle correctness, invisible pull failures, blocking I/O in an async route, a
data-losing index overwrite, a lying cloud status), and a tail of P2/P3 hardening** — most of it
concentrated exactly where Víctor suspected: model loading and failure states.

Every claim below is verified against the current code and cited as `file:line`.

---

## 1. Framing — what the backend is today

One FastAPI process (`backend/marginalia/api/main.py:16-23`) serving 18 routes under `/api`
(6 job routes, 10 provider/settings routes, 2 path-suggestion routes) plus the built SPA as
static files. Four stages, four module groups:

| Stage | Modules | State |
|---|---|---|
| Ingest | `ingest/pdf.py`, `ingest/scan.py` | PyMuPDF render is clean; **`scan_pdfs` is orphaned — no route calls it** (§3 BE-01) |
| OCR | `ocr/engine.py` (Protocol), `ocr/openai_compat.py`, `ocr/agent_sdk.py`, `ocr/registry.py`, `ocr/prompts.py` | Seam is honored; timeout/error handling is thin (§4) |
| Model admin | `models_admin.py`, `lms_bridge.py`, `claude_auth.py` | LM Studio bridge is the strongest module in the repo; Ollama pull and cloud probes have real gaps (§4) |
| Jobs + review + export | `jobs/store.py`, `jobs/service.py`, `structure/`, `export/service.py`, `api/` | Pure mapper, on-disk store; stream lifecycle has 3 correctness holes (§3 BE-02/03/06) |

Persistence is files only: `data/jobs/{uuid4hex}/job.json` + `page_N.png`
(`backend/marginalia/jobs/store.py:49-110`), `data/settings.json` + `providers.toml`
(`backend/marginalia/config.py:18-20`). No DB, no background tasks, no scheduler — OCR runs
*inside* the SSE request (`backend/marginalia/api/jobs.py:62-69`). That last fact is the single
biggest architectural constraint on the future-features list (§5).

**Boundary verdict (CLAUDE.md §7 hard rules):**

- *OCR engines know nothing about FastAPI/jobs/vault* — **holds.** `openai_compat.py` imports only
  httpx + prompts; `agent_sdk.py` only the SDK + prompts; neither references jobs, SSE, or paths.
- *`StructureMapper` is a pure function* — **holds.** `structure/strategies.py` has zero I/O
  imports; `structure/mapper.py:22-28` is pure composition.
- *Ingest knows nothing about OCR or the vault* — **holds.** `ingest/pdf.py` and `ingest/scan.py`
  import only PyMuPDF/stdlib.
- *Thin routers* — **mostly holds, two mild deviations**: a 33-line provider-state machine lives in
  the router module (`backend/marginalia/api/providers.py:84-116`) and notebook/note-source shaping
  lives in `backend/marginalia/api/jobs.py:100-144`. They are module-level helpers, not inline route
  bodies, so this is a style deviation rather than a violation (§3 BE-23).

---

## 2. Current state per subsystem

### 2.1 OCR + model loading

**Engine construction.** `registry.build_engine` (`backend/marginalia/ocr/registry.py:16-36`) maps
`id == "claude"` to `AgentSDKEngine` and everything else to `OpenAICompatEngine`, guarding missing
`base_url`/model with `ValueError`. Two wrinkles:

- Unknown `active_provider` **silently falls back to the first catalogue entry**
  (`backend/marginalia/ocr/registry.py:52-55`, marked `# ponytail`). If `settings.json` names a
  provider that was removed from `providers.toml`, the user OCRs with whatever is first — no
  warning anywhere.
- The Claude fallback model `"claude-sonnet-4-6"` is hardcoded (`registry.py:23`), duplicating
  `providers.example.toml:32`.

**The OpenAI-compat adapter** (`backend/marginalia/ocr/openai_compat.py`) is exactly what the
architecture doc promises: one class, three params, no per-provider branches. Fragilities:

- `timeout: float = 120.0` (`openai_compat.py:36`) is a *single* httpx timeout: it is also the
  **connect** timeout. Against a firewalled/blackholed host, the job hangs ~120 s before erroring.
  httpx's granular `Timeout(connect=…, read=…)` exists for exactly this.
- `resp.raise_for_status()` on the stream (`openai_compat.py:65`) throws `httpx.HTTPStatusError`
  without the response body — the runtime's actual error ("model not found", "invalid API key")
  never reaches the caller; `run_ocr` turns it into one generic message (§2.3).
- `models()` (`openai_compat.py:43-51`) duplicates `models_admin.runtime_status` (same GET
  `/models`, different timeout: 10 s vs 4 s) and **is never called by application code** — a grep
  for `.models()` finds only test fakes. Dead protocol surface.

**The Agent SDK engine** (`backend/marginalia/ocr/agent_sdk.py:36-54`) writes the page PNG to a
temp dir and has Claude `Read` it (`allowed_tools=["Read"]`, `permission_mode="bypassPermissions"`,
`max_turns=3`). No timeout of any kind: if the SDK subprocess hangs, the page — and thus the job —
hangs forever, and the only escape is killing the server.

**Model admin** splits by runtime:

- **Ollama**: `runtime_status` (`backend/marginalia/models_admin.py:21-41`) does a real GET
  `/models` with a 4 s timeout, catching `httpx.HTTPError` → `(False, [])`. Honest.
  `pull_model` (`models_admin.py:103-118`) streams `POST /api/pull` with **`timeout=None`**
  (`models_admin.py:107`) and — critically — **reads only `status`/`total`/`completed` from each
  JSON line, never `data.get("error")`** (`models_admin.py:111-118`). Ollama reports pull failures
  ("pull model manifest: file does not exist") as `{"error": …}` lines inside the stream; those
  are dropped on the floor, and the stream just ends.
- **LM Studio**: the strongest chain in the repo. TCP pre-check (`lms_bridge.py:48-54`, 0.5 s),
  two-path headless start with socket re-probe (`lms_bridge.py:57-80`), `lms load` with a 120 s
  budget (`lms_bridge.py:83-98`), lenient JSON parsing that skips the "Waking up…" preamble
  (`lms_bridge.py:181-189`), graceful-fail everywhere, and 8 dedicated tests
  (`backend/tests/test_lms_bridge.py`). The ROADMAP §Sprint-4 spec was implemented faithfully.
- **Gemini (cloud)**: status is **presence of a key, not validity**
  (`backend/marginalia/api/providers.py:106-110`) — `state="ready"` the moment a non-placeholder
  key exists, without ever probing. A wrong key shows a green dot and fails at OCR time with the
  generic error.
- **Claude**: file/env presence probe (`backend/marginalia/claude_auth.py:25-52`), honestly
  documented as presence-not-validity. Caveat: it checks only *files*
  (`claude_auth.py:32-40`); on macOS, Claude Code stores subscription credentials in the Keychain,
  so an authenticated macOS user likely reads as "not signed in" (false negative).

### 2.2 Pipeline: ingest → structure → export

- **`render_pdf`** (`backend/marginalia/ingest/pdf.py:35-44`) rasterizes *every* page to PNG bytes
  in memory before returning; `load_notebook` (`pdf.py:47-55`) additionally reads the whole PDF
  into memory. Fine for 10–50-page notebooks; a 300-page scan at 200 DPI is hundreds of MB of RAM
  in one request.
- **`scan_pdfs`** (`backend/marginalia/ingest/scan.py:21-30`) is correct (recursive,
  case-insensitive, sorted, missing root → `[]`) — and unreachable from the API (§3 BE-01).
- **`structure/`** is exemplary: pure, deterministic, well-tested (12 tests,
  `backend/tests/test_mapper.py`), with documented collision guards and ordering rationale
  (`backend/marginalia/structure/strategies.py:96-139`). Adding `tags`/`dataview` really is "one
  more function here" as BACKLOG.md claims.
- **`export/service.py`** guards path traversal (`export/service.py:56-58`, tested at
  `backend/tests/test_export.py:38-46`) but **unconditionally overwrites** every destination file
  (`export/service.py:60`) — including wikilinks *index* notes that were built only from the
  notes in *this* export call. Since the API exports one job at a time
  (`backend/marginalia/api/jobs.py:94`, `export_notes([source], …)`), exporting notebook B into a
  folder that already holds A's index **rewrites `<folder>.md` with only `[[B]]`, erasing
  `[[A]]`** (§3 BE-06). ARCHITECTURE.md:81 says index notes are "generated/updated"; the "update"
  half is not implemented.

### 2.3 API, jobs, SSE

- **Job store** (`backend/marginalia/jobs/store.py`): uuid4-hex job ids regex-validated before
  touching the filesystem (`store.py:22-27`, tested) — a real path-traversal guard. Writes are
  non-atomic `write_text` (`store.py:109-110`) with a candid `# ponytail` note about the
  load-modify-write race (`store.py:92-94`). There is **no `list`, no `delete`, no cleanup**:
  `data/jobs/` grows forever (each job = full-page PNGs; tens of MB per notebook).
- **The orchestrator** (`backend/marginalia/jobs/service.py:19-48`) is 30 lines and wires exactly
  what it should. Three lifecycle holes, all stemming from "OCR runs inside the SSE request"
  (`api/jobs.py:69`):
  1. **Stop/disconnect leaves the job stuck `running`.** The frontend Stop button closes the
     `EventSource` (`frontend/src/lib/sse.ts:51`, `frontend/src/steps/Review.tsx:56`); Starlette
     then cancels the generator, raising `GeneratorExit`/`CancelledError` at the current `yield` —
     which the `except Exception` at `jobs/service.py:44` **does not catch** (both derive from
     `BaseException`). No `finally` resets the status set at `service.py:31`.
  2. **Re-streaming re-OCRs finished pages.** `run_ocr` loops `record.pages` unconditionally
     (`service.py:33`) — no `if page.done: continue`. ARCHITECTURE.md:96 claims "a dropped
     connection resumes from disk"; persistence exists, resumption does not. Every reconnect
     re-spends OCR time/tokens on completed pages.
  3. **Nothing stops two concurrent streams of the same job** — two `run_ocr` instances race
     the same non-atomic `job.json`.
- **`create_job` blocks the event loop.** The route is `async def`
  (`backend/marginalia/api/jobs.py:35-44`) and synchronously calls `render_pdf(data)`
  (`jobs.py:105`) or `load_notebook(...)` (`jobs.py:114`) — whole-notebook CPU-bound
  rasterization — plus `store.create` writing all PNGs (`jobs.py:43`). While it runs, **every
  in-flight SSE stream freezes** (same event loop). This is the exact anti-pattern the repo's own
  `refactor-fastapi` skill exists to catch.
- **SSE framing** (`backend/marginalia/api/sse.py:13-16`) is 4 lines: `data:` + JSON. No
  heartbeat — despite ARCHITECTURE.md:190-191 listing "a periodic heartbeat" as the mitigation for
  risk 4 — no `event:`/`id:` fields, no `Cache-Control: no-cache` header. Locally this mostly
  works; the silent window during a cold model load or a slow Claude turn is where it bites.
- **Error contract** is honored (`{"detail": …}` with correct statuses throughout `api/`), and
  `_load_or_404` correctly maps both missing jobs and malicious ids to 404
  (`api/jobs.py:161-165` — note Pydantic's `ValidationError` subclasses `ValueError`, so a
  *corrupt* `job.json` also surfaces as "Job not found", which is misleading but not a 500).
- **Everything is CWD-relative**: `data/`, `providers.toml` (`config.py:18-20`), `frontend/dist`
  (`api/main.py:21-23`). `scripts/run.sh:5` `cd`s to the repo root, so the happy path works; run
  `uv run marginalia` from anywhere else and you get an empty provider catalogue, a fresh `data/`
  in the wrong place, and no SPA — silently.

---

## 3. Improvement opportunities

Legend: **P0** blocker · **P1** high · **P2** medium · **P3** nice-to-have. Effort: S (≤half day),
M (1–2 days), L (3+ days). "FF" = which §5 future feature the item unblocks or touches.

### P0 — a shipped feature is broken

#### BE-01 · `GET /api/scan` does not exist — the Scan-folder flow 404s end-to-end
**P0 · S · `frontend/src/api/client.ts:254-256` ↔ backend route inventory · FF: batch, watcher**

The Import step's Scan button calls `scanFolder()` → `apiFetch("/scan")` → `GET /api/scan`
(`frontend/src/steps/Import.tsx:83-94`, `frontend/src/api/client.ts:254-256`), expecting
`{ pdfs: [{ rel_path, name }] }` (`client.ts:56-63`). The backend registers **no such route** —
the full route inventory is: 6 in `api/jobs.py`, 10 in `api/providers.py`, 2 in `api/paths.py`,
and `api/main.py:17-19` mounts exactly those three routers. `ingest/scan.py::scan_pdfs` is fully
implemented and tested (`backend/tests/test_ingest.py:28-37`) but imported by **no API module** —
it is dead code from the product's perspective. Clicking Scan surfaces "Not Found" via the
`ApiError` path (`client.ts:134-142`); the entire synced-folder ingest (and with it the folder
hierarchy that `mirror`/`wikilinks` exist to preserve) is only reachable via `rel_path` job
creation, which the UI can never invoke because it can't list PDFs first.

**Fix (thin, matches conventions):** a `GET /scan` route in `api/jobs.py` (or a tiny `api/scan.py`)
that reuses the existing `_scan_root()` guard (`api/jobs.py:118-122`) and delegates:

```python
@router.get("/scan")
def scan(root: Path = Depends(_scan_root_dep)) -> ScanOut:
    refs = scan_pdfs(root)
    return ScanOut(pdfs=[ScannedPdfOut(rel_path=r.rel_path, name=Path(r.rel_path).stem) for r in refs])
```

plus `ScanOut`/`ScannedPdfOut` in `api/schemas.py` and an API test. Also worth a `Lección
aprendida` in CLAUDE.md §11: an E2E test (ROADMAP #9, still open) would have caught a
frontend-calls-missing-endpoint gap that 59 unit tests cannot.

### P1 — correctness of the core flow

#### BE-02 · Stop/disconnect leaves the job stuck in `running`
**P1 · S · `backend/marginalia/jobs/service.py:31,44` · FF: batch**

`except Exception` (`service.py:44`) doesn't catch `CancelledError`/`GeneratorExit`, and there is
no `finally`, so the `running` status written at `service.py:31` is never rolled back when the
client stops or drops. Symptoms: reopening the job shows `status: "running"` with nothing running;
the "gate export on OCR error" logic upstream reasons about a stale state.

**Fix (simple, keep the current architecture):** catch the cancellation explicitly and restore a
truthful status, then re-raise:

```python
except (asyncio.CancelledError, GeneratorExit):
    store.set_status(job_id, "pending")   # or a new "stopped" literal
    raise
```

**Bigger alternative** (only if/when batch lands): decouple OCR execution from the SSE request —
`asyncio.create_task` per job + an in-memory event queue the SSE route subscribes to. That makes
Stop an explicit `POST /jobs/{id}/stop` instead of a connection drop, and is the architectural
prerequisite for batch (§5 F1). Don't do it just to fix this bug — the 3-line except is enough.

#### BE-03 · Reconnecting re-OCRs pages that are already done
**P1 · S · `backend/marginalia/jobs/service.py:33` · FF: batch**

`for page in record.pages:` has no done-skip, so ARCHITECTURE.md:96's "resumes from disk" is
half-true: pages *persist*, but a re-stream (after Stop, a drop, or a browser refresh) restarts
OCR from page 1, re-spending local GPU time or cloud tokens on completed pages.

**Fix:** guard clause at the top of the loop — `if page.done: yield {"type": "page_done", "index":
page.index}; continue` (replaying `page_done` keeps the frontend's progress model consistent), and
skip `set_status("running")`→loop entirely when all pages are done (yield `job_done` immediately).
Add a test: run `run_ocr` twice with a counting fake engine, assert the second run makes zero
engine calls.

#### BE-04 · Failed Ollama pulls look like successful pulls
**P1 · S · `backend/marginalia/models_admin.py:107,111-118` · FF: model management (Víctor #1)**

Three stacked problems in `pull_model`:
1. Ollama's in-stream `{"error": "…"}` lines are silently dropped — the loop reads only
   `status`/`total`/`completed` (`models_admin.py:118`), so "manifest not found" (typo'd model
   name — the most common user error) produces a stream that just… ends.
2. Mid-stream HTTP failures (`resp.raise_for_status()` at `models_admin.py:110`, or a dead Ollama)
   raise *inside* the SSE generator **after the 200 was already sent** — the client sees a
   truncated stream, never an error event.
3. The frontend compounds it: `pullModel` drains the body and resolves unconditionally
   (`frontend/src/api/client.ts:231-240` — "resolves when the pull finishes"), so all of the above
   reads as *success* in the UI.

**Fix (backend half):** in `pull_model`, forward error lines and catch transport errors at the
generator boundary:

```python
if "error" in data:
    yield {"status": "error", "error": data["error"], "percent": None}
    return
```

wrapped in `try/except httpx.HTTPError as exc: yield {"status": "error", "error": str(exc)…}`.
Give the client `timeout=httpx.Timeout(connect=5, read=60)` instead of `None`
(`models_admin.py:107`) — 60 s between *progress lines* is generous; `None` means a wedged Ollama
holds the request forever. (Frontend must then parse the stream for the error event — out of this
audit's scope but required to close the loop.)

#### BE-05 · Whole-PDF rasterization blocks the event loop inside an async route
**P1 · S · `backend/marginalia/api/jobs.py:42-43,105,114` · FF: batch**

`create_job` is `async def`; `render_pdf` (CPU-bound PyMuPDF over every page,
`ingest/pdf.py:35-44`), `load_notebook`, and `store.create` (writes every PNG,
`jobs/store.py:60-61`) all run synchronously on the event loop. Upload a 100-page notebook while
another job streams OCR and the SSE stream stalls for the full render.

**Fix:** `notebook = await asyncio.to_thread(render_pdf, data)` / `await
asyncio.to_thread(load_notebook, path, root=root)` and `record = await asyncio.to_thread(
store.create, notebook)`. Three call sites, no design change. (The sync `def` routes — export,
edit, status — are fine: FastAPI runs them in the threadpool.)

#### BE-06 · Wikilinks index overwrite erases previously exported links
**P1 · M · `backend/marginalia/export/service.py:60` + `structure/strategies.py:96-139` · FF: tags/dataview, batch**

The mapper builds index links only from the sources of *this* call, and the API exports **one job
per call** (`api/jobs.py:94`). Export A into `uni/`, then B into `uni/`: the second export rewrites
`uni/uni.md` with only `[[B]]` — A's link is gone. Real data loss for the primary multi-notebook
workflow (a synced folder of notebooks exported one by one), and it also clobbers any manual edits
the user made to an index note in Obsidian.

**Fix that keeps the mapper pure:** merging is I/O, so it belongs in the export service. In
`export_notes`, for plans with `links` (index plans), read the existing file if present, parse its
`- [[name]]` lines, union with the new links, and write the union (stable-sorted). ~15 lines plus
tests (`export twice, assert both links present`). Alternative (simpler but weaker): only write an
index file if it doesn't exist — avoids data loss but never picks up new notebooks; the merge is
worth the extra half-day. Content notes (`- source` plans) keep overwrite semantics — re-exporting
a notebook *should* replace its note (though see Open Question Q4).

#### BE-07 · Cloud providers report `ready` on key *presence*, not key *validity*
**P1 · S · `backend/marginalia/api/providers.py:106-110` · FF: model management (Víctor #1)**

For `kind == "cloud"` (Gemini), status is `ready` if the key is non-placeholder — no network probe,
no model list. A revoked/typo'd key shows green and dies at OCR time with the generic BE-15 message.
Meanwhile the plumbing to do it right already exists: `runtime_status`
(`models_admin.py:21-41`) sends `Authorization: Bearer <key>` and would return Gemini's real model
list from its OpenAI-compat `/models` endpoint (free, no tokens).

**Fix:** route configured cloud providers through the same `runtime_status` call the local branch
uses (`providers.py:111`), mapping failure to a new `invalid_key` state (extend the vocabulary
documented at `api/schemas.py:38`) with hint "Key rejected by the provider." Two branches collapse
into one; the status endpoint becomes honest for 3 of 4 providers (Claude stays presence-based —
see BE-25).

### P2 — hardening the flow

#### BE-08 · No SSE heartbeat (documented mitigation, not implemented)
**P2 · S · `backend/marginalia/api/sse.py:13-16` vs `docs/ARCHITECTURE.md:190-191`**

Long silent gaps are real: LM Studio warming a model on first request (up to ~2 min,
`models_admin.py:87-89`), Claude thinking before its first `TextBlock`. An idle proxy/browser can
kill the connection, and `EventSource` auto-reconnect currently *re-runs OCR* (BE-03 — fix that
first or heartbeat makes things worse by masking it). Fix: in `sse_stream`, race the next event
against a 15 s timer and emit `": ping\n\n"` comment frames on timeout (~10 lines,
`asyncio.wait_for` in a loop). Also add `Cache-Control: no-cache` to both `StreamingResponse`s
(`api/jobs.py:69`, `api/providers.py:158`). Only if this proves insufficient, reach for
`sse-starlette` (BACKLOG.md:16 already gates it this way).

#### BE-09 · One-number httpx timeouts: 120 s connect hangs and infinite pulls
**P2 · S · `backend/marginalia/ocr/openai_compat.py:36,57` + `models_admin.py:107`**

`httpx.AsyncClient(timeout=self._timeout)` makes 120 s the *connect* timeout too — an unreachable
non-localhost `base_url` (LAN Ollama box, VPN'd runtime) blocks a page for 2 minutes before the
error event. Fix: `httpx.Timeout(connect=5.0, read=self._timeout, write=30.0, pool=10.0)`. Read
timeout applies *between chunks* on a stream, so 120 s still tolerates slow token generation while
bounding a totally silent stall. Same treatment for `pull_model` (covered in BE-04) and consider
5 s connect for `models()`/`runtime_status` (already short at 4 s/10 s total —
`models_admin.py:18`, `openai_compat.py:46`).

#### BE-10 · No per-page OCR timeout — a hung engine hangs the job forever
**P2 · S · `backend/marginalia/jobs/service.py:37-39` (and `ocr/agent_sdk.py:50-54`)**

`AgentSDKEngine` has no timeout at all; `OpenAICompatEngine` only httpx's. The right place for a
page-level ceiling is the orchestrator — engine-agnostic, keeps the boundary intact:

```python
async with asyncio.timeout(PAGE_TIMEOUT_S):   # e.g. 600
    async for chunk in engine.transcribe_page(image, prompt):
        ...
```

`TimeoutError` then flows into the existing error handler (improved by BE-15). One constant, one
`async with`, one test with a never-yielding fake engine.

#### BE-11 · Everything is CWD-relative — `marginalia` run elsewhere silently misbehaves
**P2 · S · `backend/marginalia/config.py:18-20`, `api/main.py:21`**

`Path("data")`, `Path("providers.toml")`, `Path("frontend/dist")` all resolve against the process
CWD. `scripts/run.sh:5` masks this; the installed console script (`pyproject.toml:19`) does not —
run it from `~` and you get an empty catalogue + a stray `~/data/`. Fix without over-engineering:
one `MARGINALIA_HOME` env var (default: CWD) resolved once in `config.py`, with the three path
constants derived from it, and a startup log line stating the resolved home. The installer scripts
set it. (Full `platformdirs` treatment is the over-engineered version — not needed for a
run-from-checkout app.)

#### BE-12 · Non-atomic JSON writes can corrupt `settings.json` / `job.json`
**P2 · S · `backend/marginalia/config.py:77`, `jobs/store.py:109-110`**

A crash/power-cut mid-`write_text` leaves truncated JSON. Corrupt `job.json` → misleading 404
("Job not found", `api/jobs.py:161-165`); corrupt `settings.json` → **unhandled `ValidationError`
→ 500 on every endpoint that loads settings** (`config.py:71`), bricking the app until the user
hand-deletes a file they were promised never to touch. Fix: a shared 4-line
`write_text_atomic(path, text)` (temp file in the same dir + `os.replace`) used by both writers;
plus `load_settings` catching `ValidationError`/`json` errors → log + return `Settings()` defaults
(losing preferences beats bricking).

#### BE-13 · Jobs are immortal: no list, no delete, no cleanup
**P2 · M · `backend/marginalia/jobs/store.py` (absent methods), route inventory · FF: batch, search**

`data/jobs/` accumulates full-resolution PNGs forever; there is also no way to rediscover a job
after a browser refresh (the id lives only in frontend memory). Fix: `JobStore.list_jobs()`
(iterate dirs, load records — fine without a DB at this scale) + `GET /jobs` +
`DELETE /jobs/{id}` (+ `shutil.rmtree` of the validated dir) and optionally a startup sweep for
`done` jobs older than N days. This is also the first hard prerequisite for batch (§5 F1) and the
"reopen last session" UX. SQLite stays unnecessary exactly as BACKLOG.md:17 predicts — until
full-text search (§5 F4) wants FTS5 anyway.

#### BE-14 · Nothing prevents two concurrent OCR streams of the same job
**P2 · S · `backend/marginalia/api/jobs.py:62-69`, `jobs/store.py:92-94`**

Two tabs (or an EventSource auto-reconnect racing a manual restart) run `run_ocr` twice on the same
job: interleaved SSE, racing load-modify-write on `job.json` (the `# ponytail` comment at
`store.py:92-94` names this exact upgrade). Simplest honest fix at the current scale: reject with
409 in `stream_job` when `record.status == "running"` (after BE-02, `running` is trustworthy
again). A per-job `asyncio.Lock` dict in `deps.py` is the next rung if 409 proves annoying.

#### BE-15 · One generic OCR error message for every failure class
**P2 · S · `backend/marginalia/jobs/service.py:44-48` · FF: model management (Víctor #1)**

"OCR failed — check the selected provider and model" is what a user sees for: runtime down, model
not loaded, invalid API key, model name typo, timeout, SDK not authenticated. The distinctions are
already in the exception types — map them without leaking internals:

| Exception | Message |
|---|---|
| `httpx.ConnectError` / `ConnectTimeout` | "Can't reach the OCR runtime — is it running?" |
| `httpx.HTTPStatusError` 401/403 | "The provider rejected the API key." |
| `httpx.HTTPStatusError` 404 | "The selected model isn't available on the runtime." |
| `TimeoutError` (BE-10) | "Page timed out — the model may be loading; try again." |
| anything else | current generic message |

~15 lines in `run_ocr` (a small `_error_message(exc)` helper), keeping the single log-and-yield
shape. Pairs with a **preflight**: before the page loop, the *route* (which already owns
settings/providers — the orchestrator shouldn't) can call `models_admin.runtime_status` and return
an immediate, specific error event instead of failing on page 1 after a hang.

#### BE-16 · `/providers/status` probes providers sequentially
**P2 · S · `backend/marginalia/api/providers.py:75-81`**

The status endpoint the UI polls does N sequential blocking probes in one threadpool request. All
local runtimes down + non-localhost URLs = sum of timeouts (~4 s each, `models_admin.py:18`);
localhost's fast connection-refused usually saves it, which is why it feels fine today. Fix when
touching this file anyway: make the route `async def` and `asyncio.gather(*(asyncio.to_thread(
_provider_status, p, settings) for p in providers))`. Bounded worst case = slowest single probe.

#### BE-17 · LM Studio model load is a silent 3-minute POST
**P2 · M · `backend/marginalia/api/providers.py:161-175`, `lms_bridge.py:74-98` · FF: model management (Víctor #1)**

`POST /providers/{id}/load` correctly offloads to a thread (`providers.py:168`) but the client
then waits up to ~185 s (server start ≤65 s + load ≤120 s) with zero feedback, and `ensure_loaded`
returning `False` conflates "couldn't start the server" with "load failed" into one 502 blob
(`providers.py:170-174`). The ROADMAP's own Sprint-4 item 3 asked for a "loading→loaded indicator".
Fix: mirror the pull endpoint — an SSE variant streaming coarse stages (`starting_server` →
`loading` → `loaded`/`error`), each stage just bracketing the existing `lms_bridge` calls. The
bridge itself needs no changes. (Cheaper stopgap: split the two failure modes into distinct
messages by returning a reason enum from `ensure_loaded`.)

### P3 — hygiene, honesty, and dead surface

#### BE-18 · Unknown `active_provider` silently falls back to the first catalogue entry
**P3 · S · `backend/marginalia/ocr/registry.py:52-55`**

Raise `ValueError(f"Unknown provider '{active_id}'")` instead; `stream_job`'s dependency failure
becomes a clear 500→(better) 409 rather than OCR-with-the-wrong-engine. One test.

#### BE-19 · `ExportBody.strategies` is unvalidated free text `cast` to `Strategy`
**P3 · S · `backend/marginalia/api/schemas.py:113`, `api/jobs.py:92` · FF: tags/dataview**

`["wikilnks"]` (typo) silently exports mirror-only. Fix: `strategies:
list[Literal["mirror", "wikilinks"]]` in the schema — Pydantic then 422s garbage, and the `cast`
disappears. Do this *before* adding `tags`/`dataview` so the picker contract is enforced from day 1.

#### BE-20 · `OCREngine.models()` is dead protocol surface, duplicated in `models_admin`
**P3 · S · `backend/marginalia/ocr/engine.py:37-39`, `openai_compat.py:43-51`, `agent_sdk.py:32-34`**

No application code calls `.models()` (grep: only test fakes implement it); real listing goes
through `models_admin.runtime_status`. Two implementations of GET `/models` with different
timeouts is drift waiting to happen. Simplest fix per ponytail: delete `models()` from the
Protocol and both engines (+ fakes). Alternative (if you'd rather dedupe than delete): make
`models_admin.list_models` the only implementation and keep the Protocol lean anyway.

#### BE-21 · A local provider with no `base_url` reports reachable + ready
**P3 · S · `backend/marginalia/models_admin.py:28-29`**

The `not provider.base_url` early-return says `(True, [default_model])` — meant for Claude, but
Claude never reaches `runtime_status` (`providers.py:99-105` branches first). A misconfigured
*local* entry therefore shows a green "ready". Fix: return `(False, [])` unless
`provider.id == "claude"` — or better, drop the special case entirely since no current caller
needs it for Claude.

#### BE-22 · Claude auth probe is file-only — likely false negative on macOS (Keychain)
**P3 · S · `backend/marginalia/claude_auth.py:32-40`**

Claude Code on macOS stores subscription credentials in the Keychain, not
`~/.claude/.credentials.json`, so authenticated macOS users probably see "Sign in with `claude
login`". Presence≠validity is already documented (`claude_auth.py:8-11`); this is the other half.
Cheapest honest fix: also treat a resolvable `claude` CLI + existing `~/.claude/` directory as
"probably signed in", and keep the docstring's promise that the real answer arrives as an SSE error
at OCR time. The full fix remains ROADMAP #11's "cheap cached billed probe".

#### BE-23 · Business-y helpers living in router modules (thin-router deviation, mild)
**P3 · S · `backend/marginalia/api/providers.py:84-116`, `api/jobs.py:100-144`**

`_provider_status` is a 33-line provider-state machine; `_notebook_from_request`/`_note_source`
shape domain objects. CLAUDE.md §7 says logic goes to `service.py` files. These are module-level,
tested-through-the-API helpers — not inline route bodies — so this is the mildest possible
violation. If touched for BE-07/BE-16 anyway, move `_provider_status` next to its data source
(`models_admin.py` or a small `providers_service.py`); `_note_source` pairs naturally with
`structure/`. Not worth a dedicated PR on its own.

#### BE-24 · Whole-notebook-in-RAM ingest ceiling
**P3 · M · `backend/marginalia/ingest/pdf.py:35-44`, `api/jobs.py:102`**

`await file.read()` + all-pages-as-bytes caps notebook size by RAM. At Scribe scale (tens of
pages) this is a non-issue; documenting the ceiling with a `# ponytail:` marker is the honest
minimum. The real fix, if ever needed, changes the `store.create` contract to accept an iterator
of pages and write each PNG as it renders — do it only when someone actually hits it.

#### BE-25 · Missing tests for the riskiest seams
**P3 · M · `backend/tests/` (10 files, 59 tests)**

Current coverage is good where the code is pure (mapper: 12 tests; lms_bridge: 8) and absent where
the failures live: **zero tests for `models_admin`** (status mapping, pull progress, pull error
lines), none for stream cancellation/stuck-state (BE-02), none for re-stream resume (BE-03), none
for double-export index merge (BE-06), none for corrupt `settings.json` (BE-12). Each P1 fix above
should land with its test; this item is the reminder that the *test* is half the fix. An E2E smoke
(ROADMAP #9) guards the BE-01 class of bug permanently.

### Decision table — all items at a glance

| ID | Title | Prio | Effort | Anchor |
|---|---|---|---|---|
| BE-01 | Missing `GET /api/scan` — Scan-folder flow broken | P0 | S | `client.ts:254` / route inventory |
| BE-02 | Stop/disconnect leaves job stuck `running` | P1 | S | `jobs/service.py:44` |
| BE-03 | Re-stream re-OCRs completed pages | P1 | S | `jobs/service.py:33` |
| BE-04 | Ollama pull failures invisible end-to-end | P1 | S | `models_admin.py:111-118` |
| BE-05 | Blocking PDF render in async route | P1 | S | `api/jobs.py:105,114` |
| BE-06 | Wikilinks index overwrite erases links | P1 | M | `export/service.py:60` |
| BE-07 | Cloud `ready` without probing the key | P1 | S | `api/providers.py:106-110` |
| BE-08 | No SSE heartbeat | P2 | S | `api/sse.py:13-16` |
| BE-09 | Single-number httpx timeouts (connect=120 s) | P2 | S | `openai_compat.py:36` |
| BE-10 | No per-page OCR timeout | P2 | S | `jobs/service.py:37-39` |
| BE-11 | CWD-relative `data/`/`providers.toml`/dist | P2 | S | `config.py:18-20` |
| BE-12 | Non-atomic writes; corrupt settings = 500s | P2 | S | `config.py:77`, `store.py:109` |
| BE-13 | No job list/delete/cleanup — unbounded disk | P2 | M | `jobs/store.py` |
| BE-14 | Concurrent same-job streams unguarded | P2 | S | `api/jobs.py:62-69` |
| BE-15 | Generic OCR error for every failure class | P2 | S | `jobs/service.py:44-48` |
| BE-16 | Sequential provider status probes | P2 | S | `api/providers.py:75-81` |
| BE-17 | LM Studio load: 3-min silent POST | P2 | M | `api/providers.py:161-175` |
| BE-18 | Silent fallback to first provider | P3 | S | `ocr/registry.py:52-55` |
| BE-19 | Unvalidated `strategies` + `cast` | P3 | S | `api/schemas.py:113` |
| BE-20 | Dead `OCREngine.models()` duplication | P3 | S | `ocr/engine.py:37-39` |
| BE-21 | No-`base_url` local provider shows ready | P3 | S | `models_admin.py:28-29` |
| BE-22 | Claude probe misses macOS Keychain | P3 | S | `claude_auth.py:32-40` |
| BE-23 | State machine / shaping helpers in routers | P3 | S | `api/providers.py:84-116` |
| BE-24 | Whole-notebook-in-RAM ingest ceiling | P3 | M | `ingest/pdf.py:35-44` |
| BE-25 | Missing tests at the riskiest seams | P3 | M | `backend/tests/` |

---

## 4. Model-loading deep-dive (Víctor's priority)

### 4.1 What the status probe actually tells you today, per provider

| Provider | Probe | Honest? | Failure it CANNOT see |
|---|---|---|---|
| Ollama | GET `{base}/models`, 4 s (`models_admin.py:36`) | **Yes** — real distinction of down / up-no-model / ready | A model that exists but doesn't fit VRAM (fails at first inference) |
| LM Studio | 0.5 s TCP pre-check (`lms_bridge.py:48-54`) + GET `/models`; separate `lms ls` for downloaded-not-loaded (`models_admin.py:59-67`) | **Yes** — the best-covered provider | `lms` CLI absent → load features silently degrade to `False` (guard exists: `lms_bridge.py:43-45`) |
| Gemini | key non-placeholder check only (`providers.py:107-110`) | **No** — presence, not validity (BE-07) | Revoked/typo'd key, deprecated `default_model` (`providers.example.toml:25` pins `gemini-2.0-flash`, which can go stale) |
| Claude | env var / credential file presence (`claude_auth.py:25-29`) | **Half** — documented as presence-only | Expired token; macOS Keychain-stored login (BE-22) |

The design shape is right — a single `state` + `hint` vocabulary the UI renders
(`api/schemas.py:35-49`), a TCP pre-check to avoid hangs, graceful-fail subprocess bridge. The
work left is making the *cloud* half of the table as honest as the local half, and making the two
long-running operations (pull, load) report failure and progress truthfully.

### 4.2 The robustness gaps ranked, with the fix shape

1. **Pull errors are swallowed (BE-04)** — the #1 model-management bug because a *typo'd model
   name* is the most common real-world action, and today it reports success. Fix = forward
   Ollama's `error` lines + catch `httpx.HTTPError` inside the generator + bounded read timeout.
2. **Cloud key validity (BE-07)** — probe Gemini's `/models` with the key; it's the same call the
   local branch already makes, costs nothing, and returns the real model list as a bonus (today
   the Gemini picker only ever shows `default_model` — `providers.py:110`).
3. **Timeout shapes (BE-09)** — `connect=5` everywhere; keep long `read` budgets only where slow
   generation is legitimate (transcription stream, pull progress). This converts "hangs 2 min then
   generic error" into "fails in 5 s with a connect error the BE-15 mapping can name".
4. **Load feedback (BE-17)** — SSE stages around the existing `lms_bridge` calls; distinguish
   "server won't start (open the GUI)" from "model load failed (VRAM?)".
5. **Failure taxonomy at OCR time (BE-15)** — the status panel can be perfect and the user still
   hits errors mid-job (model unloaded between poll and run). Mapping exception classes to named
   messages, plus a preflight `runtime_status` check at stream start, closes that window.
6. **Selection integrity (BE-18 + a small addition)** — `POST /providers/select`
   (`providers.py:119-126`) accepts any model string without checking it against the runtime's
   list. Cheap improvement: when the provider is local and reachable, warn (not block) if the model
   isn't in `runtime_status` models — a `"model_missing"` state the UI can badge.

### 4.3 What NOT to do

- **No retry loops in the status path.** The UI already polls `/providers/status`; retries inside
  the probe just multiply latency on a down runtime. Single-shot + short timeout is correct.
- **No auto-start of runtimes on status.** `ensure_runtime_ready` is invoked from explicit user
  actions (`/loadable`, `/load` — `providers.py:144,168`); keep it that way. A status poll that
  side-effects `lms daemon up` would be surprising and slow.
- **No provider SDKs.** The OpenAI-compat surface + `lms` CLI cover everything used today;
  `lmstudio>=1.6` SDK stays the "optional later" the ROADMAP already parked (ROADMAP.md:41).

---

## 5. Future-features feasibility (BACKLOG → current architecture)

### F1 · Batch: process multiple notebooks at once — **M/L, the only one needing surgery**

The blocker is architectural: OCR executes inside the SSE request (`api/jobs.py:69`), so N
concurrent jobs = N held-open requests, and closing a tab kills its job. The batch shape:

1. **Job runner**: `asyncio.create_task(run_ocr_to_queue(...))` per job, bounded by a global
   `asyncio.Semaphore(1..2)` (one local GPU = concurrency 1 for local engines; cloud can go
   wider). Events go to an in-memory `asyncio.Queue` per job; the SSE route becomes a subscriber
   that replays persisted state then tails the queue.
2. **Prereqs already itemized**: BE-13 (`GET /jobs`, delete), BE-02/BE-03 (truthful status +
   resume — batch retries depend on them), BE-14 (single-runner guard becomes the runner's job),
   BE-05 (uploads must not stall the loop that runs every job).
3. **API adds**: `POST /jobs/batch` (list of `rel_path`s) or just N `POST /jobs` + a
   `POST /jobs/{id}/start`; queue state folds into `GET /jobs`.
4. **No DB needed** — the store's per-job dirs already isolate state; only the queue/semaphore is
   new, and it's in-memory by design (a restart re-lists jobs from disk).

### F2 · Mapping strategies `tags` + `dataview` — **S, drops in exactly as designed**

`structure/strategies.py` needs one pure function each (frontmatter `tags:` derived from the
folder path; a `dataview` index note emitting a query block instead of literal links), a widened
`Strategy` Literal (`strategies.py:14`), a branch in `build_plan` (`mapper.py:22-28`), and the
BE-19 schema Literal so the picker round-trips validated. The `NotePlan` shape already supports
both (content plans carry `source`; index plans carry `links` — a dataview plan is an index plan
with different rendering, so `export/service.py:render_note` gains one branch). Note: the tags
strategy wants frontmatter control, which today lives in `note.md.j2` — design it together with F3.

### F3 · Custom export templates — **S/M**

`_environment()` (`export/service.py:18-26`) hardcodes the package templates dir. Change to a
`ChoiceLoader([FileSystemLoader(data_dir / "templates"), FileSystemLoader(_TEMPLATES_DIR)])` so a
user file shadows the built-in; add `template` to `Settings` (`config.py:34-42`) and two thin
routes (list templates, get/put template body). Jinja2 sandboxing is a non-concern for a
single-user local app rendering its own files. Depends on BE-11 (a stable `data/` location) so
user templates live somewhere predictable.

### F4 · Full-text search across exports — **S/M, two honest tiers**

Tier 1 (ship first): `GET /search?q=` that walks `settings.vault_path` (or just the exported
paths) with a plain scan — pure stdlib, zero infra, instant for vaults <10k notes. Tier 2 (only if
tier 1 is slow for real users): SQLite FTS5 index updated in `export_notes` after each write —
this is the moment BACKLOG.md:17's "SQLite if needed" clause actually triggers, and it can share a
DB file with a future jobs index. Don't start at tier 2.

### F5 · Scheduled pull from Google Drive — **M as designed, L if taken literally**

Taken literally (Drive API + OAuth + polling), this is the largest item and mostly not backend
plumbing but credential UX. The honest reading of the product: the Scribe folder is *already
synced locally* by the Drive client — so the feature is really the **background folder watcher**
BACKLOG.md:14 parked: a `watchfiles.awatch(scan_folder)` task started at app startup, debounced,
auto-creating jobs for new PDFs (needs F1's runner so watch-triggered jobs queue instead of
racing). Recommend re-scoping "scheduled Drive pull" to "watch the synced folder" — same user
outcome, a fraction of the cost, no Google credentials in a local app.

### F6 · Fast-path ingest of Scribe's native "Convert to text" — **S/M**

A new ingest branch, not a new stage: accept `.txt` (upload or scan listing), split to pages (or
one page), create the job with `markdown` prefilled and `done=True` per page — the review UI then
opens an already-transcribed job and OCR is skipped entirely (`run_ocr` with all pages done yields
`job_done` immediately once BE-03 lands — a nice dependency). Touches: `scan_pdfs` extension or a
sibling `scan_texts`, `_notebook_from_request` acceptance, zero engine work. The BE-01 scan
endpoint should be designed with a `kind` field per entry so this slots in later.

### F7 · Kindle `myClippings.txt` — **S, parked correctly**

A pure parser (`ingest/clippings.py`: the file is `\n==========\n`-delimited records) →
`NoteSource` per book → the existing `export_notes`. No architectural friction; it's purely a
demand question, as BACKLOG.md:28-29 says.

---

## 6. Phased roadmap

Ordering principle: fix what's broken in the shipped flow first, then make model management honest
(Víctor's priority), then hardening, then enablers. Each sprint is a coherent PR batch per the
repo's issue→PR→sprint rhythm; every important bug (BE-01/02/03/04/06) gets its own issue before
the fix per the standing rule.

**Sprint A — "the shipped flow tells the truth"** *(all S except BE-06)*
BE-01 (scan endpoint) · BE-02 (stuck running) · BE-03 (resume, no re-OCR) · BE-05 (to_thread) ·
BE-06 (index merge) · BE-14 (409 on double stream) · BE-12 (atomic writes).
*Outcome: Stop/refresh/re-export are all safe; the Scan button works.*

**Sprint B — "model management you can trust"** *(Víctor priority; all S except BE-17)*
BE-04 (pull errors) · BE-07 (cloud key probe) · BE-09 (timeout shapes) · BE-15 (error taxonomy +
preflight) · BE-16 (concurrent probes) · BE-17 (load progress SSE) · BE-21 (no-base_url lie) ·
BE-18 (no silent fallback).
*Outcome: every provider state is honest; every pull/load failure is visible and named.*

**Sprint C — hardening + hygiene** *(S/M)*
BE-08 (heartbeat) · BE-10 (page timeout) · BE-11 (MARGINALIA_HOME) · BE-13 (job list/delete/GC) ·
BE-19 (strategy Literal) · BE-20 (drop dead `models()`) · BE-22 (Keychain caveat) · BE-25 (tests
backfill + E2E smoke) · BE-23/BE-24 opportunistically.

**Sprint D — future-feature enablers** *(only when a feature is actually scheduled)*
F1 runner (task + queue + semaphore, absorbing BE-02's "bigger alternative") → F2 strategies →
F3 templates → F6 fast-path → F4 search tier 1 → F5 as folder watcher.

---

## 7. Risks & limitations of this audit

- **Read-only, static.** Nothing was executed; runtime behaviors (Starlette's exact cancellation
  path, Ollama's error-line format, fetch's behavior on abruptly closed chunked responses) are
  asserted from code + documented library semantics, not observation. BE-02/BE-04 deserve a quick
  manual repro before filing (start OCR → Stop → check `job.json` status; pull a garbage model
  name → watch the UI report success).
- **Claude/macOS Keychain (BE-22)** is inferred from Claude Code's documented credential storage,
  not tested on a Mac.
- **Frontend is out of scope** except where it defines the backend contract (scan, pull); the
  frontend halves of BE-01/BE-04/BE-17 need their own small changes.
- **Git history untouched** (per audit constraints) — whether `/api/scan` was removed in a
  refactor or never wired is unknown; only the current state is asserted.
- **Single-user local posture assumed throughout.** None of the recommendations add auth,
  rate-limiting, or multi-tenant anything; several "accept it" calls (settings write races,
  in-memory queues) are only valid under that posture.

---

## 8. Open questions for Víctor

1. **BE-02 semantics**: when the user presses Stop, should the job become `pending` (resumable,
   simplest) or a new explicit `stopped` status (clearer UI, touches the `Literal` in
   `store.py:45` + frontend types)?
2. **BE-06 merge policy**: when re-exporting into a folder, should index notes *union* links
   (never lose anything, may keep links to notes the user deleted) or *rebuild from the vault's
   actual files* (self-healing, slightly more code)? Union is recommended as the first cut.
3. **Batch concurrency**: for local engines, is queue-depth-1 (one notebook OCRing at a time,
   others queued) acceptable? Parallel local OCR on one GPU will thrash VRAM; cloud engines could
   run 2–3 wide.
4. **Re-export overwrite of content notes**: today re-exporting a notebook silently replaces
   `<notebook>.md`, including edits made *in Obsidian* after export. Acceptable (the review UI is
   the editing surface), or should export detect a newer mtime and warn?
5. **"Scheduled Drive pull" re-scope**: is the folder-watcher reading (F5, watch the locally
   synced folder) the actual intent, or is true Drive-API pull (device without the Drive client)
   a real scenario for you?
6. **BE-11 location**: is `MARGINALIA_HOME` (env var, default CWD) the right call, or do you
   prefer pinning to the repo checkout dir since the installer is clone-based?
