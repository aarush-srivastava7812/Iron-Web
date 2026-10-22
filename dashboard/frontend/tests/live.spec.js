import { test, expect } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const report = process.env.IRONWEB_LIVE_REPORT_DIR
  ? resolve(
      import.meta.dirname,
      "../../..",
      process.env.IRONWEB_LIVE_REPORT_DIR,
    )
  : resolve(import.meta.dirname, "../../../report/dashboard_live");
test.beforeEach(async ({ page }) => {
  const origin = "http://127.0.0.1:8094";
  const response = await page.request.post(origin + "/api/auth/developer", {
    headers: { Origin: origin, "X-Voyara-Developer": "1" },
  });
  expect(response.ok()).toBeTruthy();
});

test("real live feed synchronizes graph, inspector, replay, resources and layout", async ({
  page,
}) => {
  const errors = [],
    requests = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => requests.push(r.url()));
  await page.goto("/");
  await expect(page.getByTestId("live-dashboard")).toBeVisible({
    timeout: 60000,
  });
  const response = await page.request.get(
    "http://127.0.0.1:8200/api/dashboard/snapshot",
  );
  expect(response.status()).toBe(200);
  const data = await response.json();
  expect(data.agents.registered).toBe(9);
  if (process.env.IRONWEB_TEST_TRIP_ID)
    expect(data.observations.events.length).toBeGreaterThan(0);
  const testedTrip =
    process.env.IRONWEB_TEST_TRIP_ID ||
    data.observations.events.find((e) => e.trip_id)?.trip_id;
  if (testedTrip)
    expect(
      data.observations.events.some((e) => e.trip_id === testedTrip),
    ).toBeTruthy();
  // Read-only native feeds can legitimately have no hosted inference calls.
  // Opt-in provider acceptance still requires the test trip to have used one.
  expect(data.credentials.hosted_calls).toBeGreaterThanOrEqual(0);
  expect(data.credentials.provider).toBeTruthy();
  if (process.env.IRONWEB_TEST_TRIP_ID) {
    expect(data.credentials.hosted_calls).toBeGreaterThan(0);
    expect(data.credentials.usage.input_tokens).toBeGreaterThan(0);
  }
  expect(
    data.shared_memory.claims.some(
      (c) =>
        c.properties.predicate === "destination" &&
        (process.env.IRONWEB_TEST_DESTINATION
          ? c.properties.value_json.includes(
              process.env.IRONWEB_TEST_DESTINATION,
            )
          : Boolean(c.properties.value_json)),
    ),
  ).toBeTruthy();
  await expect(
    page.getByRole("button", { name: "Follow live", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Filter agents", exact: true })
    .click();
  await page.getByRole("button", { name: /Planner.*reads/ }).click();
  await expect(
    page.getByRole("button", { name: "Clear Planner filter", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Clear Planner filter", exact: true })
    .click();
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 1280, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    await mkdir(report, { recursive: true });
    for (const view of [
      "Memory graph",
      "Agents",
      "Activity",
      "Architecture",
      "Resources",
    ]) {
      await page
        .getByRole("navigation", { name: "Dashboard pages" })
        .getByRole("link", { name: view, exact: true })
        .click();
      expect(
        await page.evaluate(() => ({
          w: document.documentElement.scrollWidth,
          h: document.documentElement.scrollHeight,
        })),
      ).toEqual({ w: viewport.width, h: viewport.height });
      const stage = await page.locator(".live-stage").boundingBox();
      expect(stage.width).toBeGreaterThan(viewport.width / 2);
      await expect(
        page.getByRole("heading", { name: view, exact: true, level: 1 }),
      ).toBeVisible();
      await expect(
        page
          .getByRole("navigation", { name: "Dashboard pages" })
          .getByRole("link", { name: view, exact: true }),
      ).toHaveAttribute("aria-current", "page");
      if (view === "Activity") {
        const dock = await page.locator(".live-dock").boundingBox();
        expect(dock.y + dock.height).toBeLessThanOrEqual(viewport.height);
      }
      await page.screenshot({
        path: resolve(
          report,
          `${viewport.width}x${viewport.height}-${view.toLowerCase().replaceAll(" ", "-")}.png`,
        ),
      });
    }
  }
  await page.getByRole("button", { name: "Cache", exact: true }).click();
  await expect(page.getByText(/Context cache hit rate/)).toBeVisible();
  await page.getByRole("button", { name: "Provider", exact: true }).click();
  await expect(
    page.getByText("Observed HTTP inference requests", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Hardware", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Runtime hardware", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Latency", exact: true }).click();
  await expect(page.locator(".live-resources")).toBeVisible();
  await page
    .getByRole("navigation", { name: "Dashboard pages" })
    .getByRole("link", { name: "Activity", exact: true })
    .click();
  if (data.observations.events.length > 1) {
    await page
      .getByRole("button", { name: "Reset replay", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Follow live", exact: true }),
    ).toHaveAttribute("aria-pressed", "false");
    await page.getByRole("button", { name: "Next event", exact: true }).click();
    await expect(page).toHaveURL(/event=/);
    await page
      .getByRole("button", { name: "Follow live", exact: true })
      .click();
  }
  await page
    .getByRole("navigation", { name: "Dashboard pages" })
    .getByRole("link", { name: "Memory graph", exact: true })
    .click();
  const node = page.locator("[data-memory-id]").first();
  // A force-layout node can keep moving between real source snapshots. Click
  // its current position without Playwright's stationary-element prerequisite.
  await node.click({ force: true });
  await expect(page).toHaveURL(/mem=/);
  await page.getByRole("tab", { name: "Links", exact: true }).click();
  await expect(page.locator(".inspector-scroll")).toContainText(
    "relationships",
  );
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.locator(".inspector-scroll")).toBeVisible();
  await page.getByRole("tab", { name: "Diff", exact: true }).click();
  expect(requests.some((url) => url.includes("events.json"))).toBeFalsy();
  await page
    .getByRole("button", { name: "Source & credentials", exact: true })
    .click();
  await page.getByText(/Memory vector payloads/).click();
  await page
    .getByRole("button", { name: "Inspect numeric vector", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    '"values_included": true',
  );
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await writeFile(
    resolve(report, "verified-summary.json"),
    JSON.stringify(
      {
        trip_id: testedTrip,
        registered_agents: data.agents.registered,
        observed_events: data.observations.events.length,
        tested_trip_events: data.observations.events.filter(
          (e) => e.trip_id === testedTrip,
        ).length,
        captured_contexts: data.tiers.captured_contexts.length,
        no_events_fixture_requested: !requests.some((url) =>
          url.includes("events.json"),
        ),
        browser_errors: errors,
        scope:
          "Counts only; no raw memory, context, vector or credential export",
      },
      null,
      2,
    ),
  );
  await writeFile(
    resolve(report, "verified-errors.json"),
    JSON.stringify(errors, null, 2),
  );
  expect(errors).toEqual([]);
});
test("drawers and reduced motion work with the actual feed", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1100, height: 760 });
  await page.goto("/memory");
  await expect(page.getByTestId("live-dashboard")).toBeVisible({
    timeout: 60000,
  });
  await expect(page.locator(".live-explorer")).toBeHidden();
  await page.getByRole("button", { name: "Explorer", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Find a memory" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator(".live-explorer")).toBeHidden();
  await page.getByRole("button", { name: "Inspector", exact: true }).click();
  await expect(page.locator(".live-inspector")).toBeVisible();
  await page
    .getByRole("button", { name: "Close inspector", exact: true })
    .click();
  await page
    .getByRole("navigation", { name: "Dashboard pages" })
    .getByRole("link", { name: "Activity", exact: true })
    .click();
  expect(await page.locator(".live-heatmap-row").count()).toBe(10);
  await page.screenshot({ path: resolve(report, "1100x760-activity.png") });
});

test("a stalled SSE transport marks the real snapshot stale and reconnects", async ({
  page,
}) => {
  test.setTimeout(90000);
  const held = [];
  const stall = (route) => {
    held.push(route);
  };
  // Only the stream transport is held. Initial HTTP and recovered snapshots
  // still come from the actual memory owner; no mock memory is introduced.
  await page.route("**/api/dashboard/stream", stall);
  await page.goto("/");
  // Loading the real snapshot can exceed the default five-second assertion
  // under concurrent test load. Keep the heartbeat deadlines below unchanged.
  await expect(page.getByTestId("live-dashboard")).toBeVisible({
    timeout: 30000,
  });
  await expect(page.locator(".feed-warning")).toContainText(
    "No fresh memory snapshot",
    { timeout: 18000 },
  );
  await page.unroute("**/api/dashboard/stream", stall);
  await Promise.all(
    held.map((route) => route.abort("timedout").catch(() => {})),
  );
  await expect(page.locator(".feed-warning")).toBeHidden({ timeout: 18000 });
  await expect(page.getByTestId("live-dashboard")).toBeVisible();
});
