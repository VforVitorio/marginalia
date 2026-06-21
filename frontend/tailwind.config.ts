import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Warm paper palette — light mode
        parchment: {
          50: "#fdf8f0",
          100: "#f9eedb",
          200: "#f2dbb8",
          300: "#e8c28d",
          400: "#dca46a",
          500: "#c8834a",
          600: "#a96238",
          700: "#8a4a2c",
          800: "#6e3823",
          900: "#5a2e1e",
        },
        // Ink palette
        ink: {
          50: "#f4f0eb",
          100: "#e5ddd2",
          200: "#c8baaa",
          300: "#a99281",
          400: "#8a7060",
          500: "#6b5244",
          600: "#52403a",
          700: "#3d3030",
          800: "#2a2222",
          900: "#1a1515",
          950: "#0e0c0c",
        },
        // Accent — muted terracotta
        terracotta: {
          300: "#d4937a",
          400: "#c47a60",
          500: "#b06448",
          600: "#924e36",
        },
        // Dark mode surface
        obsidian: {
          800: "#1c1917",
          850: "#161412",
          900: "#100f0d",
          950: "#0a0908",
        },
      },
      fontFamily: {
        // Serif for display / headings
        serif: ["Lora", "Georgia", "serif"],
        // Sans for UI text
        sans: ["DM Sans", "system-ui", "sans-serif"],
        // Mono for markdown content
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        "4xl": "2rem",
      },
      animation: {
        "pulse-soft": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        shimmer: "shimmer 2s linear infinite",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      boxShadow: {
        "inner-warm": "inset 0 1px 3px 0 rgba(90,46,30,0.08)",
        warm: "0 2px 8px 0 rgba(90,46,30,0.12), 0 1px 3px 0 rgba(90,46,30,0.08)",
        "warm-lg":
          "0 8px 24px 0 rgba(90,46,30,0.14), 0 2px 8px 0 rgba(90,46,30,0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
