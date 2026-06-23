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
 */

import { useState } from "react";
import {
  getLoadableModels,
  loadModel,
  setProviderKey,
  type ProviderState,
  type ProviderStatus,
} from "../api/client";

interface ProviderPickerProps {
  status: ProviderStatus[] | null;
  active: string | null;
  loading: boolean;
  onSelect: (providerId: string, model?: string) => Promise<void>;
  onRefresh: () => Promise<void>;
}

export function ProviderPicker({ status, active, loading, onSelect, onRefresh }: ProviderPickerProps) {
  const [open, setOpen] = useState(false);
  const activeProvider = status?.find((p) => p.id === active) ?? null;

  return (
    <div className="relative">
      <button
        className="btn-secondary flex items-center gap-2 text-sm"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
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

      {open && status && (
        <div
          role="listbox"
          className="absolute right-0 top-10 z-50 w-80 rounded-xl border border-default bg-surface shadow-warm-lg overflow-hidden"
        >
          <ul className="py-1 max-h-[26rem] overflow-y-auto">
            {status.map((provider) => (
              <li key={provider.id}>
                <ProviderRow
                  provider={provider}
                  isActive={provider.id === active}
                  onSelect={async (model) => {
                    await onSelect(provider.id, model);
                    setOpen(false);
                  }}
                  onRefresh={onRefresh}
                />
              </li>
            ))}
          </ul>
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

interface ProviderRowProps {
  provider: ProviderStatus;
  isActive: boolean;
  onSelect: (model?: string) => Promise<void>;
  onRefresh: () => Promise<void>;
}

function ProviderRow({ provider, isActive, onSelect, onRefresh }: ProviderRowProps) {
  const [expanded, setExpanded] = useState<null | "models" | "load" | "key">(null);

  const selectable = provider.state === "ready" || provider.state === "unknown";
  const canLoad = provider.state === "unreachable" || provider.state === "no_model";
  const canEnterKey = provider.state === "needs_key";

  async function handleRowClick() {
    if (provider.models.length > 1) {
      setExpanded((e) => (e === "models" ? null : "models"));
    } else if (selectable) {
      await onSelect(provider.models[0] ?? provider.current_model ?? undefined);
    }
  }

  return (
    <div className={isActive ? "bg-surface-2" : ""}>
      <div className="px-3 py-2.5 flex items-center gap-3">
        <span className={`status-dot ${dotClass(provider.state)} flex-shrink-0`} />
        <ProviderKindIcon kind={provider.kind} />
        <button
          className="flex-1 min-w-0 text-left disabled:cursor-default"
          onClick={handleRowClick}
          disabled={!selectable && provider.models.length <= 1}
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
            onClick={() => setExpanded((e) => (e === "load" ? null : "load"))}
          />
        )}
        {canEnterKey && (
          <RowAction
            label="Add key"
            onClick={() => setExpanded((e) => (e === "key" ? null : "key"))}
          />
        )}
      </div>

      {expanded === "models" && (
        <ModelList
          models={provider.models}
          current={provider.current_model}
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
    </div>
  );
}

// ── Load panel (LM Studio: pick a downloaded model and load it) ──────────────────

function LoadPanel({ providerId, onLoaded }: { providerId: string; onLoaded: (model: string) => Promise<void> }) {
  const [models, setModels] = useState<string[] | null>(null);
  const [loadingModel, setLoadingModel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch the loadable list once, lazily.
  if (models === null && !error) {
    getLoadableModels(providerId)
      .then(setModels)
      .catch(() => setError("Couldn't list downloaded models. Is LM Studio's `lms` CLI installed?"));
  }

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
      {error && <p className="text-2xs py-1" style={{ color: "var(--color-error)" }}>{error}</p>}
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
                <span className="text-2xs text-muted">Loading…</span>
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
      {error && <p className="text-2xs" style={{ color: "var(--color-error)" }}>{error}</p>}
      <p className="text-2xs text-muted">Stored locally in your settings, never committed.</p>
    </div>
  );
}

// ── Model list (ready provider with >1 model) ────────────────────────────────────

interface ModelListProps {
  models: string[];
  current: string | null;
  onSelect: (model: string) => Promise<void>;
}

function ModelList({ models, current, onSelect }: ModelListProps) {
  return (
    <ul className="border-t border-default bg-surface py-1">
      {models.map((model) => (
        <li key={model}>
          <button
            className={[
              "w-full text-left px-3 py-2 text-xs transition-colors",
              model === current ? "text-accent bg-surface-2" : "text-primary hover:bg-surface-2",
            ].join(" ")}
            onClick={() => onSelect(model)}
          >
            {model}
          </button>
        </li>
      ))}
    </ul>
  );
}

// ── Small bits ───────────────────────────────────────────────────────────────────

function RowAction({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      className="btn-ghost text-2xs py-1 px-2 flex-shrink-0"
      onClick={onClick}
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
