import { createFileRoute, redirect } from "@tanstack/react-router";
import { ensureActiveRole, ROLE_SLUG } from "@/lib/auth/role-guards";
import { readStoredLocale } from "@/lib/i18n/locale-path";

export const Route = createFileRoute("/")({
  beforeLoad: async () => {
    const locale = readStoredLocale();
    if (typeof window === "undefined") {
      throw redirect({
        to: "/$locale/login",
        params: { locale },
      });
    }
    const role = await ensureActiveRole();
    if (!role) {
      throw redirect({
        to: "/$locale/login",
        params: { locale },
      });
    }
    throw redirect({
      to: "/$locale/$role",
      params: { locale, role: ROLE_SLUG[role] },
    });
  },
  component: () => null,
});
