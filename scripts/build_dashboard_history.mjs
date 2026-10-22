// Build an explicitly labelled project replay. Never read account stores or credentials.
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { replay, topology, validateEvents } from "../dashboard/frontend/src/memory.js";

const root = resolve(import.meta.dirname, "..");
const read = async (path) => JSON.parse(await readFile(resolve(root, path), "utf8"));
const source = validateEvents(await read("dashboard/frontend/public/events.json"));
const benchmark = await read("report/tinyfish_memory/benchmark.json");
const live = await read("report/tinyfish_memory/live-research.json");
const model = replay(source);
const tree = topology(model.memories);
const roles = { planner: "itinerary_planner", researcher: "explore_agent", reviewer: "budget_booking_agent" };
const registered = ["travel_orchestrator", "trip_consultant", "explore_agent", "stay_agent", "food_guide_agent", "tour_guide_agent", "itinerary_planner", "budget_booking_agent", "travel_support_agent"];
const boot = "saved-project-replay-20261017";
const byteSize = (value) => Buffer.byteLength(typeof value === "string" ? value : JSON.stringify(value));
const observations = model.applied.map((event) => {
  const agent = roles[event.agent];
  const row = { id: event.id, boot, timestamp: Date.parse(event.timestamp) / 1000, trip_id: "saved-example-trip", agent_id: agent,
    kind: event.conflict ? "context_failed" : event.action === "read" ? "context_assembled" : event.action === "forget" ? "memory_forget_requested" : "memory_processed",
    detail: { memory_id: event.memoryPath, replay: true, status: event.conflict ? "failed" : "ready", cache_hit: false, action: event.action } };
  if (event.action === "read" && event.accepted) {
    const card = { card_id: event.memoryPath, version: "saved-" + event.id, claim_ids: [event.memoryPath], content: event.after ?? event.currentBefore };
    const agentBytes = byteSize("Recorded example role: " + agent);
    const travellerBytes = byteSize(event.currentBefore);
    row.context = { agent_id: agent, event_id: event.id, captured_at: row.timestamp, status: "ready", claim_ids: [event.memoryPath], source_ids: [event.memoryPath], cards: [card],
      tokens: { agent: agentBytes, traveller: travellerBytes, prompt: agentBytes + travellerBytes + byteSize(card) },
      fields: [{ predicate: event.memoryPath.split("/").at(-1), values: [event.currentBefore], status: "supported", claim_ids: [event.memoryPath] }], required_issues: {},
      note: "Reconstructed from the existing seeded replay. Byte counts are computed from these strings; no hosted-model token usage was measured." };
  }
  return row;
});
const contexts = [...new Map(observations.filter(e => e.context).map(e => [e.agent_id, e.context])).values()];
const claims = [...model.memories.values()].map(m => ({ id: m.path, memory_id: m.path, subject_name: "Example traveler", predicate: m.path.split("/").at(-1), value_json: JSON.stringify(m.value), content: typeof m.value === "string" ? m.value : JSON.stringify(m.value), accepted: true, protected: false, origin: "seeded_replay", valid_from: 0, valid_until: 253402300799, recorded_at: Date.parse(m.updatedAt)/1000, status: "recorded", version: m.version }));
const nodes = tree.nodes.map(n => ({ id: n.id, labels: [n.isMemory ? "MemoryClaim" : "ReplayFolder"], properties: n.isMemory ? claims.find(c => c.id === n.id) : { id: n.id, name: n.label } }));
const rows = observations.filter(e => e.context).map(e => ({ run_id: "recorded-read-"+e.id, sequence: e.id, trip_id: e.trip_id, agent_id: e.agent_id, status: "recorded", summary: "Seeded replay: read " + e.detail.memory_id, started_at: e.timestamp, finished_at: e.timestamp, elapsed_ms: null, payload: { observation_boot: boot, memory: { claims: e.context.claim_ids.length, cards: e.context.cards.length, cache_hit: null }, provider: {}, recorded_result: e.context, source: "Seeded 17 Oct project example; not a measured agent execution" } })).reverse();
const stamp = Date.parse(benchmark.generated_at)/1000;
const scope = "Saved project replay: seeded 17 Oct trip graph + recorded 22 Oct controlled TinyFish results. Not a signed-in account or live provider activity.";
const snapshot = {
  schema: "iron_web_dashboard_v1", status: "recorded", timestamp: stamp, trip_id: "saved-example-trip", scope: "saved_project_replay",
  replay: { kind: "project_demo", title: "Saved project replay", captured_at: benchmark.generated_at, description: scope, source: "Existing events.json example and report/tinyfish_memory receipts", illustrative: true },
  connection: { mode: "recorded", user_id: "public-project-replay", username: "Saved project replay" },
  observations: { boot, sequence: observations.at(-1).id, retained_from: 1, events: observations, contexts },
  history: { rows, total: rows.length, next_before: null }, history_error: null,
  graph: { nodes, edges: tree.edges.map(e => ({ source: e.source, target: e.target, relation: e.type.toUpperCase() })), truncated: false, edges_truncated: false, next_offset: null },
  shared_memory: { claims, total: claims.length, truncated: false }, vectors: { points: [], count: 0, dimensions: 384, note: "Numeric vectors were not captured for this seeded example." }, receipts: [],
  storage: { backend: "iron_web_2", graph_live: false, memories: claims.length, sources: claims.length, vector_backend: "Recorded example", scope: "Seeded replay, not current database contents" },
  databases: { falkordb: { status: "recorded example", role: "No database connection in history mode" }, journal: { status: "bundled snapshot", type: "JSON replay" } },
  models: { embedding: "Not measured in this seeded replay", reranker: "Not measured", reranker_enabled: false, extraction_policy: "recorded example" },
  cache: { entries: null, max_entries: 256, payload_bytes: null, max_payload_bytes: 8388608 },
  tiers: { tokenizer: "voyara-deterministic-utf8-v1", accounting: "Computed UTF-8 bytes of seeded replay text; not hosted tokens", policy: { context_limit: 24000, half_tokens: 2000, card_tokens: 2000, max_cards: 8 }, captured_contexts: contexts, templates: [], layers: [
    { tier: 1, name: "Hot context", storage: "Recorded example", description: "Role and traveler context reconstructed from saved example events." },
    { tier: 2, name: "Context cards", storage: "Recorded example", description: "Example source-derived cards; no captured GPU allocation." },
    { tier: 3, name: "Durable shared memory", storage: "Saved example graph", description: "Graph reconstructed from the existing seeded event sequence." },
  ] },
  credentials: { runtime: "recorded_project_demo", provider: "Not measured for the seeded replay", hosted_calls: 0, configured: [], explanation: scope, usage: { requests: 0, usage_responses: 0, input_tokens: null, output_tokens: null, scope: "No hosted provider usage captured for this example" } },
  agents: { registered: registered.length, observed: new Set(observations.map(e => e.agent_id)).size, rows: registered.map(agent_id => ({ agent_id, reads_in_window: observations.filter(e => e.agent_id === agent_id && e.context).length, events_in_window: observations.filter(e => e.agent_id === agent_id).length, last_seen: observations.filter(e => e.agent_id === agent_id).at(-1)?.timestamp || null })) },
  resources: { source: "unavailable in saved example", ram_bytes: null, vram_bytes: null, gpu_util: null },
  notes: [scope, "A seeded example is not historical account telemetry. Follow live replaces the entire dataset with the authenticated feed.", "Missing timings, billing and hosted token counts remain unavailable."],
  tinyfish: { configured: false, scope: "Controlled lifecycle run, 22 Oct: one seeded quotation; 9 reuse calls; 10 independent changed-plan cases. Mock HTTP, not live account totals.",
    metrics: { source_quotes: 1, reuse_events: benchmark.repeated_requests.memory_reuses, fresh: 1, plans_flagged: benchmark.changed_plan_detection.passed, stale: benchmark.stale_exclusion.passed, conflicts: 0, graph_indexed: 0, refresh_requests: 1 },
    evidence: [{ id: "saved-fixture-v2", previous_id: "saved-fixture-v1", topic: "hours", freshness: "fresh at controlled run", verification: "seeded source statement", changed: true, graph_synced: false, retrieved_at: benchmark.generated_at, expires_at: "Not applicable: saved controlled example", statements: [{ quote: "Museum opens at 09:00 every day.", source_url: "https://tourism.example.org/jaipur" }] }],
    jobs: [{ id: "recorded-public-connectivity-check", status: "recorded connectivity check", topics: ["Jaipur public research; extraction disabled"], metrics: { elapsed_ms: live.elapsed_ms, sources: live.sources, fetched_pages: live.fetched_pages, source_quotes: 0 } }],
    events: [{ id: 1, kind: "evidence_reused", timestamp: stamp, detail: { count: benchmark.repeated_requests.memory_reuses } }, { id: 2, kind: "plan_flagged", timestamp: stamp, detail: { reason: "10/10 independent seeded changed-plan challenge cases passed" } }] },
};
await writeFile(resolve(root, "dashboard/frontend/public/history-snapshot.json"), JSON.stringify(snapshot, null, 2) + "\n");
console.log(JSON.stringify({ memories: claims.length, events: observations.length, contexts: contexts.length, saved_reads: rows.length, provenance: scope }));
