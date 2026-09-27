import { parseJwt } from "./parse-jwt";
import type { Role } from "../types";

export const AUTH_TOKEN_KEY = "token";
export const AUTH_COOKIE_NAME = "bnu_token";
const SESSION_ROLE_KEY = "bnu_session_role";
const TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60;

const ROLES = new Set<Role>([
  "senior_management",
  "program_director",
  "academic_affairs",
  "professor",
  "it_academic_integrity",
  "student",
]);

function readCookie(source: string, name: string): string | null {
  const parts = source.split(";").map((p) => p.trim());
  const match = parts.find((p) => p.startsWith(`${name}=`));
  if (!match) return null;
  return decodeURIComponent(match.slice(name.length + 1)) || null;
}

export function getAuthToken(): string | null {
  if (typeof window !== "undefined") {
    try {
      const stored = window.localStorage.getItem(AUTH_TOKEN_KEY);
      if (stored) return stored;
    } catch {
      /* ignore */
    }
    return readCookie(document.cookie, AUTH_COOKIE_NAME);
  }
  return null;
}

export function setAuthToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
  document.cookie = `${AUTH_COOKIE_NAME}=${encodeURIComponent(token)}; path=/; max-age=${TOKEN_MAX_AGE_SECONDS}; SameSite=Lax`;
}

export function clearAuthToken() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(SESSION_ROLE_KEY);
  document.cookie = `${AUTH_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
}

/** UI route hint from the last live /auth/me response. Not an authorization claim. */
export function rememberSessionRole(userId: string, role: string) {
  if (typeof window === "undefined") return;
  if (!userId || !ROLES.has(role as Role)) return;
  window.localStorage.setItem(
    SESSION_ROLE_KEY,
    JSON.stringify({ user_id: userId, role }),
  );
}

export function sessionRoleForToken(token: string | null): Role | null {
  const userId = userIdFromToken(token);
  if (!userId || typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SESSION_ROLE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { user_id?: string; role?: string };
    if (
      parsed.user_id !== userId ||
      !parsed.role ||
      !ROLES.has(parsed.role as Role)
    ) {
      return null;
    }
    return parsed.role as Role;
  } catch {
    return null;
  }
}

export function roleFromToken(token: string | null): Role | null {
  if (!token) return null;
  const payload = parseJwt(token);
  return (payload?.role as Role | undefined) ?? null;
}

export function userIdFromToken(token: string | null): string | null {
  if (!token) return null;
  const payload = parseJwt(token);
  return (payload?.user_id as string | undefined) ?? null;
}

export function scopeIdFromToken(token: string | null): string | null {
  if (!token) return null;
  const payload = parseJwt(token);
  return (payload?.scope_id as string | undefined) ?? null;
}

export function studentIdFromToken(token: string | null): string | null {
  if (!token) return null;
  const payload = parseJwt(token);
  return (payload?.student_id as string | undefined) ?? null;
}
