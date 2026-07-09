import { describe, expect, it } from "vitest";

import { applyPageEvent, type ReviewPage } from "./reviewReducer";

const pages = (): ReviewPage[] => [
  { index: 1, markdown: "", done: false, streaming: false },
  { index: 2, markdown: "hello", done: false, streaming: false },
];

describe("applyPageEvent", () => {
  it("page_started marks only its page streaming", () => {
    const next = applyPageEvent(pages(), { type: "page_started", index: 1 });
    expect(next[0].streaming).toBe(true);
    expect(next[1].streaming).toBe(false);
  });

  it("page_delta appends text to its page", () => {
    const next = applyPageEvent(pages(), { type: "page_delta", index: 2, text: " world" });
    expect(next[1].markdown).toBe("hello world");
    expect(next[0].markdown).toBe("");
  });

  it("page_done marks done and clears streaming", () => {
    const streaming = applyPageEvent(pages(), { type: "page_started", index: 1 });
    const next = applyPageEvent(streaming, { type: "page_done", index: 1 });
    expect(next[0]).toMatchObject({ done: true, streaming: false });
  });

  it("keeps the untouched page object referentially stable", () => {
    const before = pages();
    const next = applyPageEvent(before, { type: "page_delta", index: 1, text: "x" });
    expect(next[1]).toBe(before[1]); // page 2 not re-created → memoized pane won't re-render
  });

  it("job_done and error leave pages unchanged", () => {
    const before = pages();
    expect(applyPageEvent(before, { type: "job_done" })).toBe(before);
    expect(applyPageEvent(before, { type: "error", message: "boom" })).toBe(before);
  });

  it("an event for an unknown page index is a no-op on content", () => {
    const before = pages();
    const next = applyPageEvent(before, { type: "page_done", index: 99 });
    expect(next.map((p) => p.done)).toEqual([false, false]);
  });
});
