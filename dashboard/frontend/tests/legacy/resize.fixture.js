import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";
const report = resolve(import.meta.dirname, "../../../report/dashboard_resize");
async function load(page) {
  await page.goto("/");
  await expect(page.locator('[data-testid="replay-cursor"]')).toHaveText("27");
}

test("manual canvas sizing stays within the viewport and fit mode is restored", async ({
  page,
}) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await load(page);
  await expect(page.locator(".rail")).toHaveCount(0);
  await expect(page.getByRole("tab")).toHaveCount(4);
  const svg = page.locator(".graph-svg");
  await expect(svg).toHaveAttribute("data-canvas-width", "1060");
  await page.getByRole("button", { name: "Adjust graph size" }).click();
  await page.getByRole("slider", { name: "Graph width", exact: true }).focus();
  await page.keyboard.press("End");
  await expect(svg).toHaveAttribute("data-canvas-width", "2800");
  await page.getByRole("slider", { name: "Graph height", exact: true }).focus();
  await page.keyboard.press("End");
  await expect(svg).toHaveAttribute("data-canvas-height", "1400");
  expect(
    (await page.getByTestId("graph-viewport").boundingBox()).height,
  ).toBeLessThan(1000);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("tab", { name: "Activity", exact: true }).click();
  await page.getByRole("tab", { name: "Memory graph", exact: true }).click();
  await expect(svg).toHaveAttribute("data-canvas-height", "1400");
  await page.reload();
  await expect(svg).toHaveAttribute("data-canvas-width", "2800");
  await expect(svg).toHaveAttribute("data-canvas-height", "1400");
  await page.getByRole("button", { name: "Adjust graph size" }).click();
  await page.getByRole("button", { name: "Reset graph size" }).click();
  await expect(
    page.getByRole("checkbox", { name: "Fit graph to stage" }),
  ).toBeChecked();
  await expect(svg).toHaveAttribute("data-canvas-width", "1060");
  const viewport = await page.getByTestId("graph-viewport").boundingBox();
  await expect(svg).toHaveAttribute(
    "data-canvas-height",
    String(Math.round(viewport.height)),
  );
  await expect(page.getByText("₹42,000")).toBeVisible();
  await mkdir(report, { recursive: true });
  await page.screenshot({
    path: resolve(report, "dimensions.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("drag handle changes both dimensions and supports keyboard adjustment", async ({
  page,
}) => {
  await load(page);
  const handle = page.getByRole("button", { name: "Resize graph canvas" });
  await handle.scrollIntoViewIfNeeded();
  const bounds = await handle.boundingBox();
  await page.mouse.move(
    bounds.x + bounds.width / 2,
    bounds.y + bounds.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    bounds.x + bounds.width / 2 + 110,
    bounds.y + bounds.height / 2 + 60,
    { steps: 7 },
  );
  await page.mouse.up();
  const svg = page.locator(".graph-svg");
  const width = Number(await svg.getAttribute("data-canvas-width")),
    height = Number(await svg.getAttribute("data-canvas-height"));
  expect(width).toBeGreaterThan(1300);
  expect(height).toBeGreaterThan(620);
  await handle.focus();
  await page.keyboard.press("ArrowRight");
  await expect(svg).toHaveAttribute("data-canvas-width", String(width + 20));
  await page.keyboard.press("ArrowDown");
  await expect(svg).toHaveAttribute("data-canvas-height", String(height + 20));
});

test("labels stay readable and do not intersect at the default canvas size", async ({
  page,
}) => {
  await load(page);
  const labels = await page.locator(".node-label").evaluateAll((elements) =>
    elements.map((element) => {
      const b = element.getBoundingClientRect();
      return {
        text: element.textContent,
        left: b.left,
        right: b.right,
        top: b.top,
        bottom: b.bottom,
        fontSize: parseFloat(getComputedStyle(element).fontSize),
      };
    }),
  );
  for (const label of labels) expect(label.fontSize).toBeGreaterThanOrEqual(12);
  for (let i = 0; i < labels.length; i++)
    for (let j = i + 1; j < labels.length; j++) {
      const a = labels[i],
        b = labels[j];
      expect(
        Math.min(a.right, b.right) - Math.max(a.left, b.left) <= 1 ||
          Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) <= 1,
        `${a.text} overlaps ${b.text}`,
      ).toBeTruthy();
    }
  await page.getByRole("button", { name: "Open help", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
});
