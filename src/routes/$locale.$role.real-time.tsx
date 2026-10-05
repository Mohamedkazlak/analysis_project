import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getRealTimeStruggling } from "@/lib/api";
import { AiDecisionSection } from "@/components/ai-insights";
import { ScopeBanner } from "@/components/dashboard/scope-banner";
import { useRole } from "@/components/role-context";
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
  SearchInput,
} from "@/components/dashboard/dashboard-ui";
import type { StrugglingStudent } from "@/lib/types";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { roleGuard } from "@/lib/auth/role-guards";
import { useLocale, translateOrgName } from "@/lib/i18n";

export const Route = createFileRoute("/$locale/$role/real-time")({
  beforeLoad: roleGuard("/real-time"),
  head: () => ({
    meta: [
      { title: "Live Exam Monitoring — BNU" },
      {
        name: "description",
        content:
          "Live view of in-progress exams and students currently in session.",
      },
      { property: "og:title", content: "Live Exam Monitoring — BNU" },
      {
        property: "og:description",
        content:
          "Live view of in-progress exams and students currently in session.",
      },
    ],
  }),
  component: RealTime,
});

type SortKey = keyof Pick<
  StrugglingStudent,
  "name" | "college" | "lastScore" | "average" | "trend"
>;

function RealTime() {
  const { role } = useRole();
  const { locale, messages } = useLocale();
  const c = messages.common;
  const rt = messages.realTimePage;
  const o = messages.overview;

  const isIntegrity = role === "it_academic_integrity";
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("real-time");
  const { data, isPending, dataUpdatedAt } = useQuery({
    queryKey: [...queryKey, locale],
    queryFn: () => getRealTimeStruggling(filters, locale),
    enabled,
    refetchInterval: 15000,
  });
  const [sortKey, setSortKey] = useState<SortKey>("lastScore");
  const [asc, setAsc] = useState(true);
  const [clock, setClock] = useState("");
  const [course, setCourse] = useState("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    const tick = () =>
      setClock(
        new Date(dataUpdatedAt || Date.now()).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [dataUpdatedAt]);

  if (!filtersReady) return <FiltersRequiredNotice />;
  if (isPending || !data) return <ScreenSkeleton cards={3} panels={2} />;

  const courseOptions = [
    { value: "all", label: messages.filters.allCurriculum },
    ...Array.from(new Set(data.students.map((s) => s.course))).map((c) => ({
      value: c,
      label: c,
    })),
  ];

  const rows = data.students
    .filter(
      (s) =>
        (course === "all" || s.course === course) &&
        s.name.toLowerCase().includes(query.trim().toLowerCase()),
    )
    .sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      const cmp =
        typeof av === "string" && typeof bv === "string"
          ? av.localeCompare(bv)
          : Number(av) - Number(bv);
      return asc ? cmp : -cmp;
    });

  const toggle = (key: SortKey) => {
    if (key === sortKey) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(true);
    }
  };

  const flaggedLive = data.liveExams.reduce((n, e) => n + e.flagged, 0);

  return (
    <>
      <ScopeBanner />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatBlock
          label={rt.inSession}
          value={`${data.activeNow}`}
          sub={rt.sittingsInProgress.replace(
            "{n}",
            String(data.liveExams.length),
          )}
          tone="iris"
        />
        <StatBlock
          label={isIntegrity ? rt.flaggedInSession : rt.struggling}
          value={`${isIntegrity ? flaggedLive : data.students.length}`}
          sub={isIntegrity ? rt.liveAnomalies : rt.belowCohortMean}
          tone="rose"
        />
        <StatBlock
          label={rt.lastUpdated}
          value={clock || "—"}
          sub={rt.autoRefresh}
          tone="mint"
        />
      </div>

      {isIntegrity && (
        <AiDecisionSection role="it_academic_integrity" page="real-time" />
      )}
      {!isIntegrity && <AiDecisionSection page="real-time" />}

      <Panel
        title={
          isIntegrity ? `${rt.liveExams} · ${rt.universityWide}` : rt.liveExams
        }
        action={
          <span className="flex items-center gap-2 text-[11px] font-medium text-ink-soft">
            <span className="size-1.5 animate-pulse rounded-full bg-mint" />{" "}
            {rt.liveClock.replace("{clock}", clock)}
          </span>
        }
      >
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>{c.exam}</Th>
              <Th>{o.college}</Th>
              <Th align="right">{rt.active}</Th>
              <Th align="right">{rt.submitted}</Th>
              <Th align="right">{rt.expected}</Th>
              <Th align="right">{rt.flaggedCol}</Th>
              <Th align="right">{c.status}</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {data.liveExams.map((exam) => (
              <tr
                key={exam.examId}
                className={exam.flagged > 0 ? "bg-rose/5" : "bg-white/40"}
              >
                <td className="px-4 py-3 font-semibold text-ink">
                  {exam.exam}
                </td>
                <td className="px-4 py-3 text-ink-soft">
                  {translateOrgName(exam.program, locale)}
                </td>
                <td className="px-4 py-3 text-right font-semibold text-ink">
                  {exam.activeNow}
                </td>
                <td className="px-4 py-3 text-right text-ink-soft">
                  {exam.submitted}
                </td>
                <td className="px-4 py-3 text-right text-ink-soft">
                  {exam.expected}
                </td>
                <td className="px-4 py-3 text-right">
                  {exam.flagged > 0 ? (
                    <Badge tone="fail">{exam.flagged}</Badge>
                  ) : (
                    <Badge tone="pass">0</Badge>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <Badge tone={exam.status === "Closing" ? "warn" : "neutral"}>
                    {exam.status === "Closing"
                      ? rt.statusClosing
                      : rt.statusInProgress}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>

      {!isIntegrity && (
        <Panel
          title={rt.strugglingTitle}
          action={
            <FilterBar>
              <SearchInput
                value={query}
                onChange={setQuery}
                placeholder={c.findStudent}
              />
              <Select
                label={messages.filters.curriculum}
                value={course}
                options={courseOptions}
                onChange={setCourse}
              />
            </FilterBar>
          }
        >
          <TableShell>
            <thead className="bg-iris/8">
              <tr>
                <Th onClick={() => toggle("name")}>{c.student}</Th>
                <Th onClick={() => toggle("college")}>{o.college}</Th>
                <Th>{c.course}</Th>
                <Th onClick={() => toggle("lastScore")}>{rt.lastScore}</Th>
                <Th onClick={() => toggle("average")} align="right">
                  {c.average}
                </Th>
                <Th onClick={() => toggle("trend")} align="right">
                  {c.trend}
                </Th>
                <Th align="right">{rt.lastActivity}</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/5">
              {rows.map((row) => (
                <tr
                  key={row.studentId}
                  className={row.lastScore < 60 ? "bg-rose/5" : "bg-white/40"}
                >
                  <td className="px-4 py-3 font-semibold text-ink">
                    {row.name}
                  </td>
                  <td className="px-4 py-3 text-ink-soft">
                    {row.college ? translateOrgName(row.college, locale) : "—"}
                  </td>
                  <td className="px-4 py-3 text-ink-soft">{row.course}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Meter
                        value={row.lastScore}
                        tone={row.lastScore < 60 ? "rose" : "amber"}
                      />
                      <span className="font-semibold text-ink">
                        {row.lastScore}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right text-ink-soft">
                    {row.average}
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-semibold ${row.trend >= 0 ? "text-mintink" : "text-rosee"}`}
                  >
                    {row.trend >= 0 ? "▲" : "▼"} {Math.abs(row.trend)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Badge tone="neutral">
                      {row.lastActivity === "recently"
                        ? rt.recently
                        : row.lastActivity}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        </Panel>
      )}

      <AiInsight>{data.insight}</AiInsight>
    </>
  );
}
