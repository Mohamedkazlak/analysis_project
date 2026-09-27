import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
  redirect,
  stripSearchParams,
} from "@tanstack/react-router";
import { type ReactNode } from "react";

import appCss from "../styles.css?url";
import { RoleProvider } from "@/components/role-context";
import { AnalyticsFilterProvider } from "@/components/dashboard/analytics-filter-context";
import { AppShell } from "@/components/app-shell";
import {
  ensureActiveRole,
  legacyRedirectTo,
  roleNavigateTarget,
} from "@/lib/auth/role-guards";
import { FILTER_SEARCH_DEFAULTS, fromSearchParams } from "@/lib/filter-types";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="glass-panel max-w-md p-8 text-center">
        <h1 className="font-display text-6xl font-extrabold text-ink">404</h1>
        <h2 className="font-display mt-4 text-xl font-bold text-ink">
          Report not found
        </h2>
        <p className="mt-2 text-sm text-ink-soft">
          This report doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-full bg-iris px-4 py-2 text-[12px] font-semibold text-white"
          >
            Back to overview
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="glass-panel max-w-md p-8 text-center">
        <h1 className="font-display text-xl font-bold text-ink">
          This report didn't load
        </h1>
        <p className="mt-2 text-sm text-ink-soft">
          Something went wrong while fetching the data.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="rounded-full bg-iris px-4 py-2 text-[12px] font-semibold text-white"
          >
            Try again
          </button>
          <a
            href="/"
            className="rounded-full border border-white/80 bg-white/70 px-4 py-2 text-[12px] font-semibold text-ink"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()(
  {
    validateSearch: (search: Record<string, unknown>) =>
      fromSearchParams(search),
    search: {
      middlewares: [stripSearchParams(FILTER_SEARCH_DEFAULTS)],
    },
    beforeLoad: async ({ location }) => {
      if (location.pathname === "/login") return;
      // localStorage is only available in the browser. Skip on SSR so a
      // successful login is not bounced back to /login during hydration.
      if (typeof window === "undefined") return;
      const role = await ensureActiveRole();
      if (!role) {
        throw redirect({ to: "/login" });
      }
      const dest = legacyRedirectTo(location.pathname, role);
      if (dest) {
        throw redirect({ ...roleNavigateTarget(dest), search: {} });
      }
    },
    head: () => ({
      meta: [
        { charSet: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { title: "BNU — AI-driven Dashboard" },
        {
          name: "description",
          content:
            "Assessment reporting and analytics for online testing programs.",
        },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
      links: [
        { rel: "stylesheet", href: appCss },
        { rel: "preconnect", href: "https://fonts.googleapis.com" },
        {
          rel: "preconnect",
          href: "https://fonts.gstatic.com",
          crossOrigin: "anonymous",
        },
        {
          rel: "stylesheet",
          href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap",
        },
        { rel: "icon", href: "/favicon.png", type: "image/png" },
      ],
    }),
    shellComponent: RootShell,
    component: RootComponent,
    notFoundComponent: NotFoundComponent,
    errorComponent: ErrorComponent,
  },
);

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();
  const router = useRouter();
  const isLogin = router.state.location.pathname === "/login";

  return (
    <QueryClientProvider client={queryClient}>
      <RoleProvider>
        <AnalyticsFilterProvider>
          {isLogin ? (
            <Outlet />
          ) : (
            <AppShell>
              {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
              <Outlet />
            </AppShell>
          )}
        </AnalyticsFilterProvider>
      </RoleProvider>
    </QueryClientProvider>
  );
}
