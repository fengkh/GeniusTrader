"use client";

import Link from "next/link";
import type { FormEvent, ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckSquare, Plus, RefreshCw, Search, X } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import {
  createResearchTask,
  listResearchTasks,
  updateResearchTaskStatus
} from "@/lib/api/research-tasks";
import type {
  Page,
  ResearchTask,
  ResearchTaskPriority,
  ResearchTaskStatus,
  ResearchTaskType
} from "@/lib/api/types";

const statusOptions: Array<{ value: ResearchTaskStatus | ""; label: string }> = [
  { value: "", label: "全部状态" },
  { value: "pending", label: "待处理" },
  { value: "monitoring", label: "跟踪中" },
  { value: "confirmed", label: "已发生" },
  { value: "disproved", label: "未发生" },
  { value: "partially_confirmed", label: "部分发生" },
  { value: "unable_to_determine", label: "无法判断" },
  { value: "no_longer_applicable", label: "不再适用" },
  { value: "dismissed", label: "已忽略" }
];

const typeOptions: Array<{ value: ResearchTaskType | ""; label: string }> = [
  { value: "", label: "全部类型" },
  { value: "verification", label: "待核实" },
  { value: "observation", label: "观察条件" },
  { value: "follow_up", label: "后续跟进" },
  { value: "missing_document", label: "缺少材料" },
  { value: "user_note", label: "用户笔记" }
];

const priorityOptions: Array<{ value: ResearchTaskPriority | ""; label: string }> = [
  { value: "", label: "全部优先级" },
  { value: "high", label: "高" },
  { value: "medium", label: "中" },
  { value: "low", label: "低" }
];

export default function ResearchTasksPage() {
  const { user, loading: authLoading } = useAuth();
  const [page, setPage] = useState<Page<ResearchTask> | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<ResearchTaskStatus | "">("");
  const [taskType, setTaskType] = useState<ResearchTaskType | "">("");
  const [priority, setPriority] = useState<ResearchTaskPriority | "">("");
  const [stockId, setStockId] = useState("");
  const [highlightedTaskId, setHighlightedTaskId] = useState("");
  const [openOnly, setOpenOnly] = useState(true);
  const [loading, setLoading] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [workingTaskId, setWorkingTaskId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const filters = useMemo(
    () => ({ query, status, taskType, priority, stockId, openOnly }),
    [openOnly, priority, query, status, stockId, taskType]
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      const initialStockId = params.get("stock_id");
      if (initialStockId) {
        setStockId((current) => current || initialStockId);
      }
      setHighlightedTaskId(params.get("task") ?? "");
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const loadData = useCallback(async () => {
    if (!user) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setPage(
        await listResearchTasks({
          q: filters.query,
          status: filters.status,
          task_type: filters.taskType,
          priority: filters.priority,
          stock_id: filters.stockId,
          open_only: filters.openOnly,
          limit: 50
        })
      );
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [filters, user]);

  useEffect(() => {
    if (!authLoading && user) {
      const timer = window.setTimeout(() => {
        void loadData();
      }, 0);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [authLoading, loadData, user]);

  async function handleStatus(task: ResearchTask, nextStatus: ResearchTaskStatus) {
    setWorkingTaskId(task.id);
    setError(null);
    setMessage(null);
    try {
      await updateResearchTaskStatus(task.id, {
        status: nextStatus,
        note: `用户在任务中心标记为：${statusLabel(nextStatus)}`
      });
      setMessage("研究事项状态已更新，结果会进入后续复盘材料。");
      await loadData();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setWorkingTaskId(null);
    }
  }

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="研究事项属于用户私有数据，请先登录。"
        action={
          <Link
            href="/login?redirect=/information/tasks"
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
        eyebrow="信息中心 / 任务"
        title="研究事项"
        description="管理待核实、观察条件和后续跟进；AI 只提供建议，创建和状态更新必须由用户显式操作。"
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setPanelOpen(true)}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800"
              type="button"
            >
              <Plus className="h-4 w-4" />
              新建事项
            </button>
            <button
              onClick={() => void loadData()}
              disabled={loading}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
              type="button"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              刷新
            </button>
          </div>
        }
      />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 lg:grid-cols-[1.2fr_150px_150px_150px_1fr_auto] lg:items-end">
          <label className="block">
            <span className="text-xs font-semibold text-slate-500">搜索</span>
            <span className="relative mt-1 block">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="focus-ring h-9 w-full rounded-md border border-slate-300 pl-9 pr-3 text-sm"
                placeholder="标题、说明、证据摘要"
              />
            </span>
          </label>
          <Select value={taskType} onChange={(value) => setTaskType(value as ResearchTaskType | "")} options={typeOptions} />
          <Select value={status} onChange={(value) => setStatus(value as ResearchTaskStatus | "")} options={statusOptions} />
          <Select value={priority} onChange={(value) => setPriority(value as ResearchTaskPriority | "")} options={priorityOptions} />
          <input
            value={stockId}
            onChange={(event) => setStockId(event.target.value)}
            className="focus-ring h-9 rounded-md border border-slate-300 px-3 text-sm"
            placeholder="stock_id 可选"
          />
          <label className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={openOnly}
              onChange={(event) => setOpenOnly(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            仅打开
          </label>
        </div>
        <p className="mt-3 text-xs text-slate-500">结果：{page?.total ?? 0} 项；状态结果会写入研究事项更新记录和后续复盘输入。</p>
      </section>

      {message ? <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">{message}</div> : null}
      {error ? <ErrorState title="研究事项操作失败" description={error} /> : null}
      {loading || authLoading ? <LoadingSkeleton lines={8} /> : null}

      {!loading && page ? (
        page.items.length === 0 ? (
          <EmptyState
            title="暂无研究事项"
            description="可以手动创建，也可以从信息分析或每日复盘建议中显式采纳。"
            action={
              <button
                onClick={() => setPanelOpen(true)}
                className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
                type="button"
              >
                新建事项
              </button>
            }
          />
        ) : (
          <section className="grid gap-3">
            {page.items.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                highlighted={task.id === highlightedTaskId}
                working={workingTaskId === task.id}
                onStatus={handleStatus}
              />
            ))}
          </section>
        )
      ) : null}

      {panelOpen ? (
        <CreateTaskPanel
          stockId={stockId}
          onClose={() => setPanelOpen(false)}
          onSaved={async () => {
            setPanelOpen(false);
            setMessage("研究事项已创建。");
            await loadData();
          }}
        />
      ) : null}
    </div>
  );
}

function TaskRow({
  task,
  highlighted,
  working,
  onStatus
}: {
  task: ResearchTask;
  highlighted: boolean;
  working: boolean;
  onStatus: (task: ResearchTask, status: ResearchTaskStatus) => Promise<void>;
}) {
  return (
    <article className={`rounded-lg border bg-white p-4 shadow-sm ${highlighted ? "border-blue-300 ring-2 ring-blue-100" : "border-slate-200"}`}>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <CheckSquare className="h-4 w-4 text-blue-700" />
            <h2 className="font-semibold text-slate-950">{task.title}</h2>
            <Pill>{typeLabel(task.task_type)}</Pill>
            <Pill tone={task.priority === "high" ? "rose" : "slate"}>{priorityLabel(task.priority)}</Pill>
            <Pill tone={task.status === "pending" || task.status === "monitoring" ? "amber" : "emerald"}>{statusLabel(task.status)}</Pill>
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-700">{task.description}</p>
          <p className="mt-2 text-xs text-slate-500">
            {task.stock ? `${task.stock.name} · ${task.stock.symbol}` : "未关联股票"}；到期：
            {task.due_date ?? "未设置"}；来源：{task.source_type}
          </p>
          {task.current_evidence_summary ? (
            <p className="mt-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
              证据摘要：{task.current_evidence_summary}
            </p>
          ) : null}
        </div>
        <div className="grid gap-2 sm:grid-cols-3 lg:min-w-[420px]">
          {(["confirmed", "disproved", "partially_confirmed", "unable_to_determine", "no_longer_applicable"] as ResearchTaskStatus[]).map((value) => (
            <button
              key={value}
              onClick={() => void onStatus(task, value)}
              disabled={working || task.status === value}
              className="focus-ring h-9 rounded-md border border-slate-300 px-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              type="button"
            >
              {working ? "更新中" : statusLabel(value)}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}

function CreateTaskPanel({
  stockId,
  onClose,
  onSaved
}: {
  stockId: string;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [taskType, setTaskType] = useState<ResearchTaskType>("verification");
  const [priority, setPriority] = useState<ResearchTaskPriority>("medium");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await createResearchTask({
        stock_id: stockId || null,
        task_type: taskType,
        title,
        description,
        priority,
        due_date: dueDate || null,
        source_type: "user"
      });
      await onSaved();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end bg-slate-950/30 p-4 sm:items-center sm:justify-center">
      <section className="w-full max-w-2xl rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">新建研究事项</h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">手动创建只影响当前用户，不会修改原始行情、公告或 AI 分析事实。</p>
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
        {error ? <div className="mt-3"><ErrorState title="创建失败" description={error} /></div> : null}
        <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="focus-ring h-10 rounded-md border border-slate-300 px-3 text-sm"
            placeholder="事项标题"
            required
            maxLength={240}
          />
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            className="focus-ring min-h-28 rounded-md border border-slate-300 px-3 py-2 text-sm"
            placeholder="说明需要验证什么、为什么重要，以及应参考哪些来源。"
            required
          />
          <div className="grid gap-3 sm:grid-cols-3">
            <Select value={taskType} onChange={(value) => setTaskType(value as ResearchTaskType)} options={typeOptions.filter((item) => item.value)} />
            <Select value={priority} onChange={(value) => setPriority(value as ResearchTaskPriority)} options={priorityOptions.filter((item) => item.value)} />
            <input
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className="focus-ring h-10 rounded-md border border-slate-300 px-3 text-sm"
            />
          </div>
          <button
            className="focus-ring h-10 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            type="submit"
            disabled={saving}
          >
            {saving ? "保存中" : "保存研究事项"}
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
      className="focus-ring h-9 rounded-md border border-slate-300 bg-white px-3 text-sm"
    >
      {options.map((option) => (
        <option key={option.value || "all"} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

function Pill({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "amber" | "emerald" | "rose" }) {
  const tones = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
    rose: "border-rose-200 bg-rose-50 text-rose-800"
  };
  return <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}>{children}</span>;
}

function typeLabel(value: string): string {
  return typeOptions.find((item) => item.value === value)?.label ?? value;
}

function priorityLabel(value: string): string {
  const labels: Record<string, string> = {
    high: "高优先级",
    medium: "中优先级",
    low: "低优先级"
  };
  return labels[value] ?? value;
}

function statusLabel(value: string): string {
  return statusOptions.find((item) => item.value === value)?.label ?? value;
}
