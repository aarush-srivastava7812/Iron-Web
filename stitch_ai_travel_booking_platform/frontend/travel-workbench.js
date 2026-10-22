const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const money = value => "₹" + Number(value || 0).toLocaleString("en-IN");
const clock = value => String(Math.floor(value/60)).padStart(2,"0")+":"+String(value%60).padStart(2,"0");

export async function mountTravelWorkbench(host, id, api) {
  if (!host) return;
  let trip;
  try { trip = await api(`/trips/${encodeURIComponent(id)}`); }
  catch (error) { host.textContent = error.message; return; }
  const plan=trip.plan, budget=plan?.budget;
  host.innerHTML=`<section class="travel-workbench"><span class="journey-eyebrow">CHECK THE WHOLE JOURNEY</span><h2>Travel desk</h2><p>Saved in your private trip · revision ${trip.revision} · ${esc(trip.status||"draft")}. Prices below are sample estimates; reservations are simulated.</p><div class="travel-actions"><button type="button" data-travel="generate">${plan?"Recalculate & check trip":"Build a checked trip"}</button><button type="button" data-travel="discover">Find matching destinations</button><button type="button" data-travel="duplicate">Duplicate trip</button><button type="button" data-travel="compare">Compare my trips</button></div><p class="travel-status" role="status"></p>${trip.plan_stale?'<p class="journey-warning">Trip details changed. Recalculate before using this estimate or schedule.</p>':""}${plan?`<h3>Budget, including the easy-to-miss costs</h3><table class="travel-table"><tbody>${Object.entries(budget.categories).map(([label,value])=>`<tr><th scope="row">${esc(label.replaceAll("_"," "))}</th><td>${(budget.unknown_categories||[]).includes(label)?"Unknown · fare quote needed":money(value)}</td></tr>`).join("")}</tbody><tfoot><tr><th>${budget.costs_complete===false?"Known subtotal · travel incomplete":"Total sample estimate"}</th><td>${money(budget.total_inr)}</td></tr></tfoot></table><p>${budget.costs_complete===false?esc(budget.transport?.notice||"Travel fares are unknown; this is a subtotal, not a complete trip cost."):`${money(budget.per_person_inr)} per person · ${money(budget.per_day_inr)} per day · ${money(budget.remaining_inr)} remaining.`}</p><details><summary>Price assumptions · ${esc(budget.estimated_on)}</summary><ul>${budget.assumptions.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></details>${budget.alternatives.length?`<h4>Ways to bring the cost down</h4><ul>${budget.alternatives.map(a=>`<li>${esc(a.change)}: ${money(a.estimated_saving_inr||a.extra_inr)}</li>`).join("")}</ul>`:""}<h3>Feasibility and pace</h3><p>${plan.ready?"Passes the stated estimate and schedule checks.":"Review these limits before calling the trip planned."}</p><ul>${[...plan.conflicts.map(i=>i.message),...plan.unverified_requirements,...plan.itinerary.caveats].map(x=>`<li>${esc(x)}</li>`).join("")}</ul>${plan.itinerary.days.map((day,di)=>`<details class="travel-day"><summary>${esc(day.date)} · ${esc(day.effort)} effort · ${day.effort_minutes} min</summary>${day.items.map((item,ii)=>`<div class="travel-stop"><strong>${esc(item.title)}</strong><span>${clock(item.start_minute)}–${clock(item.end_minute)} · ${item.transfer_min||0} min transfer</span>${item.kind==="activity"?`<label>Start time <input type="time" value="${clock(item.start_minute)}" data-day="${di}" data-item="${ii}"></label><button type="button" data-travel="remove" data-day="${di}" data-item="${ii}">Skip this visit</button>`:""}<small>${esc(item.assumptions||"Rest window")}</small></div>`).join("")||"Arrival, departure or recovery time; no scheduled visits."}<p>Rain option: ${esc(day.contingency?.rain||"Verify an indoor alternative.")}</p><p>Half day: ${esc(day.contingency?.half_day||"Keep the first visit.")}</p><button type="button" data-travel="half-day" data-date="${esc(day.date)}">Keep a half day</button><button type="button" data-travel="rest-day" data-date="${esc(day.date)}">Make this a rest day</button></details>`).join("")}<button type="button" data-travel="save-itinerary">Save schedule edits</button><h3>Before you go</h3><form data-form="readiness">${[["id_and_tickets","Photo ID and tickets"],["medication","Medication and prescriptions"],["charger","Charger and offline copies"],["clothing","Weather-appropriate clothing"],["hours_and_permits","Hours, permits and accessibility checked"],["transport_and_stays","Transport and stays confirmed directly"]].map(([key,label])=>`<label><input type="checkbox" name="${key}" ${trip.readiness_checks?.[key]?"checked":""}> ${esc(label)}</label>`).join("")}<button>Save readiness checklist</button><p>These are your own preparation notes; checking a box does not verify a supplier.</p></form><div class="travel-actions"><button type="button" data-travel="nearby">Nearby places & travel notes</button><button type="button" data-travel="research">Research missing destination details</button><button type="button" data-travel="research-status">Check research</button></div><p>Research checks public destination sources. Your identity and private memory stay on this server.</p>`:"<p>Add destination, dates, guests and budget in the trip details form, then build a checked trip here.</p>"}<div class="travel-results" aria-live="polite"></div><details><summary>Group discussion</summary><form data-form="collaborate"><label>Comment<input name="text" maxlength="2000" required></label><button>Add comment</button></form><ul>${(trip.collaboration||[]).map(c=>`<li>${esc(c.text||"Vote for "+c.option_id)}</li>`).join("")}</ul><form data-form="invite"><label>Invite an existing member by user ID<input name="user_id" maxlength="36" required></label><button>Add member</button></form><form data-form="vote"><label>Preferred option ID<input name="option_id" required maxlength="100"></label><button>Vote for this option</button></form></details><details><summary>Trip status and feedback</summary><form data-form="status"><label>Trip status<select name="status">${["draft","planned","completed"].map(s=>`<option ${s===trip.status?"selected":""}>${s}</option>`).join("")}</select></label><button>Save status</button></form><form data-form="feedback"><label>Preferred pace<select name="value"><option>relaxed</option><option>moderate</option><option>packed</option></select></label><label><input name="remember" type="checkbox"> Remember this explicit preference</label><button>Save feedback</button></form></details><details><summary>Simulate a reservation</summary><p>This creates a local demo record. It does not book a supplier or take payment.</p><form data-form="reservation"><label>Type<select name="kind"><option value="stay">Stay</option><option value="activity">Activity</option><option value="outbound">Outbound transport</option><option value="return">Return transport</option></select></label><label>Catalog item ID<input name="item_id" required></label><label>City<input name="city" value="${esc(trip.draft.destination||"")}" required></label><label>Starts<input name="start" type="datetime-local" required></label><label>Ends<input name="end" type="datetime-local" required></label><button>Create demo reservation</button></form></details></section>`;
  const status=host.querySelector(".travel-status"), results=host.querySelector(".travel-results");
  const mutate = async(path,body,method="POST") => {
    await api(path,{method,body:{expected_revision:trip.revision,...body}});
    await mountTravelWorkbench(host,id,api);
  };
  host.onchange=event=>{
    const input=event.target;
    if(input.dataset.day===undefined)return;
    const item=plan.itinerary.days[Number(input.dataset.day)].items[Number(input.dataset.item)];
    const [hour,minute]=input.value.split(":").map(Number), duration=item.end_minute-item.start_minute;
    item.start_minute=hour*60+minute;item.end_minute=item.start_minute+duration;
  };
  host.onclick=async event=>{
    const button=event.target.closest("[data-travel]");if(!button)return;
    event.stopPropagation();button.disabled=true;status.textContent="Checking…";
    try{
      const action=button.dataset.travel;
      if(action==="half-day"||action==="rest-day")return await mutate(`/trips/${id}/replan`,{date:button.dataset.date,action:action==="half-day"?"half_day":"rest_day"});
      if(action==="generate")return await mutate(`/trips/${id}/itinerary/generate`,{});
      if(action==="save-itinerary")return await mutate(`/trips/${id}/itinerary`,{itinerary:plan.itinerary},"PATCH");
      if(action==="remove"){
        plan.itinerary.days[Number(button.dataset.day)].items.splice(Number(button.dataset.item),1);
        return await mutate(`/trips/${id}/itinerary`,{itinerary:plan.itinerary},"PATCH");
      }
      if(action==="duplicate") {const copy=await api(`/trips/${id}/duplicate`,{method:"POST"});location.hash="travel-book/"+copy.id;return;}
      if(action==="discover"){
        const constraints=plan?.constraints||trip.constraints||trip.draft;
        const data=await api("/travel/destinations/search",{method:"POST",body:constraints});
        results.innerHTML=`<h3>${data.status==="matched"?"Matching destinations":"No exact match"}</h3><p>${esc(data.explanation)}</p>${(data.matches.length?data.matches:data.compromises).map(d=>`<article><strong>${esc(d.name)}</strong><p>${money(d.budget.total_inr)} ${d.budget.costs_complete===false?"known subtotal · fares incomplete":"sample estimate"} · ${d.score}% interest match</p><p>${esc(d.reasons.join("; "))}</p></article>`).join("")}`;
      }
      if(action==="compare"){
        const trips=await api("/trips");
        results.innerHTML=`<form data-form="compare"><h3>Choose two to eight trips</h3>${trips.map(t=>`<label><input type="checkbox" name="trip" value="${esc(t.id)}" ${t.id===id?"checked":""}>${esc(t.title)}</label>`).join("")}<button>Compare selected trips</button></form>`;
      }
      if(action==="nearby"){
        if(!plan)throw new Error("Build a checked trip first.");
        const data=await api(`/travel/destinations/${plan.destination_id}`);
        results.innerHTML=`<h3>Nearby catalog cities</h3><ul>${data.nearby.map(p=>`<li>${esc(p.name)} · ${p.distance_km} km straight-line distance</li>`).join("")}</ul><p>Season: ${esc(data.season||"unknown")} · ${esc(data.season_source)}</p><p>Weather, permits and accessibility need verification.</p><h4>Mapped places</h4><ul>${data.map_places.map(p=>`<li>${esc(p.name)} · ${esc(p.category)} · <a target="_blank" rel="noopener noreferrer" href="${esc(p.provenance.osm_url)}">OpenStreetMap source</a></li>`).join("")||"No OSM places imported for this city yet."}</ul><small>© OpenStreetMap contributors · <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">ODbL attribution</a></small>`;
      }
      if(action==="research"){
        if(!plan)throw new Error("Build a checked trip first.");
        const data=await api(`/travel/destinations/${plan.destination_id}/research`,{method:"POST",body:{}});
        sessionStorage.setItem("voyara-research-"+id,data.status_url);status.textContent="Research "+data.status+". Use Check research to read its saved result.";return;
      }
      if(action==="research-status"){
        const path=sessionStorage.getItem("voyara-research-"+id);if(!path)throw new Error("Start destination research first.");
        const data=await api(path);
        results.innerHTML=`<h3>Research: ${esc(data.status)}</h3><p>${esc(data.error||data.notice||"")}</p>${Object.entries(data.findings||{}).map(([topic, finding])=>`<article><h4>${esc(topic)}</h4><p>${esc(finding.status.replaceAll("_"," "))}</p>${(finding.statements||[]).map(statement=>`<blockquote>${esc(statement.quote)} <a href="${esc(statement.source_url)}" target="_blank" rel="noopener noreferrer">Source</a></blockquote>`).join("")}</article>`).join("")}${(data.pages||[]).map(p=>`<article><a target="_blank" rel="noopener noreferrer" href="${esc(p.url)}">${esc(p.title||p.url)}</a><small>Retrieved ${esc(p.retrieved_at)}</small><pre class="travel-source">${esc(p.text.slice(0,5000))}</pre></article>`).join("")}`;
      }
      status.textContent="Updated.";
    }catch(error){status.textContent=typeof error.message==="string"?error.message:"Please review the trip inputs.";}
    finally{button.disabled=false;}
  };
  host.onsubmit=async event=>{
    const form=event.target.closest("[data-form]");if(!form)return;
    event.preventDefault();event.stopPropagation();const data=Object.fromEntries(new FormData(form));
    const button=form.querySelector("button");button.disabled=true;
    try{
      if(form.dataset.form==="collaborate")await mutate(`/trips/${id}/collaboration`,{action:"comment",text:data.text});
      if(form.dataset.form==="invite")await mutate(`/trips/${id}/collaboration`,{action:"invite",user_id:data.user_id});
      if(form.dataset.form==="vote")await mutate(`/trips/${id}/collaboration`,{action:"vote",option_id:data.option_id});
      if(form.dataset.form==="status")await mutate(`/trips/${id}`,{status:data.status},"PATCH");
      if(form.dataset.form==="readiness")await mutate(`/trips/${id}/readiness`,{checks:Object.fromEntries(["id_and_tickets","medication","charger","clothing","hours_and_permits","transport_and_stays"].map(key=>[key,!!data[key]]))});
      if(form.dataset.form==="feedback")await mutate(`/trips/${id}/feedback`,{preference:"pace",value:data.value,remember:!!data.remember});
      if(form.dataset.form==="reservation")await mutate(`/trips/${id}/demo-reservations`,{...data,start:new Date(data.start).toISOString(),end:new Date(data.end).toISOString()});
      if(form.dataset.form==="compare"){
        const rows=await api("/trips/compare",{method:"POST",body:new FormData(form).getAll("trip")});
        results.innerHTML=`<h3>Trip comparison</h3><table class="travel-table"><thead><tr><th>Trip</th><th>Total</th><th>Days / visits</th><th>Pace / effort</th><th>Readiness</th></tr></thead><tbody>${rows.map(row=>`<tr><td><a href="#travel-book/${esc(row.id)}">Open trip</a></td><td>${money(row.total_cost_inr)}${row.costs_complete===false?" · known subtotal":""}</td><td>${row.duration_days} / ${row.activity_count}</td><td>${esc(row.pace)} / ${row.effort_minutes} min</td><td>${row.score}<small>${esc(row.score_basis)} ${esc(row.tradeoffs.join("; "))}</small></td></tr>`).join("")}</tbody></table>`;
      }
    }catch(error){status.textContent=error.message;}
    finally{button.disabled=false;}
  };
}
