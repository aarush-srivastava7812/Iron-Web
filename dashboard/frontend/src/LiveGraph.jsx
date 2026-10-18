import { useEffect, useMemo, useRef, useState } from "react";
import {
  forceSimulation,
  forceX,
  forceY,
  forceManyBody,
  forceLink,
  forceCollide,
} from "d3-force";
import { motion, useReducedMotion } from "framer-motion";
import { COLORS, agentColor, agentName, isConflict } from "./liveData.js";

export default function LiveGraph({ graph, selected, onSelect, event, agent }) {
  const ref = useRef(null),
    previous = useRef({});
  const [size, setSize] = useState({ width: 800, height: 440 }),
    [zoom, setZoom] = useState(1),
    [pan, setPan] = useState({ x: 0, y: 0 }),
    [hover, setHover] = useState(null),
    [sized, setSized] = useState(true);
  const reduced = useReducedMotion(),
    drag = useRef(null);
  useEffect(() => {
    const observer = new ResizeObserver(([e]) => {
      setSize({ width: e.contentRect.width, height: e.contentRect.height });
      setZoom(1);
      setPan({ x: 0, y: 0 });
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  const key = graph.nodes.map((n) => `${n.id}:${n.access}`).join("|"),
    edgeKey = graph.edges.map((e) => e.id).join("|");
  const nodes = useMemo(() => {
    const radius = (n) =>
      sized ? Math.min(18, 5 + Math.sqrt(n.access) * 2.4) : 7;
    const ns = graph.nodes.map((n) => ({ ...n, r: radius(n) })),
      es = graph.edges.map((e) => ({ ...e }));
    const anchors = {
      hot: size.width / 6,
      context: size.width / 2,
      durable: (size.width * 5) / 6,
    };
    const tierOrder = ["hot", "context", "durable"];
    for (const tier of tierOrder) {
      const group = ns.filter((n) => n.tier === tier);
      const columns = tier === "durable" ? 3 : 2;
      group.forEach((n, i) => {
        n.ax =
          anchors[tier] +
          ((i % columns) - (columns - 1) / 2) * Math.min(70, size.width / 14);
        n.ay =
          50 +
          ((Math.floor(i / columns) + 0.5) /
            Math.max(1, Math.ceil(group.length / columns))) *
            Math.max(1, size.height - 95);
      });
    }
    const sim = forceSimulation(ns)
      .stop()
      .force("x", forceX((n) => n.ax).strength(0.45))
      .force("y", forceY((n) => n.ay).strength(0.4))
      .force("charge", forceManyBody().strength(-55))
      .force(
        "collision",
        forceCollide((n) => n.r + 10),
      )
      .force(
        "link",
        forceLink(es)
          .id((n) => n.id)
          .distance(55)
          .strength(0.045),
      );
    sim.tick(180);
    sim.stop();
    for (const n of ns) {
      const band = (tierOrder.indexOf(n.tier) * size.width) / 3;
      n.x = Math.max(
        band + n.r + 14,
        Math.min(band + size.width / 3 - n.r - 14, n.x),
      );
      n.y = Math.max(n.r + 28, Math.min(size.height - n.r - 32, n.y));
    }
    return ns;
    // Topology and size determine positions; new telemetry does not restart idle physics.
  }, [key, edgeKey, size.width, size.height, sized]);
  const positions = new Map(nodes.map((n) => [n.id, n])),
    neighbors = new Set([selected]);
  for (const e of graph.edges) {
    if (e.source === selected) neighbors.add(e.target);
    if (e.target === selected) neighbors.add(e.source);
  }
  const visibleLabels = new Set();
  const labelBoxes = [];
  const priority = (n) =>
    n.id === selected ? 100000 : n.id === hover ? 99999 : n.degree;
  for (const n of [...nodes].sort((a, b) => priority(b) - priority(a))) {
    const always = n.id === selected || n.id === hover;
    if (!always && zoom <= 1.15 && (n.degree < 5 || visibleLabels.size >= 9))
      continue;
    const width = Math.min(25, n.label.length) * 7.2;
    const x =
      n.x < 100 ? n.x : n.x > size.width - 100 ? n.x - width : n.x - width / 2;
    const box = { x, y: n.y + n.r + 5, w: width, h: 18 };
    const overlaps = labelBoxes.some(
      (b) =>
        box.x < b.x + b.w + 6 &&
        box.x + box.w + 6 > b.x &&
        box.y < b.y + b.h + 4 &&
        box.y + box.h + 4 > b.y,
    );
    if (always || zoom > 1.15 || !overlaps) {
      visibleLabels.add(n.id);
      labelBoxes.push(box);
    }
  }
  const targetId =
    event?.context?.claim_ids?.find((id) => positions.has(id)) ||
    (event?.detail?.memory_id
      ? nodes.find(
          (n) => n.raw?.properties?.memory_id === event.detail.memory_id,
        )?.id
      : undefined);
  const target = positions.get(targetId),
    old = previous.current[event?.agent_id] || { x: 20, y: size.height / 2 };
  useEffect(() => {
    if (target && event?.agent_id)
      previous.current[event.agent_id] = { x: target.x, y: target.y };
  }, [event?.id, target?.x, target?.y]);
  return (
    <div className="live-graph">
      <div className="graph-tools">
        <span title="Durable nodes are the actual paged FalkorDB graph; hot/card nodes are observed derived contexts.">
          {graph.nodes.filter((n) => n.raw).length} KG +{" "}
          {graph.nodes.filter((n) => !n.raw).length} context nodes ·{" "}
          {graph.edges.length} links
        </span>
        <div>
          <button
            aria-label="Zoom out"
            onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))}
          >
            −
          </button>
          <span className="mono">{Math.round(zoom * 100)}%</span>
          <button
            aria-label="Zoom in"
            onClick={() => setZoom((z) => Math.min(3, z + 0.2))}
          >
            +
          </button>
          <button
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
            aria-label="Fit graph"
          >
            Fit
          </button>
          <button aria-pressed={sized} onClick={() => setSized((v) => !v)}>
            Size by: {sized ? "access count" : "uniform"}
          </button>
        </div>
      </div>
      <div className="live-graph-body" ref={ref}>
        <svg
          width={size.width}
          height={size.height}
          viewBox={`0 0 ${size.width} ${size.height}`}
          role="img"
          aria-label="Live three-tier memory graph"
          onPointerDown={(e) => {
            if (e.target.tagName === "svg" || e.target.dataset.band) {
              drag.current = { x: e.clientX, y: e.clientY, pan };
              e.currentTarget.setPointerCapture(e.pointerId);
            }
          }}
          onPointerMove={(e) => {
            if (drag.current)
              setPan({
                x: drag.current.pan.x + e.clientX - drag.current.x,
                y: drag.current.pan.y + e.clientY - drag.current.y,
              });
          }}
          onPointerUp={() => (drag.current = null)}
          onPointerCancel={() => (drag.current = null)}
        >
          {["hot", "context", "durable"].map((tier, i) => (
            <g key={tier}>
              <rect
                data-band="true"
                x={(size.width * i) / 3}
                y="0"
                width={size.width / 3}
                height={size.height}
                fill={COLORS[tier]}
                opacity=".035"
              />
              <text
                x={(size.width * i) / 3 + 16}
                y="23"
                className="kicker"
                fill={COLORS[tier]}
              >
                {
                  ["01 HOT CONTEXT", "02 CONTEXT CARDS", "03 DURABLE EVIDENCE"][
                    i
                  ]
                }
              </text>
            </g>
          ))}
          <g
            transform={`translate(${size.width / 2 + pan.x} ${size.height / 2 + pan.y}) scale(${zoom}) translate(${-size.width / 2} ${-size.height / 2})`}
          >
            {graph.edges.map((e) => {
              const a = positions.get(e.source),
                b = positions.get(e.target);
              return a && b ? (
                <line
                  key={e.id}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={selected && (e.source === selected || e.target === selected)
                    ? "var(--state-current)"
                    : "var(--graph-edge)"}
                  opacity={
                    selected &&
                    !(neighbors.has(e.source) && neighbors.has(e.target))
                      ? 0.18
                      : 0.8
                  }
                  strokeWidth={selected && (e.source === selected || e.target === selected) ? 1.5 : 1}
                  vectorEffect="non-scaling-stroke"
                >
                  <title>{e.relation}</title>
                </line>
              ) : null;
            })}
            {nodes.map((n) => {
              const dim =
                  (selected && !neighbors.has(n.id)) ||
                  (agent && n.agent_id && n.agent_id !== agent),
                dormant = /expired|superseded|retract|redacted/.test(
                  n.raw?.lifecycle_status || "",
                ),
                show = visibleLabels.has(n.id);
              return (
                <g
                  key={n.id}
                  data-memory-id={n.id}
                  role="button"
                  tabIndex="0"
                  aria-label={`Inspect ${n.label}`}
                  aria-pressed={n.id === selected}
                  onClick={() => onSelect(n.id)}
                  onKeyDown={(e) => {
                    if (["Enter", " "].includes(e.key)) {
                      e.preventDefault();
                      onSelect(n.id);
                    }
                  }}
                  onMouseEnter={() => setHover(n.id)}
                  onMouseLeave={() => setHover(null)}
                  onFocus={() => setHover(n.id)}
                  onBlur={() => setHover(null)}
                  transform={`translate(${n.x},${n.y})`}
                  opacity={dim ? 0.45 : dormant ? 0.55 : 1}
                >
                  <title>
                    {n.label} · {n.id} · {n.access} observed accesses ·{" "}
                    {n.degree} links
                  </title>
                  <circle r={n.r + 7} fill="transparent" />
                  {selected === n.id && (
                    <circle
                      r={n.r + 4}
                      fill="none"
                      stroke="var(--state-current)"
                      strokeWidth="2"
                      className="current-ring"
                    />
                  )}
                  <circle
                    r={n.r}
                    fill={COLORS[n.tier]}
                    stroke={COLORS[n.tier]}
                    strokeDasharray={dormant ? "3 3" : undefined}
                    fillOpacity={dormant ? 0.25 : 1}
                  />
                  {show && (
                    <text
                      y={n.r + 17}
                      textAnchor={
                        n.x < 100
                          ? "start"
                          : n.x > size.width - 100
                            ? "end"
                            : "middle"
                      }
                      className="live-node-label"
                    >
                      {n.label.length > 25
                        ? n.label.slice(0, 23) + "…"
                        : n.label}
                    </text>
                  )}
                </g>
              );
            })}
            {target && (
              <g
                key={`event-${event.id}`}
                transform={`translate(${target.x} ${target.y})`}
                data-pulse-event={event.id}
              >
                {!reduced && (
                  <motion.circle
                    r={target.r + 3}
                    fill="none"
                    stroke={
                      isConflict(event)
                        ? "var(--state-conflict)"
                        : agentColor(event.agent_id)
                    }
                    initial={{ scale: 1, opacity: 1 }}
                    animate={{ scale: 3, opacity: 0 }}
                    transition={{ duration: 1.1 }}
                  />
                )}
              </g>
            )}
            {target && event.agent_id && (
              <motion.g
                key={`cursor-${event.id}`}
                initial={reduced ? false : { x: old.x, y: old.y }}
                animate={{ x: target.x, y: target.y }}
                transition={{ duration: reduced ? 0 : 0.65, ease: "easeOut" }}
                data-agent-cursor={event.id}
              >
                <circle r="4" fill={agentColor(event.agent_id)} />
                <text
                  y="-13"
                  textAnchor="middle"
                  fill={agentColor(event.agent_id)}
                  className="live-node-label"
                >
                  {agentName(event.agent_id)}
                </text>
              </motion.g>
            )}
          </g>
        </svg>
        {!nodes.length && (
          <div className="visual-empty">
            No memory in this scope yet.
            <span>
              Build a trip in the website to see actual agent activity.
            </span>
          </div>
        )}
      </div>
      <div className="color-key">
        {Object.entries(COLORS).map(([tier, color]) => (
          <span key={tier}>
            <i style={{ background: color }} />
            {tier === "durable"
              ? "Durable evidence"
              : tier === "hot"
                ? "Hot context"
                : "Context cards"}
          </span>
        ))}
        <span className="key-note">Accesses counted in retained events</span>
      </div>
    </div>
  );
}
