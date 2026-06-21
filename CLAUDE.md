# marginalia — Claude Code Context

Fuente de verdad para trabajar en este repo. Supera cualquier convención más vieja en commits o docs.
Sigue las reglas globales:
- [[clean-code]] (`~/.claude/CLEAN_CODE.md`) — estilo de código.
- [[project-bootstrap]] (`~/.claude/PROJECT_BOOTSTRAP.md`) — GitHub, CI, stack de seguridad.
- [[token-savers]] (`~/.claude/TOKEN_SAVERS.md`) — RTK y herramientas de ahorro de tokens.

Los deltas de este proyecto van abajo.

---

## 1. Visión

marginalia transforma cuadernos manuscritos del Kindle Scribe (PDF) en notas Markdown en Obsidian.
Combina ingesta (carpeta sincronizada o drag&drop) + OCR (local Qwen3-VL vía Ollama/LM Studio, o cloud
Claude/Gemini) + review humana imagen↔markdown + export que respeta la jerarquía de carpetas del origen.
End-state: una app local todo-en-uno, todo por botones, cero terminal para el uso diario.

## 2. Tech stack

| Capa | Herramienta |
|---|---|
| Web framework | FastAPI + Uvicorn |
| Validación | Pydantic v2 |
| Gestor de paquetes | uv |
| Linter/formato | Ruff (line-length 120) |
| Tipos | mypy (`backend/marginalia`) |
| Tests | pytest + pytest-asyncio |
| PDF → imagen | PyMuPDF (fitz) |
| OCR local | Qwen3-VL vía Ollama / LM Studio (API OpenAI-compat) |
| OCR cloud | Claude (`claude-agent-sdk`, suscripción) · Gemini (endpoint OpenAI-compat, free tier) |
| Plantillas export | Jinja2 |
| Frontend | Vite + React + TypeScript + Tailwind + GSAP |
| Streaming | SSE (`StreamingResponse` nativo de FastAPI) |

## 3. Estructura

```
backend/marginalia/{config,models_admin}.py
backend/marginalia/{ingest,ocr,jobs,structure,export,api}/
frontend/src/{steps,components,api,lib}/
docs/ARCHITECTURE.md   # decisiones + flujo de datos + árbol completo
```

El árbol completo con la responsabilidad de cada módulo está en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 4. Git workflow

- **Trunk-based**: `main` única rama larga. Ramas `feat/ fix/ docs/` salen de main y PR directo a main. Sin rama dev.
- **Sin squash**: release-please necesita el historial de commits individual.
- **Conventional Commits**: imperativo, inglés, **sin** atribución AI (regla global dura — ni `Co-Authored-By` ni "Generated with").
- **El usuario commitea él mismo**: cuando pida, dale el/los comando(s); nunca auto-commitees.
- CI verde (`test` / `lint` / `typecheck` / `frontend-build`) antes de cualquier merge. Si CI falla en main, se arregla; nunca `enforce_admins`.

## 5. Comandos

Backend (desde la raíz):
```bash
uv sync                                              # instala deps
uv run uvicorn marginalia.api.main:app --reload      # dev API (:8000)
uv run pytest -q                                      # tests
uvx ruff check . && uvx ruff format --check .         # lint + formato
uv run mypy backend/marginalia                        # tipos
```

Frontend (desde `frontend/`):
```bash
npm ci
npm run dev          # :5173, proxy /api → :8000
npm run build        # → frontend/dist (lo sirve FastAPI en prod)
npm run lint && npm run typecheck
```

## 6. Contrato API ↔ frontend

- **Dev**: Vite `:5173` con proxy `/api` → FastAPI `:8000`. **Prod/diario**: FastAPI sirve `frontend/dist` + API en `:8000` (un proceso, una URL).
- **Versionado**: prefijo `/api`. **Errores**: `{ "detail": "..." }` con el status HTTP correcto.
- **OCR en vivo**: SSE en `GET /api/jobs/{id}/stream`. Eventos: `page_started`, `page_delta`, `page_done`, `job_done`, `error`.
- **Auth**: ninguna (app local de un usuario). El estado de auth de Claude se expone como **dato** (conectado/no), no como login.

## 7. Calidad de código

Aplica [[clean-code]]. Específico del repo:
- **Routers finos**: nada de lógica de negocio en las rutas — va a los `service.py`.
- **Límites duros**: los engines OCR no conocen FastAPI/jobs/vault; el `StructureMapper` es función pura; `ingest` no conoce OCR ni vault. No cruzar esos límites.
- Docstrings de módulo / clase / función pública (regla global). snake_case en backend, camelCase en frontend.
- Marca simplificaciones deliberadas con un comentario `# ponytail: ...` que nombre el techo y el upgrade path.

## 8. Workflow rules

- **Long-running (OCR, build, `ollama pull`) — nunca te quedes solo esperando**: lanza, haz otra cosa, comprueba y actúa.
- **Fire-and-check, no bloquear**: sondea una vez → actúa → sigue con otra tarea. En verde, mergea.

## 9. Tooling notes

- Solo `uv` (sin `pip` directo). `data/` y `providers.toml` están gitignored; `providers.example.toml` **sí** se commitea.
- Modelos locales: la app habla con Ollama (`:11434`) y LM Studio (`:1234`) por HTTP; **no asume** modelos instalados — los lista del runtime y permite `pull` por botón.
- Screenshot de UI: `frontend/scripts/shot.mjs` (Playwright) — ver [[FRONTEND_VISUAL_VERIFICATION]].
- Para tocar `AgentSDKEngine` / auth de suscripción, consulta la skill `claude-api`.

## 10. Skills recomendadas

| Skill | Cuándo |
|---|---|
| `frontend-design` + ui-skills.com | cualquier decisión visual (Import/Review/Export) |
| `refactor-fastapi` | limpieza backend (Pydantic v2, async I/O, DI) |
| `claude-api` | tocar `AgentSDKEngine` / auth de suscripción |
| `code-review` → `simplify` | en cada diff |
| `run` / `verify` | conducir la app y confirmar OCR→review→export |

## 11. Lecciones aprendidas

<!-- add new entries above this line -->

## 12. Documentos relacionados

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — decisiones de arquitectura, flujo de datos, árbol completo.
- [README.md](README.md) — pitch de usuario.
- [KICKOFF.md](KICKOFF.md) — brief original (referencia histórica).
- [BACKLOG.md](BACKLOG.md) — ideas fuera del MVP, anotadas y aparcadas.
- `providers.example.toml` — plantilla de configuración de proveedores.
- `scripts/setup-github.sh` — aplica branch protection + labels (lo corre el usuario).
