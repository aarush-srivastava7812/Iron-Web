import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, getToken, setToken, type User } from "./api";

export type CartItem = { item_type: "stay" | "food" | "transport" | "guide"; item_id: number; name: string; price: number };
type AppState = {
  user: User | null;
  authLoading: boolean;
  cart: CartItem[];
  signIn: (identifier: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  signOut: () => void;
  addToCart: (item: CartItem) => void;
  removeFromCart: (index: number) => void;
  clearCart: () => void;
};
const State = createContext<AppState | null>(null);
const CART_KEY = "voyara_trip_request";

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(Boolean(getToken()));
  const [cart, setCart] = useState<CartItem[]>(() => {
    try { return JSON.parse(localStorage.getItem(CART_KEY) ?? "[]") as CartItem[]; }
    catch { return []; }
  });

  useEffect(() => {
    if (!getToken()) return;
    api<User>("/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setAuthLoading(false));
  }, []);
  useEffect(() => localStorage.setItem(CART_KEY, JSON.stringify(cart)), [cart]);

  const value = useMemo<AppState>(() => ({
    user,
    authLoading,
    cart,
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
    addToCart(item) { setCart((current) => [...current, item]); },
    removeFromCart(index) { setCart((current) => current.filter((_, itemIndex) => itemIndex !== index)); },
    clearCart() { setCart([]); },
  }), [user, authLoading, cart]);

  return <State.Provider value={value}>{children}</State.Provider>;
}

export function useApp() {
  const value = useContext(State);
  if (!value) throw new Error("useApp must be used inside AppProvider");
  return value;
}
