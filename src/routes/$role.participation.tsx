import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
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
import { getParticipationReport } from "@/lib/api";
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
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { roleGuard } from "@/lib/auth/role-guards";
import { ScopeBanner } from "@/components/dashboard/scope-banner";

export const Route = createFileRoute("/$role/participation")({
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
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("participation");
  const { data, isPending } = useQuery({
    queryKey,
    queryFn: () => getParticipationReport(filters),
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
      ? "Attempts per College"
      : grain === "curriculum"
        ? "Attempts per Curriculum"
        : "Attempts per Exam";
  const timeTitle =
    grain === "college"
      ? "Average Time Taken per College"
      : grain === "curriculum"
        ? "Average Time Taken per Curriculum"
        : "Average Time Taken per Exam";
  const attendanceTitle =
    grain === "college" ? "Attendance by college" : "Attendance by curriculum";
  const attendanceLabel = grain === "college" ? "College" : "Curriculum";
  const categoryCount = Math.max(
    data.attemptsPerExam.length,
    data.avgTimePerExam.length,
    1,
  );
  const attemptsHeight = Math.min(360, Math.max(256, categoryCount * 36));
  const timeHeight = Math.min(480, Math.max(224, categoryCount * 32));
  const angledLabels = grain !== "exam" || categoryCount > 8;

  return (
    <>
      <ScopeBanner />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatBlock
          label="Completion rate"
          value={`${data.completionRate}%`}
          sub="Of expected sittings"
          tone="mint"
        />
        <StatBlock
          label="Attendance"
          value={`${data.attendanceRate}%`}
          sub="On-time sittings"
          tone="iris"
        />
        <StatBlock
          label="Non-participants"
          value={`${noShows}`}
          sub="No attempt recorded"
          tone="rose"
        />
      </div>

      <Panel title={attemptsTitle}>
        <div style={{ height: attemptsHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data.attemptsPerExam}
              margin={{
                top: 8,
                right: 8,
                bottom: angledLabels ? 28 : 0,
                left: -18,
              }}
            >
              <CartesianGrid stroke={chartColors.grid} vertical={false} />
              <XAxis
                dataKey="exam"
                tick={{ fontSize: 10, fill: chartColors.axis }}
                axisLine={false}
                tickLine={false}
                interval={0}
                angle={angledLabels ? -25 : 0}
                textAnchor={angledLabels ? "end" : "middle"}
                height={angledLabels ? 64 : undefined}
              />
              <YAxis
                tick={{ fontSize: 11, fill: chartColors.axis }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend
                wrapperStyle={{ fontSize: 11, color: chartColors.axis }}
              />
              <Bar
                isAnimationActive={false}
                dataKey="expected"
                name="Enrolled"
                radius={[8, 8, 0, 0]}
                maxBarSize={40}
                fill={chartColors.violet}
                opacity={0.35}
              />
              <Bar
                isAnimationActive={false}
                dataKey="attempts"
                name="Attempted"
                radius={[8, 8, 0, 0]}
                maxBarSize={40}
                fill={chartColors.iris}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <AiInsight>{data.insight}</AiInsight>

      <Panel title={timeTitle}>
        <div
          className={
            categoryCount > 12 ? "max-h-[28rem] overflow-y-auto" : undefined
          }
        >
          <div style={{ height: timeHeight }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.avgTimePerExam}
                layout="vertical"
                margin={{ top: 4, right: 16, bottom: 0, left: 8 }}
              >
                <CartesianGrid stroke={chartColors.grid} horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  unit=" min"
                />
                <YAxis
                  type="category"
                  dataKey="exam"
                  tick={{ fontSize: 10, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  width={grain === "exam" ? 160 : 140}
                  interval={0}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  formatter={(v: number) => `${v} min`}
                />
                <Bar
                  isAnimationActive={false}
                  dataKey="minutes"
                  name="Minutes"
                  radius={[0, 8, 8, 0]}
                  maxBarSize={22}
                  fill={chartColors.cyan}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </Panel>

      <Panel title={attendanceTitle}>
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>{attendanceLabel}</Th>
              <Th align="right">Students</Th>
              <Th align="right">Participated</Th>
              <Th align="right">Absent</Th>
              <Th align="right">Attendance</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {data.attendanceByCurriculum.map((row) => (
              <tr key={row.course} className="bg-white/40">
                <td className="px-4 py-3 font-semibold text-ink">
                  {row.course}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-ink-soft">
                  {(row.students ?? 0).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-ink-soft">
                  {(row.participated ?? 0).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-ink-soft">
                  {row.absentees.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right font-semibold text-ink">
                  {row.attendance}%
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>

      <Panel title="Missing & Late Participants">
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>Student</Th>
              <Th>College</Th>
              <Th>Assessment</Th>
              <Th>Reason</Th>
              <Th align="right">Minutes late</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {data.absentees.map((row, i) => (
              <tr key={`${row.student}-${i}`} className="bg-white/40">
                <td className="px-4 py-3 font-semibold text-ink">
                  {row.student}
                </td>
                <td className="px-4 py-3 text-ink-soft">
                  {row.college || "—"}
                </td>
                <td className="px-4 py-3 text-ink-soft">{row.exam}</td>
                <td className="px-4 py-3">
                  <Badge tone={row.reason === "No attempt" ? "fail" : "warn"}>
                    {row.reason}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-right text-ink-soft">
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
