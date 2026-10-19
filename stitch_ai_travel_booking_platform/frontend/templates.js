export function createViews({ escapeHTML, airportOptions, today }) {
  const img = (id, w = 900) =>
    `https://images.unsplash.com/${id.startsWith("photo-") ? id : "photo-" + id}?auto=format&fit=crop&w=${w}&q=82`;
  const money = (n) => "₹" + Number(n).toLocaleString("en-IN");
  const photo = (id) =>
    `https://images.unsplash.com/${/^photo-[a-zA-Z0-9-]+$/.test(id) ? id : "photo-1709338573277-c161cbf8702c"}?auto=format&fit=crop&w=900&q=82`;
  let saved = [];
  let destinations = [],
    experiences = [],
    hotels = [];

  const app = document.getElementById("app");
  let activeFilter = "All";
  function toast(message) {
    const t = document.getElementById("toast");
    t.textContent = message;
    t.classList.add("show");
    clearTimeout(window.toastTimer);
    window.toastTimer = setTimeout(() => t.classList.remove("show"), 2600);
  }

  function pageHero(
    kicker,
    title,
    desc,
    imageId = "photo-1595815771614-ade9d652a65d",
  ) {
    return `<section class="page-hero"><img class="page-hero-art" src="${photo(imageId)}" alt=""><div class="container"><div class="interior-hero-copy"><div class="eyebrow">${kicker}</div><h1>${title}</h1><p>${desc}</p><a class="interior-hero-link" href="#destinations">Explore India <span aria-hidden="true">↗</span></a></div></div><span class="interior-hero-trail" aria-hidden="true">✧</span></section>`;
  }

  function sectionHead(kicker, title, desc, link = "") {
    return `<div class="section-head"><div><div class="eyebrow">${kicker}</div><h2>${title}</h2>${desc ? `<p>${desc}</p>` : ""}</div>${link ? `<a class="text-link" href="${link}">Explore all <span>→</span></a>` : ""}</div>`;
  }

  function destinationCard(d) {
    return `<article class="destination-card"><a href="#destination/${encodeURIComponent(d.name)}"><div class="destination-photo" style="background-image:url('${photo(d.img)}')"><span class="photo-label">${escapeHTML(d.tag.toUpperCase())}</span><h3>${escapeHTML(d.name)}</h3></div></a><div class="card-body"><p>${escapeHTML(d.desc)}</p><div class="meta-row"><span class="rating"><b>★</b> ${escapeHTML(d.rating)} <span>(${escapeHTML(d.reviews)})</span></span><span>◷ ${d.nights} Nights</span></div><div class="card-actions"><div class="price">${money(d.price)} <small>/ person</small></div><a class="mini-btn" href="#destination/${encodeURIComponent(d.name)}">Explore →</a></div></div></article>`;
  }

  function packageCard(d) {
    return `<article class="package-card"><div class="package-image" style="background-image:url('${photo(d.img)}')"><span class="tag ${d.tag === "Best seller" ? "orange" : ""}">${escapeHTML(d.tag)}</span><button class="heart" aria-label="Save ${escapeHTML(d.name)}" onclick="toggleSave('package',${d.id})">${saved.includes("package:" + d.id) ? "♥" : "♡"}</button></div><div class="card-body"><a href="#package/${encodeURIComponent(d.name)}"><h3>${escapeHTML(d.name)} escape</h3></a><div class="meta-row"><span class="rating"><b>★</b> ${escapeHTML(d.rating)} (${escapeHTML(d.reviews)})</span><span>◷ ${d.nights}N / ${d.nights + 1}D</span></div><p style="margin-top:10px">${escapeHTML(d.desc)}</p><div class="card-actions"><div><small style="color:var(--muted);font-size:10px">Starting from</small><div class="price">${money(d.price)} <small>/ person</small></div></div><a class="mini-btn" href="#package/${encodeURIComponent(d.name)}">View trip →</a></div></div></article>`;
  }

  function experienceCard(e) {
    return `<article class="experience-card"><div class="package-image" style="background-image:url('${photo(e.img)}')"><span class="tag">${escapeHTML(e.type)}</span></div><div class="card-body"><div class="meta-row"><span>⌖ ${escapeHTML(e.place)}</span><span>★ 4.8</span></div><h3 style="margin-top:10px">${escapeHTML(e.name)}</h3><p>${escapeHTML(e.desc)}</p><div class="card-actions"><div class="price">${money(e.price)} <small>/ person</small></div><button class="mini-btn" onclick="bookExperience(${e.id})">Book experience →</button></div></div></article>`;
  }

  function hotelCard(h) {
    return `<article class="hotel-card"><div class="package-image" style="background-image:url('${photo(h.img)}')"><span class="tag blue">${escapeHTML(h.type)}</span><button class="heart" aria-label="Save hotel" onclick="toggleSave('stay',${h.id})">${saved.includes("stay:" + h.id) ? "♥" : "♡"}</button></div><div class="card-body"><div class="meta-row"><span>⌖ ${escapeHTML(h.place)}</span><span class="rating"><b>★</b> ${escapeHTML(h.rating)}</span></div><h3 style="margin-top:10px">${escapeHTML(h.name)}</h3><p>${escapeHTML(h.amenities)}</p><div class="card-actions"><div class="price">${money(h.price)} <small>/ night</small></div><button class="mini-btn" onclick="bookHotel(${h.id})">View rooms →</button></div></div></article>`;
  }

  function home() {
    return `<section class="hero"><div class="container"><div class="hero-copy"><div class="eyebrow">YOUR NEXT CHAPTER STARTS HERE</div><h1>India is calling.<br><span style="color:#ffbd65">Let’s go together.</span></h1><p>From snow-capped mountains to golden beaches, discover the places, people and little moments that make a trip unforgettable — with your AI travel team by your side.</p><div class="hero-buttons"><a class="btn" href="#planner">Plan my trip with AI ✦</a><a class="btn btn-outline" href="#destinations">Explore destinations ↗</a></div><div class="trust-row"><div class="avatar-stack"><span>☺</span><span>✦</span><span>☻</span></div><span>Plan at your own pace</span><span class="stars">★★★★★</span><b>India, your way</b></div></div></div></section><div class="container"><form class="search-panel" id="quickSearch"><div class="field"><label>Where would you like to go?</label><input name="destination" placeholder="Search destinations in India" list="destinationList"><datalist id="destinationList">${destinations.map((d) => `<option>${escapeHTML(d.name)}</option>`).join("")}</datalist></div><div class="field"><label>Departure from</label><select name="from"><option>New Delhi</option><option>Mumbai</option><option>Bengaluru</option><option>Hyderabad</option><option>Chennai</option></select></div><div class="field"><label>Travel date</label><input type="date" name="date" min="${today()}"></div><div class="field"><label>Travellers</label><select name="travellers"><option>2 Adults</option><option>1 Adult</option><option>2 Adults, 1 Child</option><option>4 adults</option><option>Group of 6+</option></select></div><button class="btn" type="submit">Search trips <span>⌕</span></button></form><div class="chips"><span style="font-size:11px;color:var(--muted);padding:8px">Popular:</span>${["Kashmir", "Manali", "Jaipur", "Goa", "Kerala", "Udaipur", "Varanasi"].map((n) => `<a class="chip" href="#destination/${n}">${n}</a>`).join("")}</div></div><section class="section"><div class="container">${sectionHead("FIND YOUR KIND OF INDIA", "Where will your story take you?", "Handpicked places for every pace, from mountain mornings to barefoot beach days.", "#destinations")}<div class="grid grid-4">${destinations.slice(0, 4).map(destinationCard).join("")}</div></div></section><section class="section" style="background:#edf5f8"><div class="container">${sectionHead("MADE FOR YOUR TRAVEL STYLE", "Holiday packages worth remembering", "Thoughtfully planned escapes, with the details taken care of.", "#packages")}<div class="grid grid-3">${[destinations[0], destinations[3], destinations[4]].map(packageCard).join("")}</div></div></section><section class="section"><div class="container"><div class="feature-band"><div><div class="eyebrow">YOUR PERSONAL TRAVEL TEAM</div><h2>Big dream. Little planning stress.</h2><p>Tell us what you love. Our AI travel team brings destination ideas, day-wise itineraries, stays and budget tips together into one thoughtful plan.</p><a class="btn" href="#planner">Meet your AI travel team ✦</a></div><div style="font-size:90px;opacity:.85">✈️</div></div></div></section><section class="section"><div class="container">${sectionHead("SMALL GROUPS, BIG MEMORIES", "Experiences that bring you closer", "Meet local experts and find a different side of every destination.", "#tours")}<div class="grid grid-3">${experiences.slice(0, 3).map(experienceCard).join("")}</div></div></section>`;
  }

  function destinationsPage() {
    return `${pageHero("EXPLORE INDIA", "Find your next India escape", "From Himalayan hideaways to tropical coastlines, discover a destination that feels like you.", "photo-1626621341517-bbf3d9990a23")}<section class="section"><div class="container"><div class="toolbar"><div class="filters">${["All", "North India", "West India", "South India", "East India", "Islands"].map((f) => `<button class="chip ${activeFilter === f ? "selected" : ""}" onclick="filterDestinations('${f}')">${f}</button>`).join("")}</div><span class="subtext">${destinations.length} remarkable places to begin</span></div><div class="grid grid-2" id="destinationGrid">${destinations
      .filter((d) => activeFilter === "All" || d.region === activeFilter)
      .map(destinationCard)
      .join("")}</div></div></section>`;
  }

  function packagesPage(query) {
    const place = query?.get ? (query.get("place") || query.get("destination") || "") : "";
    const filtered = place
      ? destinations.filter((d) => d.name.toLowerCase().includes(place.toLowerCase()) || (d.region && d.region.toLowerCase().includes(place.toLowerCase())))
      : destinations;
    const initialList = filtered.length ? filtered : destinations;
    return `${pageHero("HOLIDAYS, YOUR WAY", place ? `Packages in ${escapeHTML(place)}` : "A little more wonder in every getaway", place ? `Explore curated holiday packages and tailor-made journeys in ${escapeHTML(place)}.` : "Explore thoughtfully designed India holiday packages with clear pricing, flexible options and room to make the trip your own.", "photo-1595815771614-ade9d652a65d")}<section class="section"><div class="container"><div class="toolbar"><div class="filters">${["All", "Best seller", "Adventure", "Cultural", "Beach", "Wellness", "Spiritual"].map((f) => `<button class="chip ${activeFilter === f ? "selected" : ""}" onclick="filterPackages('${f}')">${f}</button>`).join("")}</div><div class="field" style="min-width:190px"><select id="packageSort" onchange="sortPackages(this.value)" aria-label="Sort packages"><option value="featured">Sort: Recommended</option><option value="low">Price: Low to high</option><option value="high">Price: High to low</option></select></div></div><div class="grid grid-3" id="packageGrid">${initialList.map(packageCard).join("")}</div></div></section>`;
  }

  function toursPage(query) {
    const place = query?.get ? (query.get("place") || query.get("destination") || "") : "";
    const filteredExp = place
      ? experiences.filter((e) => (e.place && e.place.toLowerCase() === place.toLowerCase()) || e.name.toLowerCase().includes(place.toLowerCase()))
      : experiences;
    const initialList = filteredExp.length ? filteredExp : experiences;
    return `${pageHero("LOCAL STORIES, REAL MOMENTS", place ? `Experiences in ${escapeHTML(place)}` : "Experiences beyond the usual", place ? `Curated local tours, alpine adventures and cultural trails in ${escapeHTML(place)}.` : "Join passionate local guides for active adventures, food trails, heritage walks and restorative escapes.", "photo-1551632811-561732d1e306")}<section class="section"><div class="container"><div class="toolbar"><div class="filters">${["All", "Adventure", "Culture", "Nature", "Spiritual", "Food"].map((f) => `<button class="chip ${activeFilter === f ? "selected" : ""}" onclick="filterExperiences('${f}')">${f}</button>`).join("")}</div><span class="subtext">${initialList.length} experiences in ${escapeHTML(place || "India")}</span></div><div class="grid grid-3" id="experienceGrid">${initialList.map(experienceCard).join("")}</div></div></section>`;
  }

  function hotelsPage(query) {
    const place = query?.get ? (query.get("place") || query.get("destination") || "") : "";
    const filteredHotels = place
      ? hotels.filter((h) => (h.place && h.place.toLowerCase() === place.toLowerCase()) || h.name.toLowerCase().includes(place.toLowerCase()))
      : hotels;
    const initialList = filteredHotels.length ? filteredHotels : hotels;
    return `${pageHero("STAYS THAT FEEL RIGHT", place ? `Stays in ${escapeHTML(place)}` : "Find your home away from home", place ? `Handpicked mountain lodges, boutique stays and luxury retreats in ${escapeHTML(place)}.` : "From characterful heritage havelis to quiet mountain retreats, choose stays that make the journey even better.", "photo-1566073771259-6a8506099945")}<section class="section"><div class="container"><div class="toolbar"><div class="field" style="max-width:300px"><input id="hotelSearch" placeholder="Search by hotel or destination" value="${escapeHTML(place)}" oninput="filterHotels(this.value)"></div><div class="filters">${["All stays", "Heritage", "Mountain", "Beachside", "Backwater"].map((f) => `<button class="chip" onclick="hotelType('${f}')">${f}</button>`).join("")}</div></div><div class="grid grid-3" id="hotelGrid">${initialList.map(hotelCard).join("")}</div></div></section>`;
  }

  function destinationDetail(name, kind = "destination") {
    const d =
      destinations.find(
        (x) => x.name.toLowerCase() === (name || "Kashmir").toLowerCase(),
      ) || destinations[0];
    const highlights = Array.isArray(d.highlights) && d.highlights.length
      ? `<div class="detail-block"><h2>Top highlights</h2><ul class="check-list">${d.highlights.map((h) => `<li>${escapeHTML(h)}</li>`).join("")}</ul></div>`
      : "";
    const extraMeta = [
      d.best_season ? `<div><b style="color:var(--navy)">Best season</b><p>${escapeHTML(d.best_season)}</p></div>` : "",
      d.climate ? `<div><b style="color:var(--navy)">Climate</b><p>${escapeHTML(d.climate)}</p></div>` : "",
    ].join("");
    return `${pageHero(`${(d.region||"Explore").toUpperCase()} · ${escapeHTML((d.tag||"Explore").toUpperCase())}`, `Discover ${escapeHTML(d.name)}`, d.desc, d.img)}<section class="section"><div class="container"><div class="detail-layout"><div><div class="detail-gallery"><img src="${photo(d.img)}" alt="${escapeHTML(d.name)} scenery"><img src="${photo(destinations[(destinations.indexOf(d) + 1) % destinations.length].img)}" alt="Local scenery"><img src="${photo(destinations[(destinations.indexOf(d) + 2) % destinations.length].img)}" alt="Travel experience"></div><div class="detail-block" style="margin-top:20px"><span class="tag">${escapeHTML(d.tag||"Explore")}</span><h2 style="margin-top:14px">The best of ${escapeHTML(d.name)}</h2><p>${escapeHTML(d.desc)} Explore at your own pace with local recommendations, carefully chosen stays and experiences that bring the region to life. Voyara helps you balance the must-sees with the little discoveries you'll remember most.</p><div class="grid grid-3"><div><b style="color:var(--navy)">Best for</b><p>Couples, families &amp; explorers</p></div><div><b style="color:var(--navy)">Ideal duration</b><p>${d.nights} nights / ${d.nights + 1} days</p></div><div><b style="color:var(--navy)">Traveller rating</b><p>★ ${escapeHTML(d.rating)}/5</p></div>${extraMeta}</div></div>${highlights}<div class="detail-block"><h2>Suggested itinerary</h2>${[
      `Arrive &amp; settle in`,
      `Explore local highlights`,
      `A day for experiences`,
      `Slow morning &amp; hidden gems`,
      `Your favourite discoveries`,
      `Scenic day trip`,
      `Departure day`,
    ]
      .slice(0, d.nights + 1)
      .map(
        (t, i) =>
          `<div class="itinerary-item"><div class="day-badge">DAY ${i + 1}</div><div><b style="color:var(--navy)">${t}</b><p style="margin:5px 0 0">${["Arrive, check in and enjoy a relaxed introduction to the destination.", "Discover signature sights with time for local food and photos.", "Choose a guided activity or a scenic day trip at your own pace.", "Leave room for a café stop, market visit or an unplanned detour.", "Enjoy a flexible day tailored to your interests and travel style.", "A longer excursion or a scenic discovery beyond the town centre.", "Breakfast, check-out and onward travel with support if plans change."][i]}</p></div></div>`,
      )
      .join(
        "",
      )}</div><div class="detail-block"><h2>Why travel with Voyara?</h2><ul class="check-list"><li>Handpicked local stays and experiences</li><li>Flexible itinerary suggestions</li><li>Transparent package inclusions</li><li>Human support before and during your trip</li></ul></div></div><aside class="sticky-card"><div class="eyebrow">YOUR GETAWAY STARTS HERE</div><h3>${escapeHTML(d.name)} escape</h3><div class="rating"><b>★</b> ${escapeHTML(d.rating)} <span style="color:var(--muted);font-weight:400">(${escapeHTML(d.reviews||"–")} reviews)</span></div><div class="price">${money(d.price)} <small>/ person</small></div><p class="subtext">From · ${d.nights} nights · Customisable</p><ul class="check-list"><li>Stay options to suit your style</li><li>Curated local experiences</li><li>Flexible day-wise plan</li><li>Travel support included</li></ul><a class="btn" style="width:100%" href="#booking?place=${encodeURIComponent(d.name)}">Plan this trip →</a><a class="btn btn-outline" style="width:100%;margin-top:8px" href="#hotels?place=${encodeURIComponent(d.name)}">View Stays in ${escapeHTML(d.name)}</a><a class="btn btn-outline" style="width:100%;margin-top:8px" href="#tours?place=${encodeURIComponent(d.name)}">View Experiences</a><button class="btn btn-outline" style="width:100%;margin-top:8px" onclick="toggleSave('package',${d.id})">${saved.includes("package:" + d.id) ? "♥ Saved" : "♡ Save for later"}</button><p style="font-size:10px;text-align:center;color:var(--muted);margin-top:14px">No payment needed to start planning.</p></aside></div></div></section>`;
  }

  function packageDetail(name) {
    const d =
      destinations.find(
        (x) => x.name.toLowerCase() === (name || "Kashmir").toLowerCase(),
      ) || destinations[0];
    return `${pageHero("VOYARA SIGNATURE HOLIDAYS", `${escapeHTML(d.name)}: the thoughtfully planned escape`, `${d.nights} nights of local discovery, comfortable stays and memorable experiences — with flexibility built in.`, d.img)}<section class="section"><div class="container"><div class="detail-layout"><div><div class="detail-gallery"><img src="${photo(d.img)}" alt="${escapeHTML(d.name)}"><img src="${photo(destinations[3].img)}" alt="Travel"><img src="${photo(destinations[4].img)}" alt="Nature"></div><div class="detail-block" style="margin-top:20px"><h2>Your trip at a glance</h2><div class="grid grid-3"><div><span class="tag">Duration</span><p>${d.nights} nights / ${d.nights + 1} days</p></div><div><span class="tag">Travel style</span><p>Comfort & discovery</p></div><div><span class="tag">Group</span><p>Private / small group</p></div></div><p>${escapeHTML(d.desc)} This sample package gives you a considered starting point, then lets you personalise the pace, hotel category and experiences before confirming.</p></div><div class="detail-block"><h2>Day-by-day itinerary</h2>${Array.from({ length: d.nights + 1 }, (_, i) => `<div class="itinerary-item"><div class="day-badge">DAY ${i + 1}</div><div><b style="color:var(--navy)">${["Welcome to " + d.name, "Landmarks & local flavour", "A signature experience", "Your day, your way", "Scenic discoveries", "A slower morning", "Farewell for now"][Math.min(i, 6)]}</b><p>Suggested activities, comfortable transfer options and time to enjoy the destination without feeling rushed.</p></div></div>`).join("")}</div><div class="detail-block"><h2>What’s included</h2><ul class="check-list"><li>${d.nights} nights in selected accommodation</li><li>Daily breakfast at the stay</li><li>Curated sightseeing recommendations</li><li>Local experiences as listed in your final plan</li><li>Pre-trip assistance and on-trip support</li></ul><h3>Not included</h3><p>Flights, personal expenses, optional activities and anything not specifically listed in your final booking confirmation.</p></div></div><aside class="sticky-card"><div class="eyebrow">PACKAGE PRICE</div><h3>${escapeHTML(d.name)} discovery</h3><div class="price">${money(d.price)} <small>/ person</small></div><p class="subtext">Indicative starting price. Final price depends on dates, stay and group size.</p><ul class="check-list"><li>Customise your travel dates</li><li>Choose your stay category</li><li>Review inclusions before paying</li></ul><a href="#booking?place=${encodeURIComponent(d.name)}" class="btn" style="width:100%">Customise & book →</a><a href="#hotels?place=${encodeURIComponent(d.name)}" class="btn btn-outline" style="width:100%;margin-top:8px">Explore Stays in ${escapeHTML(d.name)}</a><a href="#tours?place=${encodeURIComponent(d.name)}" class="btn btn-outline" style="width:100%;margin-top:8px">Explore Experiences</a><a href="#planner" class="btn btn-outline" style="width:100%;margin-top:8px">Ask AI to personalise</a></aside></div></div></section>`;
  }

  function plannerPage() {
    return `${pageHero("YOUR AI TRAVEL TEAM", "A trip that feels like you", "Share a few details and let your travel team turn your ideas into a practical, personalised itinerary.", "photo-1709338573277-c161cbf8702c")}<section class="section"><div class="container"><div class="booking-layout"><form class="form-card" id="plannerForm"><div class="eyebrow">LET’S BUILD YOUR JOURNEY</div><h2 style="font:800 25px Manrope;color:var(--navy);margin:0 0 7px">Tell us what you have in mind</h2><p class="subtext" style="margin-bottom:23px">No perfect answers needed. You can change anything later.</p><div class="form-grid"><div class="field"><label>Where would you like to go?</label><select name="place" required>${destinations.map((d) => `<option>${escapeHTML(d.name)}</option>`).join("")}</select></div><div class="field"><label>When are you travelling?</label><input type="date" name="date" min="${today()}" required></div><div class="field"><label>Trip duration</label><select name="duration"><option value="3">3 days</option><option value="5" selected>5 days</option><option value="7">7 days</option><option value="10">10 days</option></select></div><div class="field"><label>Number of travellers</label><select name="group"><option value="1">1 traveller</option><option value="2" selected>2 travellers</option><option value="3">3 travellers</option><option value="4">4 travellers</option><option value="6">6 travellers</option></select></div><div class="field"><label>Total trip budget (INR)</label><input name="budget" type="number" value="60000" min="1" max="1000000000" required></div><div class="field"><label>Travel pace</label><select name="pace"><option>Relaxed & slow</option><option selected>A little of everything</option><option>Active & adventurous</option><option>See as much as possible</option></select></div><div class="field full"><label>What do you love doing?</label><div class="filters">${["Nature", "Food", "Culture", "Adventure", "Wellness", "Shopping", "Photography", "Spiritual"].map((x) => `<label class="chip"><input type="checkbox" name="interests" value="${x}" style="accent-color:var(--orange)"> ${x}</label>`).join("")}</div></div><div class="field full"><label>Additional request (optional; may need clarification)</label><textarea name="notes" placeholder="Notes may need clarification. Confirm exact requirements in the fields above."></textarea></div></div><button class="btn" style="margin-top:20px" type="submit">Create my trip outline ✦</button><p style="font-size:10px;color:var(--muted)">Your confirmed details are saved to your private trip memory and used by the connected travel agents.</p></form><div><div class="detail-block"><div class="agent-icon">✦</div><h2>Meet your AI travel team</h2><p>Each specialist brings a different lens to your trip. Together, they help you plan with more confidence.</p><div class="itinerary-item"><div class="day-badge">01</div><div><b>Explore Agent</b><p>Finds places that fit your style.</p></div></div><div class="itinerary-item"><div class="day-badge">02</div><div><b>Trip Consultant</b><p>Shapes the day-wise itinerary.</p></div></div><div class="itinerary-item"><div class="day-badge">03</div><div><b>Stay Agent</b><p>Suggests accommodation options.</p></div></div><div class="itinerary-item"><div class="day-badge">04</div><div><b>Budget & Booking Agent</b><p>Keeps costs clear and practical.</p></div></div></div><div class="detail-block"><h3>Good to know</h3><p>The travel agents use your confirmed details and available research sources. Provider prices and availability still need confirmation. No payment is collected.</p></div></div></div><div id="plannerResult" style="margin-top:25px"></div></div></section>`;
  }

  function flightsPage(query) {
    const toDefault = query?.get ? (query.get("to") || query.get("place") || "Kashmir") : "Kashmir";
    const fromDefault = query?.get ? (query.get("from") || "New Delhi") : "New Delhi";
    return `<section class="reference-hero home-hero"><div class="hero-scene" style="background-image:url('${photo("photo-1436491865332-7a61a109cc05")}')"></div><div class="container reference-hero-inner"><div class="reference-hero-copy"><span class="paint-label">TRANSIT & ROUTES</span><h1>Seamless Travel Across India.<br>Flights, Trains &amp; Buses.</h1><p>Compare high-speed express trains, luxury sleeper buses, and domestic flights — powered by Voyara's Route &amp; Transit AI Specialists.</p><div class="hero-assurance"><span class="assurance-symbol">✦</span><span>Handpicked transit connections across India.<br><small>Comfort, speed and transparent fares curated for your journey.</small></span></div></div><aside class="travel-team"><h2>✦ Meet Your Route Specialists</h2><div class="team-list"><div class="team-row"><span class="team-icon tone-sky">✈️</span><span><strong>Transit Agent</strong><small>Optimises flight &amp; train corridors</small></span></div><div class="team-row"><span class="team-icon tone-peach">🚂</span><span><strong>Rail Consultant</strong><small>Vande Bharat &amp; Rajdhani routes</small></span></div><div class="team-row"><span class="team-icon tone-mint">🚌</span><span><strong>Coach Specialist</strong><small>Premium sleeper &amp; expressway buses</small></span></div><div class="team-row"><span class="team-icon tone-violet">₹</span><span><strong>Fare &amp; Booking</strong><small>Clear pricing with zero surprise fees</small></span></div></div><p>Intelligently paired for your itinerary ✦</p></aside></div></section><section class="container search-surface" style="margin-top:-36px" aria-label="Search travel routes"><div class="travel-tabs" id="travelModeTabs" aria-label="Transport Mode"><button type="button" class="travel-tab active" data-travel-mode="all"><span>✦</span> All Modes</button><button type="button" class="travel-tab" data-travel-mode="flight"><span>✈️</span> Flights</button><button type="button" class="travel-tab" data-travel-mode="train"><span>🚂</span> Trains</button><button type="button" class="travel-tab" data-travel-mode="bus"><span>🚌</span> Buses</button></div><form id="flightSearch" class="reference-search"><input type="hidden" name="mode" value="all"><div class="field"><label>Departure from</label><div class="search-value"><select name="from">${airportOptions(fromDefault)}</select></div></div><div class="field"><label>Going to</label><div class="search-value"><select name="to">${airportOptions(toDefault)}</select></div></div><div class="field"><label>Travel Date</label><div class="search-value"><input type="date" name="depart" required min="${today()}"></div></div><div class="field"><label>Return Date</label><div class="search-value"><input type="date" name="return" min="${today()}"></div></div><div class="field" style="border-right:0"><label>Travellers &amp; Class</label><div class="search-value" style="display:flex;gap:6px"><select name="travellers" style="flex:1"><option>1 adult</option><option selected>2 adults</option><option>3 adults</option><option>4 adults</option></select><select name="cabin" style="flex:1"><option>Economy</option><option>Business / AC</option></select></div></div><button type="submit" class="btn search-holidays" style="margin-left:12px;height:46px;align-self:flex-end">Search Routes <span>↗</span></button></form></section><section class="section" style="padding-top:28px"><div class="container"><div id="flightResults"><div class="detail-block" style="text-align:center;padding:48px 24px;background:#f8fbfe;border-radius:20px;border:1px dashed #d1e2f0"><div style="font-size:36px;margin-bottom:12px">✈️ 🚂 🚌</div><h3 style="font:800 20px Manrope;color:var(--navy);margin-bottom:8px">Ready to find your best connection?</h3><p style="color:var(--muted);max-width:520px;margin:0 auto 18px">Select your departure city, destination and travel date above to compare flights, express trains and sleeper coaches across India.</p></div></div></div></section>`;
  }

  function aboutPage() {
    return `${pageHero("THE PEOPLE BEHIND THE JOURNEY", "Travel should open up the world", "Voyara brings thoughtful planning, local perspective and helpful technology together — so you can spend less time coordinating and more time experiencing.", "photo-1530789253388-582c481c54b0")}<section class="section"><div class="container"><div class="detail-layout"><div><div class="eyebrow">OUR POINT OF VIEW</div><h2 style="font:800 32px Manrope;color:var(--navy)">A better trip isn’t just about where you go. It’s how it feels.</h2><p class="subtext" style="line-height:1.9">We believe the best journeys leave space for surprise while making the practical parts feel simple. Voyara is designed to connect curious travellers with meaningful places, trusted local experiences and trip plans that reflect their own pace and priorities.</p><p class="subtext" style="line-height:1.9">Our connected travel agents bring your preferences and the stored catalog together. The goal is not to travel faster or tick off more places. It’s to make each moment count.</p><a class="btn" href="#planner">Plan your next chapter ✦</a></div><img src="${photo("photo-1530789253388-582c481c54b0")}" alt="Travellers exploring a beautiful landscape" style="width:100%;height:360px;object-fit:cover;border-radius:22px"></div><div class="section-head" style="margin-top:55px"><div><div class="eyebrow">WHAT GUIDES US</div><h2>Thoughtful by nature</h2><p>Good travel is personal, responsible and full of possibility.</p></div></div><div class="about-values"><article class="value-card"><div class="icon">✦</div><h3>Personal, not one-size-fits-all</h3><p>Plans start with your interests, your budget and the way you want to feel while travelling.</p></article><article class="value-card"><div class="icon">⌖</div><h3>Local knowledge matters</h3><p>We celebrate local guides, regional food, independent stays and experiences with a sense of place.</p></article><article class="value-card"><div class="icon">♡</div><h3>Support you can count on</h3><p>Clear information and helpful support make it easier to travel with confidence.</p></article></div></div></section><section class="section" style="background:#edf5f8"><div class="container"><div class="feature-band"><div><div class="eyebrow">READY WHEN YOU ARE</div><h2>Let’s make room for a new story.</h2><p>Start with a destination, a feeling or a rough idea. We’ll help you shape the rest.</p><a class="btn" href="#destinations">Explore India →</a></div></div></div></section>`;
  }

  function contactPage() {
    return `${pageHero("WE’RE HERE TO HELP", "Let’s talk about your next trip", "Questions about a destination, a package or a booking? Send us a note and our travel support team will help you find the next step.", "photo-1526778548025-fa2f459cd5c1")}<section class="section"><div class="container"><div class="contact-layout"><div class="detail-block"><div class="eyebrow">CONTACT VOYARA</div><h2>Good journeys start with a conversation.</h2><p class="subtext">Tell us what you need. Your message is stored securely in the application.</p><div class="contact-item"><div class="icon">☎</div><div><strong>Travel support</strong><span>Use the enquiry form to share your request.</span></div></div><div class="contact-item"><div class="icon">✉</div><div><strong>Email updates</strong><span>Email delivery is not configured yet.</span></div></div><div class="contact-item"><div class="icon">⌖</div><div><strong>Based in India</strong><span>Helping curious travellers explore across India.</span></div></div><div class="detail-block" style="background:#f4f8fb;padding:17px;margin-top:25px"><b style="color:var(--navy)">Already travelling?</b><p style="margin-bottom:0">For urgent changes, use the support details in your booking confirmation.</p></div></div><form id="contactForm" class="form-card"><h2 style="font:800 24px Manrope;color:var(--navy);margin:0 0 20px">Send us a message</h2><div class="form-grid"><div class="field"><label>Your name</label><input name="name" required placeholder="How should we address you?"></div><div class="field"><label>Email address</label><input type="email" name="email" required placeholder="you@example.com"></div><div class="field"><label>What can we help with?</label><select name="topic"><option>Planning a new trip</option><option>Existing booking</option><option>Packages & pricing</option><option>Partnerships</option><option>Something else</option></select></div><div class="field"><label>Phone (optional)</label><input name="phone" type="tel" placeholder="+91"></div><div class="field full"><label>Your message</label><textarea name="message" required placeholder="Tell us a little about what you need…"></textarea></div></div><button class="btn" style="margin-top:18px" type="submit">Send message →</button><p style="font-size:10px;color:var(--muted)">Your enquiry will be saved. Email delivery is not configured yet.</p></form></div><div class="section-head" style="margin-top:55px"><div><div class="eyebrow">QUICK ANSWERS</div><h2>Frequently asked questions</h2></div></div><div class="faq"><details><summary>Can I customise a holiday package?</summary><p>Yes. Use the AI trip planner to share your interests, travel dates and budget. The sample packages are starting points that can be adjusted before submitting a booking request.</p></details><details><summary>Are the prices shown live?</summary><p>No. This website prototype uses illustrative starting prices. Your request is priced by the backend. Provider confirmation is still required.</p></details><details><summary>Can I save destinations and stays?</summary><p>Yes. Use the heart icon on a destination or stay card. Sign in with Google to save items to your account and see them on another device.</p></details><details><summary>Does the demo collect payments?</summary><p>No. The booking page saves a request to your account. It does not collect payment or confirm a provider reservation.</p></details></div></div></section>`;
  }

  function aiConcierge(route, param = "") {
    const context = {
      packages: [
        "Find a holiday that fits your budget",
        "Compare packages, trip lengths and inclusions.",
      ],
      destinations: [
        "Your India destination guide",
        "Tell us the kind of place you want to discover.",
      ],
      destination: [
        `Your ${param || "destination"} guide`,
        `Get local highlights, ideal trip length and nearby experiences.`,
      ],
      tours: [
        "Find your kind of experience",
        "From food walks and heritage trails to mountain adventures.",
      ],
      hotels: [
        "Find a stay that feels right",
        "Share your destination, style and nightly budget.",
      ],
      package: [
        "Let’s shape this holiday",
        "Ask about itinerary ideas, inclusions and practical tips.",
      ],
      planner: [
        "Your personal trip consultant",
        "Start with a place, a feeling or a budget — we’ll help shape it.",
      ],
      booking: [
        "A little help with your booking",
        "Ask about the steps, traveller details or what to prepare.",
      ],
      dashboard: [
        "Your travel companion",
        "Need ideas for your next trip or help organising a saved plan?",
      ],
      flights: [
        "Your travel route planning assistant",
        "Tell us your route, preferred mode (flight, train, bus) and dates.",
      ],
      travel: [
        "Your travel route planning assistant",
        "Tell us your route, preferred mode (flight, train, bus) and dates.",
      ],
      about: [
        "Curious about travelling with Voyara?",
        "Ask how our travel team helps you plan a more personal journey.",
      ],
      contact: [
        "How can our support team help?",
        "Get guidance on planning, packages or booking questions.",
      ],
      login: [
        "A smoother journey starts here",
        "Need help finding your saved trips or getting started?",
      ],
    };
    const c = context[route] || context.destinations;
    return `<section class="voyara-concierge-wrap" aria-label="Voyara AI travel team"><div class="container"><div class="voyara-concierge"><div class="concierge-intro"><div class="concierge-orbit"><span>✦</span></div><div><div class="concierge-kicker">MEET YOUR AI TRAVEL TEAM</div><h2>${c[0]}</h2><p>${c[1]}</p><div class="concierge-agents"><span><i class="agent-dot explore-dot">⌖</i> Explore Agent</span><span><i class="agent-dot plan-dot">✦</i> Trip Consultant</span><span><i class="agent-dot budget-dot">₹</i> Budget & Booking</span></div></div></div><div class="concierge-chat"><div class="concierge-message"><span class="concierge-avatar">✦</span><p id="conciergeReply">Namaste! Where would you love to go, and what would make the trip special?</p></div><div class="concierge-suggestions"><button type="button" data-prompt="Recommend destinations">Destination ideas</button><button type="button" data-prompt="Recommend stays">Stay ideas</button><button type="button" data-prompt="Plan my trip">Plan my trip</button></div><form class="concierge-input" id="conciergeForm"><input id="conciergePrompt" name="prompt" placeholder="Ask your travel team anything…" aria-label="Ask your travel team" required><button type="submit" aria-label="Send message">Send <span>↗</span></button></form><small class="concierge-note">A thoughtful travel starting point · Connected travel agents · Your confirmed trip memory</small></div></div></div></section>`;
  }

  return {
    toast,
    pageHero,
    sectionHead,
    destinationCard,
    packageCard,
    experienceCard,
    hotelCard,
    home,
    destinationsPage,
    packagesPage,
    toursPage,
    hotelsPage,
    destinationDetail,
    packageDetail,
    plannerPage,
    flightsPage,
    aboutPage,
    contactPage,
    aiConcierge,
    photo,
    money,
    setCatalog(c) {
      destinations = c.destinations;
      experiences = c.experiences;
      hotels = c.hotels;
    },
    setSaved(s) {
      saved = s;
    },
  };
}
