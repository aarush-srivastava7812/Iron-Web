import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
const report = resolve(
  import.meta.dirname,
  "../../../report/dashboard_controls",
);
async function loaded(page) {
  await page.goto("/");
  await expect(page.locator('[data-testid="replay-cursor"]')).toHaveText("27");
}

test("one set of view tabs opens every functioning panel", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await loaded(page);
  await mkdir(report, { recursive: true });
  for (const [label, id] of [
    ["Agent wiring", "agent-wiring"],
    ["Activity", "activity-heatmap"],
    ["Architecture", "memory-architecture"],
    ["Memory graph", "memory-graph"],
  ]) {
    await page.getByRole("tab", { name: label, exact: true }).click();
    await expect(page.getByTestId(id)).toBeVisible();
    await page.screenshot({
      path: resolve(report, id + ".png"),
      fullPage: true,
    });
  }
  await expect(page.getByRole("tab")).toHaveCount(4);
  await expect(page.locator(".rail")).toHaveCount(0);
  expect(errors).toEqual([]);
  await expect(page.getByText("SOON", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/NEXT STAGE/)).toHaveCount(0);
});

test("agents, wiring tools, heatmap and ledger share selection", async ({
  page,
}) => {
  await loaded(page);
  await page
    .getByRole("button", { name: "Select Research agent", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Research agent", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Select Research agent", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("tab", { name: "Agent wiring", exact: true }).click();
  await page.getByRole("button", { name: "Filter read tool events" }).click();
  await expect(page.getByTestId("activity-heatmap")).toBeVisible();
  await expect(page.locator(".ledger-row")).toHaveCount(2);
  await page
    .getByRole("button", { name: "Clear filters", exact: true })
    .click();
  await expect(page.locator(".ledger-row")).toHaveCount(40);
  await page.getByRole("button", { name: "Inspect heatmap event 25" }).click();
  await expect(page.getByTestId("replay-cursor")).toHaveText("25");
  await expect(page.locator("[data-inspected-event]")).toHaveAttribute(
    "data-inspected-event",
    "25",
  );
  await page.getByRole("button", { name: "Inspect ledger event 27" }).click();
  await expect(page.getByText("Stale write rejected")).toBeVisible();
  await page.getByRole("tab", { name: "Agent wiring", exact: true }).click();
  await page
    .getByRole("button", { name: "Inspect Itinerary planner", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Itinerary planner", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Explore shared memory store" })
    .click();
  await expect(page.getByTestId("memory-graph")).toBeVisible();
});

test("architecture tiers and memory contents are inspectable", async ({
  page,
}) => {
  await loaded(page);
  await page.getByRole("tab", { name: "Architecture", exact: true }).click();
  await page.getByRole("button", { name: "Inspect Hot context tier" }).click();
  await expect(
    page.getByRole("heading", { name: "Tier inspector", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("complementary", { name: "Tier inspector" })
    .getByRole("button", { name: /^traveler\.md/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "traveler.md", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Inspect memory event source" })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page
    .getByRole("combobox", { name: "Illustrative memory retention half-life" })
    .selectOption("120");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download events.json" }).click();
  expect((await download).suggestedFilename()).toBe("events.json");
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("play, pause, speed, reset, step and draggable scrubber update all views", async ({
  page,
}) => {
  await loaded(page);
  await page
    .getByRole("combobox", { name: "Playback speed" })
    .selectOption("4");
  await page.getByRole("button", { name: "Play replay", exact: true }).click();
  await expect(page.getByTestId("replay-cursor")).not.toHaveText("27");
  await page.getByRole("button", { name: "Pause replay", exact: true }).click();
  const paused = await page.getByTestId("replay-cursor").textContent();
  await page.waitForTimeout(450);
  await expect(page.getByTestId("replay-cursor")).toHaveText(paused);
  await page.getByRole("button", { name: "Reset replay", exact: true }).click();
  await expect(page.getByTestId("replay-cursor")).toHaveText("00");
  await expect(page.locator(".graph-node")).toHaveCount(0);
  await page.getByRole("button", { name: "Next event", exact: true }).click();
  await expect(page.getByTestId("replay-cursor")).toHaveText("01");
  const slider = page.getByRole("slider", { name: "Replay position" }),
    box = await slider.boundingBox();
  await page.mouse.move(box.x + box.width * 0.04, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.65, box.y + box.height / 2, {
    steps: 10,
  });
  await page.mouse.up();
  const value = Number(await slider.inputValue());
  expect(value).toBeGreaterThan(20);
  expect(value).toBeLessThan(30);
  await expect(page.getByTestId("replay-cursor")).toHaveText(
    String(value).padStart(2, "0"),
  );
  await slider.focus();
  await page.keyboard.press("End");
  await expect(page.getByTestId("replay-cursor")).toHaveText("40");
  await page.getByRole("button", { name: "Play replay", exact: true }).click();
  await expect(page.getByTestId("replay-cursor")).toHaveText("00");
  await page.getByRole("button", { name: "Pause replay", exact: true }).click();
});

test("zoom, labels, focus, fit, search clear, help and session buttons work", async ({
  page,
}) => {
  await loaded(page);
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await expect(page.locator(".graph-wrap")).toContainText("120%");
  await page.getByRole("button", { name: "Zoom out", exact: true }).click();
  await expect(page.locator(".graph-wrap")).toContainText("100%");
  await page
    .getByRole("button", { name: "Hide node labels", exact: true })
    .click();
  await expect(page.locator(".node-label")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Show node labels", exact: true })
    .click();
  await expect(page.locator(".node-label")).not.toHaveCount(0);
  await page
    .getByRole("button", { name: "Focus selected memory", exact: true })
    .click();
  await expect(page.locator(".graph-wrap")).toContainText("150%");
  await page
    .getByRole("button", { name: "Reset graph view", exact: true })
    .click();
  await expect(page.locator(".graph-wrap")).toContainText("100%");
  await page.getByRole("textbox", { name: "Find a memory" }).fill("budget");
  await page
    .getByRole("button", { name: "Clear memory search", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Find a memory" }),
  ).toHaveValue("");
  await page.getByRole("button", { name: "Open help", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "How to use this dashboard" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  for (const label of [
    "Open mock session details",
    "Open workspace session",
    "Inspect local event data",
  ]) {
    await page.getByRole("button", { name: label, exact: true }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page
      .getByRole("button", { name: "Close dialog", exact: true })
      .click();
  }
  await page.getByRole("button", { name: "Open mock session details" }).click();
  await page.getByRole("button", { name: "Reload local data" }).click();
  await expect(page.getByTestId("replay-cursor")).toHaveText("27");
});

test("all four views and replay controls are reachable on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await loaded(page);
  for (const label of [
    "Agent wiring",
    "Activity",
    "Architecture",
    "Memory graph",
  ]) {
    await page.getByRole("tab", { name: label, exact: true }).click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
  }
  await page.getByRole("button", { name: "Reset replay", exact: true }).click();
  await expect(page.getByTestId("replay-cursor")).toHaveText("00");
  await page.getByRole("button", { name: "Next event", exact: true }).click();
  await expect(page.getByTestId("replay-cursor")).toHaveText("01");
  await page.screenshot({
    path: resolve(report, "mobile.png"),
    fullPage: true,
  });
});

test("folder toggles, node labels, keyboard tabs and history rows perform real actions", async ({
  page,
}) => {
  await loaded(page);
  await page.getByRole("textbox", { name: "Find a memory" }).fill("budget");
  const cards = page.getByRole("button", { name: /02 Context cards/ });
  await cards.click();
  await expect(cards).toHaveAttribute("aria-expanded", "false");
  await cards.click();
  await expect(cards).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("button", { name: "Clear memory search" }).click();
  await page
    .getByRole("button", { name: "Inspect shared memory root" })
    .click();
  await expect(
    page.getByText("Memory directory", { exact: true }),
  ).toBeVisible();
  await page
    .locator('[data-node-path="shared/tier-3/trip/budget.json"] text')
    .click();
  await expect(
    page.getByRole("heading", { name: "budget.json", exact: true }),
  ).toBeVisible();
  await page
    .locator(".history-entry")
    .filter({ hasText: "Memory updated" })
    .click();
  await expect(page.getByTestId("replay-cursor")).toHaveText("25");
  await page.getByRole("tab", { name: "Memory graph", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("agent-wiring")).toBeVisible();
  await page.keyboard.press("End");
  await expect(page.getByTestId("memory-architecture")).toBeVisible();
});
