/**
 * PanelError — small inline error line used inside provider action panels.
 *
 * Renders the shared error paragraph style: `text-2xs` with `var(--color-error)`
 * foreground and a small vertical padding. Used by LoadPanel, KeyPanel, and
 * PullPanel inside ProviderPicker.
 */

interface PanelErrorProps {
  message: string;
}

export function PanelError({ message }: PanelErrorProps) {
  return (
    <p className="text-2xs py-1" style={{ color: "var(--color-error)" }}>
      {message}
    </p>
  );
}
