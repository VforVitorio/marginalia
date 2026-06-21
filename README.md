# marginalia

Convierte los cuadernos que escribes a mano en el Kindle Scribe en Markdown que puedas usar de verdad en Obsidian.

Escribes a mano en el Scribe, exportas el cuaderno como PDF, y marginalia hace la parte aburrida: pasa OCR sobre tu letra, te deja arreglar lo que el OCR entendió mal, y lo deja en tu vault — manteniendo la estructura de carpetas que ya usas en el dispositivo.

El nombre viene de las *marginalia*, las notas que la gente garabateaba en los márgenes de los manuscritos. La idea es la misma: que lo escrito a mano sobreviva el salto a digital.

## Solo Kindle Scribe (de momento)

Esto está hecho para el Kindle Scribe y nada más. Ni reMarkable, ni Apple Notes, ni Samsung Notes. Si usas otro dispositivo, marginalia no te sirve todavía — y ya hay herramientas que lo hacen bien para esos (Scrybble para reMarkable, por ejemplo).

No es pereza con la portabilidad: las rarezas de export cambian bastante entre dispositivos, y "soportar todo" suele acabar en "no soportar bien ninguno". El Scribe primero.

## Qué hace (MVP)

- OCR local con Qwen3-VL (2B o 4B) a través de Ollama o LM Studio. Tira con una GPU de 8 GB.
- OCR en la nube cuando lo quieras — Claude (con tu suscripción, sin API key) o Gemini (free tier). Bien para las páginas que el modelo local no traga.
- Una pantalla de review: tu página original a un lado, la transcripción al otro. Arreglas los errores antes de que nada toque tu vault.
- La estructura de carpetas se mantiene. Tus carpetas del Scribe se vuelven carpetas y wikilinks en Obsidian — tú eliges.
- Todo con botones. Cambiar de modelo, bajar uno nuevo, local o nube, exportar — sin terminal una vez está arrancado.

## Stack

| Capa | Tech |
|---|---|
| Backend | Python 3.12 + uv, FastAPI, PyMuPDF, Ollama/LM Studio, Claude Agent SDK, Gemini |
| Frontend | Vite + React + Tailwind + GSAP |
| OCR | Qwen3-VL (local) o Claude/Gemini Vision (nube) |
| Export | Jinja2 + Markdown con frontmatter |

## Cómo empezar

Necesitas: Python 3.12+, Ollama o LM Studio si quieres OCR local, un Kindle Scribe y un vault de Obsidian.

```bash
git clone https://github.com/yourusername/marginalia.git
cd marginalia
uv sync
cp providers.example.toml providers.toml   # pon tu ruta del vault y la key de Gemini si tienes
uv run uvicorn marginalia.api.main:app
```

Abre http://localhost:8000 e importa un cuaderno. (La ruta del vault y casi todo se ajusta desde la UI — `providers.toml` es solo el punto de partida y donde viven las API keys.)

## Cómo funciona

1. Exporta del Scribe: Notebooks → mantén pulsada la portada → Export/Share → PDF. A tu carpeta sincronizada o directo a la app.
2. Importa: arrastra el PDF, o apunta marginalia a tu carpeta sincronizada y elige de lo que haya.
3. Elige backend: local por privacidad, nube para las páginas difíciles. Un clic.
4. Revisa: página a página, arregla lo que el OCR leyó mal. Un cuaderno normal son un par de minutos.
5. Exporta: elige cómo aterriza en Obsidian (carpetas espejo, wikilinks) y dale a exportar.

## Estado

Pronto todavía. El MVP se está cociendo — la arquitectura está escrita en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) y [CLAUDE.md](CLAUDE.md) si quieres el detalle. Orden aproximado: esqueleto backend → adapters de OCR + structure mapper → UI de review/export → pegamento y pulido.

## Marcas

Kindle y Kindle Scribe son marcas de Amazon. Obsidian es marca de Obsidian Foundry. marginalia no está afiliada, avalada ni patrocinada por ninguna — los nombres están aquí para que sepas qué funciona con qué.

## Licencia

MIT. Úsalo, fork, véndelo, lo que sea — solo mantén el aviso. Sin garantía. Ver [LICENSE](LICENSE).

## Contribuir

PRs bienvenidos, solo-Scribe. Los issues sobre otros dispositivos se cerrarán — no por mala leche, es cuestión de alcance. Fork, rama, sigue las convenciones de [CLAUDE.md](CLAUDE.md), abre un PR.

## Roadmap (más adelante, quizá)

- Procesar varios cuadernos a la vez
- Plantillas de export personalizadas
- Búsqueda full-text sobre lo exportado
- Pull programado desde Drive
- Otros dispositivos — algún día, no pronto

## FAQ

**¿Funciona con reMarkable, iPad, etc.?** No todavía, y no en el MVP. Esto es para Kindle Scribe. Si usas otro, hay herramientas mejores para eso (Scrybble para reMarkable, Apple Importer para Apple Notes).

**¿Necesito API key?** Para OCR local (Ollama), no. Para nube, o usas tu suscripción de Claude (sin API key) o una key gratis de Gemini de AI Studio.

**¿Corre en Mac/Windows/Linux?** Sí. Backend Python puro, frontend web. Probado en macOS y Linux; Windows debería ir pero aún no está testeado oficialmente.

**¿Y si el OCR sale mal?** Para eso está la review: ves la imagen original y el texto, y lo editas antes de exportar. Si aun así va mal, tira esa página por un backend de nube (Claude o Gemini), que aguantan mejor la letra difícil.

## Contacto

Issues para bugs y peticiones (solo-Scribe). Discussions para flujos de trabajo e ideas. Sin Discord de momento — quizá cuando haya motivo.
