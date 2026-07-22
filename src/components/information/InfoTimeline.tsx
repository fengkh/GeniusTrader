import { ExternalLink } from "lucide-react";

import { StatusTag } from "@/components/status/StatusTag";
import { sourceKindLabel, sourceKindTone } from "@/lib/formatters";
import type { InfoItem } from "@/mock/types";

export function InfoTimeline({ items }: { items: InfoItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">暂无已收录公告或资讯。</p>;
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <article key={item.id} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-md border px-2 py-1 text-xs font-medium ${sourceKindTone(
                    item.sourceKind
                  )}`}
                >
                  {sourceKindLabel(item.sourceKind)}
                </span>
                <StatusTag status={item.status} />
              </div>
              <h3 className="mt-2 text-base font-semibold text-slate-950">{item.title}</h3>
            </div>
            <button className="focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">
              <ExternalLink className="h-4 w-4" />
              {item.linkLabel}
            </button>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-700">{item.summary}</p>
          <p className="mt-3 text-xs text-slate-500">
            来源：{item.sourceName}；发布时间：{item.publishedAt}；采集时间：{item.collectedAt}
          </p>
        </article>
      ))}
    </div>
  );
}
