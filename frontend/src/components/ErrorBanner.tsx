/**
 * ErrorBanner — dismissible inline error notification.
 */

interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border px-3 py-2.5 text-sm"
      style={{
        backgroundColor: "color-mix(in srgb, var(--color-error) 8%, var(--color-surface))",
        borderColor: "color-mix(in srgb, var(--color-error) 30%, transparent)",
        color: "var(--color-error)",
      }}
    >
      <svg className="w-4 h-4 mt-0.5 flex-shrink-0" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3" />
        <path d="M8 5v4M8 11v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
      <span className="flex-1">{message}</span>
      <button
        aria-label="Dismiss error"
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity"
        onClick={onDismiss}
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none">
          <path
            d="M3 3l8 8M11 3l-8 8"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </div>
  );
}
