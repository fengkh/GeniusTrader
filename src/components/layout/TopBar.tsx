"use client";

import Link from "next/link";
import { Bell, ShieldCheck } from "lucide-react";

import { MockRoleSwitcher } from "@/components/mock/MockRoleSwitcher";
import { MockScenarioSwitcher } from "@/components/mock/MockScenarioSwitcher";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { useMockState } from "@/lib/mock-state";

export function TopBar() {
  const { role, data } = useMockState();
  const unreadCount = data.notifications.filter((item) => item.state === "unread").length;

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="flex min-h-16 items-center justify-between gap-3 px-4 lg:px-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <SimulatedDataBadge compact />
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              {data.scenarioName}场景
            </span>
          </div>
          <p className="mt-1 hidden truncate text-xs text-slate-500 sm:block">
            最后更新时间：{data.generatedAt}，当前身份：
            {role === "admin" ? "管理员" : "普通用户"}
          </p>
        </div>
        <div className="hidden min-w-[360px] grid-cols-2 gap-2 md:grid">
          <MockRoleSwitcher compact />
          <MockScenarioSwitcher compact />
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/notifications"
            className="focus-ring relative inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
            aria-label="通知中心"
          >
            <Bell className="h-4 w-4" />
            {unreadCount > 0 ? (
              <span className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold text-white">
                {unreadCount}
              </span>
            ) : null}
          </Link>
          <div className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs font-medium text-slate-700 md:hidden">
            <ShieldCheck className="h-4 w-4 text-blue-700" />
            {role === "admin" ? "管理员" : "普通用户"}
          </div>
        </div>
      </div>
    </header>
  );
}
