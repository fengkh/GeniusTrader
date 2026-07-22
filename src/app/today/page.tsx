"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AlertCircle, ClipboardList, FileText, Layers3, MessageSquareWarning } from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { AbnormalEventCard } from "@/components/market/AbnormalEventCard";
import { InfoTimeline } from "@/components/information/InfoTimeline";
import { ReviewSummaryCard } from "@/components/review/ReviewSummaryCard";
import { DataStatusBar } from "@/components/status/DataStatusBar";
import { EmptyState } from "@/components/status/EmptyState";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import { formatPercent, observationStatusLabel, observationStatusTone, trendTone } from "@/lib/formatters";
import { useMockState } from "@/lib/mock-state";

export default function TodayPage() {
  const { data } = useMockState();
  const summary = data.dashboardSummary;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="今日复盘台"
        title="今日"
        description="先看客观行情、异动和重大信息，再查看舆情变化与AI整体复盘。所有内容均为模拟数据。"
      />

      <DataStatusBar
        tradeDate={data.tradeDate}
        generatedAt={data.generatedAt}
        sources={data.sourceStatuses}
      />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs font-semibold text-slate-500">自选股整体表现</p>
            <h2 className="mt-1 text-lg font-semibold text-slate-950">个人自选股池概览</h2>
          </div>
          <SimulatedDataBadge compact />
        </div>
        {summary.total === 0 ? (
          <EmptyState
            title="暂无自选股"
            description="新用户还没有自选股，今日页无法生成整体表现。请先进入自选股页添加或查看CSV导入说明。"
            action={
              <Link
                href="/watchlist"
                className="focus-ring inline-flex h-10 items-center justify-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-800"
              >
                去自选股页
              </Link>
            }
          />
        ) : (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <MetricCard label="自选股总数" value={`${summary.total}只`} />
            <MetricCard label="上涨" value={`${summary.rising}只`} tone="text-red-600" />
            <MetricCard label="下跌" value={`${summary.falling}只`} tone="text-emerald-700" />
            <MetricCard label="停牌" value={`${summary.suspended}只`} />
            <MetricCard label="数据异常" value={`${summary.dataIssues}只`} tone="text-orange-700" />
            <MetricCard
              label="平均表现"
              value={formatPercent(summary.averageChange)}
              tone={trendTone(summary.averageChange)}
            />
          </div>
        )}
      </section>

      <section id="abnormal" className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle
          icon={<AlertCircle className="h-5 w-5 text-rose-700" />}
          title="今日重大异动"
          actionLabel="异动聚合视图（下一阶段完善）"
        />
        {data.majorAbnormalEvents.length === 0 ? (
          <EmptyState title="暂无重大异动" description="当前Mock场景下没有触发预设异动规则。" />
        ) : (
          <div className="mt-4 grid gap-3 lg:grid-cols-3">
            {data.majorAbnormalEvents.map((event) => (
              <AbnormalEventCard key={event.id} event={event} />
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle
          icon={<FileText className="h-5 w-5 text-blue-700" />}
          title="重大公告与重要资讯"
        />
        <div className="mt-4">
          {data.majorInfoItems.length === 0 ? (
            <EmptyState title="暂无公告与资讯" description="当前Mock场景下没有收录关联公告或资讯。" />
          ) : (
            <InfoTimeline items={data.majorInfoItems} />
          )}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle
          icon={<Layers3 className="h-5 w-5 text-slate-700" />}
          title="板块和个人分组表现"
        />
        {data.groupPerformance.length === 0 ? (
          <EmptyState title="暂无分组表现" description="添加自选股后会展示标准板块与个人分组表现。" />
        ) : (
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {data.groupPerformance.map((group) => (
              <article key={group.name} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-semibold text-slate-500">
                  {group.kind === "sector" ? "标准板块" : "个人分组"}
                </p>
                <div className="mt-2 flex items-end justify-between gap-3">
                  <h3 className="text-base font-semibold text-slate-950">{group.name}</h3>
                  <span className={`text-lg font-semibold ${trendTone(group.averageChange)}`}>
                    {formatPercent(group.averageChange)}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-slate-600">{group.highlight}</p>
                <p className="mt-2 text-xs text-slate-500">覆盖股票：{group.stockCount}只</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle
          icon={<MessageSquareWarning className="h-5 w-5 text-amber-700" />}
          title="舆情变化与待核实信息"
        />
        {data.sentimentChanges.length === 0 ? (
          <EmptyState title="暂无舆情变化" description="用户录入链接或补充文本后会在此显示主题、情绪和可信度辅助分析。" />
        ) : (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {data.sentimentChanges.map((item) => (
              <article key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700">
                    {item.platform}
                  </span>
                  <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800">
                    待核实
                  </span>
                </div>
                <h3 className="mt-2 text-base font-semibold text-slate-950">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">{item.summary}</p>
                <p className="mt-2 text-xs text-slate-500">
                  {item.author}；{item.heatChange}；采集：{item.collectedAt}
                </p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle
          icon={<ClipboardList className="h-5 w-5 text-blue-700" />}
          title="今日整体复盘"
        />
        <div className="mt-4">
          <ReviewSummaryCard review={data.overallReview} />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle
          icon={<ClipboardList className="h-5 w-5 text-slate-700" />}
          title="待处理舆情和未完成复盘"
        />
        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_1.2fr]">
          <div className="space-y-3">
            {data.pendingTasks.map((task) => (
              <Link
                key={task.id}
                href={task.targetHref}
                className="focus-ring flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-4 hover:bg-slate-100"
              >
                <div>
                  <p className="font-semibold text-slate-950">{task.label}</p>
                  <p className="mt-1 text-sm text-slate-500">点击进入相关页面继续处理</p>
                </div>
                <div className="flex items-center gap-2">
                  <StatusTag status={task.status} />
                  <span className="text-lg font-semibold text-slate-950">{task.count}</span>
                </div>
              </Link>
            ))}
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h3 className="text-sm font-semibold text-slate-950">昨日观察条件验证</h3>
            {data.observationsForToday.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">暂无待验证观察条件。</p>
            ) : (
              <div className="mt-3 space-y-2">
                {data.observationsForToday.map((item) => (
                  <div key={item.id} className="rounded-md bg-white p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-md border px-2 py-1 text-xs font-medium ${observationStatusTone(
                          item.status
                        )}`}
                      >
                        {observationStatusLabel(item.status)}
                      </span>
                      <span className="text-xs text-slate-500">{item.stockName}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-700">{item.content}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  tone = "text-slate-950"
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function SectionTitle({
  icon,
  title,
  actionLabel
}: {
  icon: ReactNode;
  title: string;
  actionLabel?: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        {icon}
        <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
      </div>
      {actionLabel ? (
        <a
          href="#abnormal"
          className="focus-ring inline-flex h-9 items-center justify-center rounded-md border border-slate-300 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          {actionLabel}
        </a>
      ) : null}
    </div>
  );
}
