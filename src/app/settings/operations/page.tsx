"use client";

import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";

const featureMatrix = [
  ["SECURITY_MASTER_READ", "已开启", "读取本地 A 股证券主数据。"],
  ["WATCHLIST", "已开启", "真实用户自选股管理。"],
  ["OFFICIAL_ANNOUNCEMENTS", "部署配置控制", "生产首版只允许 CNINFO 和 SSE_DISCLOSURE 显式启用。"],
  ["USER_AI_BYOK", "已开启", "用户自带 API Key，经后端 AI Gateway 调用。"],
  ["DAILY_REVIEWS", "已开启", "用户主动生成每日复盘，保留版本。"],
  ["MARKET_DATA", "关闭", "暂无经授权的真实行情数据。"],
  ["PUBLIC_REGISTRATION", "关闭", "私人测试版账户由管理员创建。"],
  ["AUTO_TRADING", "关闭", "产品不是交易系统。"],
  ["SOCIAL_CRAWLING", "关闭", "第一版不做全网社交平台爬虫。"]
];

export default function OperationsSettingsPage() {
  const { user, loading } = useAuth();

  if (!loading && !user) {
    return (
      <EmptyState
        title="需要登录"
        description="发布运行状态仅登录用户可查看。"
        action={
          <Link
            href="/login?redirect=/settings/operations"
            className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
          >
            去登录
          </Link>
        }
      />
    );
  }

  if (!loading && user?.role !== "admin") {
    return <EmptyState title="无管理员权限" description="普通用户不会看到内部发布检查、任务失败摘要或运维状态。" />;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="管理员设置"
        title="发布运行状态"
        description="只读展示私人测试版功能矩阵和发布边界；完整门禁以服务器上的 release_check CLI 为准。"
        actions={
          <Link
            href="/settings"
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            返回设置
          </Link>
        }
      />

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <div className="flex gap-2">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <p>
            本页不展示 API Key、数据库密码、Cookie、Token、完整错误堆栈或普通用户私人正文。最近失败任务详情应在服务器发布检查中脱敏确认。
          </p>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-4 py-3">
          <h2 className="text-base font-semibold text-slate-950">私人测试版功能矩阵</h2>
        </div>
        <div className="divide-y divide-slate-100">
          {featureMatrix.map(([feature, state, reason]) => (
            <article key={feature} className="grid gap-3 p-4 md:grid-cols-[220px_120px_1fr] md:items-center">
              <p className="font-mono text-xs font-semibold text-slate-900">{feature}</p>
              <Pill state={state}>{state}</Pill>
              <p className="text-sm leading-6 text-slate-600">{reason}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-base font-semibold text-slate-950">发布检查入口</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Linux 服务器上运行 <code className="rounded bg-slate-100 px-1 py-0.5">python -m app.cli.release_check</code> 读取生产配置、数据库迁移、管理员账户、Provider 授权和备份状态。
        </p>
      </section>
    </div>
  );
}

function Pill({ children, state }: { children: string; state: string }) {
  const tone = state === "已开启" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : state === "关闭" ? "border-slate-200 bg-slate-50 text-slate-700" : "border-amber-200 bg-amber-50 text-amber-800";
  return <span className={`inline-flex w-fit rounded-md border px-2 py-0.5 text-[11px] font-semibold ${tone}`}>{children}</span>;
}
