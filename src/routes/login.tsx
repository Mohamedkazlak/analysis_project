import { createFileRoute, redirect } from "@tanstack/react-router";
import { readStoredLocale } from "@/lib/i18n/locale-path";

/** Bare /login → /{locale}/login */
export const Route = createFileRoute("/login")({
  beforeLoad: () => {
    throw redirect({
      to: "/$locale/login",
      params: { locale: readStoredLocale() },
    });
  },
  component: () => null,
});
