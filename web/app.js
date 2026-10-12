"use strict";
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
      card.append(node("h3", result.memory_id), node("p", result.content), node("small", `Score ${result.score === null ? "Unavailable" : result.score.toFixed(4)} · ${result.retrieval_method}`));
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
