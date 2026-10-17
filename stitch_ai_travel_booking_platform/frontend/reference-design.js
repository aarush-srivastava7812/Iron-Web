// Layouts based on the user's homepage and destinations reference images.
const paths = {
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  pin: '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.3"/>',
  plane: '<path d="m22 3-7 18-3-8-9-3L22 3ZM12 13l10-10M3 18l3 3"/>',
  bed: '<path d="M3 20V7m18 13V10H3m0 6h18M7 10V6h5v4m0 0V6h6v4"/>',
  camera: '<path d="M3 7h5l2-3h4l2 3h5v14H3Z"/><circle cx="12" cy="13" r="4"/>',
  bag: '<rect x="4" y="7" width="16" height="14" rx="2"/><path d="M8 10V5a4 4 0 0 1 8 0v5M4 13h16"/>',
  food: '<path d="M5 3v7m3-7v7M2 3v7c0 3 6 3 6 0M5 13v8M18 3v18m0-18c-5 3-5 10 0 10"/>',
  wallet:
    '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 8h18m-7 4h7v5h-7Z"/>',
  support:
    '<path d="M4 14v-3a8 8 0 0 1 16 0v3m-2 4v2h-6"/><rect x="2" y="11" width="5" height="7" rx="2"/><rect x="17" y="11" width="5" height="7" rx="2"/>',
  person:
    '<circle cx="12" cy="7" r="4"/><path d="M4 22v-3a8 8 0 0 1 16 0v3Z"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-2 6-6 2 2-6Z"/>',
  calendar:
    '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 11h18m-13 4h2m4 0h2m-8 3h2"/>',
  sparkle:
    '<path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5ZM20 2v4m-2-2h4"/>',
  mountain: '<path d="m2 20 7-15 5 9 3-6 5 12ZM6 11l3 2 2-3"/>',
  arrow: '<path d="M3 12h17m-6-6 6 6-6 6"/>',
  shield:
    '<path d="m12 2 8 4v6c0 6-8 10-8 10S4 18 4 12V6Z"/><path d="m8 12 3 3 5-6"/>',
};
export function icon(name, cls = "") {
  return `<svg class="ui-icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.compass}</svg>`;
}
const image = (id, w = 1000) =>
  `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${w}&q=85`;
// Correct the prototype's unrelated stock photos with destination-specific imagery.
export function applyReferencePhotos(catalog) {
  const photos = {
    Kashmir: "photo-1595815771614-ade9d652a65d",
    Manali: "photo-1626621341517-bbf3d9990a23",
    Jaipur: "photo-1603262110263-fb0112e7cc33",
    Goa: "photo-1512343879784-a960bf40e7f2",
    Kerala: "photo-1602216056096-3b40cc0c9944",
    Udaipur: "photo-1709338573277-c161cbf8702c",
    Varanasi: "photo-1561359313-0639aad49ca6",
    Rishikesh: "photo-1603867106100-0d2039fc8757",
    Darjeeling: "photo-1671711847762-b8308b444a42",
    "Andaman Islands": "photo-1519046904884-53103b34b206",
    "Leh Ladakh": "photo-1609230469457-6e86fe39cd25",
    Hampi: "photo-1582510003544-4d00b7f74220",
  };
  catalog.destinations.forEach((d) => {
    if (photos[d.name]) d.img = photos[d.name];
  });
  return catalog;
}
const agents = [
  {
    name: "Trip Consultant",
    role: "Understands your needs & preferences",
    desc: "Tell us your ideas and we’ll plan a journey around you.",
    href: "#planner",
    color: "violet",
    icon: "person",
    photo: "photo-1494790108377-be9c29b29330",
  },
  {
    name: "Explore Agent",
    role: "Finds the best places in India for you",
    desc: "Find the best places, hidden gems and unique experiences.",
    href: "#destinations",
    color: "sky",
    icon: "compass",
    photo: "photo-1626621341517-bbf3d9990a23",
  },
  {
    name: "Stay Agent",
    role: "Finds ideal stays within your budget",
    desc: "Handpicked stays, from luxury to budget, for your style.",
    href: "#hotels",
    color: "sand",
    icon: "bed",
    photo: "photo-1611892440504-42a792e24d32",
  },
  {
    name: "Tour Guide Agent",
    role: "Creates itineraries & local activities",
    desc: "Discover local experiences and make each day your own.",
    href: "#tours",
    color: "peach",
    icon: "camera",
    photo: "photo-1603262110263-fb0112e7cc33",
  },
  {
    name: "Food Guide Agent",
    role: "Recommends local food & restaurants",
    desc: "Find regional flavours and food stops in your trip plan.",
    href: "#planner?agent=food",
    color: "rose",
    icon: "food",
    photo: "photo-1504674900247-0877df9cc836",
  },
  {
    name: "Budget & Booking Agent",
    role: "Keeps your trip within your budget",
    desc: "Compare indicative costs and review your booking requests.",
    href: "#packages",
    color: "mint",
    icon: "wallet",
  },
  {
    name: "Travel Support Agent",
    role: "Helps you prepare for your journey",
    desc: "Planning questions and trip enquiries, all in one place.",
    href: "#contact",
    color: "violet",
    icon: "support",
  },
];

export function createReferenceViews(escapeHTML) {
  const e = escapeHTML;
  function agentPanel(destination = false) {
    const list = destination
      ? [agents[1], agents[0], agents[5], agents[6]]
      : agents;
    return `<aside class="travel-team"><h2>${icon("sparkle")} Meet Your AI ${destination ? "Destination Guide" : "Travel Team"}</h2><div class="team-list">${list.map((a) => `<a href="${destination && a.name === "Explore Agent" ? "#planner?agent=explore" : a.href}" class="team-row"><span class="team-icon tone-${a.color}">${icon(a.icon)}</span><span><strong>${a.name}</strong><small>${a.role}</small></span><span class="team-chevron">›</span></a>`).join("")}</div><p>All working together for your perfect trip ${icon("sparkle")}</p></aside>`;
  }
  function compactPackage(d, favorites) {
    const saved = favorites.some(
      (f) => f.item_type === "package" && f.item_id === d.id,
    );
    return `<article class="holiday-tile"><div class="holiday-photo"><a href="#package/${encodeURIComponent(d.name)}" aria-label="View ${e(d.name)} package"><img src="${image(d.img, 500)}" alt="${e(d.name)}" loading="lazy"></a><span class="holiday-badge">${e(d.tag)}</span><button class="heart" onclick="toggleSave('package',${d.id})" aria-label="Save ${e(d.name)}" aria-pressed="${saved}">${saved ? "♥" : "♡"}</button></div><div class="holiday-body"><a href="#package/${encodeURIComponent(d.name)}"><h3>${e(d.name)}</h3></a><p class="holiday-rating"><span>★</span> ${e(d.rating)} <small>Catalog rating</small></p><p class="holiday-duration">${icon("calendar")} ${d.nights} Nights / ${d.nights + 1} Days</p><small class="holiday-from">From</small><div class="holiday-price">₹${Number(d.price).toLocaleString("en-IN")} <small>/ person</small></div></div></article>`;
  }
  function home(catalog, favorites) {
    return `<section class="reference-hero home-hero"><div class="hero-scene" style="background-image:url('${image("photo-1709338573277-c161cbf8702c", 1800)}')"></div><div class="container reference-hero-inner"><div class="reference-hero-copy"><h1>Your AI Travel<br>Companion. Powered by<br>Multi-Agent AI System.</h1><p>Discover India like never before. Personalised itineraries,<br class="desktop-break"> thoughtful ideas, and expert travel agents — all in one place.</p><a class="btn hero-cta" href="#planner">Plan My Trip with AI ${icon("sparkle")}</a><div class="hero-assurance"><span class="assurance-symbol">${icon("shield")}</span><span>Thoughtfully planned. Uniquely yours.<br><small>Your journey, with a little expert help.</small></span></div></div>${agentPanel()}</div></section><section class="container search-surface" aria-label="Find your holiday"><div class="travel-tabs" aria-label="Search travel"><button class="travel-tab active" aria-pressed="true" data-search-tab="holiday">${icon("bag")} Holidays</button><button class="travel-tab" aria-pressed="false" data-search-tab="flights">${icon("plane")} Flights</button><button class="travel-tab" aria-pressed="false" data-search-tab="hotels">${icon("bed")} Hotels</button><button class="travel-tab" aria-pressed="false" data-search-tab="tours">${icon("camera")} Tours</button><button class="travel-tab" aria-pressed="false" data-search-tab="packages">${icon("bag")} Packages</button></div><form id="quickSearch" class="reference-search"><div class="field search-destination"><label>Where do you want to go?</label><div class="search-value">${icon("pin")}<input name="destination" list="destinationList" placeholder="Search destinations in India" required><datalist id="destinationList">${catalog.destinations.map((d) => `<option>${e(d.name)}</option>`).join("")}</datalist></div></div><div class="field"><label>Departure from</label><div class="search-value">${icon("pin")}<select name="from">${["New Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Chennai"].map((n) => `<option>${n}</option>`).join("")}</select></div></div><div class="field"><label>Dates</label><div class="search-value">${icon("calendar")}<input name="date" type="date" aria-label="Travel date" min="${new Date().toLocaleDateString("en-CA")}"></div></div><div class="field"><label>Travellers</label><div class="search-value">${icon("person")}<select name="travellers"><option>2 Adults</option><option>1 Adult</option><option>2 Adults, 1 Child</option><option>4 adults</option><option>Group of 6+</option></select></div></div><button type="submit" class="btn search-holidays">Search Holidays ${icon("search")}</button></form><div class="popular-searches"><span>Popular searches:</span>${catalog.destinations.map((d) => `<a href="#destination/${encodeURIComponent(d.name)}">${e(d.name)}</a>`).join("")}</div></section><section class="container agent-section" id="agents"><div class="reference-section-heading"><h2>${icon("sparkle")} Explore by Our <span>AI Travel Agents</span></h2><a href="#planner">Meet the travel team ${icon("arrow")}</a></div><div class="agent-gallery">${agents.map((a) => `<article class="agent-tile"><a href="${a.href}" class="agent-portrait tone-${a.color}" tabindex="-1" aria-hidden="true">${a.photo ? `<img src="${image(a.photo, 280)}" alt="" loading="lazy">` : icon(a.icon)}<span class="agent-mini-icon">${icon(a.icon)}</span></a><h3>${a.name}</h3><p>${a.desc}</p><a class="agent-explore" href="${a.href}">Explore ${icon("arrow")}</a></article>`).join("")}</div></section><section class="container holidays-section"><div class="reference-section-heading"><h2>${icon("bag")} Popular Holiday Packages</h2><div class="holiday-heading-links"><span>India</span><a href="#packages">View All Packages ${icon("arrow")}</a></div></div><div class="holiday-grid">${catalog.destinations.map((d) => compactPackage(d, favorites)).join("")}</div><p class="catalog-footnote">Illustrative starting prices. Booking requests require provider confirmation.</p></section>`;
  }
  function destinationTile(d, i) {
    const colors = ["orange", "yellow", "coral", "teal", "yellow", "coral", "teal", "orange", "coral", "yellow", "orange", "teal"];
    const doodles = ["mountain", "compass", "plane"];
    const ci = typeof i === "number" ? i : 0;
    return `<article class="escape-tile escape-${colors[ci % colors.length]}" style="--escape-image:url('${image(d.img, 900)}')"><a href="#destination/${encodeURIComponent(d.name)}" aria-label="Explore ${e(d.name)}"><div class="escape-photo"></div><div class="escape-color"></div><div class="escape-tile-copy"><span class="paint-label">Explore</span><h3>${e(d.name)}</h3><p>${e(d.desc)}</p><span class="escape-doodle">${icon(doodles[ci % 3])}</span></div><span class="escape-arrow">${icon("arrow")}</span></a></article>`;
  }
  function destinations(catalog) {
    return `<section class="reference-hero destination-hero"><div class="hero-scene" style="background-image:url('${image(catalog.destinations[0].img, 1800)}')"></div><div class="orange-hero-paper"></div><div class="container reference-hero-inner"><div class="reference-hero-copy"><span class="paint-label">Explore</span><h1>Find Your Next<br>India Escape</h1><p>From snow-capped mountains to golden beaches,<br class="desktop-break"> explore India’s most breathtaking destinations<br class="desktop-break"> with the power of AI.</p><a class="btn hero-cta" href="#planner">Discover with AI ${icon("sparkle")}</a></div>${agentPanel(true)}</div></section><section class="container destination-search-surface"><form id="destinationSearch" class="destination-search"><div class="search-value">${icon("search")}<input name="q" type="search" placeholder="Search destinations in India" aria-label="Search destinations"></div><div class="search-value">${icon("pin")}<select name="region" aria-label="Region"><option value="All">All Regions</option>${["North India", "West India", "South India", "East India", "Islands"].map((x) => `<option>${x}</option>`).join("")}</select></div><div class="search-value">${icon("mountain")}<select name="experience" aria-label="Experience"><option value="All">Any Experience</option>${[...new Set(catalog.destinations.map((d) => d.tag))].map((x) => `<option>${e(x)}</option>`).join("")}</select></div><button class="btn" type="submit">${icon("search")} Search</button></form></section><section class="container destination-collection"><div class="reference-section-heading"><div><h2>${icon("sparkle")} Explore <span>India’s</span> Top Destinations</h2><p>From the Himalayas to the tropical coasts, discover the magic of India.</p></div><span class="handwritten-count" id="destinationCount">${catalog.destinations.length} Amazing Destinations</span></div><div class="escape-grid" id="destinationGrid">${catalog.destinations.map(destinationTile).join("")}</div><p class="catalog-footnote">Explore the stored travel catalog. Availability is subject to provider confirmation.</p></section>`;
  }
  return { home, destinations, destinationTile };
}
