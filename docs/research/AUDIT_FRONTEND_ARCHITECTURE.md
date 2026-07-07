# Frontend & Architecture Audit — marginalia

**Status: read-only audit, 2026-07-07. Findings only, no code changed.**
**Scope:** `frontend/src/` (all files), the backend↔frontend contract, and feasibility of the
post-MVP feature list. Backend internals are owned by a separate audit; they appear here only
where the *contract* forces a shared decision (flagged `AR-…`).

Every non-trivial claim cites `file:line` against the code as of commit `cf87c33`.

---

## 1. Framing — what this frontend is today

marginalia's frontend is a deliberately small, single-flow SPA: ~2,900 lines of TypeScript
across 16 files, no router, no state library, no server-state cache. `App.tsx` owns a
three-value step machine (`"import" | "review" | "export"`, App.tsx:33) and conditionally
renders exactly one step (App.tsx:246-268). Server communication is a hand-rolled typed
client (`api/client.ts`) plus one SSE channel for live OCR (`lib/sse.ts` +
`lib/useJobStream.ts`). Styling is Tailwind + CSS custom properties (index.css:17-33), motion
is GSAP with a `prefers-reduced-motion` guard on step transitions (App.tsx:50-52, 97-100).

The verdict at a glance: **the architecture is right-sized and the boundaries are clean** —
this matches the "one interface, one flow" decision in docs/ARCHITECTURE.md §5 and the app
honestly resists over-engineering (e.g. the `ponytail:` comment explaining why streaming text
skips the Markdown pipeline, MarkdownEditor.tsx:133-138). The problems are not structural
bloat; they are the opposite: **a handful of under-implemented edges in the save/stream
lifecycle that can silently lose user edits (§3 P0 items, §4), and a model-loading UX that
throws away progress data the backend already streams (§5)**. The prior audit's 16/20 with
"performance" as the weak dimension is confirmed, but the streaming re-render issue turns out
to be the *third* most important finding — two data-loss paths in Review rank above it.

Contract verification against CLAUDE.md §6:

| Claim (CLAUDE.md) | Verified | Where |
|---|---|---|
| Dev: Vite :5173 proxies `/api` → :8000 | ✅ | vite.config.ts:7-13 |
| Errors are `{ detail }` + status | ✅ both sides | client.ts:134-143 ↔ jobs.py:58,83,96 |
| SSE `GET /api/jobs/{id}/stream`, events `page_started/page_delta/page_done/job_done/error` | ✅ shapes match exactly | sse.ts:15-20 ↔ backend `jobs/service.py:34-48` |
| camelCase in the frontend | ⚠️ **partially false** | API types mirror wire snake_case (`job_id`, `rel_path`, `vault_path`… client.ts:13-98) and leak into components (Review.tsx:60 `job.status`, Export.tsx:73 `vault_path`). See AR-03. |
| Auth: none; Claude state as data | ✅ | ProviderPicker renders `unknown` state honestly (ProviderPicker.tsx:448-462) |

---

## 2. Current state — how each piece actually works, and where it is fragile

### 2.1 App shell (`App.tsx`)

- Bootstraps settings + provider status once via `Promise.allSettled` so the UI renders even
  with the backend down (App.tsx:83-87). Good resilience instinct — but the failure leaves
  `status === null` forever with no retry and no user-visible signal (see FE-08).
- Step transitions animate via GSAP and move focus into the new step container for
  keyboard/SR users (App.tsx:97-120) — genuinely good a11y work.
- `handleProviderSelect` (App.tsx:170-174) awaits two round-trips (`selectProvider` +
  `getProvidersStatus`) with **no try/catch and no busy state**; a backend hiccup here is an
  unhandled promise rejection from `ProviderRow.handleRowClick` (ProviderPicker.tsx:129-135).
- Theme is initialised **twice** — once in App's mount effect (App.tsx:75-80) and once inside
  `ThemeToggle`'s initial state + effect (ThemeToggle.tsx:9-25) — and both run *after* first
  paint (index.html:1-19 has no inline script), so dark-theme users get a light flash on load.
- Fragility: `activeJob` is the only cross-step state (App.tsx:43-47, 58). Every step
  unmounts completely on navigation (App.tsx:246-268), which resets Import's scan list,
  Export's form — and, far more seriously, **re-triggers OCR when Review remounts** (§2.3,
  FE-03).

### 2.2 API client (`api/client.ts`)

- Two-layer design (`apiFetchRaw` for transport errors + detail extraction, `apiFetch<T>` for
  JSON) is clean and matches the error contract (client.ts:126-168). Network failure maps to
  `ApiError(0, "Cannot reach the backend — is it running?")` — a good product-voice error.
- **Latent header bug:** `apiFetch` builds `{ headers: {merged}, ...init }`
  (client.ts:159-162). Because `...init` spreads *after* `headers`, any caller that ever
  passes `init.headers` silently discards the merged `Content-Type`. No current caller does,
  so it's dormant — but it is exactly the kind of landmine that costs an hour later (FE-15).
- Types are **hand-maintained mirrors** of `backend/marginalia/api/schemas.py` with a blind
  cast: `response.json() as Promise<T>` (client.ts:167). Today they match field-for-field
  (verified: `Settings`↔settings, `ProviderStatus`↔schemas.py:35-49, `JobState`↔schemas.py:94-100).
  Nothing prevents drift (AR-03).
- `updatePageMarkdown` is typed `Promise<void>` (client.ts:289-298) but the backend PUT
  actually returns the saved `JobPageOut` (jobs.py:72-85). Harmless today; the discarded
  response is exactly what a save-reconciliation fix would want (see FE-01).
- `pullModel` **drains the progress stream into the void**: `await response.text()`
  (client.ts:237-239) while the backend emits `{status, percent}` SSE frames per pulled layer
  (`models_admin.py:103-118`). This is the root of the pull-UX gap (§5, FE-06).

### 2.3 SSE layer (`lib/sse.ts`, `lib/useJobStream.ts`) and Review (`steps/Review.tsx`)

The transport is tidy: `connectJobStream` owns the `EventSource`, parses frames, closes on
terminal events, and *deliberately disables* EventSource auto-reconnect (sse.ts:56-61) —
correctly, because reconnecting would re-trigger OCR (see below). `useJobStream` uses the
ref-latching pattern so callback identity never re-runs the effect (useJobStream.ts:27-31).
One smell: `sse.ts` re-exports the hook it is imported by (sse.ts:71 ↔ useJobStream.ts:10), a
circular module reference kept only for import compatibility (FE-20).

Review's lifecycle, as actually implemented:

1. Mount → `getJob` restores pages from disk (Review.tsx:70-87); failure is swallowed with
   "start with empty pages" (Review.tsx:83-85).
2. Once `initialLoading` flips false, the stream opens **unconditionally** —
   `useJobStream(initialLoading || stopped ? null : jobId, …)` (Review.tsx:127-128) does
   *not* check `jobDone`.
3. On the backend, `GET /jobs/{id}/stream` **is the OCR trigger**: the route feeds
   `run_ocr(store, engine, job_id)` straight into the response (jobs.py:62-69), and `run_ocr`
   loops **every** page with no `done` skip (`jobs/service.py:33-41`), persisting fresh OCR
   over whatever markdown is on disk (`service.py:40`).

Combined, this yields the audit's most serious finding chain:

- **Any Review remount on a finished job re-runs the whole OCR and overwrites the user's
  edits on disk** (FE-03/AR-01). The "Back to Review" buttons in Export (Export.tsx:124-126,
  242-244) make this a one-click path: review → edit pages → export → "Back to Review" →
  edits destroyed by re-OCR, plus visible text duplication in the UI because `page_delta`
  *appends* to the restored markdown (Review.tsx:102-109) and nothing resets it on
  `page_started` (Review.tsx:93-101).
- ARCHITECTURE.md §4's claim that "a dropped connection resumes from disk"
  (docs/ARCHITECTURE.md:95-96) is **not implemented** — persistence exists, resume does not.
- A network drop mid-OCR fires `onError → close → onClose`, and Review's `onClose`
  unconditionally sets `jobDone = true` (Review.tsx:130-133), so the header shows
  "OCR complete" (Review.tsx:211-212) and the Export button unlocks (Review.tsx:250) with
  half-transcribed pages (FE-04).

The auto-save path has two independent data-loss bugs:

- **FE-01 — the last edit in any burst is never saved.** `scheduleSave` reads the markdown
  from the *render-closure* `pages` (Review.tsx:145) — the state **before** the keystroke
  that triggered it, because `handleMarkdownChange` calls `setPages` and then `scheduleSave`
  in the same closure (Review.tsx:168-173). Every keystroke schedules a save of the
  *previous* value; the final keystroke (or an entire paste that lands as one change event)
  is silently dropped from disk while the UI shows it. The comment at Review.tsx:143-145
  states the correct intent — the implementation does the opposite.
- **FE-02 — unmount discards pending saves.** The cleanup effect clears all timers without
  flushing (Review.tsx:177-182). Typing and clicking "Export →" within the 800 ms debounce
  window exports the stale text.

What Review does *well*: `PageTabs` is memoised with a purpose-built comparator that ignores
`markdown` so streaming tokens don't re-render the tab strip (Review.tsx:342-384);
`savingPages` is state, not a ref, precisely so the "Saving…" chip re-renders
(Review.tsx:64-66); Stop is implemented via `stopped → jobId null → EventSource close`, which
cancels the server generator by disconnect (Review.tsx:56-58) — a clean use of the transport.

### 2.4 MarkdownEditor (`components/MarkdownEditor.tsx`)

Click-to-edit with a real reason for not making the preview a button (links inside rendered
Markdown; MarkdownEditor.tsx:81-84) and an explicit Edit button for keyboard/AT users
(MarkdownEditor.tsx:88-97). Streaming pages render a raw `<pre>` instead of the remark
pipeline (MarkdownEditor.tsx:139-145) — the right cost dodge, documented with a `ponytail:`
comment. The component is **not memoised** and its `onChange` prop is recreated inline every
Review render (Review.tsx:314), which is the mechanical core of the streaming re-render issue
(§4). Also: the streaming `<pre>` never auto-scrolls, so on long pages the newest OCR text
streams in below the fold.

### 2.5 Import (`steps/Import.tsx`)

Solid two-panel step with real loading/empty/error states in the scan card
(Import.tsx:257-303) and an auto-scan on mount (Import.tsx:134-152). Fragilities:

- **Duplicate settings ownership**: Import re-fetches `getSettings()` (Import.tsx:139-143)
  even though App already holds `settings` (App.tsx:61); Import's `updateSettings` for
  `scan_folder` (Import.tsx:116) leaves App's copy stale. Harmless today (App's copy only
  feeds vault_path/strategies to Export) but a drift trap (FE-11).
- `applyScanFolder` swallows the save error entirely ("Silently ignore", Import.tsx:118-121)
  then re-scans anyway — the user gets a scan error for a *settings* failure.
- Classic drag-flicker: `onDragLeave` on the container fires whenever the cursor crosses a
  child, toggling `dragging` (Import.tsx:175-176) (FE-19).
- `uploading` is shared between the drop zone and the scanned list (Import.tsx:34, 97, 283) —
  fine at this scale, and it correctly disables double-submission.

### 2.6 Export (`steps/Export.tsx`)

Clear form → success-screen state machine. Fragilities:

- **Nothing persists.** A chosen vault path and strategy toggles are used for the one export
  (Export.tsx:71-76) and never written back via `updateSettings`, so every session (and every
  App remount) starts from the last *externally* saved settings. For a daily-use tool this is
  a recurring paper cut (FE-09).
- Initial state is a snapshot: `useState(settings?.vault_path ?? "")` (Export.tsx:28) — if
  settings hadn't loaded when Export mounts, the field stays empty even after they arrive.
  Low probability (Export is reached late) but a freebie fix while doing FE-09.
- `StrategyToggle` renders a nice accessible checkbox pattern (role, aria-checked, keyboard —
  Export.tsx:287-298), but the list is hardcoded to exactly two entries (Export.tsx:223-238);
  see FE/AR future-features §6.2.

### 2.7 ProviderPicker and the model flow — summarized here, deep-dived in §5

State model is right: `ProviderState = ready | no_model | unreachable | needs_key | unknown`
(client.ts:34-39) drives a dot + hint per row (ProviderPicker.tsx:140-152, 448-462), and the
three action panels (Load/Pull/Key) mount lazily per row (ProviderPicker.tsx:175-216). The
gaps are freshness (status fetched once at App mount, App.tsx:83-87), progress (pull), dead
UI when the backend is down (`open && status &&` renders nothing, ProviderPicker.tsx:74), and
feedback during slow operations.

### 2.8 Shared components

`Spinner` (role="status", Spinner.tsx:18), `ErrorBanner` (role="alert", ErrorBanner.tsx:13),
`PanelError`, `StepIndicator` (nav + aria-label, StepIndicator.tsx:27), `SuggestionChips`,
`ThemeToggle`, `OnboardingModal` (manual focus trap + Esc + backdrop close,
OnboardingModal.tsx:346-374, 419-433). Quality is high for a hand-rolled set. Two nits:
`SuggestionChips` puts `role="listitem"` on `<button>`s inside a `role="list"` div
(SuggestionChips.tsx:20-24) where a plain `<ul>/<li>` would be both simpler and correct; the
OnboardingModal's GSAP entrance/step/exit animations never check `prefers-reduced-motion`
(OnboardingModal.tsx:310-324, 335-341, 386-399) although App's transitions do (FE-18).

### 2.9 Tests

**There are zero frontend tests.** `package.json` has no test script and no test framework
(package.json:6-12, 23-39); the only Playwright usage is the `shot.mjs`/`demo.mjs` dev
tooling. All of the P0 bugs above (stale-closure save, unmount flush, stream-close ≠ done)
are precisely the kind of logic that a pure reducer + vitest would have caught (FE-14).
Roadmap #9 (E2E) and #10 (ESLint flat config — the config exists, eslint.config.js) remain
the open infra items.

---

## 3. Improvement opportunities

Priority: P0 = data loss / correctness now · P1 = important UX or Víctor-named priority ·
P2 = hygiene that will bite · P3 = polish. Effort: S < ½ day · M = 1–2 days · L = multi-day.

### 3.1 Index

| ID | Title | Prio | Effort | Anchor | Future link |
|---|---|---|---|---|---|
| FE-01 | Debounced save persists stale markdown — last edit lost | P0 | S | Review.tsx:138-150 | — |
| FE-02 | Unmount/export discards pending saves | P0 | S | Review.tsx:177-182 | — |
| FE-03 | Review remount re-opens stream → re-OCR overwrites edits | P0 | S(front)+M(AR-01) | Review.tsx:127-134 | Batch, resume |
| AR-01 | `GET /stream` is a side-effecting OCR trigger; no resume | P0 | M | jobs.py:62-69, service.py:33-41 | **Blocks batch** |
| FE-04 | Stream close treated as "job done" — export unlocks on partial OCR | P1 | S | Review.tsx:130-133 | Resume UX |
| FE-05 | Streaming re-renders re-run the remark/KaTeX pipeline | P1 | M | Review.tsx:102-109, MarkdownEditor.tsx:155-165 | Batch (N jobs streaming) |
| FE-06 | Pull progress discarded — blind multi-GB downloads | P1 | M | client.ts:231-240, ProviderPicker.tsx:399-401 | Model UX (Víctor #1) |
| FE-07 | Provider status fetched once, never refreshed | P1 | S | App.tsx:83-87 | Model UX |
| FE-08 | Backend down → picker opens to nothing (dead click) | P1 | S | ProviderPicker.tsx:74 | Model UX, packaging |
| FE-09 | Vault path / strategies never persisted after export | P1 | S | Export.tsx:64-83 | Templates, batch |
| FE-10 | Provider select: no busy state, unhandled rejection | P1 | S | App.tsx:170-174 | Model UX |
| AR-02 | SSE event envelope inconsistent (job events have `type`, pull events don't) | P1 | S | sse.ts:15-20 vs models_admin.py:118 | Unblocks FE-06 cleanly |
| FE-11 | Settings state duplicated App/Import — drift trap | P2 | S | Import.tsx:139-143 vs App.tsx:61 | Drive pull settings |
| FE-12 | `getJob` failure swallowed → fake "complete" on empty job | P2 | S | Review.tsx:83-85 | — |
| FE-13 | No error boundary — render error blanks the SPA | P2 | S | main.tsx:6-10 | — |
| FE-14 | Zero frontend tests; SSE reducer untestable inline | P2 | M | Review.tsx:91-124, package.json:6-12 | All future features |
| FE-15 | `apiFetch` spread order lets `init.headers` clobber Content-Type | P2 | S | client.ts:159-162 | — |
| FE-16 | LoadPanel copy contradicts backend auto-start; no spinner during ~2 min load | P2 | S | ProviderPicker.tsx:250-254 vs providers.py:146-149 | Model UX |
| FE-17 | Theme applied post-paint (FOUC) + duplicated init logic | P2 | S | App.tsx:75-80, ThemeToggle.tsx:9-25, index.html | — |
| FE-18 | OnboardingModal ignores `prefers-reduced-motion` | P2 | S | OnboardingModal.tsx:310-324, 386-399 | — |
| AR-03 | Hand-maintained contract types; camelCase rule contradicted | P2 | S | client.ts:13-98, CLAUDE.md §6 | All features touching the API |
| AR-04 | `/providers/status` probes are serial + blocking (up to ~4 s × N) | P2 | M (backend) | providers.py:75-81, models_admin.py:18 | Model UX responsiveness |
| AR-05 | Server-state strategy: lift-to-App now vs TanStack Query later | P2 | S→M | App.tsx:60-62 | Batch, search, Drive |
| FE-19 | Drag-flicker on drop-zone child hover | P3 | S | Import.tsx:175-176 | — |
| FE-20 | Circular re-export sse.ts ↔ useJobStream.ts | P3 | S | sse.ts:71, Review.tsx:22 | — |
| FE-21 | No model picker for cloud providers (default model only) | P3 | S | providers.py:110, ProviderPicker.tsx:129-135 | Model UX |
| FE-22 | KaTeX + react-markdown in the main bundle | P3 | M | MarkdownEditor.tsx:21-25 | — |
| FE-23 | A11y polish batch (aria-expanded on rows, list semantics, aria-live for progress, streaming auto-scroll) | P3 | S | ProviderPicker.tsx:142-153, SuggestionChips.tsx:20-24 | — |

### 3.2 The P0 items in detail

**FE-01 — pass the value you already have.** `handleMarkdownChange(pageIndex, value)`
receives the fresh text (Review.tsx:168) but `scheduleSave` re-derives it from the stale
render closure (`pages.find(...)`, Review.tsx:145). Change the signature to
`scheduleSave(pageIndex, markdown)` and pass `value` through — a three-line diff that closes
a silent data-loss hole (the exported file diverges from what the user sees; a paste that
replaces a page in one change event loses the *entire paste*). No simpler alternative exists;
this *is* the simplest fix.

**FE-02 — flush, don't discard.** Keep a `pendingSaves: Map<number, string>` ref updated in
`scheduleSave`; on cleanup, iterate it and fire `updatePageMarkdown` for each entry instead
of only `clearTimeout` (Review.tsx:177-182). Also flush before `onExport` fires so
"type → Export" inside the debounce window can't export stale text. (Alternative considered:
keep Review mounted across steps with CSS hiding — heavier, changes App's render model, and
still wouldn't cover tab-close; the flush is the right size.)

**FE-03 / AR-01 — the stream must stop being the trigger.** Two layers:

- *Frontend guard (S, ships alone):* track the fetched job status and never open the stream
  when it is terminal — e.g. a `shouldStream` state set in the `getJob` handler
  (Review.tsx:70-87), used in the hook condition (Review.tsx:127-128). Additionally, on
  `page_started` reset that page's markdown to `""` (Review.tsx:93-101) so that *any* re-run
  (including mid-job remounts, which the guard can't prevent) replaces text instead of
  appending duplicates.
- *Contract fix (M, coordinate with the backend agent):* either make `run_ocr` skip pages
  with `done=True` (true "resume from disk", making ARCHITECTURE.md:95-96 honest — smallest
  change), or properly decouple `POST /jobs/{id}/start` from an idempotent, read-only
  `GET /stream`. The decoupled shape is what **batch** needs anyway (§6.1): a queue worker
  owns OCR; streams only observe. Recommendation: do the skip-done fix now (small, honest),
  adopt start/stream separation as part of the batch feature, not before (YAGNI).

Decision table for AR-01:

| Option | Effort | Fixes re-OCR | Enables resume | Enables batch | Verdict |
|---|---|---|---|---|---|
| Frontend guard only | S | Only for terminal jobs | No | No | Do now regardless |
| Backend: skip `done` pages in `run_ocr` | S | Yes (all remounts) | Yes | No | Do now |
| `POST /start` + observer `GET /stream` | M | Yes | Yes | **Yes** | Do with batch |

### 3.3 State management (AR-05) — decision, not dogma

Today: App owns `settings`/`status` (App.tsx:60-62), Import re-fetches settings
(Import.tsx:139-143), Export snapshots them (Export.tsx:28-32), ProviderPicker fetches
loadables per panel (ProviderPicker.tsx:229-233). That's four ownership styles for one small
app — but adopting a query library *today* would be over-engineering.

| Approach | Cost | When it pays |
|---|---|---|
| **Lift settings fully to App** (pass `settings` + `onSettingsChange` to Import like Export already gets, App re-fetches after Import saves) | S | Now — kills FE-11 with ~20 lines |
| TanStack Query for settings/status/job | M | When **batch** or **Drive pull** land (multiple consumers, background refetch, invalidation) |
| Zustand/context store | M | Never at this scale — no shared client state exists beyond `activeJob` |

Recommendation: do the lift now; write "adopt TanStack Query when batch lands" into the
roadmap so the decision is made once.

---

## 4. Streaming-performance deep-dive (the 16/20 weak dimension)

### 4.1 The mechanics, from the code

Every `page_delta` frame takes this path:

1. `EventSource.onmessage` → `JSON.parse` → `handlers.onEvent` (sse.ts:38-47). Each SSE
   frame is its own browser task, so React 18's automatic batching cannot merge two frames:
   **render rate = token rate**.
2. `handleSseEvent` → `setPages(prev => prev.map(...))` (Review.tsx:102-109): a new array and
   a new object for the streaming page **per token**. The `p.markdown + event.text`
   concatenation is O(page length) per token — quadratic over a page, but at handwritten-page
   sizes (a few KB) this is noise, not the problem.
3. `Review` re-renders. `PageTabs` bails out via its comparator (Review.tsx:342-384) — the
   one deliberate optimisation, and it works. Everything else re-renders: header, progress
   bar, the `<img>`, and — critically — `MarkdownEditor`, which is **not memoised** and whose
   `onChange` is a fresh inline closure every render (Review.tsx:314), so `memo` alone
   wouldn't even help yet.

### 4.2 Where the actual cost is

Three viewing scenarios during an OCR run, in increasing severity:

| User is viewing… | What re-renders per token | Cost |
|---|---|---|
| The streaming page | `StreamingText` `<pre>` (MarkdownEditor.tsx:139-145) | Cheap by design (the `ponytail:` dodge works); text-node update + reflow of a growing block |
| A **done** page (preview) while another streams | `MarkdownBody` → `ReactMarkdown` with remark-gfm + remark-math + rehype-katex (MarkdownEditor.tsx:155-165) | **The real problem.** react-markdown v9 runs the full unified pipeline synchronously on every render — no internal memoisation. A math-heavy page costs ~5–40 ms to re-parse; at a local model's 15–40 tok/s that is 100 ms–1.6 s of main-thread work *per second*: visible jank exactly while the user proof-reads |
| A done page in **edit** mode | Controlled `<textarea>` re-render | Cheap, but every keystroke now competes with token-rate renders of the whole step |

So the streaming page itself was already handled; the regression is *cross-page*: OCR of page
5 re-runs KaTeX for page 1 on every token because nothing between `setPages` and
`ReactMarkdown` breaks the render chain.

### 4.3 The fix — two small moves, no new dependencies

**Move 1 (biggest win, S): break the render chain at the editor boundary.**

- Stabilise the handler: `const handleMarkdownChange = useCallback((pageIndex, value) => …,
  [])` and pass `pageIndex` down (or bind per `activePage` with `[activePage]` deps).
- Wrap the editor: `export const MarkdownEditor = memo(function MarkdownEditor(…) {…})`.
- Belt-and-braces: `const MarkdownBody = memo(function MarkdownBody({ markdown }) {…})`
  (MarkdownEditor.tsx:155) so even in-editor state changes (hover → Edit button opacity is
  CSS-only, but `editing` toggles are not) never re-parse unchanged markdown.

After this, a token for page 5 while viewing page 1 re-renders: Review's header + progress
bar + two bailed-out memo children. The KaTeX pipeline runs exactly once per page completion.

**Move 2 (S/M): decouple render rate from token rate with a rAF buffer.**

In `Review` (or as an option inside `useJobStream`), accumulate `page_delta` text in a
`useRef<Map<number, string>>` and flush once per animation frame (or a 100 ms timer —
`requestAnimationFrame` is simpler and naturally pauses in background tabs):

```
page_delta → buffer.set(i, (buffer.get(i) ?? "") + text); scheduleFlush();
flush()    → setPages(prev => apply buffer); buffer.clear();
```

This caps state updates at ≤ 60/s regardless of token rate, batches the string
concatenations, and makes the `<pre>` reflow per-frame instead of per-token. ~20 lines.

**Explicitly not recommended** (over-engineering for one user, ≤ dozens of pages): moving
page markdown out of React state into an external store; virtualising the tab strip;
`useDeferredValue` on the preview (the memo boundary is deterministic and cheaper to reason
about); web-worker markdown parsing.

**How to verify:** React DevTools Profiler while OCR-ing a 5+ page notebook and viewing a
done math page — before: committed render per token with `MarkdownBody` in the flame graph;
after: `MarkdownEditor` greyed out ("did not render"). A `frontend/scripts/` Playwright run
recording `performance.now()` deltas around a canned SSE replay would make this a regression
test (pairs with FE-14).

---

## 5. Model-loading UX deep-dive (Víctor priority #1)

### 5.1 What exists — a fair inventory

The Sprint-4 foundation is genuinely in place and better than the roadmap snapshot suggests:

- Real per-provider state with dot + hint, driven by `GET /api/providers/status`
  (ProviderPicker.tsx:140-152; states client.ts:34-39). The fake "Claude authenticated" is
  gone — Claude reports honest `ready`/`unknown` via a presence probe (providers.py:99-105).
- Per-state actions on the row: **Load** (LM Studio headless list + load,
  ProviderPicker.tsx:223-280), **Pull** (Ollama by name with recommended-model chips,
  ProviderPicker.tsx:330-405), **Add key** (Gemini, ProviderPicker.tsx:284-326). Each panel
  has its own error line (`PanelError`) and empty state ("No downloaded models…",
  ProviderPicker.tsx:257-259).
- The app never assumes a model is installed: lists come from the runtime
  (`/providers/{id}/loadable`, `status.models`), and a 503 from `loadable` carries the
  human "open LM Studio" message straight into the panel (providers.py:144-149 →
  ProviderPicker.tsx:229-233).

### 5.2 The gaps, ranked

| # | Gap | Evidence | Consequence |
|---|---|---|---|
| 1 | **Pull is a black box.** Backend streams `{status, percent}` per layer (models_admin.py:103-118, `_percent` 121-126) but the client drains the body (client.ts:237-239) and the UI shows static "Pulling… this can take a while" (ProviderPicker.tsx:399-401) | A `qwen3-vl:4b` is a multi-GB download — minutes of dead UI; users assume a hang and kill the app | The single highest-value model-UX fix |
| 2 | **Status goes stale.** Fetched once at App mount (App.tsx:83-87); `refreshProviders` runs only after select/load/key/pull actions (App.tsx:161-168, ProviderPicker.tsx:190-215) | Start Ollama *after* opening marginalia → the row says "unreachable" forever; user concludes the app is broken | First-run killer |
| 3 | **Backend down = dead click.** Panel body requires `status` truthy (ProviderPicker.tsx:74); after a failed bootstrap the toggle is enabled but opens nothing | In the packaged "daily app" scenario (backend not yet started) the most important control silently no-ops | |
| 4 | **No busy feedback on select.** `handleRowClick` awaits `onSelect` → 2 round-trips incl. a status refresh whose backend probes are serial with 4 s timeouts each (providers.py:75-81, models_admin.py:18) | Multi-second frozen popover; double-clicks fire concurrent selects; failures reject unhandled (App.tsx:170-174) | |
| 5 | **Copy contradicts behavior.** LoadPanel asserts LM Studio "can't be started automatically" (ProviderPicker.tsx:250-254) while the backend *tries* headless start and its own errors say "couldn't be started automatically" as a fallback (providers.py:146-149, 168-174) | Users skip the Load button believing they must alt-tab first | |
| 6 | Long loads look dead: `loadModel` legitimately takes up to ~2 min (client.ts:206-212); the row shows a static "Loading…" text (ProviderPicker.tsx:269-271) with no spinner/elapsed indication; the whole app has no aria-live announcement of completion | | |
| 7 | Recommended-model chips (ProviderPicker.tsx:330, 365-376) carry no size/VRAM hint — the 8 GB-VRAM risk in ARCHITECTURE.md §11.3 is undocumented at the point of choice | | |
| 8 | No pull cancel; closing the popover keeps the fetch alive invisibly (and the panel unmounts, losing even the "Pulling…" text) | | |

### 5.3 Target flow (the fix set, in order)

1. **FE-06 — streamed pull progress (M).** Replace `pullModel`'s `response.text()` with a
   `ReadableStream` reader + `TextDecoder`, split on `\n\n`, parse `data:` frames, invoke
   `onProgress({status, percent})`. PullPanel renders a thin progress bar (reuse the Review
   progress-bar pattern, Review.tsx:217-237) + the status line ("pulling manifest",
   "downloading 43%…"), keeps the panel mounted while pulling (hoist pull state up to
   `ProviderRow` or module scope so closing/reopening the popover doesn't orphan it), and
   adds `aria-live="polite"` on the status text. Prereq: **AR-02** — give pull events the
   same `{type: …}` envelope as job events so the client can share one SSE frame parser
   (today `sse.ts`'s parser is EventSource-bound and its `SseEvent` union doesn't cover pull
   frames; extract a `parseSseFrame` used by both).
2. **FE-07 — freshness (S).** Refetch status when the popover *opens* (event-driven beats an
   interval — ponytail) plus a manual refresh button in the panel header. If that feels
   insufficient in practice, add a 15 s interval *only while the popover is open*. Show a
   subtle inline spinner during refresh so slow probes (gap 4) read as activity.
3. **FE-08 — backend-down panel (S).** When `status === null`, render a panel body with the
   `ApiError(0)` message ("Cannot reach the backend — is it running?") and a Retry button
   wired to `onRefresh`.
4. **FE-10 — select busy-state + error (S).** Per-row `busy` flag disabling the row, spinner
   in place of the check, try/catch in `handleProviderSelect` surfacing a `PanelError`.
5. **FE-16 — copy + load feedback (S).** Reword LoadPanel to "marginalia will try to start
   LM Studio headless; if that fails, open the app once"; add `Spinner size="sm"` +
   "can take ~2 min" while loading; disable *all* row actions during a load.
6. **FE-21 + chips (S).** Add size hints to the recommended chips ("qwen3-vl:4b · ~4 GB ·
   needs ~6 GB VRAM"), sourced as a hardcoded const next to `RECOMMENDED_MODELS`
   (ProviderPicker.tsx:330) — no API needed.

With 1–4 shipped, the picker meets the brief's bar ("everything by buttons, zero terminal"):
every state is visible, every action gives feedback, and no state can strand the user.

---

## 6. Future-features feasibility

Source list: BACKLOG.md:23-36 + memory plan (2026-06-28). For each: how it lands in *this*
frontend, what it needs, effort (frontend / whole-feature).

### 6.1 Batch — process multiple notebooks at once

**Feasibility: good, but gated on AR-01.** The current model (stream = trigger; one
`activeJob`, App.tsx:43-47) cannot express "three jobs queued, one running".

- **Contract:** `POST /jobs/{id}/start` (queue) + idempotent `GET /stream` (observe), or one
  multiplexed `GET /api/events` for all jobs. A `GET /jobs` listing endpoint (none exists
  today — only `GET /jobs/{id}`, jobs.py:47-50); the on-disk store can serve it by readdir,
  no DB needed yet (BACKLOG.md:17 keeps SQLite parked — correct).
- **UI placement:** Import's scanned list (Import.tsx:277-293) gains checkboxes + a
  "Transcribe all (N)" button; a queue drawer/strip under the header shows per-job status
  chips; Review gains a job switcher (a select next to the job name, Review.tsx:204) reusing
  the existing per-job page state. `ActiveJob` becomes `jobs: ActiveJob[]` + `currentJobId`.
- **Perf note:** N jobs streaming simultaneously multiplies the §4 token rate — do FE-05
  first, and prefer *sequential* queue execution server-side (single-GPU local runtimes
  serialize anyway).
- **Effort:** frontend M–L; whole feature L. **Do AR-01's start/stream split as the first PR
  of this feature.**

### 6.2 Mapping strategies `tags` + `dataview`

**Feasibility: trivial by design — the contract already carries it.** `strategies` is
`string[]` end-to-end (client.ts:96, schemas.py:114); Export's toggles are the only
hardcoded part (Export.tsx:223-238).

- **UI:** replace the two literal `<StrategyToggle>`s with a mapped
  `const STRATEGIES: {id, label, description, locked}[]` — done. Optionally fetch a
  `GET /api/strategies` catalogue later; a const is enough while strategies ship with the app
  (ponytail).
- **Effort:** frontend S; backend one function per strategy behind the existing
  `StructureMapper` contract (docs/ARCHITECTURE.md §3). Pairs with FE-09 (persist chosen
  strategies).

### 6.3 Custom export templates (Jinja2)

**Feasibility: good; first feature to grow the Export step.**

- **Contract:** `GET/PUT /api/templates` (list/save under `data/templates/`),
  `template_id?: string` added to `ExportBody` (schemas.py:109-114), and ideally
  `POST /api/templates/preview` (render sample page → markdown) for a preview pane.
- **UI:** a "Template" section in Export between strategies and actions: a select
  (default = built-in `note.md.j2`) + "Edit" opening a modal with a plain `<textarea>`
  (monospace, like the vault input). **Not** `MarkdownEditor` — it renders Markdown; a Jinja2
  source needs a raw editor. Preview on demand, not live (keep it S).
- **Effort:** frontend M; whole feature M.

### 6.4 Full-text search across exports

**Feasibility: fine, but it is the first non-linear surface — choose the shell carefully.**

| Shell | Cost | Fit |
|---|---|---|
| **Cmd+K / header-button search modal** | S shell | Preserves "one interface, one flow" (ARCHITECTURE §5); no router; recommended |
| Dedicated route + react-router | M shell | Only worth it if search grows into a browse/library view |

- **Contract:** `GET /api/search?q=` scanning vault `.md` files on demand (single user, local
  disk — a scan is fine; add SQLite FTS5 only if latency proves it, per BACKLOG's own rule).
- **UI win:** result rows deep-link with Obsidian's URI scheme
  (`obsidian://open?vault=…&file=…`) so a click lands in Obsidian — cheap, delightful.
- **Effort:** frontend M; whole feature M–L (backend indexing choices dominate).

### 6.5 Scheduled pull from Google Drive

**Feasibility: backend-dominant (OAuth + scheduler + watcher, BACKLOG.md:14-15's parked
`watchfiles`); frontend impact is mostly a settings problem.** Today settings surface is
scattered (scan folder inline in Import, vault in Export, provider in the header). This
feature is the trigger to consolidate a **Settings modal** (gear next to Guide, App.tsx:217)
holding: scan folder, vault path, schedule, provider keys. Don't build the modal before this
feature needs it. Frontend M once backend exists; whole feature L.

### 6.6 Scribe native "Convert to text" fast path

**Feasibility: cheap complement, mostly ingest-side.** A `.txt` upload becomes a job whose
pages arrive `done=true` — Review already renders done pages (the stream guard from FE-03
means no stream opens for an already-done job; without FE-03 this feature would *re-OCR a
text file*, another reason to fix it first). Two frontend touches: extend the file-input
`accept` (Import.tsx:202) and the `.pdf` guard (Import.tsx:52-55); give Review's `<img>` an
`onError` fallback placeholder ("no page image — native text import") since
`image_url` will 404 (Review.tsx:292-298). Effort: frontend S; whole feature S–M.

### 6.7 `myClippings.txt` ingest (far future)

Same shape as 6.6 (pages-pre-done job per book), plus a parser. Defer per BACKLOG.md:28-29 —
no frontend prep needed; the 6.6 groundwork covers it.

### 6.8 Readiness verdict

The single-flow architecture holds for 6.2, 6.3, 6.6, 6.7 with S/M frontend work. 6.1 (batch)
and 6.4 (search) are the two that stress it — batch needs AR-01 + multi-job state in App;
search needs a modal shell. Neither needs a router or a state library *yet*; adopt TanStack
Query at batch time (AR-05) and reconsider a router only if search outgrows a modal.

---

## 7. Phased roadmap

Order chosen so data safety lands first, Víctor's named priority second, and future features
inherit a sound base.

**Sprint A — "Never lose an edit" (P0, ~2–3 days)**
FE-01, FE-02 (save correctness) → FE-03 frontend guard + `page_started` reset → FE-04
(close ≠ done, resume banner) → FE-12 (job-fetch error state) → AR-01 skip-done fix
(coordinate one small backend PR with the backend agent). Exit test: edit → export → back →
edits intact; kill backend mid-OCR → honest error, no fake "complete".

**Sprint B — "Models that load themselves" (P1, Víctor priority, ~3 days)**
AR-02 (event envelope) → FE-06 (pull progress bar) → FE-07 (refetch on open + refresh
button) → FE-08 (backend-down panel) → FE-10 (select busy/error) → FE-16 + FE-21 (copy,
load feedback, VRAM chips). Exit test: fresh machine, Ollama installed but empty → pull a
model watching a live % → OCR runs, no terminal touched.

**Sprint C — "Smooth streams, single source of truth" (P1/P2, ~2 days)**
FE-05 (memo boundary + rAF buffer, profiler before/after) → FE-09 (persist vault/strategies)
→ FE-11 + AR-05 lift (settings single-owner) → FE-15, FE-13, FE-17, FE-20 (small hygiene).

**Sprint D — "Tests + polish + future prep" (P2/P3, ~2–3 days)**
FE-14 (extract `handleSseEvent` into a pure `applySseEvent(pages, event)` reducer; vitest for
reducer + client error mapping + save debounce; wire `npm test` into CI — closes roadmap #9's
unit half) → AR-03 (either adopt `openapi-typescript` generation from FastAPI's
`/openapi.json`, or amend CLAUDE.md §6 to bless snake_case at the API boundary — pick one,
the current state contradicts the written rule) → FE-18, FE-19, FE-22, FE-23. Then the
future-features track opens: 6.2 (strategies) as a quick win, 6.1 (batch) with AR-01's
start/stream split as its first PR.

---

## 8. Risks & limitations of this audit

1. **Static analysis only.** No profiler run, no screenshots, no live SSE session — the §4
   costs are reasoned from code + react-markdown v9's documented render model, not measured.
   The Sprint C profiler step doubles as verification.
2. **Backend coordination.** AR-01 and AR-04 have backend halves owned by the other agent;
   FE-03's frontend guard is safe alone, but the full fix needs both PRs to land — sequence
   them in the same sprint to avoid a half-fixed state.
3. **react-markdown internals.** The "re-parses every render" claim holds for v9.0.1
   (package.json:18); if the dep is ever swapped, re-validate before keeping the memo
   boundary as the only defense.
4. **Effort estimates are coarse** (S/M/L against a solo-maintainer cadence) and assume no
   scope creep — e.g. FE-06 stays a progress bar, not a download manager.
5. **Windows-path blind spots.** Path inputs (scan folder, vault) are free-text; this audit
   did not exercise UNC/`~`/trailing-slash edge cases against the backend's path handling —
   worth one manual pass when touching FE-09.

---

## 9. Open questions for Víctor

1. **Is "export → back to Review to fix one word" a flow you actually use?** If yes, FE-03/
   AR-01 is not just P0 on paper — it is actively destroying edits today and Sprint A should
   ship this week.
2. **Batch UX shape:** multi-select + "Transcribe all" in Import with a queue strip, or a
   persistent job-list sidebar? The first preserves the current shell (my recommendation);
   the second is a bigger redesign.
3. **AR-03 direction:** generate types from OpenAPI (one `npm run gen:api` script, drift
   impossible) or just amend CLAUDE.md to bless snake_case at the boundary? Both are honest;
   generation pays more once batch/search/templates grow the contract.
4. **Provider status freshness:** is refetch-on-popover-open enough, or do you want the dot
   in the *closed* header button to be live too (requires background polling)?
5. **Should a successful export auto-persist the vault path + strategies** (my
   recommendation, FE-09), or do you prefer an explicit "remember these" checkbox?
6. **TanStack Query timing:** OK to defer to the batch sprint (AR-05), or do you want the
   settings/status plumbing modernised earlier while Sprint C touches it anyway?
