import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Sparkles } from "lucide-react";
import { getStudentDirectory } from "@/lib/api";
import { AiDecisionSection } from "@/components/ai-insights";
import { openChat } from "@/lib/chat-bus";
import { useRole } from "@/components/role-context";
import {
  Badge,
  FilterBar,
  Meter,
  Panel,
  ScreenSkeleton,
  SearchInput,
  Select,
  StatBlock,
  TableShell,
  Th,
} from "@/components/dashboard/dashboard-ui";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { ScopeBanner } from "@/components/dashboard/scope-banner";
import { useLocale, translateOrgName, translateStanding } from "@/lib/i18n";
import { roleGuard } from "@/lib/auth/role-guards";

export const Route = createFileRoute("/$locale/$role/students/")({
  beforeLoad: roleGuard("/students"),
  head: () => ({
    meta: [
      { title: "Student Profiles — BNU" },
      {
        name: "description",
        content:
          "Browse every student's academic record, yearly averages and standing across academic years.",
      },
      { property: "og:title", content: "Student Profiles — BNU" },
      {
        property: "og:description",
        content:
          "Browse every student's academic record, yearly averages and standing across academic years.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: StudentDirectory,
});

/**
 * PERMISSION GATE — runs before any student record is requested.
 * Only Senior Management and Faculty may read named student records.
 * The same check runs in FastAPI and in the row-level policy.
 */
function StudentDirectory() {
  const { locale: localeParam, role: roleParam } = Route.useParams();
  const { role } = useRole();
  const { locale, messages } = useLocale();
  const c = messages.common;
  const sp = messages.studentsPage;
  const allowed =
    role === "senior_management" ||
    role === "program_director" ||
    role === "academic_affairs" ||
    role === "professor";
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("student-directory");
  const { data, isPending } = useQuery({
    queryKey,
    queryFn: () => getStudentDirectory(filters),
    enabled: allowed && enabled,
  });
  const [query, setQuery] = useState("");
  const [standing, setStanding] = useState("all");

  if (!allowed) {
    return (
      <Panel title={c.restricted}>
        <p className="text-[13px] text-ink-soft">
          Individual student records are available to Senior Management, Program
          Directors, Academic Affairs and Professors.
        </p>
      </Panel>
    );
  }

  if (!filtersReady) return <FiltersRequiredNotice />;
  if (isPending || !data) return <ScreenSkeleton cards={4} panels={2} />;

  const standings = Array.from(new Set(data.map((r) => r.standing)));
  const rows = data.filter(
    (r) =>
      (standing === "all" || r.standing === standing) &&
      (r.name.toLowerCase().includes(query.trim().toLowerCase()) ||
        r.program.toLowerCase().includes(query.trim().toLowerCase())),
  );

  const atRisk = data.filter(
    (r) => r.standing === "At risk" || r.standing === "Watch list",
  ).length;
  const improving = data.filter((r) => r.trend > 0).length;

  return (
    <>
      <ScopeBanner />
      <AiDecisionSection page="students" />

      <div className="flex justify-end">
        <button
          onClick={() =>
            openChat({
              context: "Ask about the directory",
              question: "Which students need attention right now?",
            })
          }
          className="inline-flex items-center gap-1.5 rounded-full border border-ai/40 bg-white/70 px-3.5 py-1.5 text-[12px] font-semibold text-ai transition-colors hover:bg-ai/10"
        >
          <Sparkles className="size-3.5" strokeWidth={2.4} /> Ask about the
          directory
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatBlock
          label={sp.onRecord}
          value={`${data.length}`}
          sub={sp.fullHistory}
          tone="iris"
        />
        <StatBlock
          label={c.improving}
          value={`${improving}`}
          sub={sp.higherThanFirst}
          tone="mint"
        />
        <StatBlock
          label={c.needsAttention}
          value={`${atRisk}`}
          sub={sp.watchOrRisk}
          tone="rose"
        />
        <StatBlock
          label={c.cohortAverage}
          value={`${(data.reduce((a, b) => a + b.overallAverage, 0) / data.length).toFixed(1)}`}
          sub={sp.acrossYears}
        />
      </div>

      <Panel
        title={sp.profilesTitle}
        action={
          <FilterBar>
            <Select
              label={c.standing}
              value={standing}
              onChange={setStanding}
              options={[
                { value: "all", label: c.all },
                ...standings.map((s) => ({
                  value: s,
                  label: translateStanding(s, messages.standing),
                })),
              ]}
            />
            <SearchInput
              value={query}
              onChange={setQuery}
              placeholder={c.searchStudents}
            />
          </FilterBar>
        }
      >
        <TableShell>
          <thead>
            <tr className="border-b border-black/5">
              <Th>{c.student}</Th>
              <Th>{c.program}</Th>
              <Th>{c.section}</Th>
              <Th align="right">{c.allYearsAvg}</Th>
              <Th align="right">{c.currentYear}</Th>
              <Th align="right">{c.trend}</Th>
              <Th>{c.standing}</Th>
              <Th align="right">{c.profile}</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.studentId}
                className="border-b border-black/5 last:border-0 hover:bg-white/60"
              >
                <td className="px-4 py-2.5 font-semibold">{r.name}</td>
                <td className="px-4 py-2.5 text-ink-soft">
                  {translateOrgName(r.program, locale)}
                </td>
                <td className="px-4 py-2.5 text-ink-soft">{r.section}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center justify-end gap-2">
                    <span className="font-semibold">{r.overallAverage}</span>
                    <Meter
                      value={r.overallAverage}
                      tone={r.overallAverage >= 70 ? "mint" : "amber"}
                    />
                  </div>
                </td>
                <td className="px-4 py-2.5 text-right font-semibold">
                  {r.latestYearAverage}
                </td>
                <td
                  className={`px-4 py-2.5 text-right font-semibold ${r.trend >= 0 ? "text-emerald-700" : "text-rose-600"}`}
                >
                  {r.trend >= 0 ? "+" : ""}
                  {r.trend}
                </td>
                <td className="px-4 py-2.5">
                  <Badge
                    tone={
                      r.standing === "Excellent" ||
                      r.standing === "Good standing"
                        ? "pass"
                        : r.standing === "Watch list"
                          ? "warn"
                          : "fail"
                    }
                  >
                    {translateStanding(r.standing, messages.standing)}
                  </Badge>
                </td>
                <td className="px-4 py-2.5 text-right">
                  <Link
                    to="/$locale/$role/students/$studentId"
                    params={{
                      locale: localeParam,
                      role: roleParam,
                      studentId: r.studentId,
                    }}
                    search={{}}
                    className="text-[12px] font-semibold text-iris hover:underline"
                  >
                    {c.viewProfile}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>
    </>
  );
}
