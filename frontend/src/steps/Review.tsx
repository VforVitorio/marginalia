/**
 * Review step — per-page image (left) ↔ editable Markdown (right).
 *
 * On mount: starts the SSE stream for the job. OCR text appends live via
 * page_delta events. The user can edit Markdown while OCR is still running
 * for earlier pages. Edits are persisted with PUT /api/jobs/{id}/pages/{n}.
 *
 * Flow:
 *  1. Mount → fetch full job state (to restore partial progress from disk).
 *  2. Start SSE stream → apply events on top.
 *  3. When a page textarea loses focus (or after a short debounce), auto-save.
 *  4. "Done — Export" button becomes active once job_done is received.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getJob,
  updatePageMarkdown,
  pageImageUrl,
  type PageState,
} from "../api/client";
import { useJobStream, type SseEvent } from "../lib/sse";
import { ErrorBanner } from "../components/ErrorBanner";
import { Spinner } from "../components/Spinner";

interface ReviewProps {
  jobId: string;
  jobName: string;
  pageCount: number;
  onExport: () => void;
  onBack: () => void;
}

interface LocalPage {
  index: number;
  markdown: string;
  done: boolean;
  streaming: boolean;
}

export function Review({ jobId, jobName, pageCount, onExport, onBack }: ReviewProps) {
  const [pages, setPages] = useState<LocalPage[]>(() =>
    Array.from({ length: pageCount }, (_, i) => ({
      index: i,
      markdown: "",
      done: false,
      streaming: false,
    })),
  );
  const [activePage, setActivePage] = useState(0);
  const [jobDone, setJobDone] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);

  // Tracks which page indices have unsaved edits.
  const pendingSave = useRef<Set<number>>(new Set());
  const saveTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  // ── Initial state fetch ──────────────────────────────────────────────────

  useEffect(() => {
    getJob(jobId)
      .then((job) => {
        setPages(
          job.pages.map((p: PageState) => ({
            index: p.index,
            markdown: p.markdown ?? "",
            done: p.done,
            streaming: false,
          })),
        );
        if (job.status === "done") setJobDone(true);
      })
      .catch(() => {
        // Non-fatal: start with empty pages and let the stream fill them.
      })
      .finally(() => setInitialLoading(false));
  }, [jobId]);

  // ── SSE stream ───────────────────────────────────────────────────────────

  const handleSseEvent = useCallback(
    (event: SseEvent) => {
      if (event.type === "page_started") {
        setPages((prev) =>
          prev.map((p) =>
            p.index === event.index ? { ...p, streaming: true } : p,
          ),
        );
        setActivePage(event.index);
      } else if (event.type === "page_delta") {
        setPages((prev) =>
          prev.map((p) =>
            p.index === event.index
              ? { ...p, markdown: p.markdown + event.text }
              : p,
          ),
        );
      } else if (event.type === "page_done") {
        setPages((prev) =>
          prev.map((p) =>
            p.index === event.index ? { ...p, done: true, streaming: false } : p,
          ),
        );
      } else if (event.type === "job_done") {
        setJobDone(true);
      } else if (event.type === "error") {
        setStreamError(event.message);
      }
    },
    [],
  );

  useJobStream(
    initialLoading ? null : jobId,
    handleSseEvent,
    () => {
      // Stream closed — if not already done, mark done so UI unblocks.
      setJobDone((prev) => prev || true);
    },
  );

  // ── Auto-save ────────────────────────────────────────────────────────────

  function scheduleSave(pageIndex: number) {
    pendingSave.current.add(pageIndex);
    const existing = saveTimers.current.get(pageIndex);
    if (existing) clearTimeout(existing);

    const timer = setTimeout(() => {
      doSave(pageIndex);
    }, 800);
    saveTimers.current.set(pageIndex, timer);
  }

  async function doSave(pageIndex: number) {
    const page = pages[pageIndex];
    if (!page) return;
    try {
      await updatePageMarkdown(jobId, pageIndex, page.markdown);
      pendingSave.current.delete(pageIndex);
      setSaveError(null);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed.");
    }
  }

  function handleMarkdownChange(pageIndex: number, value: string) {
    setPages((prev) =>
      prev.map((p) => (p.index === pageIndex ? { ...p, markdown: value } : p)),
    );
    scheduleSave(pageIndex);
  }

  // Flush on unmount
  useEffect(() => {
    return () => {
      saveTimers.current.forEach(clearTimeout);
    };
  }, []);

  // ── Rendering ────────────────────────────────────────────────────────────

  const active = pages[activePage];

  const doneCount = pages.filter((p) => p.done).length;
  const progress = pageCount > 0 ? doneCount / pageCount : 0;

  if (initialLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" label="Loading job…" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 w-full">
      {/* Header row */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <h2 className="font-serif text-lg font-medium text-primary truncate">{jobName}</h2>
          <p className="text-xs text-muted mt-0.5">
            {jobDone
              ? `${pageCount} page${pageCount !== 1 ? "s" : ""} — OCR complete`
              : `OCR running… ${doneCount} / ${pageCount} done`}
          </p>
        </div>

        {/* Progress bar */}
        <div className="flex items-center gap-2">
          <div className="w-32 h-1.5 rounded-full bg-surface-2 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progress * 100}%`,
                backgroundColor: "var(--color-accent)",
              }}
            />
          </div>
          <span className="text-2xs text-muted tabular-nums">
            {Math.round(progress * 100)}%
          </span>
        </div>

        <button className="btn-secondary" onClick={onBack}>
          ← Back
        </button>
        <button
          className="btn-primary"
          onClick={onExport}
          disabled={!jobDone}
        >
          {jobDone ? "Export →" : <><Spinner size="sm" /> OCR running…</>}
        </button>
      </div>

      {/* Errors */}
      {streamError && (
        <ErrorBanner message={`OCR error: ${streamError}`} onDismiss={() => setStreamError(null)} />
      )}
      {saveError && (
        <ErrorBanner message={`Save error: ${saveError}`} onDismiss={() => setSaveError(null)} />
      )}

      {/* Page tabs */}
      <PageTabs pages={pages} activePage={activePage} onSelect={setActivePage} />

      {/* Main pane: image + editor */}
      {active && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 min-h-[500px]">
          {/* Left — page image */}
          <div className="card p-0 overflow-hidden flex flex-col">
            <div className="px-3 py-2 border-b border-default flex items-center gap-2">
              <span className="text-xs font-medium text-muted uppercase tracking-wide">
                Page {activePage + 1}
              </span>
              <span className="ml-auto">
                {active.streaming && <Spinner size="sm" label="OCR streaming…" />}
                {active.done && !active.streaming && (
                  <DoneChip />
                )}
              </span>
            </div>
            <div className="flex-1 flex items-center justify-center bg-surface overflow-auto p-2">
              <img
                key={`${jobId}-${activePage}`}
                src={pageImageUrl(jobId, activePage)}
                alt={`Page ${activePage + 1} original`}
                className="max-w-full max-h-[600px] object-contain rounded-lg shadow-warm"
                loading="lazy"
              />
            </div>
          </div>

          {/* Right — markdown editor */}
          <div className="card p-0 flex flex-col">
            <div className="px-3 py-2 border-b border-default flex items-center gap-2">
              <span className="text-xs font-medium text-muted uppercase tracking-wide">
                Transcript
              </span>
              {pendingSave.current.has(activePage) && (
                <span className="text-2xs text-muted ml-auto italic">Saving…</span>
              )}
            </div>
            <textarea
              aria-label={`Transcript for page ${activePage + 1}`}
              className="flex-1 resize-none bg-transparent font-mono text-sm text-primary p-3 outline-none leading-relaxed min-h-[400px]"
              value={active.markdown}
              onChange={(e) => handleMarkdownChange(activePage, e.target.value)}
              spellCheck={false}
              placeholder={
                active.streaming
                  ? "Transcribing…"
                  : active.done
                  ? "Empty page — type to add notes."
                  : "Waiting for OCR…"
              }
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

interface PageTabsProps {
  pages: LocalPage[];
  activePage: number;
  onSelect: (index: number) => void;
}

function PageTabs({ pages, activePage, onSelect }: PageTabsProps) {
  return (
    <div
      role="tablist"
      aria-label="Pages"
      className="flex gap-1 overflow-x-auto pb-1 scrollbar-thin"
    >
      {pages.map((page) => (
        <button
          key={page.index}
          role="tab"
          aria-selected={page.index === activePage}
          aria-label={`Page ${page.index + 1}${page.done ? " — done" : page.streaming ? " — streaming" : ""}`}
          onClick={() => onSelect(page.index)}
          className={[
            "flex-shrink-0 w-9 h-9 rounded-lg text-xs font-medium transition-all relative",
            page.index === activePage
              ? "bg-terracotta-500 dark:bg-terracotta-400 text-parchment-50 shadow-warm"
              : "bg-surface-2 text-secondary hover:bg-parchment-200 dark:hover:bg-obsidian-800",
          ].join(" ")}
        >
          {page.index + 1}
          {page.streaming && (
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-terracotta-400 animate-pulse" />
          )}
          {page.done && !page.streaming && (
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-green-500/70" />
          )}
        </button>
      ))}
    </div>
  );
}

function DoneChip() {
  return (
    <span className="inline-flex items-center gap-1 text-2xs px-1.5 py-0.5 rounded-full bg-green-500/10 text-green-700 dark:text-green-400">
      <svg className="w-2.5 h-2.5" viewBox="0 0 10 10" fill="none">
        <path d="M2 5l2 2 4-4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      Done
    </span>
  );
}
