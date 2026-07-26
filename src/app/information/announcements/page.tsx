"use client";

import Link from "next/link";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  DownloadCloud,
  ExternalLink,
  Filter,
  RefreshCw,
  Search,
} from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import {
  importAnnouncementCandidate,
  listAnnouncementCandidates,
  listAnnouncementSyncRuns,
  patchAnnouncementCandidate,
  startAnnouncementSyncRun
} from "@/lib/api/announcements";
import { humanizeApiError } from "@/lib/api/errors";
import { listAnnouncementProviders, listExternalSources } from "@/lib/api/external-sources";
import { listWatchlistItems } from "@/lib/api/watchlist";
import type {
  AnnouncementCandidateSummary,
  AnnouncementProvider,
  ExternalSource,
  Page,
  ProviderSyncRun,
  UUID,
  WatchlistItemRead
} from "@/lib/api/types";

const EXPERIMENTAL_NOTICE =
  "当前公告同步功能处于实验阶段，数据来源、完整性、及时性、稳定性及使用授权尚未最终确认。";

type StatusFilter = "" | "pending" | "reviewed" | "dismissed" | "imported" | "unavailable";

interface Filters {
  status: StatusFilter;
  sourceCode: string;
  q: string;
  dateFrom: string;
  dateTo: string;
  limit: number;
  offset: number;
}

interface SyncForm {
  sourceCode: string;
  dateFrom: string;
  dateTo: string;
  useCurrentWatchlist: boolean;
  selectedStockIds: UUID[];
}

const today = new Date();
const defaultDateTo = toDateInput(today);
const defaultDateFrom = toDateInput(new Date(today.getTime() - 6 * 24 * 60 * 60 * 1000));

const defaultFilters: Filters = {
  status: "",
  sourceCode: "",
  q: "",
  dateFrom: "",
  dateTo: "",
  limit: 20,
  offset: 0
};

export default function AnnouncementInboxPage() {
  const { user, loading: authLoading } = useAuth();
  const [sources, setSources] = useState<ExternalSource[]>([]);
  const [providers, setProviders] = useState<AnnouncementProvider[]>([]);
  const [watchlist, setWatchlist] = useState<WatchlistItemRead[]>([]);
  const [runs, setRuns] = useState<Page<ProviderSyncRun> | null>(null);
  const [candidates, setCandidates] = useState<Page<AnnouncementCandidateSummary> | null>(null);
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [draftFilters, setDraftFilters] = useState<Filters>(defaultFilters);
  const [syncForm, setSyncForm] = useState<SyncForm>({
    sourceCode: "CNINFO",
    dateFrom: defaultDateFrom,
    dateTo: defaultDateTo,
    useCurrentWatchlist: true,
    selectedStockIds: []
  });
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const syncInFlightRef = useRef(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const providerBySource = useMemo(
    () => new Map(providers.map((provider) => [provider.source_code, provider])),
    [providers]
  );
  const currentSource = sources.find((source) => source.source_code === syncForm.sourceCode);
  const latestRun = runs?.items[0] ?? null;

  const loadAll = useCallback(async () => {
    if (!user) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [sourceRows, providerRows, watchlistPage, runPage, candidatePage] = await Promise.all([
        listExternalSources({ source_category: "exchange_announcement" }),
        listAnnouncementProviders(),
        listWatchlistItems({ limit: 100 }),
        listAnnouncementSyncRuns({ limit: 5 }),
        listAnnouncementCandidates({
          status: filters.status || undefined,
          source_code: filters.sourceCode || undefined,
          q: filters.q || undefined,
          date_from: filters.dateFrom || undefined,
          date_to: filters.dateTo || undefined,
          limit: filters.limit,
          offset: filters.offset
        })
      ]);
      setSources(sourceRows);
      setProviders(providerRows);
      setWatchlist(watchlistPage.items);
      setRuns(runPage);
      setCandidates(candidatePage);
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [filters, user]);

  useEffect(() => {
    if (!authLoading && user) {
      const timeoutId = window.setTimeout(() => {
        void loadAll();
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }
    return undefined;
  }, [authLoading, loadAll, user]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFilters({ ...draftFilters, offset: 0 });
  }

  function clearFilters() {
    setDraftFilters(defaultFilters);
    setFilters(defaultFilters);
  }

  async function handleSync(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (syncInFlightRef.current) {
      return;
    }
    syncInFlightRef.current = true;
    setSyncing(true);
    setError(null);
    setSuccess(null);
    try {
      const run = await startAnnouncementSyncRun({
        source_code: syncForm.sourceCode,
        date_from: syncForm.dateFrom,
        date_to: syncForm.dateTo,
        use_current_watchlist: syncForm.useCurrentWatchlist,
        stock_ids: syncForm.useCurrentWatchlist ? [] : syncForm.selectedStockIds
      });
      setSuccess(`同步完成：${run.status}，生成/更新候选 ${run.candidate_count} 条。`);
      await loadAll();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      syncInFlightRef.current = false;
      setSyncing(false);
    }
  }

  async function runCandidateAction(label: string, action: () => Promise<unknown>) {
    setActionLoading(label);
    setError(null);
    setSuccess(null);
    try {
      await action();
      setSuccess(`${label}已完成。`);
      await loadAll();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setActionLoading(null);
    }
  }

  function toggleStock(stockId: UUID) {
    setSyncForm((current) => ({
      ...current,
      selectedStockIds: current.selectedStockIds.includes(stockId)
        ? current.selectedStockIds.filter((item) => item !== stockId)
        : [...current.selectedStockIds, stockId]
    }));
  }

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="公告候选属于用户私有收件箱，请先登录。"
        action={
          <Link
            href="/login?redirect=/information/announcements"
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
        eyebrow="信息中心"
        title="公告候选收件箱"
        description="从当前用户自选股出发，人工同步、人工审核并主动导入上市公司公告。候选不会自动进入复盘或触发 AI。"
        actions={
          <Link
            href="/information"
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            返回信息中心
          </Link>
        }
      />

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <div className="flex gap-2">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <p>{EXPERIMENTAL_NOTICE} 不提供实时监控、永久订阅、全市场扫描、自动导入、自动 AI 或自动通知。</p>
        </div>
      </section>

      {error ? <ErrorState title="操作失败" description={error} /> : null}
      {success ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          {success}
        </div>
      ) : null}

      {loading ? <LoadingSkeleton lines={9} /> : null}

      {!loading ? (
        <>
          <section className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-base font-semibold text-slate-950">状态区</h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <Metric label="当前来源" value={currentSource?.display_name ?? syncForm.sourceCode} />
                <Metric label="Provider健康" value={currentSource?.health_status ?? "unknown"} />
                <Metric label="来源等级" value={currentSource ? `${currentSource.authority_level}/${currentSource.source_tier}` : "unknown"} />
                <Metric label="授权状态" value={currentSource?.authorization_status ?? "unknown"} />
              </div>
              <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-600">
                最近同步：
                {latestRun ? (
                  <>
                    {formatDateTime(latestRun.started_at)} · {latestRun.status} · 记录 {latestRun.record_count} · 候选{" "}
                    {latestRun.candidate_count}
                    {latestRun.error_summary ? ` · ${latestRun.error_summary}` : ""}
                  </>
                ) : (
                  "暂无同步记录"
                )}
              </div>
            </div>

            <form
              aria-busy={syncing}
              className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
              onSubmit={handleSync}
            >
              <h2 className="text-base font-semibold text-slate-950">人工同步区</h2>
              <p className="mt-1 text-sm leading-6 text-slate-600">
                仅同步当前用户自选股，服务端限制最多 20 只股票、最近 7 日、最多 50 条记录。
              </p>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <Field label="来源">
                  <select
                    value={syncForm.sourceCode}
                    onChange={(event) => setSyncForm({ ...syncForm, sourceCode: event.target.value })}
                    disabled={syncing}
                    className="focus-ring h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                  >
                    {providers.filter((provider) => provider.implemented).map((provider) => (
                      <option key={provider.source_code} value={provider.source_code}>
                        {provider.source_code}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="开始日期">
                  <input
                    type="date"
                    value={syncForm.dateFrom}
                    onChange={(event) => setSyncForm({ ...syncForm, dateFrom: event.target.value })}
                    disabled={syncing}
                    className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                  />
                </Field>
                <Field label="结束日期">
                  <input
                    type="date"
                    value={syncForm.dateTo}
                    onChange={(event) => setSyncForm({ ...syncForm, dateTo: event.target.value })}
                    disabled={syncing}
                    className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                  />
                </Field>
              </div>
              <label className="mt-3 flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <span>使用当前全部自选股</span>
                <input
                  type="checkbox"
                  checked={syncForm.useCurrentWatchlist}
                  onChange={(event) => setSyncForm({ ...syncForm, useCurrentWatchlist: event.target.checked })}
                  disabled={syncing}
                  className="h-4 w-4 rounded border-slate-300"
                />
              </label>
              {!syncForm.useCurrentWatchlist ? (
                <div className="mt-3 max-h-40 overflow-y-auto rounded-md border border-slate-200 bg-slate-50 p-2">
                  {watchlist.length === 0 ? (
                    <p className="p-2 text-sm text-slate-500">暂无自选股。</p>
                  ) : (
                    <div className="grid gap-2 sm:grid-cols-2">
                      {watchlist.map((item) => (
                        <label key={item.id} className="flex items-center gap-2 rounded bg-white p-2 text-sm">
                          <input
                            type="checkbox"
                            checked={syncForm.selectedStockIds.includes(item.stock.id)}
                            onChange={() => toggleStock(item.stock.id)}
                            disabled={syncing}
                            className="h-4 w-4 rounded border-slate-300"
                          />
                          <span className="font-medium text-slate-900">{item.stock.name}</span>
                          <span className="text-xs text-slate-500">{item.stock.exchange}{item.stock.symbol}</span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              ) : null}
              <button
                className="focus-ring mt-3 inline-flex h-10 items-center gap-2 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                disabled={syncing}
                type="submit"
              >
                {syncing ? <RefreshCw className="h-4 w-4 animate-spin" /> : <DownloadCloud className="h-4 w-4" />}
                {syncing ? "同步中" : "同步公告候选"}
              </button>
              {syncing ? (
                <div
                  className="mt-3 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm leading-6 text-blue-900"
                  role="status"
                >
                  正在向后端发起公告候选同步请求。同步期间已禁用表单和按钮，请求完成或失败后可以再次操作。
                </div>
              ) : null}
              <p className="mt-2 text-xs text-slate-500">
                当前配置：{providerBySource.get(syncForm.sourceCode)?.enabled_by_config ? "Provider配置已启用" : "Provider配置关闭"}；
                来源注册：{currentSource?.enabled ? "已启用" : "未启用"}。
              </p>
            </form>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <form className="grid gap-3 lg:grid-cols-[140px_160px_1fr_130px]" onSubmit={applyFilters}>
              <select
                value={draftFilters.status}
                onChange={(event) => setDraftFilters({ ...draftFilters, status: event.target.value as StatusFilter })}
                className="focus-ring h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
              >
                <option value="">待处理和已查看</option>
                <option value="pending">待处理</option>
                <option value="reviewed">已查看</option>
                <option value="dismissed">已忽略</option>
                <option value="imported">已导入</option>
                <option value="unavailable">不可用</option>
              </select>
              <select
                value={draftFilters.sourceCode}
                onChange={(event) => setDraftFilters({ ...draftFilters, sourceCode: event.target.value })}
                className="focus-ring h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"
              >
                <option value="">全部来源</option>
                {sources.map((source) => (
                  <option key={source.id} value={source.source_code}>{source.display_name}</option>
                ))}
              </select>
              <label className="relative block min-w-0">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
                <input
                  value={draftFilters.q}
                  onChange={(event) => setDraftFilters({ ...draftFilters, q: event.target.value })}
                  className="focus-ring h-10 w-full rounded-md border border-slate-300 pl-9 pr-3 text-sm"
                  placeholder="搜索标题或公司"
                />
              </label>
              <div className="flex gap-2">
                <button
                  className="focus-ring inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white"
                  type="submit"
                >
                  <Filter className="h-4 w-4" />
                  筛选
                </button>
                <button
                  onClick={clearFilters}
                  className="focus-ring h-10 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700"
                  type="button"
                >
                  清除
                </button>
              </div>
            </form>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <input
                type="date"
                value={draftFilters.dateFrom}
                onChange={(event) => setDraftFilters({ ...draftFilters, dateFrom: event.target.value })}
                className="focus-ring h-10 rounded-md border border-slate-300 px-3 text-sm"
              />
              <input
                type="date"
                value={draftFilters.dateTo}
                onChange={(event) => setDraftFilters({ ...draftFilters, dateTo: event.target.value })}
                className="focus-ring h-10 rounded-md border border-slate-300 px-3 text-sm"
              />
              <div className="flex items-center rounded-md bg-slate-50 px-3 text-sm text-slate-600">
                结果：{candidates?.total ?? 0} 条
              </div>
            </div>
          </section>

          {candidates && candidates.items.length > 0 ? (
            <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <div className="hidden grid-cols-[1fr_130px_120px_120px_150px] gap-3 border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-500 lg:grid">
                <span>公告</span>
                <span>类型</span>
                <span>来源</span>
                <span>状态</span>
                <span>操作</span>
              </div>
              {candidates.items.map((candidate) => (
                <CandidateRow
                  key={candidate.id}
                  candidate={candidate}
                  actionLoading={actionLoading}
                  onReview={() => runCandidateAction("标记已查看", () => patchAnnouncementCandidate(candidate.id, "reviewed"))}
                  onDismiss={() => runCandidateAction("忽略候选", () => patchAnnouncementCandidate(candidate.id, "dismissed"))}
                  onImport={() =>
                    runCandidateAction("元数据导入", () =>
                      importAnnouncementCandidate(candidate.id, { import_mode: "metadata_only" })
                    )
                  }
                />
              ))}
            </section>
          ) : (
            <EmptyState
              title="暂无公告候选"
              description="可以在功能开关和来源注册均启用后，人工同步当前自选股的公告候选。"
              action={
                <button
                  onClick={() => void loadAll()}
                  className="focus-ring inline-flex h-10 items-center gap-2 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
                  type="button"
                >
                  <RefreshCw className="h-4 w-4" />
                  重新加载
                </button>
              }
            />
          )}
        </>
      ) : null}
    </div>
  );
}

function CandidateRow({
  candidate,
  actionLoading,
  onReview,
  onDismiss,
  onImport
}: {
  candidate: AnnouncementCandidateSummary;
  actionLoading: string | null;
  onReview: () => void;
  onDismiss: () => void;
  onImport: () => void;
}) {
  return (
    <article className="grid gap-2 border-b border-slate-100 px-4 py-3 last:border-b-0 lg:grid-cols-[1fr_130px_120px_120px_150px] lg:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Link href={`/information/announcements/${candidate.id}`} className="focus-ring min-w-0 text-sm font-semibold text-slate-950 hover:text-blue-700">
            {candidate.title}
          </Link>
          <Pill tone={candidate.is_pdf ? "blue" : "slate"}>{candidate.is_pdf ? "PDF" : "无PDF"}</Pill>
          <Pill tone={candidate.authorization_status === "approved" ? "emerald" : "amber"}>
            授权{candidate.authorization_status}
          </Pill>
        </div>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          {candidate.company_name ?? "未知公司"} · {candidate.stock_symbols.join("、") || "未确认股票"} ·{" "}
          {candidate.published_at ? formatDateTime(candidate.published_at) : "发布时间未知"}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          匹配：{candidate.match_type} · 完整度：{candidate.data_completeness} · PDF提取：{candidate.document_extract_status}
        </p>
      </div>
      <Pill>{candidate.announcement_type}</Pill>
      <span className="text-xs font-medium text-slate-700">{candidate.source_display_name}</span>
      <Pill tone={statusTone(candidate.status)}>{statusLabel(candidate.status)}</Pill>
      <div className="flex flex-wrap gap-2">
        <Link
          href={`/information/announcements/${candidate.id}`}
          className="focus-ring inline-flex h-8 items-center rounded-md border border-slate-300 px-2 text-xs font-semibold text-slate-700"
        >
          查看
        </Link>
        {candidate.document_url ? (
          <a
            href={candidate.document_url}
            target="_blank"
            rel="noreferrer"
            className="focus-ring inline-flex h-8 items-center rounded-md border border-slate-300 px-2 text-xs font-semibold text-slate-700"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        ) : null}
        {candidate.status !== "reviewed" ? (
          <button className="focus-ring h-8 rounded-md border border-blue-200 px-2 text-xs font-semibold text-blue-800" disabled={!!actionLoading} onClick={onReview} type="button">
            已查看
          </button>
        ) : null}
        {candidate.status !== "dismissed" ? (
          <button className="focus-ring h-8 rounded-md border border-slate-300 px-2 text-xs font-semibold text-slate-700" disabled={!!actionLoading} onClick={onDismiss} type="button">
            忽略
          </button>
        ) : null}
        {candidate.status !== "imported" ? (
          <button className="focus-ring h-8 rounded-md bg-slate-900 px-2 text-xs font-semibold text-white" disabled={!!actionLoading} onClick={onImport} type="button">
            导入
          </button>
        ) : null}
      </div>
    </article>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function Pill({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "blue" | "amber" | "emerald" | "rose" }) {
  const tones = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    blue: "border-blue-200 bg-blue-50 text-blue-800",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
    rose: "border-rose-200 bg-rose-50 text-rose-800"
  };
  return <span className={`w-fit rounded-md border px-2 py-1 text-xs font-semibold ${tones[tone]}`}>{children}</span>;
}

function statusTone(status: string): "slate" | "blue" | "amber" | "emerald" | "rose" {
  if (status === "imported") {
    return "emerald";
  }
  if (status === "dismissed" || status === "unavailable") {
    return "rose";
  }
  if (status === "reviewed") {
    return "blue";
  }
  return "amber";
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: "待处理",
    reviewed: "已查看",
    dismissed: "已忽略",
    imported: "已导入",
    unavailable: "不可用"
  };
  return labels[status] ?? status;
}

function toDateInput(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
