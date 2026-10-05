import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ChevronDown,
  CircleCheck,
  Lightbulb,
  TrendingDown,
  TrendingUp,
  Minus,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import type { Role } from "@/lib/types";
import { aiConfig, AI_PAGE_LABELS, type AiPage } from "@/lib/ai/config";
import {
  getAiDecision,
  type AiWarning,
  type EvidenceMetric,
  type Insight,
  type Prediction,
  type RiskCase,
} from "@/lib/ai/insights";
import type { Recommendation } from "@/lib/ai/recommendations";
import { useRole } from "./role-context";
import { useFilteredQuery } from "@/components/dashboard/use-analytics-filters";
import { ROLE_SLUG, roleRouteTo } from "@/lib/auth/role-guards";
import { useLocale, translateOrgName } from "@/lib/i18n";
import { openChat } from "@/lib/chat-bus";

export function AiFrame({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-[1.75rem] border border-ai/25 bg-gradient-to-br from-white/90 via-violet/8 to-cyan/10 p-6 shadow-[0_18px_50px_-28px_rgba(79,70,229,0.45)] backdrop-blur-xl sm:p-7">
      <div className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-2xl bg-ai/12 text-ai">
          <Lightbulb className="size-4" strokeWidth={2.4} />
        </span>
        <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-ai">
          {label}
        </span>
      </div>
      {children}
    </section>
  );
}

function AiSkeleton({ label }: { label: string }) {
  return (
    <AiFrame label={label}>
      <div className="mt-3 space-y-2.5">
        <div className="h-4 w-2/3 animate-pulse rounded-full bg-ai/15" />
        <div className="h-3 w-full animate-pulse rounded-full bg-ai/10" />
        <div className="h-3 w-4/5 animate-pulse rounded-full bg-ai/10" />
        <div className="h-8 w-40 animate-pulse rounded-full bg-ai/10" />
      </div>
    </AiFrame>
  );
}

function AiAction({ label, to }: { label: string; to: string }) {
  const { role } = useRole();
  const { locale } = useLocale();
  return (
    <Link
      to={roleRouteTo(to)}
      params={{ locale, role: ROLE_SLUG[role] }}
      search={{}}
      className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-ai px-4 py-2 text-[12px] font-semibold text-white shadow-lg shadow-ai/25 transition-opacity hover:opacity-90"
    >
      {label} <span aria-hidden>→</span>
    </Link>
  );
}

const levelTone = {
  High: "bg-rose/12 text-rosee",
  Medium: "bg-amber/12 text-amberink",
  Low: "bg-mint/12 text-mintink",
} as const;

function RiskCaseRow({ item }: { item: RiskCase }) {
  const [open, setOpen] = useState(false);
  const { messages } = useLocale();
  return (
    <div className="rounded-2xl border border-white/70 bg-white/65 p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[13px] font-semibold text-ink">
            {item.subject}
          </div>
          <div className="text-[11px] text-ink-soft">{item.exam}</div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "rounded-full px-2.5 py-1 text-[11px] font-semibold",
              levelTone[item.level],
            )}
          >
            {item.level} · {item.score}/100
          </span>
          <button
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="inline-flex items-center gap-1 rounded-full border border-ai/40 px-2.5 py-1 text-[11px] font-semibold text-ai"
          >
            {messages.ai.why}
            <ChevronDown
              className={cn(
                "size-3.5 transition-transform",
                open && "rotate-180",
              )}
            />
          </button>
        </div>
      </div>
      {open && (
        <ul className="mt-3 space-y-2 border-t border-black/5 pt-3">
          {item.evidence.map((e) => (
            <li
              key={e.label}
              className="flex items-start justify-between gap-3 text-[12px]"
            >
              <span>
                <span className="font-semibold text-ink">{e.label}</span>
                <span className="text-ink-soft"> — {e.detail}</span>
              </span>
              <span className="shrink-0 font-semibold text-ai">
                +{e.weight}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const dirIcon = { rising: TrendingUp, falling: TrendingDown, stable: Minus };
const toneClass = {
  mint: "text-mintink",
  amber: "text-amberink",
  rose: "text-rosee",
  iris: "text-iris",
};

/** Compact inline standing or forecast strip. Values come from the decision payload. */
export function AiPrediction({ data }: { data: Prediction }) {
  const { messages } = useLocale();
  const Icon = dirIcon[data.direction];
  const heading =
    data.kind === "forecast" ? data.title : data.title || messages.ai.standing;
  return (
    <div className="mt-3 rounded-2xl border border-white/70 bg-white/55 px-3.5 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <Icon
          className={cn(
            "size-4",
            data.direction === "falling"
              ? "text-rosee"
              : data.direction === "rising"
                ? "text-amberink"
                : "text-ink-soft",
          )}
          strokeWidth={2.4}
        />
        <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-ink-soft">
          {heading}
        </span>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {data.rows.map((row) => (
            <span key={row.label} className="text-[11.5px]">
              <span className="text-ink-soft">{row.label} </span>
              <span className={cn("font-semibold", toneClass[row.tone])}>
                {row.value}
              </span>
            </span>
          ))}
        </div>
      </div>
      {data.summary ? (
        <p className="mt-1.5 text-[11px] leading-relaxed text-ink-soft">
          {data.summary}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Recommended actions
 * ------------------------------------------------------------------ */

function BasedOn({ item }: { item: Recommendation }) {
  const [open, setOpen] = useState(false);
  const { messages } = useLocale();
  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 text-[11px] font-semibold text-ai/90 underline decoration-ai/30 underline-offset-2"
      >
        {messages.ai.basedOn}
        <ChevronDown
          className={cn("size-3 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <div className="mt-2 rounded-2xl bg-white/70 p-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-soft">
            {item.basedOn.source}
          </div>
          <ul className="mt-1.5 space-y-1">
            {item.basedOn.evidence.map((e) => (
              <li key={e.label} className="text-[12px] leading-relaxed">
                <span className="font-semibold text-ink">{e.label}</span>
                <span className="text-ink-soft"> — {e.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** AI proposes, a human approves: every action button lands here first. */
export interface ConfirmAction {
  label: string;
  to?: string;
  confirmTitle: string;
  confirmBody: string;
  confirmLabel: string;
}

export function ConfirmDialog({
  action,
  onClose,
}: {
  action: ConfirmAction;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const { role } = useRole();
  const { locale, messages } = useLocale();
  function confirm() {
    onClose();
    if (action.to) {
      void navigate({
        to: roleRouteTo(action.to),
        params: { locale, role: ROLE_SLUG[role] },
        search: {},
      });
      return;
    }
    toast.success(
      action.confirmLabel === "Export"
        ? "Report queued for export"
        : "Done — nothing was sent automatically",
    );
  }
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-ink/30 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
    >
      <div className="w-full max-w-md rounded-3xl border-2 border-ai/50 bg-white p-5 shadow-2xl">
        <h4 className="font-display text-[16px] font-bold text-ink">
          {action.confirmTitle}
        </h4>
        <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">
          {action.confirmBody}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-full border border-black/10 px-4 py-2 text-[12px] font-semibold text-ink"
          >
            {messages.ai.cancel}
          </button>
          <button
            onClick={confirm}
            className="rounded-full bg-ai px-4 py-2 text-[12px] font-semibold text-white shadow-lg shadow-ai/25"
          >
            {action.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * The single merged decision card
 * ------------------------------------------------------------------ */

/**
 * One combined read: headline finding, current standing and ranked actions.
 * Role/scope come from the verified JWT on the server. The `role` prop only
 * controls which panels this client renders.
 */

export function AiEvidence({ metrics }: { metrics: EvidenceMetric[] }) {
  const [open, setOpen] = useState(false);
  const { locale, messages } = useLocale();
  if (!metrics.length) return null;
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-[11px] font-semibold text-ai"
      >
        {messages.ai.basedOn}
        <ChevronDown
          className={cn("size-3.5 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5">
          {metrics.slice(0, 6).map((metric) => (
            <li key={metric.id} className="text-[12px] text-ink-soft">
              <span className="font-semibold text-ink">
                {translateOrgName(metric.entity || metric.name, locale)}
              </span>
              {" · "}
              {metric.name.replace(/_/g, " ")} {metric.value}
              {metric.unit === "percent" ? "%" : ""}
              {metric.comparison?.scopeAverage != null
                ? ` · ${messages.ai.scopeAverage} ${metric.comparison.scopeAverage}`
                : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AiWarnings({
  warnings,
}: {
  warnings: { id: string; text: string; tone: "amber" | "rose" }[];
}) {
  const { messages } = useLocale();
  return (
    <div className="mt-4 space-y-2">
      <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-amberink">
        {messages.ai.warnings}
      </div>
      {warnings.map((w) => (
        <div
          key={w.id}
          className={cn(
            "flex items-start gap-2 rounded-2xl px-3.5 py-2.5 text-[12.5px] font-medium",
            w.tone === "rose"
              ? "bg-rose/10 text-rosee"
              : "bg-amber/12 text-amberink",
          )}
        >
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" strokeWidth={2.2} />
          <span>{w.text}</span>
        </div>
      ))}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 text-[11px] font-bold uppercase tracking-[0.16em] text-ink-soft">
      {children}
    </div>
  );
}

function simplifyAlertText(text: string): string {
  return text
    .replace(/\s*below the [\d.]+%?\s*review threshold\.?/gi, "")
    .replace(/\s*below the [\d.]+%?\s*threshold\.?/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function shortForecastCopy(
  status: {
    kind: string;
    message?: string;
    value?: number | null;
    low?: number | null;
    high?: number | null;
  },
  copy: {
    outlook: string;
    standing: string;
    nextPeriodEstimate: string;
    likelyRange: string;
    notEnoughHistory: string;
    showingCurrentNotForecast: string;
  },
): { title: string; body: string } {
  if (status.kind === "forecast" && status.value != null) {
    const range =
      status.low != null && status.high != null
        ? copy.likelyRange
            .replace("{low}", String(status.low))
            .replace("{high}", String(status.high))
        : "";
    return {
      title: copy.outlook,
      body: `${copy.nextPeriodEstimate.replace("{value}", String(status.value))}${range}`,
    };
  }
  if (status.kind === "insufficient") {
    return {
      title: copy.outlook,
      body: copy.notEnoughHistory,
    };
  }
  return {
    title: copy.standing,
    body: copy.showingCurrentNotForecast,
  };
}

function ExecutiveActions({
  cardId,
  slice,
  whatIfQuestion,
}: {
  cardId: string;
  slice: Record<string, string | null | undefined>;
  whatIfQuestion?: string;
}) {
  const { messages } = useLocale();
  const chips = [
    {
      label: messages.ai.askAi,
      question: messages.ai.explainMainFinding,
      primary: true,
    },
    {
      label: messages.ai.whatIf,
      question: whatIfQuestion || messages.ai.whatIfWeakest,
      primary: false,
    },
    {
      label: messages.ai.whyQuestion,
      question: messages.ai.whyDoesThisMatter,
      primary: false,
    },
  ];
  return (
    <div className="mt-5 flex flex-wrap gap-2">
      {chips.map((c) => (
        <button
          key={c.label}
          type="button"
          onClick={() =>
            openChat({
              context: "AI analysis",
              question: c.question,
              cardId,
              slice,
            })
          }
          className={cn(
            "rounded-full px-3.5 py-2 text-[12px] font-semibold transition-all duration-150 active:scale-95",
            c.primary
              ? "bg-ai text-white shadow-lg shadow-ai/25 hover:opacity-90"
              : "border border-ai/30 bg-white/70 text-ai hover:bg-ai/5",
          )}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}

export function AiRecommendations({
  items,
  onAction,
}: {
  items: Recommendation[];
  onAction: (item: Recommendation) => void;
}) {
  const { messages } = useLocale();
  return (
    <div className="mt-5">
      <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-ai">
        {messages.ai.recommendedActions}
      </div>
      {items.length === 0 ? (
        <p className="mt-2 text-[13px] text-ink-soft">
          {messages.ai.noActions}
        </p>
      ) : (
        <ul className="mt-3 space-y-2.5">
          {items.map((item) => {
            const Icon = item.kind === "action" ? CircleCheck : AlertCircle;
            return (
              <li key={item.id} className="rounded-2xl bg-white/60 p-3.5">
                <div className="flex flex-wrap items-start gap-3">
                  <Icon
                    className={cn(
                      "mt-0.5 size-4 shrink-0",
                      item.kind === "action" ? "text-ai" : "text-amberink",
                    )}
                    strokeWidth={2.2}
                  />
                  <div className="min-w-0 flex-1 basis-48">
                    <p className="text-[13px] font-medium leading-relaxed text-ink">
                      {item.text}
                    </p>
                    <BasedOn item={item} />
                  </div>
                  {item.action && (
                    <button
                      onClick={() => onAction(item)}
                      className="mt-0.5 shrink-0 rounded-full bg-ai px-3.5 py-1.5 text-[11px] font-semibold text-white shadow-lg shadow-ai/25 transition-opacity hover:opacity-90"
                    >
                      {item.action.label}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export function AiDecisionCard({
  role: roleProp,
  insightId,
  page = "overview",
}: {
  role?: Role;
  insightId?: string;
  page?: AiPage;
}) {
  const { role: contextRole, user } = useRole();
  const { locale, messages } = useLocale();
  const role = roleProp ?? contextRole;
  const traceId = insightId ?? `insight-${page}-${role}-${user.id}`;
  const [pendingItem, setPendingItem] = useState<Recommendation | null>(null);
  const [showAllImpact, setShowAllImpact] = useState(false);
  const [showAllAlerts, setShowAllAlerts] = useState(false);
  const { filters, filtersReady, queryKey, enabled } = useFilteredQuery(
    `ai-decision-${page}`,
  );
  const { data, isPending } = useQuery({
    queryKey: [...queryKey, role, traceId, locale, page],
    queryFn: () => getAiDecision(filters, locale, page),
    enabled,
    retry: false,
    staleTime: 30_000,
    refetchInterval: (query) =>
      query.state.data?.narrationStatus === "pending" ? 4000 : false,
  });

  const label =
    data?.pageLabel ||
    AI_PAGE_LABELS[page] ||
    (role === "student" ? messages.ai.recommendations : messages.ai.decision);

  if (!filtersReady) return null;
  if (isPending) return <AiSkeleton label={label} />;

  if (data?.status === "timeout" || data?.status === "unavailable") {
    return (
      <AiFrame label={label}>
        <p className="mt-2 text-[13px] text-ink-soft">
          {data.message ||
            (data.status === "timeout"
              ? messages.ai.timeout
              : messages.ai.unavailable)}
        </p>
      </AiFrame>
    );
  }

  const insight = aiConfig.showInsights[role] ? (data?.insight ?? null) : null;
  const prediction = aiConfig.showPredictions[role]
    ? (data?.prediction ?? null)
    : null;
  const recommendations = data?.recommendations?.items ?? [];
  const evidence = data?.evidence ?? [];
  const warnings: AiWarning[] | Insight["warnings"] =
    data?.warnings ?? insight?.warnings ?? [];
  const narrative = data?.narrative;
  const impactItems = data?.impactItems ?? [];
  const ruleAlerts = data?.ruleAlerts ?? [];
  const anomalies = data?.anomalies ?? [];
  const forecastStatus = data?.forecastStatus;
  const evidenceQuality = data?.evidenceQuality;
  const slice = {
    sectorId: filters.sectorId,
    collegeId: filters.collegeId,
    curriculumId: filters.curriculumId,
    studentId: filters.studentId,
    professorId: filters.professorId,
  };
  const scopeParts = [
    filters.curriculumId
      ? `${messages.ai.scopeCourse} · ${filters.curriculumId}`
      : filters.collegeId
        ? `${messages.ai.scopeCollege} · ${translateOrgName(filters.collegeId, locale)}`
        : filters.sectorId
          ? `${messages.ai.scopeSector} · ${translateOrgName(filters.sectorId, locale)}`
          : messages.ai.scopeUniversity,
  ];
  const courseMatch = impactItems[0]?.issue?.match(/^(?:Course|مقرر)\s+(.+)$/i);
  const whatIfQuestion = courseMatch?.[1]
    ? messages.ai.whatIfCourse.replace("{course}", courseMatch[1])
    : messages.ai.whatIfWeakest;

  if (!insight && recommendations.length === 0 && !prediction && !narrative)
    return (
      <AiFrame label={label}>
        <p className="mt-2 text-[13px] text-ink-soft">
          {data?.dataStatus === "insufficient"
            ? messages.ai.insufficient
            : messages.ai.empty}
        </p>
      </AiFrame>
    );

  const showWarnings =
    aiConfig.showWarnings[role] && (warnings?.length ?? 0) > 0;
  const headline = narrative?.headline || insight?.headline;
  const story = narrative?.story || insight?.body;

  const topImpact = showAllImpact
    ? impactItems.slice(0, 5)
    : impactItems.slice(0, 3);
  const topAlerts = showAllAlerts
    ? ruleAlerts.slice(0, 6)
    : ruleAlerts.slice(0, 3);
  const topAnomalies = anomalies.slice(0, 2);
  const topRecs = recommendations.slice(0, 3);
  const outlook = forecastStatus
    ? shortForecastCopy(forecastStatus, {
        outlook: messages.ai.outlook,
        standing: messages.ai.standing,
        nextPeriodEstimate: messages.ai.nextPeriodEstimate,
        likelyRange: messages.ai.likelyRange,
        notEnoughHistory: messages.ai.notEnoughHistory,
        showingCurrentNotForecast: messages.ai.showingCurrentNotForecast,
      })
    : null;

  return (
    <AiFrame label={label}>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-ink-soft">
        <span className="rounded-full bg-white/80 px-2.5 py-1 font-medium text-ink">
          {scopeParts.join(" · ")}
        </span>
        {evidenceQuality?.label && (
          <span className="rounded-full bg-mint/10 px-2.5 py-1 font-medium text-mintink">
            {evidenceQuality.label}
          </span>
        )}
      </div>

      {headline && (
        <div className="mt-5">
          <h3 className="font-display text-[1.35rem] font-bold leading-snug text-ink sm:text-[1.5rem]">
            {headline}
          </h3>
          {story && (
            <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-ink-soft">
              {story}
            </p>
          )}
        </div>
      )}

      {!headline && insight?.body && (
        <p className="mt-5 max-w-3xl text-[15px] leading-relaxed text-ink">
          {insight.body}
        </p>
      )}

      <ExecutiveActions
        cardId={traceId}
        slice={slice}
        whatIfQuestion={whatIfQuestion}
      />

      {topImpact.length > 0 && (
        <div className="mt-8">
          <SectionLabel>{messages.ai.priorities}</SectionLabel>
          <div className="space-y-3">
            {topImpact.map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-4 rounded-2xl border border-white/80 bg-white/75 px-4 py-4 shadow-sm"
              >
                <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-ai/10 text-[12px] font-bold text-ai">
                  {item.rank}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold leading-snug text-ink">
                    {simplifyAlertText(item.issue)}
                  </p>
                  <p className="mt-1.5 text-[12.5px] text-ink-soft">
                    {messages.ai.ifAddressed.replace(
                      "{pts}",
                      String(item.uplift_university),
                    )}
                  </p>
                </div>
              </div>
            ))}
          </div>
          {impactItems.length > 3 && (
            <button
              type="button"
              onClick={() => setShowAllImpact((v) => !v)}
              className="mt-3 text-[12px] font-semibold text-ai"
            >
              {showAllImpact
                ? messages.ai.showLess
                : messages.ai.showAll.replace(
                    "{count}",
                    String(impactItems.length),
                  )}
            </button>
          )}
        </div>
      )}

      {(topAlerts.length > 0 || topAnomalies.length > 0 || showWarnings) && (
        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          {topAlerts.length > 0 && (
            <div>
              <SectionLabel>{messages.ai.needsAttention}</SectionLabel>
              <div className="space-y-3">
                {topAlerts.map((a) => (
                  <div
                    key={String(a["id"])}
                    className="rounded-2xl border border-amber/20 bg-amber/5 px-4 py-3.5"
                  >
                    <div className="text-[11px] font-bold uppercase tracking-[0.12em] text-amberink">
                      {messages.ai.threshold}
                    </div>
                    <p className="mt-1.5 text-[13.5px] font-medium leading-snug text-ink">
                      {simplifyAlertText(String(a["text"] || ""))}
                    </p>
                    {a["value"] != null && a["threshold"] != null && (
                      <p className="mt-1 text-[12px] text-ink-soft">
                        {messages.ai.nowReviewLine
                          .replace("{value}", String(a["value"]))
                          .replace("{threshold}", String(a["threshold"]))}
                      </p>
                    )}
                  </div>
                ))}
              </div>
              {ruleAlerts.length > 3 && (
                <button
                  type="button"
                  onClick={() => setShowAllAlerts((v) => !v)}
                  className="mt-3 text-[12px] font-semibold text-ai"
                >
                  {showAllAlerts
                    ? messages.ai.showLess
                    : messages.ai.showAll.replace(
                        "{count}",
                        String(ruleAlerts.length),
                      )}
                </button>
              )}
            </div>
          )}

          {(topAnomalies.length > 0 ||
            (showWarnings &&
              warnings &&
              ruleAlerts.length === 0 &&
              anomalies.length === 0)) && (
            <div>
              <SectionLabel>
                {topAnomalies.length > 0
                  ? messages.ai.unusualPatterns
                  : messages.ai.warnings}
              </SectionLabel>
              <div className="space-y-3">
                {topAnomalies.map((a) => (
                  <div
                    key={String(a["id"])}
                    className="rounded-2xl border border-ai/20 bg-ai/5 px-4 py-3.5"
                  >
                    <div className="text-[11px] font-bold uppercase tracking-[0.12em] text-ai">
                      {messages.ai.pattern}
                    </div>
                    <p className="mt-1.5 text-[13.5px] font-medium leading-snug text-ink">
                      {String(a["text"] || "")}
                    </p>
                  </div>
                ))}
                {showWarnings &&
                  warnings &&
                  ruleAlerts.length === 0 &&
                  anomalies.length === 0 &&
                  warnings.slice(0, 3).map((w) => (
                    <div
                      key={w.id}
                      className={cn(
                        "rounded-2xl px-4 py-3.5 text-[13.5px] font-medium",
                        w.tone === "rose"
                          ? "bg-rose/10 text-rosee"
                          : "bg-amber/12 text-amberink",
                      )}
                    >
                      {"text" in w ? w.text : ""}
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {outlook && (
        <div className="mt-8">
          <SectionLabel>{outlook.title}</SectionLabel>
          <div className="rounded-2xl border border-white/80 bg-white/75 px-4 py-4 shadow-sm">
            <p className="text-[14px] leading-relaxed text-ink">
              {outlook.body}
            </p>
            {forecastStatus?.kind === "forecast" &&
              forecastStatus.value != null && (
                <div className="mt-3 flex flex-wrap gap-3">
                  <div className="rounded-xl bg-ai/8 px-3 py-2">
                    <div className="text-[10px] font-bold uppercase tracking-wide text-ink-soft">
                      {messages.ai.estimate}
                    </div>
                    <div className="text-[18px] font-bold text-ai">
                      {forecastStatus.value}%
                    </div>
                  </div>
                  {forecastStatus.low != null &&
                    forecastStatus.high != null && (
                      <div className="rounded-xl bg-black/[0.03] px-3 py-2">
                        <div className="text-[10px] font-bold uppercase tracking-wide text-ink-soft">
                          {messages.ai.range}
                        </div>
                        <div className="text-[18px] font-bold text-ink">
                          {forecastStatus.low}–{forecastStatus.high}%
                        </div>
                      </div>
                    )}
                </div>
              )}
          </div>
        </div>
      )}

      {!outlook && prediction && (
        <div className="mt-8">
          <SectionLabel>{messages.ai.standing}</SectionLabel>
          <AiPrediction data={prediction} />
        </div>
      )}

      {topRecs.length > 0 && (
        <div className="mt-8">
          <SectionLabel>{messages.ai.suggestedNextSteps}</SectionLabel>
          <ul className="space-y-3">
            {topRecs.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-white/80 bg-white/75 px-4 py-3.5 shadow-sm"
              >
                <p className="min-w-0 flex-1 text-[14px] font-medium leading-snug text-ink">
                  {item.text}
                </p>
                {item.action && (
                  <button
                    onClick={() => setPendingItem(item)}
                    className="shrink-0 rounded-full bg-ai px-3.5 py-1.5 text-[11px] font-semibold text-white shadow-md shadow-ai/20 transition-opacity hover:opacity-90"
                  >
                    {item.action.label}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {insight?.cases && insight.cases.length > 0 && (
        <div className="mt-8 space-y-2.5">
          <SectionLabel>{messages.ai.cases}</SectionLabel>
          {insight.cases.map((c) => (
            <RiskCaseRow key={c.id} item={c} />
          ))}
        </div>
      )}

      {insight?.action &&
        !recommendations.some((r) => r.action?.to === insight.action?.to) && (
          <AiAction {...insight.action} />
        )}

      <div className="mt-6 border-t border-black/5 pt-4">
        <AiEvidence metrics={evidence} />
      </div>

      {pendingItem && (
        <ConfirmDialog
          action={pendingItem.action!}
          onClose={() => setPendingItem(null)}
        />
      )}
    </AiFrame>
  );
}

/** Page-local AI analysis for the current dashboard surface. */
export function AiDecisionSection({
  role,
  page = "overview",
}: {
  role?: Role;
  page?: AiPage;
}) {
  const { role: contextRole } = useRole();
  const effective = role ?? contextRole;
  return (
    <AiDecisionCard
      {...(role ? { role } : {})}
      page={page}
      insightId={`insight-${page}-${effective}`}
    />
  );
}
