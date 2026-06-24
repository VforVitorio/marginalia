/**
 * responsive-shot.mjs — capture the grid-heavy screens (Import, Review) at
 * mobile + desktop widths, light + dark, for the #39 responsive pass.
 * Dev-only. Usage: node scripts/responsive-shot.mjs <pdf> <outdir>
 */
import { chromium } from "@playwright/test";

const PDF = process.argv[2];
const OUT = process.argv[3];
const URL = "http://localhost:5173/";
const DESKTOP = { width: 1440, height: 900 };
const MOBILE = { width: 390, height: 844 };
const log = (m) => console.log(`[shot] ${m}`);

const browser = await chromium.launch({ headless: true });

for (const theme of ["light", "dark"]) {
  const ctx = await browser.newContext({ viewport: DESKTOP });
  const page = await ctx.newPage();
  await page.addInitScript((t) => {
    localStorage.setItem("marginalia.onboarded", "1");
    localStorage.setItem("marginalia.theme", t);
  }, theme);

  await page.goto(URL, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);

  // Import — desktop then mobile
  await page.screenshot({ path: `${OUT}/import-desktop-${theme}.png`, fullPage: true });
  await page.setViewportSize(MOBILE);
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/import-mobile-${theme}.png`, fullPage: true });
  await page.setViewportSize(DESKTOP);
  await page.waitForTimeout(600);

  // Upload → Review
  try {
    await page.setInputFiles('input[type="file"]', PDF);
    await page.waitForSelector("text=Transcript", { timeout: 45000 });
    await page.waitForTimeout(2500); // let a little OCR text stream in
    await page.screenshot({ path: `${OUT}/review-desktop-${theme}.png`, fullPage: true });
    await page.setViewportSize(MOBILE);
    await page.waitForTimeout(800);
    await page.screenshot({ path: `${OUT}/review-mobile-${theme}.png`, fullPage: true });
    log(`${theme}: review captured`);
  } catch (e) {
    log(`${theme}: review failed — ${e.message}`);
  }

  await ctx.close();
}
await browser.close();
log("done");
