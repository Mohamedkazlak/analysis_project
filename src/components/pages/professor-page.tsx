import { useQuery } from "@tanstack/react-query";
import { AiDecisionSection } from "@/components/ai-insights";
import { ScopeBanner } from "@/components/dashboard/scope-banner";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { getStudentPerformance } from "@/lib/api";
import {
  Badge,
  Meter,
  Panel,
  ScreenSkeleton,
  StatBlock,
  TableShell,
  Th,
} from "@/components/dashboard/dashboard-ui";
import { useRole } from "@/components/role-context";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";

export function ProfessorPage() {
  const { user } = useRole();
  const myCourses = user.courses ?? [];
  const { filters, filtersReady, queryKey, enabled } = useFilteredQuery(
    "student-performance",
  );
  const performance = useQuery({
    queryKey,
    queryFn: () => getStudentPerformance(filters),
    enabled,
  });

  if (!filtersReady) return <FiltersRequiredNotice />;
  if (performance.isPending || !performance.data) {
    return <ScreenSkeleton cards={3} panels={2} />;
  }

  const rows = performance.data.ranked.slice(0, 10);

  return (
    <>
      <ScopeBanner />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatBlock
          label="My courses"
          value={`${myCourses.length}`}
          sub={myCourses.map((c) => c.code).join(" · ") || "—"}
          tone="iris"
        />
        <StatBlock
          label="Enrolled (sections)"
          value={`${myCourses.reduce((n, c) => n + c.enrolled, 0)}`}
          sub="Across assigned sections"
          tone="mint"
        />
        <StatBlock
          label="Class average"
          value={`${performance.data.averageByExam[0]?.average ?? "—"}`}
          sub="Latest exam in scope"
          tone="iris"
        />
      </div>

      <AiDecisionSection role="professor" page="overview" />

      <Panel title="Gradebook · my courses">
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>Rank</Th>
              <Th>Student</Th>
              <Th>Course</Th>
              <Th align="right">Average</Th>
              <Th align="right">Status</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {rows.map((row) => (
              <tr
                key={`${row.studentId}-${row.course}`}
                className="bg-white/40"
              >
                <td className="px-4 py-3 text-ink-soft">{row.rank}</td>
                <td className="px-4 py-3 font-semibold text-ink">{row.name}</td>
                <td className="px-4 py-3 text-ink-soft">{row.course}</td>
                <td className="px-4 py-3 text-right">
                  <div className="inline-flex items-center gap-2">
                    <Meter value={row.average} tone="iris" />
                    <span className="font-semibold text-ink">
                      {row.average}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <Badge tone={row.status === "Pass" ? "pass" : "fail"}>
                    {row.status}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>

      <Panel title="Assigned sections">
        <ul className="grid gap-2 sm:grid-cols-2">
          {myCourses.flatMap((c) =>
            c.sections.map((section) => (
              <li
                key={`${c.id}-${section}`}
                className="rounded-2xl bg-white/60 px-3.5 py-3 text-[13px]"
              >
                <div className="font-semibold text-ink">
                  {c.code} · Section {section}
                </div>
                <div className="mt-1 text-ink-soft">
                  {c.sections.length
                    ? Math.round(c.enrolled / c.sections.length)
                    : c.enrolled}{" "}
                  students enrolled
                </div>
              </li>
            )),
          )}
        </ul>
      </Panel>
    </>
  );
}
