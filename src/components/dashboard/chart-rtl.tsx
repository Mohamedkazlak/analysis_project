import type { ReactElement } from "react";
import { ResponsiveContainer } from "recharts";
import { chartColors } from "@/components/dashboard/dashboard-ui";

/** Position the tick, and undo scaleX(-1) when the chart SVG is mirrored. */
export function unmirrorAt(x: number, y: number, mirror: boolean) {
  return mirror ? `translate(${x},${y}) scale(-1,1)` : `translate(${x},${y})`;
}

export function wrapLabel(name: string, limit = 16) {
  if (name.length <= limit) return [name];
  const lines: string[] = [];
  let current = "";
  for (const word of name.split(" ")) {
    const next = current ? `${current} ${word}` : word;
    if (current && next.length > limit) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  if (current) lines.push(current);
  return lines;
}

export function CategoryTick({
  x = 0,
  y = 0,
  payload,
  mirror = false,
  limit = 16,
  textAnchor = "end",
}: {
  x?: number | undefined;
  y?: number | undefined;
  payload?: { value?: string | undefined } | undefined;
  mirror?: boolean | undefined;
  limit?: number | undefined;
  textAnchor?: "start" | "end" | "middle" | undefined;
}) {
  const lines = wrapLabel(String(payload?.value ?? ""), limit ?? 16);
  const lineHeight = 12;
  return (
    <g transform={unmirrorAt(Number(x), Number(y), Boolean(mirror))}>
      <text
        x={0}
        y={0}
        textAnchor={textAnchor ?? "end"}
        fill={chartColors.axis}
        fontSize={11}
      >
        {lines.map((line, index) => (
          <tspan
            key={`${line}-${index}`}
            x={0}
            dy={
              index === 0 ? -((lines.length - 1) * lineHeight) / 2 : lineHeight
            }
          >
            {line}
          </tspan>
        ))}
      </text>
    </g>
  );
}

export function AxisValueTick({
  x = 0,
  y = 0,
  payload,
  mirror = false,
  suffix = "",
  dy = 12,
}: {
  x?: number | undefined;
  y?: number | undefined;
  payload?: { value?: number | string | undefined } | undefined;
  mirror?: boolean | undefined;
  suffix?: string | undefined;
  dy?: number | undefined;
}) {
  return (
    <g transform={unmirrorAt(Number(x), Number(y), Boolean(mirror))}>
      <text
        x={0}
        y={0}
        dy={dy ?? 12}
        textAnchor="middle"
        fill={chartColors.axis}
        fontSize={11}
      >
        {`${payload?.value ?? ""}${suffix ?? ""}`}
      </text>
    </g>
  );
}

/** Category labels on a horizontal axis, optionally angled. */
export function AngledCategoryTick({
  x = 0,
  y = 0,
  payload,
  mirror = false,
  angle = -35,
  limit = 18,
}: {
  x?: number | undefined;
  y?: number | undefined;
  payload?: { value?: string | undefined } | undefined;
  mirror?: boolean | undefined;
  angle?: number | undefined;
  limit?: number | undefined;
}) {
  const label = String(payload?.value ?? "");
  const text =
    label.length > (limit ?? 18)
      ? `${label.slice(0, (limit ?? 18) - 1)}…`
      : label;
  return (
    <g transform={unmirrorAt(Number(x), Number(y), Boolean(mirror))}>
      <text
        x={0}
        y={0}
        dy={10}
        textAnchor="end"
        transform={`rotate(${angle ?? -35})`}
        fill={chartColors.axis}
        fontSize={10}
      >
        {text}
      </text>
    </g>
  );
}

export function BarEndLabel({
  x,
  y,
  width,
  height,
  value,
  mirror = false,
  suffix = "",
}: {
  x?: number | string | undefined;
  y?: number | string | undefined;
  width?: number | string | undefined;
  height?: number | string | undefined;
  value?: number | string | undefined;
  mirror?: boolean;
  suffix?: string;
}) {
  const cx = Number(x ?? 0) + Number(width ?? 0) + 8;
  const cy = Number(y ?? 0) + Number(height ?? 0) / 2;
  return (
    <g transform={unmirrorAt(cx, cy, mirror)}>
      <text
        x={0}
        y={0}
        dy={4}
        textAnchor="start"
        fill={chartColors.axis}
        fontSize={11}
      >
        {`${value ?? ""}${suffix}`}
      </text>
    </g>
  );
}

export function ChartLegend({
  items,
}: {
  items: { label: string; color: string }[];
}) {
  return (
    <div className="mt-2 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
      {items.map((item) => (
        <span
          key={item.label}
          className="inline-flex items-center gap-1.5 text-[11px] text-ink-soft"
        >
          <span
            className="size-2.5 shrink-0 rounded-sm"
            style={{ background: item.color }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}

/**
 * Mirror the chart SVG for Arabic so bars/categories read right-to-left
 * while tick glyphs stay upright via unmirror helpers.
 */
export function MirroredChart({
  rtl,
  height,
  children,
}: {
  rtl: boolean;
  height: number | string;
  children: ReactElement;
}) {
  return (
    <div style={{ height }} className="w-full">
      <div
        className="h-full w-full"
        style={rtl ? { transform: "scaleX(-1)" } : undefined}
      >
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function tooltipMirrorStyle(rtl: boolean) {
  return rtl ? { transform: "scaleX(-1)" } : undefined;
}
