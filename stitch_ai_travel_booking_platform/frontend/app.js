import { createViews } from "./templates.js";
import { mountPlanEditor, agentWork } from "./plan-editor.js";
import { createJourneyUI, keralaGuidePage } from "./journey-ui.js";
import "./connected.css";
import "./reference-design.css";
import "./interior-design.css";
import {
  createReferenceViews,
  applyReferencePhotos,
} from "./reference-design.js";

const escapeHTML = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const money = (n) => "₹" + Number(n).toLocaleString("en-IN");
const today = () => new Date().toLocaleDateString("en-CA");
const addDays = (date, days) => {
  const d = new Date(date + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
};
const app = document.getElementById("app");
const state = {
  user: null,
  catalog: null,
  favorites: [],
  bookings: [],
  itineraries: [],
  conversations: [],
  profile: {},
  flightSelection: null,
};
const views = createViews({ escapeHTML, airportOptions, today });
const referenceViews = createReferenceViews(escapeHTML);
let renderVersion = 0,
  packageFilter = "All",
  packageSort = "featured",
  hotelFilter = "All stays";
let currentConversation = null,
  conversationPromise = null;
const savingFavorites = new Set();
const journeyUI = createJourneyUI({api,getUser:()=>state.user,requireAuth,ensureConversation,
  activateTrip:id=>{currentConversation=id;if(state.user)sessionStorage.setItem("voyaraTrip:"+state.user.id,id);}});

async function api(path, { method = "GET", body, ...options } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const csrf = document.cookie
    .split("; ")
    .find((x) => x.startsWith("voyara_csrf="))
    ?.split("=")
    .slice(1)
    .join("=");
  if (csrf) headers["X-CSRF-Token"] = decodeURIComponent(csrf);
  const response = await fetch("/api" + path, {
    method,
    headers,
    credentials: "same-origin",
    ...options,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) {
      state.user = null;
      journeyUI.reset();
      updateAccount();
    }
    const detail = Array.isArray(data.detail)
      ? data.detail.map((x) => x.msg).join("; ")
      : data.detail;
    const error = new Error(detail || "The request failed. Please try again.");
    error.status = response.status;
    throw error;
  }
  return data;
}

function airportOptions(selected) {
  return (state.catalog?.airports || [])
    .map(
      (a) =>
        `<option value="${a.id}" ${a.name === selected ? "selected" : ""}>${escapeHTML(a.name)}</option>`,
    )
    .join("");
}
function notice(message, title = "Something needs attention") {
  return `<div class="detail-block" role="status"><h3>${escapeHTML(title)}</h3><p>${escapeHTML(message)}</p></div>`;
}
function loginPrompt() {
  return `<section class="section"><div class="container"><div class="empty-state"><div class="big-icon">♙</div><h2>Keep your journeys together</h2><p>Sign in with Google to save places, plan with your private trip memory and submit requests.</p><a class="btn" href="#login">Continue with Google →</a></div></div></section>`;
}
function requireAuth() {
  if (state.user) return true;
  sessionStorage.setItem("voyaraAfterLogin", location.hash || "#home");
  views.toast("Sign in with Google to continue.");
  location.hash = "login";
  return false;
}
function updateAccount() {
  const link = document.querySelector(".login-link");
  link.textContent = state.user
    ? state.user.full_name?.split(" ")[0] || "My account"
    : "Login / Signup";
  link.href = state.user ? "#dashboard" : "#login";
}
async function loadFavorites() {
  state.favorites = state.user ? await api("/favorites") : [];
  views.setSaved(state.favorites.map((f) => f.item_type + ":" + f.item_id));
}
function routeInfo() {
  const hash = location.hash.slice(1) || "home";
  const [path, query = ""] = hash.split("?");
  const [route, ...parts] = path.split("/");
  return {
    route,
    param: decodeURIComponent(parts.join("/")),
    query: new URLSearchParams(query),
  };
}

async function render() {
  const version = ++renderVersion;
  try {
    const { route, param, query } = routeInfo();
    document.body.dataset.page = route;
    packageFilter = "All";
    packageSort = "featured";
    hotelFilter = "All stays";
    const pages = {
      home: () => referenceViews.home(state.catalog, state.favorites),
      destinations: () => referenceViews.destinations(state.catalog),
      packages: views.packagesPage,
      tours: views.toursPage,
      hotels: views.hotelsPage,
      planner: views.plannerPage,
      flights: views.flightsPage,
      about: views.aboutPage,
      contact: views.contactPage,
      privacy: privacyPage,
      login: loginPage,
    };
    let html;
    if (route === "dashboard") {
      app.innerHTML = notice("Loading your journeys…");
      if (state.user) {
        const [bookings, itineraries, conversations, profile] =
          await Promise.all([
            api("/bookings"),
            api("/itineraries"),
            api("/assistant/conversations"),
            api("/profile"),
          ]);
        if (version !== renderVersion) return;
        Object.assign(state, { bookings, itineraries, conversations, profile });
        await loadFavorites();
      }
      html = dashboardPage();
    } else if (route === "travel-book") html = await journeyUI.bookPage(param);
    else if (route === "chat") html = `<section class="section"><div class="container"><div class="journey-planner-entry"><div><h1>Your Voyara travel team</h1><p>Talk through your trip, compare catalog choices and create your personal Travel Book.</p></div><button class="journey-primary" data-action="open-travel-chat">Start a conversation</button></div></div></section>`;
    else if (route === "booking") html = bookingPage(query);
    else if (route === "destination" || route === "package") {
      const match = state.catalog.destinations.find(
        (d) => d.name.toLowerCase() === param.toLowerCase(),
      );
      html = match
        ? route === "destination"
          ? param.toLowerCase()==="kerala"&&state.catalog.destination_guides?.Kerala?keralaGuidePage(state.catalog.destination_guides.Kerala):views.destinationDetail(param)
          : views.packageDetail(param)
        : notice(
            "Choose a place from Explore destinations.",
            "Destination not found",
          );
    } else if (route === "trip") html = await tripPage(param);
    else
      html = pages[route]
        ? pages[route]()
        : notice(
            "This page could not be found. Use the navigation to explore.",
            "Page not found",
          );
    if (version !== renderVersion) return;
    app.innerHTML = html;
    if (route === "trip" && state.user) {
      const editor = document.createElement("div");
      app.querySelector(".section .container")?.prepend(editor);
      mountPlanEditor(editor, param, api);
      const bookLink=document.createElement("a");bookLink.className="mini-btn";bookLink.href="#travel-book/"+param;bookLink.textContent="Open my personal Travel Book";editor.before(bookLink);
    }
    if (!["home", "destinations", "login", "privacy", "trip", "travel-book", "chat"].includes(route)) {
      const hero = app.querySelector(".page-hero");
      if (hero)
        hero.insertAdjacentHTML(
          "afterend",
          views.aiConcierge(route, escapeHTML(param)),
        );
      bindConcierge(route);
    }
    document
      .querySelectorAll(".main-nav a")
      .forEach((a) => a.classList.toggle("active", a.hash === "#" + route));
    document.getElementById("mainNav").classList.remove("open");
    document
      .getElementById("menuToggle")
      .setAttribute("aria-expanded", "false");
    bindForms(route, query);
    if(route==="travel-book")journeyUI.bindBook(app,param,async()=>{const y=scrollY;await render();window.scrollTo({top:y,behavior:"instant"});});
    if(route==="chat")journeyUI.open({tripId:query.get("tripId")||undefined});
    if(route==="planner"){
      const form=document.getElementById("plannerForm");
      form?.insertAdjacentHTML("beforebegin",'<div class="journey-planner-entry"><div><h2>A conversation is a good place to start.</h2><p>Tell your NVIDIA-powered travel team what you have in mind. Review your choices, then create a personal Travel Book.</p></div><button class="journey-primary" data-action="open-travel-chat">Chat with my travel team</button></div>');
    }
    if(query.get("tripId")&&state.user)await bindTripDeepLink(route,query.get("tripId"));
    labelFields(app);
    window.scrollTo({ top: 0, behavior: "instant" });
    if (route === "login") await mountGoogle(version);
  } catch (error) {
    if (version !== renderVersion) return;
    app.innerHTML = `<section class="section"><div class="container">${notice(error.message)}<button class="btn" data-action="retry">Try again</button> <a class="mini-btn" href="#home">Home</a></div></section>`;
  }
}

function loginPage() {
  if (state.user)
    return `${views.pageHero("WELCOME BACK", "Your next chapter awaits", "Your account is connected.")}<section class="section"><div class="container"><div class="auth-card"><h2>${escapeHTML(state.user.full_name || "Traveller")}</h2><p>${escapeHTML(state.user.email)}</p><a class="btn" href="#dashboard">My journeys →</a> <button class="mini-btn" data-action="logout">Sign out</button></div></div></section>`;
  return `${views.pageHero("YOUR JOURNEYS START HERE", "Welcome to Voyara", "One Google account for your saved places, trip requests and private travel memory.")}<section class="section"><div class="container"><div class="auth-card"><div class="brand-mark">↗</div><h2>Travel starts with you</h2><p>Continue with your Google account.</p><div id="googleSignIn" aria-live="polite">Checking sign-in availability…</div><p id="authStatus" role="status"></p><p class="subtext">By continuing, you agree to the <a href="#privacy">privacy information</a>.</p><a class="text-link" href="#destinations">Explore first →</a></div></div></section>`;
}
let googleScript;
async function mountGoogle(version) {
  if (state.user) return;
  const [config, developer] = await Promise.all([
    api("/auth/google/config"),
    api("/auth/developer/config"),
  ]);
  if (version !== renderVersion) return;
  const target = document.getElementById("googleSignIn");
  if (developer.enabled) {
    target.insertAdjacentHTML(
      "afterend",
      '<div class="setup-note"><b>Local developer account</b><p>Use the app while Google sign-in is being configured.</p><button class="btn" id="developerSignIn" type="button">Continue as Developer →</button></div>',
    );
    document.getElementById("developerSignIn").onclick = async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      const status = document.getElementById("authStatus");
      status.textContent = "Opening your developer account…";
      try {
        state.user = await api("/auth/developer", {
          method: "POST",
          headers: { "X-Voyara-Developer": "1" },
        });
        currentConversation = null;
        await loadFavorites();
        updateAccount();
        const next = sessionStorage.getItem("voyaraAfterLogin") || "#dashboard";
        sessionStorage.removeItem("voyaraAfterLogin");
        location.hash = next;
      } catch (error) {
        status.textContent = error.message;
        button.disabled = false;
      }
    };
  }
  if (!config.configured) {
    target.innerHTML =
      '<div class="setup-note"><b>Google sign-in is awaiting setup</b><p>The owner needs to add the Google Web client ID. You can explore now, or use the local developer account below when enabled.</p></div>';
    return;
  }
  try {
    if (!window.google?.accounts?.id) {
      googleScript ||= new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        script.async = true;
        script.onload = resolve;
        script.onerror = () =>
          reject(
            new Error(
              "Google sign-in could not load. Check your connection and reload.",
            ),
          );
        document.head.append(script);
      }).catch((error) => {
        googleScript = null;
        throw error;
      });
      await googleScript;
    }
    if (version !== renderVersion) return;
    target.replaceChildren();
    window.google.accounts.id.initialize({
      client_id: config.client_id,
      nonce: config.nonce,
      auto_select: false,
      callback: async (response) => {
        if (version !== renderVersion) return;
        const status = document.getElementById("authStatus");
        status.textContent = "Signing you in…";
        try {
          state.user = await api("/auth/google", {
            method: "POST",
            body: { credential: response.credential, nonce: config.nonce },
          });
          currentConversation = null;
          await loadFavorites();
          updateAccount();
          const next =
            sessionStorage.getItem("voyaraAfterLogin") || "#dashboard";
          sessionStorage.removeItem("voyaraAfterLogin");
          location.hash = next;
        } catch (error) {
          status.textContent = error.message;
        }
      },
    });
    window.google.accounts.id.renderButton(target, {
      theme: "outline",
      size: "large",
      text: "continue_with",
      shape: "pill",
    });
  } catch (error) {
    target.textContent = error.message;
  }
}

function selectedItem(query) {
  const kind = query.get("type") || "package";
  const lists = {
    package: state.catalog.destinations,
    stay: state.catalog.hotels,
    experience: state.catalog.experiences,
  };
  if (kind === "transport")
    return state.flightSelection
      ? { kind, item: state.flightSelection[0] }
      : null;
  const list = lists[kind];
  if (!list) return null;
  const id = Number(query.get("id"));
  const place = query.get("place");
  const item = id
    ? list.find((x) => x.id === id)
    : place
      ? list.find((x) => x.name.toLowerCase() === place.toLowerCase())
      : list[0];
  return item ? { kind, item } : null;
}
function bookingPage(query) {
  const selected = selectedItem(query);
  if (!selected)
    return `<section class="section"><div class="container">${notice("Search and select a route again, or choose a package or stay.", "Choose your journey")}<a class="btn" href="#packages">Explore packages</a> <a class="mini-btn" href="#flights">Search flights</a></div></section>`;
  const { kind, item } = selected;
  const name =
    kind === "transport"
      ? state.flightSelection
          .map((x) => x.origin + " → " + x.destination)
          .join(" / ")
      : item.name;
  return `${views.pageHero("A FEW DETAILS, THEN YOU’RE CLOSER", "Let’s get your trip started", "Review the quote before confirming your booking request.")}<section class="section"><div class="container"><div class="stepper"><div class="step active"><span>1</span>Traveller details</div><div class="step-line"></div><div class="step"><span>2</span>Review</div><div class="step-line"></div><div class="step"><span>3</span>Request saved</div></div><div class="booking-layout"><form id="bookingForm" class="form-card"><div class="eyebrow">TRAVELLER INFORMATION</div><h2>Who’s joining the journey?</h2><div class="form-grid"><div class="field"><label>First name</label><input name="first" required maxlength="60"></div><div class="field"><label>Last name</label><input name="last" required maxlength="60"></div><div class="field"><label>Email address</label><input type="email" name="email" required></div><div class="field"><label>Phone number</label><input name="phone" type="tel" required minlength="7" maxlength="20" pattern="[0-9+() -]+"></div><div class="field"><label>${kind === "stay" ? "Check-in date" : "Departure / activity date"}</label><input name="date" type="date" min="${today()}" required ${kind === "transport" ? "readonly" : ""}></div>${kind === "stay" ? `<div class="field"><label>Check-out date</label><input name="end_date" type="date" min="${today()}" required></div>` : ""}<div class="field"><label>${kind === "stay" ? "Rooms" : "Travellers"}</label><select name="travellers">${[1, 2, 3, 4, 5, 6].map((n) => `<option value="${n}" ${n === 2 ? "selected" : ""}>${n}</option>`).join("")}</select></div><div class="field full"><label>Special requests (optional)</label><textarea name="notes" maxlength="2000"></textarea></div></div><label class="consent"><input type="checkbox" name="consent" required> I agree to be contacted about this request.</label><button class="btn" type="submit">Review trip request →</button><p class="subtext">${escapeHTML(state.catalog.inventory_notice)}</p><div class="form-status" role="status"></div></form><aside class="sticky-card"><div class="eyebrow">YOUR TRIP SUMMARY</div><h3>${escapeHTML(name)}</h3><p>${kind === "package" ? `${item.nights} nights / ${item.nights + 1} days` : kind === "stay" ? "Per room, per night" : kind === "transport" ? "Economy · sample route request" : "Per person · activity request"}</p><div class="price">${money(kind === "transport" ? state.flightSelection.reduce((n, x) => n + x.price_inr, 0) : item.price)} <small>${kind === "stay" ? "/ room / night" : "/ person"}</small></div><p>Review the server quote for your dates and quantity.</p></aside></div><div id="bookingReview" aria-live="polite"></div></div></section>`;
}

function dashboardPage() {
  const hero = views.pageHero(
    "YOUR TRAVEL SPACE",
    "Every journey, all in one place",
    "Saved places, booking requests, trip plans and your private travel memory.",
  );
  if (!state.user) return hero + loginPrompt();
  const saved = state.favorites
    .map((f) => {
      const item = (
        f.item_type === "package"
          ? state.catalog.destinations
          : state.catalog.hotels
      ).find((x) => x.id === f.item_id);
      return item
        ? `<div>${f.item_type === "package" ? views.packageCard(item) : views.hotelCard(item)}</div>`
        : "";
    })
    .join("");
  return (
    hero +
    `<section class="section"><div class="container"><div class="account-bar"><div><h2>${escapeHTML(state.user.full_name || "Your journeys")}</h2><p>${escapeHTML(state.user.email)}</p></div><button class="mini-btn" data-action="logout">Sign out</button></div><div class="stat-grid"><div class="stat-card"><span>Saved places & stays</span><strong>${state.favorites.length}</strong></div><div class="stat-card"><span>Booking requests</span><strong>${state.bookings.filter((x) => x.status !== "cancelled").length}</strong></div><div class="stat-card"><span>Trip conversations</span><strong>${state.conversations.length}</strong></div></div><h2>Saved for later</h2><div class="grid grid-3">${saved || "<p>Your shortlist starts here. Save a package or stay with its heart button.</p>"}</div><h2>Booking requests</h2><div id="bookingList">${state.bookings.map((b) => `<article class="detail-block"><span class="tag">${escapeHTML(b.status)}</span><h3>Request #${b.id} · ${money(b.total_inr)}</h3><p>${b.items.map((i) => escapeHTML(itemName(i)) + ` · ${i.quantity} · ${escapeHTML(i.start_date || "")}`).join("<br>")}</p>${b.status === "requested" ? `<button class="mini-btn" data-action="cancel" data-id="${b.id}">Cancel request</button>` : ""}</article>`).join("") || "<p>No requests yet. Explore a package, stay or experience.</p>"}</div><h2>Saved itineraries</h2>${state.itineraries.map((i) => `<article class="detail-block"><h3>${escapeHTML(i.title)}</h3><p>${escapeHTML(i.start_date)} → ${escapeHTML(i.end_date)}</p><pre class="plan-text">${escapeHTML(i.notes)}</pre><button class="mini-btn" data-action="delete-itinerary" data-id="${i.id}">Delete itinerary</button></article>`).join("") || "<p>Create an itinerary with the AI trip planner.</p>"}<h2>Trip memory & conversations</h2>${state.conversations.map((c) => `<article class="detail-block"><h3>${escapeHTML(c.title)}</h3><a class="mini-btn" href="#travel-book/${encodeURIComponent(c.id)}">Open Travel Book</a> <a class="mini-btn" href="#trip/${encodeURIComponent(c.id)}">Open conversation & memory</a> <button class="mini-btn danger" data-action="forget-trip" data-id="${escapeHTML(c.id)}">Delete conversation & forget trip</button></article>`).join("") || "<p>Your conversations will appear here.</p>"}<h2>Travel preferences</h2><form id="profileForm" class="form-card"><p>Confirm preferences you want the travel agents to remember across trips.</p><div class="form-grid"><div class="field"><label>Travel style</label><select name="travel_style"><option value="">No preference</option>${["slow travel", "adventure", "culture", "family"].map((v) => `<option ${state.profile.travel_style === v ? "selected" : ""}>${v}</option>`).join("")}</select></div><div class="field"><label>Dietary preference</label><select name="diet"><option value="">No preference</option><option value="vegetarian" ${state.profile.dietary_restrictions?.includes("vegetarian") ? "selected" : ""}>Vegetarian</option></select></div></div><button type="submit" class="btn">Save preferences</button><div class="form-status" role="status"></div></form></div></section>`
  );
}
function itemName(item) {
  const lists = {
    package: state.catalog.destinations,
    stay: state.catalog.hotels,
    experience: state.catalog.experiences,
  };
  return (
    lists[item.item_type]?.find((x) => x.id === item.item_id)?.name ||
    item.item_type + " #" + item.item_id
  );
}
function privacyPage() {
  return `${views.pageHero("YOUR INFORMATION", "Privacy & your travel memory", "Control the information you share with Voyara.")}<section class="section"><div class="container"><div class="detail-block"><h2>Your account and trips</h2><p>Google verifies your sign-in. Voyara stores your account ID, verified email, name, saved items, booking requests, enquiries and trip conversations in its backend database. Google credentials are verified on the server; the browser session uses an HttpOnly cookie.</p><h2>Your travel memory</h2><p>Confirmed trip details and saved preferences are used by the connected travel agents. Open a conversation in My Trips to inspect or forget a memory event. Deleting a conversation also forgets that trip’s memory. Saved itineraries and booking records are separate records you can manage in My Trips.</p><h2>Catalog and communications</h2><p>The catalog is illustrative. Booking requests require provider confirmation and collect no payment. Enquiries and newsletter subscriptions are stored; outbound email is awaiting configuration. Images load from Unsplash and fonts from Google Fonts. Google Identity Services loads on sign-in when configured.</p><a class="btn" href="#dashboard">Manage my journeys</a> <a class="mini-btn" href="#contact">Contact us</a></div></div></section>`;
}

function partialDraftNotice(text) {
  const missing = [];
  if (/Stay Agent:\s*0 stay options/i.test(text))
    missing.push("no stay has been shortlisted");
  if (/Tour Guide Agent:\s*0 experience ideas/i.test(text))
    missing.push("no matching experience has been shortlisted");
  return missing.length
    ? `<div class="plan-caveat"><strong>This is a partial draft.</strong> ${escapeHTML(missing.join("; "))}. The displayed estimate covers the listed items only, and is not the total cost of your holiday. <a href="#hotels">Explore stays</a> or <a href="#planner">adjust your trip details</a>.</div>`
    : "";
}

function memoryDetails(context) {
  const labels = {
    destination: "Destination",
    dates: "Travel dates",
    budget: "Total budget",
    currency: "Currency",
    traveller_count: "Travellers",
    dietary: "Dietary preference",
    pace: "Travel pace",
    interests: "Interests",
  };
  const fields = (context.fields || []).filter((f) => labels[f.predicate]);
  if (!fields.length)
    return notice(
      context.detail ||
        "Confirm your trip details in the planner to build your travel memory.",
      "Your trip details",
    );
  return `<dl class="memory-details">${fields
    .map((field) => {
      let value =
        field.status === "supported"
          ? field.values
              .map((v) => (Array.isArray(v) ? v.join(", ") : String(v)))
              .join(", ")
          : "Not specified";
      if (field.predicate === "budget" && field.status === "supported")
        value = money(field.values[0]);
      return `<div class="memory-detail"><dt>${labels[field.predicate]}</dt><dd>${escapeHTML(value)}</dd></div>`;
    })
    .join(
      "",
    )}</dl><details class="memory-technical"><summary>View technical memory details</summary><pre class="plan-text">${escapeHTML(JSON.stringify(context, null, 2))}</pre></details>`;
}

function memoryEventView(event, trip) {
  const receipt = event.receipt;
  const date = new Date(receipt.submitted * 1000).toLocaleString("en-IN");
  return `<article class="memory-event"><span class="tag">${escapeHTML(receipt.status)}</span><h3>Confirmed trip update</h3><p>${escapeHTML(date)} · ${receipt.semantic_claim_count || 0} trip details saved</p><details><summary>View the saved update</summary><pre class="plan-text">${escapeHTML(event.text || "")}</pre></details><button class="mini-btn danger" data-action="forget-event" data-trip="${escapeHTML(trip)}" data-id="${escapeHTML(receipt.id)}">Forget this event</button></article>`;
}

async function tripPage(id) {
  if (!state.user) return loginPrompt();
  const path = "/assistant/conversations/" + encodeURIComponent(id);
  const conversation = await api(path);
  let events, context;
  try {
    [events, context] = await Promise.all([
      api(path + "/memory-events"),
      api(path + "/requirements"),
    ]);
  } catch (error) {
    context = { status: "unavailable", detail: error.message };
    events = { events: [] };
  }
  currentConversation = id;
  sessionStorage.setItem("voyaraTrip:" + state.user.id, id);
  return `${views.pageHero("YOUR PRIVATE TRIP MEMORY", escapeHTML(conversation.title), "These are your saved conversation and confirmed memory events.")}<section class="section"><div class="container"><a class="mini-btn" href="#planner">Update this trip’s details</a> <a class="mini-btn" href="#dashboard">My journeys</a><div class="detail-block"><h2>Conversation</h2>${conversation.messages.map((m) => `<article class="chat-record"><b>${m.role === "user" ? "You" : "Travel team"}</b>${m.role === "assistant" ? partialDraftNotice(m.content) : ""}<pre class="plan-text">${escapeHTML(m.content)}</pre></article>`).join("") || "<p>No messages yet.</p>"}<form id="tripChat"><div class="field"><label>Continue this conversation</label><input name="content" required maxlength="2000"></div><button class="btn" type="submit">Send to travel team</button><div class="form-status" role="status"></div></form></div><div class="detail-block"><h2>Your confirmed trip details</h2>${memoryDetails(context)}</div><h2>Memory events</h2>${(events.events || []).map((event) => memoryEventView(event, id)).join("") || "<p>No active memory events.</p>"}</div></section>`;
}

function labelFields(root) {
  root.querySelectorAll(".field").forEach((field, i) => {
    const label = field.querySelector("label"),
      input = field.querySelector("input,select,textarea");
    if (label && input) {
      input.id ||= "field-" + i;
      label.htmlFor = input.id;
    }
  });
}
function bindSubmit(id, handler) {
  const form = document.getElementById(id);
  if (!form) return;
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (form.dataset.busy) return;
    form.dataset.busy = "true";
    const button = form.querySelector("[type=submit]");
    let status = form.querySelector(".form-status");
    if (!status) {
      status = document.createElement("div");
      status.className = "form-status";
      status.setAttribute("role", "status");
      form.append(status);
    }
    status.textContent = "";
    if (button) button.disabled = true;
    try {
      await handler(form, status);
    } catch (error) {
      status.textContent = error.message;
    } finally {
      delete form.dataset.busy;
      if (button && !form.dataset.locked) button.disabled = false;
    }
  });
}
async function ensureConversation() {
  if (currentConversation) return currentConversation;
  const remembered = sessionStorage.getItem("voyaraTrip:" + state.user.id);
  if (!conversationPromise)
    conversationPromise = (async () => {
      if (remembered) {
        try {
          await api("/assistant/conversations/" + remembered);
          return remembered;
        } catch (error) {
          if (error.status !== 404) throw error;
        }
      }
      return (
        await api("/assistant/conversations", {
          method: "POST",
          body: { title: "New travel chat" },
        })
      ).id;
    })().finally(() => {
      conversationPromise = null;
    });
  currentConversation = await conversationPromise;
  sessionStorage.setItem("voyaraTrip:" + state.user.id, currentConversation);
  return currentConversation;
}
async function askAgents(content, page = "plan") {
  const id = await ensureConversation();
  return api("/assistant/conversations/" + id + "/messages", {
    method: "POST",
    body: { content, page },
  });
}
function bindConcierge(route) {
  const form = document.getElementById("conciergeForm");
  if (!form) return;
  const pages = {
    hotels: "stays",
    tours: "tour_guide",
    planner: "plan",
    contact: "support",
    booking: "support",
    flights: "plan",
  };
  let busy = false;
  const ask = async (value) => {
    if (!requireAuth() || busy || !value.trim()) return;
    busy = true;
    const target = document.getElementById("conciergeReply");
    const buttons = [
      ...form.querySelectorAll("button"),
      ...document.querySelectorAll(".concierge-suggestions button"),
    ];
    buttons.forEach((b) => (b.disabled = true));
    target.textContent = "Your travel team is checking your trip memory…";
    try {
      await journeyUI.open({tripId:routeInfo().query.get("tripId")||undefined,prompt:value.trim(),section:pages[route]||"explore"});
      target.textContent = "Continue in your private Voyara travel chat. Your draft and choices are saved with this trip.";
      target.parentElement.querySelectorAll(".concierge-followup").forEach((link) => link.remove());
      target.insertAdjacentHTML(
        "afterend",
        '<a class="text-link concierge-followup" href="#planner">Confirm trip details →</a>',
      );
      form.reset();
    } catch (error) {
      target.textContent = error.message;
    } finally {
      busy = false;
      buttons.forEach((b) => (b.disabled = false));
    }
  };
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    ask(form.elements.prompt.value);
  });
  document
    .querySelectorAll(".concierge-suggestions button")
    .forEach((b) => b.addEventListener("click", () => ask(b.dataset.prompt)));
}

function bindForms(route, query) {
  document.querySelectorAll("[data-search-tab]").forEach((button) =>
    button.addEventListener("click", () => {
      if (button.dataset.searchTab !== "holiday")
        location.hash = button.dataset.searchTab;
    }),
  );
  bindSubmit("destinationSearch", async (form, status) => {
    const data = new FormData(form),
      q = data.get("q").trim().toLowerCase();
    const rows = state.catalog.destinations.filter(
      (d) =>
        (!q || (d.name + " " + d.desc).toLowerCase().includes(q)) &&
        (data.get("region") === "All" || d.region === data.get("region")) &&
        (data.get("experience") === "All" || d.tag === data.get("experience")),
    );
    document.getElementById("destinationGrid").innerHTML =
      rows.map(referenceViews.destinationTile).join("") ||
      notice(
        "Try another region, experience or destination.",
        "No matching destinations",
      );
    document.getElementById("destinationCount").textContent =
      rows.length +
      (rows.length === 1 ? " Amazing Destination" : " Amazing Destinations");
    status.textContent = rows.length + " destinations found.";
  });
  bindSubmit("quickSearch", async (form, status) => {
    const name = form.elements.destination.value.trim();
    const found = state.catalog.destinations.find(
      (d) => d.name.toLowerCase() === name.toLowerCase(),
    );
    if (!found) {
      status.textContent = "Choose a destination from the suggestions.";
      return;
    }
    sessionStorage.setItem(
      "voyaraSearch",
      JSON.stringify({
        place: found.name,
        date: form.elements.date.value,
        travelers: {
          "2 Adults": 2,
          "1 Adult": 1,
          "2 Adults, 1 Child": 3,
          "4 adults": 4,
          "Group of 6+": 6,
        }[form.elements.travellers.value],
        from: form.elements.from.value,
      }),
    );
    location.hash = "destination/" + encodeURIComponent(found.name);
  });
  bindSubmit("plannerForm", async (form, status) => {
    if (!requireAuth()) return;
    const f = new FormData(form),
      days = Number(f.get("duration")),
      start = f.get("date");
    const destination = state.catalog.destinations.find(
      (d) => d.name === f.get("place"),
    );
    const id = await ensureConversation(),
      path = "/assistant/conversations/" + id;
    await api(path + "/requirements", {
      method: "PUT",
      body: {
        destination:
          destination.name === "Andaman" ? "Andaman Islands" : destination.name,
        start_date: start,
        end_date: addDays(start, days - 1),
        budget: Number(f.get("budget")),
        currency: "INR",
        traveller_count: Number(f.get("group")),
        pace: {
          "Relaxed & slow": "relaxed",
          "A little of everything": "moderate",
          "Active & adventurous": "packed",
          "See as much as possible": "packed",
        }[f.get("pace")],
        interests: f.getAll("interests"),
      },
    });
    const result = await askAgents(
      "Plan my trip" +
        (f.get("notes")?.trim()
          ? ". Additional request: " + f.get("notes").trim()
          : ""),
    );
    const target = document.getElementById("plannerResult");
    target.innerHTML = `<div class="detail-block"><span class="tag">${escapeHTML(result.connection_status)}</span><h2>Your travel team’s response</h2>${partialDraftNotice(result.reply.content)}<pre class="plan-text">${escapeHTML(result.reply.content)}</pre><p>${escapeHTML(result.detail)}</p><a class="mini-btn" href="#trip/${encodeURIComponent(id)}">View conversation & memory</a><div id="savePlanStatus" role="status"></div></div>`;
    target.insertAdjacentHTML("beforeend", agentWork(result.orchestration?.agent_results));
    if (result.orchestration?.status === "ok") {
      const editor = document.createElement("div");
      target.prepend(editor);
      await mountPlanEditor(editor, id, api);
      try {
        await api("/itineraries", {
          method: "POST",
          body: {
            title: destination.name + " · " + days + " days",
            destination_id: destination.destination_id,
            start_date: start,
            end_date: addDays(start, days - 1),
            notes: result.reply.content.slice(0, 4000),
          },
        });
        document.getElementById("savePlanStatus").textContent =
          "Itinerary saved to My Trips.";
      } catch (error) {
        document.getElementById("savePlanStatus").textContent =
          "Your conversation is saved, but the itinerary could not be saved: " +
          error.message;
      }
    }
    status.textContent = "Trip details and response saved to your account.";
    target.scrollIntoView({ behavior: "smooth" });
  });
  const pf = document.getElementById("plannerForm");
  if (pf) {
    if (query.get("agent") === "food")
      pf.querySelector('input[name="interests"][value="Food"]').checked = true;
    pf.insertAdjacentHTML(
      "afterbegin",
      '<button type="button" class="mini-btn" data-action="new-trip">Start a new trip conversation</button>',
    );
    const search = JSON.parse(sessionStorage.getItem("voyaraSearch") || "null");
    if (search) {
      pf.elements.place.value = search.place;
      if (search.date) pf.elements.date.value = search.date;
      pf.elements.group.value = String(search.travelers || 2);
    }
  }
  bindSubmit("bookingForm", async (form, status) => {
    if (!requireAuth()) return;
    const selected = selectedItem(query);
    if (!selected) throw new Error("Select a catalog item again.");
    const { kind, item } = selected,
      f = new FormData(form),
      start = f.get("date"),
      quantity = Number(f.get("travellers"));
    const items =
      kind === "transport"
        ? state.flightSelection.map((r) => ({
            item_type: "transport",
            item_id: r.id,
            quantity,
            start_date: r.date,
          }))
        : [
            {
              item_type: kind,
              item_id: item.id,
              quantity,
              start_date: start,
              ...(kind === "package"
                ? { end_date: addDays(start, item.nights) }
                : kind === "stay"
                  ? { end_date: f.get("end_date") }
                  : {}),
            },
          ];
    const quote = await api("/website/quote", {
      method: "POST",
      body: { items },
    });
    const traveler = Object.fromEntries(
      ["first", "last", "email", "phone", "notes"].map((k) => [k, f.get(k)]),
    );
    traveler.consent = true;
    const request = {
      items,
      traveler,
      request_key: crypto.randomUUID(),
      expected_total_inr: quote.total_inr,
    };
    const review = document.getElementById("bookingReview");
    review.innerHTML = `<div class="detail-block"><div class="eyebrow">REVIEW YOUR REQUEST</div><h2>${money(quote.total_inr)}</h2>${quote.lines.map((l) => `<p>${escapeHTML(l.name)} × ${l.quantity} · ${money(l.total_inr)}</p>`).join("")}<p>${escapeHTML(start)} · ${escapeHTML(traveler.first)} ${escapeHTML(traveler.last)} · ${escapeHTML(traveler.email)}</p><p>${escapeHTML(quote.notice)}</p><button class="btn" id="confirmRequest">Confirm booking request →</button> <button class="mini-btn" id="editRequest">Edit details</button><div id="confirmationStatus" role="status"></div></div>`;
    form.dataset.locked = "true";
    form
      .querySelectorAll("input,select,textarea,button")
      .forEach((el) => (el.disabled = true));
    document.getElementById("editRequest").onclick = () => {
      delete form.dataset.locked;
      review.replaceChildren();
      form
        .querySelectorAll("input,select,textarea,button")
        .forEach((el) => (el.disabled = false));
    };
    document.getElementById("confirmRequest").onclick = async (event) => {
      const button = event.currentTarget;
      const edit = document.getElementById("editRequest");
      button.disabled = true;
      edit.disabled = true;
      try {
        const booking = await api("/website/bookings", {
          method: "POST",
          body: request,
        });
        review.innerHTML =
          notice(
            "Request #" +
              booking.id +
              " is saved to your account. Provider confirmation is still required. No payment has been taken.",
            "Your request is saved",
          ) + '<a class="btn" href="#dashboard">View My Trips →</a>';
        form.hidden = true;
      } catch (error) {
        document.getElementById("confirmationStatus").textContent =
          error.message;
        button.disabled = false;
      } finally {
        edit.disabled = false;
      }
    };
    review.scrollIntoView({ behavior: "smooth" });
  });
  const bf = document.getElementById("bookingForm");
  if (bf) {
    const name = (state.user?.full_name || "").split(" ");
    bf.elements.first.value = name[0] || "";
    bf.elements.last.value = name.slice(1).join(" ");
    bf.elements.email.value = state.user?.email || "";
    bf.elements.phone.value = state.user?.phone || "";
    const search = JSON.parse(sessionStorage.getItem("voyaraSearch") || "null");
    if (search?.date) bf.elements.date.value = search.date;
    if (search?.travelers)
      bf.elements.travellers.value = String(search.travelers);
    if (selectedItem(query)?.kind === "transport") {
      bf.elements.date.value = state.flightSelection[0].date;
      bf.elements.travellers.value = String(state.flightSelection[0].travelers);
    }
    bf.elements.date.addEventListener("change", () => {
      if (bf.elements.end_date)
        bf.elements.end_date.min = addDays(bf.elements.date.value, 1);
    });
    bf.addEventListener("input", () =>
      document.getElementById("bookingReview").replaceChildren(),
    );
  }
  bindSubmit("flightSearch", async (form, status) => {
    const f = new FormData(form),
      params = new URLSearchParams({
        origin_id: f.get("from"),
        destination_id: f.get("to"),
        depart: f.get("depart"),
        travelers: parseInt(f.get("travellers")),
        cabin: f.get("cabin"),
      });
    if (f.get("return")) params.set("return_date", f.get("return"));
    const result = await api("/website/flights?" + params);
    const target = document.getElementById("flightResults");
    const combinations = result.outbound.flatMap((out) =>
      f.get("return") ? result.return.map((back) => [out, back]) : [[out]],
    );
    target.innerHTML = `${notice(result.notice, "Route options")}${combinations.length ? combinations.map((legs, i) => `<article class="flight-card"><div><h3>${legs.map((l) => escapeHTML(l.origin) + " → " + escapeHTML(l.destination)).join(" / ")}</h3><p>${legs.map((l) => escapeHTML(l.date) + " · " + l.duration_min + " min · " + escapeHTML(l.name)).join("<br>")}</p><p>Economy · ${f.get("travellers")}</p></div><div class="price">${money(legs.reduce((sum, l) => sum + l.price_inr, 0))}<small>/ person</small></div><button class="btn" data-flight="${i}">Select route →</button></article>`).join("") : notice("No matching routes are stored. Try New Delhi to Kashmir or choose other airports.", "No routes found")}`;
    target.querySelectorAll("[data-flight]").forEach((b) =>
      b.addEventListener("click", () => {
        state.flightSelection = combinations[Number(b.dataset.flight)].map(
          (l) => ({ ...l, travelers: parseInt(f.get("travellers")) }),
        );
        if(query.get("tripId")){
          if(state.flightSelection.length>1){views.toast("Search an outbound-only route to add a flight to this Travel Book.");return;}
          chooseForLinkedTrip("flight",state.flightSelection[0].id);return;
        }
        location.hash = "booking?type=transport";
      }),
    );
    status.textContent = combinations.length + " route option(s) found.";
  });
  const fs = document.getElementById("flightSearch");
  if (fs) {
    const search = JSON.parse(sessionStorage.getItem("voyaraSearch") || "null");
    const origin = state.catalog.airports.find(
      (a) => a.name === (search?.from || "New Delhi"),
    );
    if (origin) fs.elements.from.value = origin.id;
    const destination = state.catalog.airports.find(
      (a) => a.name === search?.place,
    );
    if (destination) fs.elements.to.value = destination.id;
    if (search?.date) fs.elements.depart.value = search.date;
    if (search?.travelers)
      fs.elements.travellers.value = search.travelers + " adults";
    fs.elements.depart.addEventListener(
      "change",
      () => (fs.elements.return.min = fs.elements.depart.value),
    );
  }
  bindSubmit("contactForm", async (form, status) => {
    const f = Object.fromEntries(new FormData(form));
    f.phone ||= null;
    const result = await api("/website/enquiries", { method: "POST", body: f });
    status.textContent =
      "Enquiry #" + result.reference + " received. " + result.message;
    form.reset();
  });
  bindSubmit("profileForm", async (form, status) => {
    if (!requireAuth()) return;
    const f = new FormData(form);
    state.profile = await api("/profile", {
      method: "PATCH",
      body: {
        travel_style: f.get("travel_style") || null,
        dietary_restrictions: f.get("diet") ? [f.get("diet")] : [],
      },
    });
    status.textContent = "Preferences saved to your account for future trips.";
  });
  bindSubmit("tripChat", async (form, status) => {
    if (!requireAuth()) return;
    status.textContent = "Your travel team is checking your trip memory…";
    await journeyUI.open({tripId:currentConversation,prompt:new FormData(form).get("content")});
    await render();
  });
}

async function toggleSave(kind, id) {
  if (!requireAuth()) return;
  const key = kind + ":" + id;
  if (savingFavorites.has(key)) return;
  savingFavorites.add(key);
  const buttons = [...document.querySelectorAll(`[onclick="toggleSave('${kind}',${id})"]`)];
  buttons.forEach((button) => (button.disabled = true));
  try {
    const exists = state.favorites.some(
      (f) => f.item_type === kind && f.item_id === id,
    );
    await api("/favorites" + (exists ? `/${kind}/${id}` : ""), {
      method: exists ? "DELETE" : "POST",
      ...(!exists ? { body: { item_type: kind, item_id: id } } : {}),
    });
    await loadFavorites();
    // Preserve active filters and scroll position while reflecting server state.
    document
      .querySelectorAll(`[onclick="toggleSave('${kind}',${id})"]`)
      .forEach((b) => {
        b.textContent = exists
          ? b.classList.contains("heart")
            ? "♡"
            : "♡ Save for later"
          : b.classList.contains("heart")
            ? "♥"
            : "♥ Saved";
        b.setAttribute("aria-pressed", String(!exists));
      });
    if (routeInfo().route === "dashboard") await render();
    views.toast(
      exists ? "Removed from your saved items." : "Saved to your account.",
    );
  } finally {
    savingFavorites.delete(key);
    buttons.forEach((button) => (button.disabled = false));
  }
}
function selectedChip(value) {
  document
    .querySelectorAll(".toolbar .chip")
    .forEach((b) => b.classList.toggle("selected", b.textContent === value));
}
function filterDestinations(value) {
  selectedChip(value);
  document.getElementById("destinationGrid").innerHTML =
    state.catalog.destinations
      .filter((d) => value === "All" || d.region === value)
      .map(views.destinationCard)
      .join("");
}
function updatePackages() {
  let rows = state.catalog.destinations.filter(
    (d) => packageFilter === "All" || d.tag === packageFilter,
  );
  if (packageSort !== "featured")
    rows = rows.toSorted((a, b) =>
      packageSort === "low" ? a.price - b.price : b.price - a.price,
    );
  document.getElementById("packageGrid").innerHTML =
    rows.map(views.packageCard).join("") ||
    notice("Try a different category.", "No matching packages");
}
function filterPackages(value) {
  packageFilter = value;
  selectedChip(value);
  updatePackages();
}
function sortPackages(value) {
  packageSort = value;
  updatePackages();
}
function filterExperiences(value) {
  selectedChip(value);
  document.getElementById("experienceGrid").innerHTML =
    state.catalog.experiences
      .filter((x) => value === "All" || x.type === value)
      .map(views.experienceCard)
      .join("") || notice("Try another experience type.");
}
function filterHotels() {
  const value = document.getElementById("hotelSearch").value.toLowerCase();
  document.getElementById("hotelGrid").innerHTML =
    state.catalog.hotels
      .filter(
        (h) =>
          (hotelFilter === "All stays" ||
            h.type.toLowerCase().includes(hotelFilter.toLowerCase())) &&
          (h.name + " " + h.place + " " + h.type).toLowerCase().includes(value),
      )
      .map(views.hotelCard)
      .join("") ||
    notice("Try a different place or stay type.", "No matching stays");
}
function hotelType(value) {
  hotelFilter = value;
  selectedChip(value);
  filterHotels();
}
function bookHotel(id) {
  if(routeInfo().query.get("tripId")){chooseForLinkedTrip("stay",id);return;}
  location.hash = "booking?type=stay&id=" + id;
}
async function chooseForLinkedTrip(kind,itemId){
  try{
    const id=routeInfo().query.get("tripId");if(!id||!requireAuth())return;
    const work=await api(`/assistant/conversations/${encodeURIComponent(id)}/workspace`);
    await api(`/assistant/conversations/${encodeURIComponent(id)}/selections`,{method:"POST",body:{expected_revision:work.revision,kind,item_id:itemId}});
    location.hash="travel-book/"+encodeURIComponent(id);
  }catch(error){views.toast(error.message);}
}
async function bindTripDeepLink(route,id){
  const work=await api(`/assistant/conversations/${encodeURIComponent(id)}/workspace`);
  currentConversation=id;sessionStorage.setItem("voyaraTrip:"+state.user.id,id);
  const bar=document.createElement("div");bar.className="journey-context-bar";
  bar.innerHTML=`<span>Editing your ${escapeHTML(work.draft.destination||"saved")} trip · selections are drafts</span><a href="#travel-book/${encodeURIComponent(id)}">Return to my Travel Book</a><a href="#chat?tripId=${encodeURIComponent(id)}">Edit with Voyara AI</a>`;
  app.querySelector(".section .container")?.prepend(bar);
  if(route==="hotels"){
    const allowed=new Set(work.options.stays.map(s=>s.id));
    document.getElementById("hotelGrid").innerHTML=state.catalog.hotels.filter(h=>allowed.has(h.id)).map(views.hotelCard).join("")||notice("No matching stays are listed for this trip.");
    const input=document.getElementById("hotelSearch");if(input)input.placeholder="Search this trip’s destination or browse the matched stays";
  }
  if(route==="tours"){
    const allowed=new Set(work.options.experiences.map(s=>s.id));
    const grid=document.getElementById("experienceGrid");if(grid)grid.innerHTML=state.catalog.experiences.filter(e=>allowed.has(e.id)).map(views.experienceCard).join("")||notice("No matching experiences are listed for this trip.");
  }
  if(route==="flights"){
    const form=document.getElementById("flightSearch");if(!form)return;
    const origin=state.catalog.airports.find(a=>a.name===work.draft.origin),destination=state.catalog.airports.find(a=>a.name===(work.draft.destination==="Kerala"?"Kochi":work.draft.destination));
    if(origin)form.elements.from.value=origin.id;if(destination)form.elements.to.value=destination.id;
    if(work.draft.start_date)form.elements.depart.value=work.draft.start_date;
    if(work.draft.traveller_count)form.elements.travellers.value=work.draft.traveller_count+" adults";
    form.elements.return.value="";
  }
}
function bookExperience(id) {
  if(routeInfo().query.get("tripId")){chooseForLinkedTrip("experience",id);return;}
  location.hash = "booking?type=experience&id=" + id;
}
// The supplied layout uses inline handlers. Expose only its small, explicit API.
Object.assign(window, {
  filterDestinations,
  filterPackages,
  sortPackages,
  filterExperiences,
  filterHotels,
  hotelType,
  bookHotel,
  bookExperience,
  toggleSave: (kind, id) =>
    toggleSave(kind, id).catch((error) => views.toast(error.message)),
});

app.addEventListener("click", async (event) => {
  const b = event.target.closest("[data-action]");
  if (!b || b.disabled) return;
  b.disabled = true;
  try {
    const action = b.dataset.action;
    if(action==="open-travel-chat")await journeyUI.open();
    else if(action==="open-travel-book")await journeyUI.startBook();
    else if(action==="plan-kerala"){
      if(!requireAuth())return;
      const trip=await api("/assistant/conversations",{method:"POST",body:{title:"Kerala · your journey"}});
      const work=await api(`/assistant/conversations/${trip.id}/workspace`);
      await api(`/assistant/conversations/${trip.id}/workspace`,{method:"PUT",body:{expected_revision:work.revision,draft:{destination:"Kerala"}}});
      currentConversation=trip.id;sessionStorage.setItem("voyaraTrip:"+state.user.id,trip.id);location.hash="travel-book/"+trip.id;
    }
    else if (action === "retry") await render();
    else if (action === "new-trip") {
      currentConversation = null;
      if (state.user) sessionStorage.removeItem("voyaraTrip:" + state.user.id);
      document.getElementById("plannerResult")?.replaceChildren();
      views.toast("The next plan will start a new trip conversation.");
    } else if (action === "logout") {
      await api("/auth/logout", { method: "POST" });
      window.google?.accounts?.id.disableAutoSelect();
      if (state.user) sessionStorage.removeItem("voyaraTrip:" + state.user.id);
      state.user = null;
      journeyUI.reset();
      state.favorites = [];
      state.bookings = [];
      state.itineraries = [];
      state.conversations = [];
      currentConversation = null;
      views.setSaved([]);
      updateAccount();
      location.hash = "home";
    } else if (action === "cancel") {
      await api("/bookings/" + b.dataset.id + "/cancel", { method: "POST" });
      await render();
    } else if (action === "delete-itinerary") {
      await api("/itineraries/" + b.dataset.id, { method: "DELETE" });
      await render();
    } else if (action === "forget-trip") {
      await api("/assistant/conversations/" + b.dataset.id, {
        method: "DELETE",
      });
      if (currentConversation === b.dataset.id) {
        currentConversation = null;
        sessionStorage.removeItem("voyaraTrip:" + state.user.id);
      }
      await render();
    } else if (action === "forget-event") {
      await api(
        "/assistant/conversations/" +
          b.dataset.trip +
          "/memory-events/" +
          b.dataset.id,
        { method: "DELETE" },
      );
      await render();
    }
  } catch (error) {
    views.toast(error.message);
  } finally {
    b.disabled = false;
  }
});
document.getElementById("menuToggle").addEventListener("click", () => {
  const open = document.getElementById("mainNav").classList.toggle("open");
  document
    .getElementById("menuToggle")
    .setAttribute("aria-expanded", String(open));
});
document.getElementById("mainNav").addEventListener("click", (event) => {
  if (!event.target.closest("a")) return;
  document.getElementById("mainNav").classList.remove("open");
  document.getElementById("menuToggle").setAttribute("aria-expanded", "false");
});
document
  .getElementById("newsletter")
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget,
      button = form.querySelector("button"),
      status = document.getElementById("newsletterMsg");
    if (form.dataset.busy) return;
    form.dataset.busy = "true";
    button.disabled = true;
    try {
      const result = await api("/website/newsletter", {
        method: "POST",
        body: { email: form.querySelector("input").value },
      });
      status.textContent = result.message;
      form.reset();
    } catch (error) {
      status.textContent = error.message;
    } finally {
      delete form.dataset.busy;
      button.disabled = false;
    }
  });
async function boot() {
  app.innerHTML = notice("Your next journey is loading…");
  try {
    state.catalog = applyReferencePhotos(await api("/website/catalog"));
    if (!state.catalog.destinations.length)
      throw new Error("The catalog is empty. Run the backend seed command.");
    views.setCatalog(state.catalog);
    try {
      state.user = await api("/auth/me");
    } catch (error) {
      if (error.status !== 401) throw error;
    }
    await loadFavorites();
    updateAccount();
    if (location.pathname !== "/" && !location.hash) {
      const alias = {
        plan: "planner",
        explore: "destinations",
        stays: "hotels",
        support: "contact",
      };
      const path = location.pathname.slice(1);
      history.replaceState(null, "", "/#" + (alias[path] || path));
    }
    window.addEventListener("hashchange", render);
    await render();
  } catch (error) {
    app.innerHTML = `<section class="section"><div class="container">${notice(error.message, "Unable to load Voyara")}<button class="btn" id="retryBoot">Try again</button></div></section>`;
    document.getElementById("retryBoot").onclick = boot;
  }
}
boot();
window.addEventListener("voyara-trip-updated",async event=>{const route=routeInfo();if(route.route==="travel-book"&&route.param===event.detail.tripId){const y=scrollY;await render();window.scrollTo({top:y,behavior:"instant"});}});
