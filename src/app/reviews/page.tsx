"use client";

import Link from "next/link";
import { AlertTriangle, CalendarDays, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import { generateDailyReview, listDailyReviews } from "@/lib/api/reviews";
import type {
  DailyReviewGenerationMode,
  DailyReviewStatus,
  DailyReviewSummary,
  Page
} from "@/lib/api/types";

interface ReviewFilters {
  status: DailyReviewStatus | "";
  dateFrom: string;
  dateTo: string;
  limit: number;
  offset: number;
}

const defaultFilters: ReviewFilters = {
  status: "",
  dateFrom: "",
  dateTo: "",
  limit: 20,
  offset: 0
};

const statusOptions: Array<{ value: DailyReviewStatus | ""; label: string }> = [
  { value: "", label: "全部状态" },
  { value: "complete", label: "完整" },
  { value: "partial", label: "部分完成" },
  { value: "empty", label: "空复盘" },
  { value: "failed", label: "失败" },
  { value: "stale", label: "需要更新" }
];

export default function ReviewsPage() {
  const { user, loading: authLoading } = useAuth();
  const [filters, setFilters] = useState<ReviewFilters>(defaultFilters);
  const [draftFilters, setDraftFilters] = useState<ReviewFilters>(defaultFilters);
  const [page, setPage] = useState<Page<DailyReviewSummary> | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateDate, setGenerateDate] = useState(todayInputValue());
  const [useAi, setUseAi] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [lastGeneratedId, setLastGeneratedId] = useState<string | null>(null);

  const hasActiveFilters = useMemo(
    () => Boolean(filters.status || filters.dateFrom || filters.dateTo),
    [filters.dateFrom, filters.dateTo, filters.status]
  );

  const refreshReviews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPage(
        await listDailyReviews({
          status: filters.status,
          date_from: filters.dateFrom,
          date_to: filters.dateTo,
          limit: filters.limit,
          offset: filters.offset
        })
      );
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    if (authLoading || !user) {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      void refreshReviews();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [authLoading, refreshReviews, user]);

  async function handleGenerate() {
    if (generating) {
      return;
    }
    setGenerating(true);
    setError(null);
    setSuccess(null);
    setLastGeneratedId(null);
    try {
      const review = await generateDailyReview({
        review_date: generateDate || null,
        force: false,
        use_ai: useAi
      });
      setLastGeneratedId(review.id);
      setSuccess(`复盘已生成：${reviewStatusLabel(review.status)}，当前版本 v${review.current_version_number ?? 1}。`);
      await refreshReviews();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setGenerating(false);
    }
  }

  function applyFilters() {
    setFilters({ ...draftFilters, offset: 0 });
  }

  function clearFilters() {
    setDraftFilters(defaultFilters);
    setFilters(defaultFilters);
  }

  if (authLoading) {
    return <LoadingSkeleton lines={6} />;
  }

  if (!user) {
    return (
      <ErrorState
        title="需要登录"
        description="每日复盘是真实用户数据页面，请先登录私人测试账户。"
      />
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="真实API"
        title="我的每日复盘"
        description="当前复盘仅聚合用户保存和分析的信息，不代表全市场行情复盘。"
      />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <CalendarDays className="h-5 w-5 text-blue-700" />
              <h2 className="text-lg font-semibold text-slate-950">生成复盘</h2>
            </div>
            <p className="mt-1 text-sm text-slate-600">
              默认使用当前 Asia/Shanghai 日期；AI 未配置时自动生成规则复盘。
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-[160px_auto_auto] sm:items-center">
            <input
              type="date"
              value={generateDate}
              onChange={(event) => setGenerateDate(event.target.value)}
              className="focus-ring h-9 rounded-md border border-slate-300 px-3 text-sm"
            />
            <label className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={useAi}
                onChange={(event) => setUseAi(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              使用AI解释
            </label>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
              type="button"
            >
              {generating ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              {generating ? "生成中" : "生成指定日期"}
            </button>
          </div>
        </div>
        {success ? (
          <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            {success}
            {lastGeneratedId ? (
              <Link href={`/reviews/${lastGeneratedId}`} className="ml-2 font-semibold text-emerald-950 underline">
                查看详情
              </Link>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-2 md:grid-cols-[1fr_1fr_180px_auto_auto] md:items-end">
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            起始日期
            <input
              type="date"
              value={draftFilters.dateFrom}
              onChange={(event) => setDraftFilters((current) => ({ ...current, dateFrom: event.target.value }))}
              className="focus-ring h-9 rounded-md border border-slate-300 px-3 text-sm"
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            结束日期
            <input
              type="date"
              value={draftFilters.dateTo}
              onChange={(event) => setDraftFilters((current) => ({ ...current, dateTo: event.target.value }))}
              className="focus-ring h-9 rounded-md border border-slate-300 px-3 text-sm"
            />
          </label>
          <label className="grid gap-1 text-sm font-medium text-slate-700">
            状态
            <select
              value={draftFilters.status}
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, status: event.target.value as DailyReviewStatus | "" }))
              }
              className="focus-ring h-9 rounded-md border border-slate-300 px-3 text-sm"
            >
              {statusOptions.map((item) => (
                <option key={item.value || "all"} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={applyFilters}
            className="focus-ring h-9 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800"
            type="button"
          >
            筛选
          </button>
          <button
            onClick={clearFilters}
            className="focus-ring h-9 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            type="button"
          >
            清除
          </button>
        </div>

        <div className="mt-4">
          {error ? <ErrorState title="无法读取复盘" description={error} /> : null}
          {loading ? <LoadingSkeleton lines={6} /> : null}
          {!loading && !error && page?.items.length === 0 ? (
            <EmptyState
              title={hasActiveFilters ? "当前筛选无结果" : "尚未生成任何复盘"}
              description={
                hasActiveFilters
                  ? "调整日期或状态筛选后重试。"
                  : "选择日期后生成第一份用户私有信息每日复盘。"
              }
            />
          ) : null}
          {!loading && !error && page?.items.length ? (
            <div className="grid gap-2">
              {page.items.map((review) => (
                <ReviewRow key={review.id} review={review} />
              ))}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function ReviewRow({ review }: { review: DailyReviewSummary }) {
  const overview = review.overview ?? {};
  const totalInformationCount = numberValue(overview.total_information_count);
  const watchlistStockCount = numberValue(overview.watchlist_stock_count);
  const verificationItemCount = numberValue(overview.verification_item_count);

  return (
    <Link
      href={`/reviews/${review.id}`}
      className="focus-ring grid gap-3 rounded-md border border-slate-200 bg-white p-3 hover:bg-slate-50 md:grid-cols-[1fr_auto]"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${reviewStatusTone(review.status)}`}>
            {reviewStatusLabel(review.status)}
          </span>
          <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700">
            {generationModeLabel(review.generation_mode)}
          </span>
          {review.status === "stale" ? (
            <span className="inline-flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">
              <AlertTriangle className="h-3.5 w-3.5" />
              输入已变化
            </span>
          ) : null}
        </div>
        <p className="mt-2 font-semibold text-slate-950">{review.review_date} 用户每日复盘</p>
        <p className="mt-1 text-xs text-slate-500">
          版本 v{review.current_version_number ?? "-"}；生成时间 {formatDateTime(review.generated_at)}
        </p>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-xs text-slate-600 md:min-w-[300px]">
        <Metric label="信息" value={totalInformationCount} />
        <Metric label="自选股" value={watchlistStockCount} />
        <Metric label="待核实" value={verificationItemCount} />
      </div>
    </Link>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-2">
      <span className="block text-base font-semibold text-slate-950">{value}</span>
      <span className="mt-0.5 block">{label}</span>
    </span>
  );
}

function todayInputValue(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  const day = `${now.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function numberValue(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "尚未生成";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function reviewStatusLabel(status: DailyReviewStatus): string {
  const labels: Record<DailyReviewStatus, string> = {
    complete: "完整",
    partial: "部分完成",
    empty: "空复盘",
    failed: "失败",
    stale: "需要更新"
  };
  return labels[status];
}

function reviewStatusTone(status: DailyReviewStatus): string {
  const tones: Record<DailyReviewStatus, string> = {
    complete: "border-emerald-200 bg-emerald-50 text-emerald-800",
    partial: "border-blue-200 bg-blue-50 text-blue-800",
    empty: "border-slate-200 bg-slate-50 text-slate-700",
    failed: "border-rose-200 bg-rose-50 text-rose-800",
    stale: "border-amber-200 bg-amber-50 text-amber-800"
  };
  return tones[status];
}

function generationModeLabel(mode: DailyReviewGenerationMode | null): string {
  const labels: Record<DailyReviewGenerationMode, string> = {
    rules_only: "规则复盘",
    rules_and_ai: "规则+AI解释",
    rules_with_ai_fallback: "AI失败降级"
  };
  return mode ? labels[mode] : "暂无版本";
}
