import { Activity, Calculator } from "lucide-react";

import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import type { QuantMetric } from "@/mock/types";

export function QuantOverview({ metrics }: { metrics: QuantMetric[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Calculator className="h-5 w-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">量化概览</h2>
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            程序计算指标，不是AI结论；具体口径和真实数据源仍待真实数据开发前确认。
          </p>
        </div>
        <SimulatedDataBadge compact />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCell key={metric.id} metric={metric} />
        ))}
      </div>
    </section>
  );
}

function MetricCell({ metric }: { metric: QuantMetric }) {
  const hasData = metric.value !== null && metric.visualValue !== null;
  const directionLabel =
    metric.direction === "up"
      ? "偏强"
      : metric.direction === "down"
        ? "偏弱"
        : metric.direction === "flat"
          ? "持平"
          : "待计算";
  const tone =
    metric.direction === "up"
      ? "text-red-600"
      : metric.direction === "down"
        ? "text-emerald-700"
        : "text-slate-800";

  return (
    <article className="min-h-[132px] rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold leading-4 text-slate-600">{metric.label}</p>
        <Activity className="h-3.5 w-3.5 shrink-0 text-slate-400" />
      </div>
      <p className={`mt-2 text-base font-semibold ${hasData ? tone : "text-slate-500"}`}>
        {metric.value ?? "暂无数据"}
      </p>
      <p className="mt-1 truncate text-[11px] text-slate-500">基准：{metric.benchmark}</p>
      <div className="mt-3">
        <MetricVisual metric={metric} />
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-[11px] leading-4">
        <span className={hasData ? "text-slate-600" : "text-amber-700"}>
          {hasData ? `${directionLabel} · ${metric.status}` : metric.status}
        </span>
        <span className="shrink-0 text-slate-400">{metric.dataTime.slice(5, 16)}</span>
      </div>
    </article>
  );
}

function MetricVisual({ metric }: { metric: QuantMetric }) {
  if (metric.value === null || metric.visualValue === null) {
    return (
      <div className="h-6 rounded bg-white">
        <div className="h-full rounded border border-dashed border-slate-300 bg-slate-100" />
      </div>
    );
  }

  const value = clamp(metric.visualValue, 0, 100);

  if (metric.visualType === "strength") {
    const left = Math.min(50, value);
    const width = Math.abs(value - 50);

    return (
      <div className="relative h-6 overflow-hidden rounded bg-white">
        <div className="absolute left-1/2 top-0 h-full w-px bg-slate-300" />
        <div
          className={`absolute top-1 h-4 rounded ${value >= 50 ? "bg-red-500" : "bg-emerald-600"}`}
          style={{ left: `${left}%`, width: `${width}%` }}
        />
      </div>
    );
  }

  if (metric.visualType === "trend") {
    const y = 24 - (value / 100) * 18;

    return (
      <svg viewBox="0 0 100 24" className="h-6 w-full rounded bg-white" role="img">
        <path d="M0 18 C20 14, 32 20, 50 12 S80 6, 100 10" fill="none" stroke="#cbd5e1" strokeWidth="3" />
        <path
          d={`M0 18 C20 14, 32 20, 50 ${y.toFixed(2)} S80 ${Math.max(4, y - 4).toFixed(2)}, 100 ${Math.max(4, y - 1).toFixed(2)}`}
          fill="none"
          stroke={value >= 50 ? "#dc2626" : "#047857"}
          strokeLinecap="round"
          strokeWidth="3"
        />
      </svg>
    );
  }

  return (
    <div className="h-6 overflow-hidden rounded bg-white">
      <div className="h-full rounded bg-blue-600" style={{ width: `${value}%` }} />
    </div>
  );
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}
