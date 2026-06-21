/**
 * ThemeToggle — switches between light and dark mode via the `class` strategy.
 * Persists preference to localStorage.
 */

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState<boolean>(() => {
    const stored = localStorage.getItem("marginalia.theme");
    if (stored === "dark") return true;
    if (stored === "light") return false;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (dark) {
      root.classList.add("dark");
      localStorage.setItem("marginalia.theme", "dark");
    } else {
      root.classList.remove("dark");
      localStorage.setItem("marginalia.theme", "light");
    }
  }, [dark]);

  return (
    <button
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className="btn-ghost w-8 h-8 p-0 flex items-center justify-center rounded-lg"
      onClick={() => setDark((d) => !d)}
    >
      {dark ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

function SunIcon() {
  return (
    <svg className="w-4 h-4 text-secondary" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3.05 3.05l1.06 1.06M11.89 11.89l1.06 1.06M11.89 4.11l1.06-1.06M3.05 12.95l1.06-1.06"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg className="w-4 h-4 text-secondary" viewBox="0 0 16 16" fill="none">
      <path
        d="M13.5 9A6 6 0 017 2.5a6 6 0 100 11A5.99 5.99 0 0013.5 9z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
