import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { getParticipationReport } from "@/lib/api";
import { AiDecisionSection } from "@/components/ai-insights";
import {
  AiInsight,
  Badge,
  Panel,
  ScreenSkeleton,
  StatBlock,
  TableShell,
  Th,
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
import { roleGuard } from "@/lib/auth/role-guards";
import { ScopeBanner } from "@/components/dashboard/scope-banner";
import { useLocale, translateOrgName, translateStanding } from "@/lib/i18n";

export const Route = createFileRoute("/$locale/$role/participation")({
  beforeLoad: roleGuard("/participation"),
  head: () => ({
    meta: [
      { title: "Student Participation Reports — BNU" },
      {
        name: "description",
        content:
          "Attempts per exam, completion rate, average time taken and a list of absent or late students.",
      },
      { property: "og:title", content: "Student Participation Reports — BNU" },
      {
        property: "og:description",
        content:
          "Attempts per exam, completion rate, average time taken and a list of absent or late students.",
      },
    ],
  }),
  component: Participation,
});

function Participation() {
  const { locale, messages } = useLocale();
  const rtl = locale === "ar";
  const c = messages.common;
  const p = messages.participationPage;
  const o = messages.overview;
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("participation");
  const { data, isPending } = useQuery({
    queryKey: [...queryKey, locale],
    queryFn: () => getParticipationReport(filters, locale),
    enabled,
  });
  if (!filtersReady) return <FiltersRequiredNotice />;
  if (isPending || !data) return <ScreenSkeleton cards={3} panels={3} />;

  const noShows = data.absentees.filter(
    (a) => a.reason === "No attempt",
  ).length;
  const grain = data.grain ?? "exam";
  const attemptsTitle =
    grain === "college"
      ? p.attemptsCollege
      : grain === "curriculum"
        ? p.attemptsCurriculum
        : p.attemptsExam;
  const timeTitle =
    grain === "college"
      ? p.timeCollege
      : grain === "curriculum"
        ? p.timeCurriculum
        : p.timeExam;
  const attendanceTitle =
    grain === "college" ? p.attendanceCollege : p.attendanceCurriculum;
  const attendanceLabel =
    grain === "college" ? o.college : messages.filters.curriculum;
  const categoryCount = Math.max(
    data.attemptsPerExam.length,
    data.avgTimePerExam.length,
    1,
  );
  const attemptsHeight = Math.min(360, Math.max(256, categoryCount * 36));
  const timeHeight = Math.min(480, Math.max(224, categoryCount * 32));
  const localizeCategory = (name: string) =>
    grain === "college" ? translateOrgName(name, locale) : name;
  const attemptsChart = data.attemptsPerExam.map((row) => ({
    ...row,
    exam: localizeCategory(row.exam),
  }));
  const timeChart = data.avgTimePerExam.map((row) => ({
    ...row,
    exam: localizeCategory(row.exam),
  }));

  return (
    <>
      <ScopeBanner />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatBlock
          label={c.completionRate}
          value={`${data.completionRate}%`}
          sub={c.ofExpected}
          tone="mint"
        />
        <StatBlock
          label={o.attendance}
          value={`${data.attendanceRate}%`}
          sub={c.onTimeSittings}
          tone="iris"
        />
        <StatBlock
          label={c.nonParticipants}
          value={`${noShows}`}
          sub={translateStanding("No attempt", messages.standing)}
          tone="rose"
        />
      </div>

      <Panel title={attemptsTitle}>
        <MirroredChart rtl={rtl} height={attemptsHeight}>
          <BarChart
            data={attemptsChart}
            margin={{ top: 8, right: 8, bottom: 28, left: -18 }}
          >
            <CartesianGrid stroke={chartColors.grid} vertical={false} />
            <XAxis
              dataKey="exam"
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
            />
            <Tooltip
              contentStyle={tooltipStyle}
              wrapperStyle={tooltipMirrorStyle(rtl)}
            />
            <Bar
              isAnimationActive={false}
              dataKey="expected"
              name={c.enrolled}
              radius={[8, 8, 0, 0]}
              maxBarSize={40}
              fill={chartColors.violet}
              opacity={0.35}
            />
            <Bar
              isAnimationActive={false}
              dataKey="attempts"
              name={o.attempted}
              radius={[8, 8, 0, 0]}
              maxBarSize={40}
              fill={chartColors.iris}
            />
          </BarChart>
        </MirroredChart>
        <ChartLegend
          items={[
            { label: c.enrolled, color: chartColors.violet },
            { label: o.attempted, color: chartColors.iris },
          ]}
        />
      </Panel>

      <AiInsight>{data.insight}</AiInsight>
      <AiDecisionSection page="participation" />

      <Panel title={timeTitle}>
        <div
          className={
            categoryCount > 12 ? "max-h-[28rem] overflow-y-auto" : undefined
          }
        >
          <MirroredChart rtl={rtl} height={timeHeight}>
            <BarChart
              data={timeChart}
              layout="vertical"
              margin={{ top: 4, right: 16, bottom: 0, left: 8 }}
            >
              <CartesianGrid stroke={chartColors.grid} horizontal={false} />
              <XAxis
                type="number"
                tick={(props) => (
                  <AxisValueTick
                    x={props.x}
                    y={props.y}
                    payload={props.payload}
                    mirror={rtl}
                    suffix={` ${c.minutes}`}
                  />
                )}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="exam"
                tick={(props) => (
                  <CategoryTick {...props} mirror={rtl} limit={18} />
                )}
                axisLine={false}
                tickLine={false}
                width={grain === "exam" ? 160 : 140}
                interval={0}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={tooltipMirrorStyle(rtl)}
                formatter={(v: number) => `${v} ${c.minutes}`}
              />
              <Bar
                isAnimationActive={false}
                dataKey="minutes"
                name={c.minutes}
                radius={[0, 8, 8, 0]}
                maxBarSize={22}
                fill={chartColors.cyan}
              />
            </BarChart>
          </MirroredChart>
        </div>
      </Panel>

      <Panel title={attendanceTitle}>
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>{attendanceLabel}</Th>
              <Th align="right">{o.students}</Th>
              <Th align="right">{c.participated}</Th>
              <Th align="right">{o.absent}</Th>
              <Th align="right">{o.attendance}</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {data.attendanceByCurriculum.map((row) => (
              <tr key={row.course} className="bg-white/40">
                <td className="px-4 py-3 font-semibold text-ink">
                  {grain === "college"
                    ? translateOrgName(row.course, locale)
                    : row.course}
                </td>
                <td className="px-4 py-3 text-end tabular-nums text-ink-soft">
                  {(row.students ?? 0).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-end tabular-nums text-ink-soft">
                  {(row.participated ?? 0).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-end tabular-nums text-ink-soft">
                  {row.absentees.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-end font-semibold text-ink">
                  {row.attendance}%
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>

      <Panel title={p.missingLate}>
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>{c.student}</Th>
              <Th>{o.college}</Th>
              <Th>{c.assessment}</Th>
              <Th>{c.reason}</Th>
              <Th align="right">{c.minutesLate}</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {data.absentees.map((row, i) => (
              <tr key={`${row.student}-${i}`} className="bg-white/40">
                <td className="px-4 py-3 font-semibold text-ink">
                  {row.student}
                </td>
                <td className="px-4 py-3 text-ink-soft">
                  {row.college ? translateOrgName(row.college, locale) : "—"}
                </td>
                <td className="px-4 py-3 text-ink-soft">{row.exam}</td>
                <td className="px-4 py-3">
                  <Badge tone={row.reason === "No attempt" ? "fail" : "warn"}>
                    {translateStanding(row.reason, messages.standing)}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-end text-ink-soft">
                  {row.minutesLate || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>
    </>
  );
}
