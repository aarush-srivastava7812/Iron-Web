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
  await page.goto("/tinyfish?mode=live");
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
  await page.goto("/tinyfish?mode=live");
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
  test(`${name} presents eighteen accessible slides without page scrolling`, async ({
    page,
  }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const content = await readFile(resolve(root, name), "utf8");
    await page.goto("about:blank");
    await page.setContent(content, { waitUntil: "domcontentloaded" });
    // The deck remains self-contained: budget markup separately from embedded screenshots.
    expect(Buffer.byteLength(content.replace(/data:image\/jpeg;base64,[A-Za-z0-9+/=]+/g, "embedded-dashboard-image"), "utf8")).toBeLessThan(85000);
    expect(Buffer.byteLength(content, "utf8")).toBeLessThan(500000);
    await expect(page.locator(".slide")).toHaveCount(18);
    await expect(page.locator("#evidence .explanation-grid article")).toHaveCount(3);
    await expect(page.locator("#tools")).toContainText("no automatic Search → Fetch → Agent escalation");
    await expect(page.locator(".slide:visible")).toHaveCount(1);
    await expect(page.locator("#intro")).toBeVisible();
    await expect(page.getByRole("button", {name:"Previous slide"})).toBeDisabled();
    await page.getByRole("button", {name:"Next slide"}).click();
    await expect(page.locator("#system")).toBeVisible();
    await page.keyboard.press("ArrowRight");
    await expect(page.locator("#memory")).toBeVisible();
    await expect(page.locator("#memory h3")).toHaveText(["Vector alone", "Graph alone"]);
    await expect(page.locator("#memory .dashboard-capture img")).toHaveCount(3);
    await expect.poll(() => page.locator("#memory .dashboard-capture img").evaluateAll(images => images.every(image => image.complete && image.naturalWidth > 0))).toBeTruthy();
    for (const kind of ["vector", "graph", "hybrid"]) {
      await expect(page.locator(`#memory .${kind}-capture img`)).toHaveAttribute("src", /^data:image\/jpeg;base64,/);
      await expect(page.locator(`#memory .${kind}-capture figcaption`)).toContainText("schematic");
      const trigger = page.getByRole("button", {name:`Expand ${kind} diagram`});
      const thumbnail = page.locator(`#memory .${kind}-capture img`);
      await trigger.click();
      const viewer = page.getByRole("dialog", {name:new RegExp(`${kind} memory diagram`, "i")});
      await expect(viewer).toBeVisible();
      await expect(viewer.locator("img")).toHaveAttribute("src", await thumbnail.getAttribute("src"));
      await page.keyboard.press("ArrowRight");
      await expect(page.locator("#memory")).toBeVisible();
      if (kind === "graph") await page.getByRole("button", {name:"Close expanded image"}).click();
      else await page.keyboard.press("Escape");
      await expect(viewer).toBeHidden();
      await expect(trigger).toBeFocused();
    }
    await page.getByRole("button", {name:"Expand vector diagram"}).press("Enter");
    await expect(page.locator("#image-viewer")).toBeVisible();
    await page.keyboard.press("Escape");
    const integration = page.getByRole("button", {name:"TinyFish integration"});
    await expect(integration).toHaveAttribute("aria-pressed", "false");
    await expect(page.locator("#tinyfish-memory-overlay")).toBeHidden();
    await integration.click();
    await expect(integration).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator("#tinyfish-memory-overlay")).toContainText("SQL evidence versions");
    await expect(page.locator("#tinyfish-memory-overlay")).toBeVisible();
    await integration.press("Space");
    await expect(integration).toHaveAttribute("aria-pressed", "false");
    await expect(page.locator("#memory")).toBeVisible();
    await integration.press("Enter");
    await expect(integration).toHaveAttribute("aria-pressed", "true");
    await page.locator("#memory h2").click();
    await page.keyboard.press("Space");
    await expect(page.locator("#tinyfish")).toBeVisible();
    await page.keyboard.press("Home");
    await expect(page.locator("#intro")).toBeVisible();
    await page.getByLabel("Go to slide").selectOption("results");
    const section = page.locator("#results");
    await expect(
      section.getByRole("heading", {
        name: "Can memory find the evidence?",
      }),
    ).toBeVisible();
    await expect(section.locator(".bench-row")).toHaveCount(3);
    const measurements = JSON.parse(await readFile(resolve(root, "report/tinyfish_memory/memory-benchmarks.json"), "utf8"));
    for (const [index, dataset] of measurements.datasets.entries()) {
      await expect(section.locator(".bench-row").nth(index).locator(".bench-value").first())
        .toContainText(`${(100 * dataset.native.recall_at_5).toFixed(1)}%`);
    }
    await expect(section.getByText(/No TinyFish calls in this test/)).toBeVisible();
    await page.getByLabel("Go to slide").selectOption("impact");
    await expect(page.locator("#impact .big")).toHaveText("90%");
    await expect(page.locator("#impact .metric")).toHaveCount(4);
    await expect(page.locator("#impact").getByText("Controlled test · mock transport", {exact:true})).toBeVisible();
    await expect(page.locator("#impact").getByText("Real TinyFish call", {exact:true})).toBeVisible();
    await page.getByLabel("Go to slide").selectOption("tinyfish");
    await expect(page.locator("#tinyfish .research-role")).toHaveCount(4);
    await expect(page.locator("#tinyfish .planning-roles span")).toHaveCount(4);
    await expect(page.locator("#tinyfish .tool-belt h3")).toHaveText(["Search", "Fetch", "Agent"]);
    await expect(page.locator("#tinyfish .optional-tool")).toContainText("OPTIONAL ADAPTER");
    await page.getByLabel("Go to slide").selectOption("results");
    await expect(page.locator("#counter")).toHaveText("11 / 18");
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuemax", "18");
    await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "11");
    await page.screenshot({path: resolve(root, `report/tinyfish_memory/${name.replace(".html", "")}-desktop.png`)});
    await page.keyboard.press("End");
    await expect(page.locator("#conclusion")).toBeVisible();
    await expect(page.getByRole("button", {name:"Next slide"})).toBeDisabled();
    await page.getByLabel("Go to slide").selectOption("verification");
    await page.getByRole("button", {name:"Measurement details & reports ↗"}).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByRole("dialog").getByRole("link", {name:"Live site measurements"})).toHaveAttribute("href", "report/tinyfish_memory/site-smoke.json");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).not.toBeVisible();
    for (const dataset of measurements.datasets) {
      await page.getByLabel("Go to slide").selectOption(dataset.benchmark);
      const result = page.locator(`#${dataset.benchmark}`);
      await expect(result.locator(".dataset-bar strong")).toHaveText([
        `${(100 * dataset.lexical.recall_at_5).toFixed(1)}%`,
        `${(100 * dataset.native.recall_at_5).toFixed(1)}%`,
      ]);
      await expect(result.locator(".dataset-metrics strong").nth(1)).toHaveText(`${dataset.native.median_ms.toFixed(1)} ms`);
      await expect(result).toContainText("No TinyFish calls.");
    }
    await page.evaluate(() => { location.hash = "#results"; });
    await expect(section).toBeVisible();
    await page.getByRole("button", {name:"Enter fullscreen",exact:true}).click();
    await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBeTruthy();
    await page.evaluate(() => document.exitFullscreen());
    for (const viewport of [{width:1850,height:900},{width:1440,height:900},{width:652,height:860},{width:390,height:844},{width:320,height:568},{width:844,height:390}]) {
      await page.setViewportSize(viewport);
      for (const slide of ["intro","system","memory","tinyfish","vector-memory","graph-memory","evidence","tools","workflow","impact","results","verification","locomo","dmr","longmemeval","latency","protocol","conclusion"]) {
        await page.getByLabel("Go to slide").selectOption(slide);
        await expect.poll(async () => page.evaluate(() => {
          const frame = document.querySelector('.slide:not([hidden])').getBoundingClientRect();
          const body = document.querySelector('.slide:not([hidden]) .slide-content').getBoundingClientRect();
          return body.top >= frame.top-1 && body.bottom <= frame.bottom+1 && body.left >= frame.left-1 && body.right <= frame.right+1;
        })).toBeTruthy();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1 && document.documentElement.scrollHeight <= innerHeight+1)).toBeTruthy();
        await expect(page.locator(".slide:visible")).toHaveCount(1);
        if (viewport.width === 1850) {
          expect(await page.locator(`#${slide} .slide-content`).evaluate(el => el.getBoundingClientRect().width / innerWidth)).toBeGreaterThan(0.8);
        }
        if (slide === "memory") {
          await page.getByRole("button", {name:"Expand hybrid diagram"}).click();
          await expect(page.locator("#image-viewer")).toBeVisible();
          expect(await page.locator("#image-viewer").evaluate(el => {
            const box=el.getBoundingClientRect();
            return box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight;
          })).toBeTruthy();
          await page.keyboard.press("Escape");
          // Both overlay states must fit, including narrow and landscape screens.
          for (const enabled of [false, true]) {
            if ((await integration.getAttribute("aria-pressed")) !== String(enabled)) await integration.click();
            await expect.poll(async () => page.evaluate(() => {
              const frame = document.querySelector('#memory').getBoundingClientRect();
              const body = document.querySelector('#memory .slide-content').getBoundingClientRect();
              return body.top >= frame.top-1 && body.bottom <= frame.bottom+1 && body.left >= frame.left-1 && body.right <= frame.right+1;
            })).toBeTruthy();
            await expect(page.locator("#tinyfish-memory-overlay")).toBeVisible({visible:enabled});
          }
        }
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
