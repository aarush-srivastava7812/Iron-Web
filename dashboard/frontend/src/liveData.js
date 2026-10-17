export const VIEW_NAMES = {
  graph: "Memory graph",
  agents: "Agent wiring",
  activity: "Activity",
  architecture: "Architecture",
  resources: "Resources",
};
export const COLORS = {
  hot: "var(--tier-hot)",
  context: "var(--tier-context)",
  durable: "var(--tier-evidence)",
};
// Captures can refer to the same shared device allocation. Never sum them.
export function lastCapturedCardBytes(contexts) {
  const latest = [...contexts].sort((a, b) =>
    (a.event_id ?? a.timestamp ?? 0) - (b.event_id ?? b.timestamp ?? 0)
  ).at(-1);
  const value = latest?.residency?.resident_bytes;
  return Number.isFinite(value) ? value : null;
}
export const agentColor = (id) =>
  /planner|orchestrator/.test(id || "")
    ? "var(--agent-planner)"
    : /budget|support/.test(id || "")
      ? "var(--agent-reviewer)"
      : "var(--agent-researcher)";
export const agentName = (id) =>
  ({
    travel_orchestrator: "Orchestrator",
    trip_consultant: "Consultant",
    explore_agent: "Explore",
    stay_agent: "Stay",
    food_guide_agent: "Food",
    tour_guide_agent: "Tour",
    itinerary_planner: "Planner",
    budget_booking_agent: "Budget",
    travel_support_agent: "Support",
  })[id] ||
  id?.replaceAll("_", " ") ||
  "Application";
export const glyph = (kind) =>
  /forget|retract/.test(kind)
    ? "✕"
    : /processed|completed/.test(kind)
      ? "●"
      : /validated|submitted/.test(kind)
        ? "↻"
        : "○";
export const time = (stamp) =>
  stamp
    ? new Date(stamp * 1000).toLocaleTimeString("en-GB", {
        hour12: false,
        timeZone: "UTC",
      })
    : "—";
export const bytes = (n) =>
  n == null
    ? "N/A"
    : n < 1024
      ? `${n} B`
      : n < 1048576
        ? `${(n / 1024).toFixed(1)} KB`
        : `${(n / 1048576).toFixed(1)} MB`;
export const pretty = (value) =>
  typeof value === "string" ? value : JSON.stringify(value, null, 2);
export const isConflict = (e) =>
  e?.detail?.valid === false ||
  ["context_failed"].includes(e?.kind) ||
  e?.detail?.status === "failed" ||
  Object.values(e?.context?.required_issues || {}).some((x) =>
    /disput|conflict/.test(String(x)),
  );
export const contextUnit = (data) =>
  data?.tiers?.tokenizer === "voyara-deterministic-utf8-v1"
    ? "UTF-8 bytes"
    : "consumer tokens";
export function contextsAt(data, event, historical = false) {
  const rows = historical
    ? (data?.observations?.events || [])
        .filter((e) => e.id <= event?.id && e.context)
        .map((e) => ({ ...e.context, agent_id: e.agent_id, event_id: e.id }))
    : data?.tiers?.captured_contexts || [];
  return [...new Map(rows.map((c) => [c.agent_id, c])).values()];
}
export function projection(data, event, historical = false) {
  const contexts = contextsAt(data, event, historical),
    nodes = [],
    edges = [],
    seen = new Set();
  const add = (node) => {
    if (!seen.has(node.id)) {
      seen.add(node.id);
      nodes.push(node);
    }
  };
  for (const n of data?.graph?.nodes || [])
    add({
      ...n,
      tier: "durable",
      label:
        n.properties?.predicate || n.properties?.name || n.labels?.[0] || n.id,
      raw: n,
    });
  for (const e of data?.graph?.edges || [])
    edges.push({ ...e, id: `${e.source}:${e.relation}:${e.target}` });
  for (const c of contexts) {
    const hot = `context:${c.agent_id}:${c.event_id || c.captured_at}`;
    add({
      id: hot,
      tier: "hot",
      label: `${agentName(c.agent_id)} context`,
      context: c,
      agent_id: c.agent_id,
    });
    for (const id of c.claim_ids || [])
      if (seen.has(id))
        edges.push({
          source: hot,
          target: id,
          relation: "READS",
          id: `${hot}:${id}`,
        });
    for (const card of c.cards || []) {
      const id = `card:${c.agent_id}:${card.card_id}:${card.version}`;
      add({
        id,
        tier: "context",
        label: card.card_id,
        card,
        agent_id: c.agent_id,
      });
      edges.push({
        source: hot,
        target: id,
        relation: "SELECTED",
        id: `${hot}:${id}`,
      });
      for (const claim of card.claim_ids || [])
        if (seen.has(claim))
          edges.push({
            source: id,
            target: claim,
            relation: "DERIVED_FROM",
            id: `${id}:${claim}`,
          });
    }
  }
  const access = new Map();
  for (const e of data?.observations?.events || []) {
    if (historical && e.id > event?.id) continue;
    for (const id of e.context?.claim_ids || [])
      access.set(id, (access.get(id) || 0) + 1);
  }
  return {
    nodes: nodes.map((n) => ({
      ...n,
      access: access.get(n.id) || (n.context ? 1 : 0),
      degree: edges.filter((e) => e.source === n.id || e.target === n.id)
        .length,
    })),
    edges,
    contexts,
  };
}
export function eventLabel(e) {
  if (!e) return "Waiting for application activity";
  const verbs = {
    context_requested: "requested memory",
    context_assembled: "read context",
    context_failed: "could not read context",
    memory_submitted: "submitted requirements",
    memory_processed: "saved requirements",
    context_validated: "checked context freshness",
    agent_completed: "completed work",
    inferred_writes_rejected: "rejected inferred writes",
    memory_forget_requested: "requested source deletion",
    trip_forget_requested: "requested trip deletion",
  };
  return `${agentName(e.agent_id)} ${verbs[e.kind] || e.kind.replaceAll("_", " ")}`;
}
