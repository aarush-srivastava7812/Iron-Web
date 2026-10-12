document.addEventListener("DOMContentLoaded", () => {
  // Tab Switching
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = `tab-${btn.dataset.tab}`;
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.classList.add("active");
      }
    });
  });

  // Live Status & GPU Telemetry Polling
  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) return;
      const data = await res.json();
      
      const dev = data.device || {};
      const actProv = document.getElementById("activeProviderVal");
      const vramVal = document.getElementById("vramUsageVal");
      const vramBar = document.getElementById("vramProgressBar");
      const gpuText = document.getElementById("gpuNameText");
      const provNotes = document.getElementById("providerNotes");

      if (actProv) actProv.textContent = dev.embedder_provider || dev.execution_mode || "CUDA";
      if (gpuText) gpuText.textContent = dev.execution_mode === "GPU (CUDA)" ? "NVIDIA RTX 4050 (CUDA)" : dev.execution_mode;
      if (provNotes) provNotes.textContent = dev.status_notes || "RTX 4050 Active";

      if (dev.vram_used_mb && dev.vram_total_mb) {
        const used = Math.round(dev.vram_used_mb);
        const total = Math.round(dev.vram_total_mb);
        const pct = Math.min(Math.round((used / total) * 100), 100);
        if (vramVal) vramVal.textContent = `${used.toLocaleString()} MB / ${total.toLocaleString()} MB`;
        if (vramBar) vramBar.style.width = `${pct}%`;
      }
    } catch (err) {
      console.warn("Telemetry fetch error:", err);
    }
  }

  // Poll status initially and every 3 seconds
  fetchStatus();
  setInterval(fetchStatus, 3000);

  // Live Search Execution
  const searchBtn = document.getElementById("searchSubmitBtn");
  const queryInput = document.getElementById("searchQueryInput");
  const modeSelect = document.getElementById("retrievalModeSelect");
  const topKInput = document.getElementById("topKInput");
  const temporalSelect = document.getElementById("temporalModeSelect");
  const resultsContainer = document.getElementById("searchResultsContainer");
  const resultsMeta = document.getElementById("resultsMeta");

  async function executeSearch() {
    const query = queryInput.value.trim();
    if (!query) return;

    searchBtn.disabled = true;
    searchBtn.textContent = "Inferencing on GPU...";
    resultsContainer.innerHTML = `<div class="empty-state">Running neural query with NVIDIA RTX 4050 GPU acceleration...</div>`;

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          retrieval_mode: modeSelect.value,
          k: parseInt(topKInput.value) || 5,
          temporal_mode: temporalSelect.value
        })
      });

      const data = await res.json();
      searchBtn.disabled = false;
      searchBtn.textContent = "Search Memory";

      if (data.error) {
        resultsContainer.innerHTML = `<div class="empty-state" style="color: var(--rose);">Error: ${data.error}</div>`;
        return;
      }

      resultsMeta.textContent = `GPU Latency: ${data.latency_ms} ms | Retrieved: ${data.count} records | Mode: ${data.mode.toUpperCase()}`;

      if (!data.results || data.results.length === 0) {
        resultsContainer.innerHTML = `<div class="empty-state">Zero memory records matched this query.</div>`;
        return;
      }

      resultsContainer.innerHTML = data.results.map((r, idx) => `
        <div class="result-card">
          <div class="result-card-header">
            <div>
              <span class="result-id">#${idx + 1} &bull; ${r.memory_id}</span>
              ${r.entity_ids && r.entity_ids.length ? `<span class="badge badge-cyan" style="margin-left: 8px;">Entities: ${r.entity_ids.join(", ")}</span>` : ''}
            </div>
            <span class="result-score">Score: ${r.score}</span>
          </div>
          <div class="result-content">${escapeHtml(r.content)}</div>
          ${r.retrieval_trace ? `
            <div class="result-trace">
              Trace: vector_score: ${r.retrieval_trace.vector_score ?? 'N/A'} | final_score: ${r.retrieval_trace.final_score ?? r.score} | rank: ${r.retrieval_trace.selection_rank ?? idx + 1}
            </div>
          ` : ''}
        </div>
      `).join("");

    } catch (err) {
      searchBtn.disabled = false;
      searchBtn.textContent = "Search Memory";
      resultsContainer.innerHTML = `<div class="empty-state" style="color: var(--rose);">Network/Inference error: ${err.message}</div>`;
    }
  }

  if (searchBtn) searchBtn.addEventListener("click", executeSearch);
  if (queryInput) {
    queryInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") executeSearch();
    });
  }

  // Quick Query chips
  document.querySelectorAll(".chip-btn").forEach(chip => {
    chip.addEventListener("click", () => {
      queryInput.value = chip.dataset.q;
      executeSearch();
    });
  });

  // Ingest Form Execution
  const ingestBtn = document.getElementById("ingestSubmitBtn");
  const ingestContent = document.getElementById("ingestContentInput");
  const ingestEntities = document.getElementById("ingestEntitiesInput");
  const ingestImportance = document.getElementById("ingestImportanceInput");
  const ingestStatus = document.getElementById("ingestStatusMsg");

  if (ingestBtn) {
    ingestBtn.addEventListener("click", async () => {
      const content = ingestContent.value.trim();
      if (!content) return;

      ingestBtn.disabled = true;
      ingestBtn.textContent = "Ingesting...";
      ingestStatus.textContent = "";

      const entities = ingestEntities.value.split(",").map(e => e.trim()).filter(Boolean);
      const importance = parseFloat(ingestImportance.value) || 1.0;

      try {
        const res = await fetch("/api/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            content: content,
            entity_ids: entities,
            importance: importance
          })
        });

        const data = await res.json();
        ingestBtn.disabled = false;
        ingestBtn.textContent = "Store Memory Record";

        if (data.success) {
          ingestStatus.textContent = `Memory stored! ID: ${data.memory_id} (Qdrant & Kùzu synchronized)`;
          ingestContent.value = "";
          ingestEntities.value = "";
        } else {
          ingestStatus.textContent = `Error: ${data.error}`;
          ingestStatus.style.color = "var(--rose)";
        }
      } catch (err) {
        ingestBtn.disabled = false;
        ingestBtn.textContent = "Store Memory Record";
        ingestStatus.textContent = `Failed: ${err.message}`;
        ingestStatus.style.color = "var(--rose)";
      }
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
});
