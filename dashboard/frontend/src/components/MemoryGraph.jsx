import { useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  MinusIcon,
  PlusIcon,
  ResetIcon,
  Crosshair2Icon,
} from "@radix-ui/react-icons";
import { fileName, TIERS, tierKey, topology } from "../memory.js";

import {
  layoutGraph,
  DEFAULT_GRAPH_SIZE,
  GRAPH_LIMITS,
  clampGraphSize,
} from "../graphLayout.js";
const STORAGE_KEY = "ironweb.graph-size.v1";
function savedSize() {
  try {
    return clampGraphSize(
      JSON.parse(localStorage.getItem(STORAGE_KEY)) || DEFAULT_GRAPH_SIZE,
    );
  } catch {
    return DEFAULT_GRAPH_SIZE;
  }
}

export default function MemoryGraph({
  events,
  snapshot,
  selectedPath,
  selectedAgent,
  activeEvent,
  pulseId,
  onSelect,
  actionFilter,
}) {
  const container = useRef(null);
  const [size, setSize] = useState({ width: 900, height: 600 });
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.max(1, Math.round(entry.contentRect.width));
      const height = Math.max(1, Math.round(entry.contentRect.height));
      setSize((old) =>
        old.width === width && old.height === height ? old : { width, height },
      );
    });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const [canvasSize, setCanvasSize] = useState(savedSize);
  const [fit, setFit] = useState(() => {
    try {
      return localStorage.getItem("ironweb.graph-fit.v1") !== "false";
    } catch {
      return true;
    }
  });
  const [sizeOpen, setSizeOpen] = useState(false);
  const resizeGesture = useRef(null);
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(canvasSize));
    } catch {}
    try {
      localStorage.setItem("ironweb.graph-fit.v1", String(fit));
    } catch {}
  }, [canvasSize, fit]);
  const updateSize = (value) => {
    setFit(false);
    setCanvasSize((previous) => clampGraphSize({ ...previous, ...value }));
  };
  const WIDTH = fit ? size.width : canvasSize.width,
    HEIGHT = fit ? size.height : canvasSize.height;
  const layout = useMemo(
    () => layoutGraph(events, WIDTH, HEIGHT),
    [events, WIDTH, HEIGHT],
  );
  const graph = useMemo(() => topology(snapshot.memories), [snapshot.memories]);
  const [zoom, setZoom] = useState(1),
    [pan, setPan] = useState({ x: 0, y: 0 }),
    [hover, setHover] = useState(null),
    [showLabels, setShowLabels] = useState(true);
  const drag = useRef(null),
    reducedMotion = useReducedMotion();
  const activeId = activeEvent?.memoryPath;
  const selectedNode = graph.nodes.find((n) => n.id === selectedPath);
  const related = new Set([selectedPath]);
  graph.edges.forEach((edge) => {
    if (edge.source === selectedPath) related.add(edge.target);
    if (edge.target === selectedPath) related.add(edge.source);
  });
  function point(event) {
    const box = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - box.left) / box.width) * WIDTH,
      y: ((event.clientY - box.top) / box.height) * HEIGHT,
    };
  }
  const position = (id) => layout.get(id) || { x: WIDTH / 2, y: HEIGHT / 2 };
  return (
    <div className="graph-wrap" data-testid="memory-graph">
      <div className="graph-toolbar">
        <div className="graph-meta pointer-events-none flex flex-col gap-1.5">
          <span className="eyebrow">SHARED MEMORY TOPOLOGY</span>
          <span className="mono text-[12px] text-muted">
            {graph.nodes.length} nodes{" "}
            <span className="mx-1 text-faint">/</span> {graph.edges.length}{" "}
            connections
          </span>
        </div>
        <div className="graph-camera flex shrink-0 gap-1 rounded-md border border-line bg-stage p-1">
          <button
            className="icon-button"
            title="Zoom out"
            aria-label="Zoom out"
            disabled={zoom <= 0.5}
            onClick={() => setZoom((v) => Math.max(0.5, v - 0.2))}
          >
            <MinusIcon />
          </button>
          <span className="mono flex w-11 items-center justify-center text-[12px] text-muted">
            {Math.round(zoom * 100)}%
          </span>
          <button
            className="icon-button"
            title="Zoom in"
            aria-label="Zoom in"
            disabled={zoom >= 3}
            onClick={() => setZoom((v) => Math.min(3, v + 0.2))}
          >
            <PlusIcon />
          </button>
          <button
            className="icon-button mono text-[12px]"
            aria-label={showLabels ? "Hide node labels" : "Show node labels"}
            title="Toggle node labels"
            aria-pressed={showLabels}
            onClick={() => setShowLabels((value) => !value)}
          >
            Aa
          </button>
          <span className="mx-1 my-1 w-px bg-line" />
          <button
            className="icon-button"
            title="Reset pan, zoom and scroll"
            aria-label="Reset graph view"
            onClick={() => {
              setFit(true);
              setZoom(1);
              setPan({ x: 0, y: 0 });
              container.current?.scrollTo({ left: 0, top: 0 });
            }}
          >
            <ResetIcon />
          </button>
          <button
            className="graph-size-toggle mono"
            aria-label="Adjust graph size"
            aria-expanded={sizeOpen}
            onClick={() => setSizeOpen((value) => !value)}
          >
            Size
          </button>
        </div>
      </div>
      {sizeOpen && (
        <section className="graph-size-panel" aria-label="Graph dimensions">
          <label className="graph-fit-option">
            <input
              type="checkbox"
              checked={fit}
              onChange={(event) => {
                setFit(event.target.checked);
                setZoom(1);
                setPan({ x: 0, y: 0 });
              }}
            />{" "}
            Fit graph to stage
          </label>
          {["width", "height"].map((axis) => (
            <label key={axis} className="graph-dimension">
              <span>{axis === "width" ? "Width" : "Height"}</span>
              <input
                type="range"
                aria-label={`Graph ${axis}`}
                min={GRAPH_LIMITS[axis].min}
                max={GRAPH_LIMITS[axis].max}
                step="20"
                value={canvasSize[axis]}
                onChange={(event) =>
                  updateSize({ [axis]: Number(event.target.value) })
                }
              />
              <output aria-label={`Graph ${axis} value`}>
                {canvasSize[axis]} px
              </output>
            </label>
          ))}
          <button
            onClick={() => {
              setCanvasSize(DEFAULT_GRAPH_SIZE);
              setFit(true);
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
            className="mono text-[12px] text-mint"
            aria-label="Reset graph size"
          >
            Reset size
          </button>
        </section>
      )}
      <div
        ref={container}
        className="graph-viewport"
        style={{ height: HEIGHT }}
        data-testid="graph-viewport"
      >
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="graph-svg"
          width={WIDTH}
          height={HEIGHT}
          style={{ width: WIDTH, height: HEIGHT }}
          data-canvas-width={WIDTH}
          data-canvas-height={HEIGHT}
          aria-label="Memory graph. Node size represents connection count. Select a node to inspect it."
          onPointerDown={(e) => {
            if (e.target === e.currentTarget) {
              drag.current = { ...point(e), pan };
              e.currentTarget.setPointerCapture(e.pointerId);
            }
          }}
          onPointerMove={(e) => {
            if (drag.current) {
              const p = point(e);
              setPan({
                x: drag.current.pan.x + p.x - drag.current.x,
                y: drag.current.pan.y + p.y - drag.current.y,
              });
            }
          }}
          onPointerUp={() => {
            drag.current = null;
          }}
          onPointerCancel={() => {
            drag.current = null;
          }}
          onPointerLeave={() => setHover(null)}
        >
          <g
            transform={`translate(${WIDTH / 2 + pan.x} ${HEIGHT / 2 + pan.y}) scale(${zoom}) translate(${-WIDTH / 2} ${-HEIGHT / 2})`}
          >
            {graph.edges.map((edge) => {
              const a = position(edge.source),
                b = position(edge.target),
                highlight =
                  edge.source === selectedPath || edge.target === selectedPath;
              return (
                <line
                  key={edge.id}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={
                    highlight ? "var(--state-current)" : "var(--ui-border)"
                  }
                  strokeWidth={highlight ? 1.05 : 0.65}
                  opacity={
                    selectedPath && !highlight
                      ? 0.45
                      : edge.type === "source"
                        ? 0.5
                        : 0.58
                  }
                  strokeDasharray={edge.type === "source" ? "3 4" : undefined}
                />
              );
            })}
            {graph.nodes.map((node) => {
              const p = position(node.id),
                selected = node.id === selectedPath,
                active = node.id === activeId,
                isAgentMatch =
                  (!selectedAgent && !actionFilter) ||
                  [...snapshot.history.entries()].some(
                    ([path, history]) =>
                      (path === node.id || path.startsWith(node.id + "/")) &&
                      history.some(
                        (event) =>
                          (!selectedAgent || event.agent === selectedAgent) &&
                          (!actionFilter || event.action === actionFilter),
                      ),
                  );
              const dim =
                (selectedPath && !related.has(node.id)) || !isAgentMatch;
              const label = node.id === "shared" ? "shared memory" : node.label;
              return (
                <g
                  key={node.id}
                  transform={`translate(${p.x} ${p.y})`}
                  role="button"
                  tabIndex={0}
                  aria-label={`${label}, ${node.degree} connections${selected ? ", selected" : ""}`}
                  aria-pressed={selected}
                  data-node-path={node.id}
                  onClick={() => onSelect(node.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(node.id);
                    }
                  }}
                  onPointerEnter={() => setHover(node)}
                  onFocus={() => setHover(node)}
                  onBlur={() => setHover(null)}
                  className="graph-node cursor-pointer outline-none"
                >
                  <title>
                    {label} · {node.degree} connections
                    {node.memory ? ` · written by ${node.memory.writer}` : ""}
                  </title>
                  <circle r={node.radius + 12} fill="transparent" />
                  {selected && (
                    <circle
                      r={node.radius + 5}
                      fill="none"
                      stroke="var(--state-current)"
                      strokeWidth=".8"
                      strokeDasharray="2 3"
                      opacity=".85"
                    />
                  )}
                  {active && pulseId > 0 && !reducedMotion && (
                    <motion.circle
                      key={`pulse-${pulseId}-${node.id}`}
                      data-event-pulse={activeEvent.id}
                      r={node.radius + 4}
                      fill="none"
                      stroke={
                        activeEvent.conflict
                          ? "var(--state-conflict)"
                          : activeEvent.action === "read"
                            ? "var(--agent-researcher)"
                            : "var(--state-current)"
                      }
                      strokeWidth="1.5"
                      initial={{ scale: 1, opacity: 0.85 }}
                      animate={{ scale: 2.8, opacity: 0 }}
                      transition={{ duration: 1.25, ease: "easeOut" }}
                    />
                  )}
                  <circle
                    r={node.radius}
                    fill="var(--state-current)"
                    fillOpacity={dim ? 0.64 : node.isMemory ? 0.94 : 0.78}
                    stroke={
                      selected ? "var(--state-current)" : "var(--state-current)"
                    }
                    strokeWidth={selected ? 1.2 : 0.4}
                  />
                  {node.id === "shared" && (
                    <circle r="3" fill="var(--ui-panel)" />
                  )}
                  {showLabels && (
                    <text
                      y={node.radius + 17}
                      textAnchor="middle"
                      className="node-label"
                      fill={
                        selected
                          ? "var(--ui-text)"
                          : dim
                            ? "var(--ui-secondary)"
                            : node.isMemory
                              ? "var(--ui-secondary)"
                              : "var(--ui-secondary)"
                      }
                      fontSize={node.id === "shared" ? 13 : 12}
                    >
                      {label}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      </div>
      <div className="graph-footer">
        {hover && (
          <div className="graph-tooltip pointer-events-none absolute bottom-12 left-4 z-10 max-w-[270px] border border-line bg-panel px-3 py-2.5">
            <div className="mono text-xs text-ink">{fileName(hover.id)}</div>
            <div className="mono mt-1 text-[12px] text-muted">
              {hover.degree} connections ·{" "}
              {hover.isMemory
                ? TIERS[tierKey(hover.id)]?.name || "memory"
                : "directory"}
            </div>
          </div>
        )}
        <div className="graph-legend pointer-events-none flex flex-wrap items-center gap-4 text-[12px] text-muted mono">
          <span className="flex items-center gap-2">
            <i className="size-1.5 rounded-full bg-memory" />
            Memory
          </span>
          <span className="flex items-center gap-2">
            <i className="h-px w-5 bg-line" />
            Connection
          </span>
          <span className="flex items-center gap-2">
            <i className="h-px w-5 border-t border-dashed border-line" />
            Source reference
          </span>
        </div>
        <button
          title="Center the selected memory"
          aria-label="Focus selected memory"
          onClick={() => {
            if (selectedNode) {
              const point = position(selectedNode.id);
              setZoom(1.5);
              container.current?.scrollTo({ left: 0, top: 0 });
              setPan({
                x: size.width / 2 - WIDTH / 2 - (point.x - WIDTH / 2) * 1.5,
                y: (HEIGHT / 2 - point.y) * 1.5,
              });
            } else {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }
          }}
          className="graph-focus flex shrink-0 items-center gap-2 text-faint"
        >
          <Crosshair2Icon />
          <span className="mono text-[12px]">
            {selectedNode
              ? `${selectedNode.degree} LINKS SELECTED`
              : "FIT GRAPH"}
          </span>
        </button>
        <button
          className="graph-resize-handle"
          aria-label="Resize graph canvas"
          title="Drag to resize graph width and height; arrow keys adjust by 20 pixels"
          onClick={() => setSizeOpen(true)}
          onPointerDown={(event) => {
            resizeGesture.current = {
              x: event.clientX,
              y: event.clientY,
              ...canvasSize,
            };
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            const gesture = resizeGesture.current;
            if (gesture)
              updateSize({
                width: gesture.width + event.clientX - gesture.x,
                height: gesture.height + event.clientY - gesture.y,
              });
          }}
          onPointerUp={() => {
            resizeGesture.current = null;
          }}
          onPointerCancel={() => {
            resizeGesture.current = null;
          }}
          onKeyDown={(event) => {
            if (
              !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(
                event.key,
              )
            )
              return;
            event.preventDefault();
            updateSize(
              event.key === "ArrowLeft"
                ? { width: WIDTH - 20 }
                : event.key === "ArrowRight"
                  ? { width: WIDTH + 20 }
                  : event.key === "ArrowUp"
                    ? { height: HEIGHT - 20 }
                    : { height: HEIGHT + 20 },
            );
          }}
        >
          <span />
          <span />
          <span />
        </button>
      </div>
      {!graph.nodes.length && (
        <div className="graph-empty absolute inset-x-0 top-40 pointer-events-none grid place-content-center text-center">
          <p className="text-sm text-ink">No memory at this point</p>
          <p className="mono mt-2 text-xs text-muted">
            Advance to the first write event.
          </p>
        </div>
      )}
    </div>
  );
}
