import "./memory-architecture-visuals.css";

// Architecture illustrations, deliberately separate from the dashboard's measured data.
export default function MemoryArchitectureVisuals() {
  return (
    <div className="memory-visual-gallery" aria-label="Vector, graph and hybrid memory illustrations">
      <section className="memory-visual-card" data-memory-visual="vector">
        <header><span>IRON WEB / MEMORY LAB</span><strong>Vector · find similar meaning</strong></header>
        <svg viewBox="0 0 720 250" role="img" aria-label="Illustration of semantic clusters, with a query finding nearby source embeddings">
          <ellipse cx="190" cy="124" rx="120" ry="75" className="visual-halo" />
          <ellipse cx="440" cy="92" rx="90" ry="53" className="visual-halo secondary" />
          <ellipse cx="495" cy="188" rx="96" ry="43" className="visual-halo tertiary" />
          {[[110,115],[150,86],[190,126],[233,93],[261,145],[154,158],[209,170],[398,66],[442,88],[481,58],[490,112],[413,118],[430,186],[473,202],[512,174],[548,201]].map(([x,y],i)=><circle key={i} cx={x} cy={y} r={i===2?8:5} className="visual-point" />)}
          <circle cx="190" cy="126" r="33" className="visual-radius" />
          <path d="M190 126L150 86M190 126L233 93M190 126L154 158" className="visual-link" />
          <path d="M278 55L213 107" className="visual-link" /><text x="280" y="49">query → nearest sources</text>
          <text x="120" y="222" className="visual-label">STAYS</text><text x="407" y="28" className="visual-label">FOOD</text><text x="546" y="164" className="visual-label">ACTIVITIES</text>
        </svg>
        <footer>Architecture illustration · positions are schematic, not measured embeddings</footer>
      </section>
      <section className="memory-visual-card" data-memory-visual="graph">
        <header><span>IRON WEB / MEMORY LAB</span><strong>Knowledge graph · trace the evidence</strong></header>
        <svg viewBox="0 0 720 250" role="img" aria-label="Source connected to claim and entity, with citation and version history">
          <path d="M145 125L345 65L575 125M145 125L345 192L575 125M345 65L345 192" className="visual-link" />
          <g className="visual-edge-label"><text x="193" y="77">SUPPORTS</text><text x="428" y="77">ABOUT</text><text x="196" y="184">CITES</text><text x="427" y="184">VERSION</text><text x="359" y="131">HISTORY</text></g>
          {[[145,125,"Source"],[345,65,"Claim"],[575,125,"Entity"],[345,192,"Page / version"]].map(([x,y,label])=><g key={label}><rect x={x-65} y={y-24} width="130" height="48" rx="14" className="visual-node"/><text x={x} y={y+5} textAnchor="middle" className="visual-node-label">{label}</text></g>)}
        </svg>
        <footer>Architecture illustration · explicit relationships, provenance and claim history</footer>
      </section>
      <section className="memory-visual-card hybrid-visual-card" data-memory-visual="hybrid">
        <header><span>IRON WEB / MEMORY LAB</span><strong>Hybrid · one store, two complementary retrieval paths</strong></header>
        <svg viewBox="0 0 1000 230" role="img" aria-label="Shared sources flow into vector search and graph recall in FalkorDB, then into agent context">
          <rect x="275" y="20" width="440" height="189" rx="20" className="visual-store"/>
          <text x="495" y="47" textAnchor="middle" className="visual-label">FALKORDB · SHARED SOURCE IDS</text>
          <path d="M205 115H320M205 115L320 88M205 115L320 157M665 88L790 115M665 157L790 115" className="visual-link"/>
          <g className="visual-node-label"><rect x="25" y="88" width="180" height="54" rx="12" className="visual-node"/><text x="115" y="121" textAnchor="middle">Sources + claims</text>
          <rect x="320" y="65" width="345" height="48" rx="12" className="visual-node"/><text x="492" y="95" textAnchor="middle">Vector → semantic discovery</text>
          <rect x="320" y="133" width="345" height="48" rx="12" className="visual-node"/><text x="492" y="163" textAnchor="middle">Graph → scoped claim recall</text>
          <rect x="790" y="88" width="185" height="54" rx="12" className="visual-output"/><text x="882" y="121" textAnchor="middle" fill="white">Agent context</text></g>
          <text x="736" y="107" className="visual-arrow">→</text><text x="237" y="107" className="visual-arrow">→</text>
        </svg>
        <footer>Architecture illustration · semantic search and exact claim recall share durable sources</footer>
      </section>
    </div>
  );
}
