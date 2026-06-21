/**
 * Spinner — small, accessible loading indicator.
 */

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  label?: string;
}

const SIZE_MAP = {
  sm: "w-4 h-4",
  md: "w-6 h-6",
  lg: "w-8 h-8",
};

export function Spinner({ size = "md", label = "Loading…" }: SpinnerProps) {
  return (
    <span role="status" aria-label={label} className="inline-flex">
      <svg
        className={`${SIZE_MAP[size]} animate-spin text-accent`}
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="3"
          opacity="0.25"
        />
        <path
          d="M22 12a10 10 0 01-10 10"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}
