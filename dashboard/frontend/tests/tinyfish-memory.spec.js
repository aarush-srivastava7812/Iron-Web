import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../../..");
function snapshot() {
  return {
    schema: "iron_web_dashboard_v1",
    timestamp: Date.now() / 1000,
    scope: "browser_fixture",
    connection: {
      mode: "website",
      user_id: "fixture",
      username: "UI fixture (not live)",
    },
    observations: { events: [] },
    graph: { nodes: [], edges: [] },
    shared_memory: { claims: [] },
    agents: { registered: 9, observed: 0, rows: [] },
    storage: { memories: 0 },
    tiers: {
      tokenizer: "fixture",
      policy: { context_limit: 24000 },
      captured_contexts: [],
    },
    tinyfish: {
      configured: true,
      metrics: {
        source_quotes: 1,
        reuse_events: 9,
        fresh: 1,
        plans_flagged: 1,
        stale: 0,
        conflicts: 0,
        graph_indexed: 1,
        refresh_requests: 1,
      },
      scope: "Browser test fixture, not live research activity.",
      evidence: [
        {
          id: "fixture-v2",
          previous_id: "fixture-v1",
          topic: "hours",
          freshness: "fresh",
          verification: "source_statements",
          changed: true,
          graph_synced: true,
          retrieved_at: "2026-10-22T00:00:00Z",
          expires_at: "2026-10-22T06:00:00Z",
          statements: [
            {
              quote: "Seeded museum opening hours for UI testing.",
              source_url: "https://tourism.example.org/jaipur",
            },
          ],
        },
      ],
      jobs: [
        {
          id: "fixture-job",
          destination_id: 1,
          status: "completed",
          topics: ["hours"],
          metrics: {
            elapsed_ms: 1234,
            sources: 3,
            fetched_pages: 2,
            source_quotes: 1,
          },
        },
      ],
      events: [
        {
          id: 1,
          kind: "plan_flagged",
          timestamp: Date.now() / 1000,
          detail: { topics: ["hours"] },
        },
      ],
    },
  };
}

async function feed(page, data) {
  await page.route("**/api/dashboard/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/connection"))
      return route.fulfill({
        json: { mode: "website", website_url: "http://127.0.0.1:8094" },
      });
    if (url.includes("/session"))
      return route.fulfill({ json: { connection: data.connection } });
    if (url.includes("/stream"))
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `event: snapshot\ndata: ${JSON.stringify(data)}\n\n`,
      });
    return route.fulfill({ json: data });
  });
}

test("TinyFish evidence, measured counters, navigation and mobile layout", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await feed(page, snapshot());
  await page.goto("/tinyfish");
  await expect(
    page.getByRole("heading", { name: "TinyFish intelligence", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Seeded museum opening hours for UI testing.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Changed source evidence: review applicability."),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Read source ↗" }),
  ).toHaveAttribute("href", "https://tourism.example.org/jaipur");
  await expect(
    page.getByText("Version fixture-v2 · Previous fixture-v1"),
  ).toBeVisible();
  await expect(
    page.getByText("Browser test fixture, not live research activity."),
  ).toBeVisible();
  await page.screenshot({
    path: resolve(root, "report/tinyfish_memory/dashboard-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Memory that reconnects to the world." }),
  ).toBeVisible();
  await page
    .getByRole("link", {
      name: "Inspect TinyFish evidence and refresh activity",
    })
    .click();
  await expect(page).toHaveURL(/\/tinyfish/);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: resolve(root, "report/tinyfish_memory/dashboard-mobile.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("Missing evidence feed never substitutes demonstration metrics", async ({
  page,
}) => {
  const data = snapshot();
  delete data.tinyfish;
  await feed(page, data);
  await page.goto("/tinyfish");
  await expect(
    page.getByText("Evidence feed unavailable", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".tf-metrics strong")).toHaveText([
    "—",
    "—",
    "—",
    "—",
  ]);
  await expect(
    page.getByText("No destination research jobs recorded."),
  ).toBeVisible();
});

for (const name of ["system-explained.html", "memory-system-explained.html"]) {
  test(`${name} presents six accessible slides without page scrolling`, async ({
    page,
  }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const content = await readFile(resolve(root, name), "utf8");
    await page.goto("about:blank");
    await page.setContent(content, { waitUntil: "domcontentloaded" });
    expect(Buffer.byteLength(content, "utf8")).toBeLessThan(30000);
    await expect(page.locator(".slide")).toHaveCount(6);
    await expect(page.locator(".slide:visible")).toHaveCount(1);
    await expect(page.locator("#intro")).toBeVisible();
    await expect(page.getByRole("button", {name:"Previous slide"})).toBeDisabled();
    await page.getByRole("button", {name:"Next slide"}).click();
    await expect(page.locator("#system")).toBeVisible();
    await page.keyboard.press("ArrowRight");
    await expect(page.locator("#memory")).toBeVisible();
    await page.keyboard.press("Space");
    await expect(page.locator("#tinyfish")).toBeVisible();
    await page.keyboard.press("Home");
    await expect(page.locator("#intro")).toBeVisible();
    await page.getByLabel("Go to slide").selectOption("results");
    const section = page.locator("#results");
    await expect(
      section.getByRole("heading", {
        name: "What we tested. What improved.",
      }),
    ).toBeVisible();
    await expect(section.locator(".metric")).toHaveCount(6);
    await expect(section.locator(".metric strong").nth(2)).toHaveText("90%");
    await expect(section.getByText("Controlled ablation", {exact:true})).toBeVisible();
    await expect(section.getByText("Live provider check", {exact:true})).toBeVisible();
    await expect(page.locator("#counter")).toHaveText("5 / 6");
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "5");
    await page.screenshot({path: resolve(root, `report/tinyfish_memory/${name.replace(".html", "")}-desktop.png`)});
    await page.keyboard.press("End");
    await expect(page.locator("#verification")).toBeVisible();
    await expect(page.getByRole("button", {name:"Next slide"})).toBeDisabled();
    await page.getByRole("button", {name:"Measurement details & reports ↗"}).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("dialog").getByRole("link", {name:"Live site measurements"})).toHaveAttribute("href", "report/tinyfish_memory/site-smoke.json");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).not.toBeVisible();
    await page.evaluate(() => { location.hash = "#results"; });
    await expect(section).toBeVisible();
    await page.getByRole("button", {name:"Enter fullscreen",exact:true}).click();
    await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBeTruthy();
    await page.evaluate(() => document.exitFullscreen());
    for (const viewport of [{width:1440,height:900},{width:652,height:860},{width:390,height:844},{width:320,height:568},{width:844,height:390}]) {
      await page.setViewportSize(viewport);
      for (const slide of ["intro","system","memory","tinyfish","results","verification"]) {
        await page.getByLabel("Go to slide").selectOption(slide);
        await expect.poll(async () => page.evaluate(() => {
          const frame = document.querySelector('.slide:not([hidden])').getBoundingClientRect();
          const body = document.querySelector('.slide:not([hidden]) .slide-content').getBoundingClientRect();
          return body.top >= frame.top-1 && body.bottom <= frame.bottom+1 && body.left >= frame.left-1 && body.right <= frame.right+1;
        })).toBeTruthy();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1 && document.documentElement.scrollHeight <= innerHeight+1)).toBeTruthy();
        await expect(page.locator(".slide:visible")).toHaveCount(1);
      }
    }
    await page.setViewportSize({width:390,height:844});
    await page.getByLabel("Go to slide").selectOption("results");
    await page.screenshot({
      path: resolve(
        root,
        `report/tinyfish_memory/${name.replace(".html", "")}-mobile.png`,
      ),
      fullPage: false,
    });
    expect(errors).toEqual([]);
  });
}
