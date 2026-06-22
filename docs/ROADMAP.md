# marginalia — Roadmap

Sprint + PR plan. Captures all feedback from real-use testing. (Parked, out-of-scope ideas: [BACKLOG.md](../BACKLOG.md).)

## Shipped (on `main`)

- **MVP** (#1–#6) + **infra** (#7–#8): ingest, OCR engines, jobs+SSE, structure/export, FastAPI, React UI; CI/CD, security, branch protection.
- **Clickable nav + Back** (#28) · **export target folder** (#14) · **Obsidian-tuned OCR system prompt + disclaimer** (#29) · **logo + roadmap** (#30) · **Review robustness** — gate export on OCR error, Stop button, server-side log (#40, closes #31/#32) · **onboarding modal** acrylic + line icons (#41) · **tsconfig fix** (#42).

## Open PRs (ready to merge)

- **#43** — provider **status backend**: `GET /api/providers/status` → per provider `reachable / models / current_model / state / hint`. Green (mypy/ruff/pytest). Foundation for Sprint 4.

---

## Sprint 4 — Models & Providers (CURRENT FOCUS) — *"make picking a model actually work"*

Today the picker shows a model as loaded without checking → cryptic "all connection attempts failed" when the runtime/model is down. This sprint makes provider state **real** and lets you **load models from the app**.

**PR plan:**

1. **[#43 — open] Provider status backend.** Done.
2. **Provider-picker status indicator (frontend).** Poll `GET /api/providers/status`; per provider show a real dot + label: Ready / Start the runtime / Load a model / Add API key / Sign in. Kill the fake "Claude authenticated". *(issue #37 UI part)*
3. **Local model loading + loading→loaded indicator** *(issue #37)*:
   - **Ollama**: `POST /api/providers/ollama/pull` (already have `models_admin.pull_model`) → SSE progress; the model warms on first request.
   - **LM Studio (headless, via the `lms` CLI — reuse the `lmcode` patterns below)**: load/unload/start the server with the GUI closed.
4. **Cloud config** *(issue #38)*:
   - **Gemini / OpenAI-compatible**: a small "API key" screen → `POST /api/providers/{id}/key` writes the key into `providers.toml`.
   - **Claude**: real auth probe + status; if not signed in, instruct `claude login` (it's the Claude Code subscription login — there is no web redirect we control).
5. **Real Claude auth probe** *(issue #11)*: replace the hardcoded `_claude_authenticated() = True`.

### LM Studio headless loading — approach (reusing `lmcode`) — *issue #44*

`lmcode` (`Desktop/Documents/Libre/lmcode`) drives LM Studio with the GUI closed via the `lms` CLI as a graceful-fail subprocess. Lift these into `backend/marginalia/models_admin.py`:

- **Reachability**: a 0.5 s `socket.create_connection(("127.0.0.1", 1234))` pre-check before any SDK/HTTP call (avoids multi-second hangs when down).
- **Start headless (two-path)**: `lms server start` (fast — GUI open) → fallback `lms daemon up` (full headless daemon); fire in a background thread, then poll reachability (server ~5 s, daemon ~30 s). **Don't trust the exit code — always re-probe.**
- **Load**: `lms load <id> --yes [--gpu auto|max|0-1] [--context-length N]` — timeout **120 s** (VRAM load is slow). **Unload**: `lms unload <id>` / `--all`.
- **List loaded**: `lms ps --json`. **List downloaded**: `lms ls --json`.
- **Guards**: `shutil.which("lms")` (graceful no-op if absent); `stdin/stdout/stderr=DEVNULL`; never raise — return `False`/`[]`. (`lms.exe` is at `~/.lmstudio/bin/`.)
- Optional later: the `lmstudio` Python SDK (`lmstudio>=1.6`) async client (`list_loaded()`, `model()`); the CLI is enough for headless start + load.

---

## Sprint 2 leftovers

- **#33 — inline Markdown editor** in the transcript preview: render Markdown + KaTeX (the system prompt now emits `$…$`/`$$…$$`), click-to-edit. New `MarkdownEditor.tsx` + deps (react-markdown, remark-gfm, remark-math, rehype-katex, katex).
- **#45 — Onboarding polish**: a **"Guide" button** to reopen the onboarding anytime (first-run gate via `localStorage.marginalia.onboarded` already done); make each option + the scan-folder purpose clear in the steps.

## Sprint 3 — Vault & export structure

- **#35** — drop the generic root `index.md`; folder-index notes only inside named folders.
- **#36** — rethink wikilinks + folder mapping. Structure comes from the **synced-folder scan** (a single uploaded PDF has none — Amazon doesn't expose Scribe folders); mirror the scan tree, name folder-index notes after their folder.
- **#46 — Vault + scan-folder path suggestions**: auto-detect the vault via `obsidian.json` (logic already prototyped); suggest common Drive/sync scan-folder locations.

## Sprint 5 — Polish & launch

- **#39** — responsive / mobile layout + view-ratio (consult ui-skills.com via a browser).
- **#10** ESLint flat config · **#9** E2E + screenshots · merge the **8 green dependency PRs** (#15,16,17,19,20,22,23,24).
