import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

const saved = JSON.parse(
  await readFile(
    new URL("../public/history-snapshot.json", import.meta.url),
    "utf8",
  ),
);
function liveSnapshot(owner = "Live fixture traveler", memories = 77) {
  const data = structuredClone(saved);
  delete data.replay;
  delete data.tinyfish;
  data.connection = { mode: "website", user_id: owner, username: owner };
  data.observations = { boot: owner, sequence: 0, events: [], contexts: [] };
  data.graph = { nodes: [], edges: [] };
  data.shared_memory = { claims: [] };
  data.tiers.captured_contexts = [];
  data.agents.observed = 0;
  data.storage.memories = memories;
  data.history = { rows: [], total: 0, next_before: null };
  return data;
}

async function streamControl(page) {
  await page.addInitScript(() => {
    window.testStreams = [];
    window.EventSource = class {
      constructor(url) {
        this.url = url;
        this.handlers = {};
        this.closed = false;
        window.testStreams.push(this);
      }
      addEventListener(name, fn) {
        this.handlers[name] = fn;
      }
      close() {
        this.closed = true;
      }
    };
    window.deliverSnapshot = (payload, late = false) =>
      window.testStreams.forEach((s) => {
        if (late || !s.closed)
          s.handlers.snapshot?.({ data: JSON.stringify(payload) });
      });
  });
}

test("saved history fills every page without a live feed, including history and vector details", async ({
  page,
}) => {
  const errors = [],
    liveRequests = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (r.url().includes("/api/dashboard/")) liveRequests.push(r.url());
  });
  await page.goto("/overview");
  await expect(page.getByTestId("live-dashboard")).toHaveAttribute(
    "data-source-mode",
    "history",
  );
  await expect(
    page.getByText("Saved project replay · not live", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Follow live", exact: true }),
  ).toHaveAttribute("aria-pressed", "false");
  for (const route of [
    "memory",
    "agents",
    "activity",
    "architecture",
    "resources",
    "history",
    "tinyfish",
  ]) {
    await page.goto("/" + route);
    await expect(page.getByTestId("live-dashboard")).toHaveAttribute(
      "data-source-mode",
      "history",
    );
    if (route === "memory")
      expect(
        await page.locator(".live-explorer details button").count(),
      ).toBeGreaterThan(0);
    if (route === "architecture") {
      const visuals = page.getByLabel("Vector, graph and hybrid memory illustrations");
      await expect(visuals).toBeVisible();
      await expect(visuals.getByRole("img")).toHaveCount(3);
      await expect(visuals.locator("footer").first()).toContainText("not measured embeddings");
    }
    if (route === "history") {
      await expect(page.locator(".run-history-entry")).toHaveCount(
        saved.history.rows.length,
      );
      await page.locator(".run-history-entry summary").first().click();
      await page
        .getByText("All recorded metrics, result and errors", { exact: true })
        .first()
        .click();
      await expect(
        page.locator(".run-history-entry .live-json").first(),
      ).toBeVisible();
    }
    if (route === "tinyfish")
      await expect(
        page.getByText("Museum opens at 09:00 every day.", { exact: true }),
      ).toBeVisible();
  }
  await page
    .getByRole("button", { name: "Inspect data source", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Saved replay source", exact: true }),
  ).toBeVisible();
  await page.getByText(/Memory vector payloads/).click();
  await page
    .getByRole("button", { name: "Inspect numeric vector", exact: true })
    .click();
  expect(liveRequests).toEqual([]);
  expect(errors).toEqual([]);
});

test("Follow live replaces replay; Saved history closes the stream and ignores late snapshots", async ({
  page,
}) => {
  await streamControl(page);
  const live = liveSnapshot();
  await page.route("**/api/dashboard/**", (route) => {
    if (route.request().url().includes("/connection"))
      return route.fulfill({
        json: { mode: "website", website_url: "http://127.0.0.1:8094" },
      });
    if (route.request().url().includes("/session"))
      return route.fulfill({ json: { connection: live.connection } });
    return route.fulfill({ json: live });
  });
  await page.goto("/overview");
  await page.getByRole("button", { name: "Follow live", exact: true }).click();
  await expect(page.getByTestId("live-dashboard")).toHaveAttribute(
    "data-source-mode",
    "live",
  );
  await expect(page.locator(".website-summary h2")).toHaveText(
    "Live fixture traveler",
  );
  await expect(page.locator(".history-notice")).toHaveCount(0);
  await expect(page).toHaveURL(/mode=live/);
  await expect(page.locator(".overview-metrics strong").first()).toHaveText(
    "77",
  );
  await expect(page.locator(".tf-metrics strong")).toHaveText([
    "—",
    "—",
    "—",
    "—",
  ]);
  await expect
    .poll(() =>
      page.evaluate(() => window.testStreams.filter((s) => !s.closed).length),
    )
    .toBe(1);
  await page.getByRole("link", { name: "Memory graph", exact: true }).click();
  await expect(page).toHaveURL(/mode=live/);
  await page
    .getByRole("button", { name: "Saved history", exact: true })
    .click();
  await expect(page.getByTestId("live-dashboard")).toHaveAttribute(
    "data-source-mode",
    "history",
  );
  await expect
    .poll(() => page.evaluate(() => window.testStreams.every((s) => s.closed)))
    .toBe(true);
  await page.evaluate(
    (data) => window.deliverSnapshot(data, true),
    liveSnapshot("Late account", 999),
  );
  await expect(page.getByTestId("live-dashboard")).toHaveAttribute(
    "data-source-mode",
    "history",
  );
  await expect(page.locator(".live-breadcrumb")).toContainText(
    "Saved project replay",
  );
  await page.reload();
  await expect(page.getByTestId("live-dashboard")).toHaveAttribute(
    "data-source-mode",
    "history",
  );
});

test("failed live authentication never substitutes replay; returning to history is explicit", async ({
  page,
}) => {
  await page.route("**/api/dashboard/**", (route) =>
    route.request().url().includes("/connection")
      ? route.fulfill({ json: { mode: "website" } })
      : route.fulfill({
          status: 401,
          json: {
            detail:
              "Sign in to the travel website in this browser, then click Follow live.",
          },
        }),
  );
  await page.goto("/overview");
  await page.getByRole("button", { name: "Follow live", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Connect your travel account",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Live mode never substitutes saved replay data.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator(".history-notice")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Show saved history", exact: true })
    .click();
  await expect(page.getByTestId("live-dashboard")).toHaveAttribute(
    "data-source-mode",
    "history",
  );
});

test("history/live controls and saved data fit narrow screens", async ({
  page,
}) => {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 390, height: 844 },
    { width: 320, height: 568 },
  ]) {
    await page.setViewportSize(viewport);
    for (const route of [
      "overview",
      "tinyfish",
      "memory",
      "history",
      "resources",
    ]) {
      await page.goto("/" + route);
      await expect(page.getByTestId("live-dashboard")).toHaveAttribute(
        "data-source-mode",
        "history",
      );
      await expect(
        page.getByRole("button", { name: "Saved history", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Follow live", exact: true }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth + 1,
        ),
      ).toBeTruthy();
    }
  }
});
