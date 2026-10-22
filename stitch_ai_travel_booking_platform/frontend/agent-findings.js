// Only traveler-facing findings are rendered here. Execution traces belong in diagnostics.
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const titles = {trip_consultant:"Your trip preferences", explore_agent:"Destination ideas", stay_agent:"Where to stay", tour_guide_agent:"Things to do", food_guide_agent:"Where to eat", itinerary_planner:"Your day-by-day plan", budget_booking_agent:"Your trip budget", travel_support_agent:"Before you travel"};
const money = n => n == null ? "Price to confirm" : "₹" + Number(n).toLocaleString("en-IN");
const displayText = value => /<\s*\/?\s*(?:think|analysis|reasoning)\b|\[\/?(?:analysis|reasoning)\]|API[_ -]?KEY|Bearer\s+|Traceback|system prompt|tool_calls|source_quote|retention_base|CUDAExecutionProvider/i.test(String(value ?? "")) ? "" : String(value ?? "");
export function publicSource(value) {
  try {
    const u = new URL(value);
    if(u.protocol !== "https:" || u.username || u.password || !u.hostname.includes(".") || /(?:^|\.)(?:localhost|local)$/.test(u.hostname) || /^[\d.]+$/.test(u.hostname) || u.hostname.includes(":"))return null;
    return u.href;
  } catch {return null;}
}
const link = (url, label="Research source") => {
  const safe = publicSource(url);
  return safe ? `<a href="${esc(safe)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : "";
};
export const sourceLink = evidence => evidence?.source === "tinyfish.web" ? link(evidence.ref) : "";

export function stopCost(stop, choices = []) {
  if(stop.kind === "buffer")return "Time reserved";
  const option = choices.find(o => stop.title === o.name || stop.title === "Lunch at " + o.name);
  const amount = option ? (stop.kind === "food" ? option.approx_price_per_guest_inr : option.price_per_person_inr) : stop.est_cost_inr;
  if(amount == null || (!option && stop.evidence?.source === "tinyfish.web" && amount === 0))return "Price to confirm";
  return money(amount) + (["food", "attraction"].includes(stop.kind) ? " / guest" : "");
}

function savedFindings(result) {
  // Older saved plans have no presentation. Reconstruct from travel data only.
  const rows = result.stay_options?.length ? result.stay_options.map(o=>({title:o.name,detail:[o.location,...(o.pros||[])].filter(Boolean).join(" · "),price:o.price_per_night_inr == null ? "Nightly rate to confirm" : money(o.price_per_night_inr)+" per room / night",source_url:o.evidence?.source === "tinyfish.web" ? o.evidence.ref : null}))
    : result.food_options?.length ? result.food_options.map(o=>({title:o.name,detail:[o.cuisine,o.dietary_fit].filter(Boolean).join(" · "),price:o.approx_price_per_guest_inr == null ? "Meal price to confirm" : money(o.approx_price_per_guest_inr)+" per guest / meal",source_url:o.evidence?.source === "tinyfish.web" ? o.evidence.ref : null}))
    : (result.attractions?.length ? result.attractions : result.destination_ideas||[]).map(o=>({title:o.name,detail:o.why_fit||o.location||o.region||"",source_url:o.evidence?.source === "tinyfish.web" ? o.evidence.ref : null}));
  if(result.itinerary)rows.splice(0,rows.length,...result.itinerary.days.slice(0,7).map(d=>({title:`Day ${d.day}`,detail:d.stops.map(s=>`${s.start_time}: ${s.title}`).join("; ")})));
  if(result.budget)rows.splice(0,rows.length,...result.budget.lines.map(l=>({title:l.category,detail:l.note,price:money(l.amount_inr)})));
  const failed=result.status === "failed";
  const hasFindings=rows.length>0;
  return {title:titles[result.agent_id]||"Your travel team",status:failed?"unavailable":hasFindings?"ready":"needs_review",
    overview:failed?"This part could not be completed. Review your trip details before retrying.":result.budget?.costs_complete === false?"The full trip total is still unknown. Listed amounts are a known-cost subtotal.":hasFindings?"Review these options and details for your trip.":"There is not enough checked detail to recommend an option yet.",
    findings:failed?[]:rows.slice(0,7),notes:["Confirm current prices, availability and your requirements with the supplier."],sources:failed?[]:(result.evidence||[]).filter(e=>e.source==="tinyfish.web").map(e=>e.ref)};
}

export function agentWork(results = []) {
  const views = (Array.isArray(results)?results:[]).filter(r=>titles[r.agent_id]).map(r=>({result:r,view:r.presentation||savedFindings(r)}));
  if(!views.length)return "";
  const labels={ready:"Ready to review",needs_review:"Needs confirmation",unavailable:"Could not complete"};
  return `<details class="agent-work"><summary>Your travel team's findings</summary><div class="agent-work-grid">${views.map(({result,view})=>{
    const findings=(view.findings||[]).filter(f=>displayText(f.title));
    const cited=new Set(findings.map(f=>publicSource(f.source_url)).filter(Boolean));
    const links=[...new Set((view.sources||[]).map(publicSource).filter(url=>url&&!cited.has(url)))].slice(0,3);
    return `<article><b>${esc(titles[result.agent_id])}</b><span>${esc(labels[view.status]||labels.needs_review)}${result.execution?.mode==="tinyfish"?" · TinyFish web research":""}</span><p>${esc(displayText(view.overview))}</p>${findings.length?`<ul class="agent-findings">${findings.map(f=>`<li><strong>${esc(displayText(f.title))}</strong>${f.detail?`<p>${esc(displayText(f.detail))}</p>`:""}${f.price?`<p>${esc(displayText(f.price))}</p>`:""}${link(f.source_url)}</li>`).join("")}</ul>`:""}${(view.notes||[]).map(n=>`<p class="agent-finding-note">${esc(displayText(n))}</p>`).join("")}${links.length?`<nav class="agent-sources" aria-label="${esc(titles[result.agent_id])} sources">${links.map((url,i)=>link(url,`Source ${i+1} · ${new URL(url).hostname}`)).join(" ")}</nav>`:""}</article>`;
  }).join("")}</div></details>`;
}
