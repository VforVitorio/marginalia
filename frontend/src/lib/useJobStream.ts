/**
 * React hook for streaming OCR job events.
 *
 * Extracted from sse.ts so that the SSE transport layer (connectJobStream,
 * SseEvent, SseHandlers) stays framework-agnostic while this hook lives in
 * its own module with React as an explicit dependency.
 */

import { useEffect, useRef } from "react";
import { connectJobStream, type SseEvent } from "./sse";

/**
 * Streams OCR events for a job and dispatches them via a reducer-style updater.
 * Call it with null jobId to be a no-op.
 *
 * Usage:
 *   useJobStream(jobId, (event) => {
 *     if (event.type === "page_delta") setMarkdown(i, prev => prev + event.text);
 *   });
 */
export function useJobStream(
  jobId: string | null,
  onEvent: (event: SseEvent) => void,
  onClose?: () => void,
  onError?: () => void,
): void {
  // Stable refs so the effect doesn't re-run when callback identity changes.
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  useEffect(() => {
    if (!jobId) return;

    const cleanup = connectJobStream(jobId, {
      onEvent: (ev) => onEventRef.current(ev),
      // onClose = terminal (run finished); onError = network drop (interrupted).
      onClose: () => onCloseRef.current?.(),
      onError: () => onErrorRef.current?.(),
    });

    return cleanup;
  }, [jobId]);
}
