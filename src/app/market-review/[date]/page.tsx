"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/layout/PageHeader";
import { MarketReviewDetail } from "@/components/market-review/MarketReviewDetail";
import { EmptyState } from "@/components/status/EmptyState";
import { useMockState } from "@/lib/mock-state";

export default function MarketReviewPage() {
  const params = useParams<{ date: string }>();
  const { data } = useMockState();
  const review = data.marketDailyReview;

  if (params.date !== review.date) {
    return (
      <div className="space-y-5">
        <PageHeader title="全市场复盘" description="当前Mock场景只提供一个交易日的市场复盘样本。" />
        <EmptyState
          title="没有找到该日期的市场复盘"
          description="请返回今日页或复盘历史页选择可用的Mock日期。"
          action={
            <Link
              href="/today"
              className="focus-ring inline-flex h-10 items-center justify-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
            >
              返回今日页
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="全市场复盘"
        title={`${review.date} 市场复盘`}
        description="本页验证全市场宽度、板块热度、次日观察候选、数据能力限制和AI摘要分层展示。"
        actions={
          <Link
            href="/today"
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            返回今日
          </Link>
        }
      />
      <MarketReviewDetail review={review} />
    </div>
  );
}
