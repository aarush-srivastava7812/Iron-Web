import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Cross2Icon } from "@radix-ui/react-icons";
import {
  COLORS,
  agentColor,
  agentName,
  glyph,
  time,
  pretty,
  isConflict,
  contextUnit,
  eventLabel,
} from "./liveData.js";
import { TierMeter } from "./ResourceCharts.jsx";
export { Resources, Dock } from "./LiveResources.jsx";
export function Badge({ children = "Measured", kind = "measured" }) {
  return <span className={`source-badge ${kind}`}>{children}</span>;
}
export function ViewHeader({ kicker, title, subtitle, children }) {
  return (
    <header className="live-view-header">
      <div>
        <span className="kicker">{kicker}</span>
        <h1>{title}</h1>
        <span className="view-subtitle">{subtitle}</span>
      </div>
      {children}
    </header>
  );
}
export function Json({ value }) {
  return <pre className="live-json">{pretty(value ?? null)}</pre>;
}
export function Inspector({
  data,
  node,
  graph,
  tier,
  follow,
  event,
  onEvent,
  onSelect,
  onFollow,
}) {
  const [tab, setTab] = useState("Diff");
  const p = node?.raw?.properties || {},
    linked = graph.edges.filter(
      (e) => e.source === node?.id || e.target === node?.id,
    ),
    history = (data.observations.events || []).filter(
      (e) =>
        e.context?.claim_ids?.includes(node?.id) ||
        (e.detail?.memory_id && e.detail.memory_id === p.memory_id) ||
        (node?.context && e.agent_id === node.agent_id),
    );
  const packet = event?.context || node?.context,
    fields =
      packet?.fields?.filter((f) => f.claim_ids?.includes(node?.id)) || [];
  let value;
  try {
    value = JSON.parse(p.value_json);
  } catch {
    value = p.value_json;
  }
  return (
    <>
      <header className="inspector-sticky">
        <span className="kicker">
          {tier ? "Tier inspector" : "Memory inspector"}
        </span>
        <button className={follow ? "following" : ""} onClick={onFollow}>
          {follow ? "● Following live" : "○ Selection pinned"}
        </button>
        <h2>
          {tier
            ? tier === "hot"
              ? "Hot context"
              : tier === "context"
                ? "Context cards"
                : "Durable evidence"
            : node?.label || "Current event"}
        </h2>
        <p className="mono full-id">
          {tier
            ? data.tiers.layers.find(
                (l) =>
                  ({ 1: "hot", 2: "context", 3: "durable" })[l.tier] === tier,
              )?.storage
            : node?.id || "Select a memory to inspect its provenance"}
        </p>
        {(node || tier) && (
          <span
            className="tier-badge"
            style={{ color: COLORS[tier || node.tier] }}
          >
            ◇ {(tier || node.tier).toUpperCase()}
          </span>
        )}
      </header>
      {tier ? (
        <div className="inspector-scroll">
          <p>
            {
              data.tiers.layers.find(
                (l) =>
                  ({ 1: "hot", 2: "context", 3: "durable" })[l.tier] === tier,
              )?.description
            }
          </p>
          {graph.nodes
            .filter((n) => n.tier === tier)
            .map((n) => (
              <button
                className="inspector-link"
                key={n.id}
                onClick={() => onSelect(n.id)}
              >
                {n.label}
                <small>{n.id}</small>
              </button>
            ))}
        </div>
      ) : (
        <>
          <div className="inspector-meta">
            <span style={{ color: agentColor(event?.agent_id) }}>
              {agentName(event?.agent_id)}
            </span>
            <span>
              {glyph(event?.kind)}{" "}
              {event?.kind?.replaceAll("_", " ") || "Waiting"}
            </span>
            <span className="mono">
              #{event?.id || "—"} · {time(event?.timestamp)}
            </span>
          </div>
          <div
            className="inspector-tabs"
            role="tablist"
            aria-label="Inspector views"
          >
            {["Diff", "History", "Links"].map((t) => (
              <button
                role="tab"
                aria-selected={tab === t}
                key={t}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="inspector-scroll">
            {tab === "Diff" && (
              <>
                <div className="section-label">
                  {node?.raw
                    ? "CURRENT STORED VALUE"
                    : node?.card
                      ? "OBSERVED CARD"
                      : "OBSERVED CONTEXT"}{" "}
                  <Badge />
                </div>
                {node?.raw ? (
                  <Json value={value ?? p} />
                ) : node?.card ? (
                  <Json value={node.card} />
                ) : node?.context ? (
                  <Json
                    value={{
                      agent: node.context.agent_text,
                      traveler: node.context.traveller_text,
                      claims: node.context.claim_ids,
                    }}
                  />
                ) : (
                  <Json value={event?.detail} />
                )}
                {event?.detail?.changes?.length > 0 && (
                  <>
                    <div className="section-label">COMMITTED CHANGES</div>
                    {event.detail.changes.map((c, i) => (
                      <div className="actual-diff" key={i}>
                        <strong>{c.predicate}</strong>
                        {"before" in c ? (
                          <pre className="removed">− {pretty(c.before)}</pre>
                        ) : (
                          <p>Before value was not captured for this event.</p>
                        )}
                        <pre className="added">+ {pretty(c.after)}</pre>
                        <span>
                          {c.action} · source receipt {event.detail.event_id}
                        </span>
                      </div>
                    ))}
                  </>
                )}
                {isConflict(event) && (
                  <p className="conflict-message">
                    !{" "}
                    {event.detail?.valid === false
                      ? "Context changed; the application must validate again."
                      : "Read or validation requires attention."}
                  </p>
                )}
                {fields.map((f) => (
                  <details key={f.predicate}>
                    <summary>Why this field was used · {f.predicate}</summary>
                    <Json
                      value={{
                        status: f.status,
                        scopes: f.scopes,
                        source_event_ids: f.source_event_ids,
                        claim_ids: f.claim_ids,
                      }}
                    />
                  </details>
                ))}
                <p className="truth-note">
                  The graph and stored value are the latest live snapshot. Event
                  replay uses captured contexts; missing historical before
                  values are never reconstructed.
                </p>
              </>
            )}
            {tab === "History" && (
              <>
                {history.length ? (
                  history.map((e) => (
                    <button
                      key={e.id}
                      className={`history-item ${e.id === event?.id ? "selected" : ""}`}
                      onClick={() => onEvent(e.id)}
                    >
                      <span>
                        {glyph(e.kind)} {eventLabel(e)}
                      </span>
                      <small>
                        #{e.id} · {time(e.timestamp)}
                      </small>
                    </button>
                  ))
                ) : (
                  <p>
                    No matching activity in the retained observation window.
                  </p>
                )}
                <details>
                  <summary>Current event payload</summary>
                  <Json value={event} />
                </details>
              </>
            )}
            {tab === "Links" && (
              <>
                <p>{linked.length} actual or source-derived relationships</p>
                {linked.map((e) => {
                  const id = e.source === node?.id ? e.target : e.source;
                  return (
                    <button
                      className="inspector-link"
                      key={e.id}
                      onClick={() => onSelect(id)}
                    >
                      <span>{e.relation}</span>
                      <small>
                        {graph.nodes.find((n) => n.id === id)?.label || id}
                      </small>
                    </button>
                  );
                })}
                {fields
                  .flatMap((f) => f.source_event_ids || [])
                  .map((id) => (
                    <p className="mono full-id" key={id}>
                      Receipt {id}
                    </p>
                  ))}
              </>
            )}
          </div>
        </>
      )}
    </>
  );
}
export function Wiring({ agents, event, agent, onAgent, onStore }) {
  const reduced = useReducedMotion(),
    height = Math.max(420, agents.length * 44 + 70),
    active = event?.agent_id;
  return (
    <div className="live-wiring">
      <svg
        viewBox={`0 0 900 ${height}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="All real agents and their memory tools"
      >
        <text x="20" y="24" className="svg-kicker">
          AGENTS
        </text>
        <text x="365" y="24" className="svg-kicker">
          MEMORY STORE
        </text>
        <text x="700" y="24" className="svg-kicker">
          MEMORY TOOLS
        </text>
        {agents.map((a, i) => {
          const y = 60 + i * 44,
            d = `M 200 ${y} C 290 ${y} 270 ${height / 2} 355 ${height / 2}`;
          return (
            <g
              key={a.agent_id}
              opacity={!agent || agent === a.agent_id ? 1 : 0.2}
            >
              <path
                d={d}
                fill="none"
                stroke={agentColor(a.agent_id)}
                strokeWidth="1.5"
                opacity=".4"
              />
              {active === a.agent_id && !reduced && (
                <motion.path
                  key={event.id}
                  d={d}
                  fill="none"
                  stroke={agentColor(a.agent_id)}
                  strokeWidth="2"
                  strokeDasharray="8 14"
                  initial={{ strokeDashoffset: 45, opacity: 1 }}
                  animate={{ strokeDashoffset: 0, opacity: 0 }}
                  transition={{ duration: 1.1 }}
                />
              )}
              <g
                role="button"
                tabIndex="0"
                aria-label={`Filter ${agentName(a.agent_id)}`}
                onClick={() => onAgent(a.agent_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onAgent(a.agent_id);
                }}
              >
                <rect
                  x="20"
                  y={y - 16}
                  width="180"
                  height="32"
                  rx="0"
                  fill="var(--ui-raised)"
                  stroke={agentColor(a.agent_id)}
                />
                <text x="32" y={y + 4} className="svg-title">
                  {agentName(a.agent_id)} · {a.reads_in_window}
                </text>
              </g>
            </g>
          );
        })}
        <g
          role="button"
          tabIndex="0"
          aria-label="Explore shared memory"
          onClick={onStore}
          onKeyDown={(e) => e.key === "Enter" && onStore()}
        >
          <rect
            x="355"
            y={height / 2 - 40}
            width="180"
            height="80"
            rx="0"
            fill="var(--ui-raised)"
            stroke="var(--tier-evidence)"
          />
          <text
            x="445"
            y={height / 2 - 3}
            textAnchor="middle"
            className="svg-title"
          >
            Shared memory
          </text>
          <text
            x="445"
            y={height / 2 + 19}
            textAnchor="middle"
            className="svg-kicker"
          >
            FALKORDB + QDRANT
          </text>
        </g>
        {["Read context", "Commit intake", "Forget source"].map((label, i) => {
          const y = height / 2 + (i - 1) * 110;
          const d = `M 535 ${height / 2} C 610 ${height / 2} 610 ${y} 700 ${y}`;
          const acting =
            label === "Read context"
              ? /context/.test(event?.kind)
              : label === "Commit intake"
                ? /memory_processed/.test(event?.kind)
                : /forget/.test(event?.kind);
          return (
            <g key={label}>
              <path
                d={d}
                fill="none"
                stroke={acting ? agentColor(active) : "var(--ui-secondary)"}
                strokeWidth="1.5"
                strokeDasharray="5 6"
                opacity=".5"
              />
              {acting && !reduced && (
                <motion.path
                  key={event.id}
                  d={d}
                  fill="none"
                  stroke={agentColor(active)}
                  strokeWidth="2"
                  initial={{ pathLength: 0, opacity: 1 }}
                  animate={{ pathLength: 1, opacity: 0 }}
                  transition={{ duration: 1 }}
                />
              )}
              <rect
                x="700"
                y={y - 22}
                width="175"
                height="44"
                rx="0"
                fill="var(--ui-raised)"
                stroke="var(--ui-border)"
              />
              <text x="787" y={y + 4} textAnchor="middle" className="svg-title">
                {label}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="truth-note">
        Lines connect registered agents to the shared service; a pulse
        represents the selected observed event.
      </p>
    </div>
  );
}
export function Activity({ agents, events, event, agent, onEvent }) {
  const visible = events.slice(-100),
    rows = [{ agent_id: null }, ...agents];
  return (
    <div className="live-activity">
      <div className="activity-key">
        {["travel_orchestrator", "explore_agent", "budget_booking_agent"].map(
          (id, i) => (
            <span key={id}>
              <i style={{ background: agentColor(id) }} />
              {["Planning", "Research", "Review"][i]}
            </span>
          ),
        )}
        <span>
          <i style={{ background: "var(--state-conflict)" }} />! Conflict /
          failure
        </span>
      </div>
      <div
        className="live-heatmap"
        style={{ "--event-columns": Math.max(1, visible.length) }}
      >
        {rows.map((a) => (
          <div className="live-heatmap-row" key={a.agent_id || "app"}>
            <span>{agentName(a.agent_id)}</span>
            <div>
              {visible.map((e) => (
                <button
                  key={e.id}
                  disabled={e.agent_id !== a.agent_id}
                  className={`${e.agent_id === a.agent_id ? "filled" : ""} ${event?.id === e.id ? "selected" : ""}`}
                  style={{
                    "--event-color": isConflict(e)
                      ? "var(--state-conflict)"
                      : agentColor(e.agent_id),
                    opacity: agent && e.agent_id !== agent ? 0.2 : 1,
                  }}
                  aria-label={`Inspect event ${e.id}: ${eventLabel(e)}`}
                  title={`#${e.id} ${eventLabel(e)} ${time(e.timestamp)}`}
                  onClick={() => onEvent(e.id)}
                >
                  {e.agent_id === a.agent_id
                    ? isConflict(e)
                      ? "!"
                      : glyph(e.kind)
                    : ""}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="truth-note">
        {visible.length} most recent events shown · {events.length} retained ·
        click a cell to replay its observation.
      </p>
      <div className="selected-event-summary">
        <span className="mono">#{event?.id}</span>
        {eventLabel(event)}
        <Badge />
      </div>
    </div>
  );
}
export function Architecture({ data, graph, onTier, selectedTier }) {
  return (
    <div className="live-architecture">
      {Object.entries(COLORS).map(([t, color], i) => {
        const contexts = graph.contexts,
          policy = data.tiers.policy;
        const amount =
          t === "hot"
            ? contexts.reduce(
                (s, c) =>
                  s + (c.tokens?.agent || 0) + (c.tokens?.traveller || 0),
                0,
              )
            : t === "context"
              ? contexts.reduce((s, c) => s + (c.cards?.length || 0), 0)
              : data.storage.memories;
        const limit =
          t === "hot"
            ? contexts.length * policy.half_tokens * 2
            : t === "context"
              ? contexts.length * policy.max_cards
              : null;
        return (
          <section
            key={t}
            style={{ "--tier-color": color }}
            className={selectedTier === t ? "selected" : ""}
          >
            <button onClick={() => onTier(t)} aria-label={`Inspect ${t} tier`}>
              <span className="tier-index mono">0{i + 1}</span>
              <span>
                <strong>{data.tiers.layers[i].name}</strong>
                <small>{data.tiers.layers[i].storage}</small>
              </span>
              <span className="tier-amount mono">
                {amount.toLocaleString()}{" "}
                {t === "hot"
                  ? contextUnit(data)
                  : t === "context"
                    ? "cards"
                    : "memories"}
                <Badge />
              </span>
            </button>
            <p>{data.tiers.layers[i].description}</p>
            {limit != null ? (
              <>
                <TierMeter value={amount} total={limit} color={color} />
                <div className="tier-caption">
                  {amount} / {limit}{" "}
                  {t === "hot"
                    ? "observed hot allocation"
                    : "configured card slots across captured contexts"}
                </div>
              </>
            ) : (
              <div className="tier-caption">
                Durable byte quota: N/A ·{" "}
                {graph.nodes.filter((n) => n.raw).length} KG nodes on this page
              </div>
            )}
            {selectedTier === t && (
              <div className="tier-caption">
                Selected · memory contents are available in the inspector.
                Promotion/eviction event instrumentation is not available.
              </div>
            )}
          </section>
        );
      })}
      <p className="truth-note">
        Hot context and cards are derived views, not independent copies of
        authoritative facts. Cache quota is shown under Resources.
      </p>
    </div>
  );
}
export function Dialog({ name, data, onClose }) {
  const ref = useRef(null);
  const [vector, setVector] = useState(null),
    [vectorError, setVectorError] = useState(""),
    [vectorLoading, setVectorLoading] = useState(false);
  async function loadVector() {
    setVectorLoading(true);
    setVectorError("");
    try {
      const base = (import.meta.env.VITE_DASHBOARD_API_URL || "").replace(
        /\/$/,
        "",
      );
      const response = await fetch(
        base + "/api/dashboard/vectors?include_values=true&limit=1",
        { cache: "no-store", credentials: "include" },
      );
      if (!response.ok) throw new Error("Vector inspection unavailable");
      setVector(await response.json());
    } catch (error) {
      setVectorError(error.message);
    } finally {
      setVectorLoading(false);
    }
  }
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="live-dialog"
      onCancel={onClose}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <header>
        <h2>
          {name === "help" ? "Dashboard shortcuts" : "Live memory connection"}
        </h2>
        <button aria-label="Close dialog" onClick={onClose}>
          <Cross2Icon />
        </button>
      </header>
      {name === "help" ? (
        <div>
          <p>Space · play/pause · arrows · previous/next event</p>
          <p>1–5 · switch views · F · toggle follow-live</p>
          <p>/ · find memory · Esc · close panels/clear selection</p>
          <p>
            Click a memory, activity cell, history row or timeline marker to
            inspect its actual source.
          </p>
        </div>
      ) : (
        <div>
          <p>
            Read-only relay → website memory owner → FalkorDB, embedded Qdrant
            and SQLite journal.
          </p>
          <p className="mono full-id">
            Scope: {data.scope} · trip:{" "}
            {data.trip_id || "all trips for the published traveler"}
          </p>
          <Json value={data.databases} />
          <details>
            <summary>Store counts and page limits</summary>
            <Json
              value={{
                storage: data.storage,
                graph: {
                  displayed: data.graph.nodes.length,
                  truncated: data.graph.truncated,
                  next_offset: data.graph.next_offset,
                  edges_truncated: data.graph.edges_truncated,
                },
              }}
            />
          </details>
          <details>
            <summary>
              Qdrant point payloads · {data.vectors.points.length} on this page
            </summary>
            <Json value={data.vectors} />
            <button onClick={loadVector} disabled={vectorLoading}>
              {vectorLoading ? "Loading vector…" : "Inspect numeric vector"}
            </button>
            {vectorError && <p role="status">{vectorError}</p>}
            {vector && <Json value={vector} />}
          </details>
          <details>
            <summary>
              SQLite receipt journal · {data.receipts.length} recent receipts
            </summary>
            <Json value={data.receipts} />
          </details>
          <h3>Provider and credential identity</h3>
          <Json value={data.credentials} />
          <p className="truth-note">
            Only masked credential identity is exposed. This browser never
            receives the publication grant or full API key.{" "}
            {data.notes?.join(" ")}
          </p>
        </div>
      )}
    </dialog>
  );
}
