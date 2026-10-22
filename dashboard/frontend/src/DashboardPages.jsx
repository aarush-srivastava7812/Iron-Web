import { useEffect, useState } from "react";
import {
  ArrowRightIcon,
  DashboardIcon,
  Share1Icon,
  Component1Icon,
  ActivityLogIcon,
  StackIcon,
  BarChartIcon,
} from "@radix-ui/react-icons";
import { PAGES } from "./dashboardRoutes.js";
import { agentName, eventLabel, time, isConflict } from "./liveData.js";

const ICONS = {
  overview: DashboardIcon,
  graph: Share1Icon,
  agents: Component1Icon,
  activity: ActivityLogIcon,
  architecture: StackIcon,
  resources: BarChartIcon,
  history: ActivityLogIcon,
  tinyfish: Share1Icon,
};

export function PageLink({ page, hrefFor, navigate, children, ...props }) {
  return (
    <a
      href={hrefFor(page)}
      onClick={(event) => {
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        )
          return;
        event.preventDefault();
        navigate(page);
      }}
      {...props}
    >
      {children}
    </a>
  );
}

export function PageNavigation({ current, hrefFor, navigate }) {
  return (
    <nav className="dashboard-nav" aria-label="Dashboard pages">
      {Object.entries(PAGES).map(([id, page]) => {
        const Icon = ICONS[id];
        return (
          <PageLink
            key={id}
            page={id}
            hrefFor={hrefFor}
            navigate={navigate}
            aria-current={current === id ? "page" : undefined}
          >
            <Icon aria-hidden="true" />
            <span>{page.name}</span>
          </PageLink>
        );
      })}
    </nav>
  );
}

export function Overview({
  data,
  graph,
  events,
  status,
  hrefFor,
  navigate,
  onEvent,
}) {
  const reads = events.filter((e) => e.kind === "context_assembled");
  const hits = reads.filter((e) => e.detail?.cache_hit).length;
  const metrics = [
    [
      data.storage.memories ?? "—",
      "Stored memories",
      "Durable records in the published scope",
      "graph",
    ],
    [
      `${data.agents.observed} / ${data.agents.registered}`,
      "Agents observed",
      "Observed activity / registered agents",
      "agents",
    ],
    [
      events.length,
      "Retained events",
      "The current observation window",
      "activity",
    ],
    [
      reads.length ? `${Math.round((hits / reads.length) * 100)}%` : "N/A",
      "Context cache hits",
      `${hits} hits across ${reads.length} recorded reads`,
      "resources",
    ],
  ];
  return (
    <div className="overview-page">
      <TinyFishIntelligence
        data={data}
        compact
        hrefFor={hrefFor}
        navigate={navigate}
      />
      {data.connection && (
        <section
          className="website-summary"
          aria-label="Connected travel website"
        >
          <div>
            <span className="kicker">
              {data.replay
                ? "Saved project example"
                : "Connected travel website"}
            </span>
            <h2>{data.connection.username}</h2>
            <p>
              {data.replay
                ? "Historical project replay. These are not your account totals."
                : "Live data from your signed-in Voyara account."}
            </p>
          </div>
          {!data.replay && (
            <dl>
              <div>
                <dt>Trips</dt>
                <dd>{data.travel?.conversations ?? 0}</dd>
              </div>
              <div>
                <dt>Messages</dt>
                <dd>{data.travel?.messages ?? 0}</dd>
              </div>
              <div>
                <dt>Bookings</dt>
                <dd>{data.travel?.bookings ?? 0}</dd>
              </div>
              <div>
                <dt>Saved itineraries</dt>
                <dd>{data.travel?.itineraries ?? 0}</dd>
              </div>
            </dl>
          )}
          {data.website_url && (
            <a
              href={data.website_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open travel website <ArrowRightIcon />
            </a>
          )}
        </section>
      )}
      {data.history_error && <p role="alert">{data.history_error}</p>}
      <div
        className="overview-metrics"
        aria-label={data.replay ? "Saved replay totals" : "Live memory totals"}
      >
        {metrics.map(([value, label, note, page]) => (
          <PageLink
            key={label}
            page={page}
            hrefFor={hrefFor}
            navigate={navigate}
          >
            <span>
              {label}
              <ArrowRightIcon aria-hidden="true" />
            </span>
            <strong>{value.toLocaleString()}</strong>
            <small>{note}</small>
          </PageLink>
        ))}
      </div>
      <div className="overview-grid">
        <section
          className="overview-section recent-work"
          aria-labelledby="recent-work-title"
        >
          <div className="overview-section-heading">
            <div>
              <span className="kicker">Observation window</span>
              <h2 id="recent-work-title">Recent activity</h2>
            </div>
            <PageLink page="activity" hrefFor={hrefFor} navigate={navigate}>
              View all <ArrowRightIcon aria-hidden="true" />
            </PageLink>
          </div>
          {events.length ? (
            <ol className="recent-events">
              {events
                .slice(-6)
                .reverse()
                .map((e) => (
                  <li key={e.id}>
                    <button
                      onClick={() => {
                        onEvent(e.id);
                        navigate("activity");
                      }}
                    >
                      <span
                        className={`event-dot ${isConflict(e) ? "attention" : ""}`}
                        aria-hidden="true"
                      />
                      <span>
                        <strong>{eventLabel(e)}</strong>
                        <small>
                          {agentName(e.agent_id)} · Event #{e.id}
                        </small>
                      </span>
                      <time>{time(e.timestamp)} UTC</time>
                      <ArrowRightIcon aria-hidden="true" />
                    </button>
                  </li>
                ))}
            </ol>
          ) : (
            <p className="page-empty">
              No events have been recorded in this scope yet. New observations
              will appear here automatically.
            </p>
          )}
        </section>
        <section
          className="overview-section memory-map"
          aria-labelledby="memory-map-title"
        >
          <span className="kicker">Three connected layers</span>
          <h2 id="memory-map-title">Follow a memory</h2>
          <p>
            Start with the stored evidence. See what was retrieved and what
            reached the agent.
          </p>
          <ol className="memory-steps">
            <li>
              <span>01</span>
              <div>
                <strong>Durable evidence</strong>
                <p>
                  {data.graph.nodes.length} graph nodes on this page
                  {data.graph.truncated ? " · more available in storage" : ""}
                </p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Retrieved context</strong>
                <p>{graph.contexts.length} captured agent contexts</p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Agent decisions</strong>
                <p>Inspect the context attached to a recorded event.</p>
              </div>
            </li>
          </ol>
          <PageLink
            page="graph"
            hrefFor={hrefFor}
            navigate={navigate}
            className="primary-page-link"
          >
            Explore memory graph <ArrowRightIcon aria-hidden="true" />
          </PageLink>
        </section>
      </div>
      <div className="overview-footnote">
        <span>
          <i className={status === "live" ? "live-dot" : "stale-dot"} />{" "}
          {status === "live"
            ? "Receiving live snapshots"
            : status === "history"
              ? "Showing saved project replay"
              : "Showing the last received snapshot"}
        </span>
        <span>
          Scope: {data.scope.replaceAll("_", " ")} · Updated{" "}
          {time(data.timestamp)} UTC
        </span>
      </div>
    </div>
  );
}

export function AgentDirectory({ agents, agent, onAgent }) {
  return (
    <section className="agent-directory" aria-label="Agent observations">
      <div className="directory-heading">
        <h2>Agent observations</h2>
        <p>
          Atlas, Haven, Saffron and Roam research the web through TinyFish in
          TinyFish mode. The consultant, itinerary, budget and support roles
          apply local rules and shared memory. Read counts apply to the retained
          event window. Select an agent to filter the workspace.
        </p>
      </div>
      <div className="agent-directory-grid">
        {agents.map((row) => (
          <button
            key={row.agent_id}
            onClick={() => onAgent(row.agent_id)}
            aria-pressed={agent === row.agent_id}
          >
            <strong>{agentName(row.agent_id)}</strong>
            <span>{row.reads_in_window || 0} recorded reads</span>
          </button>
        ))}
      </div>
    </section>
  );
}

export function TinyFishIntelligence({
  data,
  compact = false,
  hrefFor,
  navigate,
}) {
  const research = data.tinyfish;
  const metrics = research?.metrics || {};
  const tiles = [
    [
      "Source quotations",
      metrics.source_quotes,
      "Exact text from fetched pages",
    ],
    [
      "Evidence reuse",
      metrics.reuse_events,
      "Recorded recalls using saved findings",
    ],
    [
      "Fresh topic versions",
      metrics.fresh,
      "Freshness is separate from verification",
    ],
    [
      "Plans flagged",
      metrics.plans_flagged,
      "Changed evidence requires review",
    ],
  ];
  return (
    <section
      className={`tf-intelligence ${compact ? "compact" : ""}`}
      aria-label="TinyFish intelligence"
    >
      <header className="tf-hero">
        <div>
          <span className="kicker">TinyFish × Iron Web 2</span>
          <h2>Memory that reconnects to the world.</h2>
          <p>
            TinyFish discovers and reads public sources. Shared memory preserves
            the evidence; specialist agents use current observations alongside
            your confirmed preferences.
          </p>
        </div>
        <span className="tf-connection">
          {data.replay
            ? "Saved controlled test"
            : research
              ? research.configured
                ? "Provider configured"
                : "Provider not configured"
              : "Evidence feed unavailable"}
        </span>
      </header>
      <ol className="tf-flow" aria-label="External memory lifecycle">
        {[
          "Recall",
          "Check freshness",
          "TinyFish Search + Fetch",
          "Version evidence",
          "Share with agents",
          "Review affected plans",
        ].map((step, i) => (
          <li key={step}>
            <b>{String(i + 1).padStart(2, "0")}</b>
            {step}
          </li>
        ))}
      </ol>
      <div className="tf-metrics">
        {tiles.map(([label, value, note]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value ?? "—"}</strong>
            <small>{note}</small>
          </div>
        ))}
      </div>
      {data.replay && <p className="tf-scope">{research?.scope}</p>}
      {compact ? (
        <PageLink page="tinyfish" hrefFor={hrefFor} navigate={navigate}>
          Inspect TinyFish evidence and refresh activity <ArrowRightIcon />
        </PageLink>
      ) : (
        <>
          <p className="tf-scope">
            {research?.scope ||
              "The website must publish an authenticated evidence snapshot. No sample activity is substituted."}
          </p>
          <div className="tf-details-grid">
            <section>
              <h3>Evidence versions</h3>
              <p>
                Only fresh, undisputed versions enter the agent evidence
                context. Different quotations are review candidates, not
                automatically contradictions.
              </p>
              {research?.evidence?.length ? (
                research.evidence.map((version) => (
                  <article className="tf-evidence" key={version.id}>
                    <header>
                      <strong>{version.topic}</strong>
                      <span>
                        {version.freshness} · {version.verification}
                      </span>
                    </header>
                    <p>
                      {version.conflict_candidate
                        ? "Differing statements: excluded pending review."
                        : version.changed
                          ? "Changed source evidence: review applicability."
                          : "Source observation; applicability remains unverified."}
                    </p>
                    {version.statements.slice(0, 3).map((statement, index) => (
                      <blockquote key={index}>
                        <p>{statement.quote}</p>
                        <a
                          href={statement.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          Read source ↗
                        </a>
                      </blockquote>
                    ))}
                    <dl>
                      <div>
                        <dt>Retrieved</dt>
                        <dd>{version.retrieved_at || "Unknown"}</dd>
                      </div>
                      <div>
                        <dt>Fresh until</dt>
                        <dd>{version.expires_at || "Unknown"}</dd>
                      </div>
                      <div>
                        <dt>Graph index</dt>
                        <dd>
                          {version.graph_synced
                            ? "Indexed in FalkorDB"
                            : "Pending / no quotation"}
                        </dd>
                      </div>
                    </dl>
                    <small>
                      Version {version.id}
                      {version.previous_id
                        ? ` · Previous ${version.previous_id}`
                        : ""}
                    </small>
                  </article>
                ))
              ) : (
                <p className="page-empty">
                  No external evidence saved yet. Plan a trip or request
                  destination research from the Travel Desk to begin.
                </p>
              )}
            </section>
            <section>
              <h3>Research and refresh activity</h3>
              <div className="tf-mini-totals">
                <span>{metrics.stale ?? "—"} stale topics</span>
                <span>{metrics.conflicts ?? "—"} review candidates</span>
                <span>{metrics.graph_indexed ?? "—"} graph versions</span>
                <span>
                  {metrics.refresh_requests ?? "—"} recall refresh requests
                </span>
              </div>
              {research?.jobs?.length ? (
                research.jobs.map((job) => (
                  <article className="tf-job" key={job.id}>
                    <strong>{job.status}</strong>
                    <p>{job.topics.join(" · ")}</p>
                    {job.metrics && (
                      <small>
                        {job.metrics.elapsed_ms.toLocaleString()} ms ·{" "}
                        {job.metrics.sources} sources ·{" "}
                        {job.metrics.fetched_pages} pages ·{" "}
                        {job.metrics.source_quotes} quotes
                      </small>
                    )}
                    <code>{job.id}</code>
                  </article>
                ))
              ) : (
                <p className="page-empty">
                  No destination research jobs recorded.
                </p>
              )}
              <h3>Memory lifecycle events</h3>
              <ol className="tf-events">
                {research?.events?.map((event) => (
                  <li key={event.id}>
                    <strong>{event.kind.replaceAll("_", " ")}</strong>
                    <time>
                      {new Date(event.timestamp * 1000).toLocaleString()}
                    </time>
                    <p>
                      {event.detail.topics?.join(", ") ||
                        event.detail.topic ||
                        (event.detail.count
                          ? `${event.detail.count} evidence versions`
                          : event.detail.reason ||
                            "Evidence lifecycle recorded")}
                    </p>
                  </li>
                ))}
              </ol>
            </section>
          </div>
          <aside className="tf-trust">
            <strong>Fresh evidence. Explicit boundaries.</strong>
            <p>
              Public destination and topic queries leave the backend. Identity,
              budgets, travel dates and personal preferences stay local. Web
              quotations cannot authorize instructions or change a traveler
              preference. No source statement guarantees availability, safety or
              current prices.
            </p>
          </aside>
        </>
      )}
    </section>
  );
}

export function EventJournal({ events, event, agent, onEvent }) {
  const rows = events
    .filter((e) => !agent || e.agent_id === agent)
    .slice(-50)
    .reverse();
  return (
    <section className="event-journal" aria-labelledby="journal-title">
      <div className="directory-heading">
        <h2 id="journal-title">Event journal</h2>
        <p>
          Latest 50 matching observations. Select a row to inspect its captured
          context.
        </p>
      </div>
      {rows.length ? (
        <div className="event-table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Event</th>
                <th scope="col">Agent</th>
                <th scope="col">Observation</th>
                <th scope="col">Time (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id} data-selected={event?.id === e.id}>
                  <td>
                    <button
                      aria-label={`Open observation ${e.id}`}
                      onClick={() => onEvent(e.id)}
                    >
                      #{e.id}
                    </button>
                  </td>
                  <td>{agentName(e.agent_id)}</td>
                  <td>
                    {eventLabel(e)}
                    {isConflict(e) && (
                      <span className="event-warning">Needs attention</span>
                    )}
                  </td>
                  <td className="mono">{time(e.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="page-empty">No observations match this agent filter.</p>
      )}
    </section>
  );
}

function SavedRunResult({ run, api, recorded = false }) {
  const [saved, setSaved] = useState(recorded ? run.payload : null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  async function load() {
    if (recorded) {
      setSaved(run.payload);
      return;
    }
    setLoading(true);
    try {
      const r = await fetch(
        api + "/api/dashboard/history?run_id=" + encodeURIComponent(run.run_id),
        { credentials: "include", cache: "no-store" },
      );
      if (!r.ok) throw new Error("Saved result could not be loaded");
      setSaved((await r.json()).payload);
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <div>
      {!saved && (
        <button onClick={load} disabled={loading}>
          {loading
            ? "Loading saved result…"
            : "Load complete saved result and metrics"}
        </button>
      )}
      {error && <p role="status">{error}</p>}
      {saved && (
        <pre className="live-json">{JSON.stringify(saved, null, 2)}</pre>
      )}
    </div>
  );
}

const metric = (value, unit = "") =>
  value == null
    ? "Not available"
    : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}${unit}`;
export function RunHistoryPage({ data, agent, api }) {
  const [page, setPage] = useState({ rows: [], next_before: null, total: 0 }),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  const identity = data.connection?.user_id;
  useEffect(() => {
    setPage({ rows: [], next_before: null, total: 0 });
  }, [identity, agent]);
  useEffect(() => {
    const abort = new AbortController();
    if (data.replay) {
      const rows = (data.history?.rows || []).filter(
        (row) => !agent || row.agent_id === agent,
      );
      setPage({ rows, total: rows.length, next_before: null });
      setError("");
      setLoading(false);
      return () => abort.abort();
    }
    const params = new URLSearchParams({ limit: "30" });
    if (agent) params.set("agent_id", agent);
    setLoading(true);
    fetch(api + "/api/dashboard/history?" + params, {
      credentials: "include",
      cache: "no-store",
      signal: abort.signal,
    })
      .then(async (r) => {
        if (!r.ok)
          throw new Error((await r.json()).detail || "Run history unavailable");
        return r.json();
      })
      .then((value) => {
        setPage((previous) => ({
          ...value,
          rows: [
            ...new Map(
              [...value.rows, ...previous.rows].map((r) => [r.run_id, r]),
            ).values(),
          ].sort((a, b) => b.sequence - a.sequence),
          next_before:
            previous.rows.length > 30
              ? previous.next_before
              : value.next_before,
        }));
        setError("");
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [api, identity, agent, data.observations.sequence, data.replay]);
  async function more() {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: "30",
        before: page.next_before,
      });
      if (agent) params.set("agent_id", agent);
      const r = await fetch(api + "/api/dashboard/history?" + params, {
        credentials: "include",
        cache: "no-store",
      });
      if (!r.ok) throw new Error("Older run history unavailable");
      const value = await r.json();
      setPage((p) => ({
        ...value,
        rows: [
          ...p.rows,
          ...value.rows.filter(
            (row) => !p.rows.some((old) => old.run_id === row.run_id),
          ),
        ],
      }));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="run-history-page">
      <div className="directory-heading">
        <h2>
          {page.total} recorded agent {page.total === 1 ? "run" : "runs"}
        </h2>
        <p>
          {data.replay
            ? "Saved reads reconstructed from the seeded project replay; not measured agent executions. Provider billing, timings and hosted tokens remain unavailable."
            : "Stored on disk across restarts. Each retry is a separate run. Provider billing and unreported token usage are marked as unavailable."}
        </p>
      </div>
      {error && <p role="alert">{error}</p>}
      {data.history_error && <p role="alert">{data.history_error}</p>}
      {!page.rows.length && (
        <p className="page-empty">
          {loading
            ? "Loading saved history…"
            : "No agent runs have been recorded for this account yet. Start a trip on the travel website; its agents will appear here automatically."}
        </p>
      )}
      {page.rows.map((run) => (
        <details className="run-history-entry" key={run.run_id}>
          <summary>
            <span>
              <strong>{agentName(run.agent_id)}</strong>
              <small>{run.summary || "Agent started"}</small>
            </span>
            <span className="run-status">
              {run.status === "running" &&
              run.payload.observation_boot !== data.observations.boot
                ? "Unfinished"
                : run.status}
            </span>
            <span>{metric(run.elapsed_ms, " ms")}</span>
            <time>{new Date(run.started_at * 1000).toLocaleString()}</time>
          </summary>
          <div className="run-history-detail">
            <dl>
              {[
                ["Started", new Date(run.started_at * 1000).toLocaleString()],
                [
                  "Finished",
                  run.finished_at
                    ? new Date(run.finished_at * 1000).toLocaleString()
                    : "Not finished",
                ],
                ["Total elapsed", metric(run.elapsed_ms, " ms")],
                [
                  "Memory retrieval",
                  metric(run.payload.memory?.retrieval_ms, " ms"),
                ],
                [
                  "Provider HTTP time",
                  metric(run.payload.provider?.http_ms, " ms"),
                ],
                ["Provider requests", metric(run.payload.provider?.requests)],
                [
                  "Failed requests",
                  metric(run.payload.provider?.failed_requests),
                ],
                [
                  "Reported input tokens",
                  metric(run.payload.provider?.input_tokens),
                ],
                [
                  "Reported output tokens",
                  metric(run.payload.provider?.output_tokens),
                ],
                [
                  "Cache hit",
                  run.payload.memory?.cache_hit == null
                    ? "Not available"
                    : run.payload.memory.cache_hit
                      ? "Yes"
                      : "No",
                ],
                ["Claims used", metric(run.payload.memory?.claims)],
                ["Cards used", metric(run.payload.memory?.cards)],
                ["Provider cost", metric(run.payload.provider?.cost)],
                [
                  "Process CPU time (shared)",
                  metric(run.payload.resources?.process_cpu_ms, " ms"),
                ],
                [
                  "Process RAM (shared)",
                  metric(run.payload.resources?.ram_bytes, " bytes"),
                ],
                [
                  "Device VRAM (shared)",
                  metric(run.payload.resources?.vram_bytes, " bytes"),
                ],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <p className="truth-note">
              Context sizes use the configured memory tokenizer. Reported tokens
              include only provider responses with usage. Process RAM/CPU and
              device VRAM are shared samples, not exclusive agent allocations.
              HTTP time is part of elapsed time; overlapping agent durations
              should not be added to estimate workflow duration.
            </p>
            <p className="mono full-id">
              Run: {run.run_id} · Workflow: {run.workflow_id || "Not available"}{" "}
              · Trip: {run.trip_id || "Profile"}
            </p>
            <details>
              <summary>All recorded metrics, result and errors</summary>
              <SavedRunResult
                key={run.run_id + run.summary + run.status}
                run={run}
                api={api}
                recorded={Boolean(data.replay)}
              />
            </details>
          </div>
        </details>
      ))}
      {page.next_before && (
        <button className="primary-page-link" disabled={loading} onClick={more}>
          {loading ? "Loading…" : "Load older runs"}
        </button>
      )}
    </div>
  );
}
