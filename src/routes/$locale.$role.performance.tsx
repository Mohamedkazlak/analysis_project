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
import {
  useLocale,
  translateOrgName,
  translateStanding,
  translateTermName,
} from "@/lib/i18n";
import {
  AngledCategoryTick,
  AxisValueTick,
  ChartLegend,
  MirroredChart,
  tooltipMirrorStyle,
} from "@/components/dashboard/chart-rtl";

export const Route = createFileRoute("/$locale/$role/performance")({
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
  const { locale, messages } = useLocale();
  const rtl = locale === "ar";
  const c = messages.common;
  const pp = messages.performancePage;
  const o = messages.overview;
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

  const scoreColleges = collegeOptions(data.averageByExam).map((opt) => ({
    ...opt,
    label: translateOrgName(opt.label, locale),
  }));
  const rankedColleges = collegeOptions(data.ranked).map((opt) => ({
    ...opt,
    label: translateOrgName(opt.label, locale),
  }));
  const passColleges = collegeOptions(data.semesterComparison).map((opt) => ({
    ...opt,
    label: translateOrgName(opt.label, locale),
  }));
  const activeScoreCollege = selectedCollege(scoreColleges, scoreCollege);
  const activePassCollege = selectedCollege(passColleges, passCollege);
  const scoreRows = examChartRows(
    filterByCollege(data.averageByExam, activeScoreCollege),
  );
  const passRows = examChartRows(
    filterByCollege(data.semesterComparison, activePassCollege),
  );
  const currentTermLabel = translateTermName(data.currentTerm, locale);
  const previousTermLabel = translateTermName(data.previousTerm, locale);
  const passNote = semesterPassRateNote(
    semesterCoverage(passRows),
    currentTermLabel || null,
    previousTermLabel || null,
    {
      thisSemester: c.thisSemester,
      lastSemester: c.lastSemester,
      both: pp.passNoteBoth,
      currentOnly: pp.passNoteCurrentOnly,
      previousOnly: pp.passNotePreviousOnly,
      none: pp.passNoteNone,
    },
  );

  const courseOptions = [
    { value: "all", label: messages.filters.allCurriculum },
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

  const passed = data.passFail[0]?.value ?? 0;
  const failed = data.passFail[1]?.value ?? 0;
  const passFailData = [
    { name: o.passed, value: passed },
    { name: o.failed, value: failed },
  ];
  const scoredTotal = passed + failed;
  const passRate = scoredTotal
    ? ((passed / scoredTotal) * 100).toFixed(1)
    : "—";
  const cohortAverage =
    data.averageByExam.length === 0
      ? "—"
      : (
          data.averageByExam.reduce((a, b) => a + b.average, 0) /
          data.averageByExam.length
        ).toFixed(1);

  return (
    <>
      <ScopeBanner />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatBlock
          label={pp.highest}
          value={`${data.highest.score}`}
          sub={`${data.highest.name} · ${data.highest.exam}`}
          tone="mint"
        />
        <StatBlock
          label={pp.lowest}
          value={`${data.lowest.score}`}
          sub={`${data.lowest.name} · ${data.lowest.exam}`}
          tone="rose"
        />
        <StatBlock
          label={o.passRate}
          value={passRate === "—" ? "—" : `${passRate}%`}
          sub={`${passed} ${o.passed} · ${failed} ${o.failed}`}
          tone="iris"
        />
        <StatBlock
          label={c.cohortAverage}
          value={`${cohortAverage}`}
          sub={pp.acrossAssessments}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel
          title={pp.avgByTest}
          className="lg:col-span-2"
          action={
            scoreColleges.length > 1 ? (
              <Select
                label={o.college}
                value={activeScoreCollege}
                options={scoreColleges}
                onChange={setScoreCollege}
              />
            ) : null
          }
        >
          <MirroredChart rtl={rtl} height={288}>
            <BarChart
              data={scoreRows}
              margin={{ top: 8, right: 8, bottom: 8, left: -18 }}
            >
              <CartesianGrid stroke={chartColors.grid} vertical={false} />
              <XAxis
                dataKey="label"
                tick={(props) => <AngledCategoryTick {...props} mirror={rtl} />}
                axisLine={false}
                tickLine={false}
                interval={0}
                height={64}
              />
              <YAxis
                tick={(props) => (
                  <AxisValueTick
                    x={props.x}
                    y={props.y}
                    payload={props.payload}
                    mirror={rtl}
                    dy={4}
                  />
                )}
                axisLine={false}
                tickLine={false}
                domain={[0, 100]}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={tooltipMirrorStyle(rtl)}
                formatter={(value: number, _name, item) => {
                  const exam = (item?.payload as { exam?: string } | undefined)
                    ?.exam;
                  return [
                    `${Number(value).toFixed(1)}%`,
                    exam
                      ? pp.tooltipAverageExam.replace("{exam}", exam)
                      : pp.tooltipAverage,
                  ];
                }}
              />
              <Bar
                isAnimationActive={false}
                dataKey="average"
                name={c.average}
                radius={[10, 10, 0, 0]}
                maxBarSize={46}
                fill={chartColors.iris}
              />
            </BarChart>
          </MirroredChart>
        </Panel>

        <Panel title={pp.passFailSplit}>
          <div style={{ height: 220 }} className="w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={passFailData}
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
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ChartLegend
            items={[
              { label: o.passed, color: chartColors.mint },
              { label: o.failed, color: chartColors.rose },
            ]}
          />
        </Panel>
      </div>

      <AiDecisionSection page="performance" />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title={pp.scoreDistribution}>
          <MirroredChart rtl={rtl} height={240}>
            <BarChart
              data={data.distribution}
              margin={{ top: 8, right: 8, bottom: 0, left: -18 }}
            >
              <CartesianGrid stroke={chartColors.grid} vertical={false} />
              <XAxis
                dataKey="bucket"
                tick={(props) => (
                  <AxisValueTick
                    x={props.x}
                    y={props.y}
                    payload={props.payload}
                    mirror={rtl}
                  />
                )}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={(props) => (
                  <AxisValueTick
                    x={props.x}
                    y={props.y}
                    payload={props.payload}
                    mirror={rtl}
                    dy={4}
                  />
                )}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={tooltipMirrorStyle(rtl)}
              />
              <Bar
                isAnimationActive={false}
                dataKey="students"
                name={o.students}
                radius={[8, 8, 0, 0]}
                fill={chartColors.violet}
              />
            </BarChart>
          </MirroredChart>
        </Panel>

        <Panel
          title={pp.passRatesBySemester}
          action={
            passColleges.length > 1 ? (
              <Select
                label={o.college}
                value={activePassCollege}
                options={passColleges}
                onChange={setPassCollege}
              />
            ) : null
          }
        >
          <p className="mb-3 text-[12px] text-ink-soft">{passNote}</p>
          <MirroredChart rtl={rtl} height={260}>
            <LineChart
              data={passRows}
              margin={{ top: 8, right: 8, bottom: 8, left: -18 }}
            >
              <CartesianGrid stroke={chartColors.grid} vertical={false} />
              <XAxis
                dataKey="label"
                tick={(props) => <AngledCategoryTick {...props} mirror={rtl} />}
                axisLine={false}
                tickLine={false}
                interval={0}
                height={64}
              />
              <YAxis
                tick={(props) => (
                  <AxisValueTick
                    x={props.x}
                    y={props.y}
                    payload={props.payload}
                    mirror={rtl}
                    dy={4}
                    suffix="%"
                  />
                )}
                axisLine={false}
                tickLine={false}
                domain={[0, 100]}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={tooltipMirrorStyle(rtl)}
                formatter={(value: number, name: string) => [
                  `${Number(value).toFixed(1)}%`,
                  name,
                ]}
              />
              <Line
                isAnimationActive={false}
                type="monotone"
                dataKey="current"
                name={currentTermLabel || c.thisSemester}
                stroke={chartColors.iris}
                strokeWidth={2.5}
                connectNulls={false}
                dot={{ r: 3 }}
              />
              <Line
                isAnimationActive={false}
                type="monotone"
                dataKey="previous"
                name={previousTermLabel || c.lastSemester}
                stroke={chartColors.cyan}
                strokeWidth={2}
                strokeDasharray="5 4"
                connectNulls={false}
                dot={{ r: 3 }}
              />
            </LineChart>
          </MirroredChart>
          <ChartLegend
            items={[
              {
                label: currentTermLabel || c.thisSemester,
                color: chartColors.iris,
              },
              {
                label: previousTermLabel || c.lastSemester,
                color: chartColors.cyan,
              },
            ]}
          />
        </Panel>
      </div>

      <Panel
        title={pp.rankedTitle}
        action={
          <FilterBar>
            <SearchInput
              value={query}
              onChange={setQuery}
              placeholder={c.findStudent}
            />
            {rankedColleges.length > 1 ? (
              <Select
                label={o.college}
                value={rankedCollege}
                options={[
                  { value: "all", label: messages.filters.allColleges },
                  ...rankedColleges,
                ]}
                onChange={(value) => {
                  setRankedCollege(value);
                  setCourse("all");
                }}
              />
            ) : null}
            <Select
              label={messages.filters.curriculum}
              value={
                courseOptions.some((option) => option.value === course)
                  ? course
                  : "all"
              }
              options={courseOptions}
              onChange={setCourse}
            />
            <Select
              label={c.result}
              value={status}
              options={[
                { value: "all", label: messages.filters.allStudents },
                { value: "Pass", label: c.passing },
                { value: "Fail", label: c.failing },
              ]}
              onChange={setStatus}
            />
            <span className="text-[11px] font-medium text-ink-soft">
              {pp.sortHint
                .replace("{n}", String(sorted.length))
                .replace("{total}", String(data.ranked.length))}
            </span>
          </FilterBar>
        }
      >
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th onClick={() => toggle("rank")}>{c.rank}</Th>
              <Th onClick={() => toggle("name")}>{c.student}</Th>
              <Th>{c.course}</Th>
              <Th onClick={() => toggle("average")}>{c.averageScore}</Th>
              <Th onClick={() => toggle("best")} align="right">
                {locale === "ar" ? "الأفضل" : "Best"}
              </Th>
              <Th onClick={() => toggle("trend")} align="right">
                {c.trend}
              </Th>
              <Th align="right">{c.status}</Th>
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
                    {translateStanding(row.status, messages.standing)}
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
