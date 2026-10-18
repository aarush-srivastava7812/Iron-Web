import { useState } from "react";
import { agentColor, bytes, eventLabel } from "./liveData.js";

export const CHART_COLORS = [
  "var(--chart-teal)",
  "var(--chart-amber)",
  "var(--chart-plum)",
  "var(--chart-blue)",
];
export const formatNumber = (value) =>
  Number.isFinite(value) ? value.toLocaleString() : "N/A";
export const percent = (value, total) =>
  Number.isFinite(value) && total > 0
    ? `${Number(((value / total) * 100).toFixed(1))}%`
    : "N/A";

export function RingChart({
  segments = [],
  total,
  value,
  label,
  small = false,
}) {
  let offset = 0;
  return (
    <svg
      className={`metric-ring ${small ? "small" : ""}`}
      viewBox="0 0 140 140"
      role="img"
      aria-label={`${label}: ${value}. ${segments.map((s) => `${s.label}: ${formatNumber(s.value)}`).join("; ")}`}
    >
      <circle
        className="ring-ticks"
        cx="70"
        cy="70"
        r="64"
        pathLength="100"
        strokeDasharray="0.45 2.05"
      />
      <circle className="ring-track" cx="70" cy="70" r="53" />
      {segments.map((segment, i) => {
        const length =
          total > 0
            ? Math.min(
                Math.max(0, 100 - offset),
                (Math.max(0, segment.value || 0) / total) * 100,
              )
            : 0;
        const start = offset;
        offset += length;
        return length > 0 ? (
          <circle
            key={segment.label}
            cx="70"
            cy="70"
            r="53"
            fill="none"
            stroke={segment.color || CHART_COLORS[i % CHART_COLORS.length]}
            strokeWidth="10"
            pathLength="100"
            strokeDasharray={`${length} ${100 - length}`}
            strokeDashoffset={-start}
            transform="rotate(-90 70 70)"
          >
            <title>
              {segment.label}: {formatNumber(segment.value)}
            </title>
          </circle>
        ) : null;
      })}
      <circle className="ring-inner" cx="70" cy="70" r="42" />
      <text
        className="ring-value"
        style={{
          fontSize:
            String(value).length > 7
              ? 17
              : String(value).length > 5
                ? 22
                : undefined,
        }}
        x="70"
        y="69"
        textAnchor="middle"
      >
        {value}
      </text>
      <text className="ring-caption" x="70" y="87" textAnchor="middle">
        {label}
      </text>
    </svg>
  );
}

export function Gauge({ value, total, label, color = "var(--chart-teal)" }) {
  const ratio = Number.isFinite(value) && total > 0 ? value / total : null;
  const bounded = Math.max(0, Math.min(1, ratio ?? 0));
  return (
    <svg
      className="metric-gauge"
      viewBox="0 0 200 130"
      role="img"
      aria-label={`${label}: ${percent(value, total)}`}
    >
      <path className="gauge-track" d="M 24 100 A 76 76 0 0 1 176 100" />
      {ratio !== null && (
        <path
          d="M 24 100 A 76 76 0 0 1 176 100"
          fill="none"
          stroke={color}
          strokeWidth="10"
          pathLength="100"
          strokeDasharray={`${bounded * 100} 100`}
        />
      )}
      {Array.from({ length: 25 }, (_, i) => {
        const angle = Math.PI + (i / 24) * Math.PI;
        return (
          <line
            key={i}
            x1={100 + Math.cos(angle) * 88}
            y1={100 + Math.sin(angle) * 88}
            x2={100 + Math.cos(angle) * 94}
            y2={100 + Math.sin(angle) * 94}
            stroke={
              ratio !== null && i / 24 <= bounded ? color : "var(--ui-border)"
            }
            strokeWidth="1.5"
          />
        );
      })}
      <text className="gauge-value" x="100" y="86" textAnchor="middle">
        {percent(value, total)}
      </text>
      <text className="ring-caption" x="100" y="106" textAnchor="middle">
        {label}
      </text>
      <text className="plot-tick" x="18" y="124">
        0
      </text>
      <text className="plot-tick" x="165" y="124">
        100%
      </text>
    </svg>
  );
}

export function ChartLegend({ rows }) {
  return (
    <dl className="chart-legend">
      {rows.map((row, i) => (
        <div key={row.label}>
          <dt>
            <i
              style={{
                background: row.color || CHART_COLORS[i % CHART_COLORS.length],
              }}
            />
            {row.label}
          </dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function MemoryPlot({ rows }) {
  if (!rows.some((row) => Number.isFinite(row.value))) {
    return (
      <>
        <div className="chart-empty">
          No memory measurements are available in this snapshot.
        </div>
        <ChartLegend
          rows={rows.map((row, i) => ({
            label: row.label,
            value: "N/A",
            color: CHART_COLORS[i],
          }))}
        />
      </>
    );
  }
  const maximum = Math.max(
    1,
    ...rows.map((r) => (Number.isFinite(r.value) ? r.value : 0)),
  );
  return (
    <div className="memory-observations">
      <svg
        className="memory-plot"
        viewBox="0 0 520 170"
        role="img"
        aria-label="Current memory readings in bytes on a shared scale; these readings are not parts of a total"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line
              x1={22 + t * 476}
              x2={22 + t * 476}
              y1="10"
              y2="142"
              className="plot-grid"
            />
            <text
              x={22 + t * 476}
              y="163"
              textAnchor={t === 0 ? "start" : t === 1 ? "end" : "middle"}
              className="plot-tick"
            >
              {bytes(maximum * t)}
            </text>
          </g>
        ))}
        {rows.map((row, i) => (
          <g key={row.label}>
            <line
              x1="22"
              x2="498"
              y1={32 + i * 47}
              y2={32 + i * 47}
              className="plot-grid"
            />
            {Number.isFinite(row.value) && (
              <>
                <line
                  x1="22"
                  x2={22 + (row.value / maximum) * 476}
                  y1={32 + i * 47}
                  y2={32 + i * 47}
                  stroke={CHART_COLORS[i]}
                  strokeWidth="1.5"
                />
                <circle
                  cx={22 + (row.value / maximum) * 476}
                  cy={32 + i * 47}
                  r="6"
                  fill={CHART_COLORS[i]}
                >
                  <title>
                    {row.label}: {bytes(row.value)}
                  </title>
                </circle>
              </>
            )}
          </g>
        ))}
      </svg>
      <ChartLegend
        rows={rows.map((r, i) => ({
          ...r,
          value: bytes(r.value),
          color: CHART_COLORS[i],
        }))}
      />
    </div>
  );
}

export function LatencyPlot({ events }) {
  const [selected, setSelected] = useState(null);
  const measured = events
    .filter(
      (e) => Number.isFinite(e.detail?.latency_ms) && e.detail.latency_ms >= 0,
    )
    .slice(-18);
  if (!measured.length)
    return (
      <div className="chart-empty">
        No measured latency in this event window.
      </div>
    );
  const max = Math.max(1, ...measured.map((e) => e.detail.latency_ms));
  const log =
    max > 1000 && measured.some((e) => e.detail.latency_ms < max / 100);
  const ceiling = log ? Math.ceil(Math.log10(max + 1)) : max;
  const y = (value) =>
    206 - ((log ? Math.log10(value + 1) : value) / ceiling) * 174;
  const x = (i) =>
    measured.length === 1 ? 300 : 62 + (i / (measured.length - 1)) * 474;
  const ticks = log
    ? Array.from({ length: ceiling + 1 }, (_, i) => 10 ** i - 1)
    : [0, max / 3, (max * 2) / 3, max];
  const active = measured.find((e) => e.id === selected) || measured.at(-1);
  return (
    <div className="latency-chart latency-observations">
      <div className="plot-axis-note">
        Latency in ms · {log ? "logarithmic scale" : "linear scale"}
      </div>
      <svg
        className="latency-plot"
        viewBox="0 0 560 242"
        role="group"
        aria-label="Measured latency by event order"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1="62" x2="536" y1={y(t)} y2={y(t)} className="plot-grid" />
            <text x="51" y={y(t) + 4} textAnchor="end" className="plot-tick">
              {Math.round(t).toLocaleString()}
            </text>
          </g>
        ))}
        {measured.map((e, i) => (
          <g key={e.id}>
            <line
              x1={x(i)}
              x2={x(i)}
              y1={y(e.detail.latency_ms)}
              y2="206"
              stroke={agentColor(e.agent_id)}
              strokeWidth="1"
              opacity=".25"
            />
            <circle
              role="button"
              tabIndex="0"
              aria-label={`Inspect latency event ${e.id}: ${e.detail.latency_ms} ms`}
              cx={x(i)}
              cy={y(e.detail.latency_ms)}
              r={e.id === active.id ? 7 : 5}
              fill={agentColor(e.agent_id)}
              stroke="var(--ui-panel)"
              strokeWidth="2"
              onClick={() => setSelected(e.id)}
              onKeyDown={(key) => {
                if (["Enter", " "].includes(key.key)) {
                  key.preventDefault();
                  setSelected(e.id);
                }
              }}
            >
              <title>
                #{e.id} {eventLabel(e)}: {e.detail.latency_ms} ms
              </title>
            </circle>
            {(i === 0 ||
              i === measured.length - 1 ||
              i === Math.floor(measured.length / 2)) && (
              <text x={x(i)} y="229" textAnchor="middle" className="plot-tick">
                #{e.id}
              </text>
            )}
          </g>
        ))}
      </svg>
      <div className="plot-selection">
        <span className="mono">#{active.id}</span>
        <span>{eventLabel(active)}</span>
        <strong>
          {Math.round(active.detail.latency_ms).toLocaleString()} ms
        </strong>
      </div>
      <div className="plot-axis-note">
        Event order · select a point to inspect its measurement
      </div>
    </div>
  );
}

export function TierMeter({ value, total, color }) {
  return (
    <svg className="tier-meter" viewBox="0 0 80 50" aria-hidden="true">
      <path d="M 8 40 A 32 32 0 0 1 72 40" className="gauge-track" />
      <path
        d="M 8 40 A 32 32 0 0 1 72 40"
        fill="none"
        stroke={color}
        strokeWidth="6"
        pathLength="100"
        strokeDasharray={`${total > 0 ? Math.min(100, (value / total) * 100) : 0} 100`}
      />
      <text x="40" y="40" textAnchor="middle" className="tier-meter-value">
        {percent(value, total)}
      </text>
    </svg>
  );
}
