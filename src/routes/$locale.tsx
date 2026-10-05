import { Outlet, createFileRoute, redirect } from "@tanstack/react-router";
import {
  ROLE_SLUG,
  SLUG_ROLE,
  ensureActiveRole,
  roleNavigateTarget,
} from "@/lib/auth/role-guards";
import { isLocale, readStoredLocale } from "@/lib/i18n/locale-path";

export const Route = createFileRoute("/$locale")({
  beforeLoad: async ({ params, location }) => {
    const stored = readStoredLocale();

    if (!isLocale(params.locale)) {
      // Unprefixed role home matched as /$locale, e.g. /senior-management
      if (SLUG_ROLE[params.locale]) {
        if (typeof window === "undefined") {
          throw redirect({
            to: "/$locale/$role",
            params: { locale: stored, role: params.locale },
          });
        }
        const role = await ensureActiveRole();
        if (!role) {
          throw redirect({
            to: "/$locale/login",
            params: { locale: stored },
          });
        }
        throw redirect({
          ...roleNavigateTarget(location.pathname, stored),
          search: {},
        });
      }

      throw redirect({
        to: "/$locale/login",
        params: { locale: stored },
      });
    }

    // Bare /en or /ar → role home or login
    const parts = location.pathname.split("/").filter(Boolean);
    if (parts.length === 1) {
      if (typeof window === "undefined") {
        throw redirect({
          to: "/$locale/login",
          params: { locale: params.locale },
        });
      }
      const role = await ensureActiveRole();
      if (!role) {
        throw redirect({
          to: "/$locale/login",
          params: { locale: params.locale },
        });
      }
      throw redirect({
        to: "/$locale/$role",
        params: { locale: params.locale, role: ROLE_SLUG[role] },
        search: {},
      });
    }
  },
  component: LocaleLayout,
});

function LocaleLayout() {
  return <Outlet />;
}
