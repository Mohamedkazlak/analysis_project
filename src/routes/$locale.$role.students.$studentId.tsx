import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Sparkles } from "lucide-react";
import { getStudentProfile } from "@/lib/api";
import { AiDecisionSection } from "@/components/ai-insights";
import { openChat } from "@/lib/chat-bus";
import { useRole } from "@/components/role-context";
import {
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
import { useLocale, translateStanding } from "@/lib/i18n";
import {
  MirroredChart,
  tooltipMirrorStyle,
} from "@/components/dashboard/chart-rtl";

export const Route = createFileRoute("/$locale/$role/students/$studentId")({
  beforeLoad: roleGuard("/students"),
  head: () => ({
    meta: [
      { title: "Student Profile — BNU" },
      {
        name: "description",
        content:
          "Full academic profile: yearly averages, GPA, course grades, attendance and exam history.",
      },
      { property: "og:title", content: "Student Profile — BNU" },
      {
        property: "og:description",
        content:
          "Full academic profile: yearly averages, GPA, course grades, attendance and exam history.",
      },
      { property: "og:type", content: "profile" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: StudentProfile,
});

const standingTone = (standing: string) =>
  standing === "Excellent" || standing === "Good standing"
    ? "pass"
    : standing === "Watch list"
      ? "warn"
      : "fail";

/**
 * PERMISSION GATE — evaluated before the profile is fetched. Named student
 * records are readable by Senior Management and Faculty only; the equivalent
 * server-side check belongs in the server function + row-level policy.
 */
function StudentProfile() {
  const { locale: localeParam, role: roleParam, studentId } = Route.useParams();
  const { role } = useRole();
  const { locale, messages } = useLocale();
  const rtl = locale === "ar";
  const c = messages.common;
  const sp = messages.studentProfilePage;
  const o = messages.overview;
  const allowed =
    role === "senior_management" ||
    role === "program_director" ||
    role === "academic_affairs" ||
    role === "professor";
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("student-profile");
  const { data, isPending } = useQuery({
    queryKey: [...queryKey, studentId],
    queryFn: () => getStudentProfile(studentId, filters),
    enabled: allowed && enabled,
  });

  if (!allowed) {
    return (
      <Panel title={c.restricted}>
        <p className="text-[13px] text-ink-soft">
          Individual student records are available to Senior Management, Program
          Directors, Academic Affairs and Professors.
        </p>
      </Panel>
    );
  }

  if (!filtersReady) return <FiltersRequiredNotice />;
  if (isPending || !data) return <ScreenSkeleton cards={4} panels={3} />;

  return (
    <>
      <AiDecisionSection page="student" />
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="font-display grid size-14 place-items-center rounded-2xl bg-iris/15 text-lg font-extrabold text-iris">
              {data.name
                .split(" ")
                .map((n) => n[0])
                .join("")}
            </div>
            <div>
              <h1 className="font-display text-lg font-bold">{data.name}</h1>
              <p className="text-[12px] text-ink-soft">
                {data.program} · Section {data.section} · Rank {data.cohortRank}{" "}
                of {data.cohortSize}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Badge tone={standingTone(data.standing)}>{data.standing}</Badge>
            <Link
              to="/$locale/$role/students"
              params={{ locale: localeParam, role: roleParam }}
              search={{}}
              className="text-[12px] font-semibold text-iris hover:underline"
            >
              ← All students
            </Link>
          </div>
        </div>
      </Panel>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatBlock
          label={sp.allYearsAverage}
          value={`${data.overallAverage}`}
          sub={`${sp.cohortAvg} ${data.classAverage}`}
          tone="iris"
        />
        <StatBlock
          label={sp.currentGpa}
          value={`${data.gpa}`}
          sub={sp.gpaSub}
          tone="mint"
        />
        <StatBlock
          label={o.attendance}
          value={`${data.attendance}%`}
          sub={sp.attendanceSub}
        />
        <StatBlock
          label={sp.creditsEarned}
          value={`${data.totalCredits}`}
          sub={`${data.years.length} ${c.academicYear}`}
          tone="iris"
        />
      </div>

      <div className="flex justify-end">
        <button
          onClick={() =>
            openChat({
              context: `Ask about ${data.name}`,
              question: `What should I know about ${data.name} (${data.studentId})?`,
            })
          }
          className="inline-flex items-center gap-1.5 rounded-full border border-ai/40 bg-white/70 px-3.5 py-1.5 text-[12px] font-semibold text-ai transition-colors hover:bg-ai/10"
        >
          <Sparkles className="size-3.5" strokeWidth={2.4} /> Ask about this
          student
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel title={sp.avgByYear} className="lg:col-span-2">
          <MirroredChart rtl={rtl} height={256}>
            <LineChart
              data={data.yearTrend}
              margin={{ top: 8, right: 8, bottom: 0, left: -18 }}
            >
              <CartesianGrid stroke={chartColors.grid} vertical={false} />
              <XAxis
                dataKey="year"
                tick={{ fontSize: 11, fill: chartColors.axis }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: chartColors.axis }}
                axisLine={false}
                tickLine={false}
                domain={[30, 100]}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={tooltipMirrorStyle(rtl)}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, color: chartColors.axis }}
              />
              <Line
                isAnimationActive={false}
                type="monotone"
                dataKey="student"
                name={data.name}
                stroke={chartColors.iris}
                strokeWidth={2.5}
                dot={{ r: 3 }}
              />
              <Line
                isAnimationActive={false}
                type="monotone"
                dataKey="cohort"
                name={sp.cohortAvg}
                stroke={chartColors.cyan}
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={false}
              />
            </LineChart>
          </MirroredChart>
        </Panel>

        <Panel title={sp.topicStrengths}>
          <MirroredChart rtl={rtl} height={256}>
            <RadarChart data={data.topics} outerRadius="72%">
              <PolarGrid stroke={chartColors.grid} />
              <PolarAngleAxis
                dataKey="topic"
                tick={{ fontSize: 10, fill: chartColors.axis }}
              />
              <Radar
                isAnimationActive={false}
                dataKey="score"
                stroke={chartColors.violet}
                fill={chartColors.violet}
                fillOpacity={0.28}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={tooltipMirrorStyle(rtl)}
              />
            </RadarChart>
          </MirroredChart>
        </Panel>
      </div>

      <Panel title={sp.yearRecord}>
        <TableShell>
          <thead>
            <tr className="border-b border-black/5">
              <Th>{c.academicYear}</Th>
              <Th>{c.level}</Th>
              <Th align="right">{c.average}</Th>
              <Th align="right">{c.gpa}</Th>
              <Th align="right">{c.exams}</Th>
              <Th align="right">{o.passRate}</Th>
              <Th align="right">{o.attendance}</Th>
              <Th align="right">{c.credits}</Th>
              <Th>{c.standing}</Th>
            </tr>
          </thead>
          <tbody>
            {data.years.map((y) => (
              <tr
                key={y.year}
                className="border-b border-black/5 last:border-0"
              >
                <td className="px-4 py-2.5 font-semibold">{y.year}</td>
                <td className="px-4 py-2.5 text-ink-soft">{y.yearLabel}</td>
                <td className="px-4 py-2.5 text-right font-semibold">
                  {y.average}
                </td>
                <td className="px-4 py-2.5 text-right">{y.gpa}</td>
                <td className="px-4 py-2.5 text-right">{y.examsTaken}</td>
                <td className="px-4 py-2.5 text-right">{y.passRate}%</td>
                <td className="px-4 py-2.5 text-right">{y.attendance}%</td>
                <td className="px-4 py-2.5 text-right">{y.credits}</td>
                <td className="px-4 py-2.5">
                  <Badge tone={standingTone(y.standing)}>
                    {translateStanding(y.standing, messages.standing)}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title={sp.courseAverages}>
          <MirroredChart rtl={rtl} height={256}>
            <BarChart
              data={data.courseMatrix.map((row) => {
                const entry: Record<string, string | number> = {
                  course: row.course,
                };
                data.years.forEach((y, i) => {
                  entry[y.year] = row.values[i] ?? 0;
                });
                return entry;
              })}
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
              />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={tooltipMirrorStyle(rtl)}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, color: chartColors.axis }}
              />
              {data.years.map((y, i) => (
                <Bar
                  key={y.year}
                  isAnimationActive={false}
                  dataKey={y.year}
                  radius={[8, 8, 0, 0]}
                  maxBarSize={26}
                  fill={
                    [chartColors.iris, chartColors.violet, chartColors.cyan][
                      i % 3
                    ]
                  }
                />
              ))}
            </BarChart>
          </MirroredChart>
        </Panel>

        <Panel title={sp.examHistory}>
          <TableShell>
            <thead>
              <tr className="border-b border-black/5">
                <Th>{c.exam}</Th>
                <Th>{c.course}</Th>
                <Th>{c.date}</Th>
                <Th align="right">{c.score}</Th>
                <Th align="right">{c.minutes}</Th>
                <Th>{c.result}</Th>
              </tr>
            </thead>
            <tbody>
              {data.recentAttempts.map((a) => (
                <tr
                  key={`${a.course}-${a.exam}`}
                  className="border-b border-black/5 last:border-0"
                >
                  <td className="px-4 py-2.5 font-medium">{a.exam}</td>
                  <td className="px-4 py-2.5 text-ink-soft">{a.course}</td>
                  <td className="px-4 py-2.5 text-ink-soft">{a.date}</td>
                  <td className="px-4 py-2.5 text-right font-semibold">
                    {a.status === "No attempt" ? "—" : a.score}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {a.status === "No attempt" ? "—" : a.minutes}
                  </td>
                  <td className="px-4 py-2.5">
                    <Badge
                      tone={
                        a.status === "Pass"
                          ? "pass"
                          : a.status === "Fail"
                            ? "fail"
                            : "neutral"
                      }
                    >
                      {translateStanding(a.status, messages.standing)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </Panel>
      </div>
    </>
  );
}
