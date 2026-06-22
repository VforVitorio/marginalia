# marginalia — Roadmap

Sprint plan. Each unchecked item becomes a GitHub issue under a milestone. Captures all feedback from
real-use testing so nothing is lost. (For parked, out-of-MVP ideas see [BACKLOG.md](../BACKLOG.md).)

## Shipped

- **MVP** (PRs #1–#6): ingest (PyMuPDF), OCR engines (Ollama/LM Studio/Gemini/Claude), jobs + SSE, structure/export (mirror + wikilinks), FastAPI, React UI.
- **Infra** (PRs #7–#8): CI/CD (test/lint/typecheck/frontend-build), security scanners (CodeQL/OSV/gitleaks/pip-audit), Dependabot, release-please, branch protection, labels.

## In flight (PRs open)

- **#28** — clickable step indicator + Back button on Review.
- **#14** — export into a chosen target folder for loose drag-and-drop notebooks.

## Sprint 2 — OCR quality & review UX

- [ ] **OCR system prompt.** Give the model real context: it's transcribing *handwritten study notes* into a Markdown vault. Ask for clean GitHub-flavoured Markdown, math as `$…$` / `$$…$$`, preserved structure (headings/lists/tables), and *no hallucination* (`[illegible]` when unsure). Wire a system prompt through both engines. *(rough Gemma output observed in testing)*
- [ ] **Bug — errored/empty export.** Export must NOT be enabled when OCR errored; surface the error prominently in Review (per-page + banner); log the exception server-side. *(observed: a failed job exported empty notes)*
- [ ] **Cancel / Stop button** during OCR (none today) — stop the stream and the engine.
- [ ] **Inline Markdown editor** in the transcript preview — rendered Markdown that you click to edit in place, not just a raw textarea.
- [ ] **Onboarding** — a 3-window first-run intro (LexFlow-style): what it does → pick a provider/model → import a PDF.

## Sprint 3 — Vault & export structure

- [ ] **Auto-detect the Obsidian vault** (macOS/Linux/Windows, via `obsidian.json`) + manual entry.
- [ ] **Export into a named folder** (your "Kindle" folder) and **drop the generic root `index.md`** — folder-index notes only inside real, named folders.
- [ ] **Rethink wikilinks + folder mapping.** The current mapping is too naive. Real Scribe folder structure comes from the **synced-folder scan** (a single emailed PDF carries no hierarchy) — use the scan listing to mirror the notebook organisation; name folder-index notes after their folder.

## Sprint 4 — Models & providers

- [ ] **Local model management** — list models per provider from the runtime; one-click load / `pull`; **recommend 2 small vision models** (e.g. Gemma 3n E2B + Qwen3-VL 2B or MiniCPM-V) so 8 GB users have a known-good pick.
- [ ] **Cloud setup UX** — guided config for the Gemini free-tier key and the Claude subscription.

## Sprint 5 — Responsive & polish

- [ ] **Responsive / mobile** layout + view-ratio tuning, screenshot-driven (must work on phones and any screen).
- [ ] **Real Claude auth probe** — replace the hardcoded `_claude_authenticated() = True` ("authenticated" is currently a lie). *(issue #11)*
- [ ] **ESLint flat config** (dropped during integration; v9 peer conflict). *(issue #10)*
- [ ] **End-to-end verification + screenshots.** *(issue #9)*
