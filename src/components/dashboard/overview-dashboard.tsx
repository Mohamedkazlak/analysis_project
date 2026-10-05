import { AiDecisionSection } from "@/components/ai-insights";
import { ScopeBanner } from "@/components/dashboard/scope-banner";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type ReactElement } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getManagementOverview } from "@/lib/api";
import {
  AiInsight,
  KpiCard,
  Meter,
  Panel,
  ScreenSkeleton,
  TableShell,
  Th,
  FilterBar,
  Select,
  chartColors,
  tooltipStyle,
} from "@/components/dashboard/dashboard-ui";
import {
  useAnalyticsFilters,
  useFilteredQuery,
} from "@/components/dashboard/use-analytics-filters";
import { useRole } from "@/components/role-context";
import { useLocale, translateOrgName, translateScopeLabel } from "@/lib/i18n";
import type { ManagementOverview, Role } from "@/lib/types";

type CollegeRow = ManagementOverview["passRateByCollege"][number];

function count(value: number) {
  return value.toLocaleString();
}

function chartHeight(rows: number, rowPx = 44, min = 260) {
  return Math.max(min, rows * rowPx + 48);
}

function wrapCollegeName(name: string) {
  const limit = 16;
  if (name.length <= limit) return [name];
  const lines: string[] = [];
  let current = "";
  for (const word of name.split(" ")) {
    const next = current ? `${current} ${word}` : word;
    if (current && next.length > limit) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  if (current) lines.push(current);
  return lines;
}

/** Position the tick, and undo scaleX(-1) when the chart SVG is mirrored. */
function unmirrorAt(x: number, y: number, mirror: boolean) {
  return mirror ? `translate(${x},${y}) scale(-1,1)` : `translate(${x},${y})`;
}

function CollegeNameTick({
  x = 0,
  y = 0,
  payload,
  mirror = false,
}: {
  x?: number;
  y?: number;
  payload?: { value?: string };
  mirror?: boolean;
}) {
  const lines = wrapCollegeName(String(payload?.value ?? ""));
  const lineHeight = 12;
  return (
    <g transform={unmirrorAt(x, y, mirror)}>
      <text x={0} y={0} textAnchor="end" fill={chartColors.axis} fontSize={11}>
        {lines.map((line, index) => (
          <tspan
            key={`${line}-${index}`}
            x={0}
            dy={
              index === 0 ? -((lines.length - 1) * lineHeight) / 2 : lineHeight
            }
          >
            {line}
          </tspan>
        ))}
      </text>
    </g>
  );
}

function AxisPercentTick({
  x = 0,
  y = 0,
  payload,
  mirror = false,
}: {
  x?: number;
  y?: number;
  payload?: { value?: number | string };
  mirror?: boolean;
}) {
  return (
    <g transform={unmirrorAt(x, y, mirror)}>
      <text
        x={0}
        y={0}
        dy={12}
        textAnchor="middle"
        fill={chartColors.axis}
        fontSize={11}
      >
        {`${payload?.value ?? ""}%`}
      </text>
    </g>
  );
}

function BarPercentLabel({
  x,
  y,
  width,
  height,
  value,
  mirror = false,
}: {
  x?: number | string | undefined;
  y?: number | string | undefined;
  width?: number | string | undefined;
  height?: number | string | undefined;
  value?: number | string | undefined;
  mirror?: boolean;
}) {
  const cx = Number(x ?? 0) + Number(width ?? 0) + 8;
  const cy = Number(y ?? 0) + Number(height ?? 0) / 2;
  return (
    <g transform={unmirrorAt(cx, cy, mirror)}>
      <text
        x={0}
        y={0}
        dy={4}
        textAnchor="start"
        fill={chartColors.axis}
        fontSize={11}
      >
        {`${Number(value)}%`}
      </text>
    </g>
  );
}

function ChartLegend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="mt-2 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
      {items.map((item) => (
        <span
          key={item.label}
          className="inline-flex items-center gap-1.5 text-[11px] text-ink-soft"
        >
          <span
            className="size-2.5 shrink-0 rounded-sm"
            style={{ background: item.color }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}

function MirroredChart({
  rtl,
  height,
  children,
}: {
  rtl: boolean;
  height: number;
  children: ReactElement;
}) {
  return (
    <div style={{ height }} className="w-full">
      <div
        className="h-full w-full"
        style={rtl ? { transform: "scaleX(-1)" } : undefined}
      >
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function SplitStat({
  title,
  parts,
  rtl,
}: {
  title: string;
  parts: { label: string; value: number; color: string }[];
  rtl: boolean;
}) {
  const total = parts.reduce((sum, part) => sum + part.value, 0);
  const ordered = rtl ? [...parts].reverse() : parts;
  return (
    <div className="glass-panel p-5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-soft">
        {title}
      </div>
      <div className="mt-3 flex justify-between gap-3 text-[13px] font-semibold text-ink">
        {ordered.map((part) => (
          <span key={part.label}>
            {(total ? (part.value / total) * 100 : 0).toFixed(1)}% {part.label}
          </span>
        ))}
      </div>
      <div
        className="mt-2 flex h-3 overflow-hidden rounded-full bg-black/5"
        style={{ direction: rtl ? "rtl" : "ltr" }}
      >
        {parts.map((part) => (
          <div
            key={part.label}
            style={{
              width: `${total ? (part.value / total) * 100 : 0}%`,
              background: part.color,
            }}
          />
        ))}
      </div>
      <div className="mt-2 flex justify-between gap-3 text-[12px] tabular-nums text-ink-soft">
        {ordered.map((part) => (
          <span key={part.label}>
            {count(part.value)} {part.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function withDisplayCollege(
  rows: CollegeRow[],
  locale: "en" | "ar",
): (CollegeRow & { displayCollege: string })[] {
  return rows.map((row) => ({
    ...row,
    displayCollege: translateOrgName(row.college, locale),
  }));
}

function PresidentCharts({ colleges }: { colleges: CollegeRow[] }) {
  const { locale, messages } = useLocale();
  const rtl = locale === "ar";
  const o = messages.overview;
  const labeled = withDisplayCollege(colleges, locale);
  const mix = labeled.map((row) => {
    const sat = row.passed + row.failed || 1;
    const expected = row.expected || 1;
    return {
      ...row,
      passedShare: (row.passed / sat) * 100,
      failedShare: (row.failed / sat) * 100,
      onTimeShare: (row.onTime / expected) * 100,
      lateShare: (row.late / expected) * 100,
      absentShare: (row.absent / expected) * 100,
    };
  });
  const byPassRate = [...labeled].sort((a, b) => a.passRate - b.passRate);
  const byParticipation = [...labeled].sort(
    (a, b) => a.participation - b.participation,
  );
  const rankH = chartHeight(colleges.length);
  const totals = colleges.reduce(
    (acc, row) => ({
      passed: acc.passed + row.passed,
      failed: acc.failed + row.failed,
      onTime: acc.onTime + row.onTime,
      late: acc.late + row.late,
      absent: acc.absent + row.absent,
      attempted: acc.attempted + row.participants,
      noAttempt: acc.noAttempt + row.absent,
    }),
    {
      passed: 0,
      failed: 0,
      onTime: 0,
      late: 0,
      absent: 0,
      attempted: 0,
      noAttempt: 0,
    },
  );

  const yWidth = rtl ? 150 : 132;
  // Build charts in normal LTR geometry, then mirror the SVG for Arabic so
  // bars grow from the visual right and labels stay readable (unmirrored).
  const chartMargin = {
    top: 8,
    right: 48,
    left: 8,
    bottom: 8,
  };
  const barEndRadius: [number, number, number, number] = [0, 8, 8, 0];

  const yAxisProps = {
    type: "category" as const,
    dataKey: "displayCollege",
    width: yWidth,
    interval: 0,
    tick: (props: { x?: number; y?: number; payload?: { value?: string } }) => (
      <CollegeNameTick {...props} mirror={rtl} />
    ),
    axisLine: false,
    tickLine: false,
  };

  const xAxisProps = {
    type: "number" as const,
    domain: [0, 100] as [number, number],
    tick: (props: {
      x?: number;
      y?: number;
      payload?: { value?: number | string };
    }) => <AxisPercentTick {...props} mirror={rtl} />,
    axisLine: false,
    tickLine: false,
  };

  const fmt = (template: string, vars: Record<string, string | number>) =>
    Object.entries(vars).reduce(
      (s, [k, v]) => s.replace(`{${k}}`, String(v)),
      template,
    );

  return (
    <>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <SplitStat
          title={o.passFail}
          rtl={rtl}
          parts={[
            { label: o.passed, value: totals.passed, color: chartColors.mint },
            { label: o.failed, value: totals.failed, color: chartColors.rose },
          ]}
        />
        <SplitStat
          title={o.attendance}
          rtl={rtl}
          parts={[
            { label: o.onTime, value: totals.onTime, color: chartColors.iris },
            { label: o.late, value: totals.late, color: chartColors.yellow },
            { label: o.absent, value: totals.absent, color: chartColors.rose },
          ]}
        />
        <SplitStat
          title={o.participation}
          rtl={rtl}
          parts={[
            {
              label: o.attempted,
              value: totals.attempted,
              color: chartColors.cyan,
            },
            {
              label: o.noAttempt,
              value: totals.noAttempt,
              color: chartColors.violet,
            },
          ]}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title={o.studentsByCollege}>
          <p className="mb-3 text-[12px] text-ink-soft">
            {o.studentsByCollegeHint}
          </p>
          <MirroredChart rtl={rtl} height={rankH}>
            <BarChart data={mix} layout="vertical" margin={chartMargin}>
              <CartesianGrid stroke={chartColors.grid} horizontal={false} />
              <XAxis {...xAxisProps} />
              <YAxis {...yAxisProps} />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={rtl ? { transform: "scaleX(-1)" } : undefined}
                formatter={(value: number, name: string, item) => {
                  const row = item?.payload as CollegeRow | undefined;
                  const raw = name === o.passed ? row?.passed : row?.failed;
                  return [
                    fmt(o.studentsTooltip, {
                      count: count(raw ?? 0),
                      pct: Number(value).toFixed(1),
                    }),
                    name,
                  ];
                }}
              />
              <Bar
                isAnimationActive={false}
                dataKey="passedShare"
                name={o.passed}
                stackId="sittings"
                fill={chartColors.mint}
                maxBarSize={28}
              />
              <Bar
                isAnimationActive={false}
                dataKey="failedShare"
                name={o.failed}
                stackId="sittings"
                fill={chartColors.rose}
                maxBarSize={28}
                radius={barEndRadius}
              />
            </BarChart>
          </MirroredChart>
          <ChartLegend
            items={[
              { label: o.passed, color: chartColors.mint },
              { label: o.failed, color: chartColors.rose },
            ]}
          />
        </Panel>

        <Panel title={o.attendanceMix}>
          <p className="mb-3 text-[12px] text-ink-soft">
            {o.attendanceMixHint}
          </p>
          <MirroredChart rtl={rtl} height={rankH}>
            <BarChart data={mix} layout="vertical" margin={chartMargin}>
              <CartesianGrid stroke={chartColors.grid} horizontal={false} />
              <XAxis {...xAxisProps} />
              <YAxis {...yAxisProps} />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={rtl ? { transform: "scaleX(-1)" } : undefined}
                formatter={(value: number, name: string, item) => {
                  const row = item?.payload as CollegeRow | undefined;
                  const raw =
                    name === o.onTime
                      ? row?.onTime
                      : name === o.late
                        ? row?.late
                        : row?.absent;
                  return [
                    fmt(o.studentsTooltip, {
                      count: count(raw ?? 0),
                      pct: Number(value).toFixed(1),
                    }),
                    name,
                  ];
                }}
              />
              <Bar
                isAnimationActive={false}
                dataKey="onTimeShare"
                name={o.onTime}
                stackId="att"
                fill={chartColors.iris}
                maxBarSize={28}
              />
              <Bar
                isAnimationActive={false}
                dataKey="lateShare"
                name={o.late}
                stackId="att"
                fill={chartColors.yellow}
                maxBarSize={28}
              />
              <Bar
                isAnimationActive={false}
                dataKey="absentShare"
                name={o.absent}
                stackId="att"
                fill={chartColors.rose}
                maxBarSize={28}
                radius={barEndRadius}
              />
            </BarChart>
          </MirroredChart>
          <ChartLegend
            items={[
              { label: o.onTime, color: chartColors.iris },
              { label: o.late, color: chartColors.yellow },
              { label: o.absent, color: chartColors.rose },
            ]}
          />
        </Panel>

        <Panel title={o.passRateByCollege}>
          <p className="mb-3 text-[12px] text-ink-soft">
            {o.passRateByCollegeHint}
          </p>
          <MirroredChart rtl={rtl} height={rankH}>
            <BarChart data={byPassRate} layout="vertical" margin={chartMargin}>
              <CartesianGrid stroke={chartColors.grid} horizontal={false} />
              <XAxis {...xAxisProps} />
              <YAxis {...yAxisProps} />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={rtl ? { transform: "scaleX(-1)" } : undefined}
                formatter={(value: number, _name, item) => {
                  const row = item?.payload as CollegeRow | undefined;
                  return [
                    fmt(o.passedFailedTooltip, {
                      passed: count(row?.passed ?? 0),
                      failed: count(row?.failed ?? 0),
                    }),
                    `${Number(value).toFixed(1)}%`,
                  ];
                }}
              />
              <Bar
                isAnimationActive={false}
                dataKey="passRate"
                name={o.passRate}
                fill={chartColors.violet}
                maxBarSize={28}
                radius={barEndRadius}
              >
                <LabelList
                  dataKey="passRate"
                  content={(props) => (
                    <BarPercentLabel
                      x={props.x}
                      y={props.y}
                      width={props.width}
                      height={props.height}
                      value={props.value as number | string | undefined}
                      mirror={rtl}
                    />
                  )}
                />
              </Bar>
            </BarChart>
          </MirroredChart>
        </Panel>

        <Panel title={o.participationByCollege}>
          <p className="mb-3 text-[12px] text-ink-soft">
            {o.participationByCollegeHint}
          </p>
          <MirroredChart rtl={rtl} height={rankH}>
            <BarChart
              data={byParticipation}
              layout="vertical"
              margin={chartMargin}
            >
              <CartesianGrid stroke={chartColors.grid} horizontal={false} />
              <XAxis {...xAxisProps} />
              <YAxis {...yAxisProps} />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={rtl ? { transform: "scaleX(-1)" } : undefined}
                formatter={(value: number, _name, item) => {
                  const row = item?.payload as CollegeRow | undefined;
                  return [
                    fmt(o.satMissedTooltip, {
                      sat: count(row?.participants ?? 0),
                      missed: count(row?.absent ?? 0),
                    }),
                    `${Number(value).toFixed(1)}%`,
                  ];
                }}
              />
              <Bar
                isAnimationActive={false}
                dataKey="participation"
                name={o.participation}
                fill={chartColors.cyan}
                maxBarSize={28}
                radius={barEndRadius}
              >
                <LabelList
                  dataKey="participation"
                  content={(props) => (
                    <BarPercentLabel
                      x={props.x}
                      y={props.y}
                      width={props.width}
                      height={props.height}
                      value={props.value as number | string | undefined}
                      mirror={rtl}
                    />
                  )}
                />
              </Bar>
            </BarChart>
          </MirroredChart>
        </Panel>
      </div>

      <Panel title={o.collegeTotals}>
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>{o.college}</Th>
              <Th align="right">{o.students}</Th>
              <Th align="right">{o.passed}</Th>
              <Th align="right">{o.failed}</Th>
              <Th align="right">{o.passRate}</Th>
              <Th align="right">{o.onTime}</Th>
              <Th align="right">{o.missedAny}</Th>
              <Th align="right">{o.attendance}</Th>
              <Th align="right">{o.participation}</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {labeled.map((row) => (
              <tr key={row.college} className="bg-white/40">
                <td className="px-4 py-3 font-semibold text-ink">
                  {row.displayCollege}
                </td>
                <td className="px-4 py-3 text-end tabular-nums">
                  {count(row.students ?? row.participants)}
                </td>
                <td className="px-4 py-3 text-end tabular-nums">
                  {count(row.passed)}
                </td>
                <td className="px-4 py-3 text-end tabular-nums">
                  {count(row.failed)}
                </td>
                <td className="px-4 py-3 text-end tabular-nums font-semibold">
                  {row.passRate}%
                </td>
                <td className="px-4 py-3 text-end tabular-nums">
                  {count(row.onTime)}
                </td>
                <td className="px-4 py-3 text-end tabular-nums">
                  {count(row.absent)}
                </td>
                <td className="px-4 py-3 text-end tabular-nums">
                  {row.attendance}%
                </td>
                <td className="px-4 py-3 text-end tabular-nums">
                  {row.participation}%
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>
    </>
  );
}

const palette = [
  chartColors.iris,
  chartColors.cyan,
  chartColors.mint,
  chartColors.amber,
];

/** Shared KPI / chart overview used by senior_management and program_director shells. */
export function OverviewDashboard({
  role,
  scopeLabel,
}: {
  role: Role;
  scopeLabel?: string;
}) {
  const { viewer } = useRole();
  const { locale, messages } = useLocale();
  const { options } = useAnalyticsFilters();
  const { filters, filtersReady, queryKey, enabled } = useFilteredQuery(
    "management-overview",
  );
  const sectorName = options?.sectors.find(
    (item) => item.id === filters.sectorId,
  )?.name;
  const collegeName = options?.colleges.find(
    (item) => item.id === filters.collegeId,
  )?.name;
  const universityWide =
    role === "senior_management" &&
    viewer.level !== "sector" &&
    !filters.sectorId &&
    !filters.collegeId;
  const presidentScope = universityWide
    ? messages.scope.universityWide
    : translateScopeLabel(
        [sectorName, collegeName].filter(Boolean).join(" · ") ||
          scopeLabel ||
          "",
        locale,
        messages.scope,
      );
  const { data, isPending } = useQuery({
    queryKey: [...queryKey, locale],
    queryFn: () => getManagementOverview(filters, locale),
    enabled,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
  const [sort, setSort] = useState("passRate");
  const o = messages.overview;

  if (!filtersReady)
    return <FiltersRequiredNotice message={messages.filters.required} />;
  if (isPending || !data) return <ScreenSkeleton cards={4} panels={2} />;

  const isPresident = role === "senior_management";
  const showColleges = data.passRateByCollege.length > 1;
  const filtered = data.passRateByCourse;
  const ordered = [...filtered].sort((a, b) =>
    sort === "course"
      ? a.course.localeCompare(b.course)
      : sort === "participants"
        ? b.participants - a.participants
        : b.passRate - a.passRate,
  );
  const colleges = [...data.passRateByCollege].sort((a, b) => {
    if (sort === "attendance") return b.attendance - a.attendance;
    if (sort === "participation") return b.participation - a.participation;
    if (sort === "college") return a.college.localeCompare(b.college);
    return b.passRate - a.passRate;
  });

  if (isPresident) {
    return (
      <>
        {presidentScope ? (
          <div className="rounded-2xl border border-iris/20 bg-iris/8 px-4 py-2.5 text-[12px] font-medium text-iris">
            {messages.scope.scope} · {presidentScope}
          </div>
        ) : null}
        <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
          {data.kpis.map((kpi) => (
            <KpiCard key={kpi.label} kpi={kpi} />
          ))}
        </div>

        <AiInsight>{data.insight}</AiInsight>
        <AiDecisionSection role={role} page="overview" />

        <FilterBar>
          <Select
            label={o.sortSittings}
            value={sort}
            options={[
              { value: "passRate", label: o.sortPassRate },
              { value: "attendance", label: o.sortAttendance },
              { value: "participation", label: o.sortParticipation },
              { value: "college", label: o.sortCollege },
            ]}
            onChange={setSort}
          />
        </FilterBar>

        <PresidentCharts colleges={colleges} />
      </>
    );
  }

  return (
    <>
      <ScopeBanner />
      {scopeLabel ? (
        <div className="rounded-2xl border border-iris/20 bg-iris/8 px-4 py-2.5 text-[12px] font-medium text-iris">
          {messages.scope.scope} ·{" "}
          {translateScopeLabel(scopeLabel, locale, messages.scope)}
        </div>
      ) : null}

      <FilterBar>
        <Select
          label={o.sortBy}
          value={sort}
          options={[
            { value: "passRate", label: o.sortPassRate },
            { value: "participants", label: o.sortParticipants },
            { value: "course", label: o.sortCourse },
          ]}
          onChange={setSort}
        />
      </FilterBar>

      <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
        {data.kpis.map((kpi) => (
          <KpiCard key={kpi.label} kpi={kpi} />
        ))}
      </div>

      <AiDecisionSection role={role} page="overview" />

      {showColleges && (
        <Panel title={o.passRateByCollege}>
          <TableShell>
            <thead className="bg-iris/8">
              <tr>
                <Th>{o.college}</Th>
                <Th>{messages.filters.curriculum}</Th>
                <Th>{o.sortParticipants.split(" ")[0]}</Th>
                <Th>{o.passRate}</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/5">
              {colleges.map((row, i) => (
                <tr key={row.college} className="bg-white/40">
                  <td className="px-4 py-3 font-semibold text-ink">
                    {translateOrgName(row.college, locale)}
                  </td>
                  <td className="px-4 py-3 text-ink-soft">{row.courses}</td>
                  <td className="px-4 py-3 text-ink-soft">
                    {row.participants.toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Meter
                        value={row.passRate}
                        tone={
                          (["iris", "cyan", "mint", "amber"] as const)[i % 4]!
                        }
                      />
                      <span className="font-semibold text-ink">
                        {row.passRate}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel
          title={
            locale === "ar"
              ? "معدل النجاح حسب المقرر"
              : "Pass rate by curriculum"
          }
          className="lg:col-span-2"
          action={
            <span className="rounded-full bg-violet/12 px-2.5 py-1 text-[11px] font-semibold text-violet">
              {locale === "ar" ? "الفصل الحالي" : "Current term"}
            </span>
          }
        >
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={ordered}
                margin={{ top: 8, right: 8, bottom: 0, left: -18 }}
              >
                <CartesianGrid stroke={chartColors.grid} vertical={false} />
                <XAxis
                  dataKey="course"
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  reversed={locale === "ar"}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  domain={[0, 100]}
                  unit="%"
                  orientation={locale === "ar" ? "right" : "left"}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(v: number) => `${v}%`}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="passRate"
                  radius={[10, 10, 0, 0]}
                  maxBarSize={54}
                >
                  {ordered.map((row, i) => (
                    <Cell key={row.course} fill={palette[i % palette.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel
          title={
            locale === "ar"
              ? "نشاط الامتحانات · 6 أشهر"
              : "Exam activity · 6 mo"
          }
        >
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={data.activityTrend}
                margin={{ top: 8, right: 8, bottom: 0, left: -18 }}
              >
                <defs>
                  <linearGradient
                    id={`activity-${role}`}
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor={chartColors.iris}
                      stopOpacity={0.35}
                    />
                    <stop
                      offset="100%"
                      stopColor={chartColors.violet}
                      stopOpacity={0.02}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={chartColors.grid} vertical={false} />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  reversed={locale === "ar"}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  orientation={locale === "ar" ? "right" : "left"}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Area
                  isAnimationActive={false}
                  type="monotone"
                  dataKey="exams"
                  name={o.kpiExams}
                  stroke={chartColors.iris}
                  strokeWidth={2}
                  fill={`url(#activity-${role})`}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <AiInsight>{data.insight}</AiInsight>

      <Panel
        title={
          locale === "ar"
            ? "المشاركة حسب المقرر"
            : "Participation by curriculum"
        }
        action={
          <span className="text-[11px] font-medium text-ink-soft">
            {locale === "ar" ? "الفصل الحالي" : "Current term"}
          </span>
        }
      >
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>{messages.filters.curriculum}</Th>
              <Th>{o.sortParticipants.split(" ")[0]}</Th>
              <Th>{o.passRate}</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {ordered.map((row, i) => (
              <tr key={row.course} className="bg-white/40">
                <td className="px-4 py-3 font-semibold text-ink">
                  {row.course}
                </td>
                <td className="px-4 py-3 text-ink-soft">
                  {row.participants.toLocaleString()}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Meter
                      value={row.passRate}
                      tone={
                        (["iris", "cyan", "mint", "amber"] as const)[i % 4]!
                      }
                    />
                    <span className="font-semibold text-ink">
                      {row.passRate}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>
    </>
  );
}
