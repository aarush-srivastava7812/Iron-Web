import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, catalog, getToken, setToken, type CatalogItem, type CatalogKind, type User } from "./api";

export type CartItem = {
  item_type: "stay" | "food" | "transport" | "guide";
  item_id: number;
  name: string;
  price: number;
  destination_id?: number;
  destination_name?: string;
  start_date: string;
  end_date: string;
  start_time: string;
  duration_min: number;
  quantity: number;
};
export type NewCartItem = Pick<CartItem, "item_type" | "item_id" | "name" | "price"> & Partial<Omit<CartItem, "item_type" | "item_id" | "name" | "price">>;
type AppState = {
  user: User | null;
  authLoading: boolean;
  cart: CartItem[];
  favorites: Set<string>;
  toggleFavorite: (itemType: Exclude<CatalogKind, "destinations">, itemId: number) => void;
  signIn: (identifier: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  signOut: () => void;
  addToCart: (item: NewCartItem) => void;
  updateCartItem: (index: number, changes: Partial<NewCartItem>) => void;
  removeFromCart: (index: number) => void;
  clearCart: () => void;
};
const State = createContext<AppState | null>(null);
const CART_KEY = "voyara_trip_request";

function normalizeCart(items: Partial<CartItem>[]): CartItem[] {
  return items.filter((item): item is Partial<CartItem> & Pick<CartItem, "item_type" | "item_id" | "name" | "price"> =>
    Boolean(item && item.item_type && Number.isInteger(item.item_id) && item.name && Number.isFinite(item.price)))
    .map((item) => ({
      ...item,
      start_date: item.start_date ?? "",
      end_date: item.end_date ?? "",
      start_time: item.start_time ?? (item.item_type === "stay" ? "15:00" : item.item_type === "food" ? "19:00" : item.item_type === "transport" ? "08:00" : "10:00"),
      duration_min: item.duration_min ?? (item.item_type === "transport" ? 60 : item.item_type === "food" ? 90 : 180),
      quantity: item.quantity ?? 1,
    }));
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(Boolean(getToken()));
  const [cart, setCart] = useState<CartItem[]>(() => {
    try { return normalizeCart(JSON.parse(localStorage.getItem(CART_KEY) ?? "[]") as Partial<CartItem>[]); }
    catch { return []; }
  });

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setAuthLoading(false));
  }, []);
  useEffect(() => {
    // api() clears the stored token on any 401; mirror that in React state.
    const signOut = () => { setUser(null); setAuthLoading(false); };
    window.addEventListener("voyara:unauthorized", signOut);
    return () => window.removeEventListener("voyara:unauthorized", signOut);
  }, []);
  useEffect(() => localStorage.setItem(CART_KEY, JSON.stringify(cart)), [cart]);

  // Validate the persisted cart against the live catalog so stale items
  // (deleted listings, other-account leftovers) disappear gracefully.
  const cartValidated = useRef(false);
  useEffect(() => {
    if (cartValidated.current || cart.length === 0) return;
    cartValidated.current = true;
    const kinds = [...new Set(cart.map((item) => (item.item_type === "stay" ? "stays" : item.item_type === "guide" ? "guides" : item.item_type) as CatalogKind))];
    Promise.all(kinds.map((kind) => catalog(kind, { limit: "100" }).catch(() => [] as CatalogItem[])))
      .then((results) => {
        const validIds = new Map<CatalogKind, Set<number>>(kinds.map((kind, index) => [kind, new Set(results[index].map((item) => item.id))]));
        setCart((current) => current.filter((item) => {
          const kind = item.item_type === "stay" ? "stays" : item.item_type === "guide" ? "guides" : item.item_type;
          return validIds.get(kind as CatalogKind)?.has(item.item_id);
        }));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const favoriteKey = (itemType: string, itemId: number) => `${itemType}:${itemId}`;

  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (!user) { setFavorites(new Set()); return; }
    api<{ item_type: string; item_id: number }[]>("/favorites")
      .then((rows) => setFavorites(new Set(rows.map((row) => favoriteKey(row.item_type, row.item_id)))))
      .catch(() => setFavorites(new Set()));
  }, [user]);

  const value = useMemo<AppState>(() => ({
    user,
    authLoading,
    cart,
    favorites,
    toggleFavorite(itemType, itemId) {
      const key = favoriteKey(itemType, itemId);
      const isSaved = favorites.has(key);
      setFavorites((current) => {
        const next = new Set(current);
        if (isSaved) next.delete(key); else next.add(key);
        return next;
      });
      if (isSaved) {
        api(`/favorites/${itemType}/${itemId}`, { method: "DELETE" }).catch(() => {
          setFavorites((current) => new Set(current).add(key));
        });
      } else {
        api("/favorites", { method: "POST", body: JSON.stringify({ item_type: itemType, item_id: itemId }) }).catch(() => {
          setFavorites((current) => { const next = new Set(current); next.delete(key); return next; });
        });
      }
    },
    async signIn(identifier, password) {
      const result = await api<{ access_token: string; user: User }>("/auth/login", {
        method: "POST", body: JSON.stringify({ identifier, password }),
      });
      setToken(result.access_token); setUser(result.user); setAuthLoading(false);
    },
    async register(email, username, password) {
      const result = await api<{ access_token: string; user: User }>("/auth/register", {
        method: "POST", body: JSON.stringify({ email, username, password }),
      });
      setToken(result.access_token); setUser(result.user); setAuthLoading(false);
    },
    signOut() { setToken(null); setUser(null); },
    addToCart(item) {
      setCart((current) => {
        const [prepared] = normalizeCart([item]);
        // Merge into an existing entry for the same listing with the same
        // schedule instead of adding a duplicate row.
        const mergeable = (existing: CartItem) =>
          existing.item_type === prepared.item_type && existing.item_id === prepared.item_id
          && existing.start_date === prepared.start_date && existing.end_date === prepared.end_date
          && existing.start_time === prepared.start_time && existing.duration_min === prepared.duration_min;
        const index = current.findIndex(mergeable);
        if (index === -1) return [...current, ...normalizeCart([item])];
        return current.map((existing, position) => position === index
          ? { ...existing, quantity: Math.min(existing.quantity + prepared.quantity, 20) } : existing);
      });
    },
    updateCartItem(index, changes) {
      setCart((current) => current.map((item, itemIndex) => itemIndex === index
        ? normalizeCart([{ ...item, ...changes }])[0] ?? item
        : item));
    },
    removeFromCart(index) { setCart((current) => current.filter((_, itemIndex) => itemIndex !== index)); },
    clearCart() { setCart([]); },
  }), [user, authLoading, cart, favorites]);

  return <State.Provider value={value}>{children}</State.Provider>;
}

export function useApp() {
  const value = useContext(State);
  if (!value) throw new Error("useApp must be used inside AppProvider");
  return value;
}
