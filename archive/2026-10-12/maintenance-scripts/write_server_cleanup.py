from pathlib import Path
root=Path(__file__).resolve().parents[1]
(root/'server.py').write_text('''"""Local memory dashboard and JSON API. Report values come only from saved verified runs."""
from __future__ import annotations
import json
import logging
import sys
import time
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from memory.engine import MemoryEngine
from memory.models import EngineStorageError

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
_ENGINE = None
_START_TIME = time.time()


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = MemoryEngine()
    return _ENGINE


def load_verified_reports(directory=None):
    directory = Path(directory) if directory is not None else ROOT/"data/results"
    reports, invalid = [], []
    for path in sorted(directory.rglob("*_summary.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("protocol") == "local_retrieval_v2" and isinstance(data.get("evaluation"), dict) and len(data.get("fingerprint", "")) == 64:
                reports.append(data)
        except (ValueError, OSError, AttributeError) as error:
            logger.warning("Unreadable evaluation report %s: %s", path.name, error)
            invalid.append(path.name)
    return dict(status="available" if reports else "no_verified_results", reports=reports, unreadable_reports=invalid)


class IronWebHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT/"web"), **kwargs)

    def _send_json(self, data, status=200):
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/status":
                engine = get_engine()
                self._send_json(dict(timestamp=int(time.time()), server=dict(status="ONLINE", uptime_sec=int(time.time()-_START_TIME)),
                    device=engine.get_device_status().model_dump(),
                    storage=dict(memories=engine.vector_store.count(), nodes=engine.graph_store.get_node_counts())))
            elif path in {"/api/results", "/api/ablations"}:
                self._send_json(load_verified_reports())
            elif path == "/api/competitors":
                self._send_json(dict(status="no_verified_comparison", comparisons=[]))
            elif path.startswith("/api/"):
                self._send_json({"error": "Endpoint not found"}, 404)
            else:
                return super().do_GET()
        except Exception:
            logger.exception("GET request failed")
            self._send_json({"error": "Request failed; see the server log for details."}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/api/add", "/api/search"}:
            return self._send_json({"error": "Endpoint not found"}, 404)
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            return self._send_json({"error": "Cross-origin writes are unavailable."}, 403)
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._send_json({"error": "Content-Type must be application/json."}, 415)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 1_048_576:
                return self._send_json({"error": "Request body must contain at most 1 MiB of JSON."}, 413)
            def invalid_number(value):
                raise ValueError("JSON numbers must be finite.")
            body = json.loads(self.rfile.read(size).decode("utf-8"), parse_constant=invalid_number)
            if not isinstance(body, dict):
                raise ValueError("Request must be a JSON object.")
            if path == "/api/search":
                allowed = {"query", "k", "temporal_mode", "query_time", "retrieval_mode"}
                if set(body)-allowed:
                    raise ValueError("Unknown search fields.")
                if not isinstance(body.get("query"), str) or not body["query"].strip():
                    raise ValueError("Query must be a nonempty string.")
                started = time.perf_counter()
                results = get_engine().search(**body)
                self._send_json(dict(query=body["query"], count=len(results),
                    latency_ms=(time.perf_counter()-started)*1000, results=[r.model_dump() for r in results]))
            else:
                allowed = {"content", "metadata", "entity_ids", "timestamp", "valid_from", "valid_until", "importance", "memory_id"}
                if set(body)-allowed:
                    raise ValueError("Unknown memory fields.")
                mid = get_engine().add(**body)
                self._send_json(dict(success=True, memory_id=mid), 201)
        except (ValueError, TypeError, UnicodeError) as error:
            self._send_json({"error": str(error)}, 400)
        except EngineStorageError as error:
            logger.exception("Storage operation failed")
            self._send_json({"error": "Storage operation failed.", "rolled_back": error.rolled_back}, 500)
        except Exception:
            logger.exception("POST request failed")
            self._send_json({"error": "Request failed; see the server log for details."}, 500)


def run_server(port=8080):
    logging.basicConfig(level=logging.INFO)
    server = ThreadingHTTPServer(("127.0.0.1", port), IronWebHandler)
    logger.info("Memory dashboard: http://127.0.0.1:%s/", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if _ENGINE is not None:
            _ENGINE.close()


if __name__ == "__main__":
    run_server(int(sys.argv[1]) if len(sys.argv) > 1 else 8080)
''',encoding='utf-8')
(root/'web/index.html').write_text('''<!doctype html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Iron Web memory</title><link rel="stylesheet" href="style.css"><script src="app.js" defer></script></head>
<body><main><header><h1>Iron Web memory</h1><p>Save and search local memories, with optional graph relationships and time filtering.</p></header>
<section aria-labelledby="statusTitle"><h2 id="statusTitle">Current status</h2><p id="status" role="status">Loading status…</p>
<dl id="device"></dl></section>
<section aria-labelledby="searchTitle"><h2 id="searchTitle">Search memories</h2>
<form id="searchForm"><label for="query">Search query</label><input id="query" name="query" required>
<div class="fields"><label>Search method<select id="mode"><option value="hybrid">Vector and graph</option><option value="vector">Vector</option><option value="graph">Graph</option></select></label>
<label>Time filter<select id="timeMode"><option value="auto">All validity periods</option><option value="now">Valid at the reference time</option><option value="historical">Expired before the reference time</option></select></label>
<label>Reference time<input id="referenceTime" type="datetime-local"></label><label>Results<input id="count" type="number" min="1" max="100" value="5" required></label></div>
<button type="submit">Search</button></form><p id="searchStatus" role="status"></p><div id="results"></div></section>
<section aria-labelledby="addTitle"><h2 id="addTitle">Save a memory</h2><form id="addForm">
<label for="content">Memory text</label><textarea id="content" rows="4" required></textarea>
<div class="fields"><label>Related topics, separated by commas<input id="entities"></label>
<label>Importance<input id="importance" type="number" min="0" max="1" step="0.05" value="1" required></label></div>
<button type="submit">Save memory</button></form><p id="addStatus" role="status"></p></section>
<section aria-labelledby="reportsTitle"><h2 id="reportsTitle">Recorded evaluations</h2>
<p>These local evaluations identify their data coverage and scoring method. Smoke tests use development data or test fixtures.</p>
<button id="refreshReports" type="button">Refresh evaluations</button><p id="reportStatus" role="status"></p>
<div class="table-wrap"><table><thead><tr><th>Benchmark</th><th>Run</th><th>Method</th><th>Type</th><th>Examples</th><th>Failed</th><th>Recall</th><th>Mean search time</th></tr></thead><tbody id="reportRows"></tbody></table></div></section>
<footer><p>Embeddings and reranking load when requested. Hosted entity extraction requires explicit configuration. Device status reports the observed execution providers.</p></footer>
</main></body></html>''',encoding='utf-8')
(root/'web/app.js').write_text('''"use strict";
const $ = id => document.getElementById(id);
const node = (tag, text) => { const element = document.createElement(tag); element.textContent = text; return element; };
async function request(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
async function refreshStatus() {
  try {
    const data = await request("/api/status");
    $("status").textContent = `Server online · ${data.storage.memories} saved memories`;
    const device = data.device;
    $("device").replaceChildren();
    for (const [label, value] of [["Embedding provider", device.embedder_provider], ["Reranking provider", device.reranker_provider], ["GPU memory", device.vram_total_mb === null ? "Unavailable" : `${Math.round(device.vram_used_mb)} / ${Math.round(device.vram_total_mb)} MiB`]]) {
      $("device").append(node("dt", label), node("dd", value));
    }
  } catch (error) { $("status").textContent = error.message; }
}
$("searchForm").addEventListener("submit", async event => {
  event.preventDefault();
  $("searchStatus").textContent = "Searching…";
  $("results").replaceChildren();
  const body = {query: $("query").value, k: Number($("count").value), retrieval_mode: $("mode").value, temporal_mode: $("timeMode").value};
  if ($("referenceTime").value) body.query_time = Math.floor(new Date($("referenceTime").value).getTime()/1000);
  try {
    const data = await request("/api/search", body);
    $("searchStatus").textContent = `${data.count} results · ${data.latency_ms.toFixed(1)} ms`;
    for (const result of data.results) {
      const card = node("article", ""); card.className = "result-card";
      card.append(node("h3", result.memory_id), node("p", result.content), node("small", `Score ${result.score.toFixed(4)} · ${result.retrieval_method}`));
      const details = node("details", ""); details.append(node("summary", "Saved details"), node("pre", JSON.stringify({metadata: result.metadata, trace: result.retrieval_trace}, null, 2)));
      card.append(details); $("results").append(card);
    }
    if (!data.count) $("results").append(node("p", "No memories matched this search and time filter."));
    await refreshStatus();
  } catch (error) { $("searchStatus").textContent = error.message; }
});
$("addForm").addEventListener("submit", async event => {
  event.preventDefault(); $("addStatus").textContent = "Saving…";
  const body = {content: $("content").value, importance: Number($("importance").value), metadata: {source: "web_dashboard"}};
  const entities = $("entities").value.split(",").map(value => value.trim()).filter(Boolean);
  if (entities.length) body.entity_ids = entities;
  try {
    const data = await request("/api/add", body);
    $("addStatus").textContent = `Saved as ${data.memory_id}`;
    $("content").value = ""; await refreshStatus();
  } catch (error) { $("addStatus").textContent = error.message; }
});
async function refreshReports() {
  $("reportRows").replaceChildren();
  try {
    const data = await request("/api/results");
    $("reportStatus").textContent = data.reports.length ? `${data.reports.length} recorded runs. Each row describes its own corpus and settings.` : "No verified evaluation results are available.";
    for (const report of data.reports) {
      const evaluation = report.evaluation;
      const recall = evaluation.retrieval[`recall@${report.k}`];
      const latency = evaluation.latency.mean_retrieval_ms;
      const row = node("tr", "");
      for (const value of [report.benchmark, report.run_id, report.retrieval_mode, report.is_smoke_test ? "Smoke test" : "Local evaluation", evaluation.total_examples, evaluation.failed_examples, recall === undefined ? "Unscored" : `${recall.toFixed(4)} at ${report.k}`, latency === null ? "Unavailable" : `${latency.toFixed(1)} ms`]) row.append(node("td", String(value)));
      $("reportRows").append(row);
    }
    if (data.unreadable_reports.length) $("reportStatus").textContent += ` ${data.unreadable_reports.length} report files could not be read.`;
  } catch (error) { $("reportStatus").textContent = error.message; }
}
$("refreshReports").addEventListener("click", refreshReports);
refreshStatus(); refreshReports(); setInterval(refreshStatus, 10000);
''',encoding='utf-8')
(root/'web/style.css').write_text('''* { box-sizing: border-box; } body { margin: 0; background: #f4f6fa; color: #192437; font: 16px/1.55 system-ui, sans-serif; }
main { max-width: 1100px; margin: auto; padding: 32px 24px; } header, footer { padding: 12px 0; } h1 { font-size: 32px; margin: 0; } h2 { font-size: 23px; margin-top: 0; }
section { background: white; border: 1px solid #d7dfe9; border-radius: 10px; padding: 24px; margin: 24px 0; } label { display: block; font-weight: 600; margin: 10px 0; }
input, select, textarea { width: 100%; font: inherit; padding: 10px; border: 1px solid #8493a8; border-radius: 5px; background: white; color: inherit; } textarea { resize: vertical; }
button { font: inherit; background: #214fa5; color: white; border: 0; border-radius: 5px; padding: 10px 20px; cursor: pointer; } button:hover { background: #143b84; } :focus-visible { outline: 3px solid #b66b00; outline-offset: 3px; }
.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; } dl { display: grid; grid-template-columns: minmax(160px, 1fr) 2fr; gap: 8px; } dd { margin: 0; overflow-wrap: anywhere; }
.result-card { border: 1px solid #d7dfe9; padding: 16px; border-radius: 6px; margin: 16px 0; } .result-card h3 { font-size: 16px; margin: 0; overflow-wrap: anywhere; } .result-card p { white-space: pre-wrap; overflow-wrap: anywhere; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 13px; } summary { cursor: pointer; margin-top: 12px; } .table-wrap { overflow: auto; } table { border-collapse: collapse; width: 100%; } th, td { text-align: left; border-bottom: 1px solid #d7dfe9; padding: 10px; } th { white-space: nowrap; }
@media (max-width: 600px) { main { padding: 16px; } section { padding: 18px; } dl { display: block; } dd { margin: 0 0 12px; } }
''',encoding='utf-8')
