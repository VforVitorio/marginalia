/**
 * StepIndicator — the three steps (Import / Review / Export) with the current
 * one highlighted. When `onStepClick` is provided, every step up to `maxStep`
 * is clickable so the user can jump back and forth between visited steps.
 */

interface Step {
  label: string;
  index: number;
}

const STEPS: Step[] = [
  { label: "Import", index: 0 },
  { label: "Review", index: 1 },
  { label: "Export", index: 2 },
];

interface StepIndicatorProps {
  current: number;
  /** Highest step the user is allowed to navigate to (defaults to `current`). */
  maxStep?: number;
  onStepClick?: (index: number) => void;
}

export function StepIndicator({ current, maxStep = current, onStepClick }: StepIndicatorProps) {
  return (
    <nav aria-label="Progress" className="flex items-center gap-0">
      {STEPS.map((step, i) => {
        const isPast = i < current;
        const isActive = i === current;
        const isLast = i === STEPS.length - 1;
        const clickable = onStepClick !== undefined && i <= maxStep && !isActive;

        const node = (
          <div className="flex flex-col items-center gap-1">
            <div
              className={[
                "w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-all duration-300",
                isActive
                  ? "bg-terracotta-500 text-parchment-50 dark:bg-terracotta-400 shadow-warm"
                  : isPast
                    ? "bg-terracotta-300/60 dark:bg-terracotta-600/60 text-parchment-50"
                    : "bg-parchment-200 dark:bg-obsidian-800 text-ink-400 dark:text-ink-400",
              ].join(" ")}
            >
              {isPast ? (
                <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M2.5 7l3.5 3.5 5.5-6"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                <span>{i + 1}</span>
              )}
            </div>
            <span
              className={[
                "text-2xs tracking-wide uppercase",
                isActive ? "text-accent font-medium" : "text-muted",
              ].join(" ")}
            >
              {step.label}
            </span>
          </div>
        );

        return (
          <div key={step.index} className="flex items-center">
            {clickable ? (
              <button
                type="button"
                onClick={() => onStepClick?.(i)}
                aria-label={`Go to ${step.label}`}
                className="appearance-none border-0 bg-transparent p-0 cursor-pointer rounded-lg transition-opacity hover:opacity-80 focus:outline-none focus-visible:ring-2 focus-visible:ring-terracotta-400/50"
              >
                {node}
              </button>
            ) : (
              node
            )}

            {!isLast && (
              <div
                className={[
                  "h-px w-8 mx-1 mb-4 transition-all duration-300",
                  isPast || isActive
                    ? "bg-terracotta-400/60 dark:bg-terracotta-600/60"
                    : "bg-parchment-200 dark:bg-obsidian-800",
                ].join(" ")}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
