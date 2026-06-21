/**
 * Playwright screenshot harness for visual verification.
 *
 * Usage:
 *   node scripts/shot.mjs [url] [output-path]
 *
 * Defaults:
 *   url         → http://localhost:5173
 *   output-path → shot.png (in the current working directory)
 *
 * Requires @playwright/test in devDependencies.
 * Install chromium once: npx playwright install chromium
 *
 * Example:
 *   node scripts/shot.mjs http://localhost:5173 C:/tmp/before.png
 *   node scripts/shot.mjs http://localhost:5173 C:/tmp/after.png
 */

import { chromium } from "@playwright/test";

const url = process.argv[2] ?? "http://localhost:5173";
const outPath = process.argv[3] ?? "shot.png";

const browser = await chromium.launch();

const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
});

const page = await ctx.newPage();

await page.addInitScript(() => {
  // Seed localStorage to skip any first-run gates or theme flicker.
  // marginalia uses "marginalia.theme" — seed to light for consistent screenshots.
  // Adjust if dark-mode screenshots are needed (set to "dark").
  localStorage.setItem("marginalia.theme", "light");
});

await page.goto(url, { waitUntil: "networkidle" });

// Allow GSAP animations and fonts to settle.
await page.waitForTimeout(1500);

await page.screenshot({ path: outPath, fullPage: true });

await browser.close();

console.log(`Screenshot saved to: ${outPath}`);
