/**
 * Export step — vault path confirmation, strategy toggles, one-click export.
 *
 * Pre-fills vault_path and strategies from settings (already loaded by App).
 * On a successful export, persists the vault path and strategies back via
 * `updateSettings` so the next session (and any later visit to this step)
 * remembers them (issue #146 / FE-09) — target_dir stays per-export, it isn't
 * a durable preference.
 *
 * Vault-path suggestions: fetched from the backend on mount and on the
 * "Detect" button click. Rendered as clickable chips; clicking fills the
 * input. If none are found the chip row is hidden.
 */

import { useEffect, useState } from "react";
import {
  exportJob,
  getVaultSuggestions,
  updateSettings,
  type ExportResult,
  type Settings,
} from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { Spinner } from "../components/Spinner";
import { SuggestionChips } from "../components/SuggestionChips";

interface ExportProps {
  jobId: string;
  jobName: string;
  settings: Settings | null;
  onBack: () => void;
  onDone: () => void;
  /** Called after a successful export with the freshly persisted settings, so
   * App's copy stays in sync (e.g. re-entering Export in the same session
   * shows the just-saved vault path instead of the stale pre-export one). */
  onSettingsChange?: (settings: Settings) => void;
}

export function Export({ jobId, jobName, settings, onBack, onDone, onSettingsChange }: ExportProps) {
  const [vaultPath, setVaultPath] = useState(settings?.vault_path ?? "");
  const [targetDir, setTargetDir] = useState("");
  const [strategies, setStrategies] = useState<string[]>(
    settings?.strategies ?? ["mirror"],
  );
  const [exporting, setExporting] = useState(false);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [vaultSuggestions, setVaultSuggestions] = useState<string[]>([]);
  const [detectingVaults, setDetectingVaults] = useState(false);

  async function detectVaults() {
    setDetectingVaults(true);
    try {
      const suggestions = await getVaultSuggestions();
      setVaultSuggestions(suggestions);
    } catch {
      // Silently ignore — suggestions are best-effort.
    } finally {
      setDetectingVaults(false);
    }
  }

  // Detect vaults on mount so chips are ready immediately.
  useEffect(() => {
    detectVaults();
  }, []);

  function toggleStrategy(name: string) {
    // mirror is always on; other strategies are toggleable.
    if (name === "mirror") return;
    setStrategies((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name],
    );
  }

  async function handleExport() {
    if (!vaultPath.trim()) {
      setError("Please enter your Obsidian vault path.");
      return;
    }
    setExporting(true);
    setError(null);
    try {
      const trimmedVaultPath = vaultPath.trim();
      const res = await exportJob(jobId, {
        vault_path: trimmedVaultPath,
        strategies,
        target_dir: targetDir.trim() || undefined,
      });
      setResult(res);
      persistExportSettings(trimmedVaultPath, strategies);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  }

  /**
   * Remembers the vault path + strategies for next session (issue #146).
   * Fires only after a successful export, so a half-typed or invalid path
   * never gets persisted. Best-effort: the export already succeeded, so a
   * persistence failure is silently dropped rather than surfaced as an error.
   */
  async function persistExportSettings(vaultPathToSave: string, strategiesToSave: string[]) {
    try {
      const updated = await updateSettings({
        vault_path: vaultPathToSave,
        strategies: strategiesToSave,
      });
      onSettingsChange?.(updated);
    } catch {
      // Best-effort — see docstring above.
    }
  }

  // ── Success state ────────────────────────────────────────────────────────

  if (result) {
    return (
      <div className="flex flex-col gap-6 w-full max-w-lg mx-auto">
        <div className="flex flex-col items-center gap-3 text-center py-4">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center bg-green-500/10">
            <svg className="w-7 h-7 text-green-600 dark:text-green-400" viewBox="0 0 28 28" fill="none">
              <path
                d="M5 14l6 6L23 8"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h2 className="font-serif text-xl font-medium text-primary">Exported!</h2>
          <p className="text-sm text-secondary">
            {result.written.length} file{result.written.length !== 1 ? "s" : ""} written to your vault.
          </p>
        </div>

        {/* Written files list */}
        <div className="card flex flex-col gap-1 max-h-64 overflow-y-auto">
          <p className="text-2xs font-semibold uppercase tracking-widest text-muted pb-1 border-b border-default">
            Files written
          </p>
          <ul className="flex flex-col gap-0.5 mt-1">
            {result.written.map((path) => (
              <li key={path} className="text-xs text-primary font-mono truncate" title={path}>
                {path}
              </li>
            ))}
          </ul>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button className="btn-secondary flex-1" onClick={onBack}>
            Back to Review
          </button>
          <button className="btn-primary flex-1" onClick={onDone}>
            Import another →
          </button>
        </div>
      </div>
    );
  }

  // ── Export form ──────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-6 w-full max-w-lg mx-auto">
      <div>
        <h2 className="font-serif text-lg font-medium text-primary">{jobName}</h2>
        <p className="text-sm text-secondary mt-0.5">
          Review complete. Configure the export below.
        </p>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Vault path */}
      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold uppercase tracking-widest text-muted" htmlFor="vault-path">
          Obsidian vault path
        </label>
        <input
          id="vault-path"
          className="input font-mono text-sm"
          type="text"
          placeholder="/Users/you/Obsidian/My Vault"
          value={vaultPath}
          onChange={(e) => setVaultPath(e.target.value)}
          spellCheck={false}
          autoComplete="off"
        />
        <div className="flex items-center justify-between">
          <p className="text-2xs text-muted">
            The absolute path to your Obsidian vault folder.
          </p>
          <button
            type="button"
            className="btn-ghost text-2xs py-0.5 px-2 gap-1 shrink-0"
            onClick={detectVaults}
            disabled={detectingVaults}
            aria-label="Detect Obsidian vaults"
          >
            {detectingVaults ? (
              <span className="opacity-60">Detecting…</span>
            ) : (
              "Detect"
            )}
          </button>
        </div>

        {/* Suggestion chips — only shown when suggestions exist */}
        {vaultSuggestions.length > 0 && (
          <SuggestionChips
            suggestions={vaultSuggestions}
            selected={vaultPath}
            onSelect={setVaultPath}
          />
        )}
      </div>

      {/* Target subfolder (for loose imports) */}
      <div className="flex flex-col gap-2">
        <label
          className="text-xs font-semibold uppercase tracking-widest text-muted"
          htmlFor="target-dir"
        >
          Subfolder{" "}
          <span className="font-normal normal-case tracking-normal text-muted">(optional)</span>
        </label>
        <input
          id="target-dir"
          className="input font-mono text-sm"
          type="text"
          placeholder="inbox"
          value={targetDir}
          onChange={(e) => setTargetDir(e.target.value)}
          spellCheck={false}
          autoComplete="off"
        />
        <p className="text-2xs text-muted">
          Where loose (drag-and-dropped) notebooks land. Scanned-folder imports keep their
          original structure and ignore this.
        </p>
      </div>

      {/* Strategies */}
      <div className="flex flex-col gap-3">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted">
          Export strategies
        </p>

        <StrategyToggle
          label="Mirror folder structure"
          description="Reproduce your Scribe folder hierarchy in the vault."
          enabled={true}
          locked={true}
          onToggle={() => toggleStrategy("mirror")}
        />

        <StrategyToggle
          label="Generate wikilinks index"
          description="Create a [[wikilinks]] index note per folder for easy navigation."
          enabled={strategies.includes("wikilinks")}
          locked={false}
          onToggle={() => toggleStrategy("wikilinks")}
        />
      </div>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <button className="btn-secondary" onClick={onBack} disabled={exporting}>
          ← Back
        </button>
        <button
          className="btn-primary flex-1"
          onClick={handleExport}
          disabled={exporting || !vaultPath.trim()}
        >
          {exporting ? (
            <>
              <Spinner size="sm" />
              Exporting…
            </>
          ) : (
            "Export to Obsidian →"
          )}
        </button>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

interface StrategyToggleProps {
  label: string;
  description: string;
  enabled: boolean;
  locked: boolean;
  onToggle: () => void;
}

function StrategyToggle({
  label,
  description,
  enabled,
  locked,
  onToggle,
}: StrategyToggleProps) {
  return (
    <div
      className={[
        "flex items-start gap-3 rounded-xl border p-3 transition-colors",
        enabled ? "border-terracotta-400/40 bg-terracotta-300/5" : "border-default",
        locked ? "opacity-80" : "cursor-pointer hover:border-terracotta-400/30",
      ].join(" ")}
      onClick={locked ? undefined : onToggle}
      role={locked ? undefined : "checkbox"}
      aria-checked={enabled}
      tabIndex={locked ? undefined : 0}
      onKeyDown={
        locked
          ? undefined
          : (e) => {
              if (e.key === "Enter" || e.key === " ") onToggle();
            }
      }
    >
      {/* Toggle indicator */}
      <div
        className={[
          "mt-0.5 w-8 h-4.5 rounded-full relative flex-shrink-0 transition-colors",
          enabled ? "bg-terracotta-500 dark:bg-terracotta-400" : "bg-parchment-300 dark:bg-obsidian-800",
          locked ? "opacity-70" : "",
        ].join(" ")}
        style={{ height: "18px", width: "32px" }}
      >
        <span
          className="absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white shadow transition-transform"
          style={{
            transform: enabled ? "translateX(15px)" : "translateX(2px)",
            height: "14px",
            width: "14px",
          }}
        />
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-primary flex items-center gap-2">
          {label}
          {locked && (
            <span className="text-2xs font-normal text-muted bg-surface-2 px-1.5 py-0.5 rounded">
              always on
            </span>
          )}
        </div>
        <p className="text-xs text-muted mt-0.5">{description}</p>
      </div>
    </div>
  );
}
