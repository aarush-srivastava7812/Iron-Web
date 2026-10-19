import { icon } from "./reference-design.js";
import { agentWork, mountPlanEditor } from "./plan-editor.js";
import "./journey.css";

const esc=x=>String(x??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const money=n=>"₹"+Number(n||0).toLocaleString("en-IN");
const labels={destination:"Destination",start_date:"Departure",end_date:"Return",duration_days:"Days",traveller_count:"Travellers",budget:"Total budget",pace:"Travel pace",dietary:"Dietary preference",origin:"Starting city",hotel_style:"Stay style",seat_preference:"Seat preference",transport_mode:"Travel by",interests:"Interests"};
const facts=d=>Object.entries(labels).filter(([k])=>d[k]).map(([k,label])=>`<div><dt>${label}</dt><dd>${esc(k==="budget"?money(d[k]):Array.isArray(d[k])?d[k].join(", "):d[k])}</dd></div>`).join("");
const routeSketch=()=>`<svg class="journey-route" viewBox="0 0 280 350" role="img" aria-label="Illustrative Kerala discovery sequence: Kochi, Munnar and Alleppey"><path d="M70 25C150 10 200 55 174 108S210 155 176 208 190 278 222 320L152 327C142 278 95 236 111 187S55 105 70 25Z" fill="#cde4cf"/><path d="M109 138Q195 70 172 94L125 255" fill="none" stroke="#197d84" stroke-width="3" stroke-dasharray="6 6"/><g fill="#ed9d35" stroke="#fff" stroke-width="3"><circle cx="109" cy="138" r="9"/><circle cx="172" cy="94" r="9"/><circle cx="125" cy="255" r="9"/></g><g fill="#123a54" font-family="Arial" font-size="15" font-weight="600"><text x="25" y="143">Kochi</text><text x="185" y="98">Munnar</text><text x="139" y="262">Alleppey</text><text x="142" y="196" font-size="12" letter-spacing="3">KERALA</text></g><text x="18" y="313" fill="#628784" font-family="Arial" font-size="12">Arabian Sea</text></svg>`;

export function createJourneyUI({api,getUser,requireAuth,ensureConversation,activateTrip}) {
  let activeTrip=null, owner=null, work=null, busy=false, loadedTrip=null, generation=0;
  const books=new Map();
  const launcher=document.createElement("button");
  launcher.className="journey-launcher"; launcher.type="button"; launcher.setAttribute("aria-label","Chat with Voyara AI Travel Team");
  launcher.innerHTML=`<span>${icon("plane")}</span><b>Plan with Voyara</b>`;
  const dialog=document.createElement("dialog"); dialog.className="journey-chat"; dialog.setAttribute("aria-label","Voyara AI Travel Team");
  dialog.innerHTML=`<header class="journey-chat-header"><span class="journey-chat-mark">${icon("plane")}</span><div><strong>Voyara <span>AI Travel Team</span></strong><small>Your personal travel assistant</small></div><button type="button" class="chat-icon-btn" data-chat="new" aria-label="Start a new travel chat">${icon("compass")}</button><button type="button" class="chat-icon-btn" data-chat="close" aria-label="Minimize travel chat">−</button></header><div class="journey-chat-scroll"><div class="journey-chat-greeting"><span>YOUR NEXT CHAPTER STARTS HERE</span><h2>Where will we take you?</h2><p>Namaste! Share a destination, a rough idea or the kind of trip you have in mind. We’ll build it together.</p></div><div class="journey-role-picks"><button type="button" data-prompt="Help me discover a destination in India for a relaxed holiday">${icon("compass")}<b>Explore Agent</b><span>Find your kind of escape</span></button><button type="button" data-prompt="Help me create a custom trip. Ask me what you need to know.">${icon("person")}<b>Trip Consultant</b><span>Shape a personal itinerary</span></button><button type="button" data-prompt="Help me compare options within my total trip budget">${icon("wallet")}<b>Budget & Booking</b><span>Understand the costs</span></button></div><div class="journey-chat-messages" role="log" aria-live="polite" aria-label="Travel conversation"></div><div class="journey-chat-loading" hidden><span></span><span></span><span></span><small>Preparing your trip details…</small></div><div class="journey-chat-cards"></div><div class="journey-chat-review"></div><div class="journey-chat-actions"><button type="button" data-prompt="Show me popular Kerala trips">Kerala escapes</button><button type="button" data-prompt="Show me stays for my trip">Hotels & stays</button><button type="button" data-prompt="Help me choose a flight for this trip">Flight options</button></div></div><form class="journey-chat-compose"><label class="journey-sr" for="journeyMessage">Your travel message</label><textarea id="journeyMessage" name="message" rows="1" maxlength="2000" placeholder="Tell us about the trip you have in mind…" required></textarea><button type="submit" aria-label="Send to Voyara AI">${icon("arrow")}</button><p class="journey-chat-status" role="status"></p><small>Private trip · Confirm details before research</small></form>`;
  document.body.append(launcher,dialog);
  const messages=dialog.querySelector(".journey-chat-messages"), status=dialog.querySelector(".journey-chat-status");
  const scroll=()=>{const el=dialog.querySelector(".journey-chat-scroll");el.scrollTop=el.scrollHeight;};
  const bubble=(role,text)=>`<article class="journey-message ${role==="user"?"from-you":"from-team"}"><span>${role==="user"?"You":"Voyara travel team"}</span><p>${esc(text)}</p></article>`;
  function setBusy(value,text="") {
    busy=value; dialog.querySelectorAll("button,textarea").forEach(b=>b.disabled=value);
    dialog.querySelector('[data-chat="close"]').disabled=false;
    dialog.querySelector(".journey-chat-loading").hidden=!value; status.textContent=text;
  }
  function updateReview() {
    if (!work) return;
    dialog.querySelector(".journey-chat-review").innerHTML=`<details class="journey-draft-review"><summary>Your trip draft <span>${work.missing_fields.length?work.missing_fields.length+" details to add":work.plan_ready?"Outline saved":"Ready to review"}</span></summary><dl>${facts(work.draft)||"<p>Your confirmed choices will appear here.</p>"}</dl>${work.draft.hard_requirements?.length?`<p class="journey-warning">Needs verification: ${esc(work.draft.hard_requirements.join(", "))}</p>`:""}<a href="#travel-book/${work.conversation_id}" data-close-chat>Review details & selections</a></details>${!work.missing_fields.length?`<label class="journey-remember"><input type="checkbox" id="chatRemember"> Remember these explicit preferences for future trips</label><button type="button" class="journey-primary" data-chat="confirm">${work.plan_ready?"Refresh with my travel team":"Confirm details & create my outline"}</button>`:""}${work.plan_ready?`<a class="journey-book-link" href="#travel-book/${work.conversation_id}" data-close-chat>${icon("bag")} Open my personal Travel Book ${icon("arrow")}</a>`:""}`;
  }
  function cardHTML(item,selected=false) {
    return `<article class="journey-choice">${item.image?`<img src="${esc(item.image)}" alt="Kerala backwaters" loading="lazy">`:icon(item.kind==="stay"?"bed":item.kind==="flight"?"plane":"compass")}<div><small>${esc(item.location||item.kind)} · demo catalog</small><b>${esc(item.name)}</b>${item.price_inr?`<span>${money(item.price_inr)} ${item.kind==="stay"?"/ room / night":item.kind==="flight"?"/ guest · outbound":item.kind==="destination"?"indicative catalog guide":"/ guest"}</span>`:""}</div><button type="button" data-choice-kind="${item.kind}" data-choice-id="${item.id}">${selected?"Selected":"Choose"}</button></article>`;
  }
  async function open({tripId,prompt,section}={}) {
    if (!requireAuth()) return;
    if (owner!==getUser()?.id) reset();
    owner=getUser().id;
    if (busy) {if(!dialog.open)dialog.showModal();return;}
    const ticket=generation;
    if (!dialog.open) dialog.showModal();
    setBusy(true,"Opening your private trip…");
    try {
      activeTrip=tripId||await ensureConversation(); activateTrip(activeTrip);
      const [conversation,current]=await Promise.all([api(`/assistant/conversations/${activeTrip}`),api(`/assistant/conversations/${activeTrip}/workspace`)]);
      if(ticket!==generation)return;
      work=current;
      if (loadedTrip!==activeTrip) {
        messages.innerHTML=conversation.messages.map(m=>bubble(m.role,m.content)).join("");
        dialog.querySelector(".journey-chat-cards").replaceChildren(); loadedTrip=activeTrip;
      }
      updateReview(); status.textContent=section?`Editing ${section} for this saved trip.`:"";
    } catch(e) {if(ticket===generation)status.textContent=e.message;}
    finally {if(ticket===generation){setBusy(false,status.textContent);dialog.querySelector("textarea").focus();}}
    if(ticket!==generation)return;
    scroll();
    if (prompt&&work) await send(prompt);
  }
  async function send(text) {
    if (busy||!text.trim()||!work) return;
    const ticket=generation;
    setBusy(true); messages.insertAdjacentHTML("beforeend",bubble("user",text)); scroll();
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),20000);
    try {
      const result=await api(`/assistant/conversations/${activeTrip}/chat`,{method:"POST",body:{content:text,page:"plan"},signal:controller.signal});
      if(ticket!==generation)return;
      work=result.workspace; messages.insertAdjacentHTML("beforeend",bubble("assistant",result.reply));
      window.dispatchEvent(new CustomEvent("voyara-trip-updated",{detail:{tripId:activeTrip}}));
      dialog.querySelector(".journey-chat-cards").innerHTML=result.cards.map(item=>cardHTML(item)).join("");
      updateReview(); if(result.status==="ok")dialog.querySelector("textarea").value="";
      else status.textContent="Your message is saved. You can retry or edit the trip details.";
    } catch(e) {if(ticket===generation)status.textContent=e.name==="AbortError"?"The chat took too long. Your message may be saved; reopen this chat to check before retrying.":e.message;}
    finally {clearTimeout(timeout);if(ticket===generation){setBusy(false,status.textContent);scroll();}}
  }
  async function selectChoice(kind,id) {
    const ticket=generation;
    let updated;
    if(kind==="destination") {
      const item=work.options.destinations.find(i=>i.id===id);
      updated=await api(`/assistant/conversations/${activeTrip}/workspace`,{method:"PUT",body:{expected_revision:work.revision,draft:{...work.draft,destination:item.name}}});
    } else updated=await api(`/assistant/conversations/${activeTrip}/selections`,{method:"POST",body:{expected_revision:work.revision,kind,item_id:id}});
    if(ticket!==generation)return;
    work=updated;
    window.dispatchEvent(new CustomEvent("voyara-trip-updated",{detail:{tripId:activeTrip}}));
    updateReview();status.textContent="Selected for your draft. Confirm to update the itinerary and estimate.";
  }
  launcher.onclick=()=>open();
  dialog.querySelector("form").onsubmit=e=>{e.preventDefault();send(dialog.querySelector("textarea").value.trim());};
  dialog.onclick=async e=>{
    const b=e.target.closest("button,a"); if(!b||b.disabled)return;
    if(b.hasAttribute("data-close-chat")||b.dataset.chat==="close"){dialog.close();return;}
    if(b.dataset.prompt){await send(b.dataset.prompt);return;}
    if(b.dataset.chat==="new") {
      setBusy(true,"Starting a new private trip…");
      try{const trip=await api("/assistant/conversations",{method:"POST",body:{title:"New travel chat"}});activeTrip=trip.id;loadedTrip=null;setBusy(false);await open({tripId:trip.id});}catch(error){setBusy(false,error.message);}return;
    }
    if(b.dataset.choiceKind){setBusy(true);try{await selectChoice(b.dataset.choiceKind,Number(b.dataset.choiceId));}catch(error){status.textContent=error.message;}finally{setBusy(false,status.textContent);}return;}
    if(b.dataset.chat==="confirm") {
      const ticket=generation;
      const remember=!!dialog.querySelector("#chatRemember")?.checked;
      setBusy(true,"Your specialist team is researching, drafting and checking the budget…");scroll();
      try {
        const result=await api(`/assistant/conversations/${activeTrip}/confirm-jobs`,{method:"POST",body:{expected_revision:work.revision,mode:"ai",remember_preferences:remember}});
        if(ticket!==generation)return;
        work=result.workspace;messages.insertAdjacentHTML("beforeend",bubble("assistant",result.reply)+agentWork(result.orchestration.agent_results));updateReview();
        window.dispatchEvent(new CustomEvent("voyara-trip-updated",{detail:{tripId:activeTrip}}));
        status.textContent=work.plan_ready?"Your outline is saved. Open your Travel Book to review it.":"The team needs another check. Review the response before continuing.";
      }catch(error){if(ticket===generation)status.textContent=error.message;}finally{if(ticket===generation){setBusy(false,status.textContent);scroll();}}
    }
  };
  dialog.addEventListener("close",()=>launcher.focus());
  function reset(){generation++;activeTrip=null;loadedTrip=null;owner=null;work=null;books.clear();messages.replaceChildren();dialog.querySelector(".journey-chat-review").replaceChildren();dialog.querySelector(".journey-chat-cards").replaceChildren();setBusy(false);dialog.close();}

  const field=(name,type="text",value="",extra="")=>`<label>${labels[name]||name}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;
  async function bookPage(id) {
    if(!getUser())return `<section class="section"><div class="container"><h1>Your personal Travel Book</h1><p>Sign in to create, reopen or edit your private trip.</p><a class="btn" href="#login">Sign in</a></div></section>`;
    const current=await api(`/assistant/conversations/${encodeURIComponent(id)}/workspace`);
    let book=null,bookError="";try{book=await api(`/assistant/conversations/${encodeURIComponent(id)}/travel-book`);}catch(e){if(![409,422].includes(e.status))throw e;bookError=e.message;}
    books.set(id,{work:current,book});activateTrip(id);
    const d=current.draft, name=d.destination||"next", guide=current.guide;
    return `<section class="journey-book-hero">${guide?'<img src="/travel/kerala.jpg" alt="Palm-lined Kerala backwaters and a traditional boat">':""}<div class="container"><span>YOUR PERSONAL TRAVEL BOOK</span><h1>Your ${esc(name)}<em>Escape</em></h1><p>${esc(guide?.description||"Gather the places, stays and experiences that make a journey yours.")}</p><div class="journey-hero-tags">${["Nature & relaxation","Culture & heritage","Local cuisine"].map(t=>`<span>${esc(t)}</span>`).join("")}</div></div></section><section class="section journey-book" data-trip="${esc(id)}"><div class="container"><div class="journey-book-toolbar"><span class="tag">${current.plan_ready?"SAVED ITINERARY":"TRIP DRAFT"} · DEMO INVENTORY</span><button class="mini-btn" data-book="chat">${icon("sparkle")} Edit with Voyara AI</button><a class="mini-btn" href="#trip/${id}">Conversation & memory</a></div><div class="journey-book-overview"><div><span class="journey-eyebrow">THE DETAILS, ALL TOGETHER</span><h2>Your journey at a glance</h2><dl class="journey-facts">${facts(d)||"<p>Start with your destination and travel dates below.</p>"}</dl></div>${guide?`<aside class="journey-map"><h3>Kerala at a glance</h3>${routeSketch()}<small>Regional discovery sketch. Route timing is unverified.</small></aside>`:`<aside class="journey-map"><h3>Make it your own</h3><p>Save a destination, exact dates and a total budget. Choose catalog options here or ask your travel team for help.</p></aside>`}</div>${guide?`<section class="journey-destinations"><span class="journey-eyebrow">SAME STATE, ENDLESS EXPERIENCES</span><h2>Discover your Kerala</h2><p>Regional inspiration. Your saved day-by-day plan shows the experiences actually selected.</p><div>${guide.cities.map((city,i)=>`<article><div class="journey-city-art city-${i}">${icon(i===1?"mountain":i===2?"compass":"camera")}</div><h3>${esc(city.name)}</h3><p>${esc(city.description)}</p><ul>${city.experiences.map(x=>`<li>${esc(x)}</li>`).join("")}</ul></article>`).join("")}</div></section>`:""}<details class="journey-manual" ${current.missing_fields.length?"open":""}><summary>Trip details · edit manually</summary><form id="journeyDraftForm"><div class="journey-form-grid"><label>Destination<select name="destination" required><option value="">Choose a destination</option>${d.destination&&!current.options.destinations.some(o=>o.name===d.destination)?`<option selected>${esc(d.destination)}</option>`:""}${current.options.destinations.map(o=>`<option ${o.name===d.destination?"selected":""}>${esc(o.name)}</option>`).join("")}</select></label>${field("start_date","date",d.start_date||"","required")}${field("end_date","date",d.end_date||"","required")}${field("traveller_count","number",d.traveller_count||2,'min="1" max="30" required')}${field("budget","number",d.budget||"",'min="1" step="1" required')}${field("origin","text",d.origin||"")}<label>Travel pace<select name="pace">${["relaxed","moderate","packed"].map(p=>`<option ${p===d.pace?"selected":""}>${p}</option>`).join("")}</select></label><label>Dietary preference<select name="dietary"><option value="">No stated requirement</option><option ${d.dietary==="vegetarian"?"selected":""}>vegetarian</option></select></label><label>Interests<input name="interests" value="${esc((d.interests||[]).join(", "))}" placeholder="Nature, culture, food"></label><label>Mandatory requirements<input name="hard_requirements" value="${esc((d.hard_requirements||[]).join("; "))}" placeholder="Accessibility, allergies or must-avoid rules"><small>Unverified mandatory conditions stop plan generation.</small></label></div><button class="journey-primary" type="submit">Save trip details</button><p id="journeyDraftStatus" role="status"></p></form></details><section id="journeySelections"><span class="journey-eyebrow">YOUR SELECTED TRAVEL PLAN</span><h2>A few good choices make a great trip</h2><p>${esc(current.notice)}</p>${[ ["stays","stay","Stays","hotels"],["experiences","experience","Experiences","tours"],["flights","flight","Flights","flights"] ].map(([group,kind,title,section])=>`<div class="journey-selection-heading"><h3>${title}</h3><a href="#${section}?tripId=${id}&edit=true">Browse & edit ${title.toLowerCase()} ${icon("arrow")}</a></div><div class="journey-options">${current.options[group].map(item=>cardHTML(item,kind==="experience"?(current.selections.experience||[]).includes(item.id):current.selections[kind]===item.id)).join("")||`<p>${kind==="flight"?"Add a starting city to see matching sample outbound routes.":"Choose a destination to see its demo catalog."}</p>`}</div>`).join("")}</section><div class="journey-generate"><div><h3>${current.plan_ready?"Your itinerary is ready to review":"Turn your choices into a day-by-day trip"}</h3><p>Confirm the exact trip details, then let your specialists plan or build a manual outline from your choices.</p><label class="journey-remember"><input type="checkbox" id="bookRemember"> Remember these explicit preferences for future trips</label></div><button class="journey-primary" data-book="generate-ai">Create with my AI team</button><button class="mini-btn" data-book="generate-manual">Build from my choices</button><p id="journeyGenerateStatus" role="status"></p></div><div id="journeyPlanEditor"></div><section class="journey-download"><div>${icon("bag")}<span>YOUR JOURNEY, READY TO TAKE WITH YOU</span><h2>A travel book worth keeping</h2><p>Destination guide, day-by-day itinerary, your selected stay and flight, itemized budget and private edit links. Downloaded PDFs remain fixed snapshots.</p>${book?`<strong>${money(book.budget.total_inr)} <small>total · listed selections only</small></strong>`:""}</div><button class="journey-primary" data-book="download" ${book?"":"disabled"}>Download my Travel Book ${icon("arrow")}</button><p id="journeyDownloadStatus" role="status">${esc(bookError)}</p></section>${guide?`<section class="journey-guide-notes"><h3>Before you go</h3><p>${esc(guide.season_note)}</p><p>${esc(guide.cuisine)}</p><p>${esc(guide.packing)}</p></section>`:""}</div></section>`;
  }
  async function bindBook(host,id,rerender) {
    const record=books.get(id);if(!record)return;
    const area=host.querySelector(".journey-book");if(!area)return;
    const editor=host.querySelector("#journeyPlanEditor");if(record.work.plan_ready)mountPlanEditor(editor,id,api);
    const saveStatus=host.querySelector("#journeyDraftStatus");
    host.querySelector("#journeyDraftForm").onsubmit=async event=>{
      event.preventDefault();const form=event.currentTarget,button=form.querySelector("button");button.disabled=true;
      const f=Object.fromEntries(new FormData(form));const draft={...record.work.draft,...f,traveller_count:Number(f.traveller_count),budget:Number(f.budget),interests:f.interests.split(",").map(x=>x.trim()).filter(Boolean),hard_requirements:f.hard_requirements.split(";").map(x=>x.trim()).filter(Boolean)};
      if(!draft.dietary)delete draft.dietary;if(!draft.origin)delete draft.origin;
      delete draft.duration_days;
      try{await api(`/assistant/conversations/${id}/workspace`,{method:"PUT",body:{expected_revision:record.work.revision,draft}});await rerender();}catch(e){saveStatus.textContent=e.message;button.disabled=false;}
    };
    area.onclick=async event=>{
      const button=event.target.closest("button");if(!button||button.disabled)return;
      const action=button.dataset.book;
      if(!action&&!button.dataset.choiceKind)return;
      if(action==="chat"){await open({tripId:id,section:"your travel book"});return;}
      const target=host.querySelector(action==="download"?"#journeyDownloadStatus":"#journeyGenerateStatus");
      const disabledBefore=new Map([...area.querySelectorAll("button")].map(b=>[b,b.disabled]));
      button.disabled=true;
      try {
        if(button.dataset.choiceKind) {
          const kind=button.dataset.choiceKind,itemId=Number(button.dataset.choiceId),selected=kind==="experience"?(record.work.selections.experience||[]).includes(itemId):record.work.selections[kind]===itemId;
          await api(`/assistant/conversations/${id}/selections`,{method:"POST",body:{expected_revision:record.work.revision,kind,item_id:itemId,remove:selected}});await rerender();return;
        }
        if(action==="generate-ai"||action==="generate-manual") {
          target.textContent=action==="generate-ai"?"Your specialist team is researching, building and reviewing your trip…":"Building and validating your manual catalog selections…";
          area.querySelectorAll("button").forEach(b=>b.disabled=true);
          const result=await api(`/assistant/conversations/${id}/confirm-jobs`,{method:"POST",body:{expected_revision:record.work.revision,mode:action==="generate-ai"?"ai":"manual",remember_preferences:!!host.querySelector("#bookRemember").checked}});
          if(result.orchestration.status!=="ok")throw new Error(result.reply);
          await rerender();return;
        }
        if(action==="download") {
          target.textContent="Preparing your private PDF…";
          const result=await api(`/assistant/conversations/${id}/travel-books`,{method:"POST"});
          const link=document.createElement("a");link.href=result.download_url;link.download="Voyara-Travel-Book.pdf";document.body.append(link);link.click();link.remove();target.textContent="Your PDF is ready. Its links reopen this private trip.";
        }
      }catch(e){if(target)target.textContent=e.message;}
      finally{disabledBefore.forEach((disabled,b)=>b.disabled=disabled);}
    };
  }
  async function startBook(){if(!requireAuth())return;const id=await ensureConversation();location.hash="travel-book/"+id;}
  return {open,reset,bookPage,bindBook,startBook};
}

export function keralaGuidePage(guide){
  return `<section class="journey-book-hero"><img src="/travel/kerala.jpg" alt="Kerala backwaters and a traditional boat"><div class="container"><span>YOUR DESTINATION</span><h1>Discover Kerala</h1><p>${esc(guide.description)}</p><div class="journey-hero-tags">${guide.themes.map(t=>`<span>${esc(t)}</span>`).join("")}</div></div></section><section class="section journey-book"><div class="container"><div class="journey-book-overview"><section class="journey-destinations"><span class="journey-eyebrow">ONE STATE, THREE DIFFERENT RHYTHMS</span><h2>Find your Kerala</h2><p>Build a personal journey from these destinations. Select your actual stays and experiences in your Travel Book.</p><div>${guide.cities.map((city,i)=>`<article><div class="journey-city-art city-${i}">${icon(i===1?"mountain":"camera")}</div><h3>${esc(city.name)}</h3><p>${esc(city.description)}</p><ul>${city.experiences.map(e=>`<li>${esc(e)}</li>`).join("")}</ul></article>`).join("")}</div></section><aside class="journey-map"><h3>Kerala at a glance</h3>${routeSketch()}<small>${esc(guide.route_notice)}</small></aside></div><div class="journey-guide-notes"><h3>Before you go</h3><p>${esc(guide.season_note)}</p><p>${esc(guide.cuisine)}</p><p>${esc(guide.packing)}</p></div><section class="journey-download"><div><span>YOUR PREFERENCES. YOUR PACE.</span><h2>Make this journey yours</h2><p>Start a private trip, choose the places and experiences you like, and let your travel team put the details together.</p></div><button class="journey-primary" data-action="plan-kerala">Create my Kerala Travel Book</button></section></div></section>`;
}
