"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import {
  ArrowLeft,
  BookOpenText,
  ClipboardCheck,
  FileClock,
  FilePenLine,
  Layers3,
  MessageSquare,
  NotebookPen,
  RotateCcw
} from "lucide-react";

import { InfoTimeline } from "@/components/information/InfoTimeline";
import { PageHeader } from "@/components/layout/PageHeader";
import { AbnormalEventCard } from "@/components/market/AbnormalEventCard";
import { QuantOverview } from "@/components/market/QuantOverview";
import { StockChartPanel } from "@/components/market/StockChartPanel";
import { ReviewSummaryCard } from "@/components/review/ReviewSummaryCard";
import { EmptyState } from "@/components/status/EmptyState";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import { ValuationCenter } from "@/components/valuation/ValuationCenter";
import {
  formatNumber,
  formatPercent,
  observationStatusLabel,
  observationStatusTone,
  sourceKindLabel,
  sourceKindTone,
  tradeStatusLabel,
  trendTone
} from "@/lib/formatters";
import { useMockState } from "@/lib/mock-state";
import type { BoardTag, Stock } from "@/mock/types";

export default function StockDetailPage() {
  const params = useParams<{ stockId: string }>();
  const { data, findStock } = useMockState();
  const stock = findStock(params.stockId);

  if (!stock) {
    return (
      <div className="space-y-5">
        <PageHeader title="个股详情" description="当前Mock场景没有找到对应股票。" />
        <EmptyState
          title="股票不存在或当前用户无自选股"
          description="请返回自选股页选择一个可用的Mock股票。"
          action={
            <Link
              href="/watchlist"
              className="focus-ring inline-flex h-10 items-center justify-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
            >
              返回自选股
            </Link>
          }
        />
      </div>
    );
  }

  const observations =
    data.observationsForToday.length >= 5 ? data.observationsForToday : stock.observations;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="个股详情"
        title={`${stock.name} · ${stock.code}`}
        description="顶部优先展示股票身份、价格表现、分时/日K和程序计算指标；AI复盘位于客观行情、异动与外部事实之后。"
        actions={
          <Link
            href="/watchlist"
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            <ArrowLeft className="h-4 w-4" />
            返回自选股
          </Link>
        }
      />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-500">1. 股票身份、状态与最新价格</p>
            <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="text-2xl font-semibold text-slate-950">{stock.name}</h2>
              <span className="text-sm text-slate-500">{stock.code}</span>
              <span className="text-sm text-slate-500">{stock.market}</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusTag status={stock.marketSnapshot.status} label={tradeStatusLabel(stock.tradeStatus)} />
              <SimulatedDataBadge />
              <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
                数据时间 {stock.marketSnapshot.dataTime}
              </span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[520px]">
            <IdentityStat label="最新价" value={formatNumber(stock.marketSnapshot.close)} />
            <IdentityStat
              label="涨跌幅"
              value={changeText(stock)}
              tone={trendTone(stock.marketSnapshot.changePercent)}
            />
            <IdentityStat label="成交额" value={stock.marketSnapshot.turnoverAmount ?? "暂无"} />
            <IdentityStat
              label="换手率"
              value={
                stock.marketSnapshot.turnoverRate === null
                  ? "暂无"
                  : `${stock.marketSnapshot.turnoverRate.toFixed(2)}%`
              }
            />
          </div>
        </div>
        {stock.marketSnapshot.statusMessage ? (
          <p className="mt-4 rounded-md bg-amber-50 p-3 text-sm leading-6 text-amber-800">
            {stock.marketSnapshot.statusMessage}
          </p>
        ) : null}
      </section>

      <StockChartPanel stock={stock} />

      <QuantOverview metrics={stock.quantMetrics} />

      <ValuationCenter stock={stock} />

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<Layers3 className="h-5 w-5 text-slate-700" />} title="5. 标准分类、系统建议和用户标签" />
        <p className="mt-1 text-xs leading-5 text-slate-500">
          分类信息位于行情图表之后；标准板块、动态题材和用户标签分开展示，不混为同一字段。
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <BoardTagGroup title="标准行业板块" tags={stock.standardIndustries} />
          <BoardTagGroup title="标准概念板块" tags={stock.conceptBoards} />
          <BoardTagGroup title="动态市场题材 / 系统建议" tags={stock.dynamicThemes} empty="暂无动态题材" />
          <UserTagGroup stock={stock} />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<BookOpenText className="h-5 w-5 text-emerald-700" />} title="6. 用户关注逻辑摘要" />
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold text-slate-500">用户关注原因</p>
            <p className="mt-2 text-sm leading-6 text-slate-800">{stock.focusReason}</p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-semibold text-slate-500">关注逻辑变化</p>
            <p className="mt-2 text-sm leading-6 text-slate-800">{stock.focusLogicChange}</p>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<ClipboardCheck className="h-5 w-5 text-rose-700" />} title="7. 当日交易异动" />
        {stock.abnormalEvents.length === 0 ? (
          <div className="mt-4">
            <EmptyState title="暂无当日交易异动" description="没有触发当前Mock规则版本的异动事件。" />
          </div>
        ) : (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {stock.abnormalEvents.map((event) => (
              <AbnormalEventCard key={event.id} event={event} />
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<FileClock className="h-5 w-5 text-blue-700" />} title="8. 公告与资讯时间线" />
        <div className="mt-4">
          <InfoTimeline items={stock.infoTimeline} />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<MessageSquare className="h-5 w-5 text-amber-700" />} title="9. 舆情内容和博主观点" />
        {stock.sentimentItems.length === 0 ? (
          <div className="mt-4">
            <EmptyState title="暂无舆情内容" description="用户录入链接或补充文本后会展示平台观点和待核实信息。" />
          </div>
        ) : (
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {stock.sentimentItems.map((item) => (
              <article key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-md border px-2 py-1 text-xs font-medium ${sourceKindTone(
                      item.sourceKind
                    )}`}
                  >
                    {sourceKindLabel(item.sourceKind)}
                  </span>
                  <span className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700">
                    {item.platform} · {item.author}
                  </span>
                </div>
                <h3 className="mt-2 text-base font-semibold text-slate-950">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">{item.summary}</p>
                <p className="mt-2 text-xs text-slate-500">
                  {item.heatChange}；采集：{item.collectedAt}
                </p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<ClipboardCheck className="h-5 w-5 text-blue-700" />} title="10. 当日复盘" />
        <div className="mt-4">
          <ReviewSummaryCard review={stock.todayReview} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
            type="button"
          >
            <RotateCcw className="h-4 w-4" />
            重新生成
          </button>
          <button
            className="focus-ring inline-flex h-9 items-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-medium text-white hover:bg-slate-800"
            type="button"
          >
            <FilePenLine className="h-4 w-4" />
            人工编辑
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">按钮仅展示流程入口，本轮不实现真实AI或保存。</p>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<ClipboardCheck className="h-5 w-5 text-slate-700" />} title="11. 昨日观察条件及今日验证状态" />
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {observations.map((item) => (
            <article key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-md border px-2 py-1 text-xs font-medium ${observationStatusTone(
                    item.status
                  )}`}
                >
                  {observationStatusLabel(item.status)}
                </span>
                <span className="text-xs text-slate-500">
                  {item.stockName ?? stock.name} · 来源复盘日 {item.reviewDate}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-800">{item.content}</p>
              <p className="mt-2 text-xs leading-5 text-slate-600">验证依据：{item.evidence}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<FileClock className="h-5 w-5 text-slate-700" />} title="12. 历史复盘和修订版本摘要" />
        {stock.reviewHistory.length === 0 ? (
          <div className="mt-4">
            <EmptyState title="暂无历史复盘" description="生成或手写复盘后会保留AI原始版本与人工修订版本。" />
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {stock.reviewHistory.map((version) => (
              <article key={version.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700">
                    {version.type === "ai-original" ? "AI原始版本" : "人工修订版本"}
                  </span>
                  <span className="text-xs text-slate-500">{version.date}</span>
                </div>
                <h3 className="mt-2 text-sm font-semibold text-slate-950">{version.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-700">{version.summary}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<NotebookPen className="h-5 w-5 text-emerald-700" />} title="13. 用户笔记" />
        <div className="mt-4 space-y-3">
          {stock.userNotes.map((note) => (
            <p
              key={note}
              className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm leading-6 text-emerald-900"
            >
              {note}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}

function SectionTitle({
  icon,
  title
}: {
  icon: ReactNode;
  title: string;
}) {
  return (
    <div className="flex items-center gap-2">
      {icon}
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
    </div>
  );
}

function IdentityStat({
  label,
  value,
  tone = "text-slate-900"
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function BoardTagGroup({
  title,
  tags,
  empty = "暂无"
}: {
  title: string;
  tags: BoardTag[];
  empty?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">{title}</p>
      {tags.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">{empty}</p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span
              key={`${tag.type}-${tag.name}`}
              title={`${tag.source}；更新：${tag.updatedAt}`}
              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-700"
            >
              {tag.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function UserTagGroup({ stock }: { stock: Stock }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">用户标签</p>
      {stock.userTags.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">暂无用户标签</p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {stock.userTags.map((tag) => (
            <span
              key={tag.label}
              className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800"
            >
              {tag.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function changeText(stock: Stock): string {
  const value = stock.marketSnapshot.changePercent;

  if (value === null) {
    return "暂无涨跌";
  }

  const word = value > 0 ? "上涨" : value < 0 ? "下跌" : "持平";
  return `${formatPercent(value)} ${word}`;
}
