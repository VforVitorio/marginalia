/**
 * SuggestionChips — a row of clickable pill buttons for path suggestions.
 *
 * The selected chip gets an active-tint (terracotta border + subtle fill);
 * all others get the muted default look. Clicking a chip calls onSelect with
 * that suggestion's value.
 *
 * Used by the Import step (scan-folder suggestions) and the Export step
 * (vault-path suggestions). Rendered only when suggestions.length > 0.
 */

interface SuggestionChipsProps {
  suggestions: string[];
  selected: string;
  onSelect: (s: string) => void;
}

export function SuggestionChips({ suggestions, selected, onSelect }: SuggestionChipsProps) {
  return (
    <div className="flex flex-wrap gap-1" role="list" aria-label="Suggestions">
      {suggestions.map((suggestion) => (
        <button
          key={suggestion}
          type="button"
          role="listitem"
          className={[
            "text-2xs font-mono px-2.5 py-1 rounded-full border transition-colors truncate max-w-full",
            selected === suggestion
              ? "border-terracotta-400/60 bg-terracotta-300/10 text-primary"
              : "border-default bg-surface-2 text-muted hover:border-terracotta-400/40 hover:text-primary",
          ].join(" ")}
          title={suggestion}
          onClick={() => onSelect(suggestion)}
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
}
