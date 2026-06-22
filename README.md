<p align="center">
  <img src="docs/logo.svg" alt="marginalia" width="200">
</p>

# marginalia

Turn the notebooks you write by hand on your Kindle Scribe into Markdown you can actually use in Obsidian.

You write by hand on the Scribe, export the notebook as a PDF, and marginalia does the boring part: it runs OCR over your handwriting, lets you fix whatever the OCR got wrong, and drops the result into your vault — keeping the folder structure you already use on the device.

The name comes from *marginalia*, the notes people used to scribble in the margins of manuscripts. Same idea: getting handwritten thought to survive the jump to digital.

## Kindle Scribe only (for now)

This is built for the Kindle Scribe and nothing else. No reMarkable, no Apple Notes, no Samsung Notes. If you use another device, marginalia won't help you yet — and there are tools that already do this well for those (Scrybble for reMarkable, for instance).

It's not laziness about portability: export quirks differ enough between devices that "support everything" usually ends up as "support nothing well." Scribe first.

## What it does (MVP)

- Local OCR with Qwen3-VL (2B or 4B) through Ollama or LM Studio. Runs on an 8 GB GPU.
- Cloud OCR when you want it — Claude (through your subscription, no API key) or Gemini (free tier). Good for the pages the local model chokes on.
- A review screen: your original page on one side, the transcription on the other. Fix the mistakes before anything touches your vault.
- Folder structure carries over. Your Scribe folders become folders and wikilinks in Obsidian — your call.
- Everything's a button. Switching models, pulling a new one, local vs cloud, exporting — no terminal once it's running.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12 + uv, FastAPI, PyMuPDF, Ollama/LM Studio, Claude Agent SDK, Gemini |
| Frontend | Vite + React + Tailwind + GSAP |
| OCR | Qwen3-VL (local) or Claude/Gemini Vision (cloud) |
| Export | Jinja2 + Markdown with frontmatter |

## Getting started

You'll need: Python 3.12+, Ollama or LM Studio if you want local OCR, a Kindle Scribe, and an Obsidian vault.

```bash
git clone https://github.com/VforVitorio/marginalia.git
cd marginalia
uv sync
cp providers.example.toml providers.toml   # set your vault path and Gemini key if you have one
uv run uvicorn marginalia.api.main:app
```

Open http://localhost:8000 and import a notebook. (The vault path and almost everything else is set from the UI — `providers.toml` is just the starting point and where API keys live.)

## How it works

1. Export from the Scribe: Notebooks → hold the cover → Export/Share → PDF. Save it to your synced folder or drop it straight into the app.
2. Import: drag the PDF in, or point marginalia at your synced folder and pick from what's there.
3. Pick a backend: local for privacy, cloud for the hard pages. One click.
4. Review: page by page, fix what the OCR misread. A normal notebook takes a couple of minutes.
5. Export: choose how it lands in Obsidian (mirror folders, wikilinks), hit export.

## Customizing the OCR system prompt

Transcription quality depends on two things: the **model you pick** and the **instructions it gets**. The OCR runs with a system prompt tuned for Obsidian — LaTeX math (`$…$` inline, `$$…$$` blocks), callouts, checkboxes, tables, headings: the rich Markdown Obsidian actually renders. If you want to steer it (your own conventions, a different structure), it lives in one place:

- `backend/marginalia/ocr/prompts.py` → `system_prompt()` — the full instructions.
- `backend/marginalia/ocr/prompts.py` → `handwriting_prompt()` — the short per-page instruction.

Edit, restart the backend, done.

## Status

Early. The MVP is still coming together — the architecture is written down in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [CLAUDE.md](CLAUDE.md) if you want the detail. Rough order: backend skeleton → OCR adapters + structure mapper → review/export UI → glue and polish.

## Trademarks

Kindle and Kindle Scribe are trademarks of Amazon. Obsidian is a trademark of Obsidian Foundry. marginalia is not affiliated with, endorsed by, or sponsored by either — the names are here so you know what works with what.

## License

MIT. Use it, fork it, sell it, whatever — just keep the notice. No warranty. See [LICENSE](LICENSE).

## Contributing

PRs welcome, Scribe-only. Issues about other devices will be closed — not out of spite, just scope. Fork, branch, follow the conventions in [CLAUDE.md](CLAUDE.md), open a PR.

## Roadmap (later, maybe)

- Process multiple notebooks at once
- Custom export templates
- Full-text search across exports
- Scheduled pull from Drive
- Other devices — someday, not soon

## FAQ

**Does it work with reMarkable, iPad, etc.?** Not yet, and not for the MVP. This is for the Kindle Scribe. If you use another device, there are better tools for it (Scrybble for reMarkable, Apple Importer for Apple Notes).

**Do I need an API key?** For local OCR (Ollama), no. For cloud, you either use your Claude subscription (no API key) or a free Gemini key from AI Studio.

**Does it run on Mac/Windows/Linux?** Yes. Pure-Python backend, web frontend. Tested on macOS and Linux; Windows should work but isn't officially tested yet.

**What if the OCR is bad?** That's what the review is for: you see the original image and the text, and you edit it before exporting. If it's still bad, run that page through a cloud backend (Claude or Gemini) — they hold up better on messy handwriting.

## Contact

Issues for bugs and (Scribe-only) feature requests. Discussions for workflows and ideas. No Discord yet — maybe when there's a reason for one.
