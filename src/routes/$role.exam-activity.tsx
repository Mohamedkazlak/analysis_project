import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getManagementOverview } from "@/lib/api";
import { AiDecisionSection } from "@/components/ai-insights";
import {
  AiInsight,
  FilterBar,
  Panel,
  ScreenSkeleton,
  Select,
  StatBlock,
  chartColors,
  tooltipStyle,
} from "@/components/dashboard/dashboard-ui";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { roleGuard } from "@/lib/auth/role-guards";
import {
  activityMonthOptions,
  activitySemesterOptions,
  examActivityInsight,
  examScoreRows,
  examsByCollege,
  filterActivityTrend,
  filterExamSummaries,
  monthExamChange,
} from "@/components/dashboard/exam-activity-chart";

export const Route = createFileRoute("/$role/exam-activity")({
  beforeLoad: roleGuard("/exam-activity"),
  head: () => ({
    meta: [
      { title: "Exam Activity Trends — BNU" },
      {
        name: "description",
        content:
          "Exam volume, sitting outcomes and scores across months and semesters.",
      },
      { property: "og:title", content: "Exam Activity Trends — BNU" },
      {
        property: "og:description",
        content:
          "Exam volume, sitting outcomes and scores across months and semesters.",
      },
    ],
  }),
  component: ExamActivity,
});

function count(value: number) {
  return value.toLocaleString();
}

function chartHeight(rows: number, rowPx = 36, min = 240) {
  return Math.max(min, rows * rowPx + 48);
}

function ExamActivity() {
  const { filters, filtersReady, queryKey, enabled } = useFilteredQuery(
    "management-overview",
  );
  const { data, isPending } = useQuery({
    queryKey,
    queryFn: () => getManagementOverview(filters),
    enabled,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
  const [semesterId, setSemesterId] = useState("all");
  const [monthKey, setMonthKey] = useState("all");
  const [scoreCollege, setScoreCollege] = useState("");

  const trend = data?.activityTrend ?? [];
  const examSummaries = data?.examSummaries ?? [];
  const periodRows = useMemo(
    () => [...trend, ...examSummaries],
    [trend, examSummaries],
  );
  const semesterOptions = useMemo(
    () => [
      { value: "all", label: "All semesters" },
      ...activitySemesterOptions(periodRows),
    ],
    [periodRows],
  );
  const monthOptions = useMemo(
    () => [
      { value: "all", label: "All months" },
      ...activityMonthOptions(periodRows, semesterId),
    ],
    [periodRows, semesterId],
  );
  const chartRows = useMemo(
    () => filterActivityTrend(trend, semesterId, monthKey),
    [trend, semesterId, monthKey],
  );
  const exams = useMemo(
    () => filterExamSummaries(examSummaries, semesterId, monthKey),
    [examSummaries, semesterId, monthKey],
  );
  const colleges = useMemo(() => examsByCollege(exams), [exams]);
  const selectedCollege = colleges.some((row) => row.college === scoreCollege)
    ? scoreCollege
    : (colleges[0]?.college ?? "");
  const scores = useMemo(
    () =>
      examScoreRows(exams.filter((exam) => exam.college === selectedCollege)),
    [exams, selectedCollege],
  );

  useEffect(() => {
    if (
      semesterId !== "all" &&
      !semesterOptions.some((option) => option.value === semesterId)
    ) {
      setSemesterId("all");
    }
    if (
      monthKey !== "all" &&
      !monthOptions.some((option) => option.value === monthKey)
    ) {
      setMonthKey("all");
    }
  }, [monthKey, monthOptions, semesterId, semesterOptions]);

  if (!filtersReady) return <FiltersRequiredNotice />;
  if (isPending || !data) return <ScreenSkeleton cards={3} panels={3} />;

  const latest = chartRows[chartRows.length - 1];
  const change = monthExamChange(chartRows);
  const insight = examActivityInsight(exams, chartRows);

  function onSemesterChange(id: string) {
    setSemesterId(id);
    const nextMonths = activityMonthOptions(periodRows, id);
    if (monthKey !== "all" && !nextMonths.some((m) => m.value === monthKey)) {
      setMonthKey("all");
    }
  }

  const periodFilters = (
    <FilterBar>
      <Select
        label="Semester"
        value={semesterId}
        options={semesterOptions}
        onChange={onSemesterChange}
      />
      <Select
        label="Month"
        value={monthKey}
        options={monthOptions}
        onChange={setMonthKey}
      />
    </FilterBar>
  );

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatBlock
          label="Exams in latest month"
          value={(latest?.exams ?? 0).toLocaleString()}
          sub={latest?.label ?? "No exams in this view"}
        />
        <StatBlock
          label="Students who sat"
          value={(latest?.participants ?? 0).toLocaleString()}
          sub={latest ? `Unique students in ${latest.label}` : ""}
          tone="iris"
        />
        <StatBlock
          label={change.label}
          value={change.value}
          sub={change.sub}
          tone={change.tone}
        />
      </div>

      <AiInsight size="lg" headline={insight.headline}>
        {insight.body}
      </AiInsight>
      <AiDecisionSection />

      <Panel title="Exams and students each month" action={periodFilters}>
        <p className="mb-3 text-[12px] text-ink-soft">
          Exams held, and the number of students who sat at least one. Each
          chart has its own scale.
        </p>
        {chartRows.length ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-[12px] font-semibold text-ink">Exams</p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={chartRows}
                    margin={{ top: 8, right: 8, bottom: 0, left: -4 }}
                  >
                    <CartesianGrid stroke={chartColors.grid} vertical={false} />
                    <XAxis
                      dataKey="label"
                      interval={0}
                      tick={{ fontSize: 11, fill: chartColors.axis }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11, fill: chartColors.axis }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(value: number) => [count(value), "Exams"]}
                    />
                    <Bar
                      isAnimationActive={false}
                      dataKey="exams"
                      name="Exams"
                      fill={chartColors.iris}
                      maxBarSize={48}
                      radius={[8, 8, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div>
              <p className="mb-2 text-[12px] font-semibold text-ink">
                Students who sat
              </p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={chartRows}
                    margin={{ top: 8, right: 8, bottom: 0, left: -4 }}
                  >
                    <CartesianGrid stroke={chartColors.grid} vertical={false} />
                    <XAxis
                      dataKey="label"
                      interval={0}
                      tick={{ fontSize: 11, fill: chartColors.axis }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fontSize: 11, fill: chartColors.axis }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(value: number) => count(value)}
                    />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      formatter={(value: number) => [
                        count(value),
                        "Students who sat",
                      ]}
                    />
                    <Bar
                      isAnimationActive={false}
                      dataKey="participants"
                      name="Students who sat"
                      fill={chartColors.cyan}
                      maxBarSize={48}
                      radius={[8, 8, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        ) : (
          <p className="py-10 text-center text-[13px] text-ink-soft">
            No exams in this month or semester.
          </p>
        )}
      </Panel>

      {colleges.length ? (
        <div className="grid grid-cols-1 gap-4">
          <Panel title="Exams administered by college">
            <p className="mb-3 text-[12px] text-ink-soft">
              Distinct exams in this view. A course with two sittings counts as
              two exams.
            </p>
            <div style={{ height: chartHeight(colleges.length, 36, 280) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={colleges}
                  layout="vertical"
                  margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                >
                  <CartesianGrid stroke={chartColors.grid} horizontal={false} />
                  <XAxis
                    type="number"
                    allowDecimals={false}
                    tick={{ fontSize: 11, fill: chartColors.axis }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="college"
                    width={280}
                    interval={0}
                    tick={{ fontSize: 11, fill: chartColors.axis }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(value: number) => [count(value), "Exams"]}
                  />
                  <Bar
                    isAnimationActive={false}
                    dataKey="exams"
                    name="Exams"
                    fill={chartColors.iris}
                    maxBarSize={22}
                    radius={[0, 8, 8, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Exam sitting outcomes">
            <p className="mb-3 text-[12px] text-ink-soft">
              Passed, failed and absent sittings for the exams in this view.
            </p>
            <div style={{ height: chartHeight(colleges.length, 36, 280) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={colleges}
                  layout="vertical"
                  margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                >
                  <CartesianGrid stroke={chartColors.grid} horizontal={false} />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: chartColors.axis }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(value: number) => count(value)}
                  />
                  <YAxis
                    type="category"
                    dataKey="college"
                    width={280}
                    interval={0}
                    tick={{ fontSize: 11, fill: chartColors.axis }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(value: number, name: string) => [
                      count(value),
                      name,
                    ]}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 11, color: chartColors.axis }}
                  />
                  <Bar
                    isAnimationActive={false}
                    dataKey="passed"
                    name="Passed"
                    stackId="outcome"
                    fill={chartColors.mint}
                    maxBarSize={22}
                  />
                  <Bar
                    isAnimationActive={false}
                    dataKey="failed"
                    name="Failed"
                    stackId="outcome"
                    fill={chartColors.rose}
                    maxBarSize={22}
                  />
                  <Bar
                    isAnimationActive={false}
                    dataKey="absent"
                    name="Absent"
                    stackId="outcome"
                    fill={chartColors.yellow}
                    maxBarSize={22}
                    radius={[0, 8, 8, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Panel>
        </div>
      ) : null}

      {selectedCollege ? (
        <Panel
          title="Exam scores"
          action={
            <Select
              label="College"
              value={selectedCollege}
              options={colleges.map((row) => ({
                value: row.college,
                label: row.college,
              }))}
              onChange={setScoreCollege}
            />
          }
        >
          <p className="mb-3 text-[12px] text-ink-soft">
            Average score for each exam in {selectedCollege}, lowest first.
          </p>
          <div style={{ height: chartHeight(scores.length, 34, 240) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={scores}
                layout="vertical"
                margin={{ top: 8, right: 48, left: 8, bottom: 8 }}
              >
                <CartesianGrid stroke={chartColors.grid} horizontal={false} />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  unit="%"
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={148}
                  interval={0}
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, name: string, item) => {
                    const row = item?.payload as (typeof scores)[number];
                    if (name === "Average score") {
                      return [
                        `${Number(value).toFixed(1)}% · ${row.passRate}% passed · ${row.title}`,
                        name,
                      ];
                    }
                    return [value, name];
                  }}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="avgScore"
                  name="Average score"
                  fill={chartColors.violet}
                  maxBarSize={22}
                  radius={[0, 8, 8, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      ) : null}
    </>
  );
}
