"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, ClipboardList, FileText, Layers3, MessageSquareWarning, RefreshCw } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import { getMarketDataStatus, getWatchlistMarketSnapshots } from "@/lib/api/market-data";
import type { DecimalValue, MarketDataStatus, WatchlistMarketSnapshot } from "@/lib/api/types";

export default function TodayPage() {
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [snapshots, setSnapshots] = useState<WatchlistMarketSnapshot[]>([]);
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
      const [nextStatus, nextSnapshots] = await Promise.all([
        getMarketDataStatus(),
        getWatchlistMarketSnapshots()
      ]);
      setStatus(nextStatus);
      setSnapshots(nextSnapshots);
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

  const summary = useMemo(() => buildSummary(snapshots), [snapshots]);

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="今日页读取当前用户自选股和真实行情状态，请先登录。"
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

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="今日复盘台"
        title="今日"
        description="先看真实数据日期、来源状态和自选股整体表现；没有真实行情时不展示模拟价格。"
        actions={
          <button
            onClick={() => void loadData()}
            disabled={loading}
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
            type="button"
          >
            <RefreshCw className="h-4 w-4" />
            {loading ? "刷新中" : "刷新"}
          </button>
        }
      />

      {error ? <ErrorState title="今日页加载失败" description={error} /> : null}
      {loading || authLoading ? <LoadingSkeleton lines={8} /> : null}

      {!loading && !authLoading ? (
        <>
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold text-slate-500">1. 数据日期、来源状态和最后更新时间</p>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <MetricCard label="最近完整交易日" value={status?.latest_trade_date ?? "暂无"} />
              <MetricCard label="行情来源" value={status?.latest_source_code ?? "暂无经授权的真实行情数据"} />
              <MetricCard label="最后更新时间" value={formatTime(status?.latest_fetched_at ?? null) ?? "暂无"} />
            </div>
            <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-900">
              {status?.user_notice ?? "开发验证来源，尚未确认公开展示授权。"}
              {status?.data_gaps.length ? ` ${status.data_gaps.join(" ")}` : ""}
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-semibold text-slate-500">2. 自选股整体表现</p>
            {snapshots.length === 0 ? (
              <div className="mt-4">
                <EmptyState
                  title="暂无自选股"
                  description="请先进入自选股页添加真实股票。没有自选股时今日页不生成模拟表现。"
                  action={
                    <Link
                      href="/watchlist"
                      className="focus-ring inline-flex h-10 items-center justify-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800"
                    >
                      去自选股页
                    </Link>
                  }
                />
              </div>
            ) : (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                <MetricCard label="自选股总数" value={`${summary.total}只`} />
                <MetricCard label="上涨" value={`${summary.rising}只`} tone="text-red-600" />
                <MetricCard label="下跌" value={`${summary.falling}只`} tone="text-emerald-700" />
                <MetricCard label="停牌/未交易" value={`${summary.notTrading}只`} />
                <MetricCard label="数据异常" value={`${summary.dataIssues}只`} tone="text-orange-700" />
                <MetricCard label="平均表现" value={summary.averageChange === null ? "暂无" : formatChange(summary.averageChange)} tone={changeTone(summary.averageChange)} />
              </div>
            )}
          </section>

          <PlaceholderSection
            index="3"
            icon={<AlertCircle className="h-5 w-5 text-rose-700" />}
            title="今日重大异动"
            description="真实异动规则需要真实行情快照和历史样本验证；当前不会用虚构异动填充。"
          />
          <PlaceholderSection
            index="4"
            icon={<FileText className="h-5 w-5 text-blue-700" />}
            title="重大公告与重要资讯"
            description="公告候选收件箱和人工导入闭环已独立存在；今日页聚合待后续真实资讯自动更新完成后接入。"
          />
          <PlaceholderSection
            index="5"
            icon={<Layers3 className="h-5 w-5 text-slate-700" />}
            title="板块和个人分组表现"
            description="板块表现需要真实行情快照覆盖后计算；无真实快照时不展示模拟分组涨跌。"
          />
          <PlaceholderSection
            index="6"
            icon={<MessageSquareWarning className="h-5 w-5 text-amber-700" />}
            title="舆情变化与待核实信息"
            description="舆情仍以用户主动录入和 AI 分析结果为准；当前不做全网自动爬取。"
          />
          <PlaceholderSection
            index="7"
            icon={<ClipboardList className="h-5 w-5 text-blue-700" />}
            title="今日整体复盘"
            description="每日复盘继续由复盘页触发；今日页只在真实聚合接入后展示摘要。"
          />
          <PlaceholderSection
            index="8"
            icon={<ClipboardList className="h-5 w-5 text-slate-700" />}
            title="待处理舆情和未完成复盘"
            description="待处理任务需要真实业务事件聚合后显示；当前不使用模拟任务数量。"
          />
        </>
      ) : null}
    </div>
  );
}

function PlaceholderSection({
  index,
  icon,
  title,
  description
}: {
  index: string;
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        {icon}
        <div>
          <p className="text-xs font-semibold text-slate-500">{index}. {title}</p>
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
        </div>
      </div>
      <div className="mt-4">
        <EmptyState title="待真实数据接入" description={description} />
      </div>
    </section>
  );
}

function MetricCard({ label, value, tone = "text-slate-950" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function buildSummary(rows: WatchlistMarketSnapshot[]) {
  const changes = rows
    .map((row) => decimalNumber(row.snapshot?.pct_change ?? null))
    .filter((value): value is number => value !== null);
  const averageChange = changes.length
    ? changes.reduce((sum, value) => sum + value, 0) / changes.length
    : null;
  return {
    total: rows.length,
    rising: changes.filter((value) => value > 0).length,
    falling: changes.filter((value) => value < 0).length,
    notTrading: rows.filter((row) => row.snapshot?.is_trading === false).length,
    dataIssues: rows.filter((row) => row.status !== "available").length,
    averageChange
  };
}

function decimalNumber(value: DecimalValue | null): number | null {
  if (value === null) {
    return null;
  }
  const numberValue = Number(value);
  return Number.isFinite(numberValue) ? numberValue : null;
}

function formatChange(value: number): string {
  const direction = value > 0 ? "上涨" : value < 0 ? "下跌" : "持平";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}% ${direction}`;
}

function changeTone(value: number | null): string {
  if (value === null) {
    return "text-slate-500";
  }
  if (value > 0) {
    return "text-red-600";
  }
  if (value < 0) {
    return "text-emerald-700";
  }
  return "text-slate-600";
}

function formatTime(value: string | null): string | null {
  if (!value) {
    return null;
  }
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  } catch {
    return value;
  }
}
