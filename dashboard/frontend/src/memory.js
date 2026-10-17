export const AGENTS = {
  planner: {
    name: "Itinerary planner",
    short: "Planner",
    code: "AG.01",
    initials: "PL",
  },
  researcher: {
    name: "Research agent",
    short: "Researcher",
    code: "AG.02",
    initials: "RE",
  },
  reviewer: {
    name: "Memory reviewer",
    short: "Reviewer",
    code: "AG.03",
    initials: "RV",
  },
};
export const TIERS = {
  "tier-1": {
    number: "01",
    name: "Hot context",
    description: "Agent roles & traveler essentials",
    storage: "RAM",
  },
  "tier-2": {
    number: "02",
    name: "Context cards",
    description: "Task-specific working memory",
    storage: "CPU / GPU",
  },
  "tier-3": {
    number: "03",
    name: "Durable memory",
    description: "Facts, evidence & decisions",
    storage: "PERSISTENT",
  },
};
export const fileName = (path) => path.split("/").at(-1);
export const tierKey = (path) => path.split("/")[1];
export const formatTime = (timestamp) =>
  new Date(timestamp).toLocaleTimeString("en-GB", {
    timeZone: "UTC",
    hour12: false,
  });
export const pretty = (value) =>
  typeof value === "string" ? value : JSON.stringify(value, null, 2);
const stable = (value) =>
  JSON.stringify(value, (_, item) =>
    item && typeof item === "object" && !Array.isArray(item)
      ? Object.fromEntries(
          Object.entries(item).sort(([a], [b]) => a.localeCompare(b)),
        )
      : item,
  );
export const equal = (a, b) => stable(a) === stable(b);

export function validateEvents(input) {
  if (!Array.isArray(input) || !input.length)
    throw new Error(
      "The event file is empty. Add memory events to public/events.json.",
    );
  let lastTime = -Infinity;
  return input.map((event, index) => {
    const time = Date.parse(event.timestamp);
    if (
      !Number.isFinite(time) ||
      time < lastTime ||
      !AGENTS[event.agent] ||
      !["read", "write", "update", "forget"].includes(event.action) ||
      typeof event.memoryPath !== "string" ||
      !/^shared\/tier-[123]\/.+/.test(event.memoryPath) ||
      !("before" in event) ||
      !("after" in event)
    )
      throw new Error(
        `Invalid mock event at row ${index + 1}. Check its timestamp, agent, action, path and values.`,
      );
    lastTime = time;
    return { ...event, id: index + 1 };
  });
}

export function replay(events, count = events.length) {
  const memories = new Map(),
    history = new Map(),
    applied = [];
  for (const event of events.slice(0, count)) {
    const existing = memories.get(event.memoryPath),
      current = existing?.value ?? null;
    const conflict = event.action !== "read" && !equal(current, event.before);
    const entry = {
      ...event,
      conflict,
      currentBefore: current,
      accepted: !conflict,
    };
    const versions = history.get(event.memoryPath) || [];
    if (!conflict && event.action !== "read") {
      if (event.action === "forget") memories.delete(event.memoryPath);
      else
        memories.set(event.memoryPath, {
          path: event.memoryPath,
          value: event.after,
          writer: event.agent,
          version: (existing?.version || 0) + 1,
          updatedAt: event.timestamp,
          lastEvent: event.id,
        });
    }
    if (!conflict && event.action === "read" && existing) {
      memories.set(event.memoryPath, {
        ...existing,
        lastRead: event.timestamp,
        readCount: (existing.readCount || 0) + 1,
      });
    }
    versions.push(entry);
    history.set(event.memoryPath, versions);
    applied.push(entry);
  }
  return {
    memories,
    history,
    applied,
    conflicts: applied.filter((e) => e.conflict),
  };
}

export function topology(memories) {
  const nodes = new Map(),
    edges = new Map();
  const addEdge = (source, target, type) => {
    const id = [source, target, type].join("|");
    if (source !== target) edges.set(id, { id, source, target, type });
  };
  for (const [path, memory] of memories) {
    const parts = path.split("/");
    for (let index = 0; index < parts.length; index++) {
      const id = parts.slice(0, index + 1).join("/");
      nodes.set(id, {
        id,
        label: parts[index],
        isMemory: index === parts.length - 1,
        tier: parts[1],
        memory: index === parts.length - 1 ? memory : null,
      });
      if (index > 0) addEdge(parts.slice(0, index).join("/"), id, "contains");
    }
    const references =
      JSON.stringify(memory.value).match(
        /shared\/tier-[123]\/[A-Za-z0-9_./-]+/g,
      ) || [];
    for (const reference of references)
      if (memories.has(reference)) addEdge(path, reference, "source");
  }
  const degree = new Map();
  for (const edge of edges.values())
    for (const id of [edge.source, edge.target])
      degree.set(id, (degree.get(id) || 0) + 1);
  return {
    nodes: [...nodes.values()].map((node) => ({
      ...node,
      degree: degree.get(node.id) || 0,
      radius: 4 + Math.sqrt(degree.get(node.id) || 0) * 4.4,
    })),
    edges: [...edges.values()],
  };
}

export function allMemoryNodes(events) {
  const memories = new Map();
  for (const event of events)
    if (event.action !== "forget" && event.after !== null)
      memories.set(event.memoryPath, {
        path: event.memoryPath,
        value: event.after,
      });
  return topology(memories);
}

export function diffRows(before, after) {
  if (
    before &&
    after &&
    typeof before === "object" &&
    typeof after === "object"
  ) {
    const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])];
    return keys.map((key) => ({
      key,
      before: before[key],
      after: after[key],
      changed: !equal(before[key], after[key]),
    }));
  }
  return [{ key: "content", before, after, changed: !equal(before, after) }];
}

export const ACTIONS = ["read", "write", "update", "forget"];
export function matchesEvent(event, agent = null, action = null) {
  return (
    (!agent || event.agent === agent) && (!action || event.action === action)
  );
}
export function agentStats(snapshot, agent) {
  const events = snapshot.applied.filter((event) => event.agent === agent);
  return {
    events,
    reads: events.filter((e) => e.action === "read").length,
    writes: events.filter(
      (e) => ["write", "update"].includes(e.action) && !e.conflict,
    ).length,
    conflicts: events.filter((e) => e.conflict).length,
    memories: new Set(events.map((e) => e.memoryPath)).size,
  };
}
export function memoryStrength(memory, timestamp, halfLife = 300) {
  const age = Math.max(
    0,
    (Date.parse(timestamp) - Date.parse(memory.updatedAt)) / 1000,
  );
  return Math.round(100 * Math.pow(2, -age / halfLife));
}
export function contentBytes(memories) {
  return memories.reduce(
    (total, memory) =>
      total + new TextEncoder().encode(pretty(memory.value)).byteLength,
    0,
  );
}
