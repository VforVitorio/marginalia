# BACKLOG

Ideas fuera del MVP. Regla de oro del brief: ante la duda entre añadir o no una feature, **no se añade** —
se anota aquí y se sigue. Nada de esto se construye sin pedirlo explícitamente.

## Fuera del MVP por decisión del brief
- Soporte multi-dispositivo (reMarkable, Boox, Apple/Samsung Notes).
- Las 4 estrategias de mapeo a la vez. MVP arranca con `mirror` + `wikilinks`; `tags` y `dataview` van detrás
  del mismo contrato `StructureMapper` (añadir = una función más en `structure/strategies.py`).
- Cuentas/usuarios, login, multi-tenant.
- Fine-tuning de modelos, colas distribuidas, batch masivo.

## Simplificaciones del MVP a revisitar
- **Watcher de carpeta en background** — el MVP usa escaneo on-demand (botón). Vigilar en vivo mete
  threading/debounce/estado de fondo. Upgrade path: hilo watcher (p.ej. `watchfiles`) cuando el flujo lo pida.
- **SSE a mano (`StreamingResponse`)** — añadir `sse-starlette` solo si heartbeats/reconexión se quedan cortos.
- **Workspace en disco sin DB** — SQLite si hace falta listar/consultar muchos jobs.
- **Una nota por notebook** (páginas como secciones) — trocear página-por-nota si se pide.

## Infra diferida (Fase 2, "cuando haya código shippable")
- `pre-commit` (ruff) local — de momento se confía en CI.

## Roadmap de producto (post-MVP)
- Procesar varios cuadernos a la vez (batch).
- Plantillas de export personalizadas.
- Búsqueda full-text sobre lo exportado.
- Pull programado desde Google Drive.
