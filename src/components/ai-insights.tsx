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
import { aiConfig } from "@/lib/ai/config";
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

const EMPTY_COPY =
  "Not enough data yet to generate insights — check back after your next exam.";

export function AiFrame({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border-2 border-ai/60 bg-gradient-to-br from-violet/10 via-iris/5 to-cyan/10 p-5 backdrop-blur-xl">
      <div className="flex items-center gap-2">
        <Lightbulb className="size-4 text-ai" strokeWidth={2.4} />
        <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-ai">
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
  return (
    <Link
      to={roleRouteTo(to)}
      params={{ role: ROLE_SLUG[role] }}
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
            Why
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
  const Icon = dirIcon[data.direction];
  const heading =
    data.kind === "forecast" ? data.title : data.title || "Current standing";
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
  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="inline-flex items-center gap-1 text-[11px] font-semibold text-ai/90 underline decoration-ai/30 underline-offset-2"
      >
        Based on
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
  function confirm() {
    onClose();
    if (action.to) {
      void navigate({
        to: roleRouteTo(action.to),
        params: { role: ROLE_SLUG[role] },
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
            Cancel
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
  if (!metrics.length) return null;
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 text-[11px] font-semibold text-ai"
      >
        Based on
        <ChevronDown
          className={cn("size-3.5 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <ul className="mt-2 space-y-1.5">
          {metrics.slice(0, 6).map((metric) => (
            <li key={metric.id} className="text-[12px] text-ink-soft">
              <span className="font-semibold text-ink">
                {metric.entity || metric.name}
              </span>
              {" · "}
              {metric.name.replace(/_/g, " ")} {metric.value}
              {metric.unit === "percent" ? "%" : ""}
              {metric.comparison?.scopeAverage != null
                ? ` · scope average ${metric.comparison.scopeAverage}`
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
  return (
    <div className="mt-4 space-y-2">
      <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-amberink">
        Warnings
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

export function AiRecommendations({
  items,
  onAction,
}: {
  items: Recommendation[];
  onAction: (item: Recommendation) => void;
}) {
  return (
    <div className="mt-5">
      <div className="text-[11px] font-bold uppercase tracking-[0.14em] text-ai">
        Recommended actions
      </div>
      {items.length === 0 ? (
        <p className="mt-2 text-[13px] text-ink-soft">
          No actions needed right now — you're on track.
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
}: {
  role?: Role;
  insightId?: string;
}) {
  const { role: contextRole, user } = useRole();
  const role = roleProp ?? contextRole;
  const traceId = insightId ?? `insight-${role}-${user.id}`;
  const [pendingItem, setPendingItem] = useState<Recommendation | null>(null);
  const { filters, filtersReady, queryKey, enabled } =
    useFilteredQuery("ai-decision");
  const { data, isPending } = useQuery({
    queryKey: [...queryKey, role, traceId],
    queryFn: () => getAiDecision(filters),
    enabled,
    retry: false,
    staleTime: 30_000,
    refetchInterval: (query) =>
      query.state.data?.narrationStatus === "pending" ? 4000 : false,
  });

  const label = role === "student" ? "Recommendations" : "AI decision";

  if (!filtersReady) return null;
  if (isPending) return <AiSkeleton label={label} />;

  if (data?.status === "timeout" || data?.status === "unavailable") {
    return (
      <AiFrame label={label}>
        <p className="mt-2 text-[13px] text-ink-soft">
          {data.message || "AI analysis is taking longer than expected."}
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

  if (!insight && recommendations.length === 0 && !prediction)
    return (
      <AiFrame label={label}>
        <p className="mt-2 text-[13px] text-ink-soft">
          {data?.dataStatus === "insufficient"
            ? "Not enough recorded data in this scope to produce an insight."
            : EMPTY_COPY}
        </p>
      </AiFrame>
    );

  const showWarnings =
    aiConfig.showWarnings[role] && (warnings?.length ?? 0) > 0;

  return (
    <AiFrame label={label}>
      {insight && (
        <>
          <h3 className="font-display mt-2 text-[15px] font-bold text-ink">
            {insight.headline}
          </h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-ink">
            {insight.body}
          </p>
          <AiEvidence metrics={evidence} />
        </>
      )}

      {data?.narrationStatus === "pending" && (
        <p className="mt-2 text-[11px] text-ink-soft">
          Showing verified figures. Wording is still being refined.
        </p>
      )}

      {prediction && <AiPrediction data={prediction} />}

      {showWarnings && warnings && <AiWarnings warnings={warnings} />}

      {insight?.cases && (
        <div className="mt-4 space-y-2.5">
          {insight.cases.map((c) => (
            <RiskCaseRow key={c.id} item={c} />
          ))}
        </div>
      )}

      <AiRecommendations items={recommendations} onAction={setPendingItem} />

      {insight?.action && <AiAction {...insight.action} />}
      <p className="mt-3 text-[11px] text-ink-soft">
        Traced to {traceId} · every action asks you to confirm first.
      </p>
      {pendingItem && (
        <ConfirmDialog
          action={pendingItem.action!}
          onClose={() => setPendingItem(null)}
        />
      )}
    </AiFrame>
  );
}

/** Tier 1 decision pages render this single narrative card. */
export function AiDecisionSection({ role }: { role?: Role }) {
  const { role: contextRole } = useRole();
  const effective = role ?? contextRole;
  return (
    <AiDecisionCard
      {...(role ? { role } : {})}
      insightId={`insight-${effective}`}
    />
  );
}
