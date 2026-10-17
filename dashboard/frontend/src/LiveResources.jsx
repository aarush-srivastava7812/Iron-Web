import { useState } from "react";
import {
  PlayIcon,
  PauseIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ResetIcon,
} from "@radix-ui/react-icons";
import {
  agentColor,
  agentName,
  glyph,
  time,
  bytes,
  isConflict,
  contextUnit,
  eventLabel,
} from "./liveData.js";
import { Badge, Json } from "./LivePanels.jsx";
export function Resources({ data, graph, event, onSelect, events }) {
  const [tab, setTab] = useState("Context"),
    [open, setOpen] = useState(null);
  const unit = contextUnit(data),
    policy = data.tiers.policy,
    reads = events.filter(
      (e) => e.kind === "context_assembled" && e.id <= event?.id,
    ),
    hits = reads.filter((e) => e.detail.cache_hit).length,
    usage = data.credentials.usage,
    resources = data.resources || {};
  return (
    <div className="live-resources">
      <div className="resource-tabs">
        {["Context", "Cache", "Provider", "Hardware", "Latency"].map((t) => (
          <button aria-pressed={tab === t} key={t} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      {tab === "Context" && (
        <>
          <div className="resource-title">
            <h2>Context X-ray</h2>
            <span>
              {unit} <Badge />
            </span>
          </div>
          <div className="context-xray">
            {graph.contexts.length ? (
              graph.contexts.map((c) => {
                const used = c.tokens?.prompt || 0,
                  sys = c.tokens?.agent || 0,
                  hot = c.tokens?.traveller || 0,
                  rest = Math.max(0, used - sys - hot);
                return (
                  <section key={c.agent_id}>
                    <button
                      className="context-row"
                      onClick={() =>
                        setOpen(open === c.agent_id ? null : c.agent_id)
                      }
                    >
                      <span style={{ color: agentColor(c.agent_id) }}>
                        {agentName(c.agent_id)}
                      </span>
                      <div
                        className="context-bar"
                        title={`Instructions ${sys}, traveler ${hot}, remaining framing/cards/evidence ${rest}; limit ${policy.context_limit} ${unit}`}
                      >
                        <i
                          style={{
                            width: `${(sys / policy.context_limit) * 100}%`,
                            background: "var(--agent-planner)",
                          }}
                        />
                        <i
                          style={{
                            width: `${(hot / policy.context_limit) * 100}%`,
                            background: "var(--tier-hot)",
                          }}
                        />
                        <i
                          style={{
                            width: `${(rest / policy.context_limit) * 100}%`,
                            background: "var(--tier-context)",
                          }}
                        />
                      </div>
                      <span className="mono">
                        {used} / {policy.context_limit}
                      </span>
                    </button>
                    {open === c.agent_id && (
                      <div className="context-sources">
                        {c.fields?.map((f) => (
                          <div key={f.predicate}>
                            <strong>{f.predicate}</strong>
                            <span>{f.status}</span>
                            {f.claim_ids?.map((id) => (
                              <button key={id} onClick={() => onSelect(id)}>
                                ↗{" "}
                                {graph.nodes.find((n) => n.id === id)?.label ||
                                  id}
                              </button>
                            ))}
                          </div>
                        ))}
                        <details>
                          <summary>Exact observed context and unit</summary>
                          <Json value={c} />
                        </details>
                      </div>
                    )}
                  </section>
                );
              })
            ) : (
              <p>No agent has assembled a context in this scope yet.</p>
            )}
          </div>
          <div className="activity-key">
            <span>
              <i style={{ background: "var(--agent-planner)" }} />
              Instructions
            </span>
            <span>
              <i style={{ background: "var(--tier-hot)" }} />
              Traveler
            </span>
            <span>
              <i style={{ background: "var(--tier-context)" }} />
              Other framing, cards & evidence
            </span>
          </div>
          <div className="resource-empty">
            <strong>Savings vs no-memory baseline: N/A</strong>
            <p>
              No equivalent full-history prompt was captured. No token saving or
              optimization percentage is claimed.
            </p>
          </div>
        </>
      )}
      {tab === "Cache" && (
        <>
          <div className="big-metric">
            {reads.length
              ? Math.round((hits / reads.length) * 100) + "%"
              : "N/A"}
            <span>
              Context cache hit rate <Badge />
            </span>
          </div>
          <div className="resource-grid">
            <Metric
              label="Completed reads in selected window"
              value={reads.length}
            />
            <Metric label="Cache hits" value={hits} />
            <Metric
              label="Payload bytes / quota"
              value={`${bytes(data.cache.payload_bytes)} / ${bytes(data.cache.max_payload_bytes)}`}
            />
            <Metric
              label="Entries / quota"
              value={`${data.cache.entries} / ${data.cache.max_entries}`}
            />
          </div>
          <p className="truth-note">
            Context-payload cache, not NVIDIA prompt caching. Occupancy is the
            latest application-wide snapshot. Eviction reasons and cached
            provider tokens are not instrumented.
          </p>
        </>
      )}
      {tab === "Provider" && (
        <>
          <div className="resource-title">
            <h2>{data.credentials.provider}</h2>
            <Badge />
          </div>
          <div className="resource-grid">
            <Metric
              label="Observed HTTP inference requests"
              value={usage?.requests ?? "N/A"}
            />
            <Metric
              label="Successful responses"
              value={usage?.successful ?? "N/A"}
            />
            <Metric
              label="Reported input tokens"
              value={usage?.usage_responses ? usage.input_tokens : "N/A"}
            />
            <Metric
              label="Reported output tokens"
              value={usage?.usage_responses ? usage.output_tokens : "N/A"}
            />
          </div>
          <p className="truth-note">
            {usage?.scope}. Provider input/output usage is separate from
            context-packet bytes. Cache-read/cache-write token details and cost
            are not recorded.
          </p>
        </>
      )}
      {tab === "Hardware" && (
        <>
          <div className="resource-title">
            <h2>Runtime hardware</h2>
            <Badge />
          </div>
          <div className="resource-grid">
            <Metric
              label="Website process RAM"
              value={bytes(resources.ram_bytes)}
            />
            <Metric
              label="Observed device VRAM"
              value={bytes(resources.vram_bytes)}
            />
            <Metric
              label="GPU utilization"
              value={
                resources.gpu_util == null
                  ? "Not instrumented"
                  : resources.gpu_util + "%"
              }
            />
            <Metric
              label="Captured CUDA card bytes"
              value={bytes(
                graph.contexts.reduce(
                  (s, c) => s + (c.residency?.resident_bytes || 0),
                  0,
                ),
              )}
            />
          </div>
          <p className="truth-note">
            Snapshot observations, not a fabricated historical sparkline. CPU
            card matching uses no CUDA card allocation; device-wide VRAM may
            belong to other processes.
          </p>
          <details>
            <summary>Device and residency details</summary>
            <Json
              value={{
                device: resources.device,
                contexts: graph.contexts.map((c) => ({
                  agent: c.agent_id,
                  residency: c.residency,
                })),
              }}
            />
          </details>
        </>
      )}
      {tab === "Latency" && (
        <>
          <div className="resource-title">
            <h2>Observed latency</h2>
            <Badge />
          </div>
          <div className="latency-chart">
            {events
              .filter((e) => e.detail?.latency_ms != null && e.id <= event?.id)
              .slice(-18)
              .map((e) => (
                <div
                  key={e.id}
                  title={`${eventLabel(e)}: ${e.detail.latency_ms} ms`}
                >
                  <span>#{e.id}</span>
                  <i
                    style={{
                      width:
                        Math.max(
                          2,
                          Math.min(
                            100,
                            (e.detail.latency_ms /
                              Math.max(
                                1,
                                ...events.map((x) => x.detail?.latency_ms || 0),
                              )) *
                              100,
                          ),
                        ) + "%",
                      background: agentColor(e.agent_id),
                    }}
                  />
                  <b>{Math.round(e.detail.latency_ms)} ms</b>
                </div>
              ))}
          </div>
          <p className="truth-note">
            Context events measure gateway retrieval/assembly; completion events
            measure agent work. Parallel work is not summed into a fictional
            end-to-end total.
          </p>
        </>
      )}
    </div>
  );
}
function Metric({ label, value }) {
  return (
    <div className="resource-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <Badge>
        {String(value).includes("N/A") || value === "Not instrumented"
          ? "Unavailable"
          : label.includes("quota")
            ? "Measured / configured"
            : "Measured"}
      </Badge>
    </div>
  );
}
export function Dock({
  events,
  event,
  onEvent,
  playing,
  setPlaying,
  speed,
  setSpeed,
  agent,
  data,
}) {
  const index = events.findIndex((e) => e.id === event?.id),
    groups = [
      {
        name: "Planning",
        test: (id) => /orchestrator|planner/.test(id || ""),
        color: "var(--agent-planner)",
      },
      {
        name: "Research",
        test: (id) => !/orchestrator|planner|budget|support/.test(id || ""),
        color: "var(--agent-researcher)",
      },
      {
        name: "Review",
        test: (id) => /budget|support/.test(id || ""),
        color: "var(--agent-reviewer)",
      },
    ],
    chapters = [
      ...[
        "memory_submitted",
        "context_assembled",
        "context_validated",
        "agent_completed",
      ]
        .map((k, i) => ({
          index: events.findIndex((e) => e.kind === k),
          name: ["Intake", "Recall", "Validation", "Agent results"][i],
        }))
        .filter((c) => c.index >= 0),
      { index: events.length - 1, name: "Latest" },
    ];
  return (
    <section className="live-dock" aria-label="Event timeline">
      <div className="live-transport">
        <div>
          <button
            aria-label="Previous event"
            disabled={index <= 0}
            onClick={() => onEvent(events[index - 1].id)}
          >
            <ChevronLeftIcon />
          </button>
          <button
            aria-label={playing ? "Pause replay" : "Play replay"}
            onClick={() => setPlaying(!playing)}
          >
            {playing ? <PauseIcon /> : <PlayIcon />}
            {playing ? "Pause" : "Play"}
          </button>
          <button
            aria-label="Next event"
            disabled={index < 0 || index >= events.length - 1}
            onClick={() => onEvent(events[index + 1].id)}
          >
            <ChevronRightIcon />
          </button>
          <select
            aria-label="Playback speed"
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          >
            {[0.5, 1, 2, 4].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
          <button
            aria-label="Reset replay"
            onClick={() => events[0] && onEvent(events[0].id)}
          >
            <ResetIcon />
            Reset
          </button>
        </div>
        <span className="current-event-text">
          {glyph(event?.kind)} {eventLabel(event)}
        </span>
        <span className="mono" data-testid="live-cursor">
          {Math.max(0, index + 1)} / {events.length}
        </span>
      </div>
      <div className="live-timeline-lanes">
        {groups.map((g) => (
          <div className="live-lane" key={g.name}>
            <span>
              <i style={{ background: g.color }} />
              {g.name}
            </span>
            <div style={{ "--columns": Math.max(1, events.length) }}>
              {events.map((e) =>
                g.test(e.agent_id) ? (
                  <button
                    key={e.id}
                    aria-label={`Timeline event ${e.id}: ${eventLabel(e)}`}
                    title={`#${e.id} ${time(e.timestamp)} ${eventLabel(e)}`}
                    className={`${event?.id === e.id ? "selected" : ""} ${isConflict(e) ? "conflict" : ""}`}
                    style={{
                      background: isConflict(e)
                        ? "var(--state-conflict)"
                        : g.color,
                      opacity:
                        agent && agent !== e.agent_id
                          ? 0.2
                          : e.id > (event?.id || 0)
                            ? 0.35
                            : 0.7,
                    }}
                    onClick={() => onEvent(e.id)}
                  >
                    {isConflict(e) && <span>! Conflict</span>}
                  </button>
                ) : (
                  <i key={e.id} />
                ),
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="live-axis">
        <span className="mono">
          {data.observations.retained_from > 1 ? "Retained window" : "UTC"}
        </span>
        <div>
          <input
            type="range"
            aria-label="Replay position"
            min="0"
            max={Math.max(0, events.length - 1)}
            value={Math.max(0, index)}
            onChange={(e) =>
              events[Number(e.target.value)] &&
              onEvent(events[Number(e.target.value)].id)
            }
          />
          <div className="chapter-markers">
            {chapters.map((c, i) => (
              <button
                key={i}
                style={{
                  left: `${(c.index / Math.max(1, events.length - 1)) * 100}%`,
                }}
                title={`${c.name} · event ${events[c.index]?.id}`}
                onClick={() => events[c.index] && onEvent(events[c.index].id)}
              >
                {c.name}
              </button>
            ))}
          </div>
          <div className="time-labels">
            <span>{time(events[0]?.timestamp)}</span>
            <span>{time(event?.timestamp)}</span>
            <span>{time(events.at(-1)?.timestamp)}</span>
          </div>
        </div>
      </div>
    </section>
  );
}
