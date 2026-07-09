/**
 * ErrorBoundary — top-level fallback for uncaught render errors.
 *
 * React unmounts the whole tree on an uncaught render error, which — with no
 * boundary anywhere above `App` — left the SPA as a blank page (issue #144 /
 * FE-13). This boundary sits once around `App` in main.tsx and swaps in a
 * minimal, dependency-free fallback instead, so a single component bug never
 * blanks the entire app.
 */

import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Unhandled render error:", error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;

    return (
      <div
        role="alert"
        className="flex h-screen flex-col items-center justify-center gap-3 p-8 text-center"
        style={{
          backgroundColor: "var(--color-surface, #fdf8f0)",
          color: "var(--color-text, #2a2222)",
        }}
      >
        <p className="text-lg font-semibold">Something went wrong.</p>
        <p className="text-sm" style={{ color: "var(--color-text-2, #52403a)" }}>
          Please reload the page. If the problem persists, restart marginalia.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 rounded-lg px-5 py-2 text-sm font-medium"
          style={{
            backgroundColor: "var(--color-accent, #b06448)",
            color: "var(--color-surface, #fdf8f0)",
          }}
        >
          Reload
        </button>
      </div>
    );
  }
}
