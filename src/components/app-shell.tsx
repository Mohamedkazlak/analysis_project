import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { ChatPanel } from "./chat-panel";
import { navByRole, useRole } from "./role-context";
import type { UserAffiliation } from "@/lib/types";
import { clearAuthToken } from "@/lib/auth/token";
import {
  ROLE_SLUG,
  reportPath,
  roleRouteTo,
  rolesAllowedForPath,
} from "@/lib/auth/role-guards";
import { AnalyticsFilters } from "@/components/dashboard/analytics-filters";
import {
  useLocale,
  translateOrgName,
  translatePersonTitle,
  translateScopeLabel,
} from "@/lib/i18n";

const BRAND_LOGO = "/brand-logo.png";

function AffiliationParts({ affiliation }: { affiliation: UserAffiliation }) {
  const { locale, messages } = useLocale();
  if (!affiliation.sector && !affiliation.college) {
    return (
      <span className="text-ink-soft">
        {translateScopeLabel(affiliation.label, locale, messages.scope)}
      </span>
    );
  }
  return (
    <span className="text-ink-soft">
      {affiliation.sector && (
        <span>{translateOrgName(affiliation.sector, locale)}</span>
      )}
      {affiliation.sector && affiliation.college && (
        <span className="mx-1.5 text-ink-soft/50">·</span>
      )}
      {affiliation.college && (
        <span>{translateOrgName(affiliation.college, locale)}</span>
      )}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { role, user, displayRole, affiliation } = useRole();
  const {
    locale,
    messages,
    toggleLocale,
    tNavGroup,
    tNavLabel,
    tNavTitle,
    tRole,
  } = useLocale();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const groups = navByRole[role];
  const slug = ROLE_SLUG[role];
  const report = reportPath(pathname);
  const current = groups
    .flatMap((g) => g.items)
    .find((item) => (item.to === "/" ? report === "/" : item.to === report));
  const shownRole = messages.roles[role] ?? displayRole;

  // Deep-linking into another role's report sends the user to their own home.
  useEffect(() => {
    const allowed = rolesAllowedForPath(pathname);
    if (allowed && !allowed.includes(role)) {
      void navigate({
        to: "/$role",
        params: { role: ROLE_SLUG[role] },
        search: {},
      });
    }
  }, [navigate, pathname, role]);

  return (
    <div className="min-h-screen w-full text-ink">
      <div className="flex">
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col gap-1 border-e border-white/70 bg-white/55 px-5 py-6 backdrop-blur-2xl md:flex">
          <div className="mb-6 flex items-center gap-2.5">
            <img
              className="h-11 w-auto shrink-0 object-contain"
              src={BRAND_LOGO}
              alt="BNU logo"
            />
            <div>
              <div className="font-display text-sm font-bold leading-none">
                BNU
              </div>
              <div className="mt-1 text-[10px] font-semibold text-ink-soft">
                {messages.shell.brandSubtitle}
              </div>
            </div>
          </div>

          {groups.map((group) => (
            <div key={group.group} className="mb-2">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-soft">
                {tNavGroup(group.group)}
              </div>
              {group.items.map((item) => {
                const active =
                  item.to === "/" ? report === "/" : item.to === report;
                return (
                  <Link
                    key={item.to}
                    to={roleRouteTo(item.to)}
                    params={{ role: slug }}
                    search={{}}
                    className={cn(
                      "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-[13px] transition-colors",
                      active
                        ? "bg-iris/12 font-semibold text-iris"
                        : "font-medium text-ink-soft hover:bg-white/60 hover:text-ink",
                    )}
                  >
                    <span
                      className={cn(
                        "size-1.5 rounded-full",
                        active ? "bg-iris" : "bg-ink-soft/40",
                      )}
                    />
                    {tNavLabel(item.label)}
                  </Link>
                );
              })}
            </div>
          ))}

          <div className="mt-auto rounded-2xl border border-white/70 bg-white/60 p-3.5">
            <div className="flex items-center gap-2.5 rtl:flex-row-reverse">
              <div className="font-display grid size-9 shrink-0 place-items-center rounded-full bg-violet/15 text-[12px] font-bold text-plum">
                {user.initials}
              </div>
              <div className="min-w-0 flex-1 text-start">
                <div className="text-[12px] font-semibold leading-tight">
                  {translatePersonTitle(user.name, locale)}
                </div>
                <div className="mt-0.5 text-[10px] font-semibold text-iris">
                  {shownRole}
                </div>
                <div className="mt-0.5 truncate text-[10px] text-ink-soft">
                  <AffiliationParts affiliation={affiliation} />
                </div>
              </div>
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1 px-6 py-6 pb-28 lg:px-10">
          <div className="mb-4 flex items-center gap-2.5 md:hidden">
            <img
              className="h-9 w-auto shrink-0 object-contain"
              src={BRAND_LOGO}
              alt="BNU logo"
            />
            <div>
              <div className="font-display text-sm font-bold leading-none">
                BNU
              </div>
              <div className="mt-0.5 text-[10px] font-semibold text-ink-soft">
                {messages.shell.brandSubtitle}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] font-semibold uppercase tracking-[0.14em]">
                <span className="text-iris">{shownRole}</span>
                <span className="text-ink-soft/40" aria-hidden>
                  |
                </span>
                {!affiliation.sector && !affiliation.college ? (
                  <span className="text-ink-soft">
                    {translateScopeLabel(
                      affiliation.label,
                      locale,
                      messages.scope,
                    )}
                  </span>
                ) : (
                  <>
                    {affiliation.sector && (
                      <span className="text-ink-soft">
                        {translateOrgName(affiliation.sector, locale)}
                      </span>
                    )}
                    {affiliation.sector && affiliation.college && (
                      <span className="text-ink-soft/40" aria-hidden>
                        ·
                      </span>
                    )}
                    {affiliation.college && (
                      <span className="text-ink-soft">
                        {translateOrgName(affiliation.college, locale)}
                      </span>
                    )}
                  </>
                )}
              </div>
              <h1 className="font-display mt-1 text-2xl font-extrabold text-ink">
                {current ? tNavTitle(current.title) : messages.shell.reports}
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={toggleLocale}
                aria-label={
                  locale === "en"
                    ? messages.shell.switchToArabic
                    : messages.shell.switchToEnglish
                }
                className="rounded-full border border-white/80 bg-white/70 px-4 py-2 text-[12px] font-semibold text-iris backdrop-blur-xl hover:bg-white"
              >
                {locale === "en"
                  ? messages.shell.switchToArabic
                  : messages.shell.switchToEnglish}
              </button>
              <button
                onClick={() => {
                  clearAuthToken();
                  window.location.href = "/login";
                }}
                className="flex items-center gap-2 rounded-full border border-white/80 bg-white/70 px-4 py-2 text-[12px] font-semibold text-iris backdrop-blur-xl hover:bg-white"
              >
                {messages.shell.logOut}
              </button>
              {role !== "student" && (
                <button className="rounded-full bg-iris px-4 py-2 text-[12px] font-semibold text-white shadow-lg shadow-iris/25">
                  {messages.shell.exportReport}
                </button>
              )}
            </div>
          </div>

          <div className="mt-6 flex flex-col gap-6">
            {role !== "student" ? <AnalyticsFilters /> : null}
            <div key={pathname} className="rise-in flex flex-col gap-6">
              {children}
            </div>
          </div>

          <nav className="mt-8 flex flex-wrap gap-2 md:hidden">
            {groups
              .flatMap((g) => g.items)
              .map((item) => (
                <Link
                  key={item.to}
                  to={roleRouteTo(item.to)}
                  params={{ role: slug }}
                  search={{}}
                  className="rounded-full border border-white/80 bg-white/70 px-3 py-1.5 text-[12px] font-medium text-ink-soft"
                >
                  {tNavLabel(item.label)}
                </Link>
              ))}
          </nav>
        </main>
      </div>
      <ChatPanel />
    </div>
  );
}
