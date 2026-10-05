import { createFileRoute } from "@tanstack/react-router";
import { AiDecisionSection } from "@/components/ai-insights";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getItemAnalysis } from "@/lib/api";
import {
  AiInsight,
  Badge,
  Meter,
  Panel,
  ScreenSkeleton,
  StatBlock,
  TableShell,
  Th,
  FilterBar,
  Select,
  Toggle,
  chartColors,
  tooltipStyle,
} from "@/components/dashboard/dashboard-ui";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { roleGuard } from "@/lib/auth/role-guards";
import { ScopeBanner } from "@/components/dashboard/scope-banner";
import { useLocale } from "@/lib/i18n";
import {
  AxisValueTick,
  MirroredChart,
  tooltipMirrorStyle,
} from "@/components/dashboard/chart-rtl";

export const Route = createFileRoute("/$locale/$role/item-analysis")({
  beforeLoad: roleGuard("/item-analysis"),
  head: () => ({
    meta: [
      { title: "Item Analysis Reports — BNU" },
      {
        name: "description",
        content:
          "Per-question correct rates, difficulty index, discrimination index and flagged items needing review.",
      },
      { property: "og:title", content: "Item Analysis Reports — BNU" },
      {
        property: "og:description",
        content:
          "Per-question correct rates, difficulty index, discrimination index and flagged items needing review.",
      },
    ],
  }),
  component: ItemAnalysis,
});

function ItemAnalysis() {
  const { locale, messages } = useLocale();
  const rtl = locale === "ar";
  const c = messages.common;
  const ia = messages.itemAnalysisPage;
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("item-analysis");
  const { data, isPending } = useQuery({
    queryKey: [...queryKey, locale],
    queryFn: () => getItemAnalysis(filters, locale),
    enabled,
  });
  const [examFilter, setExamFilter] = useState<string>("all");
  const [topicFilter, setTopicFilter] = useState<string>("all");
  const [flaggedOnly, setFlaggedOnly] = useState(false);

  if (!filtersReady) return <FiltersRequiredNotice />;
  if (isPending || !data) return <ScreenSkeleton cards={3} panels={3} />;

  const examOptions = Array.from(new Set(data.questions.map((q) => q.exam)));
  const topicOptions = [
    { value: "all", label: c.allTopics },
    ...Array.from(new Set(data.questions.map((q) => q.topic))).map((t) => ({
      value: t,
      label: t,
    })),
  ];
  const rows = data.questions.filter(
    (q) =>
      (examFilter === "all" || q.exam === examFilter) &&
      (topicFilter === "all" || q.topic === topicFilter) &&
      (!flaggedOnly || q.flagged),
  );
  const qPrefix = c.questionShort;
  const chartRows = rows.slice(0, 12).map((q) => ({
    label: `${qPrefix}${q.number}`,
    correct: q.pctCorrect,
    flagged: q.flagged,
  }));
  const avgCorrect = rows.length
    ? (rows.reduce((a, b) => a + b.pctCorrect, 0) / rows.length).toFixed(1)
    : "—";
  const avgDiscrim = rows.length
    ? (
        rows.reduce((a, b) => a + b.discriminationIndex, 0) / rows.length
      ).toFixed(2)
    : "—";

  return (
    <>
      <ScopeBanner />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatBlock
          label={ia.itemsAnalysed}
          value={`${rows.length}`}
          sub={examFilter === "all" ? c.allAssessments : examFilter}
        />
        <StatBlock
          label={ia.avgCorrect}
          value={avgCorrect === "—" ? "—" : `${avgCorrect}%`}
          sub={ia.acrossSelected}
          tone="iris"
        />
        <StatBlock
          label={ia.meanDiscrimination}
          value={avgDiscrim}
          sub={ia.discrimHealthy}
          tone="mint"
        />
      </div>

      <AiDecisionSection page="item-analysis" />

      <Panel
        title={ia.correctPerQuestion}
        action={
          <FilterBar>
            <Select
              label={c.assessment}
              value={examFilter}
              options={[
                { value: "all", label: c.allAssessments },
                ...examOptions.map((e) => ({ value: e, label: e })),
              ]}
              onChange={setExamFilter}
            />
            <Select
              label={c.topic}
              value={topicFilter}
              options={topicOptions}
              onChange={setTopicFilter}
            />
            <Toggle
              label={c.flaggedOnly}
              checked={flaggedOnly}
              onChange={setFlaggedOnly}
            />
          </FilterBar>
        }
      >
        <MirroredChart rtl={rtl} height={256}>
          <BarChart
            data={chartRows}
            margin={{ top: 8, right: 8, bottom: 0, left: -18 }}
          >
            <CartesianGrid stroke={chartColors.grid} vertical={false} />
            <XAxis
              dataKey="label"
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
              formatter={(v: number) => `${v}%`}
            />
            <Bar
              isAnimationActive={false}
              dataKey="correct"
              name={ia.pctCorrect}
              radius={[8, 8, 0, 0]}
              maxBarSize={38}
            >
              {chartRows.map((row) => (
                <Cell
                  key={row.label}
                  fill={row.flagged ? chartColors.rose : chartColors.iris}
                />
              ))}
            </Bar>
          </BarChart>
        </MirroredChart>
      </Panel>

      <AiInsight>{data.insight}</AiInsight>

      <Panel
        title={ia.needingReview}
        action={
          <Badge tone="warn">
            {ia.flaggedCount.replace("{n}", String(data.needsReview.length))}
          </Badge>
        }
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {data.needsReview.map((q) => (
            <div
              key={q.id}
              className="rounded-2xl border border-amber/30 bg-amber/6 p-4"
            >
              <div className="flex items-center justify-between">
                <div className="font-display text-[13px] font-bold text-ink">
                  {qPrefix}
                  {q.number} · {q.exam}
                </div>
                <Badge tone="warn">D {q.discriminationIndex}</Badge>
              </div>
              <p className="mt-1.5 text-[12px] text-ink-soft">{q.prompt}</p>
              <div className="mt-2 text-[11px] font-semibold text-amberink">
                {ia.correctTopic
                  .replace("{pct}", String(q.pctCorrect))
                  .replace("{topic}", q.topic)}
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title={ia.fullTable}>
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>{c.question}</Th>
              <Th>{c.assessment}</Th>
              <Th>{c.topic}</Th>
              <Th>{ia.pctCorrect}</Th>
              <Th align="right">{ia.pctIncorrect}</Th>
              <Th>{c.difficulty}</Th>
              <Th>{c.discrimination}</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {rows.map((q) => (
              <tr
                key={q.id}
                className={q.flagged ? "bg-rose/5" : "bg-white/40"}
              >
                <td className="px-4 py-3 font-semibold text-ink">
                  {qPrefix}
                  {q.number}
                </td>
                <td className="px-4 py-3 text-ink-soft">{q.exam}</td>
                <td className="px-4 py-3 text-ink-soft">{q.topic}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Meter
                      value={q.pctCorrect}
                      tone={q.flagged ? "rose" : "cyan"}
                    />
                    <span className="font-semibold text-ink">
                      {q.pctCorrect}%
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3 text-right text-ink-soft">
                  {q.pctIncorrect}%
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Meter value={q.difficultyIndex * 100} tone="amber" />
                    <span className="text-ink-soft">
                      {q.difficultyIndex.toFixed(2)}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Meter
                      value={Math.max(0, q.discriminationIndex) * 140}
                      tone={q.discriminationIndex < 0.15 ? "rose" : "mint"}
                    />
                    <span
                      className={
                        q.discriminationIndex < 0.15
                          ? "font-semibold text-rosee"
                          : "text-ink-soft"
                      }
                    >
                      {q.discriminationIndex.toFixed(2)}
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
