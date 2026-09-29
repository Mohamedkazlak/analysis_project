import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Kpi } from "@/lib/types";

export function Panel({
  title,
  action,
  className,
  children,
}: {
  title?: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn("glass-panel p-5", className)}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && (
            <h2 className="font-display text-sm font-bold text-ink">{title}</h2>
          )}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <div className="glass-panel p-5">
      <div className="text-[11px] font-medium uppercase tracking-[0.1em] text-ink-soft">
        {kpi.label}
      </div>
      <div className="font-display mt-2 text-3xl font-extrabold text-ink">
        {kpi.value}
      </div>
      {kpi.delta && kpi.direction && (
        <div
          className={cn(
            "mt-1 text-[12px] font-semibold",
            kpi.direction === "up" ? "text-mintink" : "text-rosee",
          )}
        >
          {kpi.direction === "up" ? "▲" : "▼"} {kpi.delta}
        </div>
      )}
    </div>
  );
}

export function StatBlock({
  label,
  value,
  sub,
  tone = "ink",
  valueClassName,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "ink" | "mint" | "rose" | "iris";
  valueClassName?: string;
}) {
  const toneClass = {
    ink: "text-ink",
    mint: "text-mintink",
    rose: "text-rosee",
    iris: "text-iris",
  }[tone];
  return (
    <div className="glass-panel p-5">
      <div className="text-[11px] font-medium uppercase tracking-[0.1em] text-ink-soft">
        {label}
      </div>
      <div
        className={cn(
          "font-display mt-2 font-extrabold break-words",
          valueClassName ?? "text-3xl",
          toneClass,
        )}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-[12px] text-ink-soft">{sub}</div>}
    </div>
  );
}

export function AiInsight({
  children,
  headline,
  size = "md",
}: {
  children: ReactNode;
  headline?: string;
  size?: "md" | "lg";
}) {
  const large = size === "lg";
  return (
    <div
      className={cn(
        "flex items-start rounded-3xl border border-ai/25 bg-gradient-to-br from-violet/10 via-iris/5 to-cyan/10 backdrop-blur-xl",
        large ? "gap-4 p-7 sm:min-h-44" : "gap-3 p-5",
      )}
    >
      <div
        className={cn(
          "font-display grid shrink-0 place-items-center rounded-xl bg-ai/15 text-ai font-extrabold",
          large ? "size-12 text-lg" : "size-9",
        )}
      >
        ✦
      </div>
      <div className="min-w-0 flex-1">
        <div
          className={cn(
            "font-bold uppercase tracking-[0.14em] text-ai",
            large ? "text-[12px]" : "text-[11px]",
          )}
        >
          AI Insight
        </div>
        {headline ? (
          <h3
            className={cn(
              "font-display mt-2 font-bold text-ink",
              large ? "text-[18px]" : "text-[15px]",
            )}
          >
            {headline}
          </h3>
        ) : null}
        <p
          className={cn(
            "leading-relaxed text-ink",
            headline ? "mt-2" : "mt-1.5",
            large ? "text-[15px]" : "text-[13px]",
          )}
        >
          {children}
        </p>
      </div>
    </div>
  );
}

export function Badge({
  tone,
  children,
}: {
  tone: "pass" | "fail" | "warn" | "neutral";
  children: ReactNode;
}) {
  const map = {
    pass: "bg-mint/12 text-mintink",
    fail: "bg-rose/12 text-rosee",
    warn: "bg-amber/12 text-amberink",
    neutral: "bg-iris/10 text-iris",
  };
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold",
        map[tone],
      )}
    >
      {children}
    </span>
  );
}

export function Meter({
  value,
  tone = "iris",
  className,
}: {
  value: number;
  tone?: "iris" | "cyan" | "mint" | "amber" | "rose";
  className?: string;
}) {
  const map = {
    iris: "bg-iris",
    cyan: "bg-cyan",
    mint: "bg-mint",
    amber: "bg-amber",
    rose: "bg-rose",
  };
  return (
    <div
      className={cn("h-1.5 w-24 shrink-0 rounded-full bg-black/10", className)}
    >
      <div
        className={cn("h-full rounded-full", map[tone])}
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

export function TableShell({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-black/5">
      <table
        className={cn("w-full min-w-[640px] text-left text-[13px]", className)}
      >
        {children}
      </table>
    </div>
  );
}

export function Th({
  children,
  align = "left",
  onClick,
}: {
  children: ReactNode;
  align?: "left" | "right";
  onClick?: () => void;
}) {
  return (
    <th
      onClick={onClick}
      className={cn(
        "px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-soft",
        align === "right" && "text-right",
        onClick && "cursor-pointer select-none hover:text-iris",
      )}
    >
      {children}
    </th>
  );
}

export function ScreenSkeleton({
  cards = 4,
  panels = 2,
}: {
  cards?: number;
  panels?: number;
}) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: cards }).map((_, i) => (
          <div key={i} className="glass-panel h-28 animate-pulse p-5" />
        ))}
      </div>
      {Array.from({ length: panels }).map((_, i) => (
        <div key={i} className="glass-panel h-64 animate-pulse p-5" />
      ))}
    </div>
  );
}

export const chartColors = {
  iris: "#4f46e5",
  violet: "#8b5cf6",
  cyan: "#0891b2",
  mint: "#059669",
  amber: "#b45309",
  yellow: "#eab308",
  rose: "#e11d48",
  grid: "#e9e5f7",
  axis: "#6b6890",
};

export const tooltipStyle = {
  borderRadius: 14,
  border: "1px solid rgba(255,255,255,0.8)",
  background: "rgba(255,255,255,0.92)",
  backdropFilter: "blur(12px)",
  fontSize: 12,
  color: "#3d3a5e",
} as const;

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-2">{children}</div>;
}

export function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex items-center gap-2 rounded-full border border-white/80 bg-white/70 px-3 py-1.5 backdrop-blur-xl">
      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-soft">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-transparent text-[11px] font-semibold text-ink outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search…",
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-44 rounded-full border border-white/80 bg-white/70 px-3.5 py-1.5 text-[11px] font-medium text-ink placeholder:text-ink-soft/70 backdrop-blur-xl outline-none focus:border-iris/40"
    />
  );
}

export function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        "rounded-full border px-3 py-1.5 text-[11px] font-semibold backdrop-blur-xl transition-colors",
        checked
          ? "border-iris/40 bg-iris/12 text-iris"
          : "border-white/80 bg-white/70 text-ink-soft",
      )}
    >
      {label}
    </button>
  );
}
