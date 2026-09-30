import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Locale, Messages } from "./types";
import en from "./messages/en";
import ar from "./messages/ar";

const STORAGE_KEY = "bnu.locale";
const catalogs: Record<Locale, Messages> = { en, ar };

function readStoredLocale(): Locale {
  if (typeof window === "undefined") return "en";
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === "ar" || raw === "en") return raw;
  } catch {
    /* ignore */
  }
  return "en";
}

function applyDocumentLocale(locale: Locale) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.lang = locale;
  root.dir = locale === "ar" ? "rtl" : "ltr";
  root.dataset["locale"] = locale;
}

interface LocaleContextValue {
  locale: Locale;
  messages: Messages;
  setLocale: (locale: Locale) => void;
  toggleLocale: () => void;
  tNavGroup: (group: string) => string;
  tNavLabel: (label: string) => string;
  tNavTitle: (title: string) => string;
  tRole: (role: string) => string;
}

const LocaleContext = createContext<LocaleContextValue>({
  locale: "en",
  messages: en,
  setLocale: () => {},
  toggleLocale: () => {},
  tNavGroup: (g) => g,
  tNavLabel: (l) => l,
  tNavTitle: (t) => t,
  tRole: (r) => r,
});

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => readStoredLocale());

  useEffect(() => {
    applyDocumentLocale(locale);
    try {
      window.localStorage.setItem(STORAGE_KEY, locale);
    } catch {
      /* ignore */
    }
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    window.location.reload();
  }, []);

  const toggleLocale = useCallback(() => {
    const next: Locale = locale === "en" ? "ar" : "en";
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    window.location.reload();
  }, [locale]);

  const messages = catalogs[locale];

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      messages,
      setLocale,
      toggleLocale,
      tNavGroup: (group) => messages.nav.groups[group] ?? group,
      tNavLabel: (label) => messages.nav.labels[label] ?? label,
      tNavTitle: (title) => messages.nav.titles[title] ?? title,
      tRole: (role) => messages.roles[role] ?? role,
    }),
    [locale, messages, setLocale, toggleLocale],
  );

  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale() {
  return useContext(LocaleContext);
}

export function speechLanguageForLocale(locale: Locale): "ar" | "en" {
  return locale === "ar" ? "ar" : "en";
}
