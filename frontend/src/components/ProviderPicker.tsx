/**
 * ProviderPicker — header panel for choosing the OCR provider and model.
 *
 * Driven by GET /api/providers/status, so every row shows the *real* state:
 * a coloured dot + a next-step hint (start the runtime / load a model / add a
 * key / sign in). It also lets the user act on that hint without a terminal:
 *   - LM Studio: "Load a model" → starts the server headless + loads (issue #44).
 *   - Gemini: an inline API-key field (issue #38).
 *   - Claude: honest "unknown" — uses the `claude login` session (issue #11).
 * All shared state is lifted to App; this component fetches only the transient
 * loadable-model list on demand.
 *
 * Model selection (`ProviderRow.handleRowClick` / `ModelList`) is provider-kind-agnostic: any
 * row whose `ProviderStatus.models` has more than one entry expands into a picker on click,
 * local or cloud alike. A ready Gemini row gets the same list UI once the backend curates its
 * models (`config.CLOUD_MODELS`, issue #148) — no special-casing needed here.
 */

import { useEffect, useRef, useState } from "react";
import {
  getLoadableModels,
  loadModel,
  pullModel,
  setProviderKey,
  type ProviderState,
  type ProviderStatus,
  type PullEvent,
} from "../api/client";
import { PanelError } from "./PanelError";
import { Spinner } from "./Spinner";

interface ProviderPickerProps {
  status: ProviderStatus[] | null;
  active: string | null;
  loading: boolean;
  /** True while a provider/model selection is in flight (App.handleProviderSelect). */
  selecting: boolean;
  /** Error from the last failed selection, or null. Cleared on the next attempt. */
  selectError: string | null;
  /** Resolves to whether the selection succeeded, so the popover only closes on success. */
  onSelect: (providerId: string, model?: string) => Promise<boolean>;
  onRefresh: () => Promise<void>;
}

export function ProviderPicker({
  status,
  active,
  loading,
  selecting,
  selectError,
  onSelect,
  onRefresh,
}: ProviderPickerProps) {
  const [open, setOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const activeProvider = status?.find((p) => p.id === active) ?? null;

  // Escape closes the popover and returns focus to the toggle (WCAG 2.1.2/2.4.3).
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        toggleRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setRefreshing(false);
    }
  }

  // Refetch status every time the popover opens — otherwise a stale "unreachable"
  // dot never recovers once the runtime comes up after the app already loaded.
  // Deliberately depends on [open] only: onRefresh's identity changes on every
  // App re-render (it's not memoised there), and including it here would refire
  // this effect — and re-fetch — on every unrelated App state change.
  useEffect(() => {
    if (!open) return;
    void handleRefresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <div className="relative">
      <button
        ref={toggleRef}
        className="btn-secondary flex items-center gap-2 text-sm"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-controls="provider-panel"
        disabled={loading}
      >
        <ProviderKindIcon kind={activeProvider?.kind ?? "local"} />
        <span className="max-w-[150px] truncate font-medium text-primary">
          {loading
            ? "Loading…"
            : activeProvider
              ? `${activeProvider.display_name}${activeProvider.current_model ? ` · ${activeProvider.current_model}` : ""}`
              : "Choose provider"}
        </span>
        {activeProvider && <span className={`status-dot ${dotClass(activeProvider.state)}`} />}
        <ChevronIcon open={open} />
      </button>

      {open && (
        <div
          id="provider-panel"
          aria-label="OCR providers"
          aria-busy={refreshing || selecting}
          className="absolute right-0 top-10 z-50 w-80 rounded-xl border border-default bg-surface shadow-warm-lg overflow-hidden"
        >
          <PanelHeader refreshing={refreshing} selecting={selecting} onRefresh={handleRefresh} />

          {selectError && (
            <div className="px-3 pt-2">
              <PanelError message={selectError} />
            </div>
          )}

          {status ? (
            <ul className={`py-1 max-h-[26rem] overflow-y-auto ${selecting ? "opacity-60" : ""}`}>
              {status.map((provider) => (
                <li key={provider.id}>
                  <ProviderRow
                    provider={provider}
                    isActive={provider.id === active}
                    disabled={selecting}
                    onSelect={async (model) => {
                      const ok = await onSelect(provider.id, model);
                      if (ok) setOpen(false);
                    }}
                    onRefresh={onRefresh}
                  />
                </li>
              ))}
            </ul>
          ) : (
            <div className="px-4 py-6 flex flex-col items-center gap-2 text-center">
              <p className="text-xs text-secondary">Cannot reach the backend — is it running?</p>
              <button
                type="button"
                className="btn-secondary text-xs px-3 py-1.5"
                onClick={() => void handleRefresh()}
                disabled={refreshing}
              >
                {refreshing ? "Retrying…" : "Retry"}
              </button>
            </div>
          )}
        </div>
      )}

      {open && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setOpen(false)}
        />
      )}
    </div>
  );
}

// ── Provider row ───────────────────────────────────────────────────────────────

type ExpandedPanel = "models" | "load" | "key" | "pull";

interface ProviderRowProps {
  provider: ProviderStatus;
  isActive: boolean;
  /** True while another selection is already in flight — disables every action on the row. */
  disabled: boolean;
  onSelect: (model?: string) => Promise<void>;
  onRefresh: () => Promise<void>;
}

function ProviderRow({ provider, isActive, disabled, onSelect, onRefresh }: ProviderRowProps) {
  const [expanded, setExpanded] = useState<ExpandedPanel | null>(null);

  const isOllama = provider.id === "ollama";
  const canLoad = !isOllama && (provider.state === "unreachable" || provider.state === "no_model");
  const canPull = isOllama && (provider.state === "no_model" || provider.state === "ready");
  const canEnterKey = provider.state === "needs_key";

  // Any provider is selectable — picking it makes it active; the dot + Load/Pull/Add-key
  // actions tell the user what's still needed before OCR will work.
  async function handleRowClick() {
    if (disabled) return;
    if (provider.models.length > 1) {
      setExpanded((e) => (e === "models" ? null : "models"));
    } else {
      await onSelect(provider.models[0] ?? provider.current_model ?? undefined);
    }
  }

  return (
    <div className={isActive ? "bg-surface-2" : ""}>
      <div className="px-3 py-2.5 flex items-center gap-3">
        <span className={`status-dot ${dotClass(provider.state)} flex-shrink-0`} />
        <ProviderKindIcon kind={provider.kind} />
        <button
          className="flex-1 min-w-0 text-left disabled:opacity-60"
          onClick={handleRowClick}
          disabled={disabled}
        >
          <div className="text-sm font-medium text-primary truncate flex items-center gap-1.5">
            {provider.display_name}
            {isActive && <CheckIcon />}
          </div>
          <div className="text-xs text-muted truncate">
            {provider.current_model ?? provider.hint ?? stateLabel(provider.state)}
          </div>
        </button>

        {canLoad && (
          <RowAction
            label="Load"
            disabled={disabled}
            onClick={() => setExpanded((e) => (e === "load" ? null : "load"))}
          />
        )}
        {canPull && (
          <RowAction
            label="Pull"
            disabled={disabled}
            onClick={() => setExpanded((e) => (e === "pull" ? null : "pull"))}
          />
        )}
        {canEnterKey && (
          <RowAction
            label="Add key"
            disabled={disabled}
            onClick={() => setExpanded((e) => (e === "key" ? null : "key"))}
          />
        )}
      </div>

      {expanded === "models" && (
        <ModelList
          models={provider.models}
          current={provider.current_model}
          disabled={disabled}
          onSelect={async (model) => {
            setExpanded(null);
            await onSelect(model);
          }}
        />
      )}

      {expanded === "load" && (
        <LoadPanel
          providerId={provider.id}
          onLoaded={async (model) => {
            setExpanded(null);
            await onRefresh();
            await onSelect(model);
          }}
        />
      )}

      {expanded === "key" && (
        <KeyPanel
          providerId={provider.id}
          onSaved={async () => {
            setExpanded(null);
            await onRefresh();
          }}
        />
      )}

      {expanded === "pull" && (
        <PullPanel
          providerId={provider.id}
          onPulled={async (model) => {
            setExpanded(null);
            await onRefresh();
            await onSelect(model);
          }}
        />
      )}
    </div>
  );
}

// ── Load panel (LM Studio: pick a downloaded model and load it) ──────────────────

function LoadPanel({ providerId, onLoaded }: { providerId: string; onLoaded: (model: string) => Promise<void> }) {
  const [models, setModels] = useState<string[] | null>(null);
  const [loadingModel, setLoadingModel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch the loadable list on mount. A 503 carries the backend's "open LM Studio" message.
  useEffect(() => {
    getLoadableModels(providerId)
      .then(setModels)
      .catch((err) => setError(err instanceof Error ? err.message : "Couldn't list downloaded models."));
  }, [providerId]);

  async function handleLoad(model: string) {
    setLoadingModel(model);
    setError(null);
    try {
      await loadModel(providerId, model);
      await onLoaded(model);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Load failed.");
    } finally {
      setLoadingModel(null);
    }
  }

  return (
    <div className="px-3 pb-2.5 pt-0.5 border-t border-default bg-surface">
      <p className="text-2xs text-muted py-1 leading-relaxed">
        marginalia will try to start <strong className="font-medium text-secondary">LM Studio</strong> headless
        and load the model — this can take up to ~2 minutes. If that fails, open the LM Studio app once (or
        enable “Run server on login” in its settings), then pick a downloaded model below.
      </p>
      {error && <PanelError message={error} />}
      {models === null && !error && <p className="text-2xs text-muted italic py-1">Looking for models…</p>}
      {models !== null && models.length === 0 && (
        <p className="text-2xs text-muted italic py-1">No downloaded models. Download one in LM Studio first.</p>
      )}
      <ul className="flex flex-col gap-0.5">
        {(models ?? []).map((model) => (
          <li key={model}>
            <button
              className="w-full text-left px-2 py-1.5 rounded-lg text-xs hover:bg-surface-2 flex items-center gap-2 disabled:opacity-60"
              onClick={() => handleLoad(model)}
              disabled={loadingModel !== null}
            >
              <span className="flex-1 min-w-0 truncate text-primary">{model}</span>
              {loadingModel === model ? (
                <span className="text-2xs text-muted flex items-center gap-1">
                  <Spinner size="sm" label={`Loading ${model}…`} />
                  Loading — can take ~2 min…
                </span>
              ) : (
                <span className="text-2xs text-accent">Load →</span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── Key panel (cloud: paste an API key) ──────────────────────────────────────────

function KeyPanel({ providerId, onSaved }: { providerId: string; onSaved: () => Promise<void> }) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (!value.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await setProviderKey(providerId, value.trim());
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the key.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="px-3 pb-2.5 pt-0.5 border-t border-default bg-surface flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5">
        <input
          type="password"
          autoComplete="off"
          spellCheck={false}
          placeholder="Paste API key"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSave();
          }}
          className="flex-1 min-w-0 rounded-lg border border-default bg-surface-2 px-2 py-1.5 text-xs text-primary outline-none focus:border-accent"
        />
        <button className="btn-primary text-xs py-1.5 px-3" onClick={handleSave} disabled={saving || !value.trim()}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
      {error && <PanelError message={error} />}
      <p className="text-2xs text-muted">Stored locally in your settings, never committed.</p>
    </div>
  );
}

// ── Pull panel (Ollama: enter a model name and pull it) ──────────────────────────

const RECOMMENDED_MODELS = ["qwen3-vl:4b", "qwen3-vl:2b", "minicpm-v", "llama3.2-vision"];

function PullPanel({
  providerId,
  onPulled,
}: {
  providerId: string;
  onPulled: (model: string) => Promise<void>;
}) {
  const [model, setModel] = useState("");
  const [pulling, setPulling] = useState(false);
  const [progress, setProgress] = useState<PullEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handlePull() {
    const target = model.trim();
    if (!target) return;
    setPulling(true);
    setProgress(null);
    setError(null);
    try {
      await pullModel(providerId, target, (event) => {
        if (event.type === "pull_progress") setProgress(event);
      });
      await onPulled(target);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Pull failed.");
    } finally {
      setPulling(false);
      setProgress(null);
    }
  }

  return (
    <div className="px-3 pb-2.5 pt-0.5 border-t border-default bg-surface flex flex-col gap-1.5">
      <p className="text-2xs text-muted py-0.5 leading-relaxed">
        <strong className="font-medium text-secondary">Ollama must be running</strong> (open the app or run
        <code className="px-1">ollama serve</code>). Pull a <strong className="font-medium text-secondary">vision</strong>{" "}
        model — text-only models can’t read handwriting.
      </p>
      <div className="flex flex-wrap gap-1 pt-0.5">
        {RECOMMENDED_MODELS.map((rec) => (
          <button
            key={rec}
            className="rounded-md border border-default bg-surface-2 px-2 py-0.5 text-2xs text-primary hover:border-accent hover:text-accent transition-colors disabled:opacity-50"
            onClick={() => setModel(rec)}
            disabled={pulling}
          >
            {rec}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-1.5">
        <input
          type="text"
          autoComplete="off"
          spellCheck={false}
          placeholder="e.g. qwen3-vl:4b"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handlePull();
          }}
          className="flex-1 min-w-0 rounded-lg border border-default bg-surface-2 px-2 py-1.5 text-xs text-primary outline-none focus:border-accent"
          disabled={pulling}
        />
        <button
          className="btn-primary text-xs py-1.5 px-3"
          onClick={handlePull}
          disabled={pulling || !model.trim()}
        >
          {pulling ? "Pulling…" : "Pull"}
        </button>
      </div>
      {pulling && <PullProgress event={progress} />}
      {error && <PanelError message={error} />}
    </div>
  );
}

/** Live status line + bar for a running pull — replaces the old static "Pulling…" text (issue #138). */
function PullProgress({ event }: { event: PullEvent | null }) {
  const percent = event?.type === "pull_progress" ? event.percent : null;
  const status = event?.type === "pull_progress" && event.status ? event.status : "Pulling…";

  return (
    <div className="flex flex-col gap-1" aria-live="polite">
      <p className="text-2xs text-muted italic tabular-nums">
        {status}
        {percent != null ? ` · ${percent}%` : ""}
      </p>
      <div
        role="progressbar"
        aria-label="Model pull progress"
        aria-valuenow={percent ?? undefined}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-1 w-full rounded-full bg-surface-2 overflow-hidden"
      >
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{
            width: `${percent ?? 0}%`,
            backgroundColor: "var(--color-accent)",
          }}
        />
      </div>
    </div>
  );
}

// ── Model list (ready provider with >1 model) ────────────────────────────────────

interface ModelListProps {
  models: string[];
  current: string | null;
  disabled: boolean;
  onSelect: (model: string) => Promise<void>;
}

function ModelList({ models, current, disabled, onSelect }: ModelListProps) {
  return (
    <ul className="border-t border-default bg-surface py-1">
      {models.map((model) => (
        <li key={model}>
          <button
            className={[
              "w-full text-left px-3 py-2 text-xs transition-colors disabled:opacity-50",
              model === current ? "text-accent bg-surface-2" : "text-primary hover:bg-surface-2",
            ].join(" ")}
            onClick={() => onSelect(model)}
            disabled={disabled}
          >
            {model}
          </button>
        </li>
      ))}
    </ul>
  );
}

// ── Panel header (title + refresh, used for both the live list and the empty state) ──

function PanelHeader({
  refreshing,
  selecting,
  onRefresh,
}: {
  refreshing: boolean;
  selecting: boolean;
  onRefresh: () => Promise<void>;
}) {
  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-default">
      <span className="text-2xs font-medium text-muted uppercase tracking-wide flex items-center gap-1.5">
        OCR providers
        {selecting && <Spinner size="sm" label="Selecting provider…" />}
      </span>
      <button
        type="button"
        className="btn-ghost p-1 rounded-md disabled:opacity-50"
        onClick={() => void onRefresh()}
        disabled={refreshing}
        aria-label="Refresh provider status"
        title="Refresh provider status"
      >
        <RefreshIcon spinning={refreshing} />
      </button>
    </div>
  );
}

// ── Small bits ───────────────────────────────────────────────────────────────────

function RowAction({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      className="btn-ghost text-2xs py-1 px-2 flex-shrink-0 disabled:opacity-50"
      onClick={onClick}
      disabled={disabled}
    >
      {label}
    </button>
  );
}

function dotClass(state: ProviderState): string {
  if (state === "ready") return "status-dot-ok";
  if (state === "unreachable") return "status-dot-err";
  return "status-dot-warn"; // no_model | needs_key | unknown
}

function stateLabel(state: ProviderState): string {
  const labels: Record<ProviderState, string> = {
    ready: "Ready",
    no_model: "No model loaded",
    unreachable: "Not reachable",
    needs_key: "Needs an API key",
    unknown: "Status unknown",
  };
  return labels[state];
}

function ProviderKindIcon({ kind }: { kind: "local" | "cloud" }) {
  if (kind === "local") {
    return (
      <svg className="w-3.5 h-3.5 text-muted flex-shrink-0" viewBox="0 0 14 14" fill="none">
        <rect x="1" y="3" width="12" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
        <path d="M4 10V11M7 10V11M10 10V11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
    );
  }
  return (
    <svg className="w-3.5 h-3.5 text-muted flex-shrink-0" viewBox="0 0 14 14" fill="none">
      <path
        d="M2 9.5C1.5 9.5 1 9 1 8.5V5.5C1 5 1.5 4.5 2 4.5h.5c.2-1.2 1.2-2 2.5-2h4c1.3 0 2.3.8 2.5 2h.5c.5 0 1 .5 1 1v3c0 .5-.5 1-1 1H2z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-accent flex-shrink-0" viewBox="0 0 16 16" fill="none">
      <path d="M3 8l3.5 3.5 6.5-7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`w-3.5 h-3.5 text-muted transition-transform ${open ? "rotate-180" : ""}`}
      viewBox="0 0 14 14"
      fill="none"
    >
      <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      className={`w-3.5 h-3.5 text-muted ${spinning ? "animate-spin" : ""}`}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
    >
      <path d="M2 7a5 5 0 005 5 5 5 0 004.5-2.8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M12 7a5 5 0 00-5-5 5 5 0 00-4.5 2.8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M12 4V7h-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
