import { AiDecisionSection } from "@/components/ai-insights";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
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
import {
  AxisValueTick,
  CategoryTick,
  ChartLegend,
  MirroredChart,
  tooltipMirrorStyle,
} from "@/components/dashboard/chart-rtl";
import { useRole } from "@/components/role-context";
import {
  useLocale,
  translateOrgName,
  translateTermName,
  translateTopicName,
} from "@/lib/i18n";

export function MyProgressPage() {
  const { user } = useRole();
  const { locale, messages } = useLocale();
  const rtl = locale === "ar";
  const mp = messages.myProgressPage;
  const c = messages.common;
  const { data, isPending } = useQuery({
    queryKey: ["student-dashboard", user.id],
    queryFn: () => getStudentDashboard(),
  });
  if (isPending || !data) return <ScreenSkeleton cards={5} panels={2} />;

  const delta = data.average - data.classAverage;
  const deltaSigned = `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}`;
  const termLabel = translateTermName(data.termName, locale);
  const deltaLabel = mp.vsClass
    .replace("{delta}", deltaSigned)
    .replace("{avg}", String(data.classAverage));
  const topicNote =
    data.topicsFrom === "courses" ? mp.courseScoresNote : mp.questionTopicsNote;
  const localizeTopic = (name: string) => {
    if (!name || name === "None") return mp.none;
    return translateTopicName(name, locale);
  };
  const topics = data.topics.map((row) => ({
    ...row,
    topic: localizeTopic(row.topic),
  }));

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatBlock
          label={mp.college}
          value={translateOrgName(data.college, locale)}
          {...(data.sector
            ? { sub: translateOrgName(data.sector, locale) }
            : {})}
          tone="iris"
          valueClassName="text-2xl leading-snug"
        />
        <StatBlock
          label={mp.thisSemester}
          value={data.scoreTimeline.length ? `${data.average}` : "—"}
          sub={
            data.scoreTimeline.length
              ? `${termLabel ? `${termLabel} · ` : ""}${deltaLabel}`
              : mp.noExamsSemester
          }
          tone="iris"
        />
        <StatBlock
          label={mp.allYearsAverage}
          value={data.overallAverage == null ? "—" : `${data.overallAverage}`}
          sub={mp.allYearsSub}
          tone="iris"
        />
        <StatBlock
          label={mp.gpa}
          value={data.gpa == null ? "—" : data.gpa.toFixed(2)}
          sub={data.gpa == null ? mp.gpaEmpty : mp.gpaSub}
          tone="mint"
        />
        <StatBlock
          label={mp.strongestTopic}
          value={localizeTopic(data.bestTopic)}
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
          label={mp.weakestTopic}
          value={localizeTopic(data.weakestTopic)}
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

      <AiDecisionSection role="student" page="my-progress" />

      <Panel
        title={
          termLabel
            ? mp.examScoresTerm.replace("{term}", termLabel)
            : mp.examScoresSemester
        }
      >
        {data.scoreTimeline.length ? (
          <>
            <MirroredChart rtl={rtl} height={288}>
              <LineChart
                data={data.scoreTimeline}
                margin={{ top: 8, right: 20, bottom: 0, left: -8 }}
              >
                <CartesianGrid stroke={chartColors.grid} vertical={false} />
                <XAxis
                  dataKey="chartLabel"
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
                  padding={{ left: 12, right: 12 }}
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
                />
                <Line
                  isAnimationActive={false}
                  type="monotone"
                  dataKey="score"
                  name={mp.myScore}
                  stroke={chartColors.iris}
                  strokeWidth={2.5}
                />
                <Line
                  type="monotone"
                  dataKey="classAverage"
                  name={mp.classAverage}
                  stroke={chartColors.cyan}
                  strokeWidth={2}
                  strokeDasharray="5 4"
                />
              </LineChart>
            </MirroredChart>
            <ChartLegend
              items={[
                { label: mp.myScore, color: chartColors.iris },
                { label: mp.classAverage, color: chartColors.cyan },
              ]}
            />
            <div className="mt-4">
              <TableShell>
                <thead>
                  <tr className="border-b border-black/5">
                    <Th>{c.course}</Th>
                    <Th>{c.exam}</Th>
                    <Th align="right">{mp.myScore}</Th>
                    <Th align="right">{mp.classAverage}</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.scoreTimeline.map((row) => (
                    <tr
                      key={`${row.courseCode}-${row.exam}`}
                      className="border-b border-black/5 last:border-0"
                    >
                      <td className="px-4 py-2.5">
                        <div className="font-semibold">
                          {translateTopicName(row.course, locale)}
                        </div>
                        <div className="text-[11px] text-ink-soft">
                          {row.courseCode}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-ink-soft">{row.exam}</td>
                      <td
                        className={`px-4 py-2.5 text-end font-semibold ${
                          row.score < 60 ? "text-rosee" : "text-ink"
                        }`}
                      >
                        {row.score}
                      </td>
                      <td className="px-4 py-2.5 text-end text-ink-soft">
                        {row.classAverage}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableShell>
            </div>
          </>
        ) : (
          <p className="text-[13px] text-ink-soft">{mp.noExamsRecorded}</p>
        )}
      </Panel>

      <Panel
        title={mp.strengthsByTopic}
        {...(topics.length
          ? {
              action: (
                <span className="text-[11px] font-medium text-ink-soft">
                  {topicNote}
                </span>
              ),
            }
          : {})}
      >
        {topics.length ? (
          <MirroredChart rtl={rtl} height={Math.max(280, topics.length * 40)}>
            <BarChart
              data={topics}
              layout="vertical"
              margin={{ top: 4, right: 16, bottom: 0, left: 8 }}
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
                  />
                )}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="topic"
                tick={(props) => (
                  <CategoryTick {...props} mirror={rtl} limit={22} />
                )}
                axisLine={false}
                tickLine={false}
                width={rtl ? 150 : 180}
                interval={0}
              />
              <Tooltip
                contentStyle={tooltipStyle}
                wrapperStyle={tooltipMirrorStyle(rtl)}
              />
              <Bar
                isAnimationActive={false}
                dataKey="score"
                name={mp.score}
                radius={[0, 8, 8, 0]}
                maxBarSize={22}
              >
                {topics.map((t) => (
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
          </MirroredChart>
        ) : (
          <p className="text-[13px] text-ink-soft">{mp.noTopicScores}</p>
        )}
      </Panel>
    </>
  );
}
