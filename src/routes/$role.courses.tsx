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
import {
  coursesCurriculumSubtitle,
  coursesScopeMessage,
  coursesScopeReady,
  courseStanding,
  courseStandingLabel,
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
    return <FiltersRequiredNotice message={coursesScopeMessage(role)} />;
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
          label="Curriculum"
          value={courseRows.length.toLocaleString()}
          sub={coursesCurriculumSubtitle(role, filters, viewer.level)}
        />
        <StatBlock
          label="Average score"
          value={`${overallAverage}`}
          sub="Mean of course averages"
          tone="iris"
        />
        <StatBlock
          label="Enrollments"
          value={totalEnrolled.toLocaleString()}
          sub="Total across these courses"
        />
        <StatBlock
          label="On track"
          value={`${onTrackCount}/${sections.length || 0}`}
          sub="Pass rate 75% or above"
          tone={
            onTrackCount === sections.length && sections.length
              ? "mint"
              : "iris"
          }
        />
      </div>

      <AiDecisionSection />

      <Panel
        title="Section Comparison"
        action={
          <FilterBar>
            <Select
              label="Standing"
              value={standing}
              options={[
                { value: "all", label: "All courses" },
                { value: "on_track", label: "On track" },
                { value: "needs_support", label: "Needs support" },
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
                {header("college", "College")}
              </Th>
              <Th onClick={() => toggleSort("course")}>
                {header("course", "Course")}
              </Th>
              <Th align="right" onClick={() => toggleSort("enrolled")}>
                {header("enrolled", "Enrollments")}
              </Th>
              <Th onClick={() => toggleSort("average")}>
                {header("average", "Average")}
              </Th>
              <Th align="right" onClick={() => toggleSort("passRate")}>
                {header("passRate", "Pass rate")}
              </Th>
              <Th align="right" onClick={() => toggleSort("standing")}>
                {header("standing", "Standing")}
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
                      {row.college || "—"}
                    </td>
                    <td className="px-4 py-3 font-semibold text-ink">
                      {row.course}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-ink-soft">
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
                    <td className="px-4 py-3 text-right text-ink-soft">
                      {row.passRate}%
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Badge tone={status === "on_track" ? "pass" : "fail"}>
                        {courseStandingLabel(status)}
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
                  No courses match this standing filter.
                </td>
              </tr>
            )}
          </tbody>
        </TableShell>
      </Panel>
    </>
  );
}
