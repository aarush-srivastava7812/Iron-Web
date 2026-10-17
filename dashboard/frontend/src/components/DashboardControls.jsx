import { useEffect, useRef } from "react";
import {
  ActivityLogIcon,
  Share1Icon,
  StackIcon,
  Component1Icon,
  Cross2Icon,
  DownloadIcon,
  ReloadIcon,
} from "@radix-ui/react-icons";
import { AGENTS } from "../memory.js";

export const VIEWS = [
  { id: "graph", label: "Memory graph", Icon: Share1Icon },
  { id: "agents", label: "Agent wiring", Icon: Component1Icon },
  { id: "activity", label: "Activity", Icon: ActivityLogIcon },
  { id: "architecture", label: "Architecture", Icon: StackIcon },
];
export function ViewTabs({ view, onView, onClear, hasFilters }) {
  return (
    <div
      className="stage-tabs flex h-[57px] shrink-0 items-center gap-5 border-b border-line px-5"
      role="tablist"
      aria-label="Visualization views"
      onKeyDown={(event) => {
        if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key))
          return;
        event.preventDefault();
        const current = VIEWS.findIndex((item) => item.id === view);
        const next =
          event.key === "Home"
            ? 0
            : event.key === "End"
              ? VIEWS.length - 1
              : (current +
                  (event.key === "ArrowRight" ? 1 : VIEWS.length - 1)) %
                VIEWS.length;
        onView(VIEWS[next].id);
        event.currentTarget.querySelectorAll('[role="tab"]')[next]?.focus();
      }}
    >
      {VIEWS.map(({ id, label, Icon }) => (
        <button
          key={id}
          role="tab"
          aria-selected={view === id}
          className={`${view === id ? "tab-active text-ink" : "text-muted"} view-tab flex h-full shrink-0 items-center gap-2 text-[12px]`}
          onClick={() => onView(id)}
        >
          <Icon className={`size-3.5 ${view === id ? "text-memory" : ""}`} />
          {label}
        </button>
      ))}
      {hasFilters && (
        <button
          className="clear-filters ml-auto shrink-0 text-[12px] text-mint"
          onClick={onClear}
        >
          Clear filters
        </button>
      )}
    </div>
  );
}
export function DashboardDialog({
  kind,
  onClose,
  events,
  cursor,
  onRestart,
  onReload,
  halfLife,
  onHalfLife,
}) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  function download() {
    const text = JSON.stringify(
      events.map(({ id, ...event }) => event),
      null,
      2,
    );
    const url = URL.createObjectURL(
      new Blob([text], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "events.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <dialog
      ref={ref}
      className="dashboard-dialog"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      aria-labelledby="dialog-title"
    >
      <div className="dialog-body">
        <div className="mb-6 flex items-center justify-between gap-4">
          <h2 id="dialog-title" className="text-xl text-ink">
            {kind === "help"
              ? "How to use this dashboard"
              : "Mock session details"}
          </h2>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <Cross2Icon />
          </button>
        </div>
        {kind === "help" ? (
          <>
            <p className="text-sm leading-7 text-muted">
              This is an interactive simulation of shared agent memory. Every
              value comes from the 40 local events in events.json. It is not
              connected to the website or its memory backend.
            </p>
            <ul className="help-list">
              <li>
                <strong>Memory graph:</strong> select yellow nodes, zoom, drag
                to pan, or focus a selected memory.
              </li>
              <li>
                <strong>Agent wiring:</strong> select an agent or a memory tool
                to inspect its activity.
              </li>
              <li>
                <strong>Activity:</strong> select a heatmap cell or ledger row
                to jump to that event.
              </li>
              <li>
                <strong>Architecture:</strong> explore the three memory tiers
                and their contents.
              </li>
              <li>
                <strong>Replay:</strong> play/pause, change speed, drag the
                scrubber, step through events, or reset to the start.
              </li>
            </ul>
            <div className="shortcut-grid mono">
              <span>Space</span>
              <span>Play / pause</span>
              <span>← / →</span>
              <span>Previous / next event</span>
              <span>/</span>
              <span>Focus memory search</span>
              <span>1–4</span>
              <span>Switch views</span>
              <span>Esc</span>
              <span>Close dialog</span>
            </div>
          </>
        ) : (
          <>
            <div className="session-stats">
              <span>
                <strong>{events.length}</strong>Mock events
              </span>
              <span>
                <strong>{new Set(events.map((e) => e.agent)).size}</strong>
                Agents
              </span>
              <span>
                <strong>{cursor}</strong>Replay position
              </span>
            </div>
            <p className="mt-5 text-xs leading-6 text-muted">
              Source: local events.json. Agents:{" "}
              {Object.values(AGENTS)
                .map((a) => a.short)
                .join(", ")}
              . Conflicts reject stale writes; a forget event removes the
              memory. No API key or backend is used.
            </p>
            <label
              className="mt-6 block text-xs text-ink"
              htmlFor="decay-half-life"
            >
              Illustrative memory retention half-life
            </label>
            <select
              id="decay-half-life"
              value={halfLife}
              onChange={(e) => onHalfLife(Number(e.target.value))}
              className="mt-2 w-full rounded border border-line bg-base p-3 text-sm"
            >
              <option value={120}>2 minutes of event time</option>
              <option value={300}>5 minutes of event time</option>
              <option value={600}>10 minutes of event time</option>
            </select>
            <p className="mt-2 text-[12px] leading-5 text-faint">
              A visual decay model only. It does not change or forget memory.
            </p>
            <div className="dialog-actions mt-6">
              <button onClick={download}>
                <DownloadIcon />
                Download events.json
              </button>
              <button onClick={onReload}>
                <ReloadIcon />
                Reload local data
              </button>
              <button onClick={onRestart}>Restart replay</button>
            </div>
          </>
        )}
        <button className="dialog-done mt-6" onClick={onClose}>
          Done
        </button>
      </div>
    </dialog>
  );
}
