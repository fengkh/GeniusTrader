"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, RefreshCw, ShieldAlert } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import {
  getSecurityMasterStatus,
  listSecurityMasterProviders,
  listSecurityMasterSyncRuns,
  startSecurityMasterSync
} from "@/lib/api/security-master";
import type {
  SecurityMasterProvider,
  SecurityMasterStatus,
  SecurityMasterSyncRun
} from "@/lib/api/types";

const sourceExchangeMap: Record<string, string[]> = {
  SSE_SECURITY_MASTER: ["SH"],
  SZSE_SECURITY_MASTER: ["SZ"],
  BSE_SECURITY_MASTER: ["BJ"],
  BAOSTOCK_DEVELOPMENT_FALLBACK: []
};

const exchangeLabels: Record<string, string> = {
  SH: "上交所",
  SZ: "深交所",
  BJ: "北交所"
};

const boardLabels: Record<string, string> = {
  main_board: "主板",
  star_board: "科创板",
  chinext: "创业板",
  bse: "北交所",
  unknown: "未知板块"
};

export default function SecurityMasterSettingsPage() {
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<SecurityMasterStatus | null>(null);
  const [providers, setProviders] = useState<SecurityMasterProvider[]>([]);
  const [runs, setRuns] = useState<SecurityMasterSyncRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncingSource, setSyncingSource] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const enabledProviders = useMemo(
    () => providers.filter((provider) => provider.implemented && provider.enabled_by_config),
    [providers]
  );

  const loadData = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [nextStatus, nextProviders, nextRuns] = await Promise.all([
        getSecurityMasterStatus(),
        listSecurityMasterProviders(),
        user.role === "admin" ? listSecurityMasterSyncRuns({ limit: 10 }) : Promise.resolve({ items: [], total: 0, limit: 10, offset: 0 })
      ]);
      setStatus(nextStatus);
      setProviders(nextProviders);
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

  async function syncSource(sourceCode: string) {
    setSyncingSource(sourceCode);
    setError(null);
    setMessage(null);
    try {
      const run = await startSecurityMasterSync({
        source_code: sourceCode,
        exchanges: sourceExchangeMap[sourceCode] ?? [],
        force: false
      });
      setMessage(`${sourceCode} 同步完成：${run.status}，收到 ${run.received_count} 条。`);
      await loadData();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSyncingSource(null);
    }
  }

  async function syncAll() {
    setSyncingSource("ALL");
    setError(null);
    setMessage(null);
    try {
      for (const provider of enabledProviders) {
        await startSecurityMasterSync({
          source_code: provider.source_code,
          exchanges: sourceExchangeMap[provider.source_code] ?? [],
          force: false
        });
      }
      setMessage("已按顺序触发全部可用证券目录来源。");
      await loadData();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSyncingSource(null);
    }
  }

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="证券目录状态需要登录后查看；同步能力仅管理员可见。"
        action={
          <Link
            href="/login?redirect=/settings/security-master"
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
        title="证券目录"
        description="证券基本信息来自证券目录同步；行情、财务、估值和技术指标仍未接入真实数据。普通用户搜索只读取本地 stocks 主数据。"
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
            当前阶段只验证 A 股证券基础目录；不接入实时行情、分钟行情、K 线、估值、自动调度或公告自动监控。
          </p>
        </div>
      </section>

      {error ? <ErrorState title="证券目录操作失败" description={error} /> : null}
      {message ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm font-medium text-emerald-900">
          {message}
        </div>
      ) : null}
      {loading || authLoading ? <LoadingSkeleton lines={8} /> : null}

      {!loading && !authLoading && user?.role !== "admin" ? (
        <EmptyState title="无管理员权限" description="普通用户可以搜索和管理自己的自选股，但不能触发证券目录同步。" />
      ) : null}

      {!loading && !authLoading && user?.role === "admin" ? (
        <>
          {status ? <StatusOverview status={status} /> : null}

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-slate-950">Provider</h2>
                <p className="mt-1 text-sm text-slate-500">
                  官方来源优先；BaoStock 仅作为开发补充或交叉核验来源。
                </p>
              </div>
              <button
                onClick={() => void syncAll()}
                disabled={syncingSource !== null || enabledProviders.length === 0}
                className="focus-ring inline-flex h-9 items-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
                type="button"
              >
                <RefreshCw className="h-4 w-4" />
                {syncingSource === "ALL" ? "同步中" : "同步全部可用来源"}
              </button>
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {providers.map((provider) => (
                <article key={provider.source_code} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-slate-950">{provider.source_code}</p>
                    <Pill tone={provider.official ? "blue" : "amber"}>{provider.official ? "官方候选" : "开发补充"}</Pill>
                    <Pill tone={provider.enabled_by_config ? "emerald" : "slate"}>
                      {provider.enabled_by_config ? "配置启用" : "配置关闭"}
                    </Pill>
                  </div>
                  <p className="mt-2 text-sm font-medium text-slate-800">{provider.display_name}</p>
                  <ul className="mt-2 space-y-1 text-xs leading-5 text-slate-500">
                    {provider.limitations.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                  <button
                    onClick={() => void syncSource(provider.source_code)}
                    disabled={!provider.enabled_by_config || syncingSource !== null}
                    className="focus-ring mt-3 h-9 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
                    type="button"
                  >
                    {syncingSource === provider.source_code ? "同步中" : `同步${provider.source_code}`}
                  </button>
                </article>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-4 py-3">
              <h2 className="text-base font-semibold text-slate-950">最近同步运行</h2>
            </div>
            <div className="divide-y divide-slate-100">
              {runs.map((run) => (
                <article key={run.id} className="grid gap-3 p-4 lg:grid-cols-[1fr_110px_140px_120px] lg:items-center">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-950">{run.source_code}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {formatTime(run.started_at)} / {run.exchanges.join("、") || "全部"}
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

function StatusOverview({ status }: { status: SecurityMasterStatus }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-base font-semibold text-slate-950">目录状态</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="股票总数" value={String(status.total_count)} />
        <Metric label="正常上市" value={String(status.active_count)} />
        <Metric label="development_seed" value={String(status.development_seed_count)} />
        <Metric label="seed 覆盖" value={String(status.seed_covered_count)} />
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <Breakdown title="交易所" values={status.by_exchange} labels={exchangeLabels} />
        <Breakdown title="板块" values={status.by_board} labels={boardLabels} />
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">
        来源：{status.sources.length ? status.sources.join("、") : "暂无"}；最近同步：
        {formatTime(status.last_synced_at) ?? "暂无"}；最近状态：{status.latest_sync_status ?? "暂无"}。
      </p>
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

function Breakdown({
  title,
  values,
  labels
}: {
  title: string;
  values: Record<string, number>;
  labels: Record<string, string>;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {Object.entries(values).map(([key, value]) => (
          <Pill key={key} tone="slate">
            {(labels[key] ?? key) + ` ${value}`}
          </Pill>
        ))}
        {Object.keys(values).length === 0 ? <span className="text-xs text-slate-500">暂无数据</span> : null}
      </div>
    </div>
  );
}

function Pill({
  children,
  tone = "slate"
}: {
  children: string;
  tone?: "slate" | "blue" | "amber" | "emerald";
}) {
  const tones = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    blue: "border-blue-200 bg-blue-50 text-blue-800",
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
