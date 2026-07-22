import { AlertTriangle, Activity, GitCompareArrows } from "lucide-react";

import type { AbnormalEvent } from "@/mock/types";

const severityTone = {
  high: "border-rose-200 bg-rose-50 text-rose-900",
  medium: "border-orange-200 bg-orange-50 text-orange-900",
  low: "border-blue-200 bg-blue-50 text-blue-900"
};

const categoryLabel = {
  "official-fixed": "官方和固定规则",
  "historical-percentile": "历史分位规则",
  relative: "相对规则"
};

export function AbnormalEventCard({ event }: { event: AbnormalEvent }) {
  return (
    <article className={`rounded-lg border p-4 ${severityTone[event.severity]}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold">{categoryLabel[event.ruleCategory]}</p>
          <h3 className="mt-1 text-base font-semibold">
            {event.stockName}：{event.type}
          </h3>
        </div>
        <AlertTriangle className="h-5 w-5 shrink-0" />
      </div>
      <div className="mt-3 space-y-2 text-sm leading-6">
        <p className="flex gap-2">
          <Activity className="mt-1 h-4 w-4 shrink-0" />
          <span>触发依据：{event.evidence}</span>
        </p>
        <p className="flex gap-2">
          <GitCompareArrows className="mt-1 h-4 w-4 shrink-0" />
          <span>对比基准：{event.benchmark}</span>
        </p>
        <p>实际数据：{event.actualData}</p>
        <p className="text-xs">
          规则版本：{event.ruleVersion}；数据时间：{event.dataTime}
        </p>
      </div>
    </article>
  );
}
