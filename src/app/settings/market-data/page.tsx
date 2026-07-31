"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, RefreshCw, ShieldAlert } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import {
  getMarketDataStatus,
  listMarketDataSyncRuns,
  startMarketDataSync
} from "@/lib/api/market-data";
import type { MarketDataStatus, MarketDataSyncRun } from "@/lib/api/types";

export default function MarketDataSettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [runs, setRuns] = useState<MarketDataSyncRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [nextStatus, nextRuns] = await Promise.all([
        getMarketDataStatus(),
        user.role === "admin" ? listMarketDataSyncRuns({ limit: 10 }) : Promise.resolve({ items: [], total: 0, limit: 10, offset: 0 })
      ]);
      setStatus(nextStatus);
      setRuns(nextRuns.items);
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

  async function syncMarketData() {
    setSyncing(true);
    setError(null);
    setMessage(null);
    try {
      const run = await startMarketDataSync({
        source_code: "BAOSTOCK",
        sync_mode: "latest_completed_trade_day",
        use_current_watchlist: true,
        dry_run: false
      });
      setMessage(`行情同步完成：${run.status}，收到 ${run.received_count} 条。`);
      await loadData();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSyncing(false);
    }
  }

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="行情数据源状态需要登录后查看。"
        action={
          <Link
            href="/login?redirect=/settings/market-data"
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
        eyebrow="管理员设置"
        title="行情数据"
        description="查看真实日级行情快照来源、授权状态和同步运行。未确认生产授权前，Tushare 不作为生产主来源。"
        actions={
          <Link
            href="/settings"
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            返回设置
          </Link>
        }
      />

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <div className="flex gap-2">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <p>
            Tushare 当前仅为开发验证候选。个人 Token 不等于生产授权；生产公开展示、再分发和派生数据展示必须等待授权冻结。
          </p>
        </div>
      </section>

      {error ? <ErrorState title="行情数据操作失败" description={error} /> : null}
      {message ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm font-medium text-emerald-900">{message}</div> : null}
      {loading || authLoading ? <LoadingSkeleton lines={8} /> : null}

      {!loading && !authLoading && user?.role !== "admin" ? (
        <EmptyState title="无管理员权限" description="普通用户可以查看行情空状态，但不能触发数据同步。" />
      ) : null}

      {!loading && !authLoading && user?.role === "admin" ? (
        <>
          {status ? <StatusOverview status={status} /> : null}
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-slate-950">手动同步</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  同步只写入已有股票的日级快照；Provider 未配置或未授权时不会写入任何行情。
                </p>
              </div>
              <button
                onClick={() => void syncMarketData()}
                disabled={syncing}
                className="focus-ring inline-flex h-9 items-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                type="button"
              >
                <RefreshCw className="h-4 w-4" />
                {syncing ? "同步中" : "同步最近完整交易日"}
              </button>
            </div>
          </section>
          <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-4 py-3">
              <h2 className="text-base font-semibold text-slate-950">最近行情同步运行</h2>
            </div>
            <div className="divide-y divide-slate-100">
              {runs.map((run) => (
                <article key={run.id} className="grid gap-3 p-4 lg:grid-cols-[1fr_110px_160px_160px] lg:items-center">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-950">{run.source_code}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {formatTime(run.started_at)} / 交易日 {run.resolved_trade_date ?? "暂无"}
                    </p>
                  </div>
                  <Pill tone={run.status === "complete" ? "emerald" : run.status === "partial" ? "amber" : "slate"}>
                    {run.status}
                  </Pill>
                  <p className="text-xs leading-5 text-slate-600">
                    收到 {run.received_count}，新增 {run.created_count}，更新 {run.updated_count}
                  </p>
                  <p className="text-xs leading-5 text-slate-500">
                    失败 {run.failure_count}
                    {run.error_code ? ` / ${run.error_code}` : ""}
                  </p>
                </article>
              ))}
              {runs.length === 0 ? <p className="p-4 text-sm text-slate-500">暂无同步运行记录。</p> : null}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function StatusOverview({ status }: { status: MarketDataStatus }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-base font-semibold text-slate-950">数据源状态</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="最近完整交易日" value={status.latest_trade_date ?? "暂无"} />
        <Metric label="最新来源" value={status.latest_source_code ?? "暂无"} />
        <Metric label="最新同步状态" value={status.latest_sync_status ?? "暂无"} />
        <Metric label="最后更新时间" value={formatTime(status.latest_fetched_at) ?? "暂无"} />
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {status.sources.map((source) => (
          <article key={source.source_code} className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-semibold text-slate-950">{source.source_code}</p>
              <Pill tone={source.production_enabled ? "emerald" : "amber"}>
                {source.production_enabled ? "生产可用" : "生产关闭"}
              </Pill>
              <Pill tone="slate">{source.authorization_status}</Pill>
            </div>
            <p className="mt-2 text-sm text-slate-700">{source.display_name}</p>
            <p className="mt-2 text-xs leading-5 text-slate-500">{source.limitations.join(" ")}</p>
          </article>
        ))}
      </div>
      {status.data_gaps.length > 0 ? (
        <ul className="mt-3 space-y-1 rounded-md bg-amber-50 p-3 text-xs leading-5 text-amber-900">
          {status.data_gaps.map((gap) => (
            <li key={gap}>{gap}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function Pill({ children, tone = "slate" }: { children: string; tone?: "slate" | "amber" | "emerald" }) {
  const tones = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-800"
  };
  return <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}>{children}</span>;
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
