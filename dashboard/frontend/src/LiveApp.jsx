import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Cross2Icon,
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
  time,
  projection,
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
import "./resource-charts.css";
import "./dashboard-pages.css";
import { PAGES, readPage, pageUrl } from "./dashboardRoutes.js";
import {
  PageLink,
  PageNavigation,
  Overview,
  AgentDirectory,
  EventJournal,
  RunHistoryPage,
  TinyFishIntelligence,
} from "./DashboardPages.jsx";
const API = (import.meta.env.VITE_DASHBOARD_API_URL || "").replace(/\/$/, "");
const initial = new URLSearchParams(location.search);
function useFeed() {
  const [data, setData] = useState(null),
    [status, setStatus] = useState("connecting"),
    [error, setError] = useState(""),
    [website, setWebsite] = useState(""),
    [revision, setRevision] = useState(0);
  const reconnect = useCallback(() => {
    setData(null);
    setError("");
    setStatus("connecting");
    setRevision((n) => n + 1);
  }, []);
  useEffect(() => {
    let alive = true,
      stream,
      lastMessageAt = null,
      owner = null,
      checking = false,
      mode = "website";
    const controller = new AbortController();
    const fail = (message, auth = false) => {
      if (!alive) return;
      setError(message);
      setStatus(auth ? "disconnected" : "stale");
      if (auth) {
        setData(null);
        stream?.close();
        lastMessageAt = null;
        owner = null;
      }
    };
    const receive = (payload) => {
      if (payload.schema !== "iron_web_dashboard_v1")
        throw new Error("Unsupported memory feed schema");
      if (mode === "website" && payload.connection?.mode !== "website")
        throw new Error("The feed is not connected to a website account");
      if (!alive) return;
      owner = payload.connection?.user_id || null;
      lastMessageAt = performance.now();
      setData(payload);
      setStatus("live");
      setError("");
    };
    const connect = () => {
      stream?.close();
      const source = new EventSource(API + "/api/dashboard/stream", {
        withCredentials: true,
      });
      stream = source;
      source.addEventListener("snapshot", (e) => {
        if (!alive || stream !== source) return;
        try {
          receive(JSON.parse(e.data));
        } catch (e) {
          fail(e.message, true);
        }
      });
      source.addEventListener("feed_error", (e) => {
        if (!alive || stream !== source) return;
        const detail = JSON.parse(e.data);
        fail(detail.message, detail.status === 401);
      });
      source.onerror = () => {
        if (alive && stream === source)
          setStatus((s) => (s === "disconnected" ? s : "reconnecting"));
      };
    };
    async function start() {
      try {
        const config = await fetch(API + "/api/dashboard/connection", {
          credentials: "include",
          signal: controller.signal,
          cache: "no-store",
        });
        if (config.ok) {
          const info = await config.json();
          mode = info.mode;
          if (alive) setWebsite(info.website_url || "");
        }
        const r = await fetch(API + "/api/dashboard/snapshot?fresh=true", {
          credentials: "include",
          signal: controller.signal,
          cache: "no-store",
        });
        const payload = await r.json();
        if (!r.ok) {
          fail(payload.detail || "Memory feed unavailable", r.status === 401);
          return;
        }
        receive(payload);
        if (alive) connect();
      } catch (e) {
        if (e.name !== "AbortError") fail(e.message);
      }
    }
    start();
    // Fresh cookie probes stop an old stream after website logout/account switch.
    const probe = setInterval(async () => {
      if (!alive || checking || mode !== "website") return;
      checking = true;
      try {
        const r = await fetch(API + "/api/dashboard/session", {
          credentials: "include",
          cache: "no-store",
          signal: controller.signal,
        });
        if (r.status === 401) {
          fail(
            "Sign in to the travel website in this browser, then click Follow live.",
            true,
          );
          return;
        }
        if (r.ok) {
          const session = await r.json();
          if (session.connection.user_id !== owner && alive) reconnect();
        }
      } catch (e) {
        if (e.name !== "AbortError")
          fail("The travel website is unreachable. Reconnecting…");
      } finally {
        checking = false;
      }
    }, 3000);
    const watchdog = setInterval(() => {
      if (lastMessageAt === null || performance.now() - lastMessageAt < 10000)
        return;
      lastMessageAt = performance.now();
      fail("No fresh memory snapshot for 10 seconds. Reconnecting…");
      connect();
    }, 2000);
    return () => {
      alive = false;
      controller.abort();
      clearInterval(probe);
      clearInterval(watchdog);
      stream?.close();
    };
  }, [revision, reconnect]);
  return { data, status, error, website, reconnect };
}
export default function LiveApp() {
  const { data, status, error, website, reconnect } = useFeed();
  const searchRequested = useRef(false);
  const [focusRequest, requestSearch] = useState(0);
  const [viewerError, setViewerError] = useState("");
  async function unlock(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const secret = new FormData(form).get("secret");
    form.reset();
    try {
      const response = await fetch(API + "/viewer/session", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret }),
      });
      if (!response.ok)
        throw new Error(
          (await response.json()).detail || "Viewer sign-in failed",
        );
      location.reload();
    } catch (failure) {
      setViewerError(failure.message);
    }
  }
  const [view, setView] = useState(
      readPage(location.pathname, location.search),
    ),
    [cursor, setCursor] = useState(Number(initial.get("event")) || null),
    [selected, setSelected] = useState(initial.get("mem") || null),
    [follow, setFollow] = useState(
      !initial.has("event") && !initial.has("mem"),
    ),
    [agent, setAgent] = useState(initial.get("agent") || null),
    [query, setQuery] = useState(""),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1),
    [drawer, setDrawer] = useState(null),
    [dialog, setDialog] = useState(null),
    [agentMenu, setAgentMenu] = useState(false),
    [tier, setTier] = useState(null);
  const followLive = useCallback(() => {
    setFollow(true);
    setCursor(null);
    setSelected(null);
    setTier(null);
    setAgent(null);
    setAgentMenu(false);
    setQuery("");
    setPlaying(false);
    setDrawer(null);
    setDialog(null);
    reconnect();
  }, [reconnect]);
  const ownerRef = useRef(null);
  useEffect(() => {
    const owner = data?.connection?.user_id;
    if (owner && ownerRef.current !== owner) {
      if (ownerRef.current) {
        setFollow(true);
        setCursor(null);
        setSelected(null);
        setAgent(null);
        setQuery("");
        setTier(null);
        setDrawer(null);
      }
      ownerRef.current = owner;
    }
  }, [data?.connection?.user_id]);
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
  const hrefFor = useCallback(
    (page) => pageUrl(page, { cursor, selected, follow, agent }),
    [cursor, selected, follow, agent],
  );
  const navigate = useCallback(
    (page) => {
      if (!Object.hasOwn(PAGES, page)) return;
      if (readPage(location.pathname, location.search) !== page)
        history.pushState(null, "", hrefFor(page));
      setView(page);
      setDrawer(null);
      setPlaying(false);
    },
    [hrefFor],
  );
  useEffect(() => {
    if (view === "not-found") return;
    history.replaceState(null, "", hrefFor(view));
  }, [view, hrefFor]);
  useEffect(() => {
    const pop = () => {
      const q = new URLSearchParams(location.search);
      setView(readPage(location.pathname, location.search));
      setCursor(Number(q.get("event")) || null);
      setFollow(!q.has("event") && !q.has("mem"));
      setSelected(q.get("mem"));
      setAgent(q.get("agent"));
      setDrawer(null);
      setPlaying(false);
    };
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  useEffect(() => {
    document.title = `${PAGES[view]?.name || "Page not found"} · TinyFish × Iron Web`;
    const frame = requestAnimationFrame(() => {
      const target = searchRequested.current
        ? '[aria-label="Find a memory"]'
        : "#page-title";
      document.querySelector(target)?.focus({ preventScroll: true });
      searchRequested.current = false;
      const main = document.querySelector(".dashboard-main");
      if (main) main.scrollTop = 0;
    });
    return () => cancelAnimationFrame(frame);
  }, [view, !!data, focusRequest]);
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
    if (innerWidth < 1280) setDrawer("inspector");
  };
  useEffect(() => {
    const key = (e) => {
      if (e.key === "Escape") {
        setDrawer(null);
        setDialog(null);
        setAgentMenu(false);
        return;
      }
      if (
        e.ctrlKey ||
        e.metaKey ||
        e.altKey ||
        e.target.closest(
          "input,textarea,select,button,a,[role=button],[contenteditable=true]",
        )
      )
        return;
      if (e.key === "/") {
        e.preventDefault();
        searchRequested.current = true;
        requestSearch((n) => n + 1);
        navigate("graph");
        if (innerWidth < 1280) setDrawer("explorer");
      }
      if (e.code === "Space" && view === "activity") {
        e.preventDefault();
        setFollow(false);
        setPlaying((v) => !v);
      }
      if (/^[1-5]$/.test(e.key))
        navigate(Object.keys(VIEW_NAMES)[Number(e.key) - 1]);
      if (e.key.toLowerCase() === "f") {
        e.preventDefault();
        if (follow) setFollow(false);
        else followLive();
      }
      const index = events.findIndex((x) => x.id === event?.id);
      if (e.key === "ArrowRight" && events[index + 1])
        moveTo(events[index + 1].id);
      if (e.key === "ArrowLeft" && events[index - 1])
        moveTo(events[index - 1].id);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [event?.id, events, moveTo, navigate, view, follow, followLive]);
  useEffect(() => {
    if (!drawer || (view === "graph" && innerWidth >= 1280)) return;
    const panel = document.querySelector(
      drawer === "explorer" ? ".live-explorer" : ".live-inspector",
    );
    const previous = document.activeElement;
    const focusable = () =>
      [
        ...(panel?.querySelectorAll(
          "button, input, select, summary, a[href], [tabindex='0']",
        ) || []),
      ].filter((el) => !el.disabled && el.getClientRects().length);
    focusable()[0]?.focus({ preventScroll: true });
    const trap = (e) => {
      if (e.key !== "Tab") return;
      const items = focusable(),
        first = items[0],
        last = items.at(-1);
      if (!first) return;
      if (
        e.shiftKey &&
        (document.activeElement === first ||
          !panel.contains(document.activeElement))
      ) {
        e.preventDefault();
        last.focus();
      } else if (
        !e.shiftKey &&
        (document.activeElement === last ||
          !panel.contains(document.activeElement))
      ) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", trap);
    return () => {
      window.removeEventListener("keydown", trap);
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, [drawer, view]);
  const activateAgent = (id) => {
    setAgent((a) => (a === id ? null : id));
    setAgentMenu(false);
  };
  const selectedNode = graph.nodes.find((n) => n.id === selected);
  if (!data)
    return (
      <div className="live-loading">
        <span className="brand">
          ironweb <small>× TINYFISH</small>
        </span>
        <h1>
          {error.startsWith("Sign in to the travel website")
            ? "Connect your travel account"
            : error
              ? "Memory feed unavailable"
              : "Connecting to your travel website"}
        </h1>
        <p>
          {error ||
            "Sign in to Voyara in this browser to view your real travel activity."}
        </p>
        {error === "Viewer sign-in required." ? (
          <form onSubmit={unlock} className="viewer-login">
            <label htmlFor="viewer-secret">Dashboard viewer secret</label>
            <input
              id="viewer-secret"
              name="secret"
              type="password"
              autoComplete="off"
              required
              maxLength={512}
            />
            <button type="submit">Unlock dashboard</button>
            {viewerError && <p role="alert">{viewerError}</p>}
          </form>
        ) : (
          <div className="website-connect">
            <button onClick={followLive}>Follow live</button>
            {website && (
              <a href={website} target="_blank" rel="noopener noreferrer">
                Open travel website to sign in
              </a>
            )}
          </div>
        )}
        <span>No sample data is substituted.</span>
      </div>
    );
  return (
    <div
      className="live-app dashboard-shell"
      data-page={view}
      data-testid="live-dashboard"
    >
      <a className="dashboard-skip" href="#page-title">
        Skip to main content
      </a>
      <header className="live-topbar">
        <PageLink
          page="overview"
          hrefFor={hrefFor}
          navigate={navigate}
          className="brand"
          aria-label="Dashboard home"
        >
          <span className="brand-mark">
            <i />
            <i />
            <i />
            <i />
          </span>
          ironweb <small>× TINYFISH</small>
        </PageLink>
        <span className="live-breadcrumb mono">
          workspace /{" "}
          <b>
            {data.connection?.username ||
              (data.trip_id ? data.trip_id.slice(0, 8) : "shared memory")}
          </b>
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
          onClick={followLive}
        >
          Follow live
        </button>
        <button
          className="icon-button source-tools"
          aria-label="Inspect data source"
          title="Source & credentials"
          onClick={() => setDialog("connection")}
        >
          <ReaderIcon />
        </button>
        <button
          className="icon-button"
          aria-label="Open help"
          onClick={() => setDialog("help")}
        >
          <QuestionMarkCircledIcon />
        </button>
      </header>
      <PageNavigation current={view} hrefFor={hrefFor} navigate={navigate} />
      <main className="dashboard-main" id="dashboard-content">
        {status !== "live" && (
          <div className="feed-warning" role="status">
            {error || "Connection interrupted. Reconnecting…"} · Last snapshot{" "}
            {time(data.timestamp)} · displayed data is stale
          </div>
        )}
        <ViewHeader
          kicker={
            historical
              ? "Pinned observation · graph shows latest storage"
              : "Memory workspace"
          }
          title={PAGES[view]?.name || "Page not found"}
          subtitle={
            PAGES[view]?.description ||
            "This dashboard page does not exist. Use the navigation to continue."
          }
        >
          {agent && (
            <button
              className="active-agent-filter"
              onClick={() => setAgent(null)}
              aria-label={`Clear ${agentName(agent)} filter`}
            >
              <Cross2Icon /> {agentName(agent)}
            </button>
          )}
          {view === "graph" && (
            <span className="page-heading-note">
              Select a node to inspect its source
            </span>
          )}
        </ViewHeader>
        {view === "overview" && (
          <Overview
            data={data}
            graph={graph}
            events={events}
            status={status}
            hrefFor={hrefFor}
            navigate={navigate}
            onEvent={moveTo}
          />
        )}
        {view === "tinyfish" && <TinyFishIntelligence data={data} />}
        {view === "not-found" && (
          <div className="page-empty">
            <PageLink page="overview" hrefFor={hrefFor} navigate={navigate}>
              Go to overview
            </PageLink>
          </div>
        )}
        {view === "activity" && (
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
        )}
        {view === "history" && (
          <RunHistoryPage data={data} agent={agent} api={API} />
        )}
        {Object.hasOwn(VIEW_NAMES, view) && (
          <div
            className={`live-columns ${view !== "graph" ? "single-page" : "graph-page"}`}
            data-drawer={drawer || "none"}
          >
            {drawer && (
              <button
                className="drawer-backdrop"
                aria-label="Close side panel"
                onClick={() => setDrawer(null)}
              />
            )}
            {view === "graph" && (
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
            )}
            <section
              className="live-stage"
              aria-label={`${PAGES[view]?.name} workspace`}
            >
              {view === "graph" && (
                <div className="live-mobile-tools">
                  <button onClick={() => setDrawer("explorer")}>
                    <HamburgerMenuIcon /> Explorer
                  </button>
                  <button onClick={() => setDrawer("inspector")}>
                    <ReaderIcon /> Inspector
                  </button>
                </div>
              )}
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
                <>
                  <Wiring
                    agents={agents}
                    event={event}
                    agent={agent}
                    storeLabel={
                      data.storage.backend === "iron_web_2"
                        ? "FALKORDB + SQLITE"
                        : "SHARED MEMORY SERVICE"
                    }
                    onAgent={activateAgent}
                    onStore={() => {
                      navigate("graph");
                      setTier("durable");
                    }}
                  />
                  <AgentDirectory
                    agents={agents}
                    agent={agent}
                    onAgent={activateAgent}
                  />
                </>
              )}
              {view === "activity" && (
                <>
                  <Activity
                    agents={agents}
                    events={events}
                    event={event}
                    agent={agent}
                    onEvent={(id) => {
                      moveTo(id);
                      setDrawer("inspector");
                    }}
                  />
                  <EventJournal
                    events={events}
                    event={event}
                    agent={agent}
                    onEvent={(id) => {
                      moveTo(id);
                      setDrawer("inspector");
                    }}
                  />
                </>
              )}
              {view === "architecture" && (
                <Architecture
                  data={data}
                  graph={graph}
                  onTier={(t) => {
                    setTier(t);
                    setFollow(false);
                    setDrawer("inspector");
                  }}
                  selectedTier={tier}
                />
              )}
              {view === "resources" && (
                <Resources
                  data={data}
                  graph={graph}
                  event={event}
                  onSelect={(id) => {
                    select(id);
                    navigate("graph");
                    if (innerWidth < 1280) setDrawer("inspector");
                  }}
                  events={events}
                />
              )}
            </section>
            {(view === "graph" || drawer === "inspector") && (
              <aside className="live-inspector" aria-label="Memory inspector">
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
                  onFollow={followLive}
                />
              </aside>
            )}
          </div>
        )}
      </main>
      {dialog && (
        <Dialog name={dialog} data={data} onClose={() => setDialog(null)} />
      )}
    </div>
  );
}
