import { useEffect, useState } from "react";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  FileTextIcon,
  MagnifyingGlassIcon,
  LayersIcon,
  CubeIcon,
} from "@radix-ui/react-icons";
import {
  TIERS,
  fileName,
  tierKey,
  matchesEvent,
  memoryStrength,
} from "../memory.js";

export default function Explorer({
  snapshot,
  selectedPath,
  onSelect,
  query,
  setQuery,
  selectedAgent,
  actionFilter,
  onSource,
  halfLife,
}) {
  const [collapsed, setCollapsed] = useState(new Set(["tier-1", "tier-2"]));
  useEffect(() => {
    const tier = tierKey(selectedPath || "");
    setCollapsed((value) => {
      if (!value.has(tier)) return value;
      const next = new Set(value);
      next.delete(tier);
      return next;
    });
  }, [selectedPath]);
  useEffect(() => {
    if (query) setCollapsed(new Set());
  }, [query]);
  const memories = [...snapshot.memories.values()];
  const filtered = memories.filter(
    (memory) =>
      memory.path.toLowerCase().includes(query.toLowerCase()) &&
      ((!selectedAgent && !actionFilter) ||
        (snapshot.history.get(memory.path) || []).some((event) =>
          matchesEvent(event, selectedAgent, actionFilter),
        )),
  );
  function toggle(key) {
    setCollapsed((value) => {
      const next = new Set(value);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }
  return (
    <aside
      className="explorer flex min-h-0 flex-col border-r border-line bg-panel"
      aria-label="Memory explorer"
    >
      <div className="flex h-[57px] shrink-0 items-center justify-between px-5">
        <h2 className="eyebrow">MEMORY EXPLORER</h2>
        <span className="mono text-[12px] text-muted">
          {String(memories.length).padStart(2, "0")}
        </span>
      </div>
      <div className="px-4 pb-4">
        <label className="search-field flex h-9 items-center gap-2.5 rounded border border-line bg-stage px-3">
          <MagnifyingGlassIcon className="shrink-0 text-muted" />
          <input
            aria-label="Find a memory"
            className="min-w-0 flex-1 bg-transparent text-[12px] text-ink outline-none placeholder:text-faint"
            placeholder="Find a memory…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <button
            type="button"
            className="mono text-[12px] text-muted"
            onClick={() => {
              if (query) setQuery("");
              else
                document.querySelector('[aria-label="Find a memory"]')?.focus();
            }}
            aria-label={query ? "Clear memory search" : "Focus memory search"}
          >
            {query ? "×" : "/"}
          </button>
        </label>
      </div>
      <div className="tree min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        <button
          onClick={() => onSelect("shared")}
          aria-label="Inspect shared memory root"
          className="mono mb-3 flex w-full items-center gap-2 px-2 text-left text-[12px] text-muted"
        >
          <CubeIcon className="text-memory" />
          <span>shared-memory</span>
          <span className="ml-auto text-faint">ROOT</span>
        </button>
        {Object.entries(TIERS).map(([key, tier]) => {
          const rows = filtered.filter(
            (memory) => tierKey(memory.path) === key,
          );
          const closed = collapsed.has(key);
          return (
            <div className="mb-3" key={key}>
              <button
                className="tier-heading flex w-full items-center gap-2 rounded px-2 py-2 text-left"
                onClick={() => toggle(key)}
                aria-expanded={!closed}
              >
                {closed ? (
                  <ChevronRightIcon className="size-3 text-muted" />
                ) : (
                  <ChevronDownIcon className="size-3 text-muted" />
                )}
                <span className="mono tier-number">{tier.number}</span>
                <span className="text-[12px] font-medium text-ink">
                  {tier.name}
                </span>
                <span className="mono ml-auto text-[12px] text-faint">
                  {rows.length}
                </span>
              </button>
              {!closed && (
                <div className="ml-[13px] border-l border-line pl-2">
                  {rows.map((memory) => {
                    const selected = memory.path === selectedPath;
                    return (
                      <button
                        key={memory.path}
                        title={memory.path}
                        onClick={() => onSelect(memory.path)}
                        className={`memory-row group flex min-h-8 w-full items-center gap-2 rounded px-2 py-1.5 text-left ${selected ? "selected" : ""}`}
                        aria-pressed={selected}
                      >
                        <FileTextIcon className="size-3 shrink-0 text-faint group-hover:text-memory" />
                        <span className="mono truncate text-[12px]">
                          {fileName(memory.path)}
                        </span>
                        <span
                          className="memory-decay ml-auto"
                          title={`Illustrative retention: ${memoryStrength(memory, snapshot.applied.at(-1)?.timestamp, halfLife)}%`}
                        >
                          <i
                            style={{
                              width: `${memoryStrength(memory, snapshot.applied.at(-1)?.timestamp, halfLife)}%`,
                            }}
                          />
                        </span>
                      </button>
                    );
                  })}
                  {!rows.length && (
                    <p className="mono py-2 pl-2 text-[12px] text-faint">
                      No matching memories.
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="shrink-0 border-t border-line px-5 py-4">
        <button
          onClick={onSource}
          className="flex w-full items-center gap-2 border-t border-line pt-3 text-[12px] text-faint mono"
          aria-label="Inspect local event data"
        >
          <LayersIcon className="size-3" />
          LOCAL MOCK DATA <span className="ml-auto">JSON</span>
        </button>
      </div>
    </aside>
  );
}
