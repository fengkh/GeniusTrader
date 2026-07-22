import { RefreshCcw } from "lucide-react";

import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import type { DataSourceStatus } from "@/mock/types";

export function DataStatusBar({
  tradeDate,
  generatedAt,
  sources
}: {
  tradeDate: string;
  generatedAt: string;
  sources: DataSourceStatus[];
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <SimulatedDataBadge />
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              数据日期：{tradeDate}
            </span>
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
              最后更新时间：{generatedAt}
            </span>
          </div>
          <p className="text-sm text-slate-600">
            页面打开或手动刷新只展示最新可用 Mock 快照，不承诺分钟刷新或实时行情。
          </p>
        </div>
        <button className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">
          <RefreshCcw className="h-4 w-4" />
          手动刷新
        </button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {sources.map((source) => (
          <div key={source.label} className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-slate-900">{source.label}</p>
              <StatusTag status={source.status} />
            </div>
            <p className="mt-2 text-xs text-slate-500">来源：{source.source}</p>
            <p className="mt-1 text-xs text-slate-500">更新：{source.updatedAt}</p>
            <p className="mt-2 text-xs leading-5 text-slate-600">{source.message}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
