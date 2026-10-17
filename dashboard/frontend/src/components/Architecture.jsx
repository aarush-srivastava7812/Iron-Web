import {
  TIERS,
  tierKey,
  fileName,
  contentBytes,
  memoryStrength,
} from "../memory.js";

export default function Architecture({
  snapshot,
  activeEvent,
  onTier,
  onMemory,
  halfLife,
}) {
  const now = snapshot.applied.at(-1)?.timestamp;
  return (
    <div
      className="alternate-view architecture-view"
      data-testid="memory-architecture"
    >
      <div className="view-heading">
        <div>
          <span className="eyebrow">THREE-TIER ARCHITECTURE</span>
          <h2>From working context to shared evidence.</h2>
        </div>
      </div>
      <p className="mb-6 max-w-xl text-xs leading-6 text-muted">
        This is the architecture represented by the mock memory paths. Content
        sizes measure this snapshot's JSON/text, not live RAM, GPU or database
        allocation.
      </p>
      <div className="tier-cards">
        {Object.entries(TIERS).map(([key, tier]) => {
          const memories = [...snapshot.memories.values()].filter(
            (memory) => tierKey(memory.path) === key,
          );
          return (
            <section
              key={key}
              className={`architecture-tier ${activeEvent && tierKey(activeEvent.memoryPath) === key ? "active" : ""}`}
            >
              <button
                className="tier-card-heading"
                onClick={() => onTier(key)}
                aria-label={`Inspect ${tier.name} tier`}
              >
                <span className="mono text-memory">{tier.number}</span>
                <span>
                  <strong>{tier.name}</strong>
                  <small>{tier.description}</small>
                </span>
                <span className="mono text-[12px] text-muted">
                  {tier.storage}
                </span>
              </button>
              <div className="tier-metrics mono">
                <span>
                  <strong>{memories.length}</strong> memories
                </span>
                <span>
                  <strong>{contentBytes(memories).toLocaleString()}</strong>{" "}
                  content bytes
                </span>
              </div>
              <div className="tier-memory-list">
                {memories.map((memory) => (
                  <button
                    key={memory.path}
                    onClick={() => onMemory(memory.path)}
                    className="tier-memory"
                  >
                    <span className="mono truncate">
                      {fileName(memory.path)}
                    </span>
                    <span
                      className="memory-decay"
                      title={`Illustrative retention: ${memoryStrength(memory, now, halfLife)}%, using a ${halfLife}s half-life`}
                    >
                      <i
                        style={{
                          width: `${memoryStrength(memory, now, halfLife)}%`,
                        }}
                      />
                    </span>
                    <span className="mono text-faint">v{memory.version}</span>
                  </button>
                ))}
                {!memories.length && (
                  <p className="p-4 text-xs text-faint">
                    No memories in this tier at the selected event.
                  </p>
                )}
              </div>
            </section>
          );
        })}
      </div>
      <p className="mono mt-5 text-[12px] leading-5 text-faint">
        Retention bars are an illustrative decay model based on event time. They
        do not remove data; only a forget event does.
      </p>
    </div>
  );
}
