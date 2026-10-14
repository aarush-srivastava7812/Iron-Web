import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowRight, ArrowUpRight, CalendarDays, Check, ChevronDown,
  Compass, Heart, Menu, MessageCircle, Plane, Search, ShieldCheck,
  ShoppingBag, Sparkles, UserRound, X,
} from "lucide-react";
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, catalog, emptyProfile, imageFor, money, type CatalogItem, type CatalogKind, type ImageCatalog, type Profile } from "./api";
import { CatalogCard, EmptyState, Image, Loader } from "./components";
import { useApp, type CartItem } from "./state";

type BookingItem = { item_type: string; item_id: number; quantity: number; unit_price_inr: number; start_date: string | null; end_date: string | null };
type Booking = { id: number; status: string; total_inr: number; created_at: string; items: BookingItem[] };
type Itinerary = { id: number; title: string; destination_id: number | null; start_date: string | null; end_date: string | null; notes: string; booking_ids: number[] };
type Conversation = { id: string; title: string; created_at: string };
type Message = { id: number; role: string; content: string; created_at: string };
type Memory = { id: number; category: string; value: Record<string, unknown> };

function useImages() {
  const [images, setImages] = useState<ImageCatalog>({ destinations: [], stays: [], food: [] });
  useEffect(() => { api<ImageCatalog>("/images.json").then(setImages).catch((reason: Error) => console.error("Unable to load the travel image catalog; using image fallbacks.", reason)); }, []);
  return images;
}

function Shell({ children }: { children: ReactNode }) {
  const { user, cart, signOut } = useApp();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => { window.scrollTo(0, 0); }, [location.pathname]);
  const navItems = [
    ["/destinations", "Explore"],
    ["/stays", "Stays"],
    ["/food", "Food"],
    ["/transport", "Transport"],
    ["/guides", "Guides"],
  ];
  return <div className="site-shell">
    <header className="site-header">
      <Link to="/" className="brand"><span className="brand-mark"><Compass size={18} /></span> voyara<span className="brand-period">.</span></Link>
      <nav className={`main-nav ${mobileOpen ? "main-nav-open" : ""}`}>
        {navItems.map(([to, label]) => <NavLink key={to} to={to} onClick={() => setMobileOpen(false)}>{label}</NavLink>)}
        <NavLink to="/assistant" onClick={() => setMobileOpen(false)} className="nav-assistant"><Sparkles size={14} /> AI guide</NavLink>
      </nav>
      <div className="header-actions">
        <Link to="/booking" className="icon-button cart-button" aria-label="Trip request"><ShoppingBag size={18} />{cart.length > 0 && <span className="cart-count">{cart.length}</span>}</Link>
        {user ? <>
          <Link to="/trips" className="header-link hide-small">My trips</Link>
          <Link to="/profile" className="avatar-link" title="Profile"><UserRound size={17} /></Link>
          <button className="button button-quiet hide-small" onClick={signOut}>Sign out</button>
        </> : <Link to="/login" className="button button-dark header-login">Sign in <ArrowUpRight size={15} /></Link>}
        <button className="icon-button menu-toggle" aria-label={mobileOpen ? "Close menu" : "Open menu"} onClick={() => setMobileOpen((open) => !open)}>{mobileOpen ? <X /> : <Menu />}</button>
      </div>
    </header>
    <main key={location.pathname} className="page-book-perspective page-route-transition">{children}</main>
    <footer className="site-footer">
      <div className="footer-brand"><Link to="/" className="brand"><span className="brand-mark"><Compass size={18} /></span> voyara<span className="brand-period">.</span></Link><p>Find a place that feels like yours.</p></div>
      <div className="footer-links"><Link to="/destinations">Explore</Link><Link to="/trips">My trips</Link><Link to="/assistant">AI guide</Link><Link to="/profile">Preferences</Link></div>
      <span className="footer-note">Thoughtfully planned. Yours to discover.</span>
    </footer>
  </div>;
}

function PageIntro({ eyebrow, title, detail }: { eyebrow: string; title: string; detail: string }) {
  return <div className="page-intro"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{detail}</p></div>;
}

function SectionHeading({ eyebrow, title, link, to }: { eyebrow: string; title: string; link?: string; to?: string }) {
  return <div className="section-heading"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div>{link && to && <Link to={to} className="inline-link">{link}<ArrowRight size={16} /></Link>}</div>;
}

const homeCategories: { kind: CatalogKind | "all"; icon: string; title: string; detail: string }[] = [
  { kind: "stays", icon: "🧭", title: "Holiday packages", detail: "Easy escapes" },
  { kind: "stays", icon: "🛏️", title: "Stays", detail: "Rest your way" },
  { kind: "food", icon: "☕", title: "Food & cafés", detail: "Local favourites" },
  { kind: "transport", icon: "🚆", title: "Getting there", detail: "Compare routes" },
  { kind: "guides", icon: "🥾", title: "Experiences", detail: "Do more, locally" },
  { kind: "guides", icon: "🗺️", title: "Local guides", detail: "Know the place" },
];

function HomePage() {
  const images = useImages();
  const [destinations, setDestinations] = useState<CatalogItem[]>([]);
  const [listings, setListings] = useState<(CatalogItem & { catalogKind: CatalogKind })[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<CatalogKind | "all">("all");
  const [budget, setBudget] = useState("any");
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      catalog("destinations", { limit: "100" }),
      catalog("stays", { limit: "100" }),
      catalog("food", { limit: "100" }),
      catalog("transport", { limit: "100" }),
      catalog("guides", { limit: "100" }),
    ]).then(([places, stays, food, transport, guides]) => {
      if (cancelled) return;
      setDestinations(places);
      setListings([
        ...stays.map((item) => ({ ...item, catalogKind: "stays" as const })),
        ...food.map((item) => ({ ...item, catalogKind: "food" as const })),
        ...transport.map((item) => ({ ...item, catalogKind: "transport" as const })),
        ...guides.map((item) => ({ ...item, catalogKind: "guides" as const })),
      ]);
    }).catch((reason: Error) => {
      if (!cancelled) setError(reason.message);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, []);
  const destination = destinations[0];
  const heroImage = destination ? imageFor(destination, destinations, images, "destinations") : images.destinations[0]?.image ?? "";
  const { addToCart } = useApp();
  const matchingListings = listings.filter((item) => {
    const destinationName = destinations.find((place) => place.id === item.destination_id)?.name ?? "";
    const searchable = [item.name, item.description, destinationName, item.operator, item.mode, item.cuisine]
      .filter(Boolean).join(" ").toLowerCase();
    const matchesSearch = searchable.includes(search.trim().toLowerCase());
    const matchesKind = kind === "all" || kind === item.catalogKind;
    const price = item.price_inr ?? 0;
    const matchesBudget = budget === "any" || (budget === "premium" ? price >= 15000 : price <= Number(budget));
    return matchesSearch && matchesKind && matchesBudget;
  });
  const visibleListings = showAll ? matchingListings : matchingListings.slice(0, 6);
  const showListings = (nextKind: CatalogKind | "all" = "all") => {
    setKind(nextKind);
    setShowAll(true);
    document.getElementById("stitch-listings")?.scrollIntoView({ behavior: "smooth" });
  };
  return <div className="stitch-home">
    <section className="stitch-hero">
      <div className="stitch-hero-copy"><span className="eyebrow eyebrow-light">A little farther, a little freer</span>
        <h1>Find your<br /><em>somewhere.</em></h1>
        <p>Thoughtfully planned journeys, local discoveries, and all the little details that make a trip feel like yours.</p>
        <div className="hero-actions"><Link to="/destinations" className="button button-lime">Explore destinations <ArrowUpRight size={16} /></Link><Link to="/itineraries" className="button button-glass">Build my itinerary</Link></div>
        <div className="hero-proof"><strong>One place for the whole journey.</strong><span> From the first idea to the way back home.</span></div>
      </div>
      <div className="stitch-hero-art">
        {heroImage && <Image src={heroImage} alt="" className="stitch-hero-photo" />}
        <div className="stitch-orbit" aria-hidden="true" /><span className="stitch-orbit-label" aria-hidden="true"><Plane size={44} /></span>
        <div className="stitch-floating stitch-float-one"><small><i /> YOUR NEXT ESCAPE</small><strong>{destination?.name ?? "Mountains calling"}</strong></div>
        <div className="stitch-floating stitch-float-two"><small>TRIP STYLE</small><strong>Slow travel · Local finds</strong></div>
      </div>
    </section>
    <form className="stitch-search" onSubmit={(event) => { event.preventDefault(); showListings(kind); }}>
      <label><span>Where to?</span><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Destination, city or experience" /></label>
      <label><span>I'm looking for</span><select value={kind} onChange={(event) => setKind(event.target.value as CatalogKind | "all")}><option value="all">Anything inspiring</option><option value="stays">Hotels &amp; stays</option><option value="food">Food &amp; cafés</option><option value="guides">Activities &amp; guides</option><option value="transport">Transport</option></select></label>
      <label><span>Budget per person</span><select value={budget} onChange={(event) => setBudget(event.target.value)}><option value="any">Any budget</option><option value="5000">Under ₹5,000</option><option value="15000">Under ₹15,000</option><option value="30000">Under ₹30,000</option><option value="premium">Premium</option></select></label>
      <button className="button button-dark" type="submit">Search trips <ArrowUpRight size={16} /></button>
    </form>
    <div className="stitch-trust"><span><ShieldCheck size={17} /> Request first, confirm when ready</span><span><Heart size={17} /> Made for your kind of travel</span><span><Sparkles size={17} /> Your preferences, remembered</span></div>
    <section className="stitch-section" id="destinations">
      <div className="stitch-section-heading"><div><span className="eyebrow">Made for your kind of curious</span><h2>Where will you go next?</h2><p>Big-name favourites and places worth taking the longer road for.</p></div><Link className="inline-link" to="/destinations">Explore all destinations <ArrowRight size={16} /></Link></div>
      {loading ? <Loader label="Finding your somewhere…" variant="passport" /> : error ? <EmptyState title="Destinations are taking the scenic route" detail={error} /> : <div className="stitch-destinations">
        {destinations.slice(0, 5).map((item, index) => <Link className={`stitch-destination stitch-destination-${index}`} key={item.id} to={`/destinations/${item.id}`}>
          <Image src={imageFor(item, destinations, images, "destinations")} alt={`${item.name ?? "Destination"} landscape`} />
          <span className="stitch-destination-arrow"><ArrowUpRight size={17} /></span><div><span>{item.tags?.slice(0, 2).join(" · ") || item.state}</span><h3>{item.name}</h3><p>{[item.state, item.country].filter(Boolean).join(", ")}</p></div>
        </Link>)}
      </div>}
    </section>
    <section className="stitch-section stitch-experiences" id="experiences">
      <div className="stitch-section-heading"><div><span className="eyebrow">Travel, your way</span><h2>What are you in the mood for?</h2><p>Build a trip around the things you love doing.</p></div></div>
      <div className="stitch-categories">
        {homeCategories.map(({ kind: nextKind, icon, title, detail }) => <button className="stitch-category" key={title} onClick={() => showListings(nextKind)}><span>{icon}</span><strong>{title}</strong><small>{detail}</small></button>)}
      </div>
    </section>
    <section className="stitch-section" id="stitch-listings">
      <div className="stitch-section-heading"><div><span className="eyebrow">From the Voyara catalog</span><h2>Places to stay and explore.</h2><p>Curated sample listings and prices; availability is not live.</p></div><button className="inline-link stitch-text-button" onClick={() => showListings("all")}>View all listings <ArrowRight size={16} /></button></div>
      {loading ? <Loader label="Loading recommendations…" variant="suitcase" /> : error ? <EmptyState title="Listings are taking the scenic route" detail={error} /> : visibleListings.length ? <div className="catalog-grid">{visibleListings.map((item) => <CatalogCard key={`${item.catalogKind}-${item.id}`} item={item} kind={item.catalogKind} destinations={destinations} imageCatalog={images} onAdd={() => addToCart({ item_type: item.catalogKind === "stays" ? "stay" : item.catalogKind === "transport" ? "transport" : item.catalogKind === "guides" ? "guide" : "food", item_id: item.id, name: item.name ?? item.operator ?? "Travel experience", price: item.price_inr ?? 0 })} />)}</div> : <EmptyState title="No matching listings found" detail="Try a broader destination, category or budget." />}
      {!showAll && matchingListings.length > visibleListings.length && <button className="button button-outline stitch-more" onClick={() => setShowAll(true)}>Show all {matchingListings.length} listings <ArrowRight size={15} /></button>}
    </section>
    <section className="stitch-planner" id="planner">
      <div><span className="eyebrow">Your trip, pieced together</span><h2>Less tab-hopping.<br />More looking forward.</h2><p>Bring stays, transport, food stops and things to do into one editable itinerary. Start with a destination, then shape the days around your time and budget.</p><Link className="button button-dark" to="/itineraries">Start planning <ArrowUpRight size={16} /></Link></div>
      <div className="stitch-plan-card"><div><strong>A weekend in the hills</strong><span>SAMPLE ITINERARY</span></div><article><span>🚆</span><p><strong>Morning train to the mountains</strong><small>Day 1 · Transport idea</small></p></article><article><span>🏡</span><p><strong>Check in at a local homestay</strong><small>Day 1 · Stay idea</small></p></article><article><span>🥘</span><p><strong>Find a local lunch spot</strong><small>Day 2 · Food idea</small></p></article><small>Sample only · Create a private itinerary to make it yours</small></div>
    </section>
    <section className="stitch-closing"><span className="eyebrow eyebrow-light">THE WORLD IS STILL WONDERFUL</span><h2>Ready for a little<br /><em>somewhere?</em></h2><Link to="/destinations" className="button button-lime">Let's find it <ArrowUpRight size={16} /></Link><Plane className="stitch-closing-plane" size={100} strokeWidth={0.75} /></section>
  </div>;
}
function DestinationTile({ item, destinations, images, index }: { item: CatalogItem; destinations: CatalogItem[]; images: ImageCatalog; index: number }) {
  const src = imageFor(item, destinations, images, "destinations");
  return <Link to={`/destinations/${item.id}`} className={`destination-tile tile-${index}`}>
    <Image src={src} alt={item.name ?? "Destination"} />
    <div className="tile-shade" /><span className="tile-index">0{index + 1}</span>
    <div className="tile-copy"><span>{item.tags?.[0] ?? item.state ?? "Somewhere to explore"}</span><h3>{item.name}</h3><p>{item.state}, {item.country}</p></div><span className="tile-arrow"><ArrowUpRight size={18} /></span>
  </Link>;
}

const catalogInfo: Record<Exclude<CatalogKind, "destinations">, { eyebrow: string; title: string; detail: string; placeholder: string }> = {
  stays: { eyebrow: "A place to land", title: "Stay a little longer.", detail: "From a tucked-away homestay to a slow-morning resort, find a stay that fits your kind of trip.", placeholder: "Search stays, towns or amenities" },
  food: { eyebrow: "Follow your appetite", title: "Taste the somewhere.", detail: "Local kitchens, market snacks and cozy tables worth building a day around.", placeholder: "Search cuisine, cafes or places" },
  transport: { eyebrow: "The way there matters", title: "Take the scenic route.", detail: "Compare sample routes and travel styles. Availability and prices are illustrative.", placeholder: "Search routes or operators" },
  guides: { eyebrow: "Meet someone local", title: "Go beyond the guidebook.", detail: "Find local storytellers and small-group experiences led by people who call this place home.", placeholder: "Search languages or experiences" },
};

function BrowsePage({ kind }: { kind: CatalogKind }) {
  const info = catalogInfo[kind as Exclude<CatalogKind, "destinations">] ?? { eyebrow: "Go somewhere new", title: "Find your somewhere.", detail: "Places, people and plans for your next journey.", placeholder: "Search a place or a feeling" };
  const images = useImages();
  const [destinations, setDestinations] = useState<CatalogItem[]>([]);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [search, setSearch] = useState("");
  const [price, setPrice] = useState("");
  const [category, setCategory] = useState("");
  const [diet, setDiet] = useState("");
  const [amenity, setAmenity] = useState("");
  const [routeDestination, setRouteDestination] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { addToCart } = useApp();
  function changeFilter(change: () => void) {
    change();
  }
  useEffect(() => { catalog("destinations").then(setDestinations).catch((reason: Error) => setError(reason.message)); }, []);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError("");
    const params: Record<string, string> = { q: search, max_price: price };
    if (category) params[kind === "destinations" ? "tag" : kind === "guides" ? "specialty" : "type"] = category;
    if (kind === "food" && diet) params.diet = diet;
    if (kind === "stays" && amenity) params.amenity = amenity;
    if (kind === "transport" && routeDestination) params.destination_id = routeDestination;
    catalog(kind, params).then((result) => { if (!cancelled) setItems(result); })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [kind, search, price, category, diet, amenity, routeDestination]);
  const filters = kind === "destinations" ? ["All places", "Beach", "Nature", "Culture"] :
    kind === "stays" ? ["All stays", "hotel", "hostel", "homestay", "resort"] :
    kind === "food" ? ["All food", "restaurant", "cafe", "street_stall"] :
    kind === "transport" ? ["All routes", "flight", "train", "bus", "ferry"] : ["All guides", "history", "food walks", "adventure"];
  const onAdd = (item: CatalogItem) => addToCart({
    item_type: kind === "stays" ? "stay" : kind === "transport" ? "transport" : kind === "guides" ? "guide" : "food",
    item_id: item.id, name: item.name ?? item.operator ?? "Travel experience", price: item.price_inr ?? 0,
  });
  const title = kind === "destinations" ? "Find your somewhere." : info.title;
  return <div className="browse-page">
    <PageIntro eyebrow={info.eyebrow} title={title} detail={info.detail} />
    <div className="browse-toolbar">
      <label className="search-field"><Search size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={info.placeholder} /></label>
      <label className="select-field"><span>{kind === "food" ? "Diet" : "Category"}</span><select value={kind === "food" ? diet : category} onChange={(event) => changeFilter(() => kind === "food" ? setDiet(event.target.value) : setCategory(event.target.value))}>
        {(kind === "food" ? ["", "veg", "non_veg", "both"] : ["", ...filters.slice(1)]).map((value) => <option key={value || "all"} value={value}>{value ? value.replaceAll("_", " ") : filters[0]}</option>)}
      </select><ChevronDown size={15} /></label>
      {kind === "stays" && <label className="select-field"><span>Amenity</span><select value={amenity} onChange={(event) => changeFilter(() => setAmenity(event.target.value))}><option value="">Any amenity</option><option value="wifi">Wi-Fi</option><option value="breakfast">Breakfast</option><option value="home-food">Home food</option></select><ChevronDown size={15} /></label>}
      {kind === "transport" && <label className="select-field"><span>Arrive in</span><select value={routeDestination} onChange={(event) => changeFilter(() => setRouteDestination(event.target.value))}><option value="">Any destination</option>{destinations.map((place) => <option key={place.id} value={place.id}>{place.name}</option>)}</select><ChevronDown size={15} /></label>}
      {kind !== "destinations" && <label className="select-field price-select"><span>Price ceiling</span><select value={price} onChange={(event) => changeFilter(() => setPrice(event.target.value))}><option value="">Any price</option><option value="1000">Under ₹1,000</option><option value="3000">Under ₹3,000</option><option value="7000">Under ₹7,000</option></select><ChevronDown size={15} /></label>}
      <span className="results-count">{loading ? " " : `${items.length} ${items.length === 1 ? "place" : "places"}`}</span>
    </div>
    {loading ? <Loader label="Searching the map…" variant="globe" /> : error ? <EmptyState title="We couldn't load this collection" detail={error} /> : items.length === 0 ? <EmptyState title="No matches just yet" detail="Try a wider search or clear a filter to see more." /> :
      kind === "destinations" ? <div className="destination-grid browse-destinations">{items.map((item, index) => <DestinationTile key={item.id} item={item} destinations={items} images={images} index={index % 4} />)}</div> :
      <div className="catalog-grid">{items.map((item) => <CatalogCard key={item.id} item={item} kind={kind} destinations={destinations} imageCatalog={images} onAdd={() => onAdd(item)} />)}</div>}
    <div className="browse-footnote"><ShieldCheck size={16} /> Listings and prices are curated examples. Requests are not confirmed until a provider accepts them.</div>
  </div>;
}

function DestinationPage() {
  const { id } = useParams();
  const images = useImages();
  const [destination, setDestination] = useState<CatalogItem | null>(null);
  const [items, setItems] = useState<Record<string, CatalogItem[]>>({ stays: [], food: [], transport: [], guides: [] });
  const [loading, setLoading] = useState(true);
  const { addToCart } = useApp();
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    Promise.all([api<CatalogItem>(`/destinations/${id}`), ...(["stays", "food", "transport", "guides"] as const).map((kind) => catalog(kind, { destination_id: id }))])
      .then(([place, stays, food, transport, guides]) => {
        if (cancelled) return;
        setDestination(place); setItems({ stays, food, transport, guides });
      }).catch(() => { if (!cancelled) setDestination(null); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);
  if (loading) return <div className="page-container"><Loader variant="carousel" /></div>;
  if (!destination) return <div className="page-container"><EmptyState title="Place not found" detail="Try another destination from the explore page." action={<Link to="/destinations" className="button button-dark">Explore places</Link>} /></div>;
  const photo = imageFor(destination, [destination], images, "destinations");
  return <div className="destination-detail">
    <section className="detail-hero"><Image src={photo} alt={destination.name ?? "Destination"} /><div className="detail-hero-shade" /><div className="detail-hero-content"><span className="eyebrow eyebrow-light">{destination.state}, {destination.country}</span><h1>{destination.name}</h1><p>{destination.description}</p><div className="detail-tags">{destination.tags?.map((tag) => <span key={tag}>{tag}</span>)}</div></div></section>
    <div className="destination-meta"><span><CalendarDays size={17} /> Best season: {destination.best_season ?? "Anytime"}</span><span><Compass size={17} /> {destination.climate ?? "Come as you are"}</span><span><Heart size={17} /> {money(destination.avg_cost_inr)} average trip</span></div>
    {(["stays", "food", "transport", "guides"] as const).map((kind) => <section className="content-section detail-section" key={kind}><SectionHeading eyebrow={`Around ${destination.name}`} title={{ stays: "Places to stay", food: "Good things to eat", transport: "Ways to get there", guides: "People who know the place" }[kind]} link={`Explore ${kind}`} to={`/${kind}`} />{items[kind].length ? <div className="catalog-grid detail-list">{items[kind].slice(0, 3).map((item) => <CatalogCard key={item.id} item={item} kind={kind} destinations={[destination]} imageCatalog={images} onAdd={() => addToCart({ item_type: kind === "stays" ? "stay" : kind === "transport" ? "transport" : kind === "guides" ? "guide" : "food", item_id: item.id, name: item.name ?? "Local experience", price: item.price_inr ?? 0 })} />)}</div> : <p className="inline-empty">New local recommendations are on the way.</p>}</section>)}
  </div>;
}

function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const { user, signIn, register } = useApp();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const fields = new FormData(event.currentTarget);
    try {
      if (mode === "login") await signIn(String(fields.get("identifier")), String(fields.get("password")));
      else await register(String(fields.get("email")), String(fields.get("username")), String(fields.get("password")));
      navigate("/trips");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to sign in."); }
    finally { setBusy(false); }
  }
  if (user) return <Navigate to="/trips" replace />;
  return <div className="auth-layout"><div className="auth-photo" style={{ backgroundImage: `linear-gradient(180deg,rgba(13,44,38,.05),rgba(13,44,38,.72)),url('${"https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1400&q=85"}')` }}><span className="eyebrow eyebrow-light">THE WORLD, AT YOUR PACE</span><h2>Somewhere is<br /><em>waiting for you.</em></h2><p>Your trips, your tastes, your little corner of the map.</p></div>
    <div className="auth-panel"><Link to="/" className="brand auth-brand"><span className="brand-mark"><Compass size={18} /></span> voyara<span className="brand-period">.</span></Link><span className="eyebrow">{mode === "login" ? "WELCOME BACK" : "A GOOD PLACE TO BEGIN"}</span><h1>{mode === "login" ? "Pick up where you left off." : "Let's make this yours."}</h1><p className="muted">{mode === "login" ? "Sign in to see the trips and preferences you've saved." : "Create an account to save places, preferences and plans."}</p>
      <form className="form-stack" onSubmit={submit}>{mode === "signup" && <><label>Email<input name="email" type="email" autoComplete="email" placeholder="you@example.com" required /></label><label>Username<input name="username" autoComplete="username" minLength={3} maxLength={40} placeholder="yourname" required /></label></>}
        {mode === "login" && <label>Email or username<input name="identifier" autoComplete="username" placeholder="you@example.com" required /></label>}
        <label>Password<input name="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} placeholder="At least 8 characters" required /></label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button button-dark button-full" disabled={busy}>{busy ? "Just a moment…" : mode === "login" ? "Sign in" : "Create account"}<ArrowRight size={16} /></button></form>
      <p className="auth-switch">{mode === "login" ? "New around here?" : "Already have an account?"} <Link to={mode === "login" ? "/signup" : "/login"}>{mode === "login" ? "Create account" : "Sign in"}</Link></p>
      <p className="auth-assurance"><ShieldCheck size={15} /> Your personal preferences and trips stay private to your account.</p></div>
  </div>;
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, authLoading } = useApp();
  if (authLoading) return <div className="page-container"><Loader /></div>;
  return user ? children : <Navigate to="/login" replace />;
}

function DashboardPage() {
  const { user } = useApp();
  const images = useImages();
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [destinations, setDestinations] = useState<CatalogItem[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<Profile>("/profile"), catalog("destinations", { limit: "4" }), api<Booking[]>("/bookings")])
      .then(([preferences, places, trips]) => { setProfile(preferences); setDestinations(places); setBookings(trips); })
      .catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  }, []);
  if (loading) return <div className="page-container"><Loader /></div>;
  const name = user?.full_name?.split(" ")[0] || user?.username || "traveler";
  const favorites = destinations.filter((place) => profile.favorite_destinations.includes(place.slug ?? "") || profile.favorite_destinations.includes(place.name ?? ""));
  const suggestions = favorites.length ? favorites : destinations.slice(0, 3);
  return <div className="dashboard page-container">
    <div className="dashboard-welcome"><div><span className="eyebrow">YOUR TRAVEL DESK</span><h1>Good to see you, {name}.</h1><p>Your next somewhere is a few good choices away.</p></div><Link to="/assistant" className="button button-dark"><Sparkles size={15} /> Ask your AI guide</Link></div>
    {error && <p className="form-error">{error}</p>}
    <div className="dashboard-stats"><Stat icon={<ShoppingBag />} label="Trip requests" value={String(bookings.filter((booking) => booking.status === "requested").length)} /><Stat icon={<Heart />} label="Favorite places" value={String(profile.favorite_destinations.length)} /><Stat icon={<Compass />} label="Your travel style" value={profile.travel_style || "Still discovering"} /></div>
    <div className="dashboard-columns"><section className="dashboard-main"><SectionHeading eyebrow="Picked with you in mind" title="A few places to start" link="See all places" to="/destinations" /><div className="catalog-grid">{suggestions.map((item) => <CatalogCard key={item.id} item={item} kind="destinations" destinations={destinations} imageCatalog={images} />)}</div>
      <section className="dashboard-bookings"><SectionHeading eyebrow="The next chapter" title="Recent trip requests" link="All my trips" to="/trips" />{bookings.slice(0, 2).length ? bookings.slice(0, 2).map((booking) => <BookingRow key={booking.id} booking={booking} />) : <EmptyState title="Nothing booked just yet" detail="A lovely trip starts with one small idea." action={<Link className="button button-outline" to="/destinations">Find a place</Link>} />}</section></section>
      <aside className="preference-card"><span className="preference-icon"><Sparkles size={19} /></span><span className="eyebrow">YOUR TRAVEL DNA</span><h3>A few things we know</h3><p>Keep your preferences current and your recommendations get a little more you.</p><div className="preference-list"><Preference label="Budget" value={profile.budget_range} /><Preference label="Travel style" value={profile.travel_style} /><Preference label="Food" value={profile.dietary_restrictions.join(", ") || profile.food_preferences.join(", ")} /><Preference label="Getting around" value={profile.preferred_transport.join(", ")} /></div><Link to="/profile" className="inline-link">Edit your preferences <ArrowRight size={16} /></Link></aside></div>
  </div>;
}

function Stat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="stat-card"><span>{icon}</span><div><small>{label}</small><strong>{value}</strong></div></div>;
}

function Preference({ label, value }: { label: string; value?: string | null }) {
  return <div className="preference-row"><span>{label}</span><strong>{value || "Not set yet"}</strong></div>;
}

function BookingRow({ booking }: { booking: Booking }) {
  return <article className="booking-row"><div className="booking-row-icon"><CalendarDays size={18} /></div><div className="booking-row-copy"><strong>Trip request #{booking.id}</strong><span>{booking.items.length} item{booking.items.length === 1 ? "" : "s"} · {new Date(booking.created_at).toLocaleDateString()}</span></div><span className={`status-pill status-${booking.status}`}>{booking.status}</span><strong>{money(booking.total_inr)}</strong></article>;
}

function daysBetween(start: string, end: string) {
  const toUtcDay = (value: string) => {
    const [year, month, day] = value.split("-").map(Number);
    return Date.UTC(year, month - 1, day) / 86_400_000;
  };
  return toUtcDay(end) - toUtcDay(start);
}

function addCalendarDays(value: string, days: number) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10);
}

function BookingPage() {
  const { user, cart, removeFromCart, clearCart } = useApp();
  const navigate = useNavigate();
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const stayInCart = cart.some((item) => item.item_type === "stay");
  const guideInCart = cart.some((item) => item.item_type === "guide");
  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    if (!user) { navigate("/login"); return; }
    setBusy(true);
    try {
      const items = cart.map((item) => ({
        item_type: item.item_type, item_id: item.item_id, quantity: 1,
        ...(item.item_type === "stay" || item.item_type === "guide" ? { start_date: startDate, end_date: endDate } : {}),
      }));
      await api<Booking>("/bookings", { method: "POST", body: JSON.stringify({ items }) });
      clearCart(); navigate("/trips");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to send your request."); }
    finally { setBusy(false); }
  }
  const stayNights = startDate && endDate ? Math.max(1, daysBetween(startDate, endDate)) : 1;
  const guideDays = startDate && endDate ? Math.max(1, daysBetween(startDate, endDate) + 1) : 1;
  const itemEstimate = (item: CartItem) => item.price * (item.item_type === "stay" ? stayNights : item.item_type === "guide" ? guideDays : 1);
  const subtotal = cart.reduce((sum, item) => sum + itemEstimate(item), 0);
  return <div className="page-container booking-page"><PageIntro eyebrow="A good plan, taking shape" title="Review your trip." detail="Take a look before you send a request. Nothing is booked or charged until a provider confirms." />
    {!cart.length ? <EmptyState title="Your trip list is taking a little break" detail="Add a stay, a meal, a route or a local guide and they will be waiting here." action={<Link className="button button-dark" to="/destinations">Explore destinations</Link>} /> :
      <form className="checkout-layout" onSubmit={submit}><div className="checkout-list"><div className="checkout-list-head"><span>{cart.length} trip {cart.length === 1 ? "idea" : "ideas"}</span><Link to="/destinations">Keep exploring <ArrowRight size={15} /></Link></div>
        {cart.map((item, index) => <article className="checkout-item" key={`${item.item_type}-${item.item_id}-${index}`}><span className="checkout-item-icon">{item.item_type === "transport" ? <Plane /> : item.item_type === "guide" ? <Compass /> : item.item_type === "food" ? <Heart /> : <ShoppingBag />}</span><div><small>{item.item_type}</small><strong>{item.name}</strong></div><strong>{money(itemEstimate(item))}</strong><button type="button" className="remove-button" aria-label={`Remove ${item.name}`} onClick={() => removeFromCart(index)}><X size={16} /></button></article>)}
        {(stayInCart || guideInCart) && <div className="date-fields"><label>Start date<input type="date" required value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label>End date<input type="date" required min={startDate ? addCalendarDays(startDate, stayInCart ? 1 : 0) : undefined} value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label></div>}
      </div><aside className="checkout-summary"><span className="eyebrow">YOUR REQUEST</span><h2>One thoughtful trip.</h2><div className="summary-line"><span>{cart.length} items</span><strong>{money(subtotal)}</strong></div><div className="summary-line summary-total"><span>Estimated total</span><strong>{money(subtotal)}</strong></div><p>Stays and guides are estimates per night/day. A provider confirms final pricing and availability.</p>{error && <p className="form-error">{error}</p>}<button className="button button-dark button-full" disabled={busy}>{busy ? <>Sending request… <span className="request-plane"><Plane size={15} /></span></> : <>Send booking request <ArrowRight size={16} /></>}</button><span className="safe-note"><ShieldCheck size={15} /> No payment is collected</span></aside></form>}
  </div>;
}

function TripsPage() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [itineraries, setItineraries] = useState<Itinerary[]>([]);
  const [destinations, setDestinations] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [title, setTitle] = useState("");
  const [destinationId, setDestinationId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [notes, setNotes] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const refresh = () => Promise.all([api<Booking[]>("/bookings"), api<Itinerary[]>("/itineraries"), catalog("destinations")]).then(([bookingsData, itineraryData, placeData]) => { setBookings(bookingsData); setItineraries(itineraryData); setDestinations(placeData); });
  useEffect(() => { refresh().catch((reason) => setError(reason.message)).finally(() => setLoading(false)); }, []);
  async function cancel(id: number) {
    try { await api(`/bookings/${id}/cancel`, { method: "POST" }); await refresh(); setNotice("Your request was cancelled."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to cancel this request."); }
  }
  async function savePlan(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const body = JSON.stringify({ title, destination_id: destinationId ? Number(destinationId) : null, start_date: startDate || null, end_date: endDate || null, booking_ids: bookings.map((booking) => booking.id), notes });
      await api(editing ? `/itineraries/${editing}` : "/itineraries", { method: editing ? "PATCH" : "POST", body });
      setTitle(""); setDestinationId(""); setStartDate(""); setEndDate(""); setNotes(""); setEditing(null);
      await refresh(); setNotice(editing ? "Your itinerary is updated." : "Your trip plan is saved.");
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save your plan."); }
    finally { setSaving(false); }
  }
  async function deleteItinerary(id: number) {
    try { await api(`/itineraries/${id}`, { method: "DELETE" }); if (editing === id) setEditing(null); await refresh(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to delete this itinerary."); }
  }
  if (loading) return <div className="page-container"><Loader /></div>;
  return <div className="page-container trips-page"><PageIntro eyebrow="All in one place" title="Your trips, your way." detail="Keep your ideas, booking requests and saved itineraries together." />
    {notice && <div className="inline-success"><Check size={17} />{notice}<button onClick={() => setNotice("")}><X size={15} /></button></div>}
    {error && <p className="form-error">{error}</p>}
    <div className="trips-columns"><section><SectionHeading eyebrow="Provider confirmation pending" title="Booking requests" />{bookings.length ? <div className="trip-stack">{bookings.map((booking) => <article className="trip-card" key={booking.id}><div className="trip-card-head"><div><span className="eyebrow">REQUEST #{booking.id}</span><h3>{booking.items.length} part{booking.items.length === 1 ? "" : "s"} to your trip</h3></div><span className={`status-pill status-${booking.status}`}>{booking.status}</span></div><div className="trip-items">{booking.items.map((item, index) => <span key={index}>{item.item_type} × {item.quantity}</span>)}</div><div className="trip-card-foot"><span>{new Date(booking.created_at).toLocaleDateString()}</span><strong>{money(booking.total_inr)}</strong>{booking.status !== "cancelled" && <button className="button button-outline button-small" onClick={() => cancel(booking.id)}>Cancel request</button>}</div></article>)}</div> : <EmptyState title="No trip requests yet" detail="Add your favorite finds to a trip and send a request when you are ready." action={<Link to="/destinations" className="button button-outline">Explore</Link>} />}</section>
      <aside className="itinerary-panel"><SectionHeading eyebrow="Saved plans" title="Itinerary notebook" />{itineraries.length ? itineraries.map((plan) => <article className="saved-itinerary" key={plan.id}><span className="itinerary-stamp"><Compass size={18} /></span><div><strong>{plan.title}</strong><small>{destinations.find((place) => place.id === plan.destination_id)?.name ?? "Destination to be decided"}{plan.start_date ? ` · ${plan.start_date}` : ""}{plan.booking_ids.length ? ` · ${plan.booking_ids.length} request(s)` : ""}</small></div><button aria-label={`Edit ${plan.title}`} onClick={() => { setEditing(plan.id); setTitle(plan.title); setDestinationId(plan.destination_id ? String(plan.destination_id) : ""); setStartDate(plan.start_date ?? ""); setEndDate(plan.end_date ?? ""); setNotes(plan.notes); }}><ArrowUpRight size={15} /></button><button aria-label={`Delete ${plan.title}`} onClick={() => deleteItinerary(plan.id)}><X size={16} /></button></article>) : <p className="muted small-copy">Keep an idea here until you are ready to make it a trip.</p>}
        <form className="save-itinerary-form" onSubmit={savePlan}><strong>{editing ? "Edit this itinerary" : "Save a new itinerary"}</strong><label>Trip name<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. A slow week in Kerala" required /></label><label>Destination<select value={destinationId} onChange={(event) => setDestinationId(event.target.value)}><option value="">Choose a place</option>{destinations.map((place) => <option key={place.id} value={place.id}>{place.name}</option>)}</select></label><div className="date-fields"><label>From<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label>Until<input type="date" min={startDate} value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label></div><label>Notes<textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Leave time for the local market…" rows={3} /></label><button className="button button-dark button-full" disabled={saving}>{saving ? "Saving…" : editing ? "Update itinerary" : "Save trip plan"}<ArrowRight size={15} /></button>{editing && <button type="button" className="button button-quiet button-full" onClick={() => { setEditing(null); setTitle(""); setDestinationId(""); setStartDate(""); setEndDate(""); setNotes(""); }}>Cancel editing</button>}</form></aside></div>
  </div>;
}

const preferenceChoices: Record<keyof Profile, string[]> = {
  budget_range: ["", "Under ₹5,000", "₹5,000–₹15,000", "₹15,000–₹30,000", "Premium"],
  travel_style: ["", "Slow travel", "Adventure", "Food & culture", "Relaxation", "Family-friendly", "Solo explorer"],
  food_preferences: ["Vegetarian", "Vegan", "Local street food", "Cafe lover", "Fine dining"],
  dietary_restrictions: ["Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "Halal", "Jain"],
  accessibility_needs: ["Step-free access", "Wheelchair-friendly", "Low-sensory", "Accessible transport"],
  preferred_transport: ["Train", "Bus", "Flight", "Car", "Ferry"],
  favorite_destinations: [],
};

function ProfilePage() {
  const [profile, setProfile] = useState<Profile>(emptyProfile);
  const [places, setPlaces] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([api<Profile>("/profile"), catalog("destinations")]).then(([data, destinationData]) => { setProfile(data); setPlaces(destinationData); }).catch((reason) => setError(reason.message)).finally(() => setLoading(false)); }, []);
  function toggle(field: keyof Profile, value: string) {
    setProfile((current) => {
      const values = current[field] as string[];
      return { ...current, [field]: values.includes(value) ? values.filter((entry) => entry !== value) : [...values, value] };
    });
  }
  async function save(event: FormEvent) {
    event.preventDefault(); setSaving(true); setNotice(""); setError("");
    try { setProfile(await api<Profile>("/profile", { method: "PATCH", body: JSON.stringify(profile) })); setNotice("Your preferences are saved and ready to shape your recommendations."); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save preferences."); }
    finally { setSaving(false); }
  }
  if (loading) return <div className="page-container"><Loader /></div>;
  return <div className="page-container profile-page"><PageIntro eyebrow="The little things that make a trip yours" title="Your travel preferences." detail="Tell us what you love. These notes stay with your account and help tailor your recommendations." />
    {notice && <div className="inline-success"><Check size={17} />{notice}</div>}{error && <p className="form-error">{error}</p>}
    <form onSubmit={save} className="profile-form">
      <section className="preference-section"><span className="preference-icon"><ShoppingBag size={18} /></span><div className="preference-section-copy"><h2>Your kind of spend</h2><p>A broad range is all we need to start.</p></div><select className="profile-select" value={profile.budget_range ?? ""} onChange={(event) => setProfile({ ...profile, budget_range: event.target.value || null })}>{preferenceChoices.budget_range.map((value) => <option key={value} value={value}>{value || "Choose a range"}</option>)}</select></section>
      <PreferenceScalar title="Travel style" hint="How do you like to move through a place?" value={profile.travel_style ?? ""} choices={preferenceChoices.travel_style} onChange={(value) => setProfile({ ...profile, travel_style: value || null })} />
      <PreferenceSelect title="Food you look forward to" hint="We'll use these for thoughtful local picks." field="food_preferences" profile={profile} toggle={toggle} />
      <PreferenceSelect title="Dietary needs" hint="An important part of feeling at home anywhere." field="dietary_restrictions" profile={profile} toggle={toggle} />
      <PreferenceSelect title="Accessibility needs" hint="Help us highlight options that work better for you." field="accessibility_needs" profile={profile} toggle={toggle} />
      <PreferenceSelect title="Getting around" hint="What kind of route feels right?" field="preferred_transport" profile={profile} toggle={toggle} />
      <PreferenceSelect title="Places on your mind" hint="Choose destinations you'd love to see." field="favorite_destinations" profile={profile} toggle={toggle} choices={places.map((place) => place.slug ?? place.name ?? "")} />
      <div className="profile-save"><span><ShieldCheck size={16} /> Only used for your travel experience.</span><button className="button button-dark" disabled={saving}>{saving ? "Saving…" : "Save preferences"}<Check size={16} /></button></div>
    </form>
  </div>;
}

function PreferenceScalar({ title, hint, value, choices, onChange }: { title: string; hint: string; value: string; choices: string[]; onChange: (value: string) => void }) {
  return <section className="preference-section"><div className="preference-section-copy"><h2>{title}</h2><p>{hint}</p></div><select className="profile-select" value={value} onChange={(event) => onChange(event.target.value)}>{choices.map((choice) => <option key={choice} value={choice}>{choice || "Choose a style"}</option>)}</select></section>;
}

function PreferenceSelect({ title, hint, field, profile, toggle, choices }: { title: string; hint: string; field: Exclude<keyof Profile, "budget_range" | "travel_style">; profile: Profile; toggle: (field: keyof Profile, value: string) => void; choices?: string[] }) {
  const values = choices ?? preferenceChoices[field];
  const selected = profile[field] as string[];
  return <section className="preference-section"><div className="preference-section-copy"><h2>{title}</h2><p>{hint}</p></div><div className="choice-chips">{values.map((value) => <button key={value} className={`choice-chip ${selected.includes(value) ? "choice-chip-selected" : ""}`} type="button" onClick={() => toggle(field, value)}>{selected.includes(value) && <Check size={13} />}{value}</button>)}</div></section>;
}

function AssistantPage() {
  const [sessions, setSessions] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [memory, setMemory] = useState<Memory[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const refreshSessions = () => api<Conversation[]>("/assistant/conversations").then((items) => { setSessions(items); if (!selected && items[0]) setSelected(items[0].id); });
  useEffect(() => {
    Promise.all([api<Conversation[]>("/assistant/conversations"), api<Memory[]>("/assistant/memory")])
      .then(([items, snapshots]) => { setSessions(items); setMemory(snapshots); if (items[0]) setSelected(items[0].id); })
      .catch((reason) => setError(reason.message)).finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!selected) { setMessages([]); return; }
    api<{ messages: Message[] }>(`/assistant/conversations/${selected}`).then((conversation) => setMessages(conversation.messages)).catch((reason) => setError(reason.message));
  }, [selected]);
  async function newConversation() {
    try { const item = await api<Conversation>("/assistant/conversations", { method: "POST", body: JSON.stringify({ title: "New travel chat" }) }); setSessions((current) => [item, ...current]); setSelected(item.id); setMessages([]); setNotice(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to start a conversation."); }
  }
  async function send(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim()) return;
    setSending(true); setError(""); setNotice("");
    try {
      let conversationId = selected;
      if (!conversationId) {
        const conversation = await api<Conversation>("/assistant/conversations", { method: "POST", body: JSON.stringify({ title: "New travel chat" }) });
        conversationId = conversation.id; setSelected(conversationId); setSessions((current) => [conversation, ...current]);
      }
      const result = await api<{ message: Message; connection_status: string; detail: string }>(`/assistant/conversations/${conversationId}/messages`, { method: "POST", body: JSON.stringify({ content: draft.trim() }) });
      setMessages((current) => [...current, result.message]); setDraft(""); setNotice(result.detail); await refreshSessions();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save your message."); }
    finally { setSending(false); }
  }
  async function saveMemory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const category = String(data.get("category"));
    const note = String(data.get("note"));
    try { const item = await api<Memory>("/assistant/memory", { method: "POST", body: JSON.stringify({ category, value: { note }, source_conversation_id: selected || null }) }); setMemory((current) => [item, ...current]); event.currentTarget.reset(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to save this memory."); }
  }
  async function forgetMemory(id: number) {
    try { await api(`/assistant/memory/${id}`, { method: "DELETE" }); setMemory((current) => current.filter((item) => item.id !== id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to delete this memory."); }
  }
  if (loading) return <div className="page-container"><Loader label="Opening your travel notebook…" variant="carousel" /></div>;
  return <div className="assistant-page"><aside className="assistant-sessions"><span className="eyebrow">YOUR TRAVEL DESK</span><h2>Conversations</h2><button className="button button-dark button-full" onClick={newConversation}><MessageCircle size={16} /> New conversation</button><div className="session-list">{sessions.map((session) => <button key={session.id} className={`session-item ${session.id === selected ? "session-active" : ""}`} onClick={() => setSelected(session.id)}><MessageCircle size={15} /><span>{session.title}</span></button>)}</div><div className="assistant-session-note"><ShieldCheck size={15} /> Your conversation history is private to your account.</div></aside>
    <section className="assistant-chat"><div className="assistant-chat-head"><div><span className="eyebrow">A LITTLE HELP WITH THE BIG IDEAS</span><h1>Your travel companion.</h1></div><span className="assistant-online"><i /> Memory-ready connection point</span></div>
      <div className="chat-messages">{messages.length ? messages.map((message) => <article key={message.id} className={`chat-message message-${message.role}`}><span>{message.role === "user" ? "YOU" : "VOYARA"}</span><p>{message.content}</p></article>) : <div className="chat-welcome"><span className="chat-welcome-icon"><Sparkles size={24} /></span><h2>Let's make a trip feel like you.</h2><p>Try asking about a slow weekend, a vegetarian food trail, or a route with a view.</p><div className="prompt-chips">{["Plan a slow weekend in the hills", "Find vegetarian food in Goa", "I love trains and local culture"].map((prompt) => <button key={prompt} onClick={() => setDraft(prompt)}>{prompt}<ArrowUpRight size={13} /></button>)}</div></div>}</div>
      {notice && <div className="connection-notice"><Compass size={16} />{notice}</div>}{error && <p className="form-error">{error}</p>}
      <form className="chat-compose" onSubmit={send}><textarea value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Tell me what kind of trip you have in mind…" rows={2} /><button className="button button-dark" disabled={sending || !draft.trim()}>{sending ? "Saving…" : "Send"}<ArrowUpRight size={16} /></button></form><p className="assistant-disclaimer">Your message will be saved. AI replies become available when your memory/chat backend is connected.</p></section>
    <aside className="memory-sidebar"><span className="eyebrow">THE LITTLE THINGS</span><h2>What your guide knows</h2><p>Preference snapshots are saved across sessions and ready for your AI implementation.</p><div className="memory-list">{memory.length ? memory.map((item) => <article className="memory-card" key={item.id}><span><Sparkles size={14} /> {item.category.replaceAll("_", " ")}</span><p>{Object.values(item.value).join(", ") || "Preference saved"}</p><button aria-label={`Forget ${item.category}`} onClick={() => forgetMemory(item.id)}><X size={14} /></button></article>) : <EmptyState title="A blank page" detail="Save a preference here to give your guide a place to start." />}</div><form className="memory-form" onSubmit={saveMemory}><label>Save a memory<input name="category" placeholder="e.g. food_preferences" required /></label><label>A note about it<input name="note" placeholder="I love family-run cafes" required /></label><button className="button button-outline button-full">Add to memory <ArrowRight size={14} /></button></form><Link to="/profile" className="inline-link">Edit your travel profile <ArrowRight size={14} /></Link></aside>
  </div>;
}

function NotFound() {
  return <div className="page-container"><EmptyState title="We took a wrong turn" detail="That page is not on this map, but there are plenty of lovely places to go next." action={<Link to="/" className="button button-dark">Back home</Link>} /></div>;
}

export default function App() {
  return <Shell><Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/destinations" element={<BrowsePage kind="destinations" />} />
    <Route path="/destinations/:id" element={<DestinationPage />} />
    <Route path="/stays" element={<BrowsePage kind="stays" />} />
    <Route path="/food" element={<BrowsePage kind="food" />} />
    <Route path="/transport" element={<BrowsePage kind="transport" />} />
    <Route path="/guides" element={<BrowsePage kind="guides" />} />
    <Route path="/login" element={<AuthPage mode="login" />} />
    <Route path="/signup" element={<AuthPage mode="signup" />} />
    <Route path="/trips" element={<RequireAuth><DashboardPage /></RequireAuth>} />
    <Route path="/dashboard" element={<RequireAuth><DashboardPage /></RequireAuth>} />
    <Route path="/booking" element={<BookingPage />} />
    <Route path="/itineraries" element={<RequireAuth><TripsPage /></RequireAuth>} />
    <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
    <Route path="/assistant" element={<RequireAuth><AssistantPage /></RequireAuth>} />
    <Route path="*" element={<NotFound />} />
  </Routes></Shell>;
}
