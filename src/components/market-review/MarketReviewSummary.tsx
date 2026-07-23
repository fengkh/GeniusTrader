import Link from "next/link";
import { ArrowRight, BarChart3, Gauge } from "lucide-react";

import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import {
  boardStageLabel,
  capabilityStatusLabel,
  formatPercent,
  marketReviewStatusLabel,
  trendTone
} from "@/lib/formatters";
import type { MarketDailyReview } from "@/mock/types";

export function MarketReviewSummary({ review }: { review: MarketDailyReview }) {
  const topBoards = review.hotBoards.slice(0, 3);
  const candidateCount = review.boardCandidates.length + review.stockCandidates.length;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Gauge className="h-5 w-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">全市场每日复盘</h2>
            <StatusTag status={review.dataStatus} label={marketReviewStatusLabel(review.status)} />
            <SimulatedDataBadge compact />
          </div>
          <p className="mt-1 text-sm leading-6 text-slate-600">
            {review.date} · {capabilityStatusLabel(review.capabilityStatus)} · 生成 {review.generatedAt}
          </p>
        </div>
        <Link
          href={`/market-review/${review.date}`}
          className="focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800"
        >
          查看完整市场复盘
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryMetric label="上涨 / 下跌 / 平盘" value={`${review.breadth.rising} / ${review.breadth.falling} / ${review.breadth.flat}`} />
        <SummaryMetric label="涨停 / 跌停" value={`${review.breadth.limitUp} / ${review.breadth.limitDown}`} />
        <SummaryMetric label="成交额" value={review.breadth.totalAmount ?? "暂无"} />
        <SummaryMetric label="中位涨跌 / MA20" value={`${formatPercent(review.breadth.medianChangePercent)} / ${formatPercent(review.breadth.ma20AboveRatio)}`} />
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[0.95fr_1.2fr_0.85fr]">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <h3 className="text-sm font-semibold text-slate-950">主要指数表现</h3>
          <div className="mt-3 space-y-2">
            {review.indexPerformance.slice(0, 3).map((index) => (
              <div key={index.code} className="flex items-center justify-between gap-2 rounded-md bg-white px-3 py-2">
                <span className="truncate text-xs font-medium text-slate-700">{index.name}</span>
                <span className={`text-xs font-semibold ${trendTone(index.changePercent)}`}>
                  {formatPercent(index.changePercent)}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-slate-700" />
            <h3 className="text-sm font-semibold text-slate-950">热点板块</h3>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            {topBoards.map((board) => (
              <div key={board.id} className="rounded-md bg-white p-3">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-semibold text-slate-950">{board.name}</p>
                  <span className="text-xs text-slate-500">#{board.ranking}</span>
                </div>
                <p className="mt-1 text-xs text-slate-600">{boardStageLabel(board.stage)}</p>
                <p className="mt-1 text-sm font-semibold text-red-600">{formatPercent(board.change1d)}</p>
                <p className="mt-1 text-[11px] text-slate-500">完整度：{board.dataCompleteness}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <h3 className="text-sm font-semibold text-slate-950">次日观察候选</h3>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{candidateCount}项</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            候选来自程序排名或AI解释的结构化说明，仅用于观察条件准备，不提供交易动作。
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <span className="rounded-md bg-white px-2 py-1 text-slate-600">
              连续强势 {review.continuousStrongBoards.length}
            </span>
            <span className="rounded-md bg-white px-2 py-1 text-slate-600">
              退潮分化 {review.retreatBoards.length}
            </span>
          </div>
        </div>
      </div>

      <p className="mt-3 rounded-md bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-800">
        程序计算负责指数、宽度、热度、排行和候选数量；AI仅做摘要解释，不能生成行情数字或覆盖原始事实。
      </p>
    </section>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-base font-semibold text-slate-950">{value}</p>
    </div>
  );
}
