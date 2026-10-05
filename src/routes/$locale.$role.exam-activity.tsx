import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
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
import {
  AxisValueTick,
  CategoryTick,
  ChartLegend,
  MirroredChart,
  tooltipMirrorStyle,
} from "@/components/dashboard/chart-rtl";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { useLocale, translateOrgName } from "@/lib/i18n";
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

export const Route = createFileRoute("/$locale/$role/exam-activity")({
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
  const { locale, messages } = useLocale();
  const rtl = locale === "ar";
  const c = messages.common;
  const ea = messages.examActivity;
  const o = messages.overview;
  const { filters, filtersReady, queryKey, enabled } = useFilteredQuery(
    "management-overview",
  );
  const { data, isPending } = useQuery({
    queryKey: [...queryKey, locale],
    queryFn: () => getManagementOverview(filters, locale),
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
      { value: "all", label: c.allSemesters },
      ...activitySemesterOptions(periodRows),
    ],
    [c.allSemesters, periodRows],
  );
  const monthOptions = useMemo(
    () => [
      { value: "all", label: c.allMonths },
      ...activityMonthOptions(periodRows, semesterId, locale),
    ],
    [c.allMonths, locale, periodRows, semesterId],
  );
  const chartRows = useMemo(
    () => filterActivityTrend(trend, semesterId, monthKey, locale),
    [trend, semesterId, monthKey, locale],
  );
  const exams = useMemo(
    () => filterExamSummaries(examSummaries, semesterId, monthKey),
    [examSummaries, semesterId, monthKey],
  );
  const colleges = useMemo(() => {
    return examsByCollege(exams).map((row) => ({
      ...row,
      displayCollege: translateOrgName(row.college, locale),
    }));
  }, [exams, locale]);
  const selectedCollege = colleges.some((row) => row.college === scoreCollege)
    ? scoreCollege
    : (colleges[0]?.college ?? "");
  const selectedCollegeLabel =
    colleges.find((row) => row.college === selectedCollege)?.displayCollege ??
    selectedCollege;
  const scores = useMemo(
    () =>
      examScoreRows(
        exams.filter((exam) => exam.college === selectedCollege),
        locale,
      ),
    [exams, locale, selectedCollege],
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
  const change = monthExamChange(chartRows, locale);
  const insight = examActivityInsight(exams, chartRows, locale);

  function onSemesterChange(id: string) {
    setSemesterId(id);
    const nextMonths = activityMonthOptions(periodRows, id, locale);
    if (monthKey !== "all" && !nextMonths.some((m) => m.value === monthKey)) {
      setMonthKey("all");
    }
  }

  const periodFilters = (
    <FilterBar>
      <Select
        label={c.semester}
        value={semesterId}
        options={semesterOptions}
        onChange={onSemesterChange}
      />
      <Select
        label={c.month}
        value={monthKey}
        options={monthOptions}
        onChange={setMonthKey}
      />
    </FilterBar>
  );

  const axisTick = (props: {
    x?: number;
    y?: number;
    payload?: { value?: string | number };
  }) => (
    <CategoryTick
      x={props.x}
      y={props.y}
      payload={{ value: String(props.payload?.value ?? "") }}
      mirror={rtl}
      limit={22}
    />
  );

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatBlock
          label={ea.examsLatestMonth}
          value={(latest?.exams ?? 0).toLocaleString()}
          sub={latest?.label ?? ea.noExamsInView}
        />
        <StatBlock
          label={c.studentsWhoSat}
          value={(latest?.participants ?? 0).toLocaleString()}
          sub={latest ? ea.uniqueInMonth.replace("{label}", latest.label) : ""}
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
      <AiDecisionSection page="exam-activity" />

      <Panel title={ea.monthlyTitle} action={periodFilters}>
        <p className="mb-3 text-[12px] text-ink-soft">{ea.monthlyHint}</p>
        {chartRows.length ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-[12px] font-semibold text-ink">
                {c.exams}
              </p>
              <MirroredChart rtl={rtl} height={256}>
                <BarChart
                  data={chartRows}
                  margin={{ top: 8, right: 8, bottom: 0, left: -4 }}
                >
                  <CartesianGrid stroke={chartColors.grid} vertical={false} />
                  <XAxis
                    dataKey="label"
                    interval={0}
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
                    allowDecimals={false}
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
                    formatter={(value: number) => [count(value), c.exams]}
                  />
                  <Bar
                    isAnimationActive={false}
                    dataKey="exams"
                    name={c.exams}
                    fill={chartColors.iris}
                    maxBarSize={48}
                    radius={[8, 8, 0, 0]}
                  />
                </BarChart>
              </MirroredChart>
            </div>
            <div>
              <p className="mb-2 text-[12px] font-semibold text-ink">
                {c.studentsWhoSat}
              </p>
              <MirroredChart rtl={rtl} height={256}>
                <BarChart
                  data={chartRows}
                  margin={{ top: 8, right: 8, bottom: 0, left: -4 }}
                >
                  <CartesianGrid stroke={chartColors.grid} vertical={false} />
                  <XAxis
                    dataKey="label"
                    interval={0}
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
                    allowDecimals={false}
                    tick={(props) => (
                      <AxisValueTick
                        x={props.x}
                        y={props.y}
                        payload={{
                          value: count(Number(props.payload?.value ?? 0)),
                        }}
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
                    formatter={(value: number) => [
                      count(value),
                      c.studentsWhoSat,
                    ]}
                  />
                  <Bar
                    isAnimationActive={false}
                    dataKey="participants"
                    name={c.studentsWhoSat}
                    fill={chartColors.cyan}
                    maxBarSize={48}
                    radius={[8, 8, 0, 0]}
                  />
                </BarChart>
              </MirroredChart>
            </div>
          </div>
        ) : (
          <p className="py-10 text-center text-[13px] text-ink-soft">
            {ea.emptyPeriod}
          </p>
        )}
      </Panel>

      {colleges.length ? (
        <div className="grid grid-cols-1 gap-4">
          <Panel title={ea.byCollegeTitle}>
            <p className="mb-3 text-[12px] text-ink-soft">{ea.byCollegeHint}</p>
            <MirroredChart
              rtl={rtl}
              height={chartHeight(colleges.length, 36, 280)}
            >
              <BarChart
                data={colleges}
                layout="vertical"
                margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
              >
                <CartesianGrid stroke={chartColors.grid} horizontal={false} />
                <XAxis
                  type="number"
                  allowDecimals={false}
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
                  type="category"
                  dataKey="displayCollege"
                  width={160}
                  interval={0}
                  tick={axisTick}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  wrapperStyle={tooltipMirrorStyle(rtl)}
                  formatter={(value: number) => [count(value), c.exams]}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="exams"
                  name={c.exams}
                  fill={chartColors.iris}
                  maxBarSize={22}
                  radius={[0, 8, 8, 0]}
                />
              </BarChart>
            </MirroredChart>
          </Panel>

          <Panel title={ea.outcomesTitle}>
            <p className="mb-3 text-[12px] text-ink-soft">{ea.outcomesHint}</p>
            <MirroredChart
              rtl={rtl}
              height={chartHeight(colleges.length, 36, 280)}
            >
              <BarChart
                data={colleges}
                layout="vertical"
                margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
              >
                <CartesianGrid stroke={chartColors.grid} horizontal={false} />
                <XAxis
                  type="number"
                  tick={(props) => (
                    <AxisValueTick
                      x={props.x}
                      y={props.y}
                      payload={{
                        value: count(Number(props.payload?.value ?? 0)),
                      }}
                      mirror={rtl}
                    />
                  )}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="displayCollege"
                  width={160}
                  interval={0}
                  tick={axisTick}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  wrapperStyle={tooltipMirrorStyle(rtl)}
                  formatter={(value: number, name: string) => [
                    count(value),
                    name,
                  ]}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="passed"
                  name={o.passed}
                  stackId="outcome"
                  fill={chartColors.mint}
                  maxBarSize={22}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="failed"
                  name={o.failed}
                  stackId="outcome"
                  fill={chartColors.rose}
                  maxBarSize={22}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="absent"
                  name={o.absent}
                  stackId="outcome"
                  fill={chartColors.yellow}
                  maxBarSize={22}
                  radius={[0, 8, 8, 0]}
                />
              </BarChart>
            </MirroredChart>
            <ChartLegend
              items={[
                { label: o.passed, color: chartColors.mint },
                { label: o.failed, color: chartColors.rose },
                { label: o.absent, color: chartColors.yellow },
              ]}
            />
          </Panel>
        </div>
      ) : null}

      {selectedCollege ? (
        <Panel
          title={ea.scoresTitle}
          action={
            <Select
              label={o.college}
              value={selectedCollege}
              options={colleges.map((row) => ({
                value: row.college,
                label: row.displayCollege,
              }))}
              onChange={setScoreCollege}
            />
          }
        >
          <p className="mb-3 text-[12px] text-ink-soft">
            {ea.scoresHint.replace("{college}", selectedCollegeLabel)}
          </p>
          <MirroredChart rtl={rtl} height={chartHeight(scores.length, 34, 240)}>
            <BarChart
              data={scores}
              layout="vertical"
              margin={{ top: 8, right: 48, left: 8, bottom: 8 }}
            >
              <CartesianGrid stroke={chartColors.grid} horizontal={false} />
              <XAxis
                type="number"
                domain={[0, 100]}
                tick={(props) => (
                  <AxisValueTick
                    x={props.x}
                    y={props.y}
                    payload={props.payload}
                    mirror={rtl}
                    suffix="%"
                  />
                )}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={148}
                interval={0}
                tick={(props) => (
                  <CategoryTick {...props} mirror={rtl} limit={14} />
                )}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={tooltipMirrorStyle(rtl)}
                formatter={(value: number, name: string, item) => {
                  const row = item?.payload as (typeof scores)[number];
                  if (name === c.averageScore) {
                    return [
                      `${Number(value).toFixed(1)}% · ${row.passRate}% ${o.passed} · ${row.title}`,
                      name,
                    ];
                  }
                  return [value, name];
                }}
              />
              <Bar
                isAnimationActive={false}
                dataKey="avgScore"
                name={c.averageScore}
                fill={chartColors.violet}
                maxBarSize={22}
                radius={[0, 8, 8, 0]}
              />
            </BarChart>
          </MirroredChart>
        </Panel>
      ) : null}
    </>
  );
}
