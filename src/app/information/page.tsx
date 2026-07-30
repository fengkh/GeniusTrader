"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import {
  FilePlus2,
  Filter,
  Link2,
  Plus,
  Search,
  X
} from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import {
  createManualInformation,
  createUrlInformation,
  listInformation
} from "@/lib/api/information";
import { listStocks } from "@/lib/api/stocks";
import { humanizeApiError } from "@/lib/api/errors";
import type {
  InformationSourceType,
  InformationSummary,
  Page,
  StockRead
} from "@/lib/api/types";

type FlagFilter = "all" | "true" | "false";
type CreateMode = "manual" | "url";

interface InformationFilters {
  q: string;
  status: string;
  sourceType: InformationSourceType | "";
  stockId: string;
  isImportant: FlagFilter;
  isRead: FlagFilter;
  dateFrom: string;
  dateTo: string;
  limit: number;
  offset: number;
}

interface CreateFormState {
  mode: CreateMode;
  title: string;
  text: string;
  url: string;
  sourceType: InformationSourceType;
  sourceName: string;
  publishedAt: string;
  userNote: string;
  fetchNow: boolean;
}

const defaultFilters: InformationFilters = {
  q: "",
  status: "",
  sourceType: "",
  stockId: "",
  isImportant: "all",
  isRead: "all",
  dateFrom: "",
  dateTo: "",
  limit: 20,
  offset: 0
};

const defaultCreateForm: CreateFormState = {
  mode: "manual",
  title: "",
  text: "",
  url: "",
  sourceType: "unknown",
  sourceName: "",
  publishedAt: "",
  userNote: "",
  fetchNow: true
};

const sourceTypeOptions: Array<{ value: InformationSourceType | ""; label: string }> = [
  { value: "", label: "全部来源" },
  { value: "announcement", label: "正式公告" },
  { value: "news", label: "新闻资讯" },
  { value: "social", label: "平台讨论" },
  { value: "analyst_opinion", label: "平台观点" },
  { value: "user_note", label: "用户补充" },
  { value: "unknown", label: "未知来源" }
];

const createSourceTypeOptions = sourceTypeOptions.filter(
  (item): item is { value: InformationSourceType; label: string } => item.value !== ""
);

const statusOptions = [
  { value: "", label: "全部状态" },
  { value: "submitted", label: "已提交" },
  { value: "fetching", label: "抓取中" },
  { value: "fetch_failed", label: "抓取失败" },
  { value: "ready", label: "可分析" },
  { value: "analyzing", label: "分析中" },
  { value: "analyzed", label: "已分析" },
  { value: "analysis_failed", label: "AI失败" }
];

export default function InformationPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [filters, setFilters] = useState<InformationFilters>(defaultFilters);
  const [draftFilters, setDraftFilters] = useState<InformationFilters>(defaultFilters);
  const [page, setPage] = useState<Page<InformationSummary> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const loadItems = useCallback(
    async (offset = filters.offset) => {
      if (!user) {
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const nextPage = await listInformation({
          q: filters.q,
          status: filters.status,
          source_type: filters.sourceType,
          stock_id: filters.stockId || undefined,
          is_important: flagToBoolean(filters.isImportant),
          is_read: flagToBoolean(filters.isRead),
          date_from: toDateTime(filters.dateFrom),
          date_to: toDateTime(filters.dateTo),
          limit: filters.limit,
          offset
        });
        setPage(nextPage);
      } catch (caught) {
        setError(humanizeApiError(caught));
      } finally {
        setLoading(false);
      }
    },
    [filters, user]
  );

  useEffect(() => {
    if (!authLoading && user) {
      const timeoutId = window.setTimeout(() => {
        void loadItems(0);
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }

    return undefined;
  }, [authLoading, loadItems, user]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = { ...draftFilters, offset: 0 };
    setFilters(next);
  }

  function clearFilters() {
    setDraftFilters(defaultFilters);
    setFilters(defaultFilters);
  }

  function goPage(direction: "prev" | "next") {
    if (!page) {
      return;
    }
    const nextOffset =
      direction === "prev"
        ? Math.max(0, page.offset - page.limit)
        : page.offset + page.limit;
    const next = { ...filters, offset: nextOffset };
    setFilters(next);
    setDraftFilters(next);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="信息中心"
        title="信息中心"
        description="本页连接本地后端 API，承载手动文本和单个公开 URL 的受控录入、筛选与 AI 分析入口。"
        actions={
          <button
            onClick={() => setCreateOpen(true)}
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800"
            type="button"
          >
            <Plus className="h-4 w-4" />
            新增信息
          </button>
        }
      />

      <section className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-950">
        当前是真实后端联调页，但不接入真实公告资讯 Provider、不进行全站爬取。URL
        抓取由后端按单链接受控规则执行，失败后可手动补充正文。
        <Link
          href="/information/announcements"
          className="focus-ring ml-0 mt-3 inline-flex h-9 items-center rounded-md border border-blue-300 bg-white px-3 text-sm font-semibold text-blue-800 hover:bg-blue-50 sm:ml-3 sm:mt-0"
        >
          进入公告候选
        </Link>
        <Link
          href="/information/tasks"
          className="focus-ring ml-0 mt-3 inline-flex h-9 items-center rounded-md border border-blue-300 bg-white px-3 text-sm font-semibold text-blue-800 hover:bg-blue-50 sm:ml-3 sm:mt-0"
        >
          进入研究事项
        </Link>
      </section>

      {!user && !authLoading ? (
        <EmptyState
          title="需要登录"
          description="信息条目属于用户私有数据，请先登录。"
          action={
            <Link
              href="/login?redirect=/information"
              className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
            >
              去登录
            </Link>
          }
        />
      ) : null}

      {user ? (
        <>
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <form className="grid gap-3 lg:grid-cols-[1.2fr_150px_150px_130px_130px] xl:grid-cols-[1.4fr_150px_150px_130px_130px_130px]" onSubmit={applyFilters}>
              <label className="relative block min-w-0">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
                <input
                  value={draftFilters.q}
                  onChange={(event) => setDraftFilters({ ...draftFilters, q: event.target.value })}
                  className="focus-ring h-10 w-full rounded-md border border-slate-300 pl-9 pr-3 text-sm"
                  placeholder="搜索标题、备注或来源"
                />
              </label>
              <Select
                value={draftFilters.status}
                onChange={(value) => setDraftFilters({ ...draftFilters, status: value })}
                options={statusOptions}
              />
              <Select
                value={draftFilters.sourceType}
                onChange={(value) =>
                  setDraftFilters({ ...draftFilters, sourceType: value as InformationSourceType | "" })
                }
                options={sourceTypeOptions}
              />
              <Select
                value={draftFilters.isImportant}
                onChange={(value) => setDraftFilters({ ...draftFilters, isImportant: value as FlagFilter })}
                options={[
                  { value: "all", label: "全部重要性" },
                  { value: "true", label: "重要" },
                  { value: "false", label: "非重要" }
                ]}
              />
              <Select
                value={draftFilters.isRead}
                onChange={(value) => setDraftFilters({ ...draftFilters, isRead: value as FlagFilter })}
                options={[
                  { value: "all", label: "全部阅读" },
                  { value: "false", label: "未读" },
                  { value: "true", label: "已读" }
                ]}
              />
              <div className="flex gap-2 xl:col-auto lg:col-span-5 xl:col-span-1">
                <button
                  className="focus-ring inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800"
                  type="submit"
                >
                  <Filter className="h-4 w-4" />
                  筛选
                </button>
                <button
                  onClick={clearFilters}
                  className="focus-ring h-10 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                  type="button"
                >
                  清除
                </button>
              </div>
            </form>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <input
                value={draftFilters.stockId}
                onChange={(event) => setDraftFilters({ ...draftFilters, stockId: event.target.value })}
                className="focus-ring h-10 rounded-md border border-slate-300 px-3 text-sm"
                placeholder="stock_id 筛选（可选）"
              />
              <input
                value={draftFilters.dateFrom}
                onChange={(event) => setDraftFilters({ ...draftFilters, dateFrom: event.target.value })}
                className="focus-ring h-10 rounded-md border border-slate-300 px-3 text-sm"
                type="date"
              />
              <input
                value={draftFilters.dateTo}
                onChange={(event) => setDraftFilters({ ...draftFilters, dateTo: event.target.value })}
                className="focus-ring h-10 rounded-md border border-slate-300 px-3 text-sm"
                type="date"
              />
              <div className="flex items-center rounded-md bg-slate-50 px-3 text-sm text-slate-600">
                结果：{page?.total ?? 0} 条
              </div>
            </div>
          </section>

          {error ? <ErrorState title="信息列表加载失败" description={error} /> : null}
          {loading ? (
            <LoadingSkeleton lines={7} />
          ) : page && page.items.length > 0 ? (
            <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <div className="hidden grid-cols-[1fr_120px_120px_120px_120px] gap-3 border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-500 lg:grid">
                <span>信息</span>
                <span>来源</span>
                <span>状态</span>
                <span>标记</span>
                <span>更新时间</span>
              </div>
              {page.items.map((item) => (
                <InformationRow key={item.id} item={item} />
              ))}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-sm text-slate-600">
                <span>
                  第 {page.offset + 1} - {Math.min(page.offset + page.limit, page.total)} 条，共 {page.total} 条
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => goPage("prev")}
                    className="focus-ring h-9 rounded-md border border-slate-300 px-3 font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={page.offset === 0}
                    type="button"
                  >
                    上一页
                  </button>
                  <button
                    onClick={() => goPage("next")}
                    className="focus-ring h-9 rounded-md border border-slate-300 px-3 font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={page.offset + page.limit >= page.total}
                    type="button"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </section>
          ) : (
            <EmptyState
              title="暂无信息条目"
              description="可以手动录入公开信息正文，也可以提交单个公开 URL 让后端进行受控抓取。"
              action={
                <button
                  onClick={() => setCreateOpen(true)}
                  className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
                  type="button"
                >
                  新增信息
                </button>
              }
            />
          )}
        </>
      ) : null}

      {createOpen ? (
        <CreateInformationPanel
          onClose={() => setCreateOpen(false)}
          onCreated={(itemId) => router.push(`/information/items/${itemId}`)}
        />
      ) : null}
    </div>
  );
}

function InformationRow({ item }: { item: InformationSummary }) {
  return (
    <Link
      href={`/information/items/${item.id}`}
      className="focus-ring grid gap-2 border-b border-slate-100 px-4 py-3 hover:bg-slate-50 last:border-b-0 lg:grid-cols-[1fr_120px_120px_120px_120px] lg:items-center"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="truncate text-sm font-semibold text-slate-950">
            {item.title || "未命名信息"}
          </h2>
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
            {item.input_type === "manual_text" ? "手动文本" : "公开URL"}
          </span>
        </div>
        <p className="mt-1 line-clamp-1 text-xs text-slate-500">{item.user_note || "暂无用户备注"}</p>
      </div>
      <span className="text-xs font-medium text-slate-700">{sourceTypeLabel(item.source_type)}</span>
      <StatusPill status={item.status} />
      <div className="flex flex-wrap gap-1.5">
        {item.is_important ? <SmallPill tone="amber">重要</SmallPill> : <SmallPill>普通</SmallPill>}
        {item.is_read ? <SmallPill>已读</SmallPill> : <SmallPill tone="blue">未读</SmallPill>}
      </div>
      <span className="text-xs text-slate-500">{formatDateTime(item.updated_at)}</span>
    </Link>
  );
}

function CreateInformationPanel({
  onClose,
  onCreated
}: {
  onClose: () => void;
  onCreated: (itemId: string) => void;
}) {
  const [form, setForm] = useState<CreateFormState>(defaultCreateForm);
  const [selectedStocks, setSelectedStocks] = useState<StockRead[]>([]);
  const [stockQuery, setStockQuery] = useState("");
  const [stockResults, setStockResults] = useState<StockRead[]>([]);
  const [stockLoading, setStockLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function searchStocks() {
    setStockLoading(true);
    setError(null);
    try {
      const result = await listStocks({ q: stockQuery, limit: 10 });
      setStockResults(result.items);
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setStockLoading(false);
    }
  }

  function addStock(stock: StockRead) {
    setSelectedStocks((current) =>
      current.some((item) => item.id === stock.id) ? current : [...current, stock]
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const related_stock_ids = selectedStocks.map((stock) => stock.id);
      const detail =
        form.mode === "manual"
          ? await createManualInformation({
              title: emptyToNull(form.title),
              text: form.text,
              source_type: form.sourceType,
              source_name: emptyToNull(form.sourceName),
              published_at: toDateTime(form.publishedAt),
              user_note: emptyToNull(form.userNote),
              related_stock_ids,
              analyze_now: false
            })
          : await createUrlInformation({
              url: form.url,
              source_type: form.sourceType,
              user_note: emptyToNull(form.userNote),
              related_stock_ids,
              fetch_now: form.fetchNow
            });
      onCreated(detail.id);
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end bg-slate-950/30 p-4 sm:items-center sm:justify-center">
      <section className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">新增信息</h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              支持手动正文和单个公开 URL。链接抓取失败不会删除条目，可后续补充正文。
            </p>
          </div>
          <button
            onClick={onClose}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50"
            type="button"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error ? <div className="mt-4"><ErrorState title="新增失败" description={error} /></div> : null}

        <div className="mt-4 flex rounded-md border border-slate-300 bg-slate-50 p-1">
          <ModeButton active={form.mode === "manual"} onClick={() => setForm({ ...form, mode: "manual" })}>
            <FilePlus2 className="h-4 w-4" />
            手动文本
          </ModeButton>
          <ModeButton active={form.mode === "url"} onClick={() => setForm({ ...form, mode: "url" })}>
            <Link2 className="h-4 w-4" />
            公开URL
          </ModeButton>
        </div>

        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
          {form.mode === "manual" ? (
            <>
              <Field label="标题（可选）">
                <input
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                  className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                  maxLength={300}
                />
              </Field>
              <Field label="正文">
                <textarea
                  value={form.text}
                  onChange={(event) => setForm({ ...form, text: event.target.value })}
                  className="focus-ring min-h-36 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  required
                />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="来源名称（可选）">
                  <input
                    value={form.sourceName}
                    onChange={(event) => setForm({ ...form, sourceName: event.target.value })}
                    className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                    maxLength={200}
                  />
                </Field>
                <Field label="发布时间（可选）">
                  <input
                    value={form.publishedAt}
                    onChange={(event) => setForm({ ...form, publishedAt: event.target.value })}
                    className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                    type="date"
                  />
                </Field>
              </div>
            </>
          ) : (
            <>
              <Field label="公开 URL">
                <input
                  value={form.url}
                  onChange={(event) => setForm({ ...form, url: event.target.value })}
                  className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                  placeholder="https://example.com/article"
                  type="url"
                  required
                />
              </Field>
              <label className="flex items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <span>创建后立即尝试受控抓取</span>
                <input
                  type="checkbox"
                  checked={form.fetchNow}
                  onChange={(event) => setForm({ ...form, fetchNow: event.target.checked })}
                  className="h-4 w-4 rounded border-slate-300"
                />
              </label>
            </>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="来源类型">
              <select
                value={form.sourceType}
                onChange={(event) => setForm({ ...form, sourceType: event.target.value as InformationSourceType })}
                className="focus-ring h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
              >
                {createSourceTypeOptions.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="用户备注（可选）">
              <input
                value={form.userNote}
                onChange={(event) => setForm({ ...form, userNote: event.target.value })}
                className="focus-ring h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
              />
            </Field>
          </div>

          <section className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-sm font-semibold text-slate-950">关联股票（可选）</p>
            <div className="mt-3 flex gap-2">
              <input
                value={stockQuery}
                onChange={(event) => setStockQuery(event.target.value)}
                className="focus-ring h-10 min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 text-sm"
                placeholder="搜索代码或名称"
              />
              <button
                onClick={searchStocks}
                className="focus-ring h-10 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                type="button"
              >
                {stockLoading ? "搜索中" : "搜索"}
              </button>
            </div>
            {selectedStocks.length > 0 ? (
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedStocks.map((stock) => (
                  <button
                    key={stock.id}
                    onClick={() =>
                      setSelectedStocks((current) => current.filter((item) => item.id !== stock.id))
                    }
                    className="focus-ring rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-800"
                    type="button"
                  >
                    {stock.name} {stock.symbol} ×
                  </button>
                ))}
              </div>
            ) : null}
            {stockResults.length > 0 ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {stockResults.map((stock) => (
                  <button
                    key={stock.id}
                    onClick={() => addStock(stock)}
                    className="focus-ring rounded-md border border-slate-200 bg-white p-2 text-left text-sm hover:bg-slate-50"
                    type="button"
                  >
                    <span className="font-semibold text-slate-950">{stock.name}</span>
                    <span className="ml-2 text-xs text-slate-500">
                      {stock.exchange}{stock.symbol}
                    </span>
                  </button>
                ))}
              </div>
            ) : null}
          </section>

          <button
            className="focus-ring h-10 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="submit"
            disabled={submitting}
          >
            {submitting ? "提交中..." : "保存信息"}
          </button>
        </form>
      </section>
    </div>
  );
}

function Select({
  value,
  onChange,
  options
}: {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="focus-ring h-10 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-800"
    >
      {options.map((item) => (
        <option key={item.value} value={item.value}>
          {item.label}
        </option>
      ))}
    </select>
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

function ModeButton({
  active,
  onClick,
  children
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`focus-ring inline-flex h-9 flex-1 items-center justify-center gap-2 rounded px-3 text-sm font-semibold ${
        active ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-white"
      }`}
      type="button"
    >
      {children}
    </button>
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

  return <span className={`w-fit rounded-md border px-2 py-1 text-xs font-semibold ${tone}`}>{statusLabel(status)}</span>;
}

function SmallPill({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "amber" | "blue" }) {
  const tones = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    blue: "border-blue-200 bg-blue-50 text-blue-800"
  };

  return <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}>{children}</span>;
}

function sourceTypeLabel(value: string): string {
  return sourceTypeOptions.find((item) => item.value === value)?.label ?? value;
}

function statusLabel(value: string): string {
  return statusOptions.find((item) => item.value === value)?.label ?? value;
}

function flagToBoolean(value: FlagFilter): boolean | null {
  if (value === "all") {
    return null;
  }
  return value === "true";
}

function toDateTime(value: string): string | undefined {
  return value ? `${value}T00:00:00+08:00` : undefined;
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}
