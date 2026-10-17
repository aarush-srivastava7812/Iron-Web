import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
const report = resolve(
  import.meta.dirname,
  "../../../report/dashboard_visualizer_step3",
);
test("desktop mock dashboard renders and highlights the real rejected write", async ({
  page,
}) => {
  const errors = [],
    apiRequests = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url());
  });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Dashboard home" }),
  ).toBeVisible();
  await expect(page.getByText("Stale write rejected")).toBeVisible();
  await expect(page.getByText("₹42,000")).toBeVisible();
  await expect(page.locator("[data-inspected-event]")).toHaveAttribute(
    "data-inspected-event",
    "27",
  );
  await page.getByRole("button", { name: "Replay event", exact: true }).click();
  await expect(page.locator("[data-event-pulse]")).toHaveAttribute(
    "data-event-pulse",
    "27",
  );
  await mkdir(report, { recursive: true });
  await page.screenshot({
    path: resolve(report, "desktop.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
  expect(apiRequests).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("event selection and graph selection update the shared inspector", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("[data-inspected-event]")).toHaveAttribute(
    "data-inspected-event",
    "27",
  );
  await page.getByRole("button", { name: "Next event", exact: true }).click();
  await expect(page.locator("[data-inspected-event]")).toHaveAttribute(
    "data-inspected-event",
    "28",
  );
  await expect(
    page.getByText("Memory read. No value was changed."),
  ).toBeVisible();
  await page.locator('[data-node-path="shared/tier-1/traveler.md"]').click();
  await expect(
    page.getByRole("heading", { name: "traveler.md", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".memory-row.selected")).toContainText(
    "traveler.md",
  );
  await page.getByRole("textbox", { name: "Find a memory" }).fill("budget");
  await expect(page.locator(".memory-row")).toHaveCount(2);
  await page
    .getByRole("textbox", { name: "Find a memory" })
    .fill("nothing-matches");
  await expect(page.locator(".memory-row")).toHaveCount(0);
});

test("forget removes the node and backward navigation restores it", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: /Event 36: researcher forget/ })
    .click();
  await expect(
    page.locator('[data-node-path="shared/tier-3/scratch/weather-cache.json"]'),
  ).toHaveCount(0);
  await expect(page.getByText("FORGOTTEN", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Previous event", exact: true })
    .click();
  await expect(
    page.locator('[data-node-path="shared/tier-3/scratch/weather-cache.json"]'),
  ).toHaveCount(1);
});

test("mobile layout fits the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Dashboard home" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: resolve(report, "mobile.png"),
    fullPage: true,
  });
});

test("reduced motion suppresses pulses while retaining event state", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("[data-inspected-event]")).toHaveAttribute(
    "data-inspected-event",
    "27",
  );
  await page.getByRole("button", { name: "Replay event", exact: true }).click();
  await expect(page.locator("[data-event-pulse]")).toHaveCount(0);
});

test("empty and invalid event sources produce an explicit recoverable state", async ({
  page,
}) => {
  await page.route("**/events.json", (route) => route.fulfill({ json: [] }));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "The session could not be loaded" }),
  ).toBeVisible();
  await expect(page.getByText(/event file is empty/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});
