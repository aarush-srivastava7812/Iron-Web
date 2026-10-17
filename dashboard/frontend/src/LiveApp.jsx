import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  PlayIcon,
  PauseIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ResetIcon,
  Cross2Icon,
  Share1Icon,
  Component1Icon,
  ActivityLogIcon,
  StackIcon,
  BarChartIcon,
  HamburgerMenuIcon,
  ReaderIcon,
  QuestionMarkCircledIcon,
} from "@radix-ui/react-icons";
import LiveGraph from "./LiveGraph.jsx";
import {
  VIEW_NAMES,
  COLORS,
  agentColor,
  agentName,
  glyph,
  time,
  bytes,
  pretty,
  isConflict,
  contextUnit,
  projection,
  eventLabel,
} from "./liveData.js";
import {
  Inspector,
  Wiring,
  Activity,
  Architecture,
  Resources,
  Dock,
  Dialog,
  Badge,
  ViewHeader,
} from "./LivePanels.jsx";
import "./live.css";
const API = (import.meta.env.VITE_DASHBOARD_API_URL || "").replace(/\/$/, "");
const icons = [
  Share1Icon,
  Component1Icon,
  ActivityLogIcon,
  StackIcon,
  BarChartIcon,
];
const initial = new URLSearchParams(location.search);
function useFeed() {
  const [data, setData] = useState(null),
    [status, setStatus] = useState("connecting"),
    [error, setError] = useState("");
  useEffect(() => {
    let alive = true, stream, lastMessageAt = null;
    const receive = (payload) => {
      if (payload.schema !== "iron_web_dashboard_v1")
        throw new Error("Unsupported memory feed schema");
      if (alive) {
        lastMessageAt = performance.now();
        setData(payload);
        setStatus("live");
        setError("");
      }
    };
    const controller = new AbortController();
    fetch(API + "/api/dashboard/snapshot", {
      credentials: "include",
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok)
          throw new Error((await r.json()).detail || "Memory feed unavailable");
        return r.json();
      })
      .then(receive)
      .catch((e) => {
        if (e.name !== "AbortError" && alive) {
          setError(e.message);
          setStatus("disconnected");
        }
      });
    const connect = () => {
      stream?.close();
      const source = new EventSource(API + "/api/dashboard/stream", { withCredentials: true });
      stream = source;
      source.addEventListener("snapshot", (e) => {
        if (!alive || stream !== source) return;
        try {
          receive(JSON.parse(e.data));
        } catch (err) {
          setError(err.message);
          setStatus("disconnected");
        }
      });
      source.addEventListener("feed_error", (e) => {
        if (!alive || stream !== source) return;
        lastMessageAt = performance.now();
        setError(JSON.parse(e.data).message);
        setStatus("stale");
      });
      source.onerror = () => {
        if (alive && stream === source)
          setStatus((s) => (s === "connecting" ? "connecting" : "reconnecting"));
      };
    };
    connect();
    // The relay emits every two seconds. A proxy can leave a dead SSE socket
    // open without onerror; elapsed local time must still invalidate "live".
    const watchdog = setInterval(() => {
      if (lastMessageAt === null || performance.now() - lastMessageAt < 10000) return;
      lastMessageAt = performance.now();
      setError("No fresh memory snapshot for 10 seconds. Reconnecting…");
      setStatus("stale");
      connect();
    }, 2000);
    return () => {
      alive = false;
      controller.abort();
      clearInterval(watchdog);
      stream?.close();
    };
  }, []);
  return { data, status, error };
}
export default function LiveApp() {
  const { data, status, error } = useFeed();
  const [viewerError, setViewerError] = useState("");
  async function unlock(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const secret = new FormData(form).get("secret");
    form.reset();
    try {
      const response = await fetch(API + "/viewer/session", {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ secret }),
      });
      if (!response.ok) throw new Error((await response.json()).detail || "Viewer sign-in failed");
      location.reload();
    } catch (failure) { setViewerError(failure.message); }
  }
  const [view, setView] = useState(
      VIEW_NAMES[initial.get("view")] ? initial.get("view") : "graph",
    ),
    [cursor, setCursor] = useState(Number(initial.get("event")) || null),
    [selected, setSelected] = useState(initial.get("mem") || null),
    [follow, setFollow] = useState(
      !initial.has("event") && !initial.has("mem"),
    ),
    [agent, setAgent] = useState(null),
    [query, setQuery] = useState(""),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1),
    [drawer, setDrawer] = useState(null),
    [dialog, setDialog] = useState(null),
    [agentMenu, setAgentMenu] = useState(false),
    [tier, setTier] = useState(null);
  const events = data?.observations?.events || [],
    latest = events.at(-1),
    event = events.find((e) => e.id === cursor) || latest,
    historical = !follow && event?.id !== latest?.id;
  const graph = useMemo(
    () => projection(data, event, historical),
    [data, event?.id, historical],
  );
  const agents = data?.agents?.rows || [],
    context =
      event?.context ||
      graph.contexts.find((c) => c.agent_id === event?.agent_id) ||
      graph.contexts.at(-1),
    reads = events.filter((e) => e.kind === "context_assembled"),
    hits = reads.filter((e) => e.detail?.cache_hit).length;
  const moveTo = useCallback(
    (id) => {
      setFollow(false);
      setCursor(id);
      setPlaying(false);
      setTier(null);
      const rows = data?.observations?.events || [];
      const selectedEvent = rows.find((e) => e.id === id);
      const source =
        selectedEvent?.context ||
        rows
          .filter(
            (e) =>
              e.id <= id &&
              e.context &&
              (!selectedEvent?.agent_id ||
                e.agent_id === selectedEvent.agent_id),
          )
          .at(-1)?.context;
      const sourceNode = selectedEvent?.detail?.memory_id
        ? data?.graph?.nodes.find(
            (n) => n.properties?.memory_id === selectedEvent.detail.memory_id,
          )
        : null;
      setSelected(sourceNode?.id || source?.claim_ids?.[0] || null);
    },
    [data],
  );
  useEffect(() => {
    if (!data) return;
    if (follow) {
      setCursor(latest?.id || null);
      setTier(null);
      const c =
        latest?.context ||
        data.tiers.captured_contexts.find(
          (c) => c.agent_id === latest?.agent_id,
        ) ||
        data.tiers.captured_contexts.at(-1);
      const target = c?.claim_ids?.[0] || data.shared_memory.claims[0]?.id;
      setSelected(target || null);
    } else if (cursor && !events.some((e) => e.id === cursor)) {
      setCursor(events[0]?.id || null);
    }
  }, [data, follow]);
  useEffect(() => {
    const params = new URLSearchParams();
    params.set("view", view);
    if (cursor && !follow) params.set("event", cursor);
    if (selected) params.set("mem", selected);
    history.replaceState(null, "", `${location.pathname}?${params}`);
  }, [view, cursor, selected, follow]);
  useEffect(() => {
    const pop = () => {
      const q = new URLSearchParams(location.search);
      setView(VIEW_NAMES[q.get("view")] ? q.get("view") : "graph");
      setCursor(Number(q.get("event")) || null);
      setFollow(!q.has("event"));
      setSelected(q.get("mem"));
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  useEffect(() => {
    if (!playing) return;
    const index = events.findIndex((e) => e.id === event?.id);
    if (index >= events.length - 1) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(() => {
      setCursor(events[index + 1].id);
      setFollow(false);
    }, 1000 / speed);
    return () => clearTimeout(timer);
  }, [playing, event?.id, events, speed]);
  const select = (id) => {
    setSelected(id);
    setFollow(false);
    setTier(null);
  };
  useEffect(() => {
    const key = (e) => {
      if (e.key === "Escape") {
        setDrawer(null);
        setDialog(null);
        setAgentMenu(false);
        setSelected(null);
        return;
      }
      if (
        e.ctrlKey ||
        e.metaKey ||
        e.altKey ||
        e.target.closest("input,textarea,select,button,[role=button]")
      )
        return;
      if (e.key === "/") {
        e.preventDefault();
        if (innerWidth < 1280) setDrawer("explorer");
        setTimeout(
          () => document.querySelector("[aria-label='Find a memory']")?.focus(),
          0,
        );
      }
      if (e.code === "Space") {
        e.preventDefault();
        setFollow(false);
        setPlaying((v) => !v);
      }
      if (/^[1-5]$/.test(e.key))
        setView(Object.keys(VIEW_NAMES)[Number(e.key) - 1]);
      if (e.key.toLowerCase() === "f") {
        e.preventDefault();
        setFollow((v) => !v);
      }
      const index = events.findIndex((x) => x.id === event?.id);
      if (e.key === "ArrowRight" && events[index + 1])
        moveTo(events[index + 1].id);
      if (e.key === "ArrowLeft" && events[index - 1])
        moveTo(events[index - 1].id);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [event?.id, events, moveTo]);
  const activateAgent = (id) => {
    setAgent((a) => (a === id ? null : id));
    setAgentMenu(false);
  };
  const selectedNode = graph.nodes.find((n) => n.id === selected);
  if (!data)
    return (
      <div className="live-loading">
        <span className="brand">
          ironweb <small>MEMORY</small>
        </span>
        <h1>
          {error
            ? "Memory feed unavailable"
            : "Connecting to application memory"}
        </h1>
        <p>
          {error ||
            "Waiting for the website memory owner and read-only dashboard relay."}
        </p>
        {error === "Viewer sign-in required." ? (
          <form onSubmit={unlock} className="viewer-login">
            <label htmlFor="viewer-secret">Dashboard viewer secret</label>
            <input id="viewer-secret" name="secret" type="password" autoComplete="off" required maxLength={512} />
            <button type="submit">Unlock dashboard</button>
            {viewerError && <p role="alert">{viewerError}</p>}
          </form>
        ) : <button onClick={() => location.reload()}>Reconnect</button>}
        <span>No sample data is substituted.</span>
      </div>
    );
  return (
    <div className="live-app" data-testid="live-dashboard">
      <header className="live-topbar">
        <button
          className="brand"
          onClick={() => {
            setView("graph");
            setFollow(true);
          }}
          aria-label="Dashboard home"
        >
          <span className="brand-mark">
            <i />
            <i />
            <i />
            <i />
          </span>
          ironweb <small>MEMORY</small>
        </button>
        <span className="live-breadcrumb mono">
          workspace /{" "}
          <b>{data.trip_id ? data.trip_id.slice(0, 8) : "shared memory"}</b>
        </span>
        <div
          className="top-context"
          title={`Measured context packet, not hosted model tokens. ${data.tiers.tokenizer}`}
        >
          <span>
            Context{" "}
            {context?.tokens
              ? Math.round(
                  (context.tokens.prompt / data.tiers.policy.context_limit) *
                    100,
                ) + "%"
              : "N/A"}
          </span>
          <span>
            Cache{" "}
            {reads.length
              ? Math.round((hits / reads.length) * 100) + "%"
              : "N/A"}
          </span>
          <Badge />
        </div>
        <div className="live-agent-control">
          <button
            aria-label="Filter agents"
            aria-expanded={agentMenu}
            onClick={() => setAgentMenu((v) => !v)}
          >
            Agents{" "}
            <b>
              {data.agents.observed}/{data.agents.registered}
            </b>{" "}
            ▾
          </button>
          {agentMenu && (
            <div className="agent-menu">
              {agents.map((a) => (
                <button
                  key={a.agent_id}
                  className={`live-agent-chip ${!agent || agent === a.agent_id ? "active" : ""} ${a.agent_id === event?.agent_id ? "acting" : ""}`}
                  style={{ "--agent-color": agentColor(a.agent_id) }}
                  aria-pressed={agent === a.agent_id}
                  onClick={() => activateAgent(a.agent_id)}
                >
                  {a.agent_id === event?.agent_id ? "●" : "○"}{" "}
                  {agentName(a.agent_id)}
                  <span>{a.reads_in_window} reads</span>
                </button>
              ))}
              <button
                onClick={() => {
                  setAgent(null);
                  setAgentMenu(false);
                }}
              >
                Show all agents
              </button>
            </div>
          )}
        </div>
        <button
          className={`connection-state ${status}`}
          onClick={() => setDialog("connection")}
        >
          <i />
          {status.toUpperCase()}
        </button>
        <button
          className={`follow-button ${follow ? "active" : ""}`}
          aria-pressed={follow}
          onClick={() => {
            setFollow((v) => !v);
            setPlaying(false);
          }}
        >
          Follow live
        </button>
        <button
          className="icon-button"
          aria-label="Open help"
          onClick={() => setDialog("help")}
        >
          <QuestionMarkCircledIcon />
        </button>
      </header>
      {status !== "live" && (
        <div className="feed-warning" role="status">
          {error || "Connection interrupted. Reconnecting…"} · Last snapshot{" "}
          {time(data.timestamp)} · displayed data is stale
        </div>
      )}
      <main className="live-columns" data-drawer={drawer || "none"}>
        {drawer && (
          <button
            className="drawer-backdrop"
            aria-label="Close side panel"
            onClick={() => setDrawer(null)}
          />
        )}
        <aside className="live-explorer">
          <header>
            <span className="kicker">Memory explorer</span>
            <span>{graph.nodes.length}</span>
            <button
              className="live-drawer-close"
              aria-label="Close explorer"
              onClick={() => setDrawer(null)}
            >
              <Cross2Icon />
            </button>
          </header>
          <label className="live-search">
            <input
              aria-label="Find a memory"
              placeholder="Find memory or claim…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <span>/</span>
          </label>
          <div className="live-tree">
            {Object.entries(COLORS).map(([t, color]) => (
              <details
                key={t}
                open={
                  !!query ||
                  selectedNode?.tier === t ||
                  (!selectedNode && t === "durable")
                }
              >
                <summary style={{ "--tier-color": color }}>
                  <i />
                  {t === "hot"
                    ? "Hot context"
                    : t === "context"
                      ? "Context cards"
                      : "Durable evidence"}
                  <small>
                    {graph.nodes.filter((n) => n.tier === t).length}
                  </small>
                </summary>
                {graph.nodes
                  .filter(
                    (n) =>
                      n.tier === t &&
                      (!agent || !n.agent_id || n.agent_id === agent) &&
                      `${n.label} ${n.id}`
                        .toLowerCase()
                        .includes(query.toLowerCase()),
                  )
                  .map((n) => (
                    <button
                      className={selected === n.id ? "selected" : ""}
                      key={n.id}
                      onClick={() => select(n.id)}
                      title={n.id}
                    >
                      <span>{n.context ? "○" : n.card ? "▤" : "◇"}</span>
                      <span>{n.label}</span>
                      <small>{n.access || ""}</small>
                    </button>
                  ))}
              </details>
            ))}
          </div>
          <footer>
            <span>{data.scope.replaceAll("_", " ")}</span>
            <button onClick={() => setDialog("connection")}>
              Source & credentials
            </button>
          </footer>
        </aside>
        <section className="live-stage" aria-label="Memory visualization stage">
          <div className="live-mobile-tools">
            <button onClick={() => setDrawer("explorer")}>
              <HamburgerMenuIcon /> Explorer
            </button>
            <button onClick={() => setDrawer("inspector")}>
              <ReaderIcon /> Inspector
            </button>
          </div>
          <nav role="tablist" aria-label="Visualization views">
            {Object.entries(VIEW_NAMES).map(([id, name], i) => {
              const Icon = icons[i];
              return (
                <button
                  key={id}
                  role="tab"
                  aria-selected={view === id}
                  onClick={() => setView(id)}
                >
                  <Icon />
                  {name}
                </button>
              );
            })}
          </nav>
          <ViewHeader
            kicker={
              historical
                ? "Historical context · KG latest"
                : "Application memory"
            }
            title={VIEW_NAMES[view]}
            subtitle={
              view === "graph"
                ? "Actual graph relationships and observed context"
                : view === "resources"
                  ? "Recorded usage with explicit units and sources"
                  : `${events.length} retained observations · ${data.agents.observed} agents observed`
            }
          >
            {agent && (
              <button onClick={() => setAgent(null)}>
                × {agentName(agent)}
              </button>
            )}
          </ViewHeader>
          {view === "graph" && (
            <LiveGraph
              graph={graph}
              selected={selected}
              onSelect={select}
              event={event}
              agent={agent}
            />
          )}
          {view === "agents" && (
            <Wiring
              agents={agents}
              event={event}
              agent={agent}
              onAgent={activateAgent}
              onStore={() => {
                setView("graph");
                setTier("durable");
              }}
            />
          )}
          {view === "activity" && (
            <Activity
              agents={agents}
              events={events}
              event={event}
              agent={agent}
              onEvent={moveTo}
            />
          )}
          {view === "architecture" && (
            <Architecture
              data={data}
              graph={graph}
              onTier={(t) => {
                setTier(t);
                setFollow(false);
              }}
              selectedTier={tier}
            />
          )}
          {view === "resources" && (
            <Resources
              data={data}
              graph={graph}
              event={event}
              onSelect={select}
              events={events}
            />
          )}
        </section>
        <aside className="live-inspector">
          <button
            className="live-drawer-close"
            aria-label="Close inspector"
            onClick={() => setDrawer(null)}
          >
            <Cross2Icon />
          </button>
          <Inspector
            key={selected || tier || "event"}
            data={data}
            node={selectedNode}
            graph={graph}
            tier={tier}
            follow={follow}
            event={event}
            onEvent={moveTo}
            onSelect={select}
            onFollow={() => setFollow(true)}
          />
        </aside>
      </main>
      <Dock
        events={events}
        event={event}
        onEvent={moveTo}
        playing={playing}
        setPlaying={(value) => {
          setFollow(false);
          if (value && event?.id === latest?.id) setCursor(events[0]?.id);
          setPlaying(value);
        }}
        speed={speed}
        setSpeed={setSpeed}
        agent={agent}
        data={data}
      />
      {dialog && (
        <Dialog name={dialog} data={data} onClose={() => setDialog(null)} />
      )}
    </div>
  );
}
