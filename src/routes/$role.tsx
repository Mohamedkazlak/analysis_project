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

export const Route = createFileRoute("/$role")({
  beforeLoad: async ({ params, location }) => {
    if (typeof window === "undefined") return;
    const role = await ensureActiveRole();
    if (!role) {
      throw redirect({ to: "/login" });
    }
    const dest = legacyRedirectTo(location.pathname, role);
    if (dest) {
      throw redirect({ ...roleNavigateTarget(dest), search: {} });
    }
    const slugRole = SLUG_ROLE[params.role];
    if (!slugRole) {
      throw redirect({
        to: "/$role",
        params: { role: ROLE_SLUG[role] },
        search: {},
      });
    }
    if (slugRole !== role) {
      const rest = location.pathname.slice(`/${params.role}`.length);
      throw redirect({
        ...roleNavigateTarget(`${roleHome(role)}${rest}`),
        search: {},
      });
    }
  },
  component: RoleLayout,
});

function RoleLayout() {
  const { role: slug } = Route.useParams();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  useLayoutEffect(() => {
    const role = getActiveDemoRole();
    if (!role) {
      window.location.href = "/login";
      return;
    }
    const dest = legacyRedirectTo(pathname, role);
    if (dest) {
      void navigate({ ...roleNavigateTarget(dest), search: {}, replace: true });
      return;
    }
    const slugRole = SLUG_ROLE[slug];
    if (!slugRole) {
      void navigate({
        to: "/$role",
        params: { role: ROLE_SLUG[role] },
        search: {},
        replace: true,
      });
      return;
    }
    if (slugRole !== role) {
      const rest = pathname.slice(`/${slug}`.length);
      void navigate({
        ...roleNavigateTarget(`${roleHome(role)}${rest}`),
        search: {},
        replace: true,
      });
    }
  }, [navigate, pathname, slug]);

  return <Outlet />;
}
