"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  ExternalLink,
  FileText,
  RefreshCw,
  ShieldAlert,
  XCircle
} from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import {
  extractAnnouncementDocument,
  getAnnouncementCandidate,
  importAnnouncementCandidate,
  patchAnnouncementCandidate
} from "@/lib/api/announcements";
import { humanizeApiError } from "@/lib/api/errors";
import type { AnnouncementCandidateDetail, AnnouncementImportResult } from "@/lib/api/types";

type ImportMode = "metadata_only" | "extracted_document" | "user_supplemented";

export default function AnnouncementCandidateDetailPage() {
  const params = useParams<{ candidateId: string }>();
  const candidateId = params.candidateId;
  const { user, loading: authLoading } = useAuth();
  const [detail, setDetail] = useState<AnnouncementCandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [importMode, setImportMode] = useState<ImportMode>("metadata_only");
  const [titleOverride, setTitleOverride] = useState("");
  const [userNote, setUserNote] = useState("");
  const [supplementedText, setSupplementedText] = useState("");
  const [lastImport, setLastImport] = useState<AnnouncementImportResult | null>(null);

  const loadDetail = useCallback(async () => {
    if (!user) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const nextDetail = await getAnnouncementCandidate(candidateId);
      setDetail(nextDetail);
      if (nextDetail.information_item_id) {
        setLastImport({
          candidate_id: nextDetail.id,
          information_item_id: nextDetail.information_item_id,
          import_mode: "existing",
          already_imported: true,
          created_at: nextDetail.imported_at ?? nextDetail.updated_at
        });
      }
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [candidateId, user]);

  useEffect(() => {
    if (!authLoading && user) {
      const timeoutId = window.setTimeout(() => {
        void loadDetail();
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }
    return undefined;
  }, [authLoading, loadDetail, user]);

  async function runAction(label: string, action: () => Promise<void>) {
    setActionLoading(label);
    setError(null);
    setSuccess(null);
    try {
      await action();
      setSuccess(`${label}已完成。`);
      await loadDetail();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setActionLoading(null);
    }
  }

  async function handleImport() {
    await runAction("导入公告", async () => {
      const result = await importAnnouncementCandidate(candidateId, {
        import_mode: importMode,
        title_override: emptyToNull(titleOverride),
        user_note: emptyToNull(userNote),
        supplemented_text: importMode === "user_supplemented" ? supplementedText : null
      });
      setLastImport(result);
    });
  }

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="公告候选属于用户私有数据，请先登录。"
        action={
          <Link
            href={`/login?redirect=/information/announcements/${candidateId}`}
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
        <PageHeader title="公告候选详情" description="正在读取候选元数据。" />
        <LoadingSkeleton lines={10} />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="space-y-5">
        <PageHeader title="公告候选详情" description="未能读取候选。" />
        {error ? <ErrorState title="读取失败" description={error} /> : null}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="公告候选"
        title={detail.title}
        description="候选元数据、来源状态、PDF提取和正式信息导入分开展示；导入后仍需用户主动进入信息详情调用 AI 分析。"
        actions={
          <Link
            href="/information/announcements"
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            返回候选
          </Link>
        }
      />

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <div className="flex gap-2">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <p>{detail.detail_notice}</p>
        </div>
      </section>

      {error ? <ErrorState title="操作失败" description={error} /> : null}
      {success ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          {success}
        </div>
      ) : null}

      <section className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionTitle icon={<FileText className="h-5 w-5 text-blue-700" />} title="公告元数据" />
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Metric label="公司" value={detail.company_name ?? "未知"} />
            <Metric label="股票" value={detail.stock_symbols.join("、") || "未确认"} />
            <Metric label="类型" value={detail.announcement_type} />
            <Metric label="分类置信度" value={`${Math.round(detail.announcement_type_confidence * 100)}%`} />
            <Metric label="发布时间" value={detail.published_at ? formatDateTime(detail.published_at) : "未知"} />
            <Metric label="数据完整度" value={detail.data_completeness} />
          </div>
          <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold text-slate-500">分类依据</p>
            <pre className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-slate-700">
              {JSON.stringify(detail.announcement_type_basis, null, 2)}
            </pre>
          </div>
          {detail.missing_fields.length > 0 ? (
            <p className="mt-3 text-sm text-amber-800">缺失字段：{detail.missing_fields.join("、")}</p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <a
              href={detail.source_page_url}
              target="_blank"
              rel="noreferrer"
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700"
            >
              <ExternalLink className="h-4 w-4" />
              官方页面
            </a>
            {detail.document_url ? (
              <a
                href={detail.document_url}
                target="_blank"
                rel="noreferrer"
                className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700"
              >
                <ExternalLink className="h-4 w-4" />
                PDF链接
              </a>
            ) : null}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionTitle icon={<ShieldAlert className="h-5 w-5 text-amber-700" />} title="来源和匹配" />
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Metric label="来源" value={detail.source_display_name} />
            <Metric label="来源代码" value={detail.source_code} />
            <Metric label="权威层级" value={detail.source_authority_level} />
            <Metric label="来源等级" value={detail.source_tier} />
            <Metric label="授权状态" value={detail.authorization_status} />
            <Metric label="再展示状态" value={detail.redistribution_status} />
            <Metric label="商业使用" value={detail.commercial_use_status} />
            <Metric label="法律复核" value={detail.legal_review_status} />
          </div>
          <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold text-slate-500">匹配依据</p>
            <pre className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-slate-700">
              {JSON.stringify(detail.match_evidence, null, 2)}
            </pre>
          </div>
          {detail.source_limitations.length > 0 ? (
            <ul className="mt-3 space-y-1 text-xs leading-5 text-slate-500">
              {detail.source_limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionTitle icon={<RefreshCw className="h-5 w-5 text-slate-700" />} title="PDF提取状态" />
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Metric label="提取状态" value={detail.document_extract_status} />
            <Metric label="页数" value={detail.document_page_count?.toString() ?? "未提取"} />
            <Metric label="字符数" value={detail.document_character_count?.toString() ?? "未提取"} />
            <Metric label="提取时间" value={detail.document_extracted_at ? formatDateTime(detail.document_extracted_at) : "未提取"} />
          </div>
          {detail.document_limitations.length > 0 ? (
            <ul className="mt-3 space-y-1 text-xs leading-5 text-slate-500">
              {detail.document_limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          <button
            onClick={() => runAction("提取正文", async () => {
              await extractAnnouncementDocument(detail.id);
            })}
            className="focus-ring mt-4 inline-flex h-9 items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 text-sm font-semibold text-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={!!actionLoading || !detail.document_url}
            type="button"
          >
            <RefreshCw className="h-4 w-4" />
            {actionLoading === "提取正文" ? "提取中" : "提取正文"}
          </button>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionTitle icon={<CheckCircle2 className="h-5 w-5 text-emerald-700" />} title="导入为正式信息" />
          <p className="mt-1 text-sm leading-6 text-slate-600">
            导入只创建 InformationItem，不自动 AI 分析、不自动标记重要、不自动通知。精确匹配时创建 confirmed 股票关系。
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <ModeButton active={importMode === "metadata_only"} onClick={() => setImportMode("metadata_only")}>
              元数据导入
            </ModeButton>
            <ModeButton active={importMode === "extracted_document"} onClick={() => setImportMode("extracted_document")}>
              正文导入
            </ModeButton>
            <ModeButton active={importMode === "user_supplemented"} onClick={() => setImportMode("user_supplemented")}>
              补充文本导入
            </ModeButton>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Field label="标题覆盖（可选）">
              <input
                value={titleOverride}
                onChange={(event) => setTitleOverride(event.target.value)}
                className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                maxLength={300}
              />
            </Field>
            <Field label="用户备注（可选）">
              <input
                value={userNote}
                onChange={(event) => setUserNote(event.target.value)}
                className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
              />
            </Field>
          </div>
          {importMode === "user_supplemented" ? (
            <Field label="用户补充正文">
              <textarea
                value={supplementedText}
                onChange={(event) => setSupplementedText(event.target.value)}
                className="focus-ring min-h-32 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                required
              />
            </Field>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={handleImport}
              className="focus-ring inline-flex h-10 items-center gap-2 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
              disabled={!!actionLoading || detail.status === "imported"}
              type="button"
            >
              <CheckCircle2 className="h-4 w-4" />
              {actionLoading === "导入公告" ? "导入中" : detail.status === "imported" ? "已导入" : "确认导入"}
            </button>
            <button
              onClick={() => runAction("忽略候选", async () => {
                await patchAnnouncementCandidate(detail.id, "dismissed");
              })}
              className="focus-ring inline-flex h-10 items-center gap-2 rounded-md border border-rose-200 px-4 text-sm font-semibold text-rose-700"
              disabled={!!actionLoading || detail.status === "imported"}
              type="button"
            >
              <XCircle className="h-4 w-4" />
              忽略
            </button>
            {detail.status === "dismissed" || detail.status === "reviewed" ? (
              <button
                onClick={() => runAction("恢复待处理", async () => {
                  await patchAnnouncementCandidate(detail.id, "pending");
                })}
                className="focus-ring inline-flex h-10 items-center gap-2 rounded-md border border-slate-300 px-4 text-sm font-semibold text-slate-700"
                disabled={!!actionLoading}
                type="button"
              >
                恢复待处理
              </button>
            ) : null}
          </div>
          {lastImport ? (
            <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm leading-6 text-emerald-900">
              已生成正式信息：
              <Link href={`/information/items/${lastImport.information_item_id}`} className="ml-1 font-semibold text-emerald-900 underline">
                打开信息详情
              </Link>
              <span className="ml-2 inline-flex items-center gap-1 text-xs">
                <Bot className="h-3.5 w-3.5" />
                AI 分析请在信息详情中手动发起
              </span>
            </div>
          ) : null}
        </div>
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="mt-3 block">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function ModeButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`focus-ring h-9 rounded-md px-3 text-sm font-semibold ${
        active ? "bg-slate-900 text-white" : "border border-slate-300 text-slate-700 hover:bg-slate-50"
      }`}
      type="button"
    >
      {children}
    </button>
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
