"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  Archive,
  Bot,
  CheckCircle2,
  FileText,
  RefreshCw
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import {
  archiveDailyReview,
  getDailyReview,
  regenerateDailyReview
} from "@/lib/api/reviews";
import type {
  DailyReviewDetail,
  DailyReviewGenerationMode,
  DailyReviewStatus
} from "@/lib/api/types";

interface ReviewClaim {
  claim?: string;
  description?: string;
  holder?: string;
  rationale?: string;
  time_horizon?: string;
  verification_needed?: string;
  information_item_id?: string;
  source_information_item_id?: string;
  verification_item_id?: string;
  evidence_text?: string;
  confidence?: number;
  priority?: string;
  status?: string;
  system_interpretation?: string;
  ai_reported_severity?: string;
}

interface ReviewSection {
  stock_id?: string;
  symbol?: string;
  name?: string;
  attention_reason?: string | null;
  user_tags?: string[];
  information_item_ids?: string[];
  facts?: ReviewClaim[];
  opinions?: ReviewClaim[];
  rumors?: ReviewClaim[];
  risks?: ReviewClaim[];
  verification_items?: ReviewClaim[];
  observation_conditions?: string[];
  limitations?: string[];
}

interface ReviewSnapshot {
  scope_note?: string;
  rule_summary?: string;
  overview?: Record<string, unknown>;
  watchlist_sections?: ReviewSection[];
  confirmed_non_watchlist_sections?: ReviewSection[];
  unassigned_information?: Array<Record<string, unknown>>;
  pending_relations?: Array<Record<string, unknown>>;
  global_verification_items?: ReviewClaim[];
  limitations?: string[];
  source_item_ids?: string[];
}

export default function ReviewDetailPage() {
  const params = useParams<{ reviewId: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const reviewId = params.reviewId;
  const [review, setReview] = useState<DailyReviewDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [workingAction, setWorkingAction] = useState<"archive" | "regenerate" | null>(null);
  const [useAi, setUseAi] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const snapshot = useMemo(
    () => (review?.current_version?.rule_snapshot ?? {}) as ReviewSnapshot,
    [review?.current_version]
  );
  const aiResult = useMemo(
    () => (review?.current_version?.ai_structured_result ?? null) as Record<string, unknown> | null,
    [review?.current_version]
  );
  const generationInProgress = Boolean(review?.generation_in_progress);
  const regenerating = workingAction === "regenerate" || generationInProgress;
  const actionDisabled = workingAction !== null || generationInProgress;

  const refreshReview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReview(await getDailyReview(reviewId));
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [reviewId]);

  useEffect(() => {
    if (authLoading || !user) {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      void refreshReview();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [authLoading, refreshReview, user]);

  async function handleRegenerate() {
    if (actionDisabled || !review) {
      return;
    }
    setWorkingAction("regenerate");
    setError(null);
    setSuccess(null);
    try {
      const updated = await regenerateDailyReview(review.id, useAi);
      setReview(updated);
      setSuccess(`已重新生成 v${updated.current_version_number ?? "-"}，状态：${reviewStatusLabel(updated.status)}。`);
    } catch (caught) {
      setError(humanizeApiError(caught));
      void refreshReview();
    } finally {
      setWorkingAction(null);
    }
  }

  async function handleArchive() {
    if (actionDisabled || !review) {
      return;
    }
    setWorkingAction("archive");
    setError(null);
    try {
      await archiveDailyReview(review.id, true);
      router.push("/reviews");
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setWorkingAction(null);
    }
  }

  if (authLoading || loading) {
    return <LoadingSkeleton lines={8} />;
  }

  if (!user) {
    return <ErrorState title="需要登录" description="每日复盘详情只对当前登录用户可见。" />;
  }

  if (error && !review) {
    return (
      <div className="space-y-4">
        <Link href="/reviews" className="focus-ring inline-flex items-center gap-2 text-sm font-semibold text-slate-700">
          <ArrowLeft className="h-4 w-4" />
          返回复盘列表
        </Link>
        <ErrorState title="无法读取复盘详情" description={error} />
      </div>
    );
  }

  if (!review) {
    return <EmptyState title="复盘不存在" description="该复盘可能已归档，或不属于当前用户。" />;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="真实API"
        title={`${review.review_date} 用户每日复盘`}
        description={snapshot.scope_note ?? "当前复盘仅聚合用户保存和分析的信息，不代表全市场行情复盘。"}
        actions={
          <>
            <Link
              href="/reviews"
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              <ArrowLeft className="h-4 w-4" />
              列表
            </Link>
            <button
              onClick={handleArchive}
              disabled={actionDisabled}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
              type="button"
            >
              <Archive className="h-4 w-4" />
              归档
            </button>
          </>
        }
      />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill status={review.status} />
            {generationInProgress ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-800">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                生成中
              </span>
            ) : null}
            <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700">
              v{review.current_version_number ?? "-"}
            </span>
            <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700">
              {generationModeLabel(review.generation_mode)}
            </span>
            <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700">
              生成时间 {formatDateTime(review.generated_at)}
            </span>
          </div>
          <div className="grid gap-2 sm:grid-cols-[auto_auto]">
            <label className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={useAi}
                onChange={(event) => setUseAi(event.target.checked)}
                disabled={actionDisabled}
                className="h-4 w-4 rounded border-slate-300"
              />
              使用AI解释
            </label>
            <button
              onClick={handleRegenerate}
              disabled={actionDisabled}
              className="focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
              type="button"
            >
              <RefreshCw className={`h-4 w-4 ${regenerating ? "animate-spin" : ""}`} />
              {regenerating ? "生成中" : "重新生成"}
            </button>
          </div>
        </div>
        {generationInProgress ? (
          <div className="mt-3 flex gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
            <RefreshCw className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
            <span>该日期复盘正在生成中，当前页面已禁用重复提交。完成或失败后刷新页面即可继续操作。</span>
          </div>
        ) : null}
        {review.status === "stale" ? (
          <div className="mt-3 flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>复盘生成后输入信息已变化，历史内容仍可查看。请主动重新生成后清除该状态。</span>
          </div>
        ) : null}
        {success ? (
          <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            {success}
          </div>
        ) : null}
        {error ? <div className="mt-3"><ErrorState title="操作失败" description={error} /></div> : null}
      </section>

      <RuleOverview overview={snapshot.overview ?? {}} />
      <AISummary aiResult={aiResult} fallback={review.current_version?.ai_narrative ?? snapshot.rule_summary} />
      <SectionList title="自选股分组" sections={snapshot.watchlist_sections ?? []} empty="暂无确认归属到自选股的信息。" />
      <SectionList
        title="其他已确认股票"
        sections={snapshot.confirmed_non_watchlist_sections ?? []}
        empty="暂无确认股票但不在自选股中的信息。"
        nonWatchlist
      />
      <UnassignedInformation
        items={snapshot.unassigned_information ?? []}
        pendingRelations={snapshot.pending_relations ?? []}
      />
      <Limitations limitations={snapshot.limitations ?? []} sourceIds={snapshot.source_item_ids ?? []} />
      <VersionHistory review={review} />
    </div>
  );
}

function RuleOverview({ overview }: { overview: Record<string, unknown> }) {
  const metrics = [
    ["总信息", overview.total_information_count],
    ["已分析", overview.analyzed_count],
    ["待分析", overview.pending_analysis_count],
    ["分析失败", overview.failed_analysis_count],
    ["重要信息", overview.important_count],
    ["自选股", overview.watchlist_stock_count],
    ["事实", overview.fact_count],
    ["观点", overview.opinion_count],
    ["传闻", overview.rumor_count],
    ["待核实", overview.verification_item_count]
  ];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <FileText className="h-5 w-5 text-blue-700" />
        <h2 className="text-lg font-semibold text-slate-950">规则概览</h2>
        <span className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-800">
          程序聚合
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
        {metrics.map(([label, value]) => (
          <div key={label as string} className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-lg font-semibold text-slate-950">{typeof value === "number" ? value : 0}</p>
            <p className="mt-1 text-xs text-slate-500">{label as string}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function AISummary({
  aiResult,
  fallback
}: {
  aiResult: Record<string, unknown> | null;
  fallback?: string | null;
}) {
  const hasAi = Boolean(aiResult);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Bot className="h-5 w-5 text-slate-700" />
        <h2 className="text-lg font-semibold text-slate-950">AI复盘摘要</h2>
        <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-700">
          AI解释
        </span>
        {!hasAi ? (
          <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800">
            AI未生成，展示规则摘要
          </span>
        ) : null}
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-700">
        {stringValue(aiResult?.executive_summary) || fallback || "暂无AI摘要。"}
      </p>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <TextList title="关键变化" items={stringArray(aiResult?.key_developments)} />
        <TextList title="待核实重点" items={stringArray(aiResult?.verification_focus)} />
        <TextList title="后续观察" items={stringArray(aiResult?.tomorrow_observation_focus)} />
        <TextList title="局限" items={stringArray(aiResult?.limitations)} />
      </div>
      {stringValue(aiResult?.uncertainty_summary) ? (
        <p className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
          不确定性：{stringValue(aiResult?.uncertainty_summary)}
        </p>
      ) : null}
    </section>
  );
}

function SectionList({
  title,
  sections,
  empty,
  nonWatchlist = false
}: {
  title: string;
  sections: ReviewSection[];
  empty: string;
  nonWatchlist?: boolean;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      {sections.length === 0 ? (
        <p className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">{empty}</p>
      ) : (
        <div className="mt-4 grid gap-3">
          {sections.map((section, index) => (
            <article key={`${section.stock_id ?? section.symbol ?? index}`} className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-semibold text-slate-950">{section.name ?? "未命名股票"} · {section.symbol ?? "-"}</h3>
                {nonWatchlist ? (
                  <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800">
                    不在当前自选股
                  </span>
                ) : null}
                {(section.user_tags ?? []).map((tag) => (
                  <span key={tag} className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600">
                    {tag}
                  </span>
                ))}
              </div>
              {section.attention_reason ? (
                <p className="mt-2 text-sm text-slate-600">关注原因：{section.attention_reason}</p>
              ) : null}
              <div className="mt-3 grid gap-3 xl:grid-cols-3">
                <ClaimGroup title="事实" items={section.facts ?? []} />
                <ClaimGroup title="观点" items={section.opinions ?? []} />
                <ClaimGroup title="传闻" items={section.rumors ?? []} />
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <ClaimGroup title="风险" items={section.risks ?? []} />
                <ClaimGroup title="待核实" items={section.verification_items ?? []} />
              </div>
              <TextList title="观察条件" items={section.observation_conditions ?? []} />
              <SourceLinks ids={section.information_item_ids ?? []} />
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ClaimGroup({ title, items }: { title: string; items: ReviewClaim[] }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <p className="text-xs font-semibold text-slate-500">{title}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">暂无</p>
      ) : (
        <div className="mt-2 space-y-2">
          {items.map((item, index) => (
            <div key={`${title}-${index}`} className="text-sm leading-6 text-slate-700">
              <p className="font-medium text-slate-900">{item.claim ?? item.description ?? "未命名条目"}</p>
              {item.holder || item.rationale ? (
                <p className="text-xs text-slate-500">{[item.holder, item.rationale].filter(Boolean).join(" · ")}</p>
              ) : null}
              {item.evidence_text ? <p className="text-xs text-slate-500">证据：{item.evidence_text}</p> : null}
              {item.information_item_id || item.source_information_item_id ? (
                <Link
                  href={`/information/items/${item.information_item_id ?? item.source_information_item_id}`}
                  className="text-xs font-semibold text-blue-700 hover:text-blue-800"
                >
                  查看来源
                </Link>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UnassignedInformation({
  items,
  pendingRelations
}: {
  items: Array<Record<string, unknown>>;
  pendingRelations: Array<Record<string, unknown>>;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">未归属与待确认关联</h2>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-sm font-semibold text-slate-900">未归属信息</p>
          {items.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">暂无未归属信息。</p>
          ) : (
            <div className="mt-2 space-y-2">
              {items.map((item, index) => (
                <SourceSummary key={`unassigned-${index}`} item={item} />
              ))}
            </div>
          )}
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-sm font-semibold text-slate-900">待确认股票建议</p>
          {pendingRelations.length === 0 ? (
            <p className="mt-2 text-sm text-slate-500">暂无待确认关联。</p>
          ) : (
            <div className="mt-2 space-y-2">
              {pendingRelations.map((item, index) => (
                <SourceSummary key={`pending-${index}`} item={item} />
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function SourceSummary({ item }: { item: Record<string, unknown> }) {
  const id = stringValue(item.information_item_id);
  return (
    <div className="rounded-md border border-slate-200 bg-white p-2 text-sm text-slate-700">
      <p className="font-medium text-slate-900">{stringValue(item.title) || stringValue(item.stock_name) || "未命名信息"}</p>
      <p className="mt-1 text-xs text-slate-500">
        状态：{stringValue(item.status) || stringValue(item.relation_status) || "未知"}；范围：
        {stringValue(item.relation_scope) || stringValue(item.inclusion_type) || "未归属"}
      </p>
      {id ? (
        <Link href={`/information/items/${id}`} className="mt-1 inline-flex text-xs font-semibold text-blue-700 hover:text-blue-800">
          查看来源
        </Link>
      ) : null}
    </div>
  );
}

function Limitations({ limitations, sourceIds }: { limitations: string[]; sourceIds: string[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">数据局限与来源追溯</h2>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <TextList title="数据局限" items={limitations} />
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold text-slate-500">来源信息</p>
          <SourceLinks ids={sourceIds} />
        </div>
      </div>
    </section>
  );
}

function VersionHistory({ review }: { review: DailyReviewDetail }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-slate-950">历史版本</h2>
      <div className="mt-3 grid gap-2">
        {review.versions.map((version) => (
          <div key={version.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-slate-950">v{version.version_number}</span>
              <StatusPill status={version.status} />
              <span className="text-slate-600">{generationModeLabel(version.generation_mode)}</span>
            </div>
            <span className="text-xs text-slate-500">{formatDateTime(version.generated_at)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function SourceLinks({ ids }: { ids: string[] }) {
  if (!ids.length) {
    return <p className="mt-2 text-xs text-slate-500">暂无来源ID。</p>;
  }
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {ids.map((id) => (
        <Link
          key={id}
          href={`/information/items/${id}`}
          className="focus-ring inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50"
        >
          <CheckCircle2 className="h-3.5 w-3.5" />
          {id.slice(0, 8)}
        </Link>
      ))}
    </div>
  );
}

function TextList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">{title}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">暂无</p>
      ) : (
        <ul className="mt-2 space-y-1 text-sm leading-6 text-slate-700">
          {items.map((item, index) => (
            <li key={`${title}-${index}`}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: DailyReviewStatus }) {
  return (
    <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${reviewStatusTone(status)}`}>
      {reviewStatusLabel(status)}
    </span>
  );
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "暂无";
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
