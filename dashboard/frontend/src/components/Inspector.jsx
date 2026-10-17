import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowRightIcon,
  FileTextIcon,
  Link2Icon,
  ChevronRightIcon,
  ExclamationTriangleIcon,
} from "@radix-ui/react-icons";
import {
  AGENTS,
  TIERS,
  diffRows,
  fileName,
  formatTime,
  pretty,
  tierKey,
} from "../memory.js";

function Value({ value }) {
  return (
    <pre className="mono whitespace-pre-wrap break-words text-[12px] leading-[1.8]">
      {value === undefined ? "—" : (pretty(value) ?? "null")}
    </pre>
  );
}
export default function Inspector({
  snapshot,
  selectedPath,
  activeEvent,
  onEvent,
  pulseId,
  onAgent,
  onMemory,
  onSource,
}) {
  const memory = snapshot.memories.get(selectedPath),
    history = snapshot.history.get(selectedPath) || [];
  const tier = TIERS[tierKey(selectedPath || "")],
    reduced = useReducedMotion();
  const event =
    activeEvent?.memoryPath === selectedPath ? activeEvent : history.at(-1);
  const versions = history.filter(
    (entry) => entry.action !== "read" && !entry.conflict,
  );
  const descendants = [...snapshot.memories.values()].filter((item) =>
    item.path.startsWith(selectedPath + "/"),
  );
  if (!memory && !history.length)
    return (
      <aside className="inspector border-l border-line bg-panel">
        <div className="panel-heading">
          <h2 className="eyebrow">INSPECTOR</h2>
          <FileTextIcon className="size-3 text-faint" />
        </div>
        <div className="p-5">
          <p className="mb-2 text-sm text-ink">
            {selectedPath ? "Memory directory" : "Select a memory"}
          </p>
          <p className="text-xs leading-6 text-muted">
            {selectedPath
              ? `${descendants.length} memories below ${selectedPath}. Select a yellow memory node or a file to inspect its contents.`
              : "Choose a graph node or a file to inspect its contents, writer and version history."}
          </p>
          <div className="mt-4">
            {descendants.map((memory) => (
              <button
                key={memory.path}
                className="agent-event"
                onClick={() => onMemory(memory.path)}
              >
                <span className="mono text-xs text-memory">
                  {fileName(memory.path)}
                </span>
              </button>
            ))}
          </div>
        </div>
      </aside>
    );
  const conflict = event?.conflict;
  const changed = event
    ? diffRows(event.before, event.after).filter((row) => row.changed)
    : [];
  return (
    <aside
      className="inspector flex min-h-0 flex-col border-l border-line bg-panel"
      aria-label="Memory inspector"
    >
      <div className="panel-heading">
        <h2 className="eyebrow">INSPECTOR</h2>
        <span className="mono text-[12px] text-faint">
          {memory ? "MEMORY" : "FORGOTTEN"}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="border-b border-line p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="mono flex items-center gap-1.5 text-[12px] text-muted">
              <i className="size-1 rounded-full bg-memory" />
              TIER {tier?.number} <ChevronRightIcon className="size-3" />
              {tier?.storage}
            </span>
            <span className="mono rounded border border-line px-1.5 py-0.5 text-[12px] text-muted">
              v{memory?.version || versions.length}
            </span>
          </div>
          <h3 className="text-[19px] font-medium tracking-tight text-ink">
            {fileName(selectedPath)}
          </h3>
          <p className="mono mt-1.5 break-all text-[12px] text-faint">
            {selectedPath.split("/").slice(0, -1).join("/")}
          </p>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <div>
              <div className="eyebrow mb-1.5">LAST WRITER</div>
              <button
                onClick={() =>
                  onAgent(memory?.writer || versions.at(-1)?.agent)
                }
                className="flex items-center gap-1.5 text-[12px] text-ink"
                title="Inspect this agent"
              >
                <i className="size-1 rounded-full bg-mint" />
                {AGENTS[memory?.writer || versions.at(-1)?.agent]?.short || "—"}
              </button>
            </div>
            <div>
              <div className="eyebrow mb-1.5">LAST MODIFIED</div>
              <div className="mono text-[12px] text-muted">
                {formatTime(memory?.updatedAt || versions.at(-1)?.timestamp)}
              </div>
            </div>
          </div>
        </div>
        <div className="border-b border-line px-5 py-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="eyebrow">CURRENT VALUE</h3>
            <span className="mono text-[12px] text-muted">
              {memory ? "ACCEPTED" : "REMOVED"}
            </span>
          </div>
          {memory?.value?.amount ? (
            <div className="mb-3">
              <span className="text-[27px] font-medium tracking-tight text-memory">
                ₹{memory.value.amount.toLocaleString("en-IN")}
              </span>
              <span className="mono ml-2 text-[12px] text-muted">
                {memory.value.currency} / TRIP
              </span>
            </div>
          ) : null}
          {memory?.value?.amount ? (
            <details className="stored-json">
              <summary className="mono cursor-pointer text-[12px] text-faint">
                View stored JSON
              </summary>
              <div className="mt-2 rounded border border-line bg-stage px-3 py-2.5 text-muted">
                <Value value={memory.value} />
              </div>
            </details>
          ) : (
            <div className="max-h-40 overflow-auto rounded border border-line bg-stage px-3 py-2.5 text-muted">
              <Value value={memory?.value ?? null} />
            </div>
          )}
        </div>
        {event && (
          <motion.section
            key={`inspector-${event.id}-${pulseId}`}
            initial={reduced ? false : { opacity: 0.65 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25 }}
            className="border-b border-line px-5 py-4"
            data-inspected-event={event.id}
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="eyebrow">
                EVENT {String(event.id).padStart(2, "0")}
              </h3>
              <span
                className={`mono text-[12px] ${conflict ? "text-conflict" : "text-mint"}`}
              >
                {conflict ? "WRITE CONFLICT" : event.action.toUpperCase()}
              </span>
            </div>
            {conflict && (
              <div className="conflict-note mb-3 rounded border border-conflict/25 bg-conflict/5 p-3">
                <div className="mb-2 flex items-center gap-2 text-[12px] text-conflict">
                  <ExclamationTriangleIcon className="size-3" />
                  Stale write rejected
                </div>
                <p className="text-[12px] leading-[1.75] text-muted">
                  {AGENTS[event.agent].short} expected an older value. The
                  current memory is preserved.
                </p>
              </div>
            )}
            <div className="mb-3 flex items-center gap-2 text-[12px] text-muted">
              <span className="mono agent-letter">
                {AGENTS[event.agent].initials}
              </span>
              <span>{AGENTS[event.agent].short}</span>
              <span className="mono ml-auto text-[12px] text-faint">
                {formatTime(event.timestamp)}
              </span>
            </div>
            {event.action === "read" ? (
              <p className="mono text-[12px] leading-5 text-muted">
                Memory read. No value was changed.
              </p>
            ) : (
              <>
                <div className="mb-2 flex items-center gap-2 text-[12px] text-faint mono">
                  <span>{conflict ? "EXPECTED BEFORE" : "BEFORE"}</span>
                  <ArrowRightIcon className="size-3" />
                  <span>{conflict ? "PROPOSED AFTER" : "AFTER"}</span>
                </div>
                <div className="diff-box rounded border border-line bg-stage px-3 py-2.5">
                  {changed.length ? (
                    changed.map((row) => (
                      <div className="mb-2 last:mb-0" key={row.key}>
                        <span className="mono text-[12px] text-muted">
                          {row.key}
                        </span>
                        <div className="diff-before">
                          <span>−</span>
                          <Value value={row.before} />
                        </div>
                        <div
                          className={conflict ? "diff-rejected" : "diff-after"}
                        >
                          <span>+</span>
                          <Value value={row.after} />
                        </div>
                      </div>
                    ))
                  ) : (
                    <Value value={event.after} />
                  )}
                </div>
              </>
            )}
          </motion.section>
        )}
        <div className="px-5 py-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="eyebrow">VERSION HISTORY</h3>
            <span className="mono text-[12px] text-faint">
              {versions.length} VERSIONS
            </span>
          </div>
          <div className="history-stack">
            {history
              .filter((entry) => entry.action !== "read")
              .slice()
              .reverse()
              .map((entry) => (
                <button
                  key={entry.id}
                  onClick={() => onEvent(entry.id)}
                  className={`history-entry flex w-full gap-3 py-2.5 text-left ${entry.id === event?.id ? "current" : ""}`}
                >
                  <span
                    className={`history-dot mt-1.5 ${entry.conflict ? "conflict" : ""}`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between">
                      <span
                        className={`text-[12px] ${entry.conflict ? "text-conflict" : "text-ink"}`}
                      >
                        {entry.conflict
                          ? "Write rejected"
                          : entry.action === "write"
                            ? "Memory created"
                            : entry.action === "forget"
                              ? "Memory forgotten"
                              : "Memory updated"}
                      </span>
                      <span className="mono text-[12px] text-faint">
                        #{String(entry.id).padStart(2, "0")}
                      </span>
                    </span>
                    <span className="mono mt-1 block text-[12px] text-muted">
                      {AGENTS[entry.agent].short} ·{" "}
                      {formatTime(entry.timestamp)}
                    </span>
                  </span>
                </button>
              ))}
          </div>
        </div>
      </div>
      <button
        onClick={onSource}
        aria-label="Inspect memory event source"
        className="mono flex w-full shrink-0 items-center gap-2 border-t border-line px-5 py-3 text-[12px] text-faint"
      >
        <Link2Icon className="size-3" />
        SOURCE: EVENTS.JSON <span className="ml-auto">READ ONLY</span>
      </button>
    </aside>
  );
}
