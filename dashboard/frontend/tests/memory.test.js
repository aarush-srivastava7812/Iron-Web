import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { replay, topology, validateEvents } from "../src/memory.js";
const events = validateEvents(
  JSON.parse(
    await readFile(new URL("../public/events.json", import.meta.url), "utf8"),
  ),
);
const budget = "shared/tier-3/trip/budget.json";

test("fixture has forty chronological events, three agents, and one actual stale write", () => {
  assert.equal(events.length, 40);
  assert.equal(new Set(events.map((event) => event.agent)).size, 3);
  assert.equal(replay(events).conflicts.length, 1);
  assert.equal(replay(events).conflicts[0].id, 27);
  for (const event of events)
    assert.deepEqual(
      Object.keys(event).sort(),
      [
        "timestamp",
        "agent",
        "action",
        "memoryPath",
        "before",
        "after",
        "id",
      ].sort(),
    );
});
test("a stale write preserves current state and cannot create an accepted version", () => {
  const snapshot = replay(events, 27),
    history = snapshot.history.get(budget);
  assert.equal(snapshot.memories.get(budget).value.amount, 42000);
  assert.equal(snapshot.memories.get(budget).version, 2);
  assert.equal(history.at(-1).before.amount, 48000);
  assert.equal(history.at(-1).after.amount, 45000);
  assert.equal(history.at(-1).currentBefore.amount, 42000);
  assert.equal(history.at(-1).accepted, false);
});
test("prefix replay is deterministic and forgetting removes the memory from topology", () => {
  assert.equal(replay(events, 24).memories.get(budget).value.amount, 48000);
  assert.equal(replay(events, 25).memories.get(budget).value.amount, 42000);
  assert.equal(
    replay(events, 35).memories.has("shared/tier-3/scratch/weather-cache.json"),
    true,
  );
  assert.equal(
    replay(events, 36).memories.has("shared/tier-3/scratch/weather-cache.json"),
    false,
  );
  assert.deepEqual(replay(events, 27), replay(events, 27));
  assert.equal(replay(events, 0).memories.size, 0);
});
test("reads do not alter content, writer, or version", () => {
  const before = replay(events, 27).memories.get(budget),
    after = replay(events, 28).memories.get(budget);
  assert.deepEqual(before.value, after.value);
  assert.equal(before.writer, after.writer);
  assert.equal(before.version, after.version);
});
test("graph sizes derive from real degree and references only join existing memories", () => {
  const graph = topology(replay(events).memories),
    degree = new Map(),
    ids = new Set(graph.nodes.map((node) => node.id));
  for (const edge of graph.edges) {
    assert.ok(ids.has(edge.source) && ids.has(edge.target));
    for (const id of [edge.source, edge.target])
      degree.set(id, (degree.get(id) || 0) + 1);
  }
  for (const node of graph.nodes) {
    assert.equal(node.degree, degree.get(node.id));
    assert.equal(node.radius, 4 + Math.sqrt(node.degree) * 4.4);
  }
  assert.ok(graph.edges.some((edge) => edge.type === "source"));
  assert.equal(ids.has("shared/tier-3/scratch/weather-cache.json"), false);
});
test("event validation rejects empty files, malformed actions and unordered timestamps", () => {
  assert.throws(() => validateEvents([]), /empty/);
  assert.throws(
    () => validateEvents([{ ...events[0], action: "invented" }]),
    /Invalid/,
  );
  assert.throws(() => validateEvents([events[1], events[0]]), /Invalid/);
});
