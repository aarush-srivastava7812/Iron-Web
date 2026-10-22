import test from "node:test";
import assert from "node:assert/strict";
import { sourceMode, matchesSource } from "../src/feedMode.js";
import { pageUrl } from "../src/dashboardRoutes.js";

test("history is the default; live requires an explicit mode that survives navigation", () => {
  assert.equal(sourceMode(""), "history");
  assert.equal(sourceMode("?event=3"), "history");
  assert.equal(sourceMode("?mode=live"), "live");
  assert.equal(sourceMode("?mode=unknown"), "history");
  assert.equal(
    pageUrl("graph", { sourceMode: "live", follow: true }),
    "/memory?mode=live",
  );
  assert.equal(
    pageUrl("history", { sourceMode: "history" }),
    "/history?mode=history",
  );
});

test("recorded values cannot be accepted as live or live account data as replay", () => {
  const replay = {
    replay: { kind: "project_demo" },
    connection: { mode: "recorded" },
  };
  const live = { connection: { mode: "website", user_id: "account-a" } };
  assert.equal(matchesSource(replay, "history"), true);
  assert.equal(matchesSource(replay, "live"), false);
  assert.equal(matchesSource(live, "history"), false);
  assert.equal(matchesSource(live, "live"), true);
  assert.equal(matchesSource(null, "live"), false);
  assert.equal(matchesSource(null, "history"), false);
});
