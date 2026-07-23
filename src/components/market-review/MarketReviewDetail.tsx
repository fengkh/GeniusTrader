import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowRight, Brain, DatabaseZap, Flame, Layers3, ListChecks } from "lucide-react";

import { ReviewSummaryCard } from "@/components/review/ReviewSummaryCard";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import {
  boardStageLabel,
  capabilityStatusLabel,
  formatPercent,
  marketReviewStatusLabel,
  trendTone
} from "@/lib/formatters";
import type { BoardHeatRecord, MarketDailyReview, WatchCandidate } from "@/mock/types";

export function MarketReviewDetail({ review }: { review: MarketDailyReview }) {
  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-xl font-semibold text-slate-950">全市场概览</h2>
              <StatusTag status={review.dataStatus} label={marketReviewStatusLabel(review.status)} />
              <SimulatedDataBadge compact />
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">{review.overview}</p>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {review.date} · {capabilityStatusLabel(review.capabilityStatus)} · {review.generatedAt}
          </div>
        </div>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
          <Metric label="上涨" value={`${review.breadth.rising}`} tone="text-red-600" />
          <Metric label="下跌" value={`${review.breadth.falling}`} tone="text-emerald-700" />
          <Metric label="平盘 / 停牌" value={`${review.breadth.flat} / ${review.breadth.suspended}`} />
          <Metric label="涨停 / 跌停" value={`${review.breadth.limitUp} / ${review.breadth.limitDown}`} />
          <Metric label="中位涨跌" value={formatPercent(review.breadth.medianChangePercent)} tone={trendTone(review.breadth.medianChangePercent)} />
          <Metric label="成交额" value={review.breadth.totalAmount ?? "暂无"} />
          <Metric label="成交额变化" value={formatPercent(review.breadth.amountChangePercent)} tone={trendTone(review.breadth.amountChangePercent)} />
          <Metric label="20日新高 / 新低" value={`${review.breadth.newHigh20} / ${review.breadth.newLow20}`} />
          <Metric label="站上MA20比例" value={formatPercent(review.breadth.ma20AboveRatio)} />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionHeader icon={<Layers3 className="h-5 w-5 text-blue-700" />} title="指数与风格表现" />
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {review.indexPerformance.map((index) => (
            <article key={index.code} className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs text-slate-500">{index.code} · {index.style}</p>
              <div className="mt-2 flex items-end justify-between gap-2">
                <h3 className="font-semibold text-slate-950">{index.name}</h3>
                <span className={`text-lg font-semibold ${trendTone(index.changePercent)}`}>
                  {formatPercent(index.changePercent)}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-500">成交额：{index.amount ?? "暂无"}</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">{index.note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionHeader icon={<Flame className="h-5 w-5 text-rose-700" />} title="热点板块排行与阶段" />
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <StageGroup title="连续走强板块" boards={review.continuousStrongBoards} />
          <StageGroup title="高位分化和退潮板块" boards={review.retreatBoards} />
        </div>
        <div className="mt-4 grid gap-3 xl:grid-cols-2">
          {review.hotBoards.map((board) => (
            <BoardHeatCard key={board.id} board={board} />
          ))}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <CandidatePanel title="次日板块观察候选" items={review.boardCandidates} />
        <CandidatePanel title="次日个股观察候选" items={review.stockCandidates} />
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionHeader icon={<DatabaseZap className="h-5 w-5 text-amber-700" />} title="数据来源与能力限制" />
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold text-slate-500">数据来源</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {review.dataSources.map((source) => (
                <span key={source} className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700">
                  {source}
                </span>
              ))}
            </div>
          </div>
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-900">能力限制</p>
            <ul className="mt-2 space-y-1 text-sm leading-6 text-amber-900">
              {review.capabilityNotes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionHeader icon={<Brain className="h-5 w-5 text-blue-700" />} title="AI摘要" />
        <div className="mt-4">
          <ReviewSummaryCard review={review.aiSummary} />
        </div>
      </section>
    </div>
  );
}

function StageGroup({ title, boards }: { title: string; boards: BoardHeatRecord[] }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      {boards.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">当前场景暂无该类板块。</p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          {boards.map((board) => (
            <span key={board.id} className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700">
              {board.name} · {boardStageLabel(board.stage)} · {formatPercent(board.change1d)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function BoardHeatCard({ board }: { board: BoardHeatRecord }) {
  return (
    <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-slate-950">{board.name}</h3>
            <span className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700">
              {board.type}
            </span>
            <StatusTag status={board.dataStatus} label={board.dataCompleteness} />
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-600">{board.trendSummary}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-slate-500">排名</p>
          <p className="text-xl font-semibold text-slate-950">#{board.ranking}</p>
          <p className="text-xs text-slate-500">变化 {board.rankingChange === null ? "暂无" : `${board.rankingChange > 0 ? "+" : ""}${board.rankingChange}`}</p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
        <Metric label="1日" value={formatPercent(board.change1d)} tone={trendTone(board.change1d)} />
        <Metric label="3日 / 5日" value={`${formatPercent(board.change3d)} / ${formatPercent(board.change5d)}`} />
        <Metric label="上涨比例" value={formatPercent(board.risingRatio)} />
        <Metric label="总分" value={board.totalScore === null ? "暂无" : `${board.totalScore}`} />
      </div>

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        {board.components.map((component) => (
          <div key={component.label} className="rounded-md bg-white p-3">
            <div className="flex items-center justify-between gap-2 text-xs">
              <span className="font-semibold text-slate-600">{component.label}</span>
              <span className="text-slate-500">{component.value ?? "暂无"}</span>
            </div>
            <div className="mt-2 h-2 rounded bg-slate-100">
              <div className="h-2 rounded bg-blue-600" style={{ width: `${component.score ?? 0}%` }} />
            </div>
            <p className="mt-2 text-[11px] leading-4 text-slate-500">{component.benchmark} · {component.note}</p>
          </div>
        ))}
      </div>

      <div className="mt-3 rounded-md border border-slate-200 bg-white p-3">
        <p className="text-xs font-semibold text-slate-500">板块内重点股票</p>
        <div className="mt-2 grid gap-2">
          {board.hotStocks.map((stock) => (
            <Link
              href={stock.stockId ? `/watchlist/${stock.stockId}` : "/market-review/2026-07-22"}
              key={`${board.id}-${stock.code}`}
              className="focus-ring rounded-md border border-slate-200 bg-slate-50 p-3 hover:bg-slate-100"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-950">{stock.name} · {stock.code}</p>
                  <p className="mt-1 text-xs text-slate-500">{stock.roleSuggestion}；依据：{stock.roleBasis}；置信度：{stock.confidence}</p>
                </div>
                <span className={`text-sm font-semibold ${trendTone(stock.change1d)}`}>{formatPercent(stock.change1d)}</span>
              </div>
              <p className="mt-2 text-xs leading-5 text-slate-600">
                3日 {formatPercent(stock.change3d)}；5日 {formatPercent(stock.change5d)}；相对板块 {stock.relativeBoardStrength ?? "暂无"}；量能/成交额/换手分位 {stock.volumePercentile ?? "暂无"} / {stock.amountPercentile ?? "暂无"} / {stock.turnoverPercentile ?? "暂无"}；20日高点：{stock.nearHigh20 ? "接近" : "未接近"}。
              </p>
              <p className="mt-1 text-xs leading-5 text-slate-500">驱动：{stock.coreDriver}；风险扣分：{stock.riskPenalty}；更新：{stock.updatedAt}</p>
            </Link>
          ))}
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-sm leading-6 text-slate-600 md:grid-cols-2">
        <p><span className="font-semibold text-slate-900">连续性：</span>{board.continuity}</p>
        <p><span className="font-semibold text-slate-900">催化：</span>{board.catalyst}</p>
        <p><span className="font-semibold text-slate-900">后续候选：</span>{board.followUpCandidates.join("、") || "暂无"}</p>
        <p><span className="font-semibold text-slate-900">风险股票：</span>{board.riskStocks.join("、") || "暂无"}</p>
        <p><span className="font-semibold text-slate-900">待核实：</span>{board.pendingVerification.join("、") || "暂无"}</p>
        <p><span className="font-semibold text-slate-900">数据缺口：</span>{board.dataGaps.join("、") || "暂无"}</p>
      </div>
    </article>
  );
}

function CandidatePanel({ title, items }: { title: string; items: WatchCandidate[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <SectionHeader icon={<ListChecks className="h-5 w-5 text-emerald-700" />} title={title} />
      <div className="mt-4 space-y-3">
        {items.length === 0 ? (
          <p className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">当前场景暂无候选。</p>
        ) : (
          items.map((item) => (
            <Link key={item.id} href={item.targetHref} className="focus-ring block rounded-md border border-slate-200 bg-slate-50 p-3 hover:bg-slate-100">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-slate-950">{item.subjectName}{item.subjectCode ? ` · ${item.subjectCode}` : ""}</p>
                  <p className="mt-1 text-xs text-slate-500">{boardStageLabel(item.stage)} · {item.source === "program-ranking" ? "程序排名" : item.source === "ai-explanation" ? "AI解释" : "规则模板"}</p>
                </div>
                <ArrowRight className="h-4 w-4 text-slate-400" />
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-700">{item.reason}</p>
              <div className="mt-2 grid gap-2 text-xs leading-5 text-slate-600 sm:grid-cols-2">
                <p>延续条件：{item.continuationConditions.join("；")}</p>
                <p>失效条件：{item.invalidationConditions.join("；")}</p>
                <p>风险：{item.riskNotes.join("；")}</p>
                <p>待核实：{item.pendingVerification.join("；")}；完整度：{item.dataCompleteness}</p>
              </div>
            </Link>
          ))
        )}
      </div>
      <p className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
        候选只用于复盘观察条件，不代表未来表现确定性。
      </p>
    </section>
  );
}

function SectionHeader({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2">
      {icon}
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
    </div>
  );
}

function Metric({
  label,
  value,
  tone = "text-slate-950"
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${tone}`}>{value}</p>
    </div>
  );
}
