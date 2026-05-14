"use client";

import { User } from "@/types";

export function saveToken(token: string) {
  localStorage.setItem("procura_token", token);
}

export function clearToken() {
  localStorage.removeItem("procura_token");
  localStorage.removeItem("procura_user");
}

export function saveUser(user: User) {
  localStorage.setItem("procura_user", JSON.stringify(user));
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("procura_user");
  return raw ? JSON.parse(raw) : null;
}

export function isAuthenticated(): boolean {
  return Boolean(localStorage.getItem("procura_token"));
}
