"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  BarChart3,
  BookOpenText,
  ClipboardCheck,
  FileClock,
  Layers3,
  MessageSquare,
  NotebookPen
} from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import { getStockMarketSnapshot } from "@/lib/api/market-data";
import type { DecimalValue, StockMarketSnapshot, WatchlistItemRead } from "@/lib/api/types";
import { listWatchlistItems } from "@/lib/api/watchlist";

const boardLabels: Record<string, string> = {
  main_board: "主板",
  star_board: "科创板",
  chinext: "创业板",
  bse: "北交所",
  unknown: "未知板块"
};

const exchangeLabels: Record<string, string> = {
  SH: "上交所",
  SZ: "深交所",
  BJ: "北交所"
};

const listingStatusLabels: Record<string, string> = {
  pending_listing: "待上市",
  active: "正常上市",
  suspended: "停牌",
  risk_warning: "风险警示",
  delisting_period: "退市整理",
  delisted: "已退市",
  unknown: "状态未知"
};

export default function StockDetailPage() {
  const params = useParams<{ stockId: string }>();
  const [market, setMarket] = useState<StockMarketSnapshot | null>(null);
  const [watchlistItem, setWatchlistItem] = useState<WatchlistItemRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [snapshot, watchlistPage] = await Promise.all([
        getStockMarketSnapshot(params.stockId),
        listWatchlistItems({ limit: 100 })
      ]);
      setMarket(snapshot);
      setWatchlistItem(watchlistPage.items.find((item) => item.stock.id === snapshot.stock.id) ?? null);
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

  if (error || !market) {
    return (
      <div className="space-y-5">
        <PageHeader title="个股详情" description="无法读取当前股票详情。" />
        <ErrorState title="个股详情加载失败" description={error ?? "股票不存在或当前用户无权查看。"} />
      </div>
    );
  }

  const stock = market.stock;
  const snapshot = market.snapshot;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="个股详情"
        title={`${stock.short_name || stock.name} · ${stock.symbol}`}
        description="行情、K线、量化指标只展示后端已入库的真实数据；当前不会使用 Mock 图表或 AI 生成行情数字。"
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
            <p className="text-xs font-semibold text-slate-500">1. 股票身份、状态与最新价</p>
            <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="text-2xl font-semibold text-slate-950">{stock.short_name || stock.name}</h2>
              <span className="text-sm text-slate-500">{stock.symbol}</span>
              <span className="text-sm text-slate-500">{exchangeLabel(stock.exchange)}</span>
              <StatusPill value={listingStatusLabel(stock.listing_status)} tone={statusTone(stock.listing_status)} />
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              证券目录来源：{stock.source_code}；证券目录最近同步：
              {formatTime(stock.last_synced_at) ?? "暂无"}。
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:min-w-[520px]">
            <IdentityStat label="最新价" value={snapshot?.close ? formatDecimal(snapshot.close) : "暂无"} />
            <IdentityStat label="涨跌幅" value={formatChange(snapshot?.pct_change ?? null)} tone={changeTone(snapshot?.pct_change ?? null)} />
            <IdentityStat label="成交额" value={snapshot?.amount ? formatLargeNumber(snapshot.amount) : "暂无"} />
            <IdentityStat label="换手率" value={snapshot?.turnover_rate ? `${formatDecimal(snapshot.turnover_rate)}%` : "暂无"} />
          </div>
        </div>
        <div className={`mt-4 rounded-md border p-3 text-sm leading-6 ${marketStatusTone(market.status)}`}>
          {market.message} 最近完整交易日：{market.latest_completed_trade_date ?? "暂无"}；来源：
          {market.source_code ?? "暂无"}；授权状态：{market.authorization_status ?? "暂无"}。
          {market.source_code === "TUSHARE_PRO" ? " 开发验证来源，尚未确认公开展示授权。" : ""}
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<BarChart3 className="h-5 w-5 text-blue-700" />} title="2. 分时 / 日K图表" />
        <div className="mt-4">
          <EmptyState
            title="暂无真实历史走势数据"
            description="当前只接入日级行情快照契约，分时、日K和成交量图必须等待真实历史行情能力确认后再展示。页面不会补造模拟走势。"
          />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<BarChart3 className="h-5 w-5 text-slate-700" />} title="3. 量化概览" />
        {snapshot ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="开盘 / 最高 / 最低" value={`${valueOrNone(snapshot.open)} / ${valueOrNone(snapshot.high)} / ${valueOrNone(snapshot.low)}`} />
            <Metric label="昨收 / 收盘" value={`${valueOrNone(snapshot.pre_close)} / ${valueOrNone(snapshot.close)}`} />
            <Metric label="成交量" value={snapshot.volume ? formatLargeNumber(snapshot.volume) : "暂无"} />
            <Metric label="成交额" value={snapshot.amount ? formatLargeNumber(snapshot.amount) : "暂无"} />
            <Metric label="总市值" value={snapshot.total_market_value ? formatLargeNumber(snapshot.total_market_value) : "暂无"} />
            <Metric label="流通市值" value={snapshot.circulating_market_value ? formatLargeNumber(snapshot.circulating_market_value) : "暂无"} />
            <Metric label="PE TTM" value={valueOrNone(snapshot.pe_ttm)} />
            <Metric label="PB" value={valueOrNone(snapshot.pb)} />
          </div>
        ) : (
          <div className="mt-4">
            <EmptyState title="暂无真实行情数据" description="无真实快照时不展示程序计算指标，也不由 AI 生成数值。" />
          </div>
        )}
        <p className="mt-3 text-xs leading-5 text-slate-500">
          以上字段为程序保存的行情快照，不是 AI 结论。单位：价格为元/股，涨跌幅为百分数，成交量为股，成交额和市值为人民币元。
        </p>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<Layers3 className="h-5 w-5 text-slate-700" />} title="4. 标准分类、系统建议和用户标签" />
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <TagPanel title="标准市场板块" values={[boardLabel(stock.board)]} />
          <TagPanel title="系统建议" values={["待真实分类任务补全"]} muted />
          <TagPanel title="用户标签" values={watchlistItem?.tags.map((tag) => tag.name) ?? []} />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <SectionTitle icon={<BookOpenText className="h-5 w-5 text-emerald-700" />} title="5. 用户关注逻辑摘要" />
        <p className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700">
          {watchlistItem?.attention_reason || "当前用户尚未填写关注原因。"}
        </p>
      </section>

      <PlaceholderSection title="6. 当日交易异动" icon={<ClipboardCheck className="h-5 w-5 text-rose-700" />} />
      <PlaceholderSection title="7. 公告与资讯时间线" icon={<FileClock className="h-5 w-5 text-blue-700" />} />
      <PlaceholderSection title="8. 舆情内容和博主观点" icon={<MessageSquare className="h-5 w-5 text-amber-700" />} />
      <PlaceholderSection title="9. 当日复盘" icon={<ClipboardCheck className="h-5 w-5 text-blue-700" />} />
      <PlaceholderSection title="10. 昨日观察条件及今日验证状态" icon={<ClipboardCheck className="h-5 w-5 text-slate-700" />} />
      <PlaceholderSection title="11. 历史复盘和修订版本摘要" icon={<FileClock className="h-5 w-5 text-slate-700" />} />
      <PlaceholderSection title="12. 用户笔记" icon={<NotebookPen className="h-5 w-5 text-emerald-700" />} />
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

function PlaceholderSection({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <SectionTitle icon={icon} title={title} />
      <div className="mt-4">
        <EmptyState title="待真实数据闭环补全" description="当前页面仅展示已有真实证券目录和行情快照，不使用 Mock 内容填充该模块。" />
      </div>
    </section>
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

function TagPanel({ title, values, muted = false }: { title: string; values: string[]; muted?: boolean }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p className="text-xs font-semibold text-slate-500">{title}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {values.length ? (
          values.map((value) => (
            <span
              key={value}
              className={`rounded-md border px-2 py-1 text-xs font-medium ${
                muted ? "border-slate-200 bg-white text-slate-500" : "border-slate-200 bg-white text-slate-700"
              }`}
            >
              {value}
            </span>
          ))
        ) : (
          <span className="text-xs text-slate-500">暂无</span>
        )}
      </div>
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
  return boardLabels[value] ?? value;
}

function exchangeLabel(value: string): string {
  return exchangeLabels[value] ?? value;
}

function listingStatusLabel(value: string): string {
  return listingStatusLabels[value] ?? value;
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
  if (value === "partial" || value === "stale") {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function valueOrNone(value: DecimalValue | null): string {
  return value === null ? "暂无" : formatDecimal(value);
}

function formatDecimal(value: DecimalValue): string {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value);
  }
  return numberValue.toFixed(2);
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

function formatLargeNumber(value: DecimalValue): string {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value);
  }
  if (Math.abs(numberValue) >= 100000000) {
    return `${(numberValue / 100000000).toFixed(2)}亿`;
  }
  if (Math.abs(numberValue) >= 10000) {
    return `${(numberValue / 10000).toFixed(2)}万`;
  }
  return numberValue.toFixed(2);
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
