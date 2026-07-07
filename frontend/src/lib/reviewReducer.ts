/**
 * Pure page-state transitions for the Review step's OCR SSE stream (FE-14).
 *
 * Extracted from Review.tsx so the event → state math is unit-testable without a
 * DOM or a live stream. The component keeps the rAF buffering / flush timing;
 * this module only computes the next `pages` array for one event.
 */

import type { SseEvent } from "./sse";

export interface ReviewPage {
  index: number;
  markdown: string;
  done: boolean;
  streaming: boolean;
}

/**
 * Apply one SSE event's page-state transition, returning a new array with only
 * the affected page replaced (referentially stable for untouched pages, so a
 * memoized page pane doesn't re-render). `page_delta` appends its text — the
 * caller may pass coalesced text from its own buffer. Events that don't touch
 * page state (`job_done`, `error`) return the array unchanged.
 */
export function applyPageEvent(pages: ReviewPage[], event: SseEvent): ReviewPage[] {
  switch (event.type) {
    case "page_started":
      return pages.map((page) => (page.index === event.index ? { ...page, streaming: true } : page));
    case "page_delta":
      return pages.map((page) =>
        page.index === event.index ? { ...page, markdown: page.markdown + event.text } : page,
      );
    case "page_done":
      return pages.map((page) =>
        page.index === event.index ? { ...page, done: true, streaming: false } : page,
      );
    default:
      return pages;
  }
}
