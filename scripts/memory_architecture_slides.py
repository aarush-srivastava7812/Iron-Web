"""Compact architecture slides; keep implemented and optional tool paths distinct."""
from base64 import b64encode
from pathlib import Path


def dashboard_visual(name, description):
    path = Path(__file__).resolve().parents[1] / "report/tinyfish_memory/dashboard-visuals" / f"{name}.jpg"
    payload = b64encode(path.read_bytes()).decode("ascii")
    return f'<figure class="dashboard-capture {name}-capture"><button class="expand-diagram" type="button" aria-label="Expand {name} diagram" aria-haspopup="dialog" data-diagram-title="{name.title()} memory diagram"><img src="data:image/jpeg;base64,{payload}" alt="{description}" width="1000" height="350"></button><figcaption>Click to expand · Dashboard architecture illustration · schematic</figcaption></figure>'


def hybrid_memory_slide():
    return '''<p class="eyebrow">02 / Architecture · hybrid memory</p>
<h2>Semantic reach. Connected evidence.</h2>
<div class="memory-comparison">
  <article><h3>Vector alone</h3>{{VECTOR_VISUAL}}<p class="strength">+ Finds meaning &amp; paraphrases</p><p class="weakness">− Similarity cannot establish truth or the latest value</p></article>
  <article><h3>Graph alone</h3>{{GRAPH_VISUAL}}<p class="strength">+ Traces relationships, sources &amp; claim history</p><p class="weakness">− Needs structured claims; exact links can miss paraphrases</p></article>
</div>
<div class="hybrid-shell">
  <div class="architecture-heading"><div><span class="eyebrow">OUR COMBINED ARCHITECTURE</span><strong>One FalkorDB store · vector + graph</strong></div><button id="tinyfish-overlay-toggle" class="integration-toggle" type="button" aria-pressed="false" aria-controls="tinyfish-memory-overlay">TinyFish integration <span aria-hidden="true" class="switch-track"></span></button></div>
  <div id="tinyfish-memory-overlay" class="memory-overlay" hidden>
    <div class="evidence-pipeline"><b>TinyFish Search</b><span>→</span><b>Fetch pages</b><span>→</span><b>Exact-quote gate</b><span>→</span><b>SQL evidence versions</b></div>
    <p>↓ Index source text + ABOUT / CITES / NEWER_OBSERVATION links into shared memory</p>
  </div>
  {{HYBRID_VISUAL}}
  <p class="overlay-rule" data-tinyfish-detail hidden>Fresh → reuse · Missing / stale → queue research · Conflicts → review. Web evidence stays separate from confirmed preferences.</p>
</div><p class="note">Shared source IDs connect semantic discovery with structured claim recall in one store. External evidence versions remain durable in SQL if graph indexing is pending.</p>'''.replace("{{VECTOR_VISUAL}}", dashboard_visual("vector", "Dashboard vector illustration: query and nearby semantic clusters")).replace("{{GRAPH_VISUAL}}", dashboard_visual("graph", "Dashboard knowledge graph illustration: sources, claims, entities and provenance")).replace("{{HYBRID_VISUAL}}", dashboard_visual("hybrid", "Dashboard hybrid illustration: shared sources, vector and graph retrieval, then agent context"))


def tinyfish_agents_slide():
    roles = [("Atlas", "Explore destinations", "Search"),
             ("Haven", "Research stays", "Search · Fetch*"),
             ("Saffron", "Discover food", "Search · Fetch*"),
             ("Roam", "Research attractions", "Search · Fetch*")]
    cards = ''.join(f'<div class="research-role"><strong>{name}</strong><span>{task}</span><small>{tools}</small></div>' for name, task, tools in roles)
    return '''<p class="eyebrow">03 / Architecture · nine coordinated roles</p>
<h2>Agents coordinate. TinyFish researches.</h2>
<div class="agent-architecture">
  <div class="orchestrator-box"><strong>Travel orchestrator</strong><span>Delegates work · decides when current evidence is needed</span></div>
  <div class="down-connector" aria-hidden="true">↓</div>
  <div class="planning-roles"><span>Trip consultant</span><span>Itinerary planner</span><span>Budget / booking</span><span>Travel support</span></div>
  <div class="context-bus">↕ Shared memory + evidence context ↕</div>
  <div class="research-roles">''' + cards + '''</div>
  <div class="tool-connector" aria-hidden="true">↓&emsp;↓&emsp;↓&emsp;↓</div>
  <div class="tool-belt">
    <article><span class="tool-state">DEFAULT · ALL FOUR</span><h3>Search</h3><p>Public destination query → source URLs</p></article>
    <article><span class="tool-state">CONDITIONAL*</span><h3>Fetch</h3><p>URL → readable page → quoted evidence</p></article>
    <article class="optional-tool"><span class="tool-state">OPTIONAL ADAPTER</span><h3>Agent</h3><p>Browser goal → async run → polled result</p></article>
  </div>
</div><p class="note">*Venue extraction uses Fetch when a reader is configured. Agent can replace the default client; it is not an automatic fallback. Roles are implemented locally.</p>
<p class="agent-boundary">Memory write path: destination research job → Search + Fetch → validated SQL evidence → graph + vector indexing. Role results need an explicit bridge to enter that ledger.</p>'''
