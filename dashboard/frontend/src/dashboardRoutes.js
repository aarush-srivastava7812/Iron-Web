// Pages have stable URLs; keep legacy ?view= links and pinned observations usable.
export const PAGES = {
  overview: {
    path: "/overview",
    name: "Overview",
    description:
      "A memory-driven multi-agent system, grounded in TinyFish web evidence.",
  },
  tinyfish: {
    path: "/tinyfish",
    name: "TinyFish intelligence",
    description:
      "Follow live research, evidence freshness, shared memory and the plans that need review.",
  },
  graph: {
    path: "/memory",
    name: "Memory graph",
    description:
      "Explore relationships, find a memory, and inspect its evidence.",
  },
  agents: {
    path: "/agents",
    name: "Agents",
    description: "See how your travel team reads and shares memory.",
  },
  activity: {
    path: "/activity",
    name: "Activity",
    description:
      "Trace recorded events and replay the context behind each decision.",
  },
  architecture: {
    path: "/architecture",
    name: "Architecture",
    description:
      "Understand the journey from durable evidence to an agent’s context.",
  },
  history: {
    path: "/history",
    name: "History",
    description:
      "Persistent summaries, timing, memory and provider metrics for every recorded agent run.",
  },
  resources: {
    path: "/resources",
    name: "Resources",
    description:
      "Inspect context usage, cache reuse, provider tokens, and runtime performance.",
  },
};

export function readPage(pathname, search = "") {
  const path = pathname.replace(/\/+$/, "") || "/";
  const page = Object.keys(PAGES).find((id) => PAGES[id].path === path);
  if (page) return page;
  if (path === "/" || path === "/index.html") {
    const legacy = new URLSearchParams(search).get("view");
    return Object.hasOwn(PAGES, legacy) ? legacy : "overview";
  }
  return "not-found";
}

export function pageUrl(page, { cursor, selected, follow = true, agent } = {}) {
  const params = new URLSearchParams();
  if (cursor && !follow) params.set("event", cursor);
  // Following is explicit; auto-selected live memories must not pin a reload.
  if (selected && !follow) params.set("mem", selected);
  if (agent) params.set("agent", agent);
  return `${PAGES[page]?.path || "/overview"}${params.size ? `?${params}` : ""}`;
}
