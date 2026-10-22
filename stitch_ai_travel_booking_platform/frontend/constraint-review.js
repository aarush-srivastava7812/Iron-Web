const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const labels={destination:"Destination",origin:"Starting city",start_date:"Departure",end_date:"Return",duration_days:"Days",traveller_count:"Travelers",budget:"Maximum total budget",dietary:"Dietary requirement",transport_mode:"Travel by",pace:"Pace",interests:"Interests",hotel_style:"Stay style",seat_preference:"Seat preference"};
const value=(key,item)=>key==="budget"?`₹${Number(item).toLocaleString("en-IN")} for the group`:Array.isArray(item)?item.join(", "):String(item);

function constraintPanel(analysis) {
  if(!analysis||(!Object.keys(analysis.facts||{}).length&&!analysis.soft_preferences?.length&&!analysis.hard_constraints?.length&&!Object.keys(analysis.preferences||{}).length))return "";
  const facts=Object.entries(analysis.facts||{}).map(([key,item])=>`<li><b>${esc(labels[key]||key)}:</b> ${esc(value(key,item))}</li>`).join("");
  const preferences=[...Object.entries(analysis.preferences||{}).map(([key,item])=>`${labels[key]||key}: ${value(key,item)}`),...(analysis.soft_preferences||[])];
  return `<section class="journey-constraint-agent" aria-label="Query Constraint Agent"><header><strong>Query Constraint Agent</strong><small>${analysis.mode==="nvidia"?"AI extraction + validation":"Local deterministic extraction"}</small></header><p>Here’s how I understood your request. Review before confirming.</p><div class="journey-constraint-groups"><section><h4>Facts & firm constraints</h4><ul>${facts||"<li>No firm trip details yet.</li>"}${(analysis.hard_constraints||[]).map(item=>`<li>${esc(item)} <small>Needs supplier verification</small></li>`).join("")}</ul></section><section><h4>Preferences</h4><p>Guide ranking; can be traded off.</p><ul>${preferences.map(item=>`<li>${esc(item)}</li>`).join("")||"<li>No preferences stated.</li>"}</ul></section></div>${analysis.clarification_questions?.length?`<p class="journey-warning">${analysis.clarification_questions.map(esc).join(" ")}</p>`:""}</section>`;
}

export function constraintReview(analysis) {
  const panel=constraintPanel(analysis);
  return panel?`<details class="journey-understanding"><summary>How I understood your trip</summary>${panel}</details>`:"";
}
