"use client";

import Link from "next/link";
import { Bell, CheckCircle2, Circle, Filter } from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import {
  notificationSeverityLabel,
  notificationSeverityTone,
  notificationStateLabel,
  notificationTypeLabel
} from "@/lib/formatters";
import { useMockState } from "@/lib/mock-state";
import type { NotificationMock, NotificationType } from "@/mock/types";

type NotificationFilter = "all" | "important" | NotificationType;

const filters: Array<{ id: NotificationFilter; label: string }> = [
  { id: "all", label: "全部" },
  { id: "important", label: "重要" },
  { id: "daily-review", label: "每日复盘" },
  { id: "announcement", label: "公告" },
  { id: "anomaly", label: "异动" },
  { id: "observation", label: "观察" },
  { id: "valuation", label: "估值" },
  { id: "system", label: "系统" }
];

export default function NotificationsPage() {
  const { data } = useMockState();
  const [filter, setFilter] = useState<NotificationFilter>("all");
  const unreadCount = data.notifications.filter((item) => item.state === "unread").length;
  const filteredItems = useMemo(
    () =>
      data.notifications.filter((item) => {
        if (filter === "all") {
          return true;
        }

        if (filter === "important") {
          return item.severity === "important" || item.severity === "critical";
        }

        return item.type === filter;
      }),
    [data.notifications, filter]
  );

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="通知中心"
        title="通知"
        description="站内通知用于承接复盘、公告、异动、观察条件、估值和系统事件；微信公众号仅保留Mock状态。"
        actions={
          <Link
            href="/settings/notifications"
            className="focus-ring inline-flex h-9 items-center rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            通知设置
          </Link>
        }
      />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <Bell className="h-5 w-5 text-blue-700" />
            <h2 className="text-lg font-semibold text-slate-950">站内通知列表</h2>
            <SimulatedDataBadge compact />
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              未读 {unreadCount}
            </span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {filters.map((item) => (
              <button
                key={item.id}
                onClick={() => setFilter(item.id)}
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
        </div>

        <div className="mt-4">
          {filteredItems.length === 0 ? (
            <EmptyState
              title="暂无通知"
              description="当前筛选条件下没有站内通知；通知失败不会阻断复盘、估值或行情展示。"
            />
          ) : (
            <div className="grid gap-2">
              {filteredItems.map((item) => (
                <NotificationRow key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>

        <p className="mt-4 rounded-md bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-800">
          常规涨跌不属于严重通知；严重级别仅用于账户安全或严重服务故障。AI不能提升通知严重度或修改用户偏好。
        </p>
      </section>
    </div>
  );
}

function NotificationRow({ item }: { item: NotificationMock }) {
  const isUnread = item.state === "unread";

  return (
    <Link
      href={item.targetHref}
      className={`focus-ring grid gap-2 rounded-md border p-3 hover:bg-slate-50 sm:grid-cols-[1fr_auto] ${
        isUnread ? "border-blue-200 bg-blue-50/40" : "border-slate-200 bg-white"
      }`}
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          {isUnread ? <Circle className="h-3 w-3 fill-blue-600 text-blue-600" /> : <CheckCircle2 className="h-4 w-4 text-slate-400" />}
          <span className="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-600">
            {notificationTypeLabel(item.type)}
          </span>
          <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${notificationSeverityTone(item.severity)}`}>
            {notificationSeverityLabel(item.severity)}
          </span>
          <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600">
            {notificationStateLabel(item.state)}
          </span>
        </div>
        <p className="mt-2 line-clamp-1 font-semibold text-slate-950">{item.title}</p>
        <p className="mt-1 line-clamp-2 text-sm leading-6 text-slate-600">{item.summary}</p>
        <p className="mt-1 text-xs text-slate-500">目标页面：{item.targetHref}；来源事件：{item.sourceEventId}</p>
      </div>
      <div className="flex items-center justify-between gap-2 sm:flex-col sm:items-end">
        <StatusTag status={item.dataStatus} />
        <span className="text-xs text-slate-500">{item.createdAt}</span>
        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
          <Filter className="h-3 w-3" />
          {item.serviceStatus}
        </span>
      </div>
    </Link>
  );
}
