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
    // EventSource auto-reconnects on error; close explicitly to stop that.
    source.close();
    // Only onError here — NOT onClose. A network drop is not a normal close, so
    // the caller must be able to tell "stream interrupted" from "run finished"
    // (onClose fires solely after a terminal job_done / error frame above).
    handlers.onError?.(err);
  };

  return () => {
    source.close();
  };
}

// Re-export the React hook so existing importers that do:
//   import { useJobStream } from "../lib/sse"
// continue to work without any change.
export { useJobStream } from "./useJobStream";

// ── Raw fetch-stream SSE reader (for POST-based streams) ────────────────────

/**
 * Read a raw fetch `Response` body as an SSE stream and yield parsed JSON events.
 *
 * `EventSource` (used by `connectJobStream` above) only supports GET requests and
 * handles frame buffering natively. POST-based streams — e.g. the model-pull
 * endpoint, which needs a JSON body — have no `EventSource` equivalent, so this
 * does the same `data: <json>\n\n` framing by hand. Both the job stream and the
 * pull stream now share the `{ type: ... }` envelope (see docs/research/
 * AUDIT_FRONTEND_ARCHITECTURE.md AR-02), even though they're consumed through
 * two different transports.
 */
export async function* readSseStream<T>(response: Response): AsyncGenerator<T> {
  const body = response.body;
  if (!body) return;

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const event = parseSseFrame<T>(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      if (event !== null) yield event;
      boundary = buffer.indexOf("\n\n");
    }
  }
}

/** Parse one SSE frame's `data:` lines into its JSON payload, or `null` if empty/malformed. */
function parseSseFrame<T>(frame: string): T | null {
  const dataLines = frame
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trimStart());
  if (dataLines.length === 0) return null;

  try {
    return JSON.parse(dataLines.join("\n")) as T;
  } catch {
    return null;
  }
}
