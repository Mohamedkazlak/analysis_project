import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter, useRouterState } from "@tanstack/react-router";
import type { Locale, Messages } from "./types";
import en from "./messages/en";
import ar from "./messages/ar";
import {
  localeFromPathname,
  readStoredLocale,
  swapLocaleInPath,
  writeStoredLocale,
} from "./locale-path";

const catalogs: Record<Locale, Messages> = { en, ar };

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

function resolveLocale(pathname: string): Locale {
  return localeFromPathname(pathname) ?? readStoredLocale();
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [locale, setLocaleState] = useState<Locale>(() =>
    typeof window === "undefined"
      ? "en"
      : resolveLocale(window.location.pathname),
  );

  // URL is the source of truth when /en or /ar is present.
  useEffect(() => {
    const fromPath = localeFromPathname(pathname);
    if (fromPath) {
      setLocaleState(fromPath);
    }
  }, [pathname]);

  useEffect(() => {
    applyDocumentLocale(locale);
    writeStoredLocale(locale);
  }, [locale]);

  const setLocale = useCallback(
    (next: Locale) => {
      writeStoredLocale(next);
      const target = swapLocaleInPath(pathname, next);
      if (target === pathname) {
        setLocaleState(next);
        return;
      }
      router.history.push(target);
    },
    [pathname, router],
  );

  const toggleLocale = useCallback(() => {
    setLocale(locale === "en" ? "ar" : "en");
  }, [locale, setLocale]);

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
