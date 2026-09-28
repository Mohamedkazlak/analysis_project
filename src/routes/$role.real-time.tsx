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

export const Route = createFileRoute("/$role/real-time")({
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
  "name" | "lastScore" | "average" | "trend"
>;

function RealTime() {
  const { role } = useRole();
  const isIntegrity = role === "it_academic_integrity";
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("real-time");
  const { data, isPending, dataUpdatedAt } = useQuery({
    queryKey,
    queryFn: () => getRealTimeStruggling(filters),
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
    { value: "all", label: "All curriculums" },
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
          label="Active now"
          value={`${data.activeNow}`}
          sub={`${data.liveExams.length} sittings in progress`}
          tone="iris"
        />
        <StatBlock
          label={isIntegrity ? "Flagged in session" : "Struggling"}
          value={`${isIntegrity ? flaggedLive : data.students.length}`}
          sub={
            isIntegrity ? "Live anomalies" : "Recent score below cohort mean"
          }
          tone="rose"
        />
        <StatBlock
          label="Last updated"
          value={clock || "—"}
          sub="Auto-refreshes every 15s"
          tone="mint"
        />
      </div>

      {isIntegrity && <AiDecisionSection role="it_academic_integrity" />}

      <Panel
        title={
          isIntegrity
            ? "Live exams · university-wide"
            : "Live sittings · my curriculum"
        }
        action={
          <span className="flex items-center gap-2 text-[11px] font-medium text-ink-soft">
            <span className="size-1.5 animate-pulse rounded-full bg-mint" />{" "}
            Live · {clock}
          </span>
        }
      >
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>Exam</Th>
              <Th>College</Th>
              <Th align="right">Active</Th>
              <Th align="right">Submitted</Th>
              <Th align="right">Expected</Th>
              <Th align="right">Flagged</Th>
              <Th align="right">Status</Th>
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
                <td className="px-4 py-3 text-ink-soft">{exam.program}</td>
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
                    {exam.status}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>

      {!isIntegrity && (
        <Panel
          title="Students currently struggling"
          action={
            <FilterBar>
              <SearchInput
                value={query}
                onChange={setQuery}
                placeholder="Find a student…"
              />
              <Select
                label="Curriculum"
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
                <Th onClick={() => toggle("name")}>Student</Th>
                <Th>Course</Th>
                <Th onClick={() => toggle("lastScore")}>Latest score</Th>
                <Th onClick={() => toggle("average")} align="right">
                  Average
                </Th>
                <Th onClick={() => toggle("trend")} align="right">
                  Trend
                </Th>
                <Th align="right">Last activity</Th>
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
                    <Badge tone="neutral">{row.lastActivity}</Badge>
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
