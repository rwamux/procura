"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { User } from "@/types";
import { getStoredUser, clearToken } from "@/lib/auth";
import { api } from "@/lib/api";

interface AuthContext {
  user: User | null;
  setUser: (user: User | null) => void;
  logout: () => void;
  loading: boolean;
}

const AuthCtx = createContext<AuthContext>({
  user: null,
  setUser: () => {},
  logout: () => {},
  loading: true,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = getStoredUser();
    if (stored) {
      setUserState(stored);
      setLoading(false);
    } else {
      api.auth.me()
        .then((u) => setUserState(u as User))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, []);

  const setUser = (u: User | null) => {
    setUserState(u);
    if (u) {
      localStorage.setItem("procura_user", JSON.stringify(u));
    }
  };

  const logout = () => {
    clearToken();
    setUserState(null);
    window.location.href = "/login";
  };

  return <AuthCtx.Provider value={{ user, setUser, logout, loading }}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  return useContext(AuthCtx);
}
