# inkwell — Brief de arranque para Claude Code

> Lee este documento **entero** antes de ejecutar nada. No escribas código todavía.

---

## 0. Antes de nada: cárgate el contexto

1. **Carga tu memoria global** (`~/.claude/CLAUDE.md`) y la de proyecto si existe. Aplica
   mis directrices globales (tooling, estilo, convenciones de commit, estructura) a **todo**
   lo que hagas aquí. Si algo de este brief choca con la memoria global, párate y dímelo.
2. **Enumera las skills que vas a usar** y por qué, antes de empezar. Como mínimo razona si
   aplican `frontend-design` (la UI), y cualquier skill mía de scaffolding/Python. Lista las
   elegidas en una frase cada una.
3. Si te falta una credencial, un binario o una decisión mía, **pregunta**. No improvises
   defaults silenciosos.

---

## 1. Qué construimos (contexto mínimo)

`inkwell`: pipeline local **Kindle Scribe → Obsidian**. Coge los cuadernos exportados del
Scribe (PDF) —de una carpeta sincronizada **o subidos sueltos a la app**—, les pasa OCR
(manuscrito incluido), deja revisar el resultado, y los escribe al vault respetando la
**estructura de carpetas** original del Scribe.

Piezas conceptuales (ya decididas, no las rediscutas salvo que una falle de verdad):

- **`OCREngine`** — interfaz con backends intercambiables:
  - `OpenAICompatEngine` (un solo adapter, cambia `base_url`): **Ollama**, **LM Studio**, **Gemini** (free tier de AI Studio).
  - `AgentSDKEngine`: **Claude vía suscripción** (Agent SDK autenticado por Claude Code, sin API key).
- **`StructureMapper`** — proyecta la jerarquía de carpetas del Scribe a Obsidian:
  estrategias `mirror`, `tags`, `wikilinks`, `dataview` (combinables).
- **Backend**: Python + FastAPI (SSE para streaming del OCR), `uv`.
- **Frontend**: Vite + React + Tailwind. GSAP para transiciones.

---

## 2. Fase de diseño OBLIGATORIA (antes de una sola línea de código)

Entra en modo plan. **Desarrolla en profundidad** y espera mi visto bueno:

1. **`ARCHITECTURE.md`** — decisiones de arquitectura justificadas: contratos de `OCREngine`
   y `StructureMapper`, flujo de datos ingesta → OCR → review → export, cómo conviven
   backend y frontend, cómo se hace el streaming. Para cada decisión: qué eliges, las
   alternativas que descartas, y por qué.
2. **Árbol de archivos completo** — cada módulo/carpeta con una línea de responsabilidad.
   Justifica los límites entre módulos (qué NO debe saber cada uno del otro).
3. **Riesgos y puntos frágiles** — auth de suscripción de Claude, calidad OCR del manuscrito,
   VRAM de 8 GB. Una mitigación por riesgo.

No escribas implementación en esta fase. El primer entregable es **el plan, no el código**.

---

## 3. Configuración del repo (con mis directrices globales)

Aplica mis convenciones globales para inicializar el repo: gestor `uv`, layout
`backend/` + `frontend/`, linting/formato según mi global CLAUDE.md, `.gitignore` sensato,
y `pre-commit` si mi global lo pide. `providers.toml` para configurar los backends.
**No inventes** convenciones nuevas: usa las mías. Si mi global no cubre algo, propón y
espera confirmación.

**Genera tú el `CLAUDE.md` de proyecto** (en la raíz): las convenciones específicas de este
repo, derivadas de mi global + este brief. Es tu entregable, no lo escribo yo.

**Reescribe el README**: El que tenéis es fiel en contenido pero suena demasiado "LLM-made".
Reescribelo manteniendo toda la info (scope, features, tech stack, trademark disclaimer),
pero con tono más natural, auténtico, menos corporativo. Como lo escribiría un developer
de verdad, no una IA. Esto es importante.

---

## 4. Principios de producto (esto NO se negocia)

1. **Todo por botones, nada programático para el usuario.** Elegir proveedor, cargar/cambiar
   modelo (incl. `ollama pull`), seleccionar local↔cloud, lanzar OCR, exportar al vault:
   **todo desde la UI**. El usuario nunca edita config ni toca terminal para el uso diario.
2. **Una sola interfaz, todo-en-uno.** Una app, un flujo claro: cargar cuaderno → revisar →
   exportar. Sin paneles dispersos ni menús anidados.
3. **Simple por encima de completo.** Es un proceso rápido. Si dudas entre dos caminos,
   elige el más corto y obvio.

---

## 5. Alcance: MVP y NO-objetivos

**Dentro del MVP:**
- Ingesta desde una carpeta local (Drive sincronizado).
- **Importar archivos sueltos**: subir un PDF directamente a la app (drag & drop), además de la carpeta.
- Un backend local (Ollama o LM Studio) + un backend cloud (Gemini o Claude) funcionando.
- Review UI imagen↔markdown con corrección manual.
- Export con `mirror` + una segunda estrategia (`tags` o `wikilinks`).
- Gestión de modelos por botones.

**Fuera del MVP (NO lo construyas aunque se te ocurra):**
- ❌ Soporte multi-dispositivo (reMarkable, Boox) — más adelante.
- ❌ Las cuatro estrategias de mapeo a la vez — empieza con dos.
- ❌ Cuentas/usuarios, login, multi-tenant.
- ❌ Fine-tuning de modelos, colas distribuidas, batch masivo.
- ❌ Cualquier "y ya que estamos, podríamos…". Si lo piensas, anótalo en `BACKLOG.md` y sigue.

> Regla de oro: ante la duda entre añadir o no una feature, **no la añadas**. Pregúntame.

---

## 6. Qué espero de ti en el primer turno

1. Confirmación de que cargaste la memoria global + lista de skills que usarás.
2. Borrador de `ARCHITECTURE.md` y árbol de archivos (sección 2), para que lo revise.
3. Propuesta del `CLAUDE.md` de proyecto (lo redactas tú).
4. **README reescrito**: mismo contenido, pero con tono más natural y auténtico. Sin sonar a IA.
5. Cualquier pregunta o decisión que necesites de mí antes de seguir.

**Nada de código hasta que apruebe el plan.**
