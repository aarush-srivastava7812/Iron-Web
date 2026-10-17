import test from "node:test";
import assert from "node:assert/strict";
import {
  projection,
  contextsAt,
  contextUnit,
  isConflict,
  lastCapturedCardBytes,
} from "../src/liveData.js";
test("card allocation uses the latest capture without double counting or inventing zero", () => {
  assert.equal(lastCapturedCardBytes([]), null);
  assert.equal(lastCapturedCardBytes([{ event_id: 1 }]), null);
  assert.equal(lastCapturedCardBytes([{ event_id: 1, residency: { resident_bytes: 0 } }]), 0);
  assert.equal(lastCapturedCardBytes([
    { event_id: 2, residency: { resident_bytes: 4096 } },
    { event_id: 1, residency: { resident_bytes: 4096 } },
  ]), 4096);
});
const context = {
  agent_id: "itinerary_planner",
  event_id: 2,
  claim_ids: ["claim-1"],
  cards: [{ card_id: "trip", version: "a", claim_ids: ["claim-1"] }],
};
const data = {
  tiers: {
    tokenizer: "voyara-deterministic-utf8-v1",
    captured_contexts: [context],
  },
  graph: {
    nodes: [
      {
        id: "claim-1",
        labels: ["MemoryClaim"],
        properties: { predicate: "budget", value_json: "100000" },
      },
    ],
    edges: [],
  },
  observations: {
    events: [
      { id: 1, kind: "memory_submitted" },
      { id: 2, agent_id: "itinerary_planner", context },
      {
        id: 3,
        agent_id: "itinerary_planner",
        context: { ...context, event_id: 3 },
      },
    ],
  },
};
test("live graph keeps actual claim IDs and source-derived relationships", () => {
  const graph = projection(data, data.observations.events.at(-1));
  assert.equal(graph.nodes.find((n) => n.id === "claim-1").access, 2);
  assert.ok(graph.nodes.some((n) => n.tier === "hot"));
  assert.ok(graph.nodes.some((n) => n.tier === "context"));
  assert.ok(
    graph.edges.every(
      (e) =>
        graph.nodes.some((n) => n.id === e.source) &&
        graph.nodes.some((n) => n.id === e.target),
    ),
  );
  assert.ok(graph.edges.some((e) => e.relation === "DERIVED_FROM"));
});
test("historical context never uses a future captured read", () => {
  assert.equal(contextsAt(data, { id: 1 }, true).length, 0);
  assert.equal(contextsAt(data, { id: 2 }, true)[0].event_id, 2);
  assert.equal(
    projection(data, { id: 1 }, true).nodes.find((n) => n.id === "claim-1")
      .access,
    0,
  );
});
test("units and conflicts reflect the source rather than a fictional token baseline", () => {
  assert.equal(contextUnit(data), "UTF-8 bytes");
  assert.equal(
    contextUnit({ tiers: { tokenizer: "actual-tokenizer" } }),
    "consumer tokens",
  );
  assert.equal(
    isConflict({ kind: "context_validated", detail: { valid: false } }),
    true,
  );
  assert.equal(
    isConflict({ kind: "context_assembled", detail: { status: "ready" } }),
    false,
  );
});

test("time axis uses UTC independently of the browser timezone", async () => {
  const { time } = await import("../src/liveData.js");
  assert.equal(time(1), "00:00:01");
});
