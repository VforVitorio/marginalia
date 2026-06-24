/**
 * demo.mjs — record a full end-to-end walkthrough of marginalia for a promo clip.
 *
 * Captures: onboarding → provider peek → import (upload PDF) → review (live OCR
 * streaming, side-by-side) → export (success). Records a .webm; trim/speed later
 * with ffmpeg. Dev-only tool, not part of the build.
 *
 * Usage: node scripts/demo.mjs <pdf> <outdir> <vault>
 */
import { chromium } from "@playwright/test";

const PDF = process.argv[2];
const OUTDIR = process.argv[3];
const VAULT = process.argv[4];
const URL = "http://localhost:5173/";

const log = (m) => console.log(`[demo] ${m}`);
const wait = (p, ms) => p.waitForTimeout(ms);
// Elapsed seconds since recording start — printed as MARK lines so the encoder
// can fast-forward the slow OCR window and keep the rest at reading speed.
const t0 = Date.now();
const elapsed = () => ((Date.now() - t0) / 1000).toFixed(1);

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
  recordVideo: { dir: OUTDIR, size: { width: 1440, height: 900 } },
});
const page = await ctx.newPage();

// A fresh context has no localStorage, so the onboarding modal shows on first
// load. Use domcontentloaded — Vite's HMR socket means networkidle never fires
// (that double-load was the long dead time at the start). Single load only.
await page.goto(URL, { waitUntil: "domcontentloaded" });
await wait(page, 2800);

// ── Onboarding: step through the 3 cards, pausing long enough to read ──
try {
  await wait(page, 2300); // read card 1
  await page.getByRole("button", { name: /next/i }).click({ timeout: 8000 });
  await wait(page, 2300); // read card 2
  await page.getByRole("button", { name: /next/i }).click({ timeout: 8000 });
  await wait(page, 2300); // read card 3
  await page.getByRole("button", { name: /done/i }).click({ timeout: 8000 });
  log("onboarding done");
} catch (e) {
  log("onboarding skipped: " + e.message);
}
await wait(page, 1200);

// ── Provider peek: open the picker to show Claude/local options ────────
try {
  await page.getByRole("button", { name: /claude|choose provider/i }).first().click({ timeout: 5000 });
  await wait(page, 1500);
  await page.keyboard.press("Escape");
  await wait(page, 700);
  log("provider peek done");
} catch (e) {
  log("provider peek skipped: " + e.message);
}

// ── Import: upload the PDF through the hidden file input ───────────────
await wait(page, 800);
await page.setInputFiles('input[type="file"]', PDF);
log("uploaded " + PDF);

// ── Review: stream, then wait until page 1 renders as Markdown/KaTeX ───
await page.waitForSelector("text=Transcript", { timeout: 45000 }).catch(() => log("no Transcript yet"));
log(`MARK stream ${elapsed()}`); // OCR streaming begins (raw text flowing in)
await page.screenshot({ path: OUTDIR + "/01-streaming.png" }).catch(() => {});

// Wait for the first page to finish — the formatted Markdown (a KaTeX math node)
// replacing the raw stream is the moment worth showing.
await page.waitForSelector(".katex", { timeout: 120000 }).catch(() => log("no rendered math"));
await wait(page, 1500);
log(`MARK done ${elapsed()}`); // page 1 rendered — end of the fast-forward window
await page.screenshot({ path: OUTDIR + "/02-rendered.png" }).catch(() => {});

// ── Inline edit: click-to-edit swaps in the source editor, then re-renders ──
try {
  await page.getByRole("button", { name: /edit transcript/i }).click({ timeout: 5000 });
  await wait(page, 2000); // viewer sees the editable Markdown source
  await page.screenshot({ path: OUTDIR + "/03-editing.png" }).catch(() => {});
  await page.locator('img[alt*="original"]').click(); // blur → re-render to KaTeX
  await wait(page, 1500);
  log("inline edit shown");
} catch (e) {
  log("inline edit skipped: " + e.message);
}

// ── Stop to unlock Export, then export to the vault ───────────────────
try {
  await page.getByRole("button", { name: /stop/i }).click({ timeout: 3000 });
  await wait(page, 1000);
} catch { /* already done */ }

try {
  await page.getByRole("button", { name: /^export/i }).first().click({ timeout: 5000 });
  await wait(page, 1500);
  const vault = page.locator("#vault-path");
  if (await vault.count()) {
    await vault.fill(VAULT);
    await wait(page, 700);
  }
  await page.getByRole("button", { name: /export to obsidian/i }).click({ timeout: 5000 });
  await page.waitForSelector("text=Exported", { timeout: 20000 }).catch(() => log("no success screen"));
  await wait(page, 2500);
  await page.screenshot({ path: OUTDIR + "/04-exported.png" }).catch(() => {});
  log("export done");
} catch (e) {
  log("export step issue: " + e.message);
}

await wait(page, 1000);
log(`MARK end ${elapsed()}`);
await ctx.close(); // finalizes the video file
await browser.close();
log("FINISHED — video in " + OUTDIR);
