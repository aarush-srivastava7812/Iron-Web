import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  layoutGraph,
  nodeBounds,
  clampGraphSize,
  DEFAULT_GRAPH_SIZE,
} from "../src/graphLayout.js";
import { allMemoryNodes, validateEvents } from "../src/memory.js";
const events = validateEvents(
  JSON.parse(
    await readFile(new URL("../public/events.json", import.meta.url), "utf8"),
  ),
);

test("filenames and node circles do not overlap at default and resized canvas dimensions", () => {
  for (const [width, height] of [
    [1240, 580],
    [1600, 760],
    [900, 480],
  ]) {
    const positions = layoutGraph(events, width, height);
    const nodes = allMemoryNodes(events).nodes.map((node) => ({
      ...node,
      ...positions.get(node.id),
    }));
    for (const node of nodes) {
      const bounds = nodeBounds(node);
      assert.ok(
        bounds.left >= 0 &&
          bounds.right <= width &&
          bounds.top >= 0 &&
          bounds.bottom <= height,
      );
    }
    for (let i = 0; i < nodes.length; i++)
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodeBounds(nodes[i]),
          b = nodeBounds(nodes[j]);
        const overlapX = Math.min(a.right, b.right) - Math.max(a.left, b.left),
          overlapY = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        assert.ok(
          overlapX <= 1 || overlapY <= 1,
          `${nodes[i].label} overlaps ${nodes[j].label} at ${width}x${height}`,
        );
      }
    assert.deepEqual(positions, layoutGraph(events, width, height));
  }
});
test("graph dimension preferences handle invalid values and enforce readable limits", () => {
  assert.deepEqual(clampGraphSize({}), DEFAULT_GRAPH_SIZE);
  assert.deepEqual(clampGraphSize({ width: -10, height: 50000 }), {
    width: 900,
    height: 1400,
  });
  assert.deepEqual(clampGraphSize({ width: 1600, height: 760 }), {
    width: 1600,
    height: 760,
  });
});
