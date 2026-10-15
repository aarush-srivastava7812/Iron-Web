import { ArrowRight, Check, Compass, Globe2, Heart, Luggage, MapPin, Plane, Star } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { imageFor, money, srcSetFor, type CatalogItem, type CatalogKind, type ImageCatalog } from "./api";

export function Loader({ label = "Finding your somewhere…", variant = "compass" }: { label?: string; variant?: "compass" | "globe" | "suitcase" | "runway" | "passport" | "carousel" }) {
  const art = {
    compass: <Compass size={24} />,
    globe: <Globe2 size={25} />,
    suitcase: <><Luggage size={24} /><i /><i /></>,
    runway: <Plane size={25} />,
    passport: <span className="passport-stamp"><Check size={16} /></span>,
    carousel: <><span className="carousel-track" /><Luggage size={20} /></>,
  }[variant];
  return <div className={`loading-state loader-${variant}`} role="status" aria-live="polite"><span className="loader-art">{art}</span><span>{label}</span><span className="loader-progress"><i /></span></div>;
}

export function Image({ src, alt, className = "", priority = false }: { src: string; alt: string; className?: string; priority?: boolean }) {
  return <img className={className} src={src} srcSet={srcSetFor(src)} sizes="(max-width: 700px) 100vw, 33vw" loading={priority ? "eager" : "lazy"} fetchPriority={priority ? "high" : undefined} alt={alt} onError={(event) => { event.currentTarget.onerror = null; event.currentTarget.srcset = ""; event.currentTarget.sizes = ""; event.currentTarget.src = src.replace(/([?&]w=)\d+/, "$1" + "400"); }} />;
}

export function FavoriteButton({ saved, onToggle, label }: { saved: boolean; onToggle: () => void; label: string }) {
  return <button
    type="button"
    className={`favorite-button ${saved ? "favorite-saved" : ""}`}
    aria-pressed={saved}
    aria-label={label}
    onClick={(event) => { event.preventDefault(); event.stopPropagation(); onToggle(); }}
  ><Heart size={15} fill={saved ? "currentColor" : "none"} /></button>;
}

export function CatalogCard({ item, kind, destinations, imageCatalog, onAdd, saved, onToggleFavorite }: {
  item: CatalogItem; kind: CatalogKind;
  destinations: CatalogItem[]; imageCatalog: ImageCatalog; onAdd?: () => void;
  saved?: boolean; onToggleFavorite?: () => void;
}) {
  const isDestination = kind === "destinations";
  const placeName = isDestination ? item.name : destinations.find((entry) => entry.id === item.destination_id)?.name;
  const image = imageFor(item, destinations, imageCatalog, kind);
  const subtitle = isDestination
    ? [item.state, item.country].filter(Boolean).join(", ")
    : kind === "transport" ? `${item.mode ?? "Route"} · ${Math.round((item.duration_min ?? 0) / 60)}h`
    : kind === "guides" ? `${item.languages?.join(", ") ?? "Local guide"} · ${item.specialties?.join(" · ") ?? ""}`
    : [item.kind, item.cuisine, item.diet].filter(Boolean).join(" · ");
  const price = kind === "destinations" ? item.avg_cost_inr : item.price_inr;
  const destinationPath = `/${kind}/${item.id}`;
  return <article className="catalog-card">
    <Link className="catalog-image" to={destinationPath}>
      <Image src={image} alt={placeName ?? item.name ?? "Travel listing"} />
      {item.rating ? <span className="rating"><Star size={13} fill="currentColor" /> {item.rating.toFixed(1)}</span> : null}
    </Link>
    {kind !== "destinations" && onToggleFavorite
      ? <div className="catalog-favorite"><FavoriteButton saved={Boolean(saved)} onToggle={onToggleFavorite} label={saved ? `Remove ${item.name ?? "listing"} from wishlist` : `Save ${item.name ?? "listing"} to wishlist`} /></div>
      : null}
    <div className="catalog-card-body">
      <div className="card-location"><MapPin size={13} /> {placeName || item.operator || "Voyara local partner"}</div>
      <h3>{item.name ?? item.operator ?? "Local experience"}</h3>
      <p>{item.description || subtitle || item.amenities?.join(" · ") || "A thoughtfully selected local experience."}</p>
      <div className="card-bottom">
        <span className="card-price"><strong>{money(price)}</strong><small>{kind === "stays" ? " / night" : kind === "guides" ? " / day" : kind === "food" ? " / guest" : kind === "transport" ? " / seat" : " average trip"}</small></span>
        {isDestination ? <Link className="round-link" to={destinationPath} aria-label={`Explore ${item.name}`}><ArrowRight size={17} /></Link>
          : <button className="button button-small button-outline" onClick={onAdd}>Add to trip</button>}
      </div>
    </div>
  </article>;
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return <div className="empty-state"><span className="empty-icon"><Compass size={24} /></span><h3>{title}</h3><p>{detail}</p>{action}</div>;
}
