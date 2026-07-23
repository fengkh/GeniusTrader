"use client";

import Link from "next/link";
import { CalendarDays, FileClock } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import {
  boardStageLabel,
  marketReviewStatusLabel
} from "@/lib/formatters";
import { useMockState } from "@/lib/mock-state";

type ReviewTab = "mine" | "market";

export default function ReviewsPage() {
  const { data } = useMockState();
  const [tab, setTab] = useState<ReviewTab>("mine");
  const marketReview = data.marketDailyReview;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="复盘历史"
        title="复盘历史"
        description="本页验证个人复盘与全市场复盘的历史入口，不实现完整编辑、导出或版本对比。"
      />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex rounded-md border border-slate-300 bg-slate-50 p-1">
            <TabButton active={tab === "mine"} onClick={() => setTab("mine")}>
              我的复盘
            </TabButton>
            <TabButton active={tab === "market"} onClick={() => setTab("market")}>
              市场复盘
            </TabButton>
          </div>
          <SimulatedDataBadge compact />
        </div>

        {tab === "mine" ? (
          <div className="mt-4">
            {data.stocks.length === 0 ? (
              <EmptyState title="暂无个人复盘" description="新用户添加自选股后，单股每日复盘和整体复盘会显示在这里。" />
            ) : (
              <div className="grid gap-3 lg:grid-cols-2">
                {data.stocks.slice(0, 6).map((stock) => (
                  <Link
                    key={stock.id}
                    href={`/watchlist/${stock.id}`}
                    className="focus-ring rounded-md border border-slate-200 bg-slate-50 p-4 hover:bg-slate-100"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold text-slate-950">{stock.name} · {stock.code}</p>
                        <p className="mt-1 text-xs text-slate-500">单股每日复盘 · {data.tradeDate}</p>
                      </div>
                      <StatusTag status={stock.todayReview.status === "failed" ? "ai-failure" : "normal"} label={stock.todayReview.status === "manual-edited" ? "人工修订" : stock.todayReview.status === "failed" ? "AI失败" : "已生成"} />
                    </div>
                    <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-600">{stock.todayReview.summary}</p>
                  </Link>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            <Link
              href={`/market-review/${marketReview.date}`}
              className="focus-ring block rounded-lg border border-slate-200 bg-slate-50 p-4 hover:bg-slate-100"
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <CalendarDays className="h-5 w-5 text-blue-700" />
                    <h2 className="text-lg font-semibold text-slate-950">{marketReview.date} 市场复盘</h2>
                    <StatusTag status={marketReview.dataStatus} label={marketReviewStatusLabel(marketReview.status)} />
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{marketReview.overview}</p>
                </div>
                <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                  候选 {marketReview.boardCandidates.length + marketReview.stockCandidates.length} 项
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {marketReview.hotBoards.slice(0, 4).map((board) => (
                  <span key={board.id} className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700">
                    {board.name} · {boardStageLabel(board.stage)}
                  </span>
                ))}
              </div>
              <p className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                <FileClock className="h-4 w-4" />
                AI摘要：{marketReview.aiSummary.status === "failed" ? "失败，使用规则摘要" : "已生成"}；数据状态：{marketReview.dataStatus}
              </p>
            </Link>
            <div className="rounded-md border border-slate-200 bg-white p-3">
              <p className="text-xs font-semibold text-slate-500">市场复盘状态样本</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(["complete", "partial", "provider-degraded", "ai-summary-failed", "failed", "not-generated"] as const).map((status) => (
                  <span key={status} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700">
                    {marketReviewStatusLabel(status)}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`h-8 rounded px-3 text-sm font-semibold ${
        active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
      }`}
      type="button"
    >
      {children}
    </button>
  );
}
