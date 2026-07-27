"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Bot,
  Check,
  ExternalLink,
  FileText,
  Link2,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Star,
  Trash2,
  X
} from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import {
  addInformationContent,
  addStockRelation,
  analyzeInformationItem,
  deleteStockRelation,
  fetchInformationItem,
  getInformationItem,
  patchInformationItem,
  patchStockRelation
} from "@/lib/api/information";
import { listStocks } from "@/lib/api/stocks";
import { humanizeApiError } from "@/lib/api/errors";
import type {
  InformationAnalysis,
  InformationDetail,
  InformationStockRelation,
  StockRead
} from "@/lib/api/types";

export default function InformationDetailPage() {
  const params = useParams<{ itemId: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const itemId = params.itemId;
  const [detail, setDetail] = useState<InformationDetail | null>(null);
  const [stocks, setStocks] = useState<StockRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [contentPanelOpen, setContentPanelOpen] = useState(false);
  const [relationPanelOpen, setRelationPanelOpen] = useState(false);

  const stockMap = useMemo(() => new Map(stocks.map((stock) => [stock.id, stock])), [stocks]);

  const loadDetail = useCallback(async () => {
    if (!user) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [nextDetail, stockPage] = await Promise.all([
        getInformationItem(itemId),
        listStocks({ limit: 100 })
      ]);
      setDetail(nextDetail);
      setStocks(stockPage.items);
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [itemId, user]);

  useEffect(() => {
    if (!authLoading && user) {
      const timeoutId = window.setTimeout(() => {
        void loadDetail();
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }

    return undefined;
  }, [authLoading, loadDetail, user]);

  async function runAction(label: string, action: () => Promise<InformationDetail | void>) {
    setActionLoading(label);
    setError(null);
    setSuccess(null);
    try {
      const result = await action();
      if (result) {
        setDetail(result);
      } else {
        await loadDetail();
      }
      setSuccess(`${label}已完成。`);
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setActionLoading(null);
    }
  }

  async function archiveItem() {
    if (!detail || !window.confirm("确认归档这条信息？归档后默认列表不再显示。")) {
      return;
    }
    await runAction("归档", async () => {
      await patchInformationItem(detail.id, { archived: true });
      router.push("/information");
    });
  }

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="信息详情属于用户私有数据，请先登录。"
        action={
          <Link
            href={`/login?redirect=/information/items/${itemId}`}
            className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
          >
            去登录
          </Link>
        }
      />
    );
  }

  if (loading) {
    return (
      <div className="space-y-5">
        <PageHeader title="信息详情" description="正在从本地后端读取信息条目。" />
        <LoadingSkeleton lines={9} />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="space-y-5">
        <PageHeader title="信息详情" description="未能读取信息条目。" />
        {error ? <ErrorState title="读取失败" description={error} /> : null}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="信息详情"
        title={detail.title || "未命名信息"}
        description="原始来源、用户补充正文、AI 分析和用户确认关系分开展示；AI 不覆盖原始事实。"
        actions={
          <>
            <Link
              href="/information"
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              <ArrowLeft className="h-4 w-4" />
              返回
            </Link>
            <button
              onClick={() => runAction(detail.is_read ? "标记未读" : "标记已读", () => patchInformationItem(detail.id, { is_read: !detail.is_read }))}
              className="focus-ring inline-flex h-9 items-center rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              type="button"
            >
              {detail.is_read ? "标记未读" : "标记已读"}
            </button>
            <button
              onClick={() => runAction(detail.is_important ? "取消重要" : "标记重要", () => patchInformationItem(detail.id, { is_important: !detail.is_important }))}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 text-sm font-semibold text-amber-800 hover:bg-amber-100"
              type="button"
            >
              <Star className="h-4 w-4" />
              {detail.is_important ? "取消重要" : "标记重要"}
            </button>
          </>
        }
      />

      {error ? <ErrorState title="操作失败" description={error} /> : null}
      {success ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          {success}
        </div>
      ) : null}

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill status={detail.status} />
          <SmallPill>{detail.input_type === "manual_text" ? "手动文本" : "公开URL"}</SmallPill>
          <SmallPill tone={detail.is_important ? "amber" : "slate"}>
            {detail.is_important ? "重要" : "普通"}
          </SmallPill>
          <SmallPill tone={detail.is_read ? "slate" : "blue"}>{detail.is_read ? "已读" : "未读"}</SmallPill>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-700">
          用户备注：{detail.user_note || "暂无"}
        </p>
        <p className="mt-2 text-xs text-slate-500">
          创建：{formatDateTime(detail.created_at)}；更新：{formatDateTime(detail.updated_at)}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {detail.input_type === "public_url" ? (
            <button
              onClick={() => runAction("重新抓取", () => fetchInformationItem(detail.id))}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 text-sm font-semibold text-blue-800 hover:bg-blue-100"
              type="button"
              disabled={actionLoading !== null}
            >
              <RefreshCw className="h-4 w-4" />
              {actionLoading === "重新抓取" ? "抓取中" : "重新抓取"}
            </button>
          ) : null}
          <button
            onClick={() => runAction("AI分析", () => analyzeInformationItem(detail.id, false))}
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="button"
            disabled={actionLoading !== null}
          >
            <Bot className="h-4 w-4" />
            {actionLoading === "AI分析" ? "分析中" : "AI分析"}
          </button>
          <button
            onClick={() => runAction("强制重新分析", () => analyzeInformationItem(detail.id, true))}
            className="focus-ring inline-flex h-9 items-center rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            type="button"
            disabled={actionLoading !== null}
          >
            强制重新分析
          </button>
          <button
            onClick={() => setContentPanelOpen(true)}
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            type="button"
          >
            <Plus className="h-4 w-4" />
            补充正文
          </button>
          <button
            onClick={() => setRelationPanelOpen(true)}
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            type="button"
          >
            <Plus className="h-4 w-4" />
            添加股票关联
          </button>
          <button
            onClick={archiveItem}
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-rose-200 px-3 text-sm font-semibold text-rose-700 hover:bg-rose-50"
            type="button"
          >
            <Trash2 className="h-4 w-4" />
            归档
          </button>
        </div>
      </section>

      <section className="grid min-w-0 gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionTitle icon={<Link2 className="h-5 w-5 text-blue-700" />} title="来源记录" />
          <div className="mt-4 space-y-3">
            {detail.sources.length === 0 ? (
              <p className="text-sm text-slate-500">暂无来源记录。</p>
            ) : (
              detail.sources.map((source) => (
                <article key={source.id} className="min-w-0 rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <SmallPill>{source.fetch_status}</SmallPill>
                    {source.http_status ? <SmallPill>HTTP {source.http_status}</SmallPill> : null}
                    {source.content_type ? <SmallPill>{source.content_type}</SmallPill> : null}
                  </div>
                  <p className="mt-2 text-sm text-slate-700">来源名称：{source.source_name || "未知"}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    发布时间：{source.published_at ? formatDateTime(source.published_at) : "未知"}；抓取：
                    {source.fetched_at ? formatDateTime(source.fetched_at) : "未抓取"}
                  </p>
                  {source.normalized_url ? (
                    <a
                      href={source.normalized_url}
                      target="_blank"
                      rel="noreferrer"
                      className="focus-ring mt-2 inline-flex min-w-0 max-w-full items-center gap-1 text-sm font-medium text-blue-700 hover:text-blue-800"
                    >
                      <ExternalLink className="h-4 w-4 shrink-0" />
                      <span className="min-w-0 break-all">{source.normalized_url}</span>
                    </a>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </div>

        <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionTitle icon={<FileText className="h-5 w-5 text-slate-700" />} title="当前正文版本" />
          {detail.current_content ? (
            <div className="mt-4">
              <div className="flex flex-wrap gap-2">
                <SmallPill>版本 {detail.current_content.content_version}</SmallPill>
                <SmallPill>{detail.current_content.content_origin}</SmallPill>
                <SmallPill>{detail.current_content.extraction_status}</SmallPill>
                <SmallPill>{detail.current_content.character_count} 字</SmallPill>
              </div>
              <pre className="mt-3 max-h-[420px] max-w-full overflow-auto whitespace-pre-wrap break-words rounded-md border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-800">
                {detail.current_content.extracted_text}
              </pre>
            </div>
          ) : (
            <EmptyState title="暂无可分析正文" description="URL 抓取失败或尚未补充正文时，可点击“补充正文”添加用户修正版。" />
          )}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<Bot className="h-5 w-5 text-slate-700" />} title="结构化 AI 分析" />
        <p className="mt-1 text-xs leading-5 text-slate-500">
          以下为 AI 分析结果，不替代原始正文、来源时间或正式事实。AI 失败时不影响来源和正文查看。
        </p>
        <div className="mt-4">
          {detail.latest_analysis ? (
            <AnalysisView analysis={detail.latest_analysis} />
          ) : (
            <EmptyState title="暂无 AI 分析版本" description="配置并启用 AI Provider 后，可对当前正文发起结构化分析。" />
          )}
        </div>
      </section>

      <section className="grid min-w-0 gap-5 xl:grid-cols-[1fr_1fr]">
        <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionTitle icon={<Check className="h-5 w-5 text-emerald-700" />} title="股票关联" />
          <div className="mt-4 space-y-3">
            {detail.stock_relations.length === 0 ? (
              <p className="text-sm text-slate-500">暂无股票关联，可手动添加或等待 AI 建议。</p>
            ) : (
              detail.stock_relations.map((relation) => (
                <RelationCard
                  key={relation.id}
                  relation={relation}
                  stock={stockMap.get(relation.stock_id)}
                  onConfirm={() => runAction("确认股票关联", async () => {
                    await patchStockRelation(detail.id, relation.id, { relation_status: "confirmed" });
                  })}
                  onReject={() => runAction("拒绝股票关联", async () => {
                    await patchStockRelation(detail.id, relation.id, { relation_status: "rejected" });
                  })}
                  onDelete={() => runAction("删除股票关联", async () => {
                    await deleteStockRelation(detail.id, relation.id);
                  })}
                />
              ))
            )}
          </div>
        </div>

        <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionTitle icon={<ShieldAlert className="h-5 w-5 text-amber-700" />} title="实体提及与待核实事项" />
          <div className="mt-4 grid min-w-0 gap-3 lg:grid-cols-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-950">实体提及</p>
              <div className="mt-2 min-w-0 space-y-2">
                {detail.entity_mentions.length === 0 ? (
                  <p className="text-sm text-slate-500">暂无实体提及。</p>
                ) : (
                  detail.entity_mentions.map((item) => (
                    <div key={item.id} className="min-w-0 rounded-md border border-slate-200 bg-slate-50 p-3">
                      <p className="break-words text-sm font-semibold text-slate-950">{item.entity_name}</p>
                      <p className="mt-1 break-words text-xs text-slate-500">
                        {item.entity_type} · {item.origin} · {item.status}
                      </p>
                      {item.evidence_text ? <p className="mt-2 break-words text-sm text-slate-700">{item.evidence_text}</p> : null}
                    </div>
                  ))
                )}
              </div>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-950">待核实事项</p>
              <div className="mt-2 min-w-0 space-y-2">
                {detail.verification_items.length === 0 ? (
                  <p className="text-sm text-slate-500">暂无待核实事项。</p>
                ) : (
                  detail.verification_items.map((item) => (
                    <div key={item.id} className="min-w-0 rounded-md border border-amber-200 bg-amber-50 p-3">
                      <p className="break-words text-sm font-semibold text-amber-950">{item.description}</p>
                      <p className="mt-1 break-words text-xs text-amber-800">
                        {item.status} · {item.priority ?? "未分级"} · {item.verification_type}
                      </p>
                      {item.evidence_needed ? <p className="mt-2 break-words text-sm text-amber-900">{item.evidence_needed}</p> : null}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<RefreshCw className="h-5 w-5 text-slate-700" />} title="分析版本历史" />
        {detail.analysis_versions.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">暂无版本。</p>
        ) : (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {detail.analysis_versions.map((version) => (
              <article key={version.id} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                <p className="text-sm font-semibold text-slate-950">
                  版本 {version.version_number} · {version.analysis_status}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {version.model_name ?? "未知模型"}；{formatDateTime(version.created_at)}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  Schema：{version.schema_version}；Prompt：{version.prompt_version}
                </p>
              </article>
            ))}
          </div>
        )}
      </section>

      {contentPanelOpen ? (
        <ContentPanel
          onClose={() => setContentPanelOpen(false)}
          onSubmit={(payload) =>
            runAction("补充正文", async () => {
              await addInformationContent(detail.id, payload);
            }).then(() => setContentPanelOpen(false))
          }
        />
      ) : null}

      {relationPanelOpen ? (
        <RelationPanel
          onClose={() => setRelationPanelOpen(false)}
          onSubmit={(stockId, evidenceText) =>
            runAction("添加股票关联", async () => {
              await addStockRelation(detail.id, {
                stock_id: stockId,
                relation_type: "directly_related",
                evidence_text: evidenceText
              });
            }).then(() => setRelationPanelOpen(false))
          }
        />
      ) : null}
    </div>
  );
}

function AnalysisView({ analysis }: { analysis: InformationAnalysis }) {
  if (analysis.analysis_status !== "succeeded") {
    const errorCode = readString(analysis.structured_result, "error_code") ?? "未知错误";
    return (
      <div className="flex gap-2 rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
        AI 分析失败：{errorCode}
      </div>
    );
  }

  const result = analysis.structured_result;
  const sentiment = readRecord(result, "sentiment");
  const reliability = readRecord(result, "source_reliability");

  return (
    <div className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-4">
        <Metric label="内容类型" value={readString(result, "content_type") ?? "unknown"} />
        <Metric label="情绪方向" value={readString(sentiment, "direction") ?? "unknown"} />
        <Metric label="证据强度" value={readString(result, "evidence_strength") ?? "unknown"} />
        <Metric label="来源可信度" value={readString(reliability, "level") ?? "unknown"} />
      </div>
      <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs font-semibold text-slate-500">AI摘要</p>
        <p className="mt-2 text-sm leading-6 text-slate-800">{readString(result, "summary") ?? "暂无摘要"}</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <ClaimList title="事实" items={readArray(result, "facts")} field="claim" />
        <ClaimList title="观点" items={readArray(result, "opinions")} field="claim" />
        <ClaimList title="传闻" items={readArray(result, "rumors")} field="claim" warning />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ClaimList title="风险" items={readArray(result, "risks")} field="description" warning />
        <ClaimList title="关键主张" items={readArray(result, "key_claims")} field="claim" />
      </div>
      <p className="text-xs text-slate-500">
        模型：{analysis.model_name ?? "未知"}；生成：{formatDateTime(analysis.created_at)}；Schema：
        {analysis.schema_version}
      </p>
    </div>
  );
}

function RelationCard({
  relation,
  stock,
  onConfirm,
  onReject,
  onDelete
}: {
  relation: InformationStockRelation;
  stock?: StockRead;
  onConfirm: () => void;
  onReject: () => void;
  onDelete: () => void;
}) {
  return (
    <article className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="font-semibold text-slate-950">
          {stock ? `${stock.name} ${stock.exchange}${stock.symbol}` : relation.stock_id}
        </p>
        <SmallPill tone={relation.relation_status === "confirmed" ? "emerald" : relation.relation_status === "rejected" ? "rose" : "blue"}>
          {relation.relation_status}
        </SmallPill>
        <SmallPill>{relation.relation_origin}</SmallPill>
        <SmallPill>{relation.relation_type}</SmallPill>
      </div>
      {relation.evidence_text ? <p className="mt-2 text-sm leading-6 text-slate-700">{relation.evidence_text}</p> : null}
      {relation.confidence !== null ? (
        <p className="mt-1 text-xs text-slate-500">AI 置信度：{Math.round(relation.confidence * 100)}%</p>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        {relation.relation_status !== "confirmed" ? (
          <button onClick={onConfirm} className="focus-ring h-8 rounded-md border border-emerald-200 bg-emerald-50 px-2 text-xs font-semibold text-emerald-800" type="button">
            确认
          </button>
        ) : null}
        {relation.relation_status !== "rejected" ? (
          <button onClick={onReject} className="focus-ring h-8 rounded-md border border-rose-200 bg-rose-50 px-2 text-xs font-semibold text-rose-800" type="button">
            拒绝
          </button>
        ) : null}
        <button onClick={onDelete} className="focus-ring h-8 rounded-md border border-slate-300 bg-white px-2 text-xs font-semibold text-slate-700" type="button">
          删除
        </button>
      </div>
    </article>
  );
}

function ContentPanel({
  onClose,
  onSubmit
}: {
  onClose: () => void;
  onSubmit: (payload: { title?: string | null; text: string }) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    await onSubmit({ title: emptyToNull(title), text });
    setSubmitting(false);
  }

  return (
    <Modal title="补充正文" onClose={onClose}>
      <form className="space-y-4" onSubmit={handleSubmit}>
        <Field label="标题（可选）">
          <input value={title} onChange={(event) => setTitle(event.target.value)} className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm" />
        </Field>
        <Field label="正文">
          <textarea value={text} onChange={(event) => setText(event.target.value)} className="focus-ring min-h-36 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" required />
        </Field>
        <button className="focus-ring h-10 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white disabled:bg-slate-400" disabled={submitting} type="submit">
          {submitting ? "保存中..." : "保存正文"}
        </button>
      </form>
    </Modal>
  );
}

function RelationPanel({
  onClose,
  onSubmit
}: {
  onClose: () => void;
  onSubmit: (stockId: string, evidenceText: string | null) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockRead[]>([]);
  const [selected, setSelected] = useState<StockRead | null>(null);
  const [evidence, setEvidence] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function searchStocks() {
    setLoading(true);
    setError(null);
    try {
      setResults((await listStocks({ q: query, limit: 10 })).items);
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) {
      setError("请选择一只股票。");
      return;
    }
    setSubmitting(true);
    await onSubmit(selected.id, emptyToNull(evidence));
    setSubmitting(false);
  }

  return (
    <Modal title="添加股票关联" onClose={onClose}>
      {error ? <ErrorState title="操作失败" description={error} /> : null}
      <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
        <div className="flex gap-2">
          <input value={query} onChange={(event) => setQuery(event.target.value)} className="focus-ring h-10 min-w-0 flex-1 rounded-md border border-slate-300 px-3 text-sm" placeholder="搜索股票代码或名称" />
          <button onClick={searchStocks} className="focus-ring inline-flex h-10 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700" type="button">
            <Search className="h-4 w-4" />
            {loading ? "搜索中" : "搜索"}
          </button>
        </div>
        {selected ? (
          <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
            已选择：{selected.name} {selected.exchange}{selected.symbol}
          </div>
        ) : null}
        <div className="grid gap-2 sm:grid-cols-2">
          {results.map((stock) => (
            <button key={stock.id} onClick={() => setSelected(stock)} className="focus-ring rounded-md border border-slate-200 bg-slate-50 p-3 text-left text-sm hover:bg-white" type="button">
              <span className="font-semibold text-slate-950">{stock.name}</span>
              <span className="ml-2 text-xs text-slate-500">{stock.exchange}{stock.symbol}</span>
            </button>
          ))}
        </div>
        <Field label="关联依据（可选）">
          <textarea value={evidence} onChange={(event) => setEvidence(event.target.value)} className="focus-ring min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" maxLength={500} />
        </Field>
        <button className="focus-ring h-10 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white disabled:bg-slate-400" disabled={submitting} type="submit">
          {submitting ? "保存中..." : "保存关联"}
        </button>
      </form>
    </Modal>
  );
}

function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-40 flex items-end bg-slate-950/30 p-4 sm:items-center sm:justify-center">
      <section className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <button onClick={onClose} className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 text-slate-700" type="button" aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </section>
    </div>
  );
}

function SectionTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2">
      {icon}
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
    </div>
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
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function ClaimList({
  title,
  items,
  field,
  warning = false
}: {
  title: string;
  items: Record<string, unknown>[];
  field: string;
  warning?: boolean;
}) {
  return (
    <div className={`rounded-md border p-3 ${warning ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-slate-50"}`}>
      <p className={`text-sm font-semibold ${warning ? "text-amber-950" : "text-slate-950"}`}>{title}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">暂无</p>
      ) : (
        <div className="mt-2 space-y-2">
          {items.map((item, index) => (
            <div key={index} className="rounded bg-white p-2 text-sm leading-6 text-slate-700">
              <p>{readString(item, field) ?? "未命名条目"}</p>
              {readString(item, "evidence_text") ? (
                <p className="mt-1 text-xs text-slate-500">依据：{readString(item, "evidence_text")}</p>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "analyzed"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : status.includes("failed")
        ? "border-rose-200 bg-rose-50 text-rose-800"
        : status === "analyzing" || status === "fetching"
          ? "border-blue-200 bg-blue-50 text-blue-800"
          : "border-slate-200 bg-slate-50 text-slate-700";

  return <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${tone}`}>{status}</span>;
}

function SmallPill({
  children,
  tone = "slate"
}: {
  children: ReactNode;
  tone?: "slate" | "amber" | "blue" | "emerald" | "rose";
}) {
  const tones = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    blue: "border-blue-200 bg-blue-50 text-blue-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
    rose: "border-rose-200 bg-rose-50 text-rose-800"
  };

  return <span className={`rounded-md border px-2 py-1 text-xs font-semibold ${tones[tone]}`}>{children}</span>;
}

function readRecord(source: Record<string, unknown>, key: string): Record<string, unknown> {
  const value = source[key];
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function readString(source: Record<string, unknown>, key: string): string | null {
  const value = source[key];
  return typeof value === "string" ? value : null;
}

function readArray(source: Record<string, unknown>, key: string): Record<string, unknown>[] {
  const value = source[key];
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter(
    (item): item is Record<string, unknown> =>
      item !== null && typeof item === "object" && !Array.isArray(item)
  );
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
