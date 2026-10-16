// Optional live UI smoke check. Requires Playwright and scripts/run_voyara.py.
const { chromium } = require("playwright");
const fs = require("node:fs/promises");
const path = require("node:path");
const { randomBytes } = require("node:crypto");

(async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || "msedge" });
  const page = await browser.newPage({ viewport: { width: 1365, height: 1000 }, reducedMotion: "reduce" });
  const origin = process.env.VOYARA_URL || "http://127.0.0.1:8088";
  const name = "demo_" + Date.now();
  const responses = [];
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("response", async response => {
    if (response.url().endsWith("/messages") && response.request().method() === "POST") {
      responses.push(await response.json());
    }
  });
  try {
    await page.goto(origin + "/signup");
    await page.getByLabel("Email", { exact: true }).fill(name + "@example.com");
    await page.getByLabel("Username", { exact: true }).fill(name);
    await page.getByLabel("Password", { exact: true }).fill(randomBytes(24).toString("hex"));
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    await page.waitForURL("**/trips");
    console.log("Signed in through the application UI.");
    await page.getByRole("button", { name: "Search & chat" }).click();
    await page.getByRole("tab", { name: "AI advice" }).click();
    await page.getByText("Trip details", { exact: true }).click();
    await page.getByLabel("Destination", { exact: true }).fill("Goa");
    await page.getByLabel("Total budget (INR)", { exact: true }).fill("100000");
    await page.getByLabel("Start date", { exact: true }).fill("2026-12-01");
    await page.getByLabel("End date", { exact: true }).fill("2026-12-05");
    await page.getByLabel("Travelers", { exact: true }).fill("2");
    await page.getByLabel(/^Pace/).selectOption("relaxed");
    await page.getByLabel("Vegetarian food", { exact: true }).check();
    await page.getByRole("button", { name: "Confirm trip details", exact: true }).click();
    await page.getByText("Trip details saved. Ask ‘Plan my trip’ to build a draft.", { exact: true }).waitFor({ timeout: 180000 });
    console.log("Confirmed trip details through the UI and real memory engine.");
    await page.getByRole("button", { name: "Send question", exact: true }).click();
    await page.locator(".helper-message-system").filter({ hasText: "Estimated cost:" }).first().waitFor({ timeout: 180000 });
    if (responses.at(-1)?.orchestration?.status !== "ok") throw new Error("The agent plan was not ready.");
    console.log("Rendered a plan from the connected agents.");
    await page.getByLabel("Ask for travel advice").fill("Lower my budget to INR 80000");
    await page.getByRole("button", { name: "Send question", exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll(".helper-message-system").length === 2);
    if (responses.at(-1)?.orchestration?.trip_brief?.budget_total_inr !== 80000) throw new Error("The new budget did not reach the agents.");
    const memory = responses.at(-1).orchestration.memory;
    if (!memory.some(packet => packet.claim_ids.length)) throw new Error("No memory evidence reached the workflow.");
    await page.reload();
    await page.getByRole("button", { name: "Search & chat" }).click();
    await page.getByRole("tab", { name: "AI advice" }).click();
    await page.locator(".helper-message-system").filter({ hasText: "Estimated cost:" }).first().waitFor();
    console.log("Confirmed budget update and chat recovery after reload.");
    const report = path.resolve("report/application_integration_20261016");
    await fs.mkdir(report, { recursive: true });
    await page.locator(".travel-helper-panel").screenshot({ path: path.join(report, "desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator(".travel-helper-panel").screenshot({ path: path.join(report, "mobile.png") });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    if (overflow) throw new Error("The mobile page overflows horizontally.");
    if (errors.length) throw new Error("Browser errors: " + errors.join("; "));
    await fs.writeFile(path.join(report, "browser-check.json"), JSON.stringify({
      signup: true, requirements: true, connected_plan: true, budget_update: true,
      persisted_chat: true, mobile_overflow: false, browser_errors: errors,
      embedding_scope: "live application neural embeddings; no hosted generative model",
      memory_devices: [...new Set(memory.map(packet => packet.residency.device))],
    }, null, 2));
    console.log("Browser smoke check passed; screenshots and diagnostics saved.");
  } catch (error) {
    const report = path.resolve("report/application_integration_20261016");
    await fs.mkdir(report, { recursive: true });
    await page.screenshot({ path: path.join(report, "failure.png"), fullPage: true });
    throw error;
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
