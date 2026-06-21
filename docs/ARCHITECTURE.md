# marginalia — Arquitectura

Decisiones de arquitectura, flujo de datos y límites entre módulos. Para cada decisión: qué se elige, qué
se descarta y por qué. Las convenciones de trabajo viven en [CLAUDE.md](../CLAUDE.md); el alcance del MVP
y lo aparcado, en [BACKLOG.md](../BACKLOG.md).

## 0. Resumen

Pipeline **local** Kindle Scribe → Obsidian. Cuatro etapas: **ingesta** (PDF desde carpeta sincronizada o
drag&drop) → **OCR** (local Qwen3-VL, o cloud Claude/Gemini, streameado por página) → **review** humana
(imagen ↔ markdown) → **export** al vault respetando la jerarquía de carpetas del origen. Todo por botones;
el usuario nunca toca terminal ni edita config para el uso diario.

## 1. Flujo de datos

```
                        carpeta sincronizada ──┐
                          (scan on-demand)     │
                                               ▼
  drag&drop PDF ───────────────────────►  ingest/pdf.py ──► [Notebook: páginas como PNG]
                                                                   │
                                                                   ▼
                                              jobs/service.py  (orquestador)
                                                   │  por cada página:
                                                   │     ocr/<engine>.transcribe_page(png, prompt)
                                                   │     → streamea texto → persiste page_n.md
                                                   ▼
                                          SSE: page_started/page_delta/page_done/job_done
                                                   │
                                                   ▼
                                       frontend Review (imagen ↔ markdown, editable)
                                                   │  PUT /api/jobs/{id}/pages/{n}
                                                   ▼
                                       export/service.py ──► structure/mapper.py
                                                   │            (mirror + wikilinks)
                                                   ▼
                                          vault de Obsidian (.md con frontmatter)
```

El **estado vivo** de un job es su directorio en disco (`data/jobs/{id}/`): `job.json` + `page_n.png` +
`page_n.md`. No hay base de datos (ver §6).

## 2. Seam 1 — `OCREngine` (backends de OCR intercambiables)

Un `Protocol` con un único método de trabajo que **streamea** texto de una página:

```python
class OCREngine(Protocol):
    info: EngineInfo                       # id, display_name, kind=local|cloud, current_model
    def models(self) -> list[str]: ...     # modelos disponibles en este backend
    async def transcribe_page(self, image_png: bytes, prompt: str) -> AsyncIterator[str]: ...
```

El engine recibe **una imagen y un prompt** y devuelve **trozos de texto**. No sabe nada de jobs, SSE,
vault ni FastAPI. Esa ignorancia es el límite que lo hace testeable y sustituible.

**Implementaciones:**

- **`OpenAICompatEngine`** — un solo adapter parametrizado por `base_url` + `api_key` + `model`, hablando el
  API OpenAI-compatible (`POST {base_url}/chat/completions`, imagen como data-URL en un mensaje de visión,
  `stream=true`, parseo de deltas). Los tres backends solo difieren en esos tres parámetros:
  - Ollama → `http://localhost:11434/v1`
  - LM Studio → `http://localhost:1234/v1`
  - Gemini → `https://generativelanguage.googleapis.com/v1beta/openai/` + API key del free tier.
- **`AgentSDKEngine`** — Claude vía `claude-agent-sdk`, autenticado por la sesión de Claude Code
  (suscripción Pro/Max, **sin API key**). Detrás del mismo `OCREngine`.

**Descartado:** un método `transcribe_notebook(pdf)` (mete render + orquestación + persistencia dentro del
engine → intesteable y acoplado). Un método no-streaming (rompe la review en vivo). Un cliente por
proveedor (triplica superficie para una diferencia que es una URL). Claude por API key de pago (el brief
quiere la suscripción).

## 3. Seam 2 — `StructureMapper` (jerarquía Scribe → Obsidian)

Función pura `(notebooks, strategies, vault_root) -> list[ExportedNote]`. Estrategias **combinables**; en el
MVP `mirror` (siempre) + `wikilinks` (toggle):

- **`mirror`**: destino = `vault / <ruta relativa del origen> / <notebook>.md`. Un notebook = una nota; las
  páginas son secciones `## Página N`.
- **`wikilinks`**: además genera/actualiza una nota índice por carpeta (`<carpeta>.md`) con `[[notebook]]`
  por cada notebook dentro. Materializa la estructura como enlaces, que es el valor de Obsidian.

**De dónde sale la jerarquía:** del **árbol de carpetas del origen** (la carpeta sincronizada), no de dentro
del PDF — un export del Scribe es un PDF plano por notebook. Para drag&drop suelto no hay contexto de
carpeta → el usuario elige carpeta destino (o raíz del vault) en el diálogo de export. El mapper opera sobre
**rutas de fichero**, no sobre el contenido del PDF.

**Descartado:** las 4 estrategias a la vez (el brief lo prohíbe en MVP; `tags`/`dataview` quedan en backlog
detrás del mismo contrato). Una nota por página (multiplica ficheros, rompe la unidad "un cuaderno = una
nota").

## 4. Backend FastAPI + streaming

OCR por página se emite por **SSE** desde `GET /api/jobs/{id}/stream`, con `StreamingResponse` nativo
(`text/event-stream`). Eventos: `page_started`, `page_delta`, `page_done`, `job_done`, `error`. Cada página
se **persiste al completarse**, así un corte de conexión se reanuda desde disco.

**SSE y no WebSocket:** el flujo es unidireccional servidor→cliente; SSE es más simple, reconecta solo y va
sobre HTTP normal. **`StreamingResponse` nativo y no `sse-starlette`:** cubre el caso con ~10 líneas; se
añade `sse-starlette` solo si los heartbeats/reconexión se quedan cortos.

## 5. Frontend — una sola interfaz, un flujo

SPA con un único flujo `Import → Review → Export`. GSAP para las transiciones entre pasos. Selector de
proveedor/modelo y gestión de modelos (incl. `ollama pull`) en un panel del header, todo por botones. Cero
rutas anidadas, cero paneles dispersos. **Descartado:** router multi-página (el producto es lineal).

## 6. Persistencia — workspace en disco, sin base de datos

Cada job es `data/jobs/{id}/` con `job.json` (estado, páginas, rutas) + `page_n.png` + `page_n.md`. Los
ajustes vivos (vault path, proveedor/modelo activo, estrategias) en `data/settings.json`, escrito por la UI.

**Sin DB:** el MVP es un proceso corto de un usuario local; los ficheros sobreviven a reinicios, son
inspeccionables y `job.json` es trivial. SQLite sería infra para consultas entre jobs que el MVP no hace.
**Descartado:** SQLite/Postgres (YAGNI), estado solo en memoria (se pierde al reiniciar a media review).

## 7. Configuración

`providers.toml` (gitignored; `providers.example.toml` commiteado) = **catálogo de proveedores + secretos**
(base_urls, API key de Gemini). `data/settings.json` = **elecciones de uso diario** fijadas por la UI (vault
path, proveedor/modelo activo, estrategias). Así se respeta "el usuario nunca edita config para el uso
diario": `providers.toml` es seed/credenciales, no se toca para usar la app.

## 8. Modelo de servido

- **Dev:** Vite `:5173`, proxy `/api` → FastAPI `:8000`.
- **Diario/prod:** FastAPI sirve `frontend/dist` **y** el API en `:8000` (un proceso, una URL).

## 9. Ingesta — escaneo bajo demanda (MVP)

Botón "Escanear carpeta" que lista los PDF de la carpeta configurada (recursivo, preservando ruta relativa)
+ drag&drop de PDFs sueltos. **Sin hilo watcher** en el MVP: vigilar en vivo mete threading/debounce/estado
de fondo para un MVP donde el import se lanza a mano. El watcher en background está en [BACKLOG.md](../BACKLOG.md).

## 10. Árbol de archivos (responsabilidad por módulo)

```
backend/marginalia/
├── config.py            # carga providers.toml + data/settings.json → Settings (Pydantic v2)
├── ingest/
│   ├── pdf.py           # PyMuPDF: PDF → PNGs por página; modelos Notebook/Page
│   └── scan.py          # lista PDFs de la carpeta raíz preservando ruta relativa
├── ocr/
│   ├── engine.py        # Protocol OCREngine + dataclass EngineInfo  (SEAM)
│   ├── openai_compat.py # OpenAICompatEngine (Ollama / LM Studio / Gemini)
│   ├── agent_sdk.py     # AgentSDKEngine (Claude vía suscripción)
│   ├── registry.py      # construye el engine activo desde settings; lista proveedores
│   └── prompts.py       # prompt(s) de OCR de manuscrito
├── models_admin.py      # list/pull/load de modelos vía HTTP de Ollama y LM Studio
├── jobs/
│   ├── store.py         # workspace en disco: job.json, PNGs, MDs  (única fuente de estado)
│   └── service.py       # orquesta ingest→OCR por página; emite eventos SSE; persiste
├── structure/
│   ├── mapper.py        # StructureMapper: (notebooks, strategies, vault) → ExportedNote[]
│   └── strategies.py    # mirror, wikilinks (combinables)
├── export/
│   ├── service.py       # render Jinja2 + escritura al vault
│   └── templates/note.md.j2
└── api/
    ├── main.py          # app FastAPI; monta routers; sirve frontend/dist en prod
    ├── deps.py          # DI: get_settings, get_engine, get_job_store
    ├── jobs.py          # POST /jobs, GET /jobs/{id}/stream (SSE), PUT páginas, POST export
    ├── providers.py     # GET/POST proveedores; endpoints de admin de modelos
    └── schemas.py       # modelos Pydantic de request/response
```

**Límites (qué NO debe saber cada uno):**
- `ocr/` no sabe de jobs, SSE, vault ni FastAPI. Imagen → texto.
- `structure/` no sabe de OCR, HTTP ni engines. Función pura.
- `ingest/` no sabe de OCR ni vault. PDF → imágenes / lista de rutas.
- `jobs/service.py` es el **único** sitio que cablea ingest + ocr + persistencia y emite SSE.
- `export/` solo conoce `structure/` + escritura al vault + Jinja2.
- `api/` es fino: los routers delegan, sin lógica de negocio.
- `frontend/` habla solo con `/api`.

## 11. Riesgos y mitigaciones

1. **Auth de la suscripción de Claude (Agent SDK)** — requisito duro (cloud "ambos garantizados"). Fuera del
   entorno autenticado de Claude Code no hay API key y las llamadas fallan. *Mitigación:* el backend prueba
   la auth al arrancar y expone el estado en la UI; el seam `OCREngine` deja que Gemini/local cubran el job;
   se desarrolla dentro del entorno autenticado. Si la auth no coopera, se avisa antes de darlo por cerrado.
2. **Calidad del OCR de manuscrito** — letra difícil o modelos pequeños transcriben mal. *Mitigación:* la
   review UI es la red (editar antes de exportar) + botón "re-OCR en cloud" por página + prompt afinado +
   render a DPI alto.
3. **VRAM de 8 GB / disponibilidad del modelo local** — el tag de Qwen3-VL puede no existir en Ollama o no
   caber. *Mitigación:* verificar el tag real en el scaffold; default al 2B/4B que cabe; LM Studio como
   runtime alternativo; cloud como fallback; listar lo que el runtime reporte (`/api/tags`), no hardcodear.
4. **Corte de SSE en páginas largas** — la conexión cae a media OCR. *Mitigación:* persistir cada página al
   completarse (reanuda desde disco) + heartbeat periódico.
