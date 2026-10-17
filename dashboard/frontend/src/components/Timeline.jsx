import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ReloadIcon,
  PlayIcon,
  PauseIcon,
  ResetIcon,
} from "@radix-ui/react-icons";
import { AGENTS, fileName, formatTime, matchesEvent } from "../memory.js";

const GLYPHS = { read: "○", write: "●", update: "↻", forget: "✕" };
const VERBS = {
  read: "read",
  write: "wrote",
  update: "updated",
  forget: "forgot",
};

export default function Timeline({
  events,
  fullSnapshot,
  cursor,
  onEvent,
  onReplay,
  playing,
  onTogglePlay,
  speed,
  onSpeed,
  selectedAgent,
  actionFilter,
}) {
  const conflicts = new Set(fullSnapshot.conflicts.map((event) => event.id));
  const current = events[cursor - 1];
  return (
    <section className="replay-dock" aria-label="Event timeline">
      <div className="dock-transport">
        <div
          className="transport-buttons"
          role="group"
          aria-label="Replay transport"
        >
          <button
            className="icon-button"
            aria-label="Previous event"
            title="Previous event"
            disabled={cursor <= 0}
            onClick={() => onEvent(cursor - 1)}
          >
            <ChevronLeftIcon />
          </button>
          <button
            className="play-button"
            aria-label={playing ? "Pause replay" : "Play replay"}
            onClick={onTogglePlay}
          >
            {playing ? <PauseIcon /> : <PlayIcon />}
            {playing ? "Pause" : "Play"}
          </button>
          <button
            className="icon-button"
            aria-label="Next event"
            title="Next event"
            disabled={cursor >= events.length}
            onClick={() => onEvent(cursor + 1)}
          >
            <ChevronRightIcon />
          </button>
          <select
            className="speed-select mono"
            aria-label="Playback speed"
            value={speed}
            onChange={(event) => onSpeed(Number(event.target.value))}
          >
            {[0.5, 1, 2, 4].map((value) => (
              <option key={value} value={value}>
                {value}×
              </option>
            ))}
          </select>
          <button
            className="transport-reset"
            aria-label="Reset replay"
            title="Reset to the start"
            onClick={() => onEvent(0)}
          >
            <ResetIcon />
            <span>Reset</span>
          </button>
          <button
            className="icon-button replay-pulse"
            aria-label="Replay event"
            title="Replay the selected event’s pulse"
            onClick={onReplay}
          >
            <ReloadIcon />
          </button>
        </div>
        <p className="dock-current" data-agent={current?.agent}>
          {current ? (
            <>
              <span className="action-glyph" aria-hidden="true">
                {GLYPHS[current.action]}
              </span>
              <strong>{AGENTS[current.agent].short}</strong>
              <span>{VERBS[current.action]}</span>
              <span className="mono event-filename">
                {fileName(current.memoryPath)}
              </span>
              {conflicts.has(current.id) && (
                <span className="conflict-caption">Conflict · rejected</span>
              )}
            </>
          ) : (
            <span>Session start · ready to replay</span>
          )}
        </p>
        <span className="dock-position mono">
          <span data-testid="replay-cursor">
            {String(cursor).padStart(2, "0")}
          </span>
          <span className="text-muted"> / {events.length}</span>
        </span>
      </div>
      <div
        className="dock-lanes"
        role="group"
        aria-label="Select a memory event"
      >
        <div
          className="timeline-playhead"
          style={{
            left: `calc(110px + (100% - 110px) * ${Math.max(0, cursor - 0.5) / events.length})`,
          }}
          aria-hidden="true"
        />
        {Object.entries(AGENTS).map(([id, agent]) => (
          <div className="agent-lane" key={id} data-agent={id}>
            <span className="lane-label">
              <i />
              {agent.short}
            </span>
            <div className="lane-events" style={{ "--events": events.length }}>
              {events.map((event) =>
                event.agent === id ? (
                  <button
                    key={event.id}
                    onClick={() => onEvent(event.id)}
                    className={`lane-event ${event.id <= cursor ? "past" : "future"} ${event.id === current?.id ? "inspected" : ""} ${conflicts.has(event.id) ? "conflict" : ""} ${!matchesEvent(event, selectedAgent, actionFilter) ? "dimmed" : ""}`}
                    aria-label={`Event ${event.id}: ${event.agent} ${event.action} ${event.memoryPath}${conflicts.has(event.id) ? ", conflict" : ""}`}
                    aria-pressed={event.id === current?.id}
                    title={`#${event.id} · ${agent.short} · ${event.action} · ${formatTime(event.timestamp)}`}
                  >
                    <span aria-hidden="true">{GLYPHS[event.action]}</span>
                    {conflicts.has(event.id) && (
                      <span className="lane-conflict-label">! Conflict</span>
                    )}
                  </button>
                ) : (
                  <span className="lane-empty" key={event.id} />
                ),
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="dock-axis mono">
        <span className="axis-zone">UTC</span>
        <div className="axis-track">
          <input
            className="replay-range"
            aria-label="Replay position"
            type="range"
            min="0"
            max={events.length}
            step="1"
            value={cursor}
            onChange={(event) => onEvent(Number(event.target.value))}
            style={{ "--progress": `${(cursor / events.length) * 100}%` }}
          />
          <div className="axis-times">
            {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
              <span key={fraction}>
                {formatTime(
                  events[Math.round((events.length - 1) * fraction)].timestamp,
                )}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
