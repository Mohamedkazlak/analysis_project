import { useLayoutEffect } from "react";
import {
  Outlet,
  createFileRoute,
  redirect,
  useNavigate,
  useRouterState,
} from "@tanstack/react-router";
import {
  ROLE_SLUG,
  SLUG_ROLE,
  ensureActiveRole,
  getActiveDemoRole,
  legacyRedirectTo,
  roleHome,
  roleNavigateTarget,
} from "@/lib/auth/role-guards";
import {
  isLocale,
  loginPath,
  readStoredLocale,
  stripLocalePrefix,
} from "@/lib/i18n/locale-path";

export const Route = createFileRoute("/$locale/$role")({
  beforeLoad: async ({ params, location }) => {
    if (typeof window === "undefined") return;
    const stored = readStoredLocale();

    // Unprefixed /{role}/{leaf} mis-parsed as /$locale/$role
    if (!isLocale(params.locale) && SLUG_ROLE[params.locale]) {
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

    const locale = isLocale(params.locale) ? params.locale : stored;
    if (!isLocale(params.locale)) {
      throw redirect({
        ...roleNavigateTarget(location.pathname, locale),
        search: {},
      });
    }

    const role = await ensureActiveRole();
    if (!role) {
      throw redirect({
        to: "/$locale/login",
        params: { locale },
      });
    }
    const dest = legacyRedirectTo(location.pathname, role, locale);
    if (dest) {
      throw redirect({ ...roleNavigateTarget(dest, locale), search: {} });
    }
    const slugRole = SLUG_ROLE[params.role];
    if (!slugRole) {
      throw redirect({
        to: "/$locale/$role",
        params: { locale, role: ROLE_SLUG[role] },
        search: {},
      });
    }
    if (slugRole !== role) {
      const rest = stripLocalePrefix(location.pathname).slice(
        `/${params.role}`.length,
      );
      throw redirect({
        ...roleNavigateTarget(`${roleHome(role, locale)}${rest}`, locale),
        search: {},
      });
    }
  },
  component: RoleLayout,
});

function RoleLayout() {
  const { locale: localeParam, role: slug } = Route.useParams();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  useLayoutEffect(() => {
    const locale = isLocale(localeParam) ? localeParam : readStoredLocale();
    const role = getActiveDemoRole();
    if (!role) {
      window.location.href = loginPath(locale);
      return;
    }
    if (!isLocale(localeParam) && SLUG_ROLE[localeParam]) {
      void navigate({
        ...roleNavigateTarget(pathname, locale),
        search: {},
        replace: true,
      });
      return;
    }
    const dest = legacyRedirectTo(pathname, role, locale);
    if (dest) {
      void navigate({
        ...roleNavigateTarget(dest, locale),
        search: {},
        replace: true,
      });
      return;
    }
    const slugRole = SLUG_ROLE[slug];
    if (!slugRole) {
      void navigate({
        to: "/$locale/$role",
        params: { locale, role: ROLE_SLUG[role] },
        search: {},
        replace: true,
      });
      return;
    }
    if (slugRole !== role) {
      const rest = stripLocalePrefix(pathname).slice(`/${slug}`.length);
      void navigate({
        ...roleNavigateTarget(`${roleHome(role, locale)}${rest}`, locale),
        search: {},
        replace: true,
      });
    }
  }, [localeParam, navigate, pathname, slug]);

  return <Outlet />;
}
