import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  collegeOptions,
  examChartRows,
  filterByCollege,
  selectedCollege,
  semesterCoverage,
  semesterPassRateNote,
} from "@/components/dashboard/student-performance";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AiDecisionSection } from "@/components/ai-insights";
import { getStudentPerformance } from "@/lib/api";
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
  SearchInput,
  chartColors,
  tooltipStyle,
} from "@/components/dashboard/dashboard-ui";
import type { RankedStudent } from "@/lib/types";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { roleGuard } from "@/lib/auth/role-guards";
import { ScopeBanner } from "@/components/dashboard/scope-banner";

export const Route = createFileRoute("/$role/performance")({
  beforeLoad: roleGuard("/performance"),
  head: () => ({
    meta: [
      { title: "Student Performance Reports — BNU" },
      {
        name: "description",
        content:
          "Average scores, pass/fail split, score distribution and ranked student results per exam.",
      },
      { property: "og:title", content: "Student Performance Reports — BNU" },
      {
        property: "og:description",
        content:
          "Average scores, pass/fail split, score distribution and ranked student results per exam.",
      },
    ],
  }),
  component: PerformanceReport,
});

type SortKey = keyof Pick<
  RankedStudent,
  "rank" | "name" | "average" | "best" | "trend"
>;

function PerformanceReport() {
  const { filters, filtersReady, queryKey, enabled } = useFilteredQuery(
    "student-performance",
  );
  const { data, isPending } = useQuery({
    queryKey,
    queryFn: () => getStudentPerformance(filters),
    enabled,
  });
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [asc, setAsc] = useState(true);
  const [course, setCourse] = useState("all");
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const [scoreCollege, setScoreCollege] = useState("");
  const [passCollege, setPassCollege] = useState("");
  const [rankedCollege, setRankedCollege] = useState("all");

  if (!filtersReady) return <FiltersRequiredNotice />;
  if (isPending || !data) return <ScreenSkeleton cards={4} panels={3} />;

  const scoreColleges = collegeOptions(data.averageByExam);
  const rankedColleges = collegeOptions(data.ranked);
  const passColleges = collegeOptions(data.semesterComparison);
  const activeScoreCollege = selectedCollege(scoreColleges, scoreCollege);
  const activePassCollege = selectedCollege(passColleges, passCollege);
  const scoreRows = examChartRows(
    filterByCollege(data.averageByExam, activeScoreCollege),
  );
  const passRows = examChartRows(
    filterByCollege(data.semesterComparison, activePassCollege),
  );
  const passNote = semesterPassRateNote(
    semesterCoverage(passRows),
    data.currentTerm,
    data.previousTerm,
  );

  const courseOptions = [
    { value: "all", label: "All curriculums" },
    ...Array.from(
      new Set(filterByCollege(data.ranked, rankedCollege).map((r) => r.course)),
    ).map((c) => ({
      value: c,
      label: c,
    })),
  ];

  const visible = data.ranked.filter(
    (r) =>
      (rankedCollege === "all" || r.collegeId === rankedCollege) &&
      (course === "all" || r.course === course) &&
      (status === "all" || r.status === status) &&
      r.name.toLowerCase().includes(query.trim().toLowerCase()),
  );

  const sorted = [...visible].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    const cmp =
      typeof av === "string" && typeof bv === "string"
        ? av.localeCompare(bv)
        : Number(av) - Number(bv);
    return asc ? cmp : -cmp;
  });

  const toggle = (key: SortKey) => {
    if (key === sortKey) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(true);
    }
  };

  const passed = data.passFail[0]!.value;
  const failed = data.passFail[1]!.value;
  const passRate = ((passed / (passed + failed)) * 100).toFixed(1);

  return (
    <>
      <ScopeBanner />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatBlock
          label="Highest score"
          value={`${data.highest.score}`}
          sub={`${data.highest.name} · ${data.highest.exam}`}
          tone="mint"
        />
        <StatBlock
          label="Lowest score"
          value={`${data.lowest.score}`}
          sub={`${data.lowest.name} · ${data.lowest.exam}`}
          tone="rose"
        />
        <StatBlock
          label="Pass rate"
          value={`${passRate}%`}
          sub={`${passed} passed · ${failed} failed`}
          tone="iris"
        />
        <StatBlock
          label="Cohort average"
          value={`${(data.averageByExam.reduce((a, b) => a + b.average, 0) / data.averageByExam.length).toFixed(1)}`}
          sub="Across 6 assessments"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel
          title="Average Score by Test"
          className="lg:col-span-2"
          action={
            scoreColleges.length > 1 ? (
              <Select
                label="College"
                value={activeScoreCollege}
                options={scoreColleges}
                onChange={setScoreCollege}
              />
            ) : null
          }
        >
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={scoreRows}
                margin={{ top: 8, right: 8, bottom: 8, left: -18 }}
              >
                <CartesianGrid stroke={chartColors.grid} vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  interval={0}
                  angle={-35}
                  textAnchor="end"
                  height={64}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  domain={[0, 100]}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, _name, item) => {
                    const exam = (
                      item?.payload as { exam?: string } | undefined
                    )?.exam;
                    return [
                      `${Number(value).toFixed(1)}%`,
                      exam ? `Average · ${exam}` : "Average",
                    ];
                  }}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="average"
                  name="Average"
                  radius={[10, 10, 0, 0]}
                  maxBarSize={46}
                  fill={chartColors.iris}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Pass / Fail Split">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.passFail}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="58%"
                  outerRadius="82%"
                  paddingAngle={3}
                  stroke="none"
                >
                  <Cell fill={chartColors.mint} />
                  <Cell fill={chartColors.rose} />
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: chartColors.axis }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <AiDecisionSection />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Score Distribution">
          <div className="h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.distribution}
                margin={{ top: 8, right: 8, bottom: 0, left: -18 }}
              >
                <CartesianGrid stroke={chartColors.grid} vertical={false} />
                <XAxis
                  dataKey="bucket"
                  tick={{ fontSize: 10, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar
                  isAnimationActive={false}
                  dataKey="students"
                  name="Students"
                  radius={[8, 8, 0, 0]}
                  fill={chartColors.violet}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel
          title="Exam pass rates by semester"
          action={
            passColleges.length > 1 ? (
              <Select
                label="College"
                value={activePassCollege}
                options={passColleges}
                onChange={setPassCollege}
              />
            ) : null
          }
        >
          <p className="mb-3 text-[12px] text-ink-soft">{passNote}</p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={passRows}
                margin={{ top: 8, right: 8, bottom: 8, left: -18 }}
              >
                <CartesianGrid stroke={chartColors.grid} vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  interval={0}
                  angle={-35}
                  textAnchor="end"
                  height={64}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  domain={[0, 100]}
                  unit="%"
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, name: string) => [
                    `${Number(value).toFixed(1)}%`,
                    name,
                  ]}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: chartColors.axis }}
                />
                <Line
                  isAnimationActive={false}
                  type="monotone"
                  dataKey="current"
                  name={data.currentTerm ?? "This semester"}
                  stroke={chartColors.iris}
                  strokeWidth={2.5}
                  connectNulls={false}
                  dot={{ r: 3 }}
                />
                <Line
                  isAnimationActive={false}
                  type="monotone"
                  dataKey="previous"
                  name={data.previousTerm ?? "Last semester"}
                  stroke={chartColors.cyan}
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  connectNulls={false}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <Panel
        title="Ranked Student Performance"
        action={
          <FilterBar>
            <SearchInput
              value={query}
              onChange={setQuery}
              placeholder="Find a student…"
            />
            {rankedColleges.length > 1 ? (
              <Select
                label="College"
                value={rankedCollege}
                options={[
                  { value: "all", label: "All colleges" },
                  ...rankedColleges,
                ]}
                onChange={(value) => {
                  setRankedCollege(value);
                  setCourse("all");
                }}
              />
            ) : null}
            <Select
              label="Curriculum"
              value={
                courseOptions.some((option) => option.value === course)
                  ? course
                  : "all"
              }
              options={courseOptions}
              onChange={setCourse}
            />
            <Select
              label="Result"
              value={status}
              options={[
                { value: "all", label: "All students" },
                { value: "Pass", label: "Passing" },
                { value: "Fail", label: "Failing" },
              ]}
              onChange={setStatus}
            />
            <span className="text-[11px] font-medium text-ink-soft">
              {sorted.length} of {data.ranked.length} · click a header to sort
            </span>
          </FilterBar>
        }
      >
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th onClick={() => toggle("rank")}>Rank</Th>
              <Th onClick={() => toggle("name")}>Student</Th>
              <Th>Course</Th>
              <Th onClick={() => toggle("average")}>Avg score</Th>
              <Th onClick={() => toggle("best")} align="right">
                Best
              </Th>
              <Th onClick={() => toggle("trend")} align="right">
                Trend
              </Th>
              <Th align="right">Status</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {sorted.map((row) => (
              <tr key={row.studentId} className="bg-white/40">
                <td className="px-4 py-3 text-ink-soft">
                  {String(row.rank).padStart(2, "0")}
                </td>
                <td className="px-4 py-3 font-semibold text-ink">{row.name}</td>
                <td className="px-4 py-3 text-ink-soft">{row.course}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Meter
                      value={row.average}
                      tone={row.status === "Pass" ? "iris" : "rose"}
                    />
                    <span className="font-semibold text-ink">
                      {row.average}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-right text-ink-soft">
                  {row.best}
                </td>
                <td
                  className={`px-4 py-3 text-right font-semibold ${row.trend >= 0 ? "text-mintink" : "text-rosee"}`}
                >
                  {row.trend >= 0 ? "▲" : "▼"} {Math.abs(row.trend)}
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
    </>
  );
}
