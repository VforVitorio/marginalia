/**
 * ProviderPicker — header panel for selecting the OCR provider and model.
 * Shows Claude auth status as a status dot. Compact by default, expands on
 * demand. All state is lifted to App.
 */

import { useState } from "react";
import type { ProviderInfo, ProvidersResponse } from "../api/client";

interface ProviderPickerProps {
  providers: ProvidersResponse | null;
  loading: boolean;
  onSelect: (providerId: string, model?: string) => Promise<void>;
}

export function ProviderPicker({ providers, loading, onSelect }: ProviderPickerProps) {
  const [open, setOpen] = useState(false);
  const [selectingModel, setSelectingModel] = useState<string | null>(null);

  const active = providers?.providers.find(
    (p) => p.id === providers.active,
  );

  const claudeAuth = providers?.claude_authenticated ?? false;

  async function handleProviderClick(provider: ProviderInfo) {
    if (provider.models.length > 1) {
      setSelectingModel(provider.id);
    } else {
      await onSelect(provider.id, provider.models[0] ?? undefined);
      setOpen(false);
    }
  }

  async function handleModelSelect(providerId: string, model: string) {
    await onSelect(providerId, model);
    setSelectingModel(null);
    setOpen(false);
  }

  return (
    <div className="relative">
      {/* Trigger button */}
      <button
        className="btn-secondary flex items-center gap-2 text-sm"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
        disabled={loading}
      >
        {/* Claude auth indicator */}
        <ProviderKindIcon kind={active?.kind ?? "local"} />
        <span className="max-w-[120px] truncate font-medium text-primary">
          {loading
            ? "Loading…"
            : active
            ? `${active.display_name}${active.current_model ? ` · ${active.current_model}` : ""}`
            : "Choose provider"}
        </span>
        {claudeAuth && (
          <span title="Claude authenticated" className="status-dot status-dot-ok" />
        )}
        <ChevronIcon open={open} />
      </button>

      {/* Dropdown */}
      {open && providers && (
        <div
          role="listbox"
          className="absolute right-0 top-10 z-50 w-72 rounded-xl border border-default bg-surface shadow-warm-lg overflow-hidden"
        >
          {/* Claude auth banner */}
          <div className="px-3 py-2 border-b border-default flex items-center gap-2">
            <span className={`status-dot ${claudeAuth ? "status-dot-ok" : "status-dot-warn"}`} />
            <span className="text-xs text-secondary">
              {claudeAuth
                ? "Claude subscription authenticated"
                : "Claude not authenticated — cloud OCR via Gemini only"}
            </span>
          </div>

          {/* Provider list */}
          {selectingModel ? (
            <ModelList
              providerId={selectingModel}
              providers={providers.providers}
              onBack={() => setSelectingModel(null)}
              onSelect={handleModelSelect}
            />
          ) : (
            <ul className="py-1">
              {providers.providers.map((provider) => (
                <li key={provider.id}>
                  <button
                    role="option"
                    aria-selected={provider.id === providers.active}
                    className={[
                      "w-full text-left px-3 py-2.5 flex items-center gap-3 transition-colors",
                      provider.id === providers.active
                        ? "bg-surface-2"
                        : "hover:bg-surface-2",
                    ].join(" ")}
                    onClick={() => handleProviderClick(provider)}
                  >
                    <ProviderKindIcon kind={provider.kind} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-primary truncate">
                        {provider.display_name}
                      </div>
                      {provider.current_model && (
                        <div className="text-xs text-muted truncate">
                          {provider.current_model}
                        </div>
                      )}
                    </div>
                    {provider.id === providers.active && (
                      <svg className="w-4 h-4 text-accent flex-shrink-0" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M3 8l3.5 3.5 6.5-7"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                    {provider.models.length > 1 && (
                      <svg className="w-3.5 h-3.5 text-muted flex-shrink-0" viewBox="0 0 14 14" fill="none">
                        <path
                          d="M5 3l4 4-4 4"
                          stroke="currentColor"
                          strokeWidth="1.4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Click-away overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => {
            setOpen(false);
            setSelectingModel(null);
          }}
        />
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

interface ModelListProps {
  providerId: string;
  providers: ProviderInfo[];
  onBack: () => void;
  onSelect: (providerId: string, model: string) => void;
}

function ModelList({ providerId, providers, onBack, onSelect }: ModelListProps) {
  const provider = providers.find((p) => p.id === providerId);
  if (!provider) return null;

  return (
    <div>
      <button
        className="w-full text-left px-3 py-2 flex items-center gap-2 text-sm text-secondary hover:bg-surface-2 border-b border-default"
        onClick={onBack}
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none">
          <path
            d="M9 3L5 7l4 4"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Back to providers
      </button>
      <div className="px-3 py-2 text-xs font-medium text-muted uppercase tracking-wide">
        {provider.display_name} — choose model
      </div>
      <ul className="py-1">
        {provider.models.map((model) => (
          <li key={model}>
            <button
              className={[
                "w-full text-left px-3 py-2 text-sm transition-colors",
                model === provider.current_model
                  ? "text-accent bg-surface-2"
                  : "text-primary hover:bg-surface-2",
              ].join(" ")}
              onClick={() => onSelect(providerId, model)}
            >
              {model}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
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

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`w-3.5 h-3.5 text-muted transition-transform ${open ? "rotate-180" : ""}`}
      viewBox="0 0 14 14"
      fill="none"
    >
      <path
        d="M3 5l4 4 4-4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
