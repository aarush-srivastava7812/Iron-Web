import { motion, useReducedMotion } from "framer-motion";
import { AGENTS, ACTIONS, agentStats } from "../memory.js";

export default function AgentWiring({
  snapshot,
  activeEvent,
  pulseId,
  selectedAgent,
  actionFilter,
  onAgent,
  onMemory,
  onAction,
}) {
  const reduced = useReducedMotion();
  return (
    <div className="alternate-view wiring-view" data-testid="agent-wiring">
      <div className="view-heading">
        <div>
          <span className="eyebrow">AGENT CONNECTIONS</span>
          <h2>One shared memory. Three perspectives.</h2>
        </div>
        <span className="mono text-muted text-[12px]">
          {snapshot.applied.length} observed events
        </span>
      </div>
      <svg
        className="wiring-svg"
        viewBox="0 0 820 510"
        aria-label="Agents connected to shared memory and memory tools"
      >
        <text x="28" y="34" className="wiring-label">
          AGENTS
        </text>
        <text x="344" y="34" className="wiring-label">
          MEMORY STORE
        </text>
        <text x="644" y="34" className="wiring-label">
          MEMORY TOOLS
        </text>
        {Object.keys(AGENTS).map((id, index) => {
          const y = 110 + index * 145,
            active = activeEvent?.agent === id,
            stats = agentStats(snapshot, id);
          const d = `M 220 ${y} C 295 ${y} 270 255 337 255`;
          return (
            <g key={id}>
              <path
                d={d}
                className="wiring-edge"
                stroke={active ? "var(--agent-researcher)" : "var(--ui-border)"}
                opacity={!selectedAgent || selectedAgent === id ? 0.85 : 0.25}
              />
              {active && !reduced && (
                <motion.path
                  key={`${pulseId}-${id}`}
                  data-wiring-event={activeEvent.id}
                  d={d}
                  fill="none"
                  stroke="var(--agent-researcher)"
                  strokeWidth="2.5"
                  initial={{ pathLength: 0, opacity: 1 }}
                  animate={{ pathLength: 1, opacity: 0 }}
                  transition={{ duration: 1.1 }}
                />
              )}
              <g
                role="button"
                tabIndex="0"
                aria-label={`Inspect ${AGENTS[id].name}`}
                onClick={() => onAgent(id)}
                onKeyDown={(e) => {
                  if (["Enter", " "].includes(e.key)) {
                    e.preventDefault();
                    onAgent(id);
                  }
                }}
                className="wiring-node"
              >
                <rect
                  x="28"
                  y={y - 34}
                  width="192"
                  height="68"
                  rx="12"
                  fill={
                    selectedAgent === id
                      ? "var(--ui-raised)"
                      : "var(--ui-raised)"
                  }
                  stroke={
                    selectedAgent === id
                      ? "var(--agent-researcher)"
                      : "var(--ui-border)"
                  }
                />
                <circle
                  cx="48"
                  cy={y - 10}
                  r="3"
                  fill="var(--agent-researcher)"
                />
                <text x="60" y={y - 6} className="wiring-title">
                  {AGENTS[id].short}
                </text>
                <text x="48" y={y + 15} className="wiring-description">
                  {stats.events.length} events · {stats.memories} memories
                </text>
              </g>
            </g>
          );
        })}
        <g
          role="button"
          tabIndex="0"
          aria-label="Explore shared memory store"
          onClick={onMemory}
          onKeyDown={(e) => {
            if (["Enter", " "].includes(e.key)) {
              e.preventDefault();
              onMemory();
            }
          }}
          className="wiring-node"
        >
          <rect
            x="337"
            y="210"
            width="160"
            height="90"
            rx="12"
            fill="var(--ui-raised)"
            stroke="var(--state-current)"
          />
          <text
            x="417"
            y="245"
            textAnchor="middle"
            className="wiring-title"
            fill="var(--state-current)"
          >
            Shared memory
          </text>
          <text
            x="417"
            y="267"
            textAnchor="middle"
            className="wiring-description"
          >
            {snapshot.memories.size} current memories
          </text>
        </g>
        {ACTIONS.map((action, index) => {
          const y = 95 + index * 105,
            active = activeEvent?.action === action,
            d = `M 497 255 C 565 255 570 ${y} 638 ${y}`;
          return (
            <g key={action}>
              <path
                d={d}
                className="wiring-edge"
                stroke={active ? "var(--agent-researcher)" : "var(--ui-border)"}
              />
              {active && !reduced && (
                <motion.path
                  key={`${pulseId}-${action}`}
                  data-wiring-event={activeEvent.id}
                  d={d}
                  fill="none"
                  stroke="var(--agent-researcher)"
                  strokeWidth="2"
                  initial={{ pathLength: 0, opacity: 0.9 }}
                  animate={{ pathLength: 1, opacity: 0 }}
                  transition={{ duration: 1.1 }}
                />
              )}
              <g
                role="button"
                tabIndex="0"
                aria-label={`Filter ${action} tool events`}
                onClick={() => onAction(action)}
                onKeyDown={(e) => {
                  if (["Enter", " "].includes(e.key)) {
                    e.preventDefault();
                    onAction(action);
                  }
                }}
                className="wiring-node"
              >
                <rect
                  x="638"
                  y={y - 27}
                  width="154"
                  height="54"
                  rx="9"
                  fill={
                    actionFilter === action
                      ? "var(--ui-raised)"
                      : "var(--ui-raised)"
                  }
                  stroke={
                    actionFilter === action
                      ? "var(--agent-researcher)"
                      : "var(--ui-border)"
                  }
                />
                <text x="654" y={y - 1} className="wiring-title">
                  memory.{action}
                </text>
                <text x="654" y={y + 15} className="wiring-description">
                  {snapshot.applied.filter((e) => e.action === action).length}{" "}
                  invocations
                </text>
              </g>
            </g>
          );
        })}
      </svg>
      <p className="mono text-[12px] text-muted">
        Select an agent to inspect its usage. Select a tool to open its event
        history. Tools represent the four actions in events.json.
      </p>
    </div>
  );
}
