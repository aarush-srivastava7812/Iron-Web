import { test, expect } from "@playwright/test";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { resolve } from "node:path";
const report = resolve(import.meta.dirname, "../../../report/dashboard_live");
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
  expect(data.observations.events.length).toBeGreaterThan(0);
  const testedTrip = JSON.parse(
    await readFile(resolve(report, "trip-result.json"), "utf8"),
  ).trip_id;
  expect(
    data.observations.events.some((e) => e.trip_id === testedTrip),
  ).toBeTruthy();
  expect(data.tiers.captured_contexts.length).toBeGreaterThan(0);
  expect(data.credentials.hosted_calls).toBeGreaterThan(0);
  expect(data.credentials.active_credential).toBe("NVIDIA_API_KEY");
  expect(data.credentials.usage.input_tokens).toBeGreaterThan(0);
  expect(
    data.shared_memory.claims.some(
      (c) =>
        c.properties.predicate === "destination" &&
        c.properties.value_json.includes("Goa"),
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
    page.getByRole("button", { name: "× Planner", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "× Planner", exact: true }).click();
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 1280, height: 720 },
  ]) {
    await page.setViewportSize(viewport);
    await mkdir(report, { recursive: true });
    for (const view of [
      "Memory graph",
      "Agent wiring",
      "Activity",
      "Architecture",
      "Resources",
    ]) {
      await page.getByRole("tab", { name: view, exact: true }).click();
      expect(
        await page.evaluate(() => ({
          w: document.documentElement.scrollWidth,
          h: document.documentElement.scrollHeight,
        })),
      ).toEqual({ w: viewport.width, h: viewport.height });
      const stage = await page.locator(".live-stage").boundingBox(),
        dock = await page.locator(".live-dock").boundingBox();
      expect(stage.y + stage.height).toBeLessThanOrEqual(dock.y + 1);
      expect(dock.y + dock.height).toBeLessThanOrEqual(viewport.height);
      if (view === "Agent wiring") {
        const svg = await page.locator(".live-wiring svg").boundingBox();
        expect(svg.y + svg.height).toBeLessThanOrEqual(dock.y);
      }
      if (view === "Architecture") {
        const last = await page
          .locator(".live-architecture>section")
          .last()
          .boundingBox();
        expect(last.y + last.height).toBeLessThanOrEqual(dock.y);
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
    page.getByText("Not instrumented", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Latency", exact: true }).click();
  await expect(page.locator(".latency-chart>div")).not.toHaveCount(0);
  await page.getByRole("button", { name: "Reset replay", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Follow live", exact: true }),
  ).toHaveAttribute("aria-pressed", "false");
  await page.getByRole("button", { name: "Next event", exact: true }).click();
  await expect(page).toHaveURL(/event=/);
  await page.getByRole("button", { name: "Follow live", exact: true }).click();
  await page.getByRole("tab", { name: "Memory graph", exact: true }).click();
  const node = page.locator("[data-memory-id]").first();
  await node.click();
  await expect(page).toHaveURL(/mem=/);
  await page.getByRole("tab", { name: "Links", exact: true }).click();
  await expect(page.locator(".inspector-scroll")).toContainText(
    "relationships",
  );
  await page.getByRole("tab", { name: "History", exact: true }).click();
  await expect(page.locator(".inspector-scroll")).toContainText(
    /event payload/,
  );
  await page.getByRole("tab", { name: "Diff", exact: true }).click();
  expect(requests.some((url) => url.includes("events.json"))).toBeFalsy();
  await page
    .getByRole("button", { name: "Source & credentials", exact: true })
    .click();
  await page.getByText(/Qdrant point payloads/).click();
  await page
    .getByRole("button", { name: "Inspect numeric vector", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    '"values_included": true',
  );
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await writeFile(
    resolve(report, "verified-snapshot.json"),
    JSON.stringify(data, null, 2),
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
  await page.goto("/");
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
  await page.getByRole("tab", { name: "Activity", exact: true }).click();
  expect(await page.locator(".live-heatmap-row").count()).toBe(10);
  await page.screenshot({ path: resolve(report, "1100x760-activity.png") });
});
