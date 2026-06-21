/**
 * SSE client for the OCR job stream.
 *
 * Connects to GET /api/jobs/{id}/stream and dispatches typed events.
 * The caller provides callbacks; this module owns the EventSource lifetime.
 *
 * Event shapes from the backend:
 *   { type: "page_started", index: number }
 *   { type: "page_delta",   index: number, text: string }
 *   { type: "page_done",    index: number }
 *   { type: "job_done" }
 *   { type: "error",        message: string }
 */

export type SseEvent =
  | { type: "page_started"; index: number }
  | { type: "page_delta"; index: number; text: string }
  | { type: "page_done"; index: number }
  | { type: "job_done" }
  | { type: "error"; message: string };

export interface SseHandlers {
  onEvent: (event: SseEvent) => void;
  /** Called when the stream closes normally (after job_done or server close). */
  onClose?: () => void;
  /** Called on EventSource-level errors (network drop, server error). */
  onError?: (err: Event) => void;
}

/**
 * Opens an SSE connection to /api/jobs/{jobId}/stream.
 * Returns a cleanup function — call it to close the stream.
 */
export function connectJobStream(jobId: string, handlers: SseHandlers): () => void {
  const url = `/api/jobs/${jobId}/stream`;
  const source = new EventSource(url);

  source.onmessage = (ev: MessageEvent<string>) => {
    let parsed: SseEvent;
    try {
      parsed = JSON.parse(ev.data) as SseEvent;
    } catch {
      // Ignore malformed frames (e.g. heartbeat comments parsed as data).
      return;
    }

    handlers.onEvent(parsed);

    // Close the source after terminal events so the browser doesn't reconnect.
    if (parsed.type === "job_done" || parsed.type === "error") {
      source.close();
      handlers.onClose?.();
    }
  };

  source.onerror = (err) => {
    handlers.onError?.(err);
    // EventSource auto-reconnects on error; close explicitly to stop that.
    source.close();
    handlers.onClose?.();
  };

  return () => {
    source.close();
  };
}

/**
 * React hook that streams OCR events for a job and dispatches them via a
 * reducer-style updater. Call it with null jobId to be a no-op.
 *
 * Usage:
 *   useJobStream(jobId, (event) => {
 *     if (event.type === "page_delta") setMarkdown(i, prev => prev + event.text);
 *   });
 */
import { useEffect, useRef } from "react";

export function useJobStream(
  jobId: string | null,
  onEvent: (event: SseEvent) => void,
  onClose?: () => void,
): void {
  // Stable ref so the effect doesn't re-run when the callback identity changes.
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!jobId) return;

    const cleanup = connectJobStream(jobId, {
      onEvent: (ev) => onEventRef.current(ev),
      onClose: () => onCloseRef.current?.(),
      onError: () => {
        // Error is surfaced via onClose; callers can set an error state there.
      },
    });

    return cleanup;
  }, [jobId]);
}
