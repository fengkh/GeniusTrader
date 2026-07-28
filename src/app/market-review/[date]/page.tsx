import Link from "next/link";
import { ArrowLeft, ShieldAlert } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";

export default function MarketReviewUnavailablePage() {
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="功能未上线"
        title="全市场复盘暂未开放"
        description="当前可上线私人测试版只包含用户自选股、公告资讯、AI分析、每日复盘和通知闭环；未获授权的全市场行情和估值功能保持关闭。"
        actions={
          <Link
            href="/reviews"
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            返回复盘历史
          </Link>
        }
      />

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <div className="flex gap-2">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <p>
            这里不展示 Mock 指数、随机涨跌、模拟板块宽度、估值区间或 AI 生成的行情数字。后续只有在真实数据源、授权边界和验收口径确认后，才会重新开放相关页面。
          </p>
        </div>
      </section>

      <EmptyState
        title="暂无经授权的真实全市场行情数据"
        description="本阶段请继续使用“我的每日复盘”查看当前用户自己的信息聚合和 AI 复盘版本。"
        action={
          <Link
            href="/reviews"
            className="focus-ring inline-flex h-10 items-center justify-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800"
          >
            查看我的每日复盘
          </Link>
        }
      />
    </div>
  );
}
