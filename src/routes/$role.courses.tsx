import { createFileRoute } from "@tanstack/react-router";
import { AiDecisionSection } from "@/components/ai-insights";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getCoursePerformance } from "@/lib/api";
import {
  Badge,
  Meter,
  Panel,
  ScreenSkeleton,
  StatBlock,
  TableShell,
  Th,
  FilterBar,
  Select,
} from "@/components/dashboard/dashboard-ui";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { roleGuard } from "@/lib/auth/role-guards";
import { ScopeBanner } from "@/components/dashboard/scope-banner";
import { useRole } from "@/components/role-context";
import { useLocale, translateOrgName, translateStanding } from "@/lib/i18n";
import {
  coursesCurriculumSubtitle,
  coursesScopeMessage,
  coursesScopeReady,
  courseStanding,
  filterByStanding,
  sortComparisonRows,
  toggleComparisonSort,
  type ComparisonSortKey,
  type StandingFilter,
} from "@/components/dashboard/course-performance";

export const Route = createFileRoute("/$role/courses")({
  beforeLoad: roleGuard("/courses"),
  head: () => ({
    meta: [
      { title: "Course & Instructor Performance — BNU" },
      {
        name: "description",
        content:
          "Average scores by course and a course-level comparison of enrollments and standing.",
      },
      {
        property: "og:title",
        content: "Course & Instructor Performance — BNU",
      },
      {
        property: "og:description",
        content:
          "Average scores by course and a course-level comparison of enrollments and standing.",
      },
    ],
  }),
  component: CoursePerformance,
});

function CoursePerformance() {
  const { role, viewer } = useRole();
  const { locale, messages } = useLocale();
  const c = messages.common;
  const cp = messages.coursesPage;
  const o = messages.overview;
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("course-performance");
  const scopeReady = coursesScopeReady(role, filters, viewer.level);
  const { data, isPending } = useQuery({
    queryKey,
    queryFn: () => getCoursePerformance(filters),
    enabled: enabled && scopeReady,
  });
  const [standing, setStanding] = useState<StandingFilter>("all");
  const [sortKey, setSortKey] = useState<ComparisonSortKey>("college");
  const [asc, setAsc] = useState(true);

  if (!filtersReady || !scopeReady) {
    return <FiltersRequiredNotice message={coursesScopeMessage(role, cp)} />;
  }
  if (isPending || !data) return <ScreenSkeleton cards={4} panels={1} />;

  const courseRows = data.averageByCourse;
  const sections = data.sections;
  const comparisonRows = sortComparisonRows(
    filterByStanding(sections, standing),
    sortKey,
    asc,
  );
  const totalEnrolled = sections.reduce(
    (sum, row) => sum + (row.enrolled ?? 0),
    0,
  );
  const overallAverage =
    courseRows.length === 0
      ? 0
      : Math.round(
          (courseRows.reduce((sum, row) => sum + row.average, 0) /
            courseRows.length) *
            10,
        ) / 10;
  const onTrackCount = sections.filter(
    (row) => courseStanding(row.passRate) === "on_track",
  ).length;
  const toggleSort = (key: ComparisonSortKey) => {
    const next = toggleComparisonSort(sortKey, asc, key);
    setSortKey(next.key);
    setAsc(next.asc);
  };
  const header = (key: ComparisonSortKey, label: string) => (
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      {label}
      {sortKey === key ? <span aria-hidden>{asc ? "↑" : "↓"}</span> : null}
    </span>
  );

  return (
    <>
      <ScopeBanner />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatBlock
          label={cp.curriculum}
          value={courseRows.length.toLocaleString()}
          sub={coursesCurriculumSubtitle(role, filters, viewer.level, cp)}
        />
        <StatBlock
          label={c.averageScore}
          value={`${overallAverage}`}
          sub={cp.meanAverages}
          tone="iris"
        />
        <StatBlock
          label={c.enrollments}
          value={totalEnrolled.toLocaleString()}
          sub={cp.totalEnrollments}
        />
        <StatBlock
          label={c.onTrack}
          value={`${onTrackCount}/${sections.length || 0}`}
          sub={cp.onTrackSub}
          tone={
            onTrackCount === sections.length && sections.length
              ? "mint"
              : "iris"
          }
        />
      </div>

      <AiDecisionSection />

      <Panel
        title={cp.sectionComparison}
        action={
          <FilterBar>
            <Select
              label={c.standing}
              value={standing}
              options={[
                { value: "all", label: c.allCourses },
                { value: "on_track", label: c.onTrack },
                { value: "needs_support", label: c.needsSupport },
              ]}
              onChange={(value) => setStanding(value as StandingFilter)}
            />
          </FilterBar>
        }
      >
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th onClick={() => toggleSort("college")}>
                {header("college", o.college)}
              </Th>
              <Th onClick={() => toggleSort("course")}>
                {header("course", c.course)}
              </Th>
              <Th align="right" onClick={() => toggleSort("enrolled")}>
                {header("enrolled", c.enrollments)}
              </Th>
              <Th onClick={() => toggleSort("average")}>
                {header("average", c.average)}
              </Th>
              <Th align="right" onClick={() => toggleSort("passRate")}>
                {header("passRate", o.passRate)}
              </Th>
              <Th align="right" onClick={() => toggleSort("standing")}>
                {header("standing", c.standing)}
              </Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {comparisonRows.length ? (
              comparisonRows.map((row) => {
                const status = courseStanding(row.passRate);
                return (
                  <tr
                    key={row.courseCode || row.course}
                    className="bg-white/40"
                  >
                    <td className="px-4 py-3 text-ink-soft">
                      {row.college
                        ? translateOrgName(row.college, locale)
                        : "—"}
                    </td>
                    <td className="px-4 py-3 font-semibold text-ink">
                      {row.course}
                    </td>
                    <td className="px-4 py-3 text-end tabular-nums text-ink-soft">
                      {(row.enrolled ?? 0).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Meter value={row.average} tone="iris" />
                        <span className="font-semibold text-ink">
                          {row.average}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-end text-ink-soft">
                      {row.passRate}%
                    </td>
                    <td className="px-4 py-3 text-end">
                      <Badge tone={status === "on_track" ? "pass" : "fail"}>
                        {translateStanding(status, messages.standing)}
                      </Badge>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr className="bg-white/40">
                <td
                  colSpan={6}
                  className="px-4 py-6 text-center text-[13px] text-ink-soft"
                >
                  {cp.noMatch}
                </td>
              </tr>
            )}
          </tbody>
        </TableShell>
      </Panel>
    </>
  );
}
