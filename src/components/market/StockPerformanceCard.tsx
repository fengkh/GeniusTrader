import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import { formatPercent, tradeStatusLabel, trendTone } from "@/lib/formatters";
import type { Stock } from "@/mock/types";

export function StockPerformanceCard({ stock }: { stock: Stock }) {
  const change = stock.marketSnapshot.changePercent;
  const TrendIcon = change === null ? Minus : change >= 0 ? ArrowUpRight : ArrowDownRight;

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-base font-semibold text-slate-950">{stock.name}</h3>
            <span className="text-xs text-slate-500">{stock.code}</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">{stock.market}</p>
        </div>
        <StatusTag status={stock.marketSnapshot.status} label={tradeStatusLabel(stock.tradeStatus)} />
      </div>

      <div className="mt-4 flex items-end justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-slate-500">当日表现</p>
          <div className={`mt-1 flex items-center gap-1 text-2xl font-semibold ${trendTone(change)}`}>
            <TrendIcon className="h-5 w-5" />
            {formatPercent(change)}
          </div>
        </div>
        <SimulatedDataBadge compact />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-slate-500">收盘价</dt>
          <dd className="font-medium text-slate-900">
            {stock.marketSnapshot.close ?? "暂无"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">换手率</dt>
          <dd className="font-medium text-slate-900">
            {stock.marketSnapshot.turnoverRate === null
              ? "暂无"
              : `${stock.marketSnapshot.turnoverRate.toFixed(2)}%`}
          </dd>
        </div>
      </dl>

      {stock.marketSnapshot.statusMessage ? (
        <p className="mt-3 rounded-md bg-amber-50 p-2 text-xs leading-5 text-amber-800">
          {stock.marketSnapshot.statusMessage}
        </p>
      ) : null}

      <Link
        href={`/watchlist/${stock.id}`}
        className="focus-ring mt-4 inline-flex h-9 items-center justify-center rounded-md border border-slate-300 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        进入个股详情
      </Link>
    </article>
  );
}
