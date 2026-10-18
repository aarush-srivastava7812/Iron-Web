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
  lastCapturedCardBytes,
} from "./liveData.js";
import { Badge, Json } from "./LivePanels.jsx";
import {
  RingChart,
  Gauge,
  ChartLegend,
  MemoryPlot,
  LatencyPlot,
  CHART_COLORS,
  formatNumber,
  percent,
} from "./ResourceCharts.jsx";

export function Resources({ data, graph, event, onSelect, events }) {
  const [tab, setTab] = useState("Context"),
    [open, setOpen] = useState(null);
  const unit = contextUnit(data),
    policy = data.tiers.policy;
  const reads = events.filter(
    (e) => e.kind === "context_assembled" && e.id <= event?.id,
  );
  const hits = reads.filter((e) => e.detail?.cache_hit).length;
  const usage = data.credentials.usage,
    resources = data.resources || {};
  const reported = usage?.usage_responses > 0;
  const tokenTotal = reported ? usage.input_tokens + usage.output_tokens : null;
  const cacheRatio = percent(hits, reads.length);
  return (
    <div className="live-resources resource-gallery">
      <div className="resource-tabs">
        {["Context", "Cache", "Provider", "Hardware", "Latency"].map((t) => (
          <button aria-pressed={tab === t} key={t} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="resource-title">
        <div>
          <span className="kicker">Memory observatory</span>
          <h2>
            {
              {
                Context: "Context X-ray",
                Cache: "Context reuse",
                Provider: data.credentials.provider,
                Hardware: "Runtime hardware",
                Latency: "Observed latency",
              }[tab]
            }
          </h2>
        </div>
        <Badge />
      </div>
      {tab === "Context" && (
        <>
          <p className="chart-intro">
            The shape of each agent's context. Select a ring to follow its
            sources.
          </p>
          <div className="context-orbits">
            {graph.contexts.length ? (
              graph.contexts.map((c) => {
                const used = c.tokens?.prompt,
                  instructions = c.tokens?.agent || 0,
                  traveler = c.tokens?.traveller || 0;
                const segments = [
                  {
                    label: "Instructions",
                    value: instructions,
                    color: CHART_COLORS[2],
                  },
                  {
                    label: "Traveler",
                    value: traveler,
                    color: CHART_COLORS[1],
                  },
                  {
                    label: "Other framing, cards & evidence",
                    value: Math.max(0, (used || 0) - instructions - traveler),
                    color: CHART_COLORS[0],
                  },
                ];
                return (
                  <section
                    className={`context-orbit ${open === c.agent_id ? "expanded" : ""}`}
                    key={c.agent_id}
                  >
                    <button
                      className="context-orbit-button"
                      aria-expanded={open === c.agent_id}
                      onClick={() =>
                        setOpen(open === c.agent_id ? null : c.agent_id)
                      }
                    >
                      <RingChart
                        small
                        segments={segments}
                        total={policy.context_limit}
                        value={percent(used, policy.context_limit)}
                        label="of limit"
                      />
                      <div>
                        <span
                          className="orbit-agent"
                          style={{ color: agentColor(c.agent_id) }}
                        >
                          {agentName(c.agent_id)}
                        </span>
                        <strong className="mono">
                          {formatNumber(used)}{" "}
                          <small>/ {formatNumber(policy.context_limit)}</small>
                        </strong>
                        <span className="orbit-unit">{unit}</span>
                        <span className="orbit-action">
                          {open === c.agent_id
                            ? "Close sources"
                            : "Inspect sources"}{" "}
                          ↗
                        </span>
                      </div>
                    </button>
                    {open === c.agent_id && (
                      <div className="context-sources">
                        <ChartLegend
                          rows={segments.map((s) => ({
                            ...s,
                            value: formatNumber(s.value),
                          }))}
                        />
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
              <div className="chart-empty">
                No agent has assembled a context in this scope yet.
              </div>
            )}
          </div>
          <div className="chart-inline-legend">
            {[
              "Instructions",
              "Traveler",
              "Other framing, cards & evidence",
            ].map((label, i) => (
              <span key={label}>
                <i
                  style={{
                    background: [
                      CHART_COLORS[2],
                      CHART_COLORS[1],
                      CHART_COLORS[0],
                    ][i],
                  }}
                />
                {label}
              </span>
            ))}
            <span>Unfilled ring = remaining budget</span>
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
          <p className="chart-intro">
            Reuse in the selected event window, with current cache occupancy
            alongside it.
          </p>
          <div className="chart-composition cache-composition">
            <section className="chart-panel primary-chart">
              <h3>Context cache hit rate</h3>
              <RingChart
                segments={[
                  { label: "Cache hits", value: hits, color: CHART_COLORS[0] },
                  {
                    label: "Reads without a cache hit",
                    value: reads.length - hits,
                    color: CHART_COLORS[1],
                  },
                ]}
                total={reads.length}
                value={cacheRatio}
                label="cache hits"
              />
              <ChartLegend
                rows={[
                  { label: "Cache hits", value: hits, color: CHART_COLORS[0] },
                  {
                    label: "Reads without a cache hit",
                    value: reads.length - hits,
                    color: CHART_COLORS[1],
                  },
                  {
                    label: "Completed reads in selected window",
                    value: reads.length,
                    color: "var(--ui-text)",
                  },
                ]}
              />
            </section>
            <div className="quota-stack">
              <section className="chart-panel quota-panel">
                <Gauge
                  value={data.cache.payload_bytes}
                  total={data.cache.max_payload_bytes}
                  label="payload quota"
                  color={CHART_COLORS[2]}
                />
                <h3>Payload bytes / quota</h3>
                <p className="mono">
                  {bytes(data.cache.payload_bytes)}{" "}
                  <span>/ {bytes(data.cache.max_payload_bytes)}</span>
                </p>
              </section>
              <section className="chart-panel quota-panel">
                <Gauge
                  value={data.cache.entries}
                  total={data.cache.max_entries}
                  label="entry quota"
                  color={CHART_COLORS[3]}
                />
                <h3>Entries / quota</h3>
                <p className="mono">
                  {formatNumber(data.cache.entries)}{" "}
                  <span>/ {formatNumber(data.cache.max_entries)}</span>
                </p>
              </section>
            </div>
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
          <p className="chart-intro">
            Reported token composition and observed responses from the provider.
          </p>
          <div className="chart-composition provider-composition">
            <section className="chart-panel primary-chart">
              <h3>Reported token composition</h3>
              <RingChart
                total={tokenTotal}
                value={reported ? formatNumber(tokenTotal) : "N/A"}
                label="total tokens"
                segments={
                  reported
                    ? [
                        {
                          label: "Input",
                          value: usage.input_tokens,
                          color: CHART_COLORS[2],
                        },
                        {
                          label: "Output",
                          value: usage.output_tokens,
                          color: CHART_COLORS[1],
                        },
                      ]
                    : []
                }
              />
              <ChartLegend
                rows={[
                  {
                    label: "Reported input tokens",
                    value: reported ? formatNumber(usage.input_tokens) : "N/A",
                    color: CHART_COLORS[2],
                  },
                  {
                    label: "Reported output tokens",
                    value: reported ? formatNumber(usage.output_tokens) : "N/A",
                    color: CHART_COLORS[1],
                  },
                ]}
              />
            </section>
            <section className="chart-panel response-chart">
              <h3>Successful responses</h3>
              <Gauge
                value={usage?.successful}
                total={usage?.requests}
                label="response success"
              />
              <ChartLegend
                rows={[
                  {
                    label: "Observed HTTP inference requests",
                    value: formatNumber(usage?.requests),
                    color: "var(--ui-text)",
                  },
                  {
                    label: "Successful responses",
                    value: formatNumber(usage?.successful),
                    color: CHART_COLORS[0],
                  },
                ]}
              />
            </section>
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
          <p className="chart-intro">
            Current memory observations on a shared byte scale. Each reading has
            a different scope.
          </p>
          <section className="chart-panel">
            <h3>Memory residency</h3>
            <MemoryPlot
              rows={[
                { label: "Website process RAM", value: resources.ram_bytes },
                { label: "Observed device VRAM", value: resources.vram_bytes },
                {
                  label: "Last captured CUDA card allocation",
                  value: lastCapturedCardBytes(graph.contexts),
                },
              ]}
            />
          </section>
          <section className="hardware-status">
            <span className="status-glyph">◇</span>
            <div>
              <h3>GPU utilization</h3>
              <p>
                {resources.gpu_util == null
                  ? "Not instrumented"
                  : resources.gpu_util + "%"}
              </p>
            </div>
            <Badge>
              {resources.gpu_util == null ? "Unavailable" : "Measured"}
            </Badge>
          </section>
          <p className="truth-note">
            Snapshot observations, not a fabricated historical sparkline. CPU
            card matching uses no CUDA card allocation; device-wide VRAM may
            belong to other processes. Captures can share an allocation; they
            are not summed across agents. Missing captures are unavailable.
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
          <p className="chart-intro">
            Every point is an observed operation. Select a point for its exact
            measurement.
          </p>
          <section className="chart-panel">
            <h3>Operation latency</h3>
            <LatencyPlot events={events.filter((e) => e.id <= event?.id)} />
          </section>
          <div className="chart-inline-legend">
            {["Planning", "Research", "Review"].map((label, i) => (
              <span key={label}>
                <i
                  style={{
                    background: [
                      "var(--agent-planner)",
                      "var(--agent-researcher)",
                      "var(--agent-reviewer)",
                    ][i],
                  }}
                />
                {label}
              </span>
            ))}
          </div>
          <p className="truth-note">
            Context events measure gateway retrieval/assembly; completion events
            measure agent work. Parallel work is not summed into a fictional
            end-to-end total. Event order is evenly spaced; it does not
            represent elapsed time between operations.
          </p>
        </>
      )}
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
