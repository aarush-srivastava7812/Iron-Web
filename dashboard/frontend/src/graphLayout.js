import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
} from "d3-force";
import { allMemoryNodes } from "./memory.js";

export const DEFAULT_GRAPH_SIZE = { width: 1240, height: 580 };
export const GRAPH_LIMITS = {
  width: { min: 900, max: 2800 },
  height: { min: 480, max: 1400 },
};
export function clampGraphSize(size) {
  return Object.fromEntries(
    Object.entries(GRAPH_LIMITS).map(([axis, limit]) => [
      axis,
      Math.min(
        limit.max,
        Math.max(
          limit.min,
          Number.isFinite(Number(size?.[axis]))
            ? Math.round(Number(size[axis]))
            : DEFAULT_GRAPH_SIZE[axis],
        ),
      ),
    ]),
  );
}
const labelFor = (node) =>
  node.id === "shared" ? "shared memory" : node.label;
export function nodeBounds(node) {
  const halfWidth = Math.max(node.radius + 8, labelFor(node).length * 3.7 + 9);
  return {
    left: node.x - halfWidth,
    right: node.x + halfWidth,
    top: node.y - node.radius - 7,
    bottom: node.y + node.radius + 35,
  };
}
function contain(node, width, height) {
  const bounds = nodeBounds(node);
  const dx =
    bounds.left < 16
      ? 16 - bounds.left
      : bounds.right > width - 16
        ? width - 16 - bounds.right
        : 0;
  const dy =
    bounds.top < 18
      ? 18 - bounds.top
      : bounds.bottom > height - 24
        ? height - 24 - bounds.bottom
        : 0;
  node.x += dx;
  node.y += dy;
}
export function layoutGraph(events, width, height) {
  const graph = allMemoryNodes(events);
  if (!graph.nodes.length) return new Map();
  const nodes = graph.nodes.map((node) => ({ ...node })),
    edges = graph.edges.map((edge) => ({ ...edge }));
  const anchors = {
    "tier-1": { x: width * 0.18, y: height * 0.36 },
    "tier-2": { x: width * 0.72, y: height * 0.22 },
    "tier-3": { x: width * 0.63, y: height * 0.72 },
  };
  const simulation = forceSimulation(nodes)
    .stop()
    .force(
      "link",
      forceLink(edges)
        .id((node) => node.id)
        .distance((edge) => (edge.type === "source" ? 170 : 100))
        .strength((edge) => (edge.type === "source" ? 0.13 : 0.65)),
    )
    .force("charge", forceManyBody().strength(-550))
    .force(
      "collision",
      forceCollide()
        .radius((node) => node.radius + 30)
        .iterations(2),
    )
    .force("center", forceCenter(width / 2, height / 2))
    .force(
      "x",
      forceX((node) => anchors[node.tier]?.x || width / 2).strength(0.08),
    )
    .force(
      "y",
      forceY((node) => anchors[node.tier]?.y || height / 2).strength(0.1),
    );
  simulation.tick(300);
  simulation.stop();
  const minX = Math.min(...nodes.map((node) => node.x)),
    maxX = Math.max(...nodes.map((node) => node.x)),
    minY = Math.min(...nodes.map((node) => node.y)),
    maxY = Math.max(...nodes.map((node) => node.y));
  for (const node of nodes) {
    node.x = 100 + ((node.x - minX) / Math.max(1, maxX - minX)) * (width - 200);
    node.y = 45 + ((node.y - minY) / Math.max(1, maxY - minY)) * (height - 120);
  }
  // Resolve label rectangles, not only node circles. Do not normalize afterwards:
  // squeezing the solved coordinates would reintroduce overlapping filenames.
  for (let iteration = 0; iteration < 320; iteration++) {
    let intersections = 0;
    for (let i = 0; i < nodes.length; i++)
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i],
          b = nodes[j],
          ab = nodeBounds(a),
          bb = nodeBounds(b);
        const overlapX =
          Math.min(ab.right, bb.right) - Math.max(ab.left, bb.left) + 7;
        const overlapY =
          Math.min(ab.bottom, bb.bottom) - Math.max(ab.top, bb.top) + 7;
        if (overlapX <= 0 || overlapY <= 0) continue;
        intersections++;
        if (overlapX < overlapY) {
          const shift = overlapX / 2 + 0.15,
            direction = a.x < b.x ? -1 : 1;
          a.x += direction * shift;
          b.x -= direction * shift;
        } else {
          const shift = overlapY / 2 + 0.15,
            direction = a.y < b.y ? -1 : 1;
          a.y += direction * shift;
          b.y -= direction * shift;
        }
      }
    for (const node of nodes) contain(node, width, height);
    if (!intersections) break;
  }
  const collides = (node, placed) => {
    const a = nodeBounds(node);
    return placed.some((other) => {
      const b = nodeBounds(other);
      return (
        Math.min(a.right, b.right) + 5 > Math.max(a.left, b.left) &&
        Math.min(a.bottom, b.bottom) + 5 > Math.max(a.top, b.top)
      );
    });
  };
  if (nodes.some((node, index) => collides(node, nodes.slice(0, index)))) {
    // Preserve force positions where possible; move only colliding label boxes
    // to the nearest free position when the user chooses a compact canvas.
    const ordered = [...nodes].sort(
      (a, b) =>
        nodeBounds(b).right -
        nodeBounds(b).left -
        (nodeBounds(a).right - nodeBounds(a).left),
    );
    const placed = [];
    for (const node of ordered) {
      if (collides(node, placed)) {
        const original = { x: node.x, y: node.y },
          half = (nodeBounds(node).right - nodeBounds(node).left) / 2;
        let best = null,
          bestDistance = Infinity;
        for (let y = node.radius + 25; y < height - node.radius - 60; y += 10)
          for (let x = half + 18; x < width - half - 18; x += 10) {
            const distance = (x - original.x) ** 2 + (y - original.y) ** 2;
            if (distance >= bestDistance) continue;
            node.x = x;
            node.y = y;
            if (!collides(node, placed)) {
              best = { x, y };
              bestDistance = distance;
            }
          }
        Object.assign(node, best || original);
      }
      placed.push(node);
    }
  }
  return new Map(nodes.map((node) => [node.id, { x: node.x, y: node.y }]));
}
