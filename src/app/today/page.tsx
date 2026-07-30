"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  AlertCircle,
  CheckSquare,
  ClipboardList,
  FileText,
  RefreshCw,
  Star
} from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import type { TodayActionItem, TodayOverview } from "@/lib/api/types";
import { getTodayOverview } from "@/lib/api/workbench";

export default function TodayPage() {
  const { user, loading: authLoading } = useAuth();
  const [overview, setOverview] = useState<TodayOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setOverview(await getTodayOverview());
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!authLoading) {
      const timer = window.setTimeout(() => {
        void loadData();
      }, 0);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [authLoading, loadData]);

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="今日研究总览读取当前用户自选股、研究事项和复盘状态，请先登录。"
        action={
          <Link
            href="/login?redirect=/today"
            className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
          >
            去登录
          </Link>
        }
      />
    );
  }

  const stats = overview?.overview;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="研究工作台"
        title="今日"
        description="聚合自选股、公告候选、待分析信息、研究事项、观察条件和最新复盘状态；不生成模拟行情或投资建议。"
        actions={
          <button
            onClick={() => void loadData()}
            disabled={loading}
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
            type="button"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            {loading ? "刷新中" : "刷新"}
          </button>
        }
      />

      {error ? <ErrorState title="今日研究总览加载失败" description={error} /> : null}
      {loading || authLoading ? <LoadingSkeleton lines={8} /> : null}

      {!loading && !authLoading && overview ? (
        <>
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold text-slate-500">1. 数据日期、来源状态和最后更新时间</p>
            <div className="mt-3 grid gap-3 md:grid-cols-4">
              <MetricCard label="业务日期" value={stats?.business_date ?? "暂无"} />
              <MetricCard label="自选股" value={`${stats?.watchlist_count ?? 0}只`} />
              <MetricCard label="行情状态" value={marketStatusLabel(stats?.market_data_status)} />
              <MetricCard label="最新复盘" value={reviewStatusLabel(stats?.latest_review_status)} />
            </div>
            <p className="mt-3 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm leading-6 text-blue-950">
              今日页只展示后端已聚合的用户私有数据。行情、公告、AI 分析和研究事项的失败会分区降级，不会让整页不可用。
            </p>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold text-slate-500">2. 自选股整体研究状态</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <MetricCard label="新增信息相关股票" value={`${stats?.stocks_with_new_information ?? 0}只`} />
              <MetricCard label="新公告候选" value={`${stats?.new_announcement_candidate_count ?? 0}条`} />
              <MetricCard label="待处理公告候选" value={`${stats?.pending_announcement_candidate_count ?? 0}条`} />
              <MetricCard label="待分析信息" value={`${stats?.information_needing_analysis_count ?? 0}条`} />
              <MetricCard label="打开研究事项" value={`${stats?.open_research_task_count ?? 0}项`} />
              <MetricCard label="到期观察条件" value={`${stats?.due_observation_count ?? 0}项`} />
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <Star className="h-5 w-5 text-amber-700" />
              <h2 className="text-lg font-semibold text-slate-950">3. 需要优先查看的自选股</h2>
            </div>
            {overview.priority_stocks.length === 0 ? (
              <EmptyBlock title="暂无优先股票" description="当前没有公告候选、待办或观察条件触发优先级。" />
            ) : (
              <div className="mt-4 grid gap-3">
                {overview.priority_stocks.map((stock) => (
                  <Link
                    key={stock.stock_id}
                    href={`/watchlist/${stock.stock_id}`}
                    className="focus-ring grid gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 hover:bg-white md:grid-cols-[1fr_100px_1.6fr]"
                  >
                    <div>
                      <p className="font-semibold text-slate-950">{stock.name}</p>
                      <p className="text-xs text-slate-500">{stock.symbol}</p>
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-slate-950">{stock.priority_score}</p>
                      <p className="text-xs text-slate-500">关注分</p>
                    </div>
                    <p className="text-sm leading-6 text-slate-700">
                      {stock.priority_reasons.length ? stock.priority_reasons.join("；") : "暂无具体触发原因。"}
                    </p>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <ActionSection actions={overview.action_items} />

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <CheckSquare className="h-5 w-5 text-blue-700" />
              <h2 className="text-lg font-semibold text-slate-950">5. 今日到期观察条件</h2>
            </div>
            {overview.observation_conditions.length === 0 ? (
              <EmptyBlock title="暂无到期观察条件" description="用户采纳或创建观察条件后，到期项会在这里提示验证。" />
            ) : (
              <div className="mt-4 grid gap-2">
                {overview.observation_conditions.map((item) => (
                  <Link
                    key={item.task_id}
                    href={`/information/tasks?task=${item.task_id}`}
                    className="focus-ring rounded-md border border-blue-100 bg-blue-50 p-3 text-sm leading-6 text-blue-950 hover:bg-white"
                  >
                    <span className="font-semibold">{item.title}</span>
                    <span className="ml-2 text-blue-700">
                      {item.stock ? `${item.stock.name} · ${item.stock.symbol}` : "未关联个股"}
                    </span>
                    <span className="ml-2 text-blue-700">到期：{item.due_date ?? "未设置"}</span>
                  </Link>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <ClipboardList className="h-5 w-5 text-slate-700" />
              <h2 className="text-lg font-semibold text-slate-950">6. 今日整体复盘状态</h2>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-4">
              <MetricCard label="复盘日期" value={overview.latest_review.review_date ?? "暂无"} />
              <MetricCard label="状态" value={reviewStatusLabel(overview.latest_review.status)} />
              <MetricCard label="版本" value={overview.latest_review.version ? `v${overview.latest_review.version}` : "暂无"} />
              <MetricCard label="生成任务" value={overview.latest_review.generation_in_progress ? "生成中" : "空闲"} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                href="/reviews"
                className="focus-ring inline-flex h-9 items-center rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800"
              >
                进入复盘历史
              </Link>
              {overview.latest_review.review_id ? (
                <Link
                  href={`/reviews/${overview.latest_review.review_id}`}
                  className="focus-ring inline-flex h-9 items-center rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                >
                  查看最新复盘
                </Link>
              ) : null}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function ActionSection({ actions }: { actions: TodayActionItem[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <AlertCircle className="h-5 w-5 text-rose-700" />
        <h2 className="text-lg font-semibold text-slate-950">4. 今日待处理事项</h2>
      </div>
      {actions.length === 0 ? (
        <EmptyBlock title="暂无待处理事项" description="没有待分析信息、待处理公告候选、过期复盘或到期观察条件。" />
      ) : (
        <div className="mt-4 grid gap-2 md:grid-cols-2">
          {actions.map((action) => (
            <Link
              key={`${action.target_url}-${action.title}`}
              href={action.target_url}
              className={`focus-ring rounded-md border p-3 text-sm font-semibold hover:bg-white ${actionTone(action.severity)}`}
            >
              <FileText className="mb-2 h-4 w-4" />
              {action.title}：{action.count}
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

function EmptyBlock({ title, description }: { title: string; description: string }) {
  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function marketStatusLabel(value?: string | null): string {
  if (value === "available") {
    return "可用";
  }
  if (value === "partial" || value === "stale") {
    return "部分可用";
  }
  return "暂无可用行情";
}

function reviewStatusLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    complete: "完整",
    partial: "部分完成",
    empty: "空复盘",
    failed: "失败",
    stale: "需要更新"
  };
  return value ? labels[value] ?? value : "暂无";
}

function actionTone(value: "info" | "notice" | "important"): string {
  if (value === "important") {
    return "border-rose-200 bg-rose-50 text-rose-900";
  }
  if (value === "notice") {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }
  return "border-blue-200 bg-blue-50 text-blue-900";
}
