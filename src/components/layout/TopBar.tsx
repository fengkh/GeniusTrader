"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, LogOut, ShieldCheck, UserCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { getUnreadNotificationCount } from "@/lib/api/notifications";

export function TopBar() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const [unreadCount, setUnreadCount] = useState(0);
  const displayedUnreadCount = user ? unreadCount : 0;

  const refreshUnreadCount = useCallback(async () => {
    if (!user) {
      return;
    }
    try {
      const response = await getUnreadNotificationCount();
      setUnreadCount(response.unread_count);
    } catch {
      setUnreadCount(0);
    }
  }, [user]);

  useEffect(() => {
    if (loading || !user) {
      return undefined;
    }
    const timeoutId = window.setTimeout(() => {
      void refreshUnreadCount();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loading, refreshUnreadCount, user]);

  async function handleLogout() {
    await logout();
    setUnreadCount(0);
    router.push("/login");
  }

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="flex min-h-16 items-center justify-between gap-3 px-4 lg:px-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-800">
              私人测试版
            </span>
            <span className="rounded-md bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">
              行情未授权关闭
            </span>
          </div>
          <p className="mt-1 hidden truncate text-xs text-slate-500 sm:block">
            官方公告、用户自带 AI、每日复盘和站内通知按真实账户隔离；不提供交易或荐股。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs font-medium text-slate-700 sm:inline-flex">
            <UserCircle className="h-4 w-4 text-slate-600" />
            {loading ? (
              "读取用户..."
            ) : user ? (
              <>
                <span>{user.display_name || user.username}</span>
                <span className="text-slate-400">·</span>
                <span>{user.role === "admin" ? "管理员" : "普通用户"}</span>
              </>
            ) : (
              <Link href="/login" className="text-blue-700 hover:text-blue-800">
                未登录
              </Link>
            )}
          </div>
          {user ? (
            <>
              <button
                onClick={handleLogout}
                className="focus-ring hidden h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50 sm:inline-flex"
                type="button"
              >
                <LogOut className="h-4 w-4" />
                退出
              </button>
              <button
                onClick={handleLogout}
                className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 sm:hidden"
                type="button"
                aria-label="退出登录"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </>
          ) : null}
          <Link
            href="/notifications"
            className="focus-ring relative inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
            aria-label="通知中心"
          >
            <Bell className="h-4 w-4" />
            {displayedUnreadCount > 0 ? (
              <span className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-rose-600 px-1 text-[10px] font-semibold text-white">
                {displayedUnreadCount}
              </span>
            ) : null}
          </Link>
          <div className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs font-medium text-slate-700 md:hidden">
            <ShieldCheck className="h-4 w-4 text-blue-700" />
            {user?.role === "admin" ? "管理员" : "普通用户"}
          </div>
        </div>
      </div>
    </header>
  );
}
