import {
  AGENTS,
  ACTIONS,
  TIERS,
  agentStats,
  tierKey,
  fileName,
  formatTime,
  contentBytes,
} from "../memory.js";

function Frame({ label, children, clear }) {
  return (
    <aside
      className="inspector flex min-h-0 flex-col border-l border-line bg-panel"
      aria-label={label}
    >
      <div className="panel-heading">
        <h2 className="eyebrow">{label}</h2>
        {clear && (
          <button className="text-[12px] text-mint" onClick={clear}>
            Clear filter
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
    </aside>
  );
}
export function AgentInspector({
  agent,
  snapshot,
  onEvent,
  onAction,
  onClear,
}) {
  const stats = agentStats(snapshot, agent),
    info = AGENTS[agent];
  return (
    <Frame label="Agent inspector" clear={onClear}>
      <span className="mono text-[12px] text-mint">{info.code}</span>
      <h3 className="mb-2 mt-3 text-xl text-ink">{info.name}</h3>
      <p className="mb-6 text-xs leading-6 text-muted">
        The explorer and visualizations highlight this agent's observed
        interactions at the current replay position.
      </p>
      <div className="agent-stats">
        <span>
          <strong>{stats.events.length}</strong>Events
        </span>
        <span>
          <strong>{stats.memories}</strong>Memories
        </span>
        <span>
          <strong>{stats.reads}</strong>Reads
        </span>
        <span>
          <strong>{stats.writes}</strong>Accepted writes
        </span>
      </div>
      <h4 className="eyebrow mb-3 mt-6">FILTER BY ACTION</h4>
      <div className="action-filters">
        {ACTIONS.map((action) => (
          <button key={action} onClick={() => onAction(action)}>
            {action}
          </button>
        ))}
      </div>
      <h4 className="eyebrow mb-3 mt-6">RECENT EVENTS</h4>
      {stats.events
        .slice(-12)
        .reverse()
        .map((event) => (
          <button
            className="agent-event"
            key={event.id}
            onClick={() => onEvent(event.id)}
          >
            <span className="mono text-[12px] text-faint">
              #{event.id} · {formatTime(event.timestamp)}
            </span>
            <span
              className={`block text-xs ${event.conflict ? "text-conflict" : "text-ink"}`}
            >
              {event.conflict ? "Write conflict" : event.action} /{" "}
              {fileName(event.memoryPath)}
            </span>
          </button>
        ))}
      {!stats.events.length && (
        <p className="text-xs text-muted">No activity from this agent yet.</p>
      )}
    </Frame>
  );
}
export function TierInspector({ tierId, snapshot, onMemory }) {
  const tier = TIERS[tierId],
    memories = [...snapshot.memories.values()].filter(
      (memory) => tierKey(memory.path) === tierId,
    );
  return (
    <Frame label="Tier inspector">
      <span className="mono text-[12px] text-memory">
        TIER {tier.number} / {tier.storage}
      </span>
      <h3 className="mb-2 mt-3 text-xl text-ink">{tier.name}</h3>
      <p className="text-xs leading-6 text-muted">
        {tier.description}. This is a mock snapshot, not live storage telemetry.
      </p>
      <div className="agent-stats mt-5">
        <span>
          <strong>{memories.length}</strong>Memories
        </span>
        <span>
          <strong>{contentBytes(memories)}</strong>Content bytes
        </span>
      </div>
      <h4 className="eyebrow mb-3 mt-6">MEMORY CONTENTS</h4>
      {memories.map((memory) => (
        <button
          key={memory.path}
          className="agent-event"
          onClick={() => onMemory(memory.path)}
        >
          <span className="mono text-xs text-ink">{fileName(memory.path)}</span>
          <span className="mono mt-1 block text-[12px] text-muted">
            v{memory.version} · {AGENTS[memory.writer].short}
          </span>
        </button>
      ))}
    </Frame>
  );
}
