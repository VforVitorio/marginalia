/**
 * MarkdownEditor — click-to-edit rendered Markdown panel.
 *
 * Two modes:
 *  - Preview (default): renders value as GitHub-flavoured Markdown with KaTeX
 *    math, tables, callouts, checkboxes, and ==highlight== via react-markdown.
 *  - Edit: clicking the preview (or the "Edit" button) swaps in a <textarea>.
 *    On blur the pane returns to preview and calls onChange.
 *
 * While `streaming` is true the component stays in preview and editing is
 * disabled — OCR is still writing the text.
 *
 * Props:
 *  value       — current Markdown string
 *  onChange    — called on every textarea change (caller debounce-saves)
 *  streaming   — when true, lock to preview and disable editing
 *  placeholder — muted text shown when value is empty
 */

import { memo, useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

export interface MarkdownEditorProps {
  value: string;
  onChange: (next: string) => void;
  streaming?: boolean;
  placeholder?: string;
}

// Memoised: while one page streams, Review re-renders on every token (even
// with the rAF buffer, at up to 60/s). Without this boundary, a page whose
// markdown hasn't changed would still re-run the full remark/KaTeX pipeline
// on each of those renders — the actual cost (see MarkdownBody below).
export const MarkdownEditor = memo(function MarkdownEditor({
  value,
  onChange,
  streaming = false,
  placeholder = "Nothing here yet.",
}: MarkdownEditorProps) {
  const [editing, setEditing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Enter edit mode (disabled while streaming).
  const enterEdit = useCallback(() => {
    if (streaming) return;
    setEditing(true);
  }, [streaming]);

  // Exit edit mode on blur.
  const exitEdit = useCallback(() => {
    setEditing(false);
  }, []);

  // Auto-focus the textarea when entering edit mode.
  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [editing]);

  // If streaming starts while in edit mode, return to preview.
  useEffect(() => {
    if (streaming) setEditing(false);
  }, [streaming]);

  if (editing) {
    return (
      <textarea
        ref={textareaRef}
        aria-label="Markdown editor"
        className="flex-1 resize-none bg-transparent font-mono text-sm text-primary p-3 outline-none leading-relaxed min-h-[400px] w-full"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={exitEdit}
        spellCheck={false}
        placeholder={placeholder}
      />
    );
  }

  // Preview mode. The container is NOT a button: rendered Markdown contains its
  // own links, and a button wrapping interactive content is invalid. Editing is
  // reached via the explicit Edit button (keyboard/AT) or a click on empty area
  // (mouse convenience — link clicks are let through).
  return (
    <div className="group relative flex-1 flex flex-col min-h-[400px]">
      {!streaming && (
        <button
          type="button"
          aria-label="Edit transcript"
          title="Edit"
          className="absolute top-2 right-2 z-10 btn-ghost text-2xs px-2 py-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
          onClick={enterEdit}
        >
          Edit
        </button>
      )}
      <div
        className={[
          "flex-1 overflow-y-auto p-3",
          streaming ? "cursor-default" : "cursor-text",
        ].join(" ")}
        onClick={
          streaming
            ? undefined
            : (e) => {
                // Click-to-edit for mouse users; let clicks on links work normally.
                if (!(e.target as HTMLElement).closest("a")) enterEdit();
              }
        }
      >
        {value.trim() === "" ? (
          <PlaceholderText text={placeholder} />
        ) : streaming ? (
          <StreamingText text={value} />
        ) : (
          <MarkdownBody markdown={value} />
        )}
      </div>
    </div>
  );
});

// ── Sub-components ────────────────────────────────────────────────────────────

function PlaceholderText({ text }: { text: string }) {
  return (
    <p className="text-sm text-muted italic select-none">{text}</p>
  );
}

/**
 * StreamingText — raw text shown while OCR is still writing the page.
 *
 * ponytail: rendering raw text during streaming skips re-running the full
 * remark → rehype → KaTeX pipeline on every token (the page's biggest render
 * cost). The formatted Markdown renders once, when the page finishes.
 */
function StreamingText({ text }: { text: string }) {
  return (
    <pre className="m-0 font-mono text-sm text-primary leading-relaxed whitespace-pre-wrap break-words">
      {text}
    </pre>
  );
}

/**
 * MarkdownBody — renders a Markdown string with GFM + KaTeX math.
 *
 * Prose styling is applied via explicit Tailwind classes on each element
 * (no @tailwindcss/typography required). Covers headings, paragraphs,
 * lists, blockquotes (including GitHub-style callouts), inline/block code,
 * tables, horizontal rules, and links.
 *
 * Belt-and-braces memo: react-markdown v9 re-runs the full unified pipeline
 * (remark-gfm, remark-math, rehype-katex) synchronously on every render with
 * no internal memoisation of its own — this is the actual cost the
 * MarkdownEditor memo boundary exists to avoid. Memoising here too means even
 * an in-editor state change that isn't a markdown change (e.g. toggling
 * `editing`) can't force a re-parse.
 */
const MarkdownBody = memo(function MarkdownBody({ markdown }: { markdown: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={PROSE_COMPONENTS}
    >
      {markdown}
    </ReactMarkdown>
  );
});

/**
 * Custom renderers that produce readable prose without @tailwindcss/typography.
 * Every block element gets explicit spacing and color classes so the rendered
 * output matches the project's design tokens.
 */
const PROSE_COMPONENTS: React.ComponentProps<typeof ReactMarkdown>["components"] = {
  // Headings
  h1: ({ children }) => (
    <h1 className="text-lg font-semibold text-primary mt-4 mb-2 leading-snug first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-semibold text-primary mt-3 mb-1.5 leading-snug">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold text-primary mt-2.5 mb-1 leading-snug">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-sm font-medium text-secondary mt-2 mb-1">{children}</h4>
  ),

  // Paragraph
  p: ({ children }) => (
    <p className="text-sm text-primary leading-relaxed mb-2 last:mb-0">{children}</p>
  ),

  // Lists
  ul: ({ children }) => (
    <ul className="text-sm text-primary list-disc list-inside mb-2 space-y-0.5 pl-1">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="text-sm text-primary list-decimal list-inside mb-2 space-y-0.5 pl-1">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="leading-relaxed">{children}</li>
  ),

  // Blockquote — covers plain quotes and GitHub-style callouts like > [!note]
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-accent/50 pl-3 my-2 text-sm text-secondary italic">
      {children}
    </blockquote>
  ),

  // Inline code
  code: ({ children, className }) => {
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return (
        <code className="block bg-surface-2 rounded-md px-3 py-2 text-xs font-mono text-primary overflow-x-auto my-2 whitespace-pre">
          {children}
        </code>
      );
    }
    return (
      <code className="bg-surface-2 rounded px-1 py-0.5 text-xs font-mono text-primary">{children}</code>
    );
  },

  // Fenced code block wrapper
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto">{children}</pre>
  ),

  // Table
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full text-xs text-primary border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-default">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="text-left font-medium text-secondary px-2 py-1">{children}</th>
  ),
  td: ({ children }) => (
    <td className="px-2 py-1 border-b border-default/50">{children}</td>
  ),

  // Horizontal rule
  hr: () => (
    <hr className="my-3 border-default" />
  ),

  // Links
  a: ({ href, children }) => (
    <a
      href={href}
      className="text-accent underline underline-offset-2 hover:opacity-80"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),

  // Strong / em
  strong: ({ children }) => (
    <strong className="font-semibold text-primary">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic">{children}</em>
  ),
};
