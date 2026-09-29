import { AiDecisionSection } from "@/components/ai-insights";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getStudentDashboard } from "@/lib/api";
import {
  Panel,
  ScreenSkeleton,
  StatBlock,
  TableShell,
  Th,
  chartColors,
  tooltipStyle,
} from "@/components/dashboard/dashboard-ui";
import { useRole } from "@/components/role-context";

export function MyProgressPage() {
  const { user } = useRole();
  const { data, isPending } = useQuery({
    queryKey: ["student-dashboard", user.id],
    queryFn: () => getStudentDashboard(),
  });
  if (isPending || !data) return <ScreenSkeleton cards={5} panels={2} />;

  const delta = data.average - data.classAverage;
  const deltaLabel = `${delta >= 0 ? "+" : ""}${delta.toFixed(1)} vs class ${data.classAverage}`;
  const topicNote =
    data.topicsFrom === "courses"
      ? "Course scores this semester"
      : "Percent correct on question topics";

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatBlock
          label="College"
          value={data.college}
          {...(data.sector ? { sub: data.sector } : {})}
          tone="iris"
          valueClassName="text-2xl leading-snug"
        />
        <StatBlock
          label="My average"
          value={`${data.average}`}
          sub={
            data.scoreTimeline.length
              ? `${data.termName ? `${data.termName} · ` : ""}${deltaLabel}`
              : "No exams this semester"
          }
          tone="iris"
        />
        <StatBlock
          label="GPA"
          value={data.gpa == null ? "—" : data.gpa.toFixed(2)}
          sub={
            data.gpa == null
              ? "No graded credits yet"
              : "Cumulative, from transcript grades"
          }
          tone="mint"
        />
        <StatBlock
          label="Strongest topic"
          value={data.bestTopic}
          {...(data.bestTopicScore == null
            ? {}
            : { sub: `${data.bestTopicScore}` })}
          tone={
            data.bestTopicScore != null && data.bestTopicScore >= 75
              ? "mint"
              : "ink"
          }
          valueClassName="text-xl leading-snug"
        />
        <StatBlock
          label="Weakest topic"
          value={data.weakestTopic}
          {...(data.weakestTopicScore == null
            ? {}
            : { sub: `${data.weakestTopicScore}` })}
          tone={
            data.weakestTopicScore != null && data.weakestTopicScore < 60
              ? "rose"
              : "ink"
          }
          valueClassName="text-xl leading-snug"
        />
      </div>

      <AiDecisionSection role="student" />

      <Panel
        title={
          data.termName
            ? `Exam scores · ${data.termName}`
            : "Exam scores this semester"
        }
      >
        {data.scoreTimeline.length ? (
          <>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={data.scoreTimeline}
                  margin={{ top: 8, right: 20, bottom: 0, left: -8 }}
                >
                  <CartesianGrid stroke={chartColors.grid} vertical={false} />
                  <XAxis
                    dataKey="chartLabel"
                    tick={{ fontSize: 11, fill: chartColors.axis }}
                    axisLine={false}
                    tickLine={false}
                    interval={0}
                    padding={{ left: 12, right: 12 }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: chartColors.axis }}
                    axisLine={false}
                    tickLine={false}
                    domain={[0, 100]}
                  />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend
                    wrapperStyle={{ fontSize: 11, color: chartColors.axis }}
                  />
                  <Line
                    isAnimationActive={false}
                    type="monotone"
                    dataKey="score"
                    name="My score"
                    stroke={chartColors.iris}
                    strokeWidth={2.5}
                  />
                  <Line
                    type="monotone"
                    dataKey="classAverage"
                    name="Class average"
                    stroke={chartColors.cyan}
                    strokeWidth={2}
                    strokeDasharray="5 4"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4">
              <TableShell>
                <thead>
                  <tr className="border-b border-black/5">
                    <Th>Course</Th>
                    <Th>Exam</Th>
                    <Th align="right">My score</Th>
                    <Th align="right">Class average</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.scoreTimeline.map((row) => (
                    <tr
                      key={`${row.courseCode}-${row.exam}`}
                      className="border-b border-black/5 last:border-0"
                    >
                      <td className="px-4 py-2.5">
                        <div className="font-semibold">{row.course}</div>
                        <div className="text-[11px] text-ink-soft">
                          {row.courseCode}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-ink-soft">{row.exam}</td>
                      <td
                        className={`px-4 py-2.5 text-right font-semibold ${
                          row.score < 60 ? "text-rosee" : "text-ink"
                        }`}
                      >
                        {row.score}
                      </td>
                      <td className="px-4 py-2.5 text-right text-ink-soft">
                        {row.classAverage}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableShell>
            </div>
          </>
        ) : (
          <p className="text-[13px] text-ink-soft">
            No exams are recorded for this semester.
          </p>
        )}
      </Panel>

      <Panel
        title="Strengths & Weaknesses by Topic"
        {...(data.topics.length
          ? {
              action: (
                <span className="text-[11px] font-medium text-ink-soft">
                  {topicNote}
                </span>
              ),
            }
          : {})}
      >
        {data.topics.length ? (
          <div style={{ height: Math.max(280, data.topics.length * 40) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.topics}
                layout="vertical"
                margin={{ top: 4, right: 16, bottom: 0, left: 8 }}
              >
                <CartesianGrid stroke={chartColors.grid} horizontal={false} />
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="topic"
                  tick={{ fontSize: 11, fill: chartColors.axis }}
                  axisLine={false}
                  tickLine={false}
                  width={210}
                />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar
                  isAnimationActive={false}
                  dataKey="score"
                  name="Score"
                  radius={[0, 8, 8, 0]}
                  maxBarSize={22}
                >
                  {data.topics.map((t) => (
                    <Cell
                      key={t.topic}
                      fill={
                        t.score >= 75
                          ? chartColors.mint
                          : t.score >= 60
                            ? chartColors.iris
                            : chartColors.rose
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-[13px] text-ink-soft">
            No topic scores this semester.
          </p>
        )}
      </Panel>
    </>
  );
}
