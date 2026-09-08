const { chromium } = require("playwright");
const path = require("path");

const URL = "https://flowmate-ai-506118.web.app";
const OUT_DIR = path.join(__dirname, "output");

async function clickTab(page, label) {
  await page.getByRole("tab", { name: label, exact: true }).click();
}

async function showInsight(page) {
  const btn = page.locator(".panel-side-toggle-floating");
  if (await btn.count()) {
    await btn.click();
    await page.waitForTimeout(1200);
  }
}

async function hideInsight(page) {
  const btn = page.locator(".panel-side-toggle");
  if (await btn.count()) {
    await btn.click();
    await page.waitForTimeout(400);
  }
}

async function waitForTable(page) {
  await page.locator(".filterable-table table tbody tr").first().waitFor({ timeout: 30000 });
}

async function scrollTableTo(page, fraction) {
  await page.locator(".table-scroll").evaluate((el, frac) => {
    el.scrollTo({ left: (el.scrollWidth - el.clientWidth) * frac, behavior: "smooth" });
  }, fraction);
}

let t0;
function mark(label) {
  console.log(`${((Date.now() - t0) / 1000).toFixed(1)}s -- ${label}`);
}

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
    recordVideo: { dir: OUT_DIR, size: { width: 1440, height: 900 } },
  });
  const page = await context.newPage();
  t0 = Date.now();

  // 1. Landing -- dashboard loads with the sprint overview (Ticket Watcher, default tab).
  await page.goto(URL, { waitUntil: "networkidle" });
  await waitForTable(page);
  mark("landing: table visible");
  await page.waitForTimeout(4000);

  // 2. Ticket Watcher -- flagged stalled/blocked/unassigned tickets.
  await showInsight(page);
  mark("ticket_watcher: insight shown");
  await page.waitForTimeout(8000);
  await hideInsight(page);
  await page.waitForTimeout(1500);

  // 3. Bottleneck Detector -- at-risk tickets + calibrated miss-risk %.
  await clickTab(page, "Bottleneck Detector");
  await waitForTable(page);
  mark("bottleneck_detector: table visible");
  await page.waitForTimeout(2000);
  await scrollTableTo(page, 1);
  mark("bottleneck_detector: scrolled right");
  await page.waitForTimeout(2500);
  await scrollTableTo(page, 0);
  await page.waitForTimeout(1000);
  await showInsight(page);
  mark("bottleneck_detector: insight shown");
  await page.waitForTimeout(8000);
  await hideInsight(page);
  await page.waitForTimeout(1500);

  // 4. Review Nudger -- drafted follow-up messages, ready to send.
  await clickTab(page, "Review Nudger");
  await waitForTable(page);
  mark("review_nudger: table visible");
  await page.waitForTimeout(3000);
  await showInsight(page);
  mark("review_nudger: insight shown");
  await page.waitForTimeout(8000);
  await hideInsight(page);
  await page.waitForTimeout(1500);

  // 5. Standup Writer -- team-wide AI Insight patterns...
  await clickTab(page, "Standup Writer");
  await waitForTable(page);
  mark("standup_writer: table visible");
  await page.waitForTimeout(3000);
  await showInsight(page);
  mark("standup_writer: insight shown");
  await page.waitForTimeout(8000);
  await hideInsight(page);
  await page.waitForTimeout(1500);

  // ...then the on-demand personal standup: pick an engineer with a real
  // cached result and click Generate so the demo shows genuine live-Gemini
  // output, not a spinner or an error (today's free-tier quota is exhausted).
  await page.locator(".personal-standup select").selectOption({ label: "Allison Hill" });
  await page.waitForTimeout(800);
  await page.locator(".personal-standup button", { hasText: "Generate My Standup" }).click();
  await page.locator(".personal-standup-result").waitFor({ timeout: 15000 });
  mark("personal standup: result shown");
  await page.waitForTimeout(9000);

  await page.waitForTimeout(2000);
  mark("end");
  await context.close();
  await browser.close();

  console.log("Recording saved under:", OUT_DIR);
})();
