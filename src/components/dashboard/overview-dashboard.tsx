import { AiDecisionSection } from "@/components/ai-insights";
import { ScopeBanner } from "@/components/dashboard/scope-banner";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
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
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import type { ManagementOverview, Role } from "@/lib/types";

type CollegeRow = ManagementOverview["passRateByCollege"][number];

function count(value: number) {
  return value.toLocaleString();
}

function chartHeight(rows: number, rowPx = 44, min = 260) {
  return Math.max(min, rows * rowPx + 48);
}

function wrapCollegeName(name: string) {
  const limit = 18;
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

function CollegeNameTick({
  x = 0,
  y = 0,
  payload,
}: {
  x?: number;
  y?: number;
  payload?: { value?: string };
}) {
  const lines = wrapCollegeName(String(payload?.value ?? ""));
  const lineHeight = 12;
  return (
    <text x={x} y={y} textAnchor="end" fill={chartColors.axis} fontSize={11}>
      {lines.map((line, index) => (
        <tspan
          key={`${line}-${index}`}
          x={x}
          dy={index === 0 ? -((lines.length - 1) * lineHeight) / 2 : lineHeight}
        >
          {line}
        </tspan>
      ))}
    </text>
  );
}

function SplitStat({
  title,
  parts,
}: {
  title: string;
  parts: { label: string; value: number; color: string }[];
}) {
  const total = parts.reduce((sum, part) => sum + part.value, 0);
  return (
    <div className="glass-panel p-5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-soft">
        {title}
      </div>
      <div className="mt-3 flex justify-between gap-3 text-[13px] font-semibold text-ink">
        {parts.map((part) => (
          <span key={part.label}>
            {(total ? (part.value / total) * 100 : 0).toFixed(1)}% {part.label}
          </span>
        ))}
      </div>
      <div className="mt-2 flex h-3 overflow-hidden rounded-full bg-black/5">
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
        {parts.map((part) => (
          <span key={part.label}>
            {count(part.value)} {part.label.toLowerCase()}
          </span>
        ))}
      </div>
    </div>
  );
}

function PresidentCharts({ colleges }: { colleges: CollegeRow[] }) {
  const mix = colleges.map((row) => {
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
  const byPassRate = [...colleges].sort((a, b) => a.passRate - b.passRate);
  const byParticipation = [...colleges].sort(
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

  return (
    <>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <SplitStat
          title="Pass / fail"
          parts={[
            { label: "Passed", value: totals.passed, color: chartColors.mint },
            { label: "Failed", value: totals.failed, color: chartColors.rose },
          ]}
        />
        <SplitStat
          title="Attendance"
          parts={[
            { label: "On time", value: totals.onTime, color: chartColors.iris },
            { label: "Late", value: totals.late, color: chartColors.yellow },
            { label: "Absent", value: totals.absent, color: chartColors.rose },
          ]}
        />
        <SplitStat
          title="Participation"
          parts={[
            {
              label: "Attempted",
              value: totals.attempted,
              color: chartColors.cyan,
            },
            {
              label: "No attempt",
              value: totals.noAttempt,
              color: chartColors.violet,
            },
          ]}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Students by college">
          <p className="mb-3 text-[12px] text-ink-soft">
            Each bar is every student who sat. Green passed and red failed.
          </p>
          <div style={{ height: rankH }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={mix}
                layout="vertical"
                margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
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
                  dataKey="college"
                  width={132}
                  interval={0}
                  tick={CollegeNameTick}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, name: string, item) => {
                    const row = item?.payload as CollegeRow | undefined;
                    const raw = name === "Passed" ? row?.passed : row?.failed;
                    return [
                      `${count(raw ?? 0)} students · ${Number(value).toFixed(1)}%`,
                      name,
                    ];
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: chartColors.axis }}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="passedShare"
                  name="Passed"
                  stackId="sittings"
                  fill={chartColors.mint}
                  maxBarSize={28}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="failedShare"
                  name="Failed"
                  stackId="sittings"
                  fill={chartColors.rose}
                  maxBarSize={28}
                  radius={[8, 8, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Attendance mix">
          <p className="mb-3 text-[12px] text-ink-soft">
            Share of students who were on time for every exam, late to any exam,
            or missed any exam.
          </p>
          <div style={{ height: rankH }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={mix}
                layout="vertical"
                margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
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
                  dataKey="college"
                  width={132}
                  interval={0}
                  tick={CollegeNameTick}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, name: string, item) => {
                    const row = item?.payload as CollegeRow | undefined;
                    const raw =
                      name === "On time"
                        ? row?.onTime
                        : name === "Late"
                          ? row?.late
                          : row?.absent;
                    return [
                      `${count(raw ?? 0)} students · ${Number(value).toFixed(1)}%`,
                      name,
                    ];
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 11, color: chartColors.axis }}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="onTimeShare"
                  name="On time"
                  stackId="att"
                  fill={chartColors.iris}
                  maxBarSize={28}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="lateShare"
                  name="Late"
                  stackId="att"
                  fill={chartColors.yellow}
                  maxBarSize={28}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="absentShare"
                  name="Absent"
                  stackId="att"
                  fill={chartColors.rose}
                  maxBarSize={28}
                  radius={[0, 8, 8, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Pass rate by college">
          <p className="mb-3 text-[12px] text-ink-soft">
            Share of students whose average across the exams they sat is at or
            above the pass mark.
          </p>
          <div style={{ height: rankH }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={byPassRate}
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
                  dataKey="college"
                  width={132}
                  interval={0}
                  tick={CollegeNameTick}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, _name, item) => {
                    const row = item?.payload as CollegeRow | undefined;
                    return [
                      `${count(row?.passed ?? 0)} passed · ${count(row?.failed ?? 0)} failed`,
                      `${Number(value).toFixed(1)}%`,
                    ];
                  }}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="passRate"
                  name="Pass rate"
                  fill={chartColors.violet}
                  maxBarSize={28}
                  radius={[0, 8, 8, 0]}
                >
                  <LabelList
                    dataKey="passRate"
                    position="right"
                    formatter={(value: unknown) => `${Number(value)}%`}
                    style={{ fill: chartColors.axis, fontSize: 11 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Participation by college">
          <p className="mb-3 text-[12px] text-ink-soft">
            Share of students who sat every exam they were expected to sit.
          </p>
          <div style={{ height: rankH }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={byParticipation}
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
                  dataKey="college"
                  width={132}
                  interval={0}
                  tick={CollegeNameTick}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(value: number, _name, item) => {
                    const row = item?.payload as CollegeRow | undefined;
                    return [
                      `${count(row?.participants ?? 0)} sat every exam · ${count(row?.absent ?? 0)} missed at least one`,
                      `${Number(value).toFixed(1)}%`,
                    ];
                  }}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="participation"
                  name="Participation"
                  fill={chartColors.cyan}
                  maxBarSize={28}
                  radius={[0, 8, 8, 0]}
                >
                  <LabelList
                    dataKey="participation"
                    position="right"
                    formatter={(value: unknown) => `${Number(value)}%`}
                    style={{ fill: chartColors.axis, fontSize: 11 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <Panel title="College totals">
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>College</Th>
              <Th align="right">Students</Th>
              <Th align="right">Passed</Th>
              <Th align="right">Failed</Th>
              <Th align="right">Pass rate</Th>
              <Th align="right">On time</Th>
              <Th align="right">Missed any</Th>
              <Th align="right">Attendance</Th>
              <Th align="right">Participation</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {colleges.map((row) => (
              <tr key={row.college} className="bg-white/40">
                <td className="px-4 py-3 font-semibold text-ink">
                  {row.college}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {count(row.participants)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {count(row.passed)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {count(row.failed)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums font-semibold">
                  {row.passRate}%
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {count(row.onTime)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {count(row.absent)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {row.attendance}%
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
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
  const [sort, setSort] = useState("passRate");

  if (!filtersReady) return <FiltersRequiredNotice />;
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
        <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
          {data.kpis.map((kpi) => (
            <KpiCard key={kpi.label} kpi={kpi} />
          ))}
        </div>

        <AiInsight>{data.insight}</AiInsight>
        <AiDecisionSection role={role} />

        <FilterBar>
          <Select
            label="Sort sittings"
            value={sort}
            options={[
              { value: "passRate", label: "Pass rate (high → low)" },
              { value: "attendance", label: "Attendance (high → low)" },
              { value: "participation", label: "Participation (high → low)" },
              { value: "college", label: "College name" },
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
          Scope · {scopeLabel}
        </div>
      ) : null}

      <FilterBar>
        <Select
          label="Sort by"
          value={sort}
          options={[
            { value: "passRate", label: "Pass rate (high → low)" },
            { value: "participants", label: "Participants (high → low)" },
            { value: "course", label: "Curriculum name" },
          ]}
          onChange={setSort}
        />
      </FilterBar>

      <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
        {data.kpis.map((kpi) => (
          <KpiCard key={kpi.label} kpi={kpi} />
        ))}
      </div>

      <AiDecisionSection role={role} />

      {showColleges && (
        <Panel title="Pass rate by college">
          <TableShell>
            <thead className="bg-iris/8">
              <tr>
                <Th>College</Th>
                <Th>Curriculum</Th>
                <Th>Participants</Th>
                <Th>Pass rate</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/5">
              {colleges.map((row, i) => (
                <tr key={row.college} className="bg-white/40">
                  <td className="px-4 py-3 font-semibold text-ink">
                    {row.college}
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
          title="Pass rate by curriculum"
          className="lg:col-span-2"
          action={
            <span className="rounded-full bg-violet/12 px-2.5 py-1 text-[11px] font-semibold text-violet">
              Current term
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

        <Panel title="Exam activity · 6 mo">
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
                />
                <YAxis
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Area
                  isAnimationActive={false}
                  type="monotone"
                  dataKey="exams"
                  name="Exams"
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
        title="Participation by curriculum"
        action={
          <span className="text-[11px] font-medium text-ink-soft">
            Current term
          </span>
        }
      >
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>Curriculum</Th>
              <Th>Participants</Th>
              <Th>Pass rate</Th>
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
