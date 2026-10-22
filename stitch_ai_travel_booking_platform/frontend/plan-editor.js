import "./plan-editor.css";
import { agentWork, sourceLink, stopCost as formatStopCost } from "./agent-findings.js";
export { agentWork } from "./agent-findings.js";

const esc = (x) => String(x ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const stayRef = s => s.stay_id != null ? "catalog:" + s.stay_id : "web:" + JSON.stringify([s.evidence?.ref, s.name]);
const money = n => n == null ? "Price unknown" : "₹" + Number(n).toLocaleString("en-IN");

export async function mountPlanEditor(host, tripId, api) {
  const path = "/assistant/conversations/" + encodeURIComponent(tripId) + "/plan";
  let saved;
  try { saved = await api(path); }
  catch (e) { host.textContent = "Saved draft could not load: " + e.message; return; }
  if (!host.isConnected) return;
  if (!saved) { host.textContent = "Generate a day-by-day trip to open the saved editor."; return; }

  const candidates = (agent, field) => saved.plan.agent_results.find(r => r.agent_id === agent)?.[field] || [];
  const render = () => {
    const p = saved.plan, b = p.budget, stays = candidates("stay_agent", "stay_options");
    const stopCost = stop => {
      const choices = stop.kind === "food" ? candidates("food_guide_agent", "food_options") : stop.kind === "attraction" ? candidates("tour_guide_agent", "attractions") : [];
      return formatStopCost(stop, choices);
    };
    const disabled = saved.stale ? "disabled" : "";
    const controls = (s, d, i) => {
      if (!["food", "attraction"].includes(s.kind)) return "";
      const options = s.kind === "food" ? candidates("food_guide_agent", "food_options") : candidates("tour_guide_agent", "attractions");
      return `<div class="stop-controls"><select aria-label="Alternative for ${esc(s.title)}" ${disabled}>${options.map((o, j) => `<option value="${j}" ${s.title.includes(o.name) ? "selected" : ""}>${esc(o.name)} · ${money(s.kind === "food" ? o.approx_price_per_guest_inr : o.price_per_person_inr)} / guest</option>`).join("")}</select><button class="mini-btn" data-plan-action="replace" data-day="${d}" data-stop="${i}" ${disabled}>Swap</button><button class="mini-btn" aria-label="Move ${esc(s.title)} earlier" data-plan-action="move_up" data-day="${d}" data-stop="${i}" ${disabled}>↑</button><button class="mini-btn" aria-label="Move ${esc(s.title)} later" data-plan-action="move_down" data-day="${d}" data-stop="${i}" ${disabled}>↓</button><button class="mini-btn" data-plan-action="remove" data-day="${d}" data-stop="${i}" ${disabled}>Remove</button></div>`;
    };
    host.innerHTML = `<section class="travel-plan"><div class="plan-heading"><div><span class="tag">TRAVEL DRAFT · VERSION ${saved.version}</span><h2>${esc(p.itinerary.title)}</h2><p>${esc(p.trip_brief.party_size)} travellers · ${esc(p.trip_brief.pace || "moderate")} pace · saved to this conversation</p></div><button class="mini-btn" data-plan-action="export">Export itinerary</button></div>${saved.stale ? '<p class="plan-caveat" role="status">Requirements changed. This is an older saved draft. Generate a new plan before editing or restoring versions.</p>' : ""}<div class="plan-editor-layout"><div>${p.itinerary.days.map((d, di) => `<article class="plan-day"><h3>Day ${d.day} <small>${esc(d.calendar_date)}</small></h3>${d.stops.map((s, si) => `<div class="plan-stop"><span class="stop-time">${esc(s.start_time)}–${esc(s.end_time)}</span><div><b>${esc(s.title)}</b><p>${esc(s.notes || s.kind)} · ${stopCost(s)}</p>${sourceLink(s.evidence)}${controls(s,di,si)}</div></div>`).join("") || "<p>Free day. Restore an earlier version to bring back removed activities.</p>"}</article>`).join("")}</div><aside class="plan-cost"><h3>${b.costs_complete===false?"Known-cost subtotal; trip total unknown":"Indicative estimate"}</h3><strong class="estimate-total">${b.costs_complete===false && b.total_inr===0?"Awaiting quotes":money(b.total_inr)}</strong><p>For all ${esc(p.trip_brief.party_size)} travellers · listed items only</p><dl>${b.lines.map(l => `<div><dt>${esc(l.category)}</dt><dd>${money(l.amount_inr)}</dd></div>`).join("")}</dl><p class="plan-delta">${p.delta_inr === undefined ? "Initial draft" : (p.delta_inr >= 0 ? "+" : "−") + money(Math.abs(p.delta_inr)) + " from previous version"}</p><p>${b.costs_complete === false ? "Budget fit: awaiting complete costs" : "Budget remaining: <b>" + money(p.trip_brief.budget_total_inr - b.total_inr) + "</b>"}</p>${stays.length ? `<label>Selected stay<select id="planStay" ${disabled}>${stays.map((s,i) => `<option value="${i}" ${(p.selected_stay_ref ? stayRef(s) === p.selected_stay_ref : s.stay_id === p.selected_stay_id) ? "selected" : ""}>${esc(s.name)} · ${money(s.price_per_night_inr)} / room / night</option>`).join("")}</select></label><button class="mini-btn" data-plan-action="stay" ${disabled}>Update stay & estimate</button>` : '<p>No stay is included.</p>'}<details><summary>Inclusions & assumptions</summary><ul>${b.warnings.concat(p.itinerary.assumptions).map(x => `<li>${esc(x)}</li>`).join("")}</ul><p>One room assumed. Occupancy, other meals, intercity travel, taxes, opening hours and route timing require verification. Catalog listings are synthetic; TinyFish web findings are labeled and source-linked. Web rates are indicative and not date-specific quotes. No supplier booking is made.</p></details><label>Compare a saved version<select id="planHistory">${saved.history.map(v => `<option value="${v.version}">Version ${v.version} · ${money(v.total_inr)} · ${esc(v.change)}</option>`).join("")}</select></label><p id="planComparison" class="plan-delta"></p><button class="mini-btn" data-plan-action="restore" ${disabled}>Restore selected version</button><p id="planSaveState" role="status" aria-live="polite">All changes saved.</p></aside></div>${agentWork(p.agent_results)}</section>`;
    const comparison = host.querySelector("#planHistory");
    const bookLink=document.createElement("a");bookLink.className="mini-btn";bookLink.href="#travel-book/"+encodeURIComponent(tripId);bookLink.textContent="Open personal Travel Book";host.querySelector(".plan-heading").append(bookLink);
    comparison.onchange = () => {
      const previous = saved.history.find(v => v.version === Number(comparison.value));
      const delta = b.total_inr - previous.total_inr;
      host.querySelector("#planComparison").textContent = `Current draft ${delta >= 0 ? "costs " + money(delta) + " more" : "saves " + money(-delta)} compared with version ${previous.version}.`;
    };
    comparison.onchange();
  };
  render();
  host.onclick = async event => {
    const button = event.target.closest("[data-plan-action]");
    if (!button || button.disabled) return;
    const action = button.dataset.planAction;
    if (action === "export") {
      const p = saved.plan;
      const text = [p.itinerary.title, `Hackathon draft v${saved.version}${saved.stale ? " · OUTDATED REQUIREMENTS" : ""}`,
        ...p.itinerary.days.flatMap(d => [`\nDay ${d.day} · ${d.calendar_date || ""}`, ...d.stops.map(s => `${s.start_time}–${s.end_time || ""} ${s.title} · ${money(s.est_cost_inr)} / guest`)]),
        "\nIndicative estimate for listed items: " + money(p.budget.total_inr),
        ...p.budget.lines.map(l => `${l.category}: ${money(l.amount_inr)}`),
        ...p.budget.warnings, ...p.itinerary.assumptions,
        "Synthetic catalog. No supplier booking. Route timing, hours, occupancy, taxes, extra meals and intercity travel remain unverified."].join("\n");
      const url = URL.createObjectURL(new Blob([text], {type:"text/plain;charset=utf-8"}));
      const link = document.createElement("a"); link.href = url; link.download = "voyara-itinerary-v" + saved.version + ".txt"; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000); return;
    }
    const request = {expected_version:saved.version, action, day:Number(button.dataset.day || 0), stop:Number(button.dataset.stop || 0)};
    if (action === "replace") request.candidate = Number(button.parentElement.querySelector("select").value);
    if (action === "stay") request.candidate = Number(host.querySelector("#planStay").value);
    if (action === "restore") request.candidate = Number(host.querySelector("#planHistory").value);
    const status = host.querySelector("#planSaveState");
    host.querySelectorAll("button,select").forEach(b => b.disabled = true);
    status.textContent = "Checking and saving your change…";
    try {
      saved = await api(path + "/edits", {method:"POST", body:request});
      if (host.isConnected) render();
      window.dispatchEvent(new CustomEvent("voyara-trip-updated",{detail:{tripId}}));
    } catch (error) {
      status.textContent = error.message;
      if (error.status === 409) {
        const refresh = document.createElement("button"); refresh.className = "mini-btn"; refresh.textContent = "Reopen latest draft";
        refresh.onclick = () => mountPlanEditor(host, tripId, api); status.append(refresh);
      }
      host.querySelectorAll("button,select").forEach(b => b.disabled = false);
    }
  };
}
