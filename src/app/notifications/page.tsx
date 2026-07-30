"use client";

import Link from "next/link";
import {
  Bell,
  CheckCircle2,
  Circle,
  Inbox,
  RefreshCw,
  Settings,
  Trash2
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import {
  listNotifications,
  markAllNotificationsRead,
  patchNotification
} from "@/lib/api/notifications";
import type {
  InAppNotification,
  InAppNotificationStatus,
  NotificationEventType,
  Page
} from "@/lib/api/types";

type NotificationFilter =
  | "all"
  | "unread"
  | "daily-review"
  | "important-information"
  | "verification"
  | "ai-failed"
  | "archived";

const filters: Array<{ id: NotificationFilter; label: string }> = [
  { id: "all", label: "全部" },
  { id: "unread", label: "未读" },
  { id: "daily-review", label: "每日复盘" },
  { id: "important-information", label: "重要信息" },
  { id: "verification", label: "待核实" },
  { id: "ai-failed", label: "AI失败" },
  { id: "archived", label: "已归档" }
];

export default function NotificationsPage() {
  const { user, loading: authLoading } = useAuth();
  const [filter, setFilter] = useState<NotificationFilter>("all");
  const [page, setPage] = useState<Page<InAppNotification> | null>(null);
  const [loading, setLoading] = useState(false);
  const [workingId, setWorkingId] = useState<string | null>(null);
  const [bulkWorking, setBulkWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const apiParams = useMemo(() => notificationParams(filter), [filter]);

  const refreshNotifications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPage(await listNotifications({ ...apiParams, limit: 60 }));
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [apiParams]);

  useEffect(() => {
    if (authLoading || !user) {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      void refreshNotifications();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [authLoading, refreshNotifications, user]);

  const visibleItems = useMemo(() => {
    const items = page?.items ?? [];
    if (filter === "daily-review") {
      return items.filter((item) => item.event_type.startsWith("user_daily_review."));
    }
    return items;
  }, [filter, page?.items]);

  const unreadCount = useMemo(
    () => visibleItems.filter((item) => item.status === "unread").length,
    [visibleItems]
  );

  async function handleAction(notificationId: string, action: "mark_read" | "mark_unread" | "archive" | "unarchive") {
    setWorkingId(notificationId);
    setError(null);
    setSuccess(null);
    try {
      await patchNotification(notificationId, action);
      await refreshNotifications();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setWorkingId(null);
    }
  }

  async function handleMarkAllRead() {
    if (bulkWorking) {
      return;
    }
    setBulkWorking(true);
    setError(null);
    setSuccess(null);
    try {
      if (filter === "daily-review") {
        await Promise.all(
          visibleItems
            .filter((item) => item.status === "unread")
            .map((item) => patchNotification(item.id, "mark_read"))
        );
      } else {
        await markAllNotificationsRead(
          apiParams.event_type ? { event_type: apiParams.event_type } : {}
        );
      }
      setSuccess("已批量标记为已读。");
      await refreshNotifications();
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setBulkWorking(false);
    }
  }

  if (authLoading) {
    return <LoadingSkeleton lines={6} />;
  }

  if (!user) {
    return <ErrorState title="需要登录" description="站内通知是真实用户数据，请先登录私人测试账户。" />;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="真实API"
        title="通知中心"
        description="站内通知由 BusinessEvent 转换生成；通知摘要不包含完整私人正文或敏感凭据。"
        actions={
          <Link
            href="/settings/notifications"
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Settings className="h-4 w-4" />
            通知设置
          </Link>
        }
      />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <Bell className="h-5 w-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">站内通知列表</h2>
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              未读 {unreadCount}
            </span>
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              当前 {visibleItems.length} 条
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={refreshNotifications}
              className="focus-ring inline-flex h-8 items-center gap-2 rounded-md border border-slate-300 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              type="button"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              刷新
            </button>
            <button
              onClick={handleMarkAllRead}
              disabled={bulkWorking || unreadCount === 0}
              className="focus-ring inline-flex h-8 items-center gap-2 rounded-md bg-slate-900 px-3 text-xs font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
              type="button"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              全部已读
            </button>
          </div>
        </div>

        <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
          {filters.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setFilter(item.id);
                setSuccess(null);
                setError(null);
              }}
              className={`focus-ring h-8 shrink-0 rounded-md border px-3 text-xs font-semibold ${
                filter === item.id
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
              }`}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>

        {success ? (
          <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
            {success}
          </div>
        ) : null}
        {error ? <div className="mt-3"><ErrorState title="无法读取通知" description={error} /></div> : null}

        <div className="mt-4">
          {loading ? <LoadingSkeleton lines={6} /> : null}
          {!loading && !error && visibleItems.length === 0 ? (
            <EmptyState
              title="暂无通知"
              description="当前筛选条件下没有站内通知。全市场、估值和微信投递状态仍属于 Mock 或未来阶段。"
            />
          ) : null}
          {!loading && !error && visibleItems.length ? (
            <div className="grid gap-2">
              {visibleItems.map((item) => (
                <NotificationRow
                  key={item.id}
                  item={item}
                  working={workingId === item.id}
                  onAction={handleAction}
                />
              ))}
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function NotificationRow({
  item,
  working,
  onAction
}: {
  item: InAppNotification;
  working: boolean;
  onAction: (notificationId: string, action: "mark_read" | "mark_unread" | "archive" | "unarchive") => Promise<void>;
}) {
  const isUnread = item.status === "unread";

  return (
    <article
      className={`grid gap-2 rounded-md border p-3 sm:grid-cols-[1fr_auto] ${
        isUnread ? "border-blue-200 bg-blue-50/40" : "border-slate-200 bg-white"
      }`}
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          {isUnread ? <Circle className="h-3 w-3 fill-blue-600 text-blue-600" /> : <CheckCircle2 className="h-4 w-4 text-slate-400" />}
          <span className="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">
            {eventTypeLabel(item.event_type)}
          </span>
          <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${severityTone(item.severity)}`}>
            {severityLabel(item.severity)}
          </span>
          <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
            {statusLabel(item.status)}
          </span>
        </div>
        <p className="mt-2 line-clamp-1 font-semibold text-slate-950">{item.title}</p>
        <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-600">{item.summary}</p>
        <p className="mt-1 text-xs text-slate-500">
          target：{item.target_type}；deep_link：{item.deep_link}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 sm:min-w-[220px] sm:justify-end">
        <span className="text-xs text-slate-500">{formatDateTime(item.created_at)}</span>
        <Link
          href={item.deep_link}
          className="focus-ring inline-flex h-8 items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          <Inbox className="h-3.5 w-3.5" />
          打开
        </Link>
        <button
          onClick={() => onAction(item.id, isUnread ? "mark_read" : "mark_unread")}
          disabled={working}
          className="focus-ring h-8 rounded-md border border-slate-300 bg-white px-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
          type="button"
        >
          {isUnread ? "已读" : "未读"}
        </button>
        <button
          onClick={() => onAction(item.id, item.status === "archived" ? "unarchive" : "archive")}
          disabled={working}
          className="focus-ring inline-flex h-8 items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
          type="button"
        >
          <Trash2 className="h-3.5 w-3.5" />
          {item.status === "archived" ? "恢复" : "归档"}
        </button>
      </div>
    </article>
  );
}

function notificationParams(filter: NotificationFilter): {
  status?: InAppNotificationStatus | "";
  event_type?: NotificationEventType | "";
} {
  if (filter === "unread") {
    return { status: "unread" };
  }
  if (filter === "archived") {
    return { status: "archived" };
  }
  if (filter === "important-information") {
    return { event_type: "information.high_priority_detected" };
  }
  if (filter === "verification") {
    return { event_type: "information.verification_required" };
  }
  if (filter === "ai-failed") {
    return { event_type: "ai_task.failed" };
  }
  return {};
}

function eventTypeLabel(eventType: NotificationEventType): string {
  const labels: Record<NotificationEventType, string> = {
    "user_daily_review.generated": "复盘已生成",
    "user_daily_review.partial": "复盘部分完成",
    "user_daily_review.failed": "复盘失败",
    "user_daily_review.became_stale": "复盘需更新",
    "information.high_priority_detected": "重要信息",
    "information.verification_required": "待核实事项",
    "ai_task.failed": "AI失败",
    "research_task.created": "研究事项已创建",
    "research_task.status_changed": "研究事项状态更新",
    "research_task.due": "研究事项到期",
    "observation_condition.due": "观察条件到期"
  };
  return labels[eventType];
}

function severityLabel(severity: "info" | "notice" | "important"): string {
  const labels = {
    info: "普通",
    notice: "提醒",
    important: "重要"
  };
  return labels[severity];
}

function severityTone(severity: "info" | "notice" | "important"): string {
  const tones = {
    info: "border-slate-200 bg-slate-50 text-slate-700",
    notice: "border-blue-200 bg-blue-50 text-blue-800",
    important: "border-amber-200 bg-amber-50 text-amber-800"
  };
  return tones[severity];
}

function statusLabel(status: InAppNotificationStatus): string {
  const labels: Record<InAppNotificationStatus, string> = {
    unread: "未读",
    read: "已读",
    archived: "已归档",
    expired: "已过期"
  };
  return labels[status];
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
