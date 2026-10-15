import { useEffect, useState } from "react";

export type User = {
  id: string;
  email: string;
  username: string;
  full_name: string | null;
};

export type CatalogKind = "destinations" | "stays" | "food" | "transport" | "guides";
export type ImageCatalog = {
  destinations: { id: string; name: string; image: string; thumb: string }[];
  stays: { image: string }[];
  food: { image: string }[];
};

export type CatalogItem = {
  id: number;
  name?: string;
  slug?: string;
  destination_id?: number;
  origin_id?: number;
  mode?: string;
  kind?: string;
  diet?: string;
  cuisine?: string;
  description?: string;
  tags?: string[];
  state?: string;
  country?: string;
  best_season?: string;
  climate?: string;
  avg_cost_inr?: number;
  price_inr?: number;
  rating?: number;
  amenities?: string[];
  operator?: string;
  duration_min?: number;
  seats_available?: number;
  languages?: string[];
  specialties?: string[];
};

export type Profile = {
  budget_range: string | null;
  travel_style: string | null;
  food_preferences: string[];
  dietary_restrictions: string[];
  accessibility_needs: string[];
  preferred_transport: string[];
  favorite_destinations: string[];
};

export type Offer = {
  id: number;
  code: string;
  title: string;
  description?: string | null;
  discount_percent?: number | null;
  discount_flat_inr?: number | null;
  module: "stays" | "food" | "transport" | "guides" | "any";
  min_amount_inr?: number | null;
  valid_till?: string | null;
  active: boolean;
};

export type Favorite = { item_type: Exclude<CatalogKind, "destinations">; item_id: number };

export type Lead = { id: number; name: string; phone: string };

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const TOKEN_KEY = "voyara_access_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(value: string | null) {
  if (value) localStorage.setItem(TOKEN_KEY, value);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}/api${path}`, { ...init, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : `Request failed (${response.status})`;
    // An expired session should sign the user out globally instead of surfacing
    // "Request failed (401)" on every page.
    if (response.status === 401 && getToken()) {
      setToken(null);
      window.dispatchEvent(new Event("voyara:unauthorized"));
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign(`/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`);
      }
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function catalog(kind: CatalogKind, params: Record<string, string> = {}) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== ""));
  return api<CatalogItem[]>(`/${kind}${query.size ? `?${query}` : ""}`);
}

export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function imageFor(item: CatalogItem, destinations: CatalogItem[], imageCatalog: ImageCatalog, kind?: CatalogKind) {
  if (kind === "stays" || kind === "food") {
    const assets = imageCatalog[kind];
    if (assets.length) return assets[Math.abs(item.id) % assets.length].image;
  }
  const destinationId = item.destination_id ?? item.id;
  const destination = destinations.find((entry) => entry.id === destinationId);
  const slug = destination?.slug;
  const bySlug = imageCatalog?.destinations?.find((entry: any) => entry.id === slug);
  if (!bySlug && slug === "munnar") {
    return imageCatalog.destinations.find((entry) => entry.id === "kerala")?.image ?? "";
  }
  const fallback = imageCatalog?.destinations?.[0];
  return bySlug?.image ?? fallback?.image ?? "";
}

export function srcSetFor(src: string) {
  if (!src) return undefined;
  return [400, 800, 1200, 1600]
    .map((width) => `${src.replace(/([?&]w=)\d+/, `$1${width}`)} ${width}w`)
    .join(", ");
}

export function money(value: number | undefined) {
  return `₹${(value ?? 0).toLocaleString("en-IN")}`;
}

export const emptyProfile: Profile = {
  budget_range: null,
  travel_style: null,
  food_preferences: [],
  dietary_restrictions: [],
  accessibility_needs: [],
  preferred_transport: [],
  favorite_destinations: [],
};
