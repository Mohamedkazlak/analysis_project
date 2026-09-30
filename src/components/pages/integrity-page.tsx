import { Link, useParams } from "@tanstack/react-router";
import { AiDecisionSection } from "@/components/ai-insights";
import { ScopeBanner } from "@/components/dashboard/scope-banner";
import { useQuery } from "@tanstack/react-query";
import { getIntegrityReport } from "@/lib/api";
import {
  AiInsight,
  Badge,
  Panel,
  ScreenSkeleton,
  StatBlock,
  TableShell,
  Th,
} from "@/components/dashboard/dashboard-ui";
import { FiltersRequiredNotice } from "@/components/dashboard/analytics-filters";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { useLocale } from "@/lib/i18n";

export function IntegrityPage() {
  const { role } = useParams({ from: "/$role" });
  const { locale, messages } = useLocale();
  const ip = messages.integrityPage;
  const c = messages.common;
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("integrity");
  const { data, isPending } = useQuery({
    queryKey: [...queryKey, locale],
    queryFn: () => getIntegrityReport(filters, locale),
    enabled,
  });
  if (!filtersReady) return <FiltersRequiredNotice />;
  if (isPending || !data) return <ScreenSkeleton cards={3} panels={2} />;

  const multi = data.rows.filter((r) => r.attempts > 1).length;

  return (
    <>
      <ScopeBanner />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatBlock
          label={ip.monitored}
          value={`${data.totalAttempts}`}
          sub={ip.thisPeriod}
        />
        <StatBlock
          label={ip.flagged}
          value={`${data.flaggedCount}`}
          sub={ip.anomalySub}
          tone="rose"
        />
        <StatBlock
          label={ip.multipleAttempts}
          value={`${multi}`}
          sub={ip.multiSub}
          tone="iris"
        />
      </div>

      <AiDecisionSection />

      <Panel title={ip.workflow}>
        <div className="flex flex-wrap items-center gap-3 text-[13px]">
          <span className="rounded-full bg-rose/12 px-3 py-1.5 font-semibold text-rosee">
            {ip.step1}
          </span>
          <span className="text-ink-soft">→</span>
          <span className="rounded-full bg-amber/12 px-3 py-1.5 font-semibold text-amberink">
            {ip.step2}
          </span>
          <span className="text-ink-soft">→</span>
          <span className="rounded-full bg-mint/12 px-3 py-1.5 font-semibold text-mintink">
            {ip.step3}
          </span>
          <Link
            to="/$role/real-time"
            params={{ role }}
            search={{}}
            className="ms-auto text-[12px] font-semibold text-iris underline underline-offset-2"
          >
            {ip.openLive}
          </Link>
        </div>
      </Panel>

      <Panel title={ip.summary}>
        <p className="text-[13px] leading-relaxed text-ink-soft">
          {ip.summaryBody
            .replace("{flagged}", String(data.flaggedCount))
            .replace("{total}", String(data.totalAttempts))
            .replace("{multi}", String(multi))}
        </p>
      </Panel>

      <AiInsight>{data.insight}</AiInsight>

      <Panel title={ip.attemptLog}>
        <TableShell>
          <thead className="bg-iris/8">
            <tr>
              <Th>{c.student}</Th>
              <Th>{c.assessment}</Th>
              <Th>{c.start}</Th>
              <Th>{c.end}</Th>
              <Th>{c.ip}</Th>
              <Th>{c.device}</Th>
              <Th align="right">{c.attempts}</Th>
              <Th align="right">{c.flags}</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {data.rows.map((row) => (
              <tr
                key={row.id}
                className={row.flags.length ? "bg-rose/5" : "bg-white/40"}
              >
                <td className="px-4 py-3 font-semibold text-ink">
                  {row.student}
                </td>
                <td className="px-4 py-3 text-ink-soft">{row.exam}</td>
                <td className="px-4 py-3 text-ink-soft">{row.startedAt}</td>
                <td className="px-4 py-3 text-ink-soft">{row.endedAt}</td>
                <td className="px-4 py-3 font-mono text-[12px] text-ink-soft">
                  {row.ip}
                </td>
                <td className="px-4 py-3 text-ink-soft">{row.device}</td>
                <td className="px-4 py-3 text-end tabular-nums">
                  {row.attempts}
                </td>
                <td className="px-4 py-3 text-end">
                  {row.flags.length ? (
                    <Badge tone="fail">{row.flags.length}</Badge>
                  ) : (
                    <span className="text-ink-soft">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </TableShell>
      </Panel>
    </>
  );
}
