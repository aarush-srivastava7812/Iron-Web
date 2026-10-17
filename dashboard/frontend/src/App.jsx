import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronRightIcon,
  CubeIcon,
  Cross2Icon,
  HamburgerMenuIcon,
  QuestionMarkCircledIcon,
  ReaderIcon,
} from "@radix-ui/react-icons";
import Explorer from "./components/Explorer.jsx";
import MemoryGraph from "./components/MemoryGraph.jsx";
import Inspector from "./components/Inspector.jsx";
import Timeline from "./components/Timeline.jsx";
import AgentWiring from "./components/AgentWiring.jsx";
import ActivityHeatmap from "./components/ActivityHeatmap.jsx";
import Architecture from "./components/Architecture.jsx";
import { AgentInspector, TierInspector } from "./components/SidebarDetails.jsx";
import {
  ViewTabs,
  DashboardDialog,
  VIEWS,
} from "./components/DashboardControls.jsx";
import { AGENTS, TIERS, replay, validateEvents } from "./memory.js";

function Loading({ error, retry }) {
  return (
    <div className="grid min-h-dvh place-content-center bg-base px-6 text-center">
      <CubeIcon className="mx-auto mb-6 size-8 text-memory" />
      <h1 className="text-xl text-ink">
        {error
          ? "The session could not be loaded"
          : "Opening the memory session"}
      </h1>
      <p className="mono mt-3 max-w-md text-xs leading-6 text-muted">
        {error ||
          "Reading local events.json. No backend connection is required."}
      </p>
      {error && (
        <button
          onClick={retry}
          className="mx-auto mt-6 rounded border border-line px-4 py-2 text-sm text-memory"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export default function App() {
  const [events, setEvents] = useState([]),
    [error, setError] = useState(""),
    [request, setRequest] = useState(0);
  const [cursor, setCursor] = useState(27),
    [selectedPath, setSelectedPath] = useState(
      "shared/tier-3/trip/budget.json",
    );
  const [inspectedId, setInspectedId] = useState(27),
    [pulseId, setPulseId] = useState(1),
    [query, setQuery] = useState("");
  const [view, setView] = useState("graph"),
    [selectedAgent, setSelectedAgent] = useState(null),
    [actionFilter, setActionFilter] = useState(null),
    [inspectorMode, setInspectorMode] = useState("memory");
  const [drawer, setDrawer] = useState(null);
  useEffect(() => {
    const close = (event) => {
      if (event.key === "Escape") setDrawer(null);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);
  useEffect(() => {
    if (drawer === "explorer")
      document.querySelector('[aria-label="Find a memory"]')?.focus();
  }, [drawer]);
  const [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState(1),
    [dialog, setDialog] = useState(null),
    [halfLife, setHalfLife] = useState(300);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    fetch("/events.json", { signal: controller.signal, cache: "no-store" })
      .then((response) => {
        if (!response.ok)
          throw new Error(
            "events.json could not be read. Check the file in public/.",
          );
        return response.json();
      })
      .then((data) => {
        const parsed = validateEvents(data);
        setEvents(parsed);
        const initial = Math.min(27, parsed.length);
        setCursor(initial);
        setInspectedId(initial);
        setSelectedPath(parsed[initial - 1].memoryPath);
        setPlaying(false);
      })
      .catch((reason) => {
        if (reason.name !== "AbortError") setError(reason.message);
      });
    return () => controller.abort();
  }, [request]);
  const snapshot = useMemo(() => replay(events, cursor), [events, cursor]),
    fullSnapshot = useMemo(() => replay(events), [events]);
  const activeEvent =
    snapshot.applied.find((event) => event.id === inspectedId) || null;
  const moveTo = useCallback(
    (id, { pause = true } = {}) => {
      const next = Math.max(0, Math.min(events.length, id));
      if (pause) {
        setPlaying(false);
        setSelectedAgent((value) =>
          events[next - 1]?.agent === value ? value : null,
        );
        setActionFilter((value) =>
          events[next - 1]?.action === value ? value : null,
        );
      }
      setCursor(next);
      setInspectedId(next || null);
      setSelectedPath(events[next - 1]?.memoryPath || "shared");
      setInspectorMode("memory");
      setPulseId((value) => value + 1);
    },
    [events],
  );
  useEffect(() => {
    if (!playing) return;
    if (cursor >= events.length) {
      setPlaying(false);
      return;
    }
    const timer = setTimeout(
      () => moveTo(cursor + 1, { pause: false }),
      1400 / speed,
    );
    return () => clearTimeout(timer);
  }, [playing, cursor, speed, moveTo, events.length]);
  const togglePlay = useCallback(() => {
    if (cursor >= events.length) moveTo(0);
    setPlaying((value) => !value);
  }, [cursor, events.length, moveTo]);
  useEffect(() => {
    function shortcuts(event) {
      if (
        dialog ||
        event.ctrlKey ||
        event.metaKey ||
        event.altKey ||
        event.target.closest(
          'input,textarea,select,button,[role="button"],summary,a',
        )
      )
        return;
      if (event.key === "/") {
        event.preventDefault();
        if (window.matchMedia("(max-width: 1279px)").matches)
          setDrawer("explorer");
        else document.querySelector('[aria-label="Find a memory"]')?.focus();
      } else if (event.code === "Space") {
        event.preventDefault();
        togglePlay();
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        moveTo(cursor + 1);
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        moveTo(cursor - 1);
      } else if (/^[1-4]$/.test(event.key))
        setView(VIEWS[Number(event.key) - 1].id);
    }
    window.addEventListener("keydown", shortcuts);
    return () => window.removeEventListener("keydown", shortcuts);
  }, [dialog, togglePlay, moveTo, cursor]);
  function clearFilters() {
    setSelectedAgent(null);
    setActionFilter(null);
    setInspectorMode("memory");
  }
  function reset() {
    clearFilters();
    setQuery("");
    setView("graph");
    moveTo(Math.min(27, events.length));
  }
  function selectMemory(path) {
    setPlaying(false);
    setSelectedPath(path);
    setQuery("");
    const last = snapshot.history.get(path)?.at(-1);
    setInspectedId(last?.id ?? null);
    setInspectorMode("memory");
    if (last) setPulseId((value) => value + 1);
  }
  function selectAgent(agent) {
    setPlaying(false);
    setSelectedAgent((value) => (value === agent ? null : agent));
    setInspectorMode(selectedAgent === agent ? "memory" : "agent");
  }
  function selectTier(tier) {
    setPlaying(false);
    setSelectedPath("shared/" + tier);
    setInspectedId(null);
    setInspectorMode("tier");
  }
  function selectAction(action) {
    setActionFilter(action);
    setView("activity");
  }
  if (error || !events.length)
    return (
      <Loading error={error} retry={() => setRequest((value) => value + 1)} />
    );
  const sharedProps = {
    snapshot,
    activeEvent,
    pulseId,
    selectedAgent,
    actionFilter,
  };
  return (
    <div className="app-shell" id="memory" data-view={view}>
      <div className="workspace flex min-w-0 flex-col">
        <header className="topbar">
          <button onClick={reset} className="brand" aria-label="Dashboard home">
            <span className="brand-mark" aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
            </span>
            ironweb <span className="brand-label mono">MEMORY</span>
          </button>
          <button
            onClick={() => setDialog("session")}
            className="session-breadcrumb mono"
            aria-label="Open workspace session"
          >
            <span>workspace</span>
            <ChevronRightIcon />
            <strong>spiti-expedition</strong>
            <span>/ 003</span>
          </button>
          <div className="topbar-right">
            <div
              className="agent-filters"
              role="group"
              aria-label="Filter by agent"
            >
              {Object.entries(AGENTS).map(([id, agent]) => (
                <button
                  key={id}
                  data-agent={id}
                  className="agent-chip"
                  aria-label={`Select ${agent.name}`}
                  aria-pressed={selectedAgent === id}
                  onClick={() => selectAgent(id)}
                  title={`Filter memories and activity by ${agent.short}`}
                >
                  <span className="agent-chip-dot" aria-hidden="true" />
                  {agent.short}
                  {selectedAgent === id && <span aria-hidden="true">✓</span>}
                </button>
              ))}
            </div>
            <button
              onClick={() => setDialog("session")}
              className="session-status mono"
              aria-label="Open mock session details"
            >
              <i />
              MOCK SESSION
            </button>
            <button
              className="icon-button"
              aria-label="Open help"
              title="Help and shortcuts"
              onClick={() => setDialog("help")}
            >
              <QuestionMarkCircledIcon />
            </button>
          </div>
        </header>
        <main className="main-grid" data-drawer={drawer || "none"}>
          {drawer && (
            <button
              className="drawer-backdrop"
              aria-label="Close side panel"
              onClick={() => setDrawer(null)}
            />
          )}
          <div className="explorer-column side-column">
            <button
              className="drawer-close"
              aria-label="Close memory explorer"
              onClick={() => setDrawer(null)}
            >
              <Cross2Icon />
            </button>
            <Explorer
              snapshot={snapshot}
              selectedPath={selectedPath}
              onSelect={selectMemory}
              query={query}
              setQuery={setQuery}
              selectedAgent={selectedAgent}
              actionFilter={actionFilter}
              onSource={() => setDialog("session")}
              halfLife={halfLife}
            />
          </div>
          <section
            className="stage flex min-h-0 min-w-0 flex-col bg-stage"
            aria-label="Memory visualization stage"
          >
            <div className="drawer-toolbar">
              <button
                onClick={() => setDrawer("explorer")}
                aria-label="Open memory explorer"
              >
                <HamburgerMenuIcon /> Explorer
              </button>
              <span className="mono">MEMORY WORKSPACE</span>
              <button
                onClick={() => setDrawer("inspector")}
                aria-label="Open memory inspector"
              >
                <ReaderIcon /> Inspector
              </button>
            </div>
            <ViewTabs
              view={view}
              onView={setView}
              onClear={clearFilters}
              hasFilters={!!(selectedAgent || actionFilter)}
            />
            {view === "graph" && (
              <MemoryGraph
                events={events}
                {...sharedProps}
                selectedPath={selectedPath}
                onSelect={selectMemory}
              />
            )}
            {view === "agents" && (
              <AgentWiring
                {...sharedProps}
                onAgent={selectAgent}
                onMemory={() => {
                  setView("graph");
                  selectMemory("shared");
                }}
                onAction={selectAction}
              />
            )}
            {view === "activity" && (
              <ActivityHeatmap
                {...sharedProps}
                events={events}
                fullSnapshot={fullSnapshot}
                cursor={cursor}
                onAgent={selectAgent}
                onAction={setActionFilter}
                onEvent={moveTo}
              />
            )}
            {view === "architecture" && (
              <Architecture
                {...sharedProps}
                onTier={selectTier}
                onMemory={selectMemory}
                halfLife={halfLife}
              />
            )}
          </section>
          <div className="inspector-column side-column">
            <button
              className="drawer-close"
              aria-label="Close memory inspector"
              onClick={() => setDrawer(null)}
            >
              <Cross2Icon />
            </button>
            {inspectorMode === "agent" && selectedAgent ? (
              <AgentInspector
                agent={selectedAgent}
                snapshot={snapshot}
                onEvent={moveTo}
                onAction={selectAction}
                onClear={clearFilters}
              />
            ) : inspectorMode === "tier" &&
              TIERS[selectedPath.split("/")[1]] ? (
              <TierInspector
                tierId={selectedPath.split("/")[1]}
                snapshot={snapshot}
                onMemory={selectMemory}
              />
            ) : (
              <Inspector
                snapshot={snapshot}
                selectedPath={selectedPath}
                activeEvent={activeEvent}
                onEvent={moveTo}
                pulseId={pulseId}
                onAgent={selectAgent}
                onMemory={selectMemory}
                onSource={() => setDialog("session")}
              />
            )}
          </div>
        </main>
        <Timeline
          events={events}
          fullSnapshot={fullSnapshot}
          cursor={cursor}
          onEvent={moveTo}
          onReplay={() => {
            setPlaying(false);
            if (activeEvent) setPulseId((value) => value + 1);
            else moveTo(1);
          }}
          playing={playing}
          onTogglePlay={togglePlay}
          speed={speed}
          onSpeed={setSpeed}
          selectedAgent={selectedAgent}
          actionFilter={actionFilter}
        />
      </div>
      {dialog && (
        <DashboardDialog
          kind={dialog}
          onClose={() => setDialog(null)}
          events={events}
          cursor={cursor}
          onRestart={() => {
            setDialog(null);
            moveTo(0);
            setPlaying(true);
          }}
          onReload={() => {
            setDialog(null);
            clearFilters();
            setQuery("");
            setRequest((value) => value + 1);
          }}
          halfLife={halfLife}
          onHalfLife={setHalfLife}
        />
      )}
    </div>
  );
}
