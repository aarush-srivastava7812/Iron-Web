import {
  AGENTS,
  ACTIONS,
  matchesEvent,
  formatTime,
  fileName,
} from "../memory.js";

export default function ActivityHeatmap({
  events,
  fullSnapshot,
  cursor,
  activeEvent,
  selectedAgent,
  actionFilter,
  onAgent,
  onAction,
  onEvent,
}) {
  const ledger = fullSnapshot.applied.filter((event) =>
    matchesEvent(event, selectedAgent, actionFilter),
  );
  return (
    <div
      className="alternate-view activity-view"
      data-testid="activity-heatmap"
    >
      <div className="view-heading">
        <div>
          <span className="eyebrow">ACTIVITY OVER TIME</span>
          <h2>Every cell is one memory event.</h2>
        </div>
        <span className="mono text-[12px] text-muted">
          {ledger.filter((e) => e.id <= cursor).length} / {ledger.length} events
        </span>
      </div>
      <div className="action-filters" aria-label="Filter event actions">
        {[null, ...ACTIONS].map((action) => (
          <button
            key={action || "all"}
            aria-pressed={actionFilter === action}
            className={actionFilter === action ? "chosen" : ""}
            onClick={() => onAction(action)}
          >
            {action || "All actions"}
          </button>
        ))}
      </div>
      <div className="heatmap-scroll">
        <div className="heatmap" style={{ "--events": events.length }}>
          <div className="heatmap-row">
            <span className="eyebrow">AGENT / EVENT</span>
            <div className="heatmap-axis">
              {events.map((event) => (
                <span key={event.id}>
                  {event.id === 1 || event.id % 5 === 0
                    ? String(event.id).padStart(2, "0")
                    : ""}
                </span>
              ))}
            </div>
          </div>
          {Object.entries(AGENTS).map(([id, agent]) => (
            <div className="heatmap-row" key={id}>
              <button
                className={`heatmap-agent ${selectedAgent === id ? "chosen" : ""}`}
                onClick={() => onAgent(id)}
                aria-label={`Inspect ${agent.name}`}
              >
                {agent.short}
                <span>{agent.code}</span>
              </button>
              <div className="heatmap-cells">
                {fullSnapshot.applied.map((event) =>
                  event.agent === id ? (
                    <button
                      key={event.id}
                      data-heatmap-event={event.id}
                      onClick={() => onEvent(event.id)}
                      aria-label={`Inspect heatmap event ${event.id}`}
                      title={`#${event.id} · ${formatTime(event.timestamp)} · ${event.action} · ${fileName(event.memoryPath)}`}
                      className={`heatmap-cell filled ${event.conflict ? "conflict" : ""} ${event.id > cursor ? "future" : ""} ${event.id === activeEvent?.id ? "selected" : ""} ${!matchesEvent(event, selectedAgent, actionFilter) ? "dimmed" : ""}`}
                    />
                  ) : (
                    <span key={event.id} className="heatmap-cell" />
                  ),
                )}
              </div>
            </div>
          ))}
          <div className="heatmap-row">
            <span className="mono text-[12px] text-faint">UTC</span>
            <div className="heatmap-times">
              <span>{formatTime(events[0].timestamp)}</span>
              <span>
                {formatTime(events[Math.floor(events.length / 2)].timestamp)}
              </span>
              <span>{formatTime(events.at(-1).timestamp)}</span>
            </div>
          </div>
        </div>
      </div>
      <div className="mono mb-6 flex flex-wrap gap-5 text-[12px] text-muted">
        <span>Mint: activity</span>
        <span className="text-conflict">Red: conflict</span>
        <span>Dim: future / filtered</span>
      </div>
      <div className="ledger-heading">
        <h3 className="eyebrow">EVENT LEDGER</h3>
        <span className="mono text-[12px] text-faint">
          SELECT A ROW TO REPLAY ITS SNAPSHOT
        </span>
      </div>
      <div className="event-ledger">
        {ledger.map((event) => (
          <button
            key={event.id}
            className={`ledger-row ${event.id === activeEvent?.id ? "selected" : ""} ${event.id > cursor ? "future" : ""}`}
            onClick={() => onEvent(event.id)}
            aria-label={`Inspect ledger event ${event.id}`}
          >
            <span className="mono text-faint">
              {String(event.id).padStart(2, "0")}
            </span>
            <span className="mono text-muted">
              {formatTime(event.timestamp)}
            </span>
            <span className="text-mint">{AGENTS[event.agent].short}</span>
            <span className={event.conflict ? "text-conflict" : "text-muted"}>
              {event.conflict ? "conflict" : event.action}
            </span>
            <span className="mono truncate text-ink">
              {fileName(event.memoryPath)}
            </span>
          </button>
        ))}
        {!ledger.length && (
          <p className="py-5 text-sm text-muted">
            No events match these filters. Choose another action or clear the
            filters.
          </p>
        )}
      </div>
    </div>
  );
}
