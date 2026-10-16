import { forwardRef, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import HTMLFlipBook from "react-pageflip";
import {
  ArrowLeft, ArrowRight, ArrowUpRight, CalendarDays, Check, ChevronDown,
  Compass, Heart, MessageCircle, Plane, Phone, Play, Search, ShieldCheck,
  ShoppingBag, Sparkles, Tag, Ticket, UserRound, X,
} from "lucide-react";
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  api, catalog, emptyProfile, imageFor, money, useDebouncedValue,
  type CatalogItem, type CatalogKind, type ImageCatalog, type Lead, type Offer, type Profile,
} from "./api";
import { CatalogCard, EmptyState, FavoriteButton, Image, Loader } from "./components";
import { useApp, type CartItem, type NewCartItem } from "./state";

type BookingItem = { item_type: string; item_id: number; quantity: number; unit_price_inr: number; start_date: string | null; end_date: string | null; start_time: string | null; duration_min: number | null };
type Booking = { id: number; status: string; total_inr: number; created_at: string; items: BookingItem[] };
type Itinerary = { id: number; title: string; destination_id: number | null; start_date: string | null; end_date: string | null; notes: string; booking_ids: number[] };

function useImages() {
  const [images, setImages] = useState<ImageCatalog>({ destinations: [], stays: [], food: [] });
  useEffect(() => { api<ImageCatalog>("/images.json").then(setImages).catch((reason: Error) => console.error("Unable to load the travel image catalog; using image fallbacks.", reason)); }, []);
  return images;
}

const ROUTE_TITLES: Record<string, string> = {
  "/": "Voyara — Find your somewhere",
  "/destinations": "Explore destinations — Voyara",
  "/stays": "Stays & hotels — Voyara",
  "/food": "Food & cafés — Voyara",
  "/transport": "Transport routes — Voyara",
  "/guides": "Local guides — Voyara",
  "/booking": "Trip planner — Voyara",
  "/trips": "Your travel desk — Voyara",
  "/itineraries": "Itineraries — Voyara",
  "/profile": "Travel preferences — Voyara",
  "/wishlist": "Wishlist — Voyara",
  "/login": "Sign in — Voyara",
  "/signup": "Create account — Voyara",
};

function useRouteMetadata(title: string, description: string) {
  useEffect(() => {
    document.title = title;
    let meta = document.querySelector('meta[name="description"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "description");
      document.head.appendChild(meta);
    }
    meta.setAttribute("content", description);
  }, [title, description]);
}

function Breadcrumbs({ trail }: { trail: { label: string; to?: string }[] }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [{ "@type": "ListItem", position: 1, name: "Home", item: "/" },
      ...trail.map((crumb, index) => ({
        "@type": "ListItem", position: index + 2, name: crumb.label,
        ...(crumb.to ? { item: crumb.to } : {}),
      }))],
  };
  return <nav className="breadcrumbs" aria-label="Breadcrumb">
    <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
    <Link to="/">Home</Link>
    {trail.map((crumb, index) => <span key={`${crumb.label}-${index}`}>
      <span aria-hidden="true"> / </span>
      {crumb.to && index < trail.length - 1 ? <Link to={crumb.to}>{crumb.label}</Link> : <span aria-current="page">{crumb.label}</span>}
    </span>)}
  </nav>;
}

function Shell({ children }: { children: ReactNode }) {
  const { user, cart, signOut } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  useRouteMetadata(
    ROUTE_TITLES[location.pathname] ?? "Voyara — Find your somewhere",
    "Discover thoughtful stays, local food, scenic routes and guides — planned in one place with Voyara."
  );
  useEffect(() => { window.scrollTo(0, 0); }, [location.pathname]);
  const navItems = [
    ["/destinations", "Explore"],
    ["/stays", "Stays"],
    ["/food", "Food"],
    ["/transport", "Transport"],
    ["/guides", "Guides"],
    ["/booking", "Plan"],
  ];
  function goBack() {
    const historyIndex = window.history.state?.idx;
    if (typeof historyIndex === "number" && historyIndex > 0) navigate(-1);
    else {
      const segments = location.pathname.split("/").filter(Boolean);
      const collection = ["destinations", "stays", "food", "transport", "guides"];
      navigate(segments.length > 1 && collection.includes(segments[0]) ? `/${segments[0]}` : "/");
    }
  }
  return <div className="site-shell">
    <header className="site-header">
      <Link to="/" className="brand"><span className="brand-mark"><Compass size={18} /></span> voyara<span className="brand-period">.</span></Link>
      <nav className="main-nav" aria-label="Main navigation">
        <div className="nav-group">
          <NavLink to="/destinations" className="nav-group-link">Explore <ChevronDown size={13} /></NavLink>
          <div className="nav-group-panel" role="menu">
            <div>
              <p>Collections</p>
              <ul>
                <li><Link to="/destinations">All destinations</Link></li>
                <li><Link to="/stays">Stays & hotels</Link></li>
                <li><Link to="/food">Food & cafés</Link></li>
                <li><Link to="/transport">Transport routes</Link></li>
                <li><Link to="/guides">Local guides</Link></li>
              </ul>
            </div>
            <div>
              <p>Quick links</p>
              <ul>
                <li><Link to="/wishlist">Your wishlist</Link></li>
                <li><Link to="/itineraries">Saved itineraries</Link></li>
                <li><Link to="/trips">My trips</Link></li>
                <li><Link to="/dashboard">Travel desk</Link></li>
                <li><Link to="/booking">Trip planner</Link></li>
              </ul>
            </div>
          </div>
        </div>
        {navItems.slice(1).map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
      </nav>
      <div className="header-actions">
        {user && <Link to="/wishlist" className="icon-button wishlist-button" aria-label="Wishlist"><Heart size={18} /></Link>}
        <Link to="/booking" className="icon-button cart-button" aria-label="Trip request"><ShoppingBag size={18} />{cart.length > 0 && <span className="cart-count">{cart.length}</span>}</Link>
        {user ? <>
          <Link to="/trips" className="header-link hide-small">My trips</Link>
              <Link to="/dashboard" className="header-link hide-small" title="Travel desk"><UserRound size={17} /></Link>
          <button className="button button-quiet hide-small" onClick={signOut}>Sign out</button>
        </> : <Link to="/login" className="button button-dark header-login">Sign in <ArrowUpRight size={15} /></Link>}
      </div>
    </header>
    <main className="page-book-perspective page-main">
      {location.pathname !== "/" && <div className="route-back-row"><button className="route-back-button" onClick={goBack}><ArrowLeft size={16} /> Back</button></div>}
      <BookStage locationKey={`${location.pathname}${location.search}`}>{children}</BookStage>
    </main>
    <TravelHelper />
    <footer className="site-footer">
      <div className="footer-brand"><Link to="/" className="brand"><span className="brand-mark"><Compass size={18} /></span> voyara<span className="brand-period">.</span></Link><p>Find a place that feels like yours.</p></div>
      <div className="footer-sitemap">
        <div><p>Explore</p><Link to="/destinations">Destinations</Link><Link to="/stays">Stays & hotels</Link><Link to="/food">Food & cafés</Link><Link to="/transport">Transport routes</Link><Link to="/guides">Local guides</Link></div>
        <div><p>Plan</p><Link to="/booking">Trip planner</Link><Link to="/itineraries">Itineraries</Link><Link to="/trips">Travel desk</Link><Link to="/wishlist">Wishlist</Link></div>
        <div><p>Account</p><Link to="/profile">Preferences</Link>{user ? <button type="button" onClick={signOut}>Sign out</button> : <Link to="/login">Sign in</Link>}{!user && <Link to="/signup">Create account</Link>}</div>
      </div>
      <span className="footer-note">Thoughtfully planned. Yours to discover.</span>
    </footer>
  </div>;
}

const FlipPage = forwardRef<HTMLDivElement, { children: ReactNode }>(function FlipPage({ children }, ref) {
  return <div ref={ref} className="flip-page"><div className="flip-page-scroll">{children}</div></div>;
});

const FLIP_MS = 780;

function BookStage({ locationKey, children }: { locationKey: string; children: ReactNode }) {
  const bookRef = useRef<{ pageFlip(): { flipNext(): void } } | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const childrenRef = useRef(children);
  const keyRef = useRef(locationKey);
  const busyRef = useRef(false);
  const [bookSize, setBookSize] = useState({ width: 0, height: 0 });
  const [pages, setPages] = useState<ReactNode[]>([children]);
  const [bookEpoch, setBookEpoch] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );

  childrenRef.current = children;

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReducedMotion(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const measure = () => {
      const width = Math.min(Math.max(stage.clientWidth, 300), 1180);
      const height = Math.min(Math.max(stage.clientHeight, 380), 900);
      setBookSize({ width, height });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(stage);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (keyRef.current === locationKey) return;
    keyRef.current = locationKey;
    if (reducedMotion || busyRef.current) {
      setPages([childrenRef.current]);
      return;
    }
    busyRef.current = true;
    setPages((current) => [...current, childrenRef.current]);
    window.setTimeout(() => {
      try { bookRef.current?.pageFlip()?.flipNext(); } catch { /* book may be mid-update */ }
    }, 60);
    window.setTimeout(() => {
      busyRef.current = false;
      setPages([childrenRef.current]);
      setBookEpoch((epoch) => epoch + 1);
    }, FLIP_MS + 120);
  }, [locationKey, reducedMotion]);

  if (reducedMotion || !bookSize.width) {
    return <div className="flip-stage" ref={stageRef}><div className="flip-static">{children}</div></div>;
  }
  return <div className="flip-stage" ref={stageRef}>
    <HTMLFlipBook
      key={bookEpoch}
      ref={bookRef}
      className="flip-book"
      style={{ width: "100%", height: "100%" }}
      width={bookSize.width}
      height={bookSize.height}
      size="fixed"
      minWidth={300}
      maxWidth={1180}
      minHeight={380}
      maxHeight={900}
      usePortrait={true}
      showCover={false}
      autoSize={false}
      drawShadow={true}
      maxShadowOpacity={0.4}
      flippingTime={FLIP_MS}
      useMouseEvents={false}
      disableFlipByClick={true}
      showPageCorners={false}
      clickEventForward={true}
      mobileScrollSupport={true}
      startPage={0}
      startZIndex={3}
      swipeDistance={12}
    >
      {pages.map((page, index) => <FlipPage key={index}>{page}</FlipPage>)}
    </HTMLFlipBook>
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

function cartItemFor(kind: CatalogKind, item: CatalogItem, destinations: CatalogItem[]): NewCartItem {
  const destination = destinations.find((place) => place.id === item.destination_id);
  return {
    item_type: kind === "stays" ? "stay" : kind === "transport" ? "transport" : kind === "guides" ? "guide" : "food",
    item_id: item.id,
    name: item.name ?? item.operator ?? "Travel experience",
    price: item.price_inr ?? 0,
    destination_id: item.destination_id,
    destination_name: destination?.name,
    duration_min: kind === "transport" ? item.duration_min ?? 60 : kind === "food" ? 90 : 180,
  };
}

function TravelHelper() {
  const { user } = useApp();
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"search" | "advice">("search");
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<{ role: "user" | "system"; content: string }[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const currentKind = location.pathname.split("/").filter(Boolean)[0];
  const searchKind = ["destinations", "stays", "food", "transport", "guides"].includes(currentKind) ? currentKind : "destinations";

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content) return;
    if (!user) { navigate("/login"); setNotice("Sign in to save a message to your travel desk."); return; }
    setSending(true); setError(""); setNotice("");
    try {
      let id = conversationId;
      if (!id) {
        const conversation = await api<{ id: string }>("/assistant/conversations", {
          method: "POST", body: JSON.stringify({ title: "Trip planning chat" }),
        });
        id = conversation.id;
        setConversationId(id);
      }
      const result = await api<{ reply: { content: string } }>(`/assistant/conversations/${id}/messages`, {
        method: "POST", body: JSON.stringify({ content }),
      });
      setMessages((current) => [...current, { role: "user", content }, { role: "system", content: result.reply.content }]);
      setDraft("");
      setNotice("Reply from your travel desk is above.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save your message.");
    } finally {
      setSending(false);
    }
  }

  function searchCatalog(event: FormEvent) {
    event.preventDefault();
    const term = query.trim();
    navigate(`/${searchKind}${term ? `?q=${encodeURIComponent(term)}` : ""}`);
    setOpen(false);
  }

  return <div className={`travel-helper ${open ? "travel-helper-open" : ""}`}>
    {open && <section className="travel-helper-panel" aria-label="Travel search and advice">
      <div className="travel-helper-head"><div><span className="eyebrow">A LITTLE HELP, ANYWHERE</span><h2>Find your next somewhere.</h2></div><button type="button" className="travel-helper-close" aria-label="Close travel helper" onClick={() => setOpen(false)}><X size={18} /></button></div>
      <div className="helper-mode-tabs" role="tablist" aria-label="Choose search or advice">
        <button type="button" role="tab" aria-selected={mode === "search"} className={mode === "search" ? "helper-mode-active" : ""} onClick={() => setMode("search")}><Search size={14} /> Manual search</button>
        <button type="button" role="tab" aria-selected={mode === "advice"} className={mode === "advice" ? "helper-mode-active" : ""} onClick={() => setMode("advice")}><Sparkles size={14} /> AI advice</button>
      </div>
      {mode === "search" ? <form className="helper-search-form" onSubmit={searchCatalog}>
        <p>Search {searchKind} by name, place or idea. Results open in the matching collection.</p>
        <label className="sr-only" htmlFor="travel-helper-search">Search {searchKind}</label>
        <div className="helper-search-field"><input id="travel-helper-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="e.g. Goa, quiet beach stay…" /><button className="button button-dark" aria-label="Search"><Search size={16} /></button></div>
      </form> : <div className="helper-advice">
        <p className="helper-disclaimer">Suggestions come from our live catalog. Sign in to keep a copy in your travel desk.</p>
        <div className="helper-messages">{messages.map((message, index) => <p className={`helper-message helper-message-${message.role}`} key={`${index}-${message.content}`}>{message.content}</p>)}</div>
        {!user && <p className="muted small-copy">Sign in to save your questions.</p>}
        <form className="helper-chat-form" onSubmit={sendMessage}><input aria-label="Ask for travel advice" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask about your trip…" /><button className="button button-dark" disabled={sending || !draft.trim()} aria-label="Send question">{sending ? "…" : <ArrowUpRight size={16} />}</button></form>
        {notice && <p className="helper-status">{notice}</p>}{error && <p className="form-error">{error}</p>}
      </div>}
    </section>}
    <button type="button" className="travel-helper-toggle" aria-expanded={open} onClick={() => setOpen((current) => !current)}>{open ? <X size={18} /> : <MessageCircle size={18} />}<span>{open ? "Close" : "Search & chat"}</span></button>
  </div>;
}

const homeFaqs = [
  { q: "How does request-first booking work?", a: "You add stays, meals, routes and guides to a trip plan and send one request. Nothing is charged — a provider confirms final pricing and availability, and you can cancel any request before confirmation." },
  { q: "Can I change dates after adding an item?", a: "Yes. Open the trip planner, pick new dates or times for any item, and the schedule chart updates instantly, warning you about overlaps or clashes with your stay." },
  { q: "Are the listings and prices final?", a: "Listings are curated examples with sample pricing. Your request gets a real confirmation from the provider before anything is booked or paid." },
  { q: "How do I cancel a trip request?", a: "Open My trips, find the request and choose Cancel. Seats held on transport routes are released the moment a request is cancelled." },
  { q: "What are travel preferences for?", a: "Your budget range, food needs, accessibility and transport style shape which listings the catalog highlights first — they stay private to your account." },
  { q: "Can I save places I'm not ready to book?", a: "Yes — tap the heart on any stay, meal, route or guide to keep it in your wishlist, then move it into a trip plan whenever you're ready." },
];

function FaqSection() {
  return <section className="stitch-section faq-section" id="faq">
    <div className="stitch-section-heading"><div><span className="eyebrow">Good to know</span><h2>Frequently asked questions.</h2><p>The little details, answered before you ask.</p></div></div>
    <div className="faq-list" itemScope itemType="https://schema.org/FAQPage">
      {homeFaqs.map((faq, index) => <details className="faq-item" key={faq.q} open={index === 0} itemScope itemProp="mainEntity" itemType="https://schema.org/Question">
        <summary itemProp="name">{faq.q}</summary>
        <div itemScope itemProp="acceptedAnswer" itemType="https://schema.org/Answer"><p itemProp="text">{faq.a}</p></div>
      </details>)}
    </div>
  </section>;
}

function OffersSection() {
  const [offers, setOffers] = useState<Offer[]>([]);
  const [tab, setTab] = useState<string>("all");
  useEffect(() => { api<Offer[]>("/offers").then(setOffers).catch(() => setOffers([])); }, []);
  const modules = ["all", ...new Set(offers.map((offer) => offer.module))];
  const visible = tab === "all" ? offers : offers.filter((offer) => offer.module === tab || offer.module === "any");
  if (!offers.length) return null;
  return <section className="stitch-section offers-section" id="offers">
    <div className="stitch-section-heading"><div><span className="eyebrow">Offers for you</span><h2>A little something off the top.</h2><p>Apply a code in the trip planner when you send a request.</p></div></div>
    <div className="offers-tabs" role="tablist" aria-label="Offer categories">
      {modules.map((module) => <button key={module} role="tab" aria-selected={tab === module} className={tab === module ? "offer-tab-active" : ""} onClick={() => setTab(module)}>{module === "all" ? "All offers" : module}</button>)}
    </div>
    <div className="offers-grid">
      {visible.map((offer) => <article className="offer-card" key={offer.code}>
        <span className="offer-code"><Ticket size={15} /> {offer.code}</span>
        <h3>{offer.title}</h3>
        {offer.description && <p>{offer.description}</p>}
        <small>{offer.discount_percent ? `${offer.discount_percent}% off` : `₹${offer.discount_flat_inr?.toLocaleString("en-IN")} off`}{offer.min_amount_inr ? ` · min ₹${offer.min_amount_inr.toLocaleString("en-IN")}` : ""}{offer.valid_till ? ` · till ${offer.valid_till}` : ""}</small>
      </article>)}
    </div>
  </section>;
}

const currencyRates: Record<string, number> = { USD: 86.4, EUR: 92.8, GBP: 108.6, AUD: 56.2, AED: 23.5, SGD: 64.1 };

function CurrencyTool() {
  const [amount, setAmount] = useState("100");
  const [code, setCode] = useState("USD");
  const numeric = Number(amount) || 0;
  return <section className="currency-tool" id="currency">
    <div><span className="eyebrow">TRAVEL MONEY</span><h2>Quick currency check.</h2><p>Indicative rates for planning your spending money. Final rates are confirmed at booking.</p></div>
    <div className="currency-card">
      <label><span>Amount</span><input type="number" min="0" value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
      <label><span>Currency</span><select value={code} onChange={(event) => setCode(event.target.value)}>{Object.keys(currencyRates).map((key) => <option key={key} value={key}>{key}</option>)}</select></label>
      <div className="currency-result"><small>≈ INR</small><strong>{money(Math.round(numeric * (currencyRates[code] ?? 1)))}</strong></div>
    </div>
  </section>;
}

const storyVideos = [
  { id: "sLRnIuYFFTw", title: "Backwaters at golden hour" },
  { id: "0lLpX4sQfjw", title: "A food walk through old lanes" },
  { id: "rB2Jxbb2dwA", title: "Misty mornings in the hills" },
];

function StoryVideos() {
  const [playing, setPlaying] = useState<string | null>(null);
  return <section className="stitch-section story-videos" id="stories">
    <div className="stitch-section-heading"><div><span className="eyebrow">Your daily dose of wanderlust</span><h2>Stories that move you.</h2><p>Short films from real journeys. Videos load only when you press play.</p></div></div>
    <div className="video-grid">
      {storyVideos.map((video) => <div className="video-card" key={video.id}>
        {playing === video.id
          ? <iframe src={`https://www.youtube.com/embed/${video.id}?autoplay=1&rel=0`} title={video.title} allow="autoplay; encrypted-media; picture-in-picture" allowFullScreen />
          : <button type="button" className="video-poster" onClick={() => setPlaying(video.id)} aria-label={`Play ${video.title}`}>
              <Play size={30} /><span>{video.title}</span>
            </button>}
      </div>)}
    </div>
  </section>;
}

function LeadCapture({ presetInterest }: { presetInterest?: string }) {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { user } = useApp();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const fields = new FormData(event.currentTarget);
    try {
      await api<Lead>("/leads", {
        method: "POST",
        body: JSON.stringify({
          name: String(fields.get("name")), phone: String(fields.get("phone")),
          email: String(fields.get("email")) || null,
          interest: String(fields.get("interest")) || presetInterest || null,
          preferred_time: String(fields.get("preferred_time")) || null,
        }),
      });
      setDone(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to send your request."); }
    finally { setBusy(false); }
  }
  return <>
    <button type="button" className="lead-callback-button" onClick={() => setOpen(true)}><Phone size={15} /> Request a call</button>
    {open && <div className="lead-modal-backdrop" onClick={() => setOpen(false)}>
      <div className="lead-modal" role="dialog" aria-modal="true" aria-label="Request a callback" onClick={(event) => event.stopPropagation()}>
        <button className="lead-modal-close" aria-label="Close" onClick={() => setOpen(false)}><X size={17} /></button>
        {done ? <><h3>We'll call you soon.</h3><p>Your request is with our travel desk. Someone will reach out at your preferred time.</p><button className="button button-dark" onClick={() => { setOpen(false); setDone(false); }}>Done</button></>
          : <form className="form-stack" onSubmit={submit}>
              <h3>Talk to a real person.</h3>
              <p className="muted">Tell us when to call and what you're dreaming about. No account needed.</p>
              <label>Your name<input name="name" required minLength={2} maxLength={120} /></label>
              <label>Phone<input name="phone" required pattern="[0-9+\-\s()]{7,20}" placeholder="+91 …" /></label>
              <label>Email (optional)<input name="email" type="email" /></label>
              <label>What are you planning?<input name="interest" defaultValue={presetInterest ?? ""} maxLength={120} placeholder="e.g. Goa in December" /></label>
              <label>Best time to call<select name="preferred_time"><option value="">Anytime</option><option value="morning">Morning</option><option value="afternoon">Afternoon</option><option value="evening">Evening</option></select></label>
              {error && <p className="form-error" role="alert">{error}</p>}
              <button className="button button-dark" disabled={busy}>{busy ? "Sending…" : "Request a callback"}</button>
              {!user && <p className="muted small-copy">Want to keep everything in one place? <Link to="/login">Sign in</Link> instead.</p>}
            </form>}
      </div>
    </div>}
  </>;
}

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
      catalog("destinations", { limit: "20" }),
      catalog("stays", { limit: "12" }),
      catalog("food", { limit: "12" }),
      catalog("transport", { limit: "12" }),
      catalog("guides", { limit: "12" }),
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
  const trending = destinations.slice(0, 3);
  const trendingChips = trending.length
    ? trending
    : [{ id: 0, name: "Goa" }, { id: 0, name: "Manali" }, { id: 0, name: "Ladakh" }];
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
      <div className="stitch-hero-edition">
        <span className="stitch-hero-edition-brand"><Compass size={14} /> VOYARA FIELD NOTES</span>
        <span className="stitch-hero-edition-tag">India, at your own pace</span>
      </div>
      <div className="stitch-hero-strip" aria-label="Trending destinations">
        <span className="stitch-hero-strip-label"><Sparkles size={13} /> Trending now</span>
        {trendingChips.map((place, index) => (
          <Link key={`${place.id}-${place.name}-${index}`} to={place.id > 0 ? `/destinations/${place.id}` : "/destinations"} className="stitch-hero-chip">
            {place.name ?? "Somewhere new"}{place.state ? <small>{place.state}</small> : null}
          </Link>
        ))}
        <span className="stitch-hero-strip-stat"><strong>120+</strong> curated stays & experiences</span>
      </div>
      <div className="stitch-hero-copy"><span className="eyebrow eyebrow-light">A little farther, a little freer</span>
        <h1>Find your<br /><em>somewhere.</em></h1>
        <p>Thoughtfully planned journeys, local discoveries, and all the little details that make a trip feel like yours.</p>
        <div className="hero-actions"><Link to="/destinations" className="button button-lime">Explore destinations <ArrowUpRight size={16} /></Link><Link to="/itineraries" className="button button-glass">Build my itinerary</Link></div>
        <div className="hero-proof"><strong>One place for the whole journey.</strong><span> From the first idea to the way back home.</span></div>
      </div>
      <div className="stitch-hero-art">
        {heroImage && <Image src={heroImage} alt="" className="stitch-hero-photo" priority />}
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
      {loading ? <Loader label="Loading recommendations…" variant="suitcase" /> : error ? <EmptyState title="Listings are taking the scenic route" detail={error} /> : visibleListings.length ? <div className="catalog-grid">{visibleListings.map((item) => <CatalogCard key={`${item.catalogKind}-${item.id}`} item={item} kind={item.catalogKind} destinations={destinations} imageCatalog={images} onAdd={() => addToCart(cartItemFor(item.catalogKind, item, destinations))} />)}</div> : <EmptyState title="No matching listings found" detail="Try a broader destination, category or budget." />}
      {/* Heart toggles appear on collection pages and the wishlist; the home strip keeps its quick-add focus. */}
      {!showAll && matchingListings.length > visibleListings.length && <button className="button button-outline stitch-more" onClick={() => setShowAll(true)}>Show all {matchingListings.length} listings <ArrowRight size={15} /></button>}
    </section>
    <section className="stitch-planner" id="planner">
      <div><span className="eyebrow">Your trip, pieced together</span><h2>Less tab-hopping.<br />More looking forward.</h2><p>Bring stays, transport, food stops and things to do into one editable itinerary. Start with a destination, then shape the days around your time and budget.</p><Link className="button button-dark" to="/itineraries">Start planning <ArrowUpRight size={16} /></Link><div className="planner-lead"><LeadCapture /></div></div>
      <div className="stitch-plan-card"><div><strong>A weekend in the hills</strong><span>SAMPLE ITINERARY</span></div><article><span>🚆</span><p><strong>Morning train to the mountains</strong><small>Day 1 · Transport idea</small></p></article><article><span>🏡</span><p><strong>Check in at a local homestay</strong><small>Day 1 · Stay idea</small></p></article><article><span>🥘</span><p><strong>Find a local lunch spot</strong><small>Day 2 · Food idea</small></p></article><small>Sample only · Create a private itinerary to make it yours</small></div>
    </section>
    <OffersSection />
    <CurrencyTool />
    <StoryVideos />
    <FaqSection />
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
  const [searchParams, setSearchParams] = useSearchParams();
  // Filters live in the URL so any filtered view is shareable and back-button friendly.
  const search = searchParams.get("q") ?? "";
  const price = searchParams.get("price") ?? "";
  const category = searchParams.get("type") ?? "";
  const diet = searchParams.get("diet") ?? "";
  const amenity = searchParams.get("amenity") ?? "";
  const routeDestination = searchParams.get("arrive") ?? "";
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);
  const debouncedSearch = useDebouncedValue(search, 300);
  const [totalLoaded, setTotalLoaded] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [moreLoading, setMoreLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { addToCart, favorites, toggleFavorite } = useApp();
  const PAGE_SIZE = 12;

  function setFilter(key: string, value: string) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(key, value); else next.delete(key);
      if (key !== "page") next.delete("page");
      return next;
    }, { replace: true });
  }
  useEffect(() => { catalog("destinations").then(setDestinations).catch((reason: Error) => setError(reason.message)); }, []);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError("");
    const params: Record<string, string> = { q: debouncedSearch, limit: String(PAGE_SIZE), offset: String((page - 1) * PAGE_SIZE) };
    if (price) params.max_price = price;
    if (category) params[kind === "destinations" ? "tag" : kind === "guides" ? "specialty" : "type"] = category;
    if (kind === "food" && diet) params.diet = diet;
    if (kind === "stays" && amenity) params.amenity = amenity;
    if (kind === "transport" && routeDestination) params.destination_id = routeDestination;
    catalog(kind, params).then((result) => {
      if (cancelled) return;
      setItems(result); setTotalLoaded(page * PAGE_SIZE); setHasMore(result.length === PAGE_SIZE);
    })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [kind, debouncedSearch, price, category, diet, amenity, routeDestination, page]);
  function loadMore() {
    setMoreLoading(true);
    const params: Record<string, string> = { q: debouncedSearch, limit: String(PAGE_SIZE), offset: String(items.length) };
    if (price) params.max_price = price;
    if (category) params[kind === "destinations" ? "tag" : kind === "guides" ? "specialty" : "type"] = category;
    if (kind === "food" && diet) params.diet = diet;
    if (kind === "stays" && amenity) params.amenity = amenity;
    if (kind === "transport" && routeDestination) params.destination_id = routeDestination;
    catalog(kind, params).then((result) => {
      setItems((current) => [...current, ...result]); setTotalLoaded(items.length + result.length);
      setHasMore(result.length === PAGE_SIZE);
    })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setMoreLoading(false));
  }
  const filters = kind === "destinations" ? ["All places", "Beach", "Nature", "Culture"] :
    kind === "stays" ? ["All stays", "hotel", "hostel", "homestay", "resort"] :
    kind === "food" ? ["All food", "restaurant", "cafe", "street_stall"] :
    kind === "transport" ? ["All routes", "flight", "train", "bus", "ferry"] : ["All guides", "history", "food walks", "adventure"];
  const onAdd = (item: CatalogItem) => addToCart(cartItemFor(kind, item, destinations));
  const title = kind === "destinations" ? "Find your somewhere." : info.title;
  return <div className="browse-page">
    <PageIntro eyebrow={info.eyebrow} title={title} detail={info.detail} />
    <div className="browse-toolbar">
      <label className="search-field"><Search size={18} /><input value={search} onChange={(event) => setFilter("q", event.target.value)} placeholder={info.placeholder} /></label>
      <label className="select-field"><span>{kind === "food" ? "Diet" : "Category"}</span><select value={kind === "food" ? diet : category} onChange={(event) => setFilter(kind === "food" ? "diet" : "type", event.target.value)}>
        {(kind === "food" ? ["", "veg", "non_veg", "both"] : ["", ...filters.slice(1)]).map((value) => <option key={value || "all"} value={value}>{value ? value.replaceAll("_", " ") : filters[0]}</option>)}
      </select><ChevronDown size={15} /></label>
      {kind === "stays" && <label className="select-field"><span>Amenity</span><select value={amenity} onChange={(event) => setFilter("amenity", event.target.value)}><option value="">Any amenity</option><option value="wifi">Wi-Fi</option><option value="breakfast">Breakfast</option><option value="home-food">Home food</option></select><ChevronDown size={15} /></label>}
      {kind === "transport" && <label className="select-field"><span>Arrive in</span><select value={routeDestination} onChange={(event) => setFilter("arrive", event.target.value)}><option value="">Any destination</option>{destinations.map((place) => <option key={place.id} value={place.id}>{place.name}</option>)}</select><ChevronDown size={15} /></label>}
      {kind !== "destinations" && <label className="select-field price-select"><span>Price ceiling</span><select value={price} onChange={(event) => setFilter("price", event.target.value)}><option value="">Any price</option><option value="1000">Under ₹1,000</option><option value="3000">Under ₹3,000</option><option value="7000">Under ₹7,000</option></select><ChevronDown size={15} /></label>}
      <span className="results-count">{loading ? " " : `Page ${page} · ${items.length} shown`}</span>
    </div>
    {loading ? <Loader label="Searching the map…" variant="globe" /> : error ? <EmptyState title="We couldn't load this collection" detail={error} /> : items.length === 0 ? <EmptyState title="No matches just yet" detail="Try a wider search or clear a filter to see more." /> :
      kind === "destinations" ? <div className="destination-grid browse-destinations">{items.map((item, index) => <DestinationTile key={item.id} item={item} destinations={items} images={images} index={index % 4} />)}</div> :
      <div className="catalog-grid">{items.map((item) => <CatalogCard key={item.id} item={item} kind={kind} destinations={destinations} imageCatalog={images} onAdd={() => onAdd(item)}
        saved={favorites.has(`${kind}:${item.id}`)} onToggleFavorite={() => toggleFavorite(kind, item.id)} />)}</div>}
    {!loading && !error && (hasMore || page > 1) && <div className="browse-pagination">
      {page > 1 && <button className="button button-outline" onClick={() => setFilter("page", String(page - 1))}><ArrowLeft size={15} /> Previous</button>}
      {hasMore && <button className="button button-dark" disabled={moreLoading} onClick={loadMore}>{moreLoading ? "Loading…" : `Show more (loaded ${totalLoaded})`} <ArrowRight size={15} /></button>}
    </div>}
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
    <Breadcrumbs trail={[{ label: "Destinations", to: "/destinations" }, { label: destination.name ?? "Destination" }]} />
    <section className="detail-hero"><Image src={photo} alt={destination.name ?? "Destination"} priority /><div className="detail-hero-shade" /><div className="detail-hero-content"><span className="eyebrow eyebrow-light">{destination.state}, {destination.country}</span><h1>{destination.name}</h1><p>{destination.description}</p><div className="detail-tags">{destination.tags?.map((tag) => <span key={tag}>{tag}</span>)}</div></div></section>
    <div className="destination-meta"><span><CalendarDays size={17} /> Best season: {destination.best_season ?? "Anytime"}</span><span><Compass size={17} /> {destination.climate ?? "Come as you are"}</span><span><Heart size={17} /> {money(destination.avg_cost_inr)} average trip</span></div>
    {(["stays", "food", "transport", "guides"] as const).map((kind) => <section className="content-section detail-section" key={kind}><SectionHeading eyebrow={`Around ${destination.name}`} title={{ stays: "Places to stay", food: "Good things to eat", transport: "Ways to get there", guides: "People who know the place" }[kind]} link={`Explore ${kind}`} to={`/${kind}`} />{items[kind].length ? <div className="catalog-grid detail-list">{items[kind].slice(0, 3).map((item) => <CatalogCard key={item.id} item={item} kind={kind} destinations={[destination]} imageCatalog={images} onAdd={() => addToCart(cartItemFor(kind, item, [destination]))} />)}</div> : <p className="inline-empty">New local recommendations are on the way.</p>}</section>)}
  </div>;
}

function CatalogDetailPage({ kind }: { kind: Exclude<CatalogKind, "destinations"> }) {
  const { id } = useParams();
  const images = useImages();
  const [item, setItem] = useState<CatalogItem | null>(null);
  const [destinations, setDestinations] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { addToCart, favorites, toggleFavorite } = useApp();
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    Promise.all([api<CatalogItem>(`/${kind}/${id}`), catalog("destinations")])
      .then(([entry, places]) => {
        if (cancelled) return;
        setItem(entry); setDestinations(places);
      })
      .catch((reason: Error) => { if (!cancelled) setError(reason.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id, kind]);
  if (loading) return <div className="page-container"><Loader variant="carousel" /></div>;
  if (!item) return <div className="page-container"><EmptyState title="This listing isn't available" detail={error || "Try exploring the collection for another option."} action={<Link to={`/${kind}`} className="button button-dark">Browse {kind}</Link>} /></div>;
  const destination = destinations.find((place) => place.id === item.destination_id);
  const image = imageFor(item, destinations, images, kind);
  const isSaved = favorites.has(`${kind}:${item.id}`);
  const kindLabel = { stays: "Stays", food: "Food", transport: "Transport", guides: "Guides" }[kind];
  const detail = kind === "stays" ? [item.kind, item.amenities?.join(" · ")].filter(Boolean).join(" · ")
    : kind === "food" ? [item.kind, item.cuisine, item.diet].filter(Boolean).join(" · ")
    : kind === "transport" ? [item.mode, item.operator, item.duration_min ? `${Math.floor(item.duration_min / 60)}h ${item.duration_min % 60}m` : ""].filter(Boolean).join(" · ")
    : [item.languages?.join(", "), item.specialties?.join(" · ")].filter(Boolean).join(" · ");
  return <div className="catalog-detail page-container">
    <Breadcrumbs trail={[{ label: kindLabel, to: `/${kind}` }, { label: item.name ?? item.operator ?? "Listing" }]} />
    <section className="catalog-detail-hero">
      <Image src={image} alt={item.name ?? item.operator ?? "Travel listing"} />
      <div className="catalog-detail-copy">
        <span className="eyebrow">{kind === "transport" ? item.mode ?? "A way to travel" : kind === "guides" ? "Local experience" : kind === "food" ? item.cuisine ?? "Local table" : item.kind ?? "A place to stay"}</span>
        <h1>{item.name ?? item.operator}</h1>
        <p className="catalog-detail-place">{destination?.name ?? "India"}{destination?.state ? `, ${destination.state}` : ""}</p>
        <p>{item.description || "A thoughtfully selected local option. Details and availability are confirmed by the provider."}</p>
        {detail && <p className="catalog-detail-facts">{detail}</p>}
        <div className="catalog-detail-action"><strong>{money(item.price_inr)}<small>{kind === "stays" ? " / night" : kind === "guides" ? " / day" : kind === "transport" ? " / seat" : " / two guests"}</small></strong><button className="button button-dark" onClick={() => addToCart(cartItemFor(kind, item, destinations))}>Add to trip plan <ShoppingBag size={16} /></button><FavoriteButton saved={isSaved} onToggle={() => toggleFavorite(kind, item.id)} label={isSaved ? "Remove from wishlist" : "Save to wishlist"} /></div>
      </div>
    </section>
    <div className="browse-footnote"><ShieldCheck size={16} /> This is a request, not a confirmed booking. Choose a date and time in your trip planner.</div>
  </div>;
}

function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const { user, signIn, register } = useApp();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const fields = new FormData(event.currentTarget);
    try {
      if (mode === "login") await signIn(String(fields.get("identifier")), String(fields.get("password")));
      else await register(String(fields.get("email")), String(fields.get("username")), String(fields.get("password")));
      navigate(searchParams.get("redirect") || "/trips", { replace: true });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to sign in."); }
    finally { setBusy(false); }
  }
  if (user) return <Navigate to={searchParams.get("redirect") || "/trips"} replace />;
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
  const location = useLocation();
  if (authLoading) return <div className="page-container"><Loader /></div>;
  // Remember where the user was heading so sign-in can return them here.
  return user ? children : <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname + location.search)}`} replace />;
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
    <div className="dashboard-welcome"><div><span className="eyebrow">YOUR TRAVEL DESK</span><h1>Good to see you, {name}.</h1><p>Your next somewhere is a few good choices away.</p></div><Link to="/booking" className="button button-dark"><Sparkles size={15} /> Plan a trip</Link></div>
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
  const { user, cart, updateCartItem, removeFromCart, clearCart } = useApp();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [coupon, setCoupon] = useState("");
  const [couponState, setCouponState] = useState<{ valid: boolean; discount: number; message: string } | null>(null);
  const now = new Date();
  const today = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
  const needsEndDate = (item: CartItem) => item.item_type === "stay" || item.item_type === "guide";
  const itemEstimate = (item: CartItem) => {
    const span = item.start_date && item.end_date ? daysBetween(item.start_date, item.end_date) : 0;
    const duration = item.item_type === "stay" ? Math.max(1, span) : item.item_type === "guide" ? Math.max(1, span + 1) : 1;
    return item.price * duration * item.quantity;
  };
  const scheduled = cart.map((item, index) => ({
    item, index,
    startMinute: item.start_time ? Number(item.start_time.slice(0, 2)) * 60 + Number(item.start_time.slice(3, 5)) : 0,
    endMinute: (item.start_time ? Number(item.start_time.slice(0, 2)) * 60 + Number(item.start_time.slice(3, 5)) : 0) + item.duration_min,
  }));
  const conflicts = new Set<number>();
  const farConflicts = new Set<number>();
  const stayWindows = scheduled.filter(({ item }) => item.item_type === "stay" && item.start_date && item.end_date)
    .map(({ item, index }) => ({ index, destination: item.destination_name ?? "", start: item.start_date as string, end: item.end_date as string }));
  for (let first = 0; first < scheduled.length; first += 1) {
    for (let second = first + 1; second < scheduled.length; second += 1) {
      const a = scheduled[first]; const b = scheduled[second];
      if (a.item.item_type !== "stay" && b.item.item_type !== "stay"
        && a.item.start_date && a.item.start_date === b.item.start_date
        && a.startMinute < b.endMinute && b.startMinute < a.endMinute) {
        conflicts.add(a.index); conflicts.add(b.index);
      }
    }
  }
  for (const { item, index } of scheduled) {
    if (item.item_type === "stay" || !item.start_date || !item.destination_name) continue;
    const stay = stayWindows.find((window) => window.index !== index
      && window.destination && window.destination !== item.destination_name
      && item.start_date! >= window.start && item.start_date! <= window.end);
    if (stay) farConflicts.add(index);
  }
  const subtotal = cart.reduce((sum, item) => sum + itemEstimate(item), 0);
  const discount = couponState?.valid ? Math.min(couponState.discount, subtotal) : 0;
  async function checkCoupon() {
    const code = coupon.trim();
    if (!code) { setCouponState(null); return; }
    try {
      const result = await api<{ valid: boolean; discount_inr: number; message: string }>("/offers/validate", {
        method: "POST", body: JSON.stringify({ code, subtotal_inr: subtotal }),
      });
      setCouponState({ valid: result.valid, discount: result.discount_inr, message: result.message });
    } catch (reason) {
      setCouponState({ valid: false, discount: 0, message: reason instanceof Error ? reason.message : "Unable to check that code." });
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    if (!user) { navigate("/login"); return; }
    if (cart.some((item) => !item.start_date || !item.start_time || !Number.isInteger(item.duration_min) || item.duration_min < 1 || !Number.isInteger(item.quantity) || item.quantity < 1)) {
      setError("Choose a date, start time, duration and quantity for every trip item."); return;
    }
    if (cart.some((item) => needsEndDate(item) && (!item.end_date || daysBetween(item.start_date, item.end_date) < (item.item_type === "stay" ? 1 : 0)))) {
      setError("Choose a valid end date for every stay and guide."); return;
    }
    if (conflicts.size) { setError("Resolve the overlapping timed activities in your itinerary before sending the request."); return; }
    setBusy(true);
    try {
      const items = cart.map((item) => ({
        item_type: item.item_type, item_id: item.item_id, quantity: item.quantity,
        start_date: item.start_date, end_date: needsEndDate(item) ? item.end_date : item.start_date,
        start_time: item.start_time, duration_min: item.duration_min,
      }));
      await api<Booking>("/bookings", { method: "POST", body: JSON.stringify({ items, coupon_code: coupon.trim() || null }) });
      clearCart(); navigate("/trips");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to send your request."); }
    finally { setBusy(false); }
  }
  return <div className="page-container booking-page"><PageIntro eyebrow="A good plan, taking shape" title="Review your trip." detail="Take a look before you send a request. Nothing is booked or charged until a provider confirms." />
    {!cart.length ? <EmptyState title="Your trip list is taking a little break" detail="Add a stay, a meal, a route or a local guide and they will be waiting here." action={<Link className="button button-dark" to="/destinations">Explore destinations</Link>} /> :
      <form className="checkout-layout" onSubmit={submit}><div className="checkout-list"><div className="checkout-list-head"><span>{cart.length} trip {cart.length === 1 ? "idea" : "ideas"}</span><Link to="/destinations">Keep exploring <ArrowRight size={15} /></Link></div>
        {cart.map((item, index) => <article className={`planner-item ${conflicts.has(index) || farConflicts.has(index) ? "planner-item-conflict" : ""}`} key={`${item.item_type}-${item.item_id}-${index}`}>
          <div className="planner-item-title"><span className="checkout-item-icon">{item.item_type === "transport" ? <Plane /> : item.item_type === "guide" ? <Compass /> : item.item_type === "food" ? <Heart /> : <ShoppingBag />}</span><div><small>{item.item_type}{item.destination_name ? ` · ${item.destination_name}` : ""}</small><strong>{item.name}</strong></div><strong>{money(itemEstimate(item))}</strong><button type="button" className="remove-button" aria-label={`Remove ${item.name}`} onClick={() => removeFromCart(index)}><X size={16} /></button></div>
          <div className="planner-item-fields">
            <label>{item.item_type === "stay" ? "Check-in" : "Date"}<input type="date" required min={today} value={item.start_date} onChange={(event) => updateCartItem(index, { start_date: event.target.value, ...(item.item_type !== "stay" && item.item_type !== "guide" ? { end_date: event.target.value } : {}) })} /></label>
            {needsEndDate(item) && <label>{item.item_type === "stay" ? "Check-out" : "Last day"}<input type="date" required min={item.start_date ? addCalendarDays(item.start_date, item.item_type === "stay" ? 1 : 0) : today} value={item.end_date} onChange={(event) => updateCartItem(index, { end_date: event.target.value })} /></label>}
            <label>{item.item_type === "stay" ? "Check-in time" : "Start time"}<input type="time" required value={item.start_time} onChange={(event) => updateCartItem(index, { start_time: event.target.value })} /></label>
            <label>Duration (minutes)<input type="number" required min="15" max="1440" step="15" value={item.duration_min} onChange={(event) => updateCartItem(index, { duration_min: Number(event.target.value) })} /></label>
            <label>{item.item_type === "transport" ? "Seats" : item.item_type === "food" ? "Guests" : "Quantity"}<input type="number" required min="1" max="20" step="1" value={item.quantity} onChange={(event) => updateCartItem(index, { quantity: Number(event.target.value) })} /></label>
          </div>
          {conflicts.has(index) && <p className="schedule-warning">This overlaps another timed activity. Adjust its time or duration.</p>}
          {farConflicts.has(index) && <p className="schedule-warning">Your stay is in another destination on this date. Move this {item.item_type} to a day that matches where you are sleeping, or change your stay.</p>}
        </article>)}
        <section className="planner-chart"><div className="planner-chart-head"><div><span className="eyebrow">YOUR DAYS, AT A GLANCE</span><h2>Trip schedule</h2></div><span>{cart.length} scheduled item{cart.length === 1 ? "" : "s"}</span></div>
          <ol className="planner-timeline">{[...scheduled].sort((a, b) => a.item.start_date.localeCompare(b.item.start_date) || a.startMinute - b.startMinute).map(({ item, index }) => <li className={conflicts.has(index) ? "timeline-conflict" : ""} key={`${item.item_type}-${item.item_id}-${index}`}><time>{item.start_date || "Choose a date"}<strong>{item.start_time || "Set time"}</strong></time><span className="timeline-track"><i style={{ width: `${Math.min(100, Math.max(15, item.duration_min / 14.4))}%` }} /></span><span className="timeline-copy"><strong>{item.name}</strong><small>{item.destination_name || item.item_type} · {Math.floor(item.duration_min / 60)}h {item.duration_min % 60}m</small></span></li>)}</ol>
          {(conflicts.size > 0 || farConflicts.size > 0) && <p className="schedule-warning">Some timed activities overlap or clash with your stay dates. Resolve these conflicts to continue.</p>}
        </section>
      </div><aside className="checkout-summary"><span className="eyebrow">YOUR REQUEST</span><h2>One thoughtful trip.</h2><div className="summary-line"><span>{cart.length} items</span><strong>{money(subtotal)}</strong></div>
        <div className="coupon-row"><input aria-label="Offer code" placeholder="Offer code e.g. WANDER10" value={coupon} onChange={(event) => { setCoupon(event.target.value); setCouponState(null); }} /><button type="button" className="button button-outline button-small" onClick={checkCoupon} disabled={!coupon.trim()}>Apply <Tag size={14} /></button></div>
        {couponState && <p className={`coupon-status ${couponState.valid ? "coupon-valid" : "coupon-invalid"}`} role="status">{couponState.valid ? `${couponState.message} You save ${money(Math.min(couponState.discount, subtotal))}.` : couponState.message}</p>}
        {discount > 0 && <div className="summary-line summary-discount"><span>Offer discount</span><strong>−{money(discount)}</strong></div>}
        <div className="summary-line summary-total"><span>Estimated total</span><strong>{money(Math.max(subtotal - discount, 0))}</strong></div><p>Stays are priced per night, guides per day, and food or transport by guest/seat. A provider confirms final pricing and availability.</p>{error && <p className="form-error">{error}</p>}<button className="button button-dark button-full" disabled={busy || conflicts.size > 0 || farConflicts.size > 0}>{busy ? <>Sending request… <span className="request-plane"><Plane size={15} /></span></> : <>Send booking request <ArrowRight size={16} /></>}</button><span className="safe-note"><ShieldCheck size={15} /> No payment is collected</span></aside></form>}
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

function NotFound() {
  return <div className="page-container"><EmptyState title="We took a wrong turn" detail="That page is not on this map, but there are plenty of lovely places to go next." action={<Link to="/" className="button button-dark">Back home</Link>} /></div>;
}

function WishlistPage() {
  const { user, favorites, toggleFavorite, addToCart } = useApp();
  const images = useImages();
  const [items, setItems] = useState<(CatalogItem & { catalogKind: Exclude<CatalogKind, "destinations"> })[]>([]);
  const [destinations, setDestinations] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(user ? true : false);
  useEffect(() => {
    if (!user || favorites.size === 0) { setItems([]); setLoading(false); return; }
    let cancelled = false;
    const wanted = [...favorites].map((key) => { const [kind, id] = key.split(":"); return { kind: kind as Exclude<CatalogKind, "destinations">, id: Number(id) }; });
    setLoading(true);
    Promise.all([catalog("destinations"), ...(["stays", "food", "transport", "guides"] as const).map((kind) => catalog(kind, { limit: "100" }).catch(() => []))])
      .then(([places, stays, food, transport, guides]) => {
        if (cancelled) return;
        setDestinations(places);
        const pools = { stays, food, transport, guides };
        const found = wanted.flatMap(({ kind, id }) => (pools[kind] as CatalogItem[]).filter((entry) => entry.id === id).map((entry) => ({ ...entry, catalogKind: kind })));
        setItems(found);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user, favorites]);
  return <div className="page-container wishlist-page"><PageIntro eyebrow="The little things you love" title="Your wishlist." detail="Tap the heart on any listing to keep it here. Move it into your trip plan whenever you're ready." />
    {loading ? <Loader label="Gathering your favourites…" variant="passport" /> : !user
      ? <EmptyState title="Sign in to keep favourites" detail="Your wishlist travels with your account." action={<Link to="/login" className="button button-dark">Sign in</Link>} />
      : items.length === 0
        ? <EmptyState title="Nothing saved just yet" detail="Tap the heart on any stay, meal, route or guide to keep it here for later." action={<Link to="/stays" className="button button-outline">Browse stays</Link>} />
        : <div className="catalog-grid">{items.map((item) => <CatalogCard key={`${item.catalogKind}-${item.id}`} item={item} kind={item.catalogKind} destinations={destinations} imageCatalog={images}
            saved={favorites.has(`${item.catalogKind}:${item.id}`)}
            onToggleFavorite={() => toggleFavorite(item.catalogKind, item.id)}
            onAdd={() => addToCart(cartItemFor(item.catalogKind, item, destinations))} />)}</div>}
  </div>;
}

export default function App() {
  return <Shell><Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/destinations" element={<BrowsePage kind="destinations" />} />
    <Route path="/destinations/:id" element={<DestinationPage />} />
    <Route path="/stays" element={<BrowsePage kind="stays" />} />
    <Route path="/stays/:id" element={<CatalogDetailPage kind="stays" />} />
    <Route path="/food" element={<BrowsePage kind="food" />} />
    <Route path="/food/:id" element={<CatalogDetailPage kind="food" />} />
    <Route path="/transport" element={<BrowsePage kind="transport" />} />
    <Route path="/transport/:id" element={<CatalogDetailPage kind="transport" />} />
    <Route path="/guides" element={<BrowsePage kind="guides" />} />
    <Route path="/guides/:id" element={<CatalogDetailPage kind="guides" />} />
    <Route path="/login" element={<AuthPage mode="login" />} />
    <Route path="/signup" element={<AuthPage mode="signup" />} />
    <Route path="/trips" element={<RequireAuth><TripsPage /></RequireAuth>} />
    <Route path="/dashboard" element={<RequireAuth><DashboardPage /></RequireAuth>} />
    <Route path="/booking" element={<BookingPage />} />
    <Route path="/itineraries" element={<RequireAuth><TripsPage /></RequireAuth>} />
    <Route path="/profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
    <Route path="/wishlist" element={<RequireAuth><WishlistPage /></RequireAuth>} />
    <Route path="/assistant" element={<Navigate to="/destinations" replace />} />
    <Route path="*" element={<NotFound />} />
  </Routes></Shell>;
}
