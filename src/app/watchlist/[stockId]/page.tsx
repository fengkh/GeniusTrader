"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  BarChart3,
  BookOpenText,
  CheckSquare,
  Clock3,
  FileText,
  ListTodo,
  NotebookPen
} from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import { getStockMarketSnapshot } from "@/lib/api/market-data";
import type {
  DecimalValue,
  ResearchTask,
  StockDailySnapshot,
  StockMarketSnapshot,
  StockResearchDossier,
  TimelineEntry
} from "@/lib/api/types";
import { getStockResearchDossier } from "@/lib/api/workbench";

export default function StockDetailPage() {
  const params = useParams<{ stockId: string }>();
  const [dossier, setDossier] = useState<StockResearchDossier | null>(null);
  const [directSnapshot, setDirectSnapshot] = useState<StockDailySnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextDossier, latestSnapshot] = await Promise.all([
        getStockResearchDossier(params.stockId),
        getStockMarketSnapshot(params.stockId).catch(() => null)
      ]);
      setDossier(nextDossier);
      setDirectSnapshot(latestSnapshot?.snapshot ?? null);
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [params.stockId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  if (loading) {
    return <LoadingSkeleton lines={10} />;
  }

  if (error || !dossier) {
    return (
      <div className="space-y-5">
        <PageHeader title="个股研究档案" description="无法读取当前股票研究档案。" />
        <ErrorState title="个股研究档案加载失败" description={error ?? "股票不存在或当前用户无权查看。"} />
      </div>
    );
  }

  const stock = dossier.identity;
  const snapshot = dossier.market_snapshot.snapshot ?? directSnapshot;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="个股研究档案"
        title={`${stock.short_name || stock.name} · ${stock.symbol}`}
        description="围绕一只自选股聚合用户关注逻辑、官方信息、研究事项、观察条件和复盘历史；禁止 AI 生成行情数字。"
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
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-500">1. 股票身份和当前状态</p>
            <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="text-2xl font-semibold text-slate-950">{stock.short_name || stock.name}</h2>
              <span className="text-sm text-slate-500">{stock.symbol}</span>
              <span className="text-sm text-slate-500">{exchangeLabel(stock.exchange)}</span>
              <StatusPill value={listingStatusLabel(stock.listing_status)} tone={statusTone(stock.listing_status)} />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              标准板块：{boardLabel(stock.board)}；证券目录来源：{stock.source_code}；最近同步：
              {formatTime(stock.last_synced_at) ?? "暂无"}。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:min-w-[560px]">
            <IdentityStat label="最新价" value={hasValue(snapshot?.close) ? formatDecimal(snapshot.close) : "暂无"} />
            <IdentityStat label="涨跌幅" value={formatChange(snapshot?.pct_change ?? null)} tone={changeTone(snapshot?.pct_change ?? null)} />
            <IdentityStat label="待办" value={`${dossier.current_state.open_task_count}项`} />
            <IdentityStat label="观察条件" value={`${dossier.current_state.observation_count}项`} />
          </div>
        </div>
        <div className={`mt-4 rounded-md border p-3 text-sm leading-6 ${marketStatusTone(dossier.market_snapshot.status)}`}>
          {dossier.market_snapshot.message} 最近完整交易日：
          {dossier.market_snapshot.latest_completed_trade_date ?? "暂无"}；来源：
          {dossier.market_snapshot.source_code ?? "暂无"}。
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<BarChart3 className="h-5 w-5 text-blue-700" />} title="2. 真实日级行情快照" />
        <MarketSnapshotSection market={dossier.market_snapshot} snapshot={snapshot} />
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<BookOpenText className="h-5 w-5 text-emerald-700" />} title="3. 用户关注逻辑" />
        <div className="mt-4 grid gap-3 lg:grid-cols-[1.2fr_1fr]">
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
            {dossier.watchlist_profile.focus_reason || "当前用户尚未填写关注原因。"}
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <MiniPanel title="个人分组" value={dossier.watchlist_profile.group?.name ?? "未分组"} />
            <MiniPanel
              title="用户标签"
              value={dossier.watchlist_profile.tags.length ? dossier.watchlist_profile.tags.map((tag) => tag.name).join("；") : "暂无"}
            />
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<ListTodo className="h-5 w-5 text-blue-700" />} title="4. 当前研究状态" />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Metric label="新增信息" value={`${dossier.current_state.new_information_count}条`} />
          <Metric label="公告候选" value={`${dossier.current_state.pending_candidate_count}条`} />
          <Metric label="打开事项" value={`${dossier.current_state.open_task_count}项`} />
          <Metric label="复盘状态" value={reviewStatusLabel(dossier.current_state.latest_review_status)} />
          <Metric label="是否 stale" value={dossier.current_state.stale ? "需要更新" : "正常"} />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<FileText className="h-5 w-5 text-blue-700" />} title="5. 官方信息与公告候选" />
        {dossier.official_information.length === 0 ? (
          <EmptyBlock title="暂无官方信息" description="尚未导入或确认与该股票相关的公告、资讯或公告候选。" />
        ) : (
          <div className="mt-4 grid gap-2">
            {dossier.official_information.map((item) => (
              <Link
                key={item.id}
                href={item.target_url}
                className="focus-ring rounded-md border border-slate-200 bg-slate-50 p-3 text-sm hover:bg-white"
              >
                <p className="font-semibold text-slate-950">{item.title || "未命名信息"}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {item.source_type} · {item.status} · {formatTime(item.created_at) ?? item.created_at}
                  {item.is_important ? " · 重要" : ""}
                </p>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<ListTodo className="h-5 w-5 text-amber-700" />} title="6. 研究事项与观察条件" />
        {dossier.research_tasks.length === 0 ? (
          <EmptyBlock title="暂无研究事项" description="可在任务中心创建，或从 AI 分析和复盘建议中显式采纳。" />
        ) : (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {dossier.research_tasks.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        )}
        <Link
          href={`/information/tasks?stock_id=${stock.id}`}
          className="focus-ring mt-4 inline-flex h-9 items-center rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800"
        >
          进入任务中心
        </Link>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<Clock3 className="h-5 w-5 text-slate-700" />} title="7. 研究时间线" />
        {dossier.timeline.length === 0 ? (
          <EmptyBlock title="暂无时间线" description="信息、公告、复盘和研究事项更新后会进入该股票时间线。" />
        ) : (
          <div className="mt-4 space-y-3">
            {dossier.timeline.map((entry, index) => (
              <TimelineCard key={`${entry.event_type}-${entry.occurred_at}-${index}`} entry={entry} />
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<CheckSquare className="h-5 w-5 text-blue-700" />} title="8. 历史复盘" />
        {dossier.review_history.length === 0 ? (
          <EmptyBlock title="暂无复盘历史" description="生成每日复盘后，与该股票相关的版本会展示在这里。" />
        ) : (
          <div className="mt-4 grid gap-2">
            {dossier.review_history.map((review) => (
              <Link
                key={review.review_id}
                href={review.target_url}
                className="focus-ring rounded-md border border-slate-200 bg-slate-50 p-3 text-sm hover:bg-white"
              >
                <span className="font-semibold text-slate-950">{review.review_date}</span>
                <span className="ml-2 text-slate-600">{reviewStatusLabel(review.status)}</span>
                <span className="ml-2 text-slate-500">版本 {review.version_count}</span>
                {review.stale ? <span className="ml-2 text-amber-700">stale</span> : null}
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<NotebookPen className="h-5 w-5 text-emerald-700" />} title="9. 数据边界" />
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-600">
          {dossier.data_boundaries.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function SectionTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2">
      {icon}
      <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
    </div>
  );
}

function MarketSnapshotSection({
  market,
  snapshot
}: {
  market: StockMarketSnapshot;
  snapshot: StockDailySnapshot | null;
}) {
  return (
    <div className="mt-4 space-y-3">
      <div className={`rounded-md border p-3 text-sm leading-6 ${marketStatusTone(market.status)}`}>
        {market.message} 本区只展示单日程序入库快照，不展示分时、K 线、盘口、估值模型或 AI 推测数字。
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SnapshotMetric label="交易日" value={snapshot?.trade_date ?? "暂无"} />
        <SnapshotMetric label="来源" value={snapshot?.source_code ?? "暂无"} />
        <SnapshotMetric label="收盘价" value={hasValue(snapshot?.close) ? formatDecimal(snapshot.close) : "暂无"} />
        <SnapshotMetric label="昨收" value={hasValue(snapshot?.pre_close) ? formatDecimal(snapshot.pre_close) : "暂无"} />
        <SnapshotMetric label="涨跌额" value={hasValue(snapshot?.change) ? formatDecimal(snapshot.change) : "暂无"} />
        <SnapshotMetric label="涨跌幅" value={formatChange(snapshot?.pct_change ?? null)} tone={changeTone(snapshot?.pct_change ?? null)} />
        <SnapshotMetric label="开盘" value={hasValue(snapshot?.open) ? formatDecimal(snapshot.open) : "暂无"} />
        <SnapshotMetric
          label="最高 / 最低"
          value={`${hasValue(snapshot?.high) ? formatDecimal(snapshot.high) : "暂无"} / ${hasValue(snapshot?.low) ? formatDecimal(snapshot.low) : "暂无"}`}
        />
        <SnapshotMetric label="成交量" value={hasValue(snapshot?.volume) ? formatCompactNumber(snapshot.volume) : "暂无"} />
        <SnapshotMetric label="成交额" value={hasValue(snapshot?.amount) ? formatCompactNumber(snapshot.amount) : "暂无"} />
        <SnapshotMetric label="换手率" value={hasValue(snapshot?.turnover_rate) ? `${formatDecimal(snapshot.turnover_rate)}%` : "暂无"} />
        <SnapshotMetric label="总市值" value={hasValue(snapshot?.total_market_value) ? formatCompactNumber(snapshot.total_market_value) : "暂无"} />
        <SnapshotMetric label="流通市值" value={hasValue(snapshot?.circulating_market_value) ? formatCompactNumber(snapshot.circulating_market_value) : "暂无"} />
        <SnapshotMetric label="PE TTM" value={hasValue(snapshot?.pe_ttm) ? formatDecimal(snapshot.pe_ttm) : "暂无"} />
        <SnapshotMetric label="PB" value={hasValue(snapshot?.pb) ? formatDecimal(snapshot.pb) : "暂无"} />
        <SnapshotMetric label="更新时间" value={formatTime(snapshot?.source_updated_at ?? snapshot?.fetched_at ?? null) ?? "暂无"} />
      </div>
      <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-600">
        <p>
          完整度：{market.data_completeness ?? snapshot?.data_completeness ?? "暂无"}；新鲜度：
          {marketStatusLabel(market.status)}；最近完整交易日：{market.latest_completed_trade_date ?? "暂无"}。
        </p>
        <p className="mt-1">缺失字段：{market.missing_fields.length ? market.missing_fields.join("、") : "无"}。</p>
      </div>
    </div>
  );
}

function TaskCard({ task }: { task: ResearchTask }) {
  return (
    <Link
      href={`/information/tasks?task=${task.id}`}
      className="focus-ring rounded-md border border-slate-200 bg-slate-50 p-3 text-sm leading-6 hover:bg-white"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-slate-950">{task.title}</span>
        <StatusPill value={taskStatusLabel(task.status)} tone={task.status === "pending" || task.status === "monitoring" ? "amber" : "emerald"} />
        <StatusPill value={task.priority} tone={task.priority === "high" ? "rose" : "slate"} />
      </div>
      <p className="mt-1 line-clamp-2 text-slate-600">{task.description}</p>
      <p className="mt-1 text-xs text-slate-500">到期：{task.due_date ?? "未设置"}；来源：{task.source_type}</p>
    </Link>
  );
}

function TimelineCard({ entry }: { entry: TimelineEntry }) {
  return (
    <Link
      href={entry.target_url}
      className="focus-ring block rounded-md border border-slate-200 bg-slate-50 p-3 text-sm leading-6 hover:bg-white"
    >
      <p className="font-semibold text-slate-950">{entry.title}</p>
      <p className="mt-1 text-slate-600">{entry.summary}</p>
      <p className="mt-1 text-xs text-slate-500">
        {formatTime(entry.occurred_at) ?? entry.occurred_at} · {entry.source_label}
        {entry.confidence ? ` · ${entry.confidence}` : ""}
      </p>
    </Link>
  );
}

function EmptyBlock({ title, description }: { title: string; description: string }) {
  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-600">{description}</p>
    </div>
  );
}

function IdentityStat({ label, value, tone = "text-slate-900" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function SnapshotMetric({ label, value, tone = "text-slate-950" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${tone}`}>{value}</p>
    </div>
  );
}

function MiniPanel({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">{title}</p>
      <p className="mt-1 text-sm font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function StatusPill({ value, tone }: { value: string; tone: "slate" | "emerald" | "amber" | "rose" }) {
  const tones = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    rose: "border-rose-200 bg-rose-50 text-rose-800"
  };
  return <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}>{value}</span>;
}

function boardLabel(value: string): string {
  const labels: Record<string, string> = {
    main_board: "主板",
    star_board: "科创板",
    chinext: "创业板",
    bse: "北交所",
    unknown: "未知板块"
  };
  return labels[value] ?? value;
}

function exchangeLabel(value: string): string {
  const labels: Record<string, string> = {
    SH: "上交所",
    SZ: "深交所",
    BJ: "北交所"
  };
  return labels[value] ?? value;
}

function listingStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    pending_listing: "待上市",
    active: "正常上市",
    suspended: "停牌",
    risk_warning: "风险警示",
    delisting_period: "退市整理",
    delisted: "已退市",
    unknown: "状态未知"
  };
  return labels[value] ?? value;
}

function statusTone(value: string): "slate" | "emerald" | "amber" | "rose" {
  if (value === "active") {
    return "emerald";
  }
  if (value === "suspended" || value === "risk_warning" || value === "pending_listing") {
    return "amber";
  }
  if (value === "delisted" || value === "delisting_period") {
    return "rose";
  }
  return "slate";
}

function marketStatusTone(value: string): string {
  if (value === "available") {
    return "border-emerald-200 bg-emerald-50 text-emerald-900";
  }
  if (value === "partial" || value === "stale" || value === "source_lag") {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function marketStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    available: "可用",
    partial: "部分可用",
    source_lag: "来源滞后",
    stale: "过期",
    unavailable: "不可用"
  };
  return labels[value] ?? value;
}

function reviewStatusLabel(value: string | null): string {
  const labels: Record<string, string> = {
    complete: "完整",
    partial: "部分完成",
    empty: "空复盘",
    failed: "失败",
    stale: "需要更新"
  };
  return value ? labels[value] ?? value : "暂无";
}

function taskStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    pending: "待处理",
    monitoring: "跟踪中",
    confirmed: "已发生",
    disproved: "未发生",
    partially_confirmed: "部分发生",
    unable_to_determine: "无法判断",
    no_longer_applicable: "不再适用",
    dismissed: "已忽略"
  };
  return labels[value] ?? value;
}

function formatDecimal(value: DecimalValue): string {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value);
  }
  return numberValue.toFixed(2);
}

function formatCompactNumber(value: DecimalValue): string {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value);
  }
  const absValue = Math.abs(numberValue);
  if (absValue >= 100000000) {
    return `${(numberValue / 100000000).toFixed(2)}亿`;
  }
  if (absValue >= 10000) {
    return `${(numberValue / 10000).toFixed(2)}万`;
  }
  return numberValue.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function formatChange(value: DecimalValue | null): string {
  if (value === null) {
    return "暂无涨跌";
  }
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value);
  }
  const direction = numberValue > 0 ? "上涨" : numberValue < 0 ? "下跌" : "持平";
  const prefix = numberValue > 0 ? "+" : "";
  return `${prefix}${numberValue.toFixed(2)}% ${direction}`;
}

function changeTone(value: DecimalValue | null): string {
  if (value === null) {
    return "text-slate-500";
  }
  const numberValue = Number(value);
  if (numberValue > 0) {
    return "text-red-600";
  }
  if (numberValue < 0) {
    return "text-emerald-700";
  }
  return "text-slate-600";
}

function hasValue(value: DecimalValue | null | undefined): value is DecimalValue {
  return value !== null && value !== undefined && String(value) !== "";
}

function formatTime(value: string | null): string | null {
  if (!value) {
    return null;
  }
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  } catch {
    return value;
  }
}
