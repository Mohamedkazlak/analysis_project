import type { Locale } from "./types";

export const LOCALE_SLUGS = ["en", "ar"] as const;
export const STORAGE_KEY = "bnu.locale";

export function isLocale(value: string | null | undefined): value is Locale {
  return value === "en" || value === "ar";
}

export function normalizeLocale(value: string | null | undefined): Locale {
  return value === "ar" ? "ar" : "en";
}

export function readStoredLocale(): Locale {
  if (typeof window === "undefined") return "en";
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (isLocale(raw)) return raw;
  } catch {
    /* ignore */
  }
  return "en";
}

export function writeStoredLocale(locale: Locale) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    /* ignore */
  }
}

export function localeFromPathname(pathname: string): Locale | null {
  const first = pathname.split("/").filter(Boolean)[0];
  return isLocale(first) ? first : null;
}

/** Strip a leading /en or /ar segment. */
export function stripLocalePrefix(pathname: string): string {
  const parts = pathname.split("/").filter(Boolean);
  if (parts[0] && isLocale(parts[0])) {
    const rest = parts.slice(1).join("/");
    return rest ? `/${rest}` : "/";
  }
  return pathname || "/";
}

/** Ensure pathname starts with /{locale}. */
export function withLocalePrefix(pathname: string, locale: Locale): string {
  const stripped = stripLocalePrefix(pathname);
  if (!stripped || stripped === "/") return `/${locale}`;
  return `/${locale}${stripped.startsWith("/") ? stripped : `/${stripped}`}`;
}

export function swapLocaleInPath(pathname: string, next: Locale): string {
  return withLocalePrefix(pathname, next);
}

export function loginPath(locale: Locale = readStoredLocale()): string {
  return `/${locale}/login`;
}

export function isLoginPath(pathname: string): boolean {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 1 && parts[0] === "login") return true;
  return parts.length === 2 && isLocale(parts[0]) && parts[1] === "login";
}
