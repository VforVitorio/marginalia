/**
 * Import step — two panels side by side (or stacked on narrow viewports):
 *   Left:  drag-and-drop / file-picker for a single PDF.
 *   Right: scanned-folder panel listing PDFs from the configured folder.
 *
 * On success either way, calls onJobCreated(jobId) so App can advance to Review.
 * Renders safely if the backend is down (shows an error instead of crashing).
 *
 * Scan-folder configuration: fetched from settings on mount; editable inline
 * with path suggestions from getScanFolderSuggestions(). Persisted via
 * updateSettings() then re-scans immediately.
 */

import { useEffect, useRef, useState } from "react";
import {
  createJobFromFile,
  createJobFromScan,
  getSettings,
  getScanFolderSuggestions,
  scanFolder,
  updateSettings,
  type ScannedPdf,
} from "../api/client";
import { ErrorBanner } from "../components/ErrorBanner";
import { Spinner } from "../components/Spinner";
import { SuggestionChips } from "../components/SuggestionChips";

interface ImportProps {
  onJobCreated: (jobId: string, jobName: string, pageCount: number) => void;
}

export function Import({ onJobCreated }: ImportProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [scannedPdfs, setScannedPdfs] = useState<ScannedPdf[] | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);

  // Scan-folder configuration state.
  const [scanFolder_, setScanFolder_] = useState("");
  const [scanFolderDraft, setScanFolderDraft] = useState("");
  const [folderSuggestions, setFolderSuggestions] = useState<string[]>([]);
  const [savingFolder, setSavingFolder] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── File helpers ─────────────────────────────────────────────────────────

  async function uploadFile(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are supported.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const job = await createJobFromFile(file);
      onJobCreated(job.job_id, job.name, job.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setUploading(false);
    }
  }

  function handleDrop(ev: React.DragEvent<HTMLDivElement>) {
    ev.preventDefault();
    setDragging(false);
    const file = ev.dataTransfer.files[0];
    if (file) uploadFile(file);
  }

  const handleFileInput = (ev: React.ChangeEvent<HTMLInputElement>) => {
    const file = ev.target.files?.[0];
    if (file) uploadFile(file);
    // Reset input so the same file can be re-selected.
    ev.target.value = "";
  };

  // ── Folder scan ──────────────────────────────────────────────────────────

  async function handleScan() {
    setScanning(true);
    setScanError(null);
    try {
      const result = await scanFolder();
      setScannedPdfs(result.pdfs);
    } catch (err) {
      setScanError(err instanceof Error ? err.message : "Scan failed.");
    } finally {
      setScanning(false);
    }
  }

  async function handleOpenScanned(pdf: ScannedPdf) {
    setUploading(true);
    setError(null);
    try {
      const job = await createJobFromScan(pdf.rel_path);
      onJobCreated(job.job_id, job.name, job.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open notebook.");
      setUploading(false);
    }
  }

  // ── Scan-folder management ────────────────────────────────────────────────

  /** Persist a new scan-folder path, then re-scan immediately. */
  async function applyScanFolder(path: string) {
    const trimmed = path.trim();
    if (!trimmed || trimmed === scanFolder_) return;
    setSavingFolder(true);
    try {
      await updateSettings({ scan_folder: trimmed });
      setScanFolder_(trimmed);
      setScanFolderDraft(trimmed);
    } catch {
      // Silently ignore — the user can retry.
    } finally {
      setSavingFolder(false);
    }
    // Always re-scan so the list reflects the new folder (even on error).
    handleScan();
  }

  function handleFolderKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") applyScanFolder(scanFolderDraft);
  }

  // Auto-scan on mount to give a useful default state.
  // Also load the current scan_folder from settings and fetch suggestions.
  useEffect(() => {
    handleScan();

    async function bootstrap() {
      try {
        const [settings, suggestions] = await Promise.all([
          getSettings(),
          getScanFolderSuggestions(),
        ]);
        setScanFolder_(settings.scan_folder ?? "");
        setScanFolderDraft(settings.scan_folder ?? "");
        setFolderSuggestions(suggestions);
      } catch {
        // Non-fatal — suggestions and current folder remain empty.
      }
    }

    bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dropZoneClass = [
    "relative flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-8 transition-all duration-200 cursor-pointer select-none min-h-[200px]",
    dragging
      ? "border-terracotta-400 bg-terracotta-300/10"
      : "border-default hover:border-terracotta-400/60 hover:bg-surface-2",
    uploading ? "pointer-events-none opacity-60" : "",
  ].join(" ");

  return (
    <div className="flex flex-col gap-6 w-full max-w-3xl mx-auto">
      {/* Global upload error */}
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* ── Drop zone ──────────────────────────────────────────────── */}
        <div className="flex flex-col gap-3">
          <SectionLabel>Drop a notebook</SectionLabel>
          <div
            role="button"
            tabIndex={0}
            aria-label="Drop PDF or click to pick"
            onDragEnter={() => setDragging(true)}
            onDragLeave={() => setDragging(false)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
            }}
            className={dropZoneClass}
          >
            {uploading ? (
              <Spinner size="lg" label="Uploading…" />
            ) : (
              <>
                <UploadIcon dragging={dragging} />
                <div className="text-center">
                  <p className="text-sm font-medium text-primary">
                    {dragging ? "Drop it!" : "Drag your PDF here"}
                  </p>
                  <p className="text-xs text-muted mt-0.5">or click to pick a file</p>
                </div>
              </>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="sr-only"
            onChange={handleFileInput}
          />
        </div>

        {/* ── Scanned folder ─────────────────────────────────────────── */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <SectionLabel>Scribe folder</SectionLabel>
            <button
              className="btn-ghost text-xs py-1 px-2 gap-1"
              onClick={handleScan}
              disabled={scanning}
            >
              {scanning ? <Spinner size="sm" /> : <RefreshIcon />}
              Scan
            </button>
          </div>

          {/* Scan-folder path input */}
          <div className="flex flex-col gap-1.5">
            <div className="flex gap-1.5">
              <input
                className="input font-mono text-xs flex-1 min-w-0"
                type="text"
                placeholder="e.g. /Users/you/Kindle Scribe"
                value={scanFolderDraft}
                onChange={(e) => setScanFolderDraft(e.target.value)}
                onKeyDown={handleFolderKeyDown}
                spellCheck={false}
                autoComplete="off"
                aria-label="Scan folder path"
              />
              <button
                type="button"
                className="btn-ghost text-xs px-2.5 py-1 shrink-0"
                disabled={savingFolder || scanFolderDraft.trim() === scanFolder_}
                onClick={() => applyScanFolder(scanFolderDraft)}
                aria-label="Apply folder and rescan"
              >
                {savingFolder ? "…" : "Apply"}
              </button>
            </div>

            {/* Suggestion chips */}
            {folderSuggestions.length > 0 && (
              <SuggestionChips
                suggestions={folderSuggestions}
                selected={scanFolder_}
                onSelect={applyScanFolder}
              />
            )}
          </div>

          <div className="card min-h-[200px] flex flex-col gap-1 overflow-y-auto max-h-72">
            {scanError && (
              <div className="text-xs text-muted italic p-2">
                {scanError}
              </div>
            )}

            {!scanError && scanning && (
              <div className="flex-1 flex items-center justify-center">
                <Spinner size="md" label="Scanning folder…" />
              </div>
            )}

            {!scanError && !scanning && scannedPdfs !== null && (
              <>
                {scannedPdfs.length === 0 ? (
                  <p className="text-xs text-muted italic p-2">
                    No PDFs found. Check the folder path above or sync your Scribe.
                  </p>
                ) : (
                  <ul className="flex flex-col gap-0.5">
                    {scannedPdfs.map((pdf) => (
                      <li key={pdf.rel_path}>
                        <button
                          className="w-full text-left px-2 py-1.5 rounded-lg text-sm hover:bg-parchment-100 dark:hover:bg-obsidian-800 transition-colors flex items-center gap-2 group"
                          onClick={() => handleOpenScanned(pdf)}
                          disabled={uploading}
                        >
                          <PdfIcon />
                          <span className="flex-1 min-w-0 truncate text-primary">
                            {pdf.name}
                          </span>
                          <ArrowIcon />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}

            {!scanError && !scanning && scannedPdfs === null && (
              <div className="flex-1 flex items-center justify-center">
                <p className="text-xs text-muted italic">Click Scan to list notebooks.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Hint */}
      <p className="text-xs text-muted text-center">
        Export from your Kindle Scribe: Notebooks → long-press cover → Export/Share → PDF
      </p>
      <p className="text-2xs text-muted text-center italic">
        Transcript quality depends on the OCR model you pick (top-right).
      </p>
    </div>
  );
}

// ── Small local sub-components ────────────────────────────────────────────────

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-widest text-muted">
      {children}
    </h2>
  );
}

function UploadIcon({ dragging }: { dragging: boolean }) {
  return (
    <div
      className={[
        "w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-200",
        dragging ? "bg-terracotta-400/20 scale-110" : "bg-surface-2",
      ].join(" ")}
    >
      <svg className="w-6 h-6 text-accent" viewBox="0 0 24 24" fill="none">
        <path
          d="M12 15V4M12 4l-4 4M12 4l4 4"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M4 15v3a2 2 0 002 2h12a2 2 0 002-2v-3"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

function PdfIcon() {
  return (
    <svg className="w-4 h-4 text-muted flex-shrink-0" viewBox="0 0 16 16" fill="none">
      <path
        d="M4 2h6l3 3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <path d="M10 2v3h3" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
      <path
        d="M6 9h1.5c.6 0 1 .4 1 1s-.4 1-1 1H6V8.5"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none">
      <path
        d="M2 7a5 5 0 005 5 5 5 0 004.5-2.8"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
      <path
        d="M12 7a5 5 0 00-5-5 5 5 0 00-4.5 2.8"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
      <path d="M12 4V7h-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg className="w-3.5 h-3.5 text-muted opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" viewBox="0 0 14 14" fill="none">
      <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
