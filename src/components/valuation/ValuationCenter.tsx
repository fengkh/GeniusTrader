import { Calculator, CircleAlert } from "lucide-react";

import { EmptyState } from "@/components/status/EmptyState";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import {
  valuationAvailabilityLabel,
  valuationConfidenceLabel
} from "@/lib/formatters";
import type { Stock } from "@/mock/types";

export function ValuationCenter({ stock }: { stock: Stock }) {
  const valuation = stock.valuation;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Calculator className="h-5 w-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">估值中心</h2>
            <SimulatedDataBadge compact />
            {valuation ? <StatusTag status={valuation.dataStatus} label={valuationAvailabilityLabel(valuation.availability)} /> : null}
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            程序计算估值样本，AI只能解释假设和边界，不能生成价格、市值、倍数或估值区间。
          </p>
        </div>
        {valuation ? (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            估值日 {valuation.valuationDate} · 财报期 {valuation.financialPeriod}
          </div>
        ) : null}
      </div>

      {!valuation ? (
        <div className="mt-4">
          <EmptyState title="暂无估值样本" description="当前Mock股票没有估值字段，页面不会补造估值结论。" />
        </div>
      ) : (
        <>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-6">
            <ValuationMetric label="当前价格" value={valuation.currentPrice ?? "暂无"} />
            <ValuationMetric label="总市值" value={valuation.marketCap ?? "暂无"} />
            <ValuationMetric label="PE" value={valuation.pe ?? "暂无"} />
            <ValuationMetric label="PB" value={valuation.pb ?? "暂无"} />
            <ValuationMetric label="PS" value={valuation.ps ?? "暂无"} />
            <ValuationMetric label="置信度" value={valuationConfidenceLabel(valuation.confidence)} />
          </div>

          <div className="mt-4 grid gap-3 xl:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-semibold text-slate-500">适用方法</p>
              <h3 className="mt-2 text-base font-semibold text-slate-950">{valuation.methodLabel}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-700">{valuation.explanation}</p>
              <p className="mt-2 text-xs text-slate-500">模型：{valuation.modelLabel}；数据时间：{valuation.dataTime}</p>
            </div>
            <div className="rounded-md border border-blue-200 bg-blue-50 p-3">
              <div className="flex items-start gap-2">
                <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-blue-700" />
                <p className="text-sm leading-6 text-blue-900">{valuation.boundaryNote}</p>
              </div>
            </div>
          </div>

          {valuation.scenarios.length > 0 ? (
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              {valuation.scenarios.map((scenario) => (
                <article key={scenario.name} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold text-slate-500">{scenario.label}情景</p>
                  <p className="mt-2 text-lg font-semibold text-slate-950">{scenario.priceRange}</p>
                  <p className="mt-1 text-sm font-medium text-slate-700">相对当前：{scenario.impliedSpace}</p>
                  <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-600">
                    {scenario.assumptions.map((assumption) => (
                      <li key={assumption}>{assumption}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          ) : (
            <div className="mt-4">
              <EmptyState
                title="暂无估值区间"
                description="缺少必要财务字段或不适用估值方法时，MVP只展示不可用原因。"
              />
            </div>
          )}

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-semibold text-slate-500">关键假设</p>
              <ul className="mt-2 space-y-1 text-sm leading-6 text-slate-700">
                {valuation.assumptions.map((assumption) => (
                  <li key={assumption}>{assumption}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
              <p className="text-xs font-semibold text-amber-900">缺失或待确认字段</p>
              {valuation.missingInputs.length === 0 ? (
                <p className="mt-2 text-sm text-amber-900">当前Mock样本无缺失字段；真实供应商口径仍需确认。</p>
              ) : (
                <ul className="mt-2 space-y-1 text-sm leading-6 text-amber-900">
                  {valuation.missingInputs.map((input) => (
                    <li key={input}>{input}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <p className="mt-3 text-xs leading-5 text-slate-500">
            当前价格位置：{valuation.pricePosition ?? "暂无"}；来源：{valuation.source}。
          </p>
        </>
      )}
    </section>
  );
}

function ValuationMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}
