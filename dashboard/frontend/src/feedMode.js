export function sourceMode(search) {
  return new URLSearchParams(search).get("mode") === "live"
    ? "live"
    : "history";
}

export function matchesSource(payload, mode) {
  if (!payload) return false;
  return mode === "history"
    ? payload?.replay?.kind === "project_demo" &&
        payload?.connection?.mode === "recorded"
    : !payload?.replay && payload?.connection?.mode !== "recorded";
}
