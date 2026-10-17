import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
const report = resolve(import.meta.dirname, "../../../report/dashboard_layout");

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 1280, height: 720 },
]) {
  test(`viewport workspace fits ${viewport.width}x${viewport.height}`, async ({
    page,
  }) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize(viewport);
    await page.goto("/");
    await expect(page.getByTestId("replay-cursor")).toHaveText("27");
    await expect(
      page.locator(".page-heading, .stage-readout, .status-footer"),
    ).toHaveCount(0);
    await expect(
      page.getByText("CONNECTED AGENTS", { exact: true }),
    ).toHaveCount(0);
    await expect(page.locator(".topbar")).toHaveCSS("height", "56px");
    await expect(page.locator(".replay-dock")).toHaveCSS("height", "140px");
    await expect(page.locator(".agent-lane")).toHaveCount(3);
    await expect(page.locator(".lane-conflict-label")).toHaveText("! Conflict");
    for (const selector of [
      ".topbar",
      ".explorer-column",
      ".stage",
      ".inspector-column",
      ".replay-dock",
      ".graph-svg",
    ]) {
      const box = await page.locator(selector).boundingBox();
      expect(box.x, selector).toBeGreaterThanOrEqual(0);
      expect(box.y, selector).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width, selector).toBeLessThanOrEqual(
        viewport.width + 1,
      );
      expect(box.y + box.height, selector).toBeLessThanOrEqual(
        viewport.height + 1,
      );
    }
    const tokens = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      return Object.fromEntries(
        [
          "--ui-bg",
          "--ui-panel",
          "--agent-planner",
          "--agent-researcher",
          "--agent-reviewer",
        ].map((name) => [
          name,
          style.getPropertyValue(name).trim().toUpperCase(),
        ]),
      );
    });
    expect(tokens).toEqual({
      "--ui-bg": "#141416",
      "--ui-panel": "#1B1B1E",
      "--agent-planner": "#60A5FA",
      "--agent-researcher": "#5EEAD4",
      "--agent-reviewer": "#C084FC",
    });
    const dimensions = await page.evaluate(() => ({
      w: document.documentElement.scrollWidth,
      h: document.documentElement.scrollHeight,
    }));
    expect(dimensions).toEqual({ w: viewport.width, h: viewport.height });
    await page
      .getByRole("button", { name: "Select Research agent", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Select Research agent", exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.locator('.agent-lane[data-agent="planner"] .lane-event.dimmed'),
    ).not.toHaveCount(0);
    await page
      .getByRole("button", { name: "Select Research agent", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Select Research agent", exact: true }),
    ).toHaveAttribute("aria-pressed", "false");
    await page
      .getByRole("button", { name: /Event 27: reviewer update/ })
      .click();
    await mkdir(report, { recursive: true });
    await page.screenshot({
      path: resolve(report, `${viewport.width}x${viewport.height}.png`),
    });
    expect(errors).toEqual([]);
  });
}

test("narrow layouts use side drawers and retain the dock", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1100, height: 760 });
  await page.goto("/");
  await expect(page.getByTestId("replay-cursor")).toHaveText("27");
  await expect(page.locator(".explorer-column")).toBeHidden();
  await expect(page.locator(".inspector-column")).toBeHidden();
  await page
    .getByRole("button", { name: "Open memory explorer", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Find a memory" }),
  ).toBeVisible();
  await page.getByRole("textbox", { name: "Find a memory" }).fill("budget");
  await expect(page.locator(".memory-row")).toHaveCount(2);
  await page.keyboard.press("Escape");
  await expect(page.locator(".explorer-column")).toBeHidden();
  await page
    .getByRole("button", { name: "Open memory inspector", exact: true })
    .click();
  await expect(page.getByText("Stale write rejected")).toBeVisible();
  await page
    .getByRole("button", { name: "Close memory inspector", exact: true })
    .click();
  await page.locator("body").click({ position: { x: 1, y: 1 } });
  await page.keyboard.press("/");
  await expect(
    page.getByRole("textbox", { name: "Find a memory" }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator(".explorer-column")).toBeHidden();
  await page.getByRole("button", { name: "Next event", exact: true }).click();
  await expect(page.getByTestId("replay-cursor")).toHaveText("28");
  await mkdir(report, { recursive: true });
  await page.screenshot({ path: resolve(report, "1100x760-drawers.png") });
});
