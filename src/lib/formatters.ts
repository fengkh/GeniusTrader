import type {
  DataStatus,
  ObservationStatus,
  SourceKind,
  StockTradeStatus
} from "@/mock/types";

export function formatPercent(value: number | null): string {
  if (value === null) {
    return "暂无";
  }

  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatNumber(value: number | null): string {
  if (value === null) {
    return "暂无";
  }

  return value.toFixed(2);
}

export function trendTone(value: number | null): string {
  if (value === null) {
    return "text-slate-500";
  }

  if (value > 0) {
    return "text-red-600";
  }

  if (value < 0) {
    return "text-emerald-700";
  }

  return "text-slate-600";
}

export function statusLabel(status: DataStatus): string {
  const labels: Record<DataStatus, string> = {
    normal: "正常",
    syncing: "同步中",
    stale: "数据过期",
    "partial-failure": "部分失败",
    failure: "完全失败",
    empty: "空数据",
    "ai-failure": "AI失败"
  };

  return labels[status];
}

export function statusTone(status: DataStatus): string {
  const tones: Record<DataStatus, string> = {
    normal: "border-emerald-200 bg-emerald-50 text-emerald-800",
    syncing: "border-blue-200 bg-blue-50 text-blue-800",
    stale: "border-amber-200 bg-amber-50 text-amber-800",
    "partial-failure": "border-orange-200 bg-orange-50 text-orange-800",
    failure: "border-rose-200 bg-rose-50 text-rose-800",
    empty: "border-slate-200 bg-slate-50 text-slate-700",
    "ai-failure": "border-rose-200 bg-rose-50 text-rose-800"
  };

  return tones[status];
}

export function tradeStatusLabel(status: StockTradeStatus): string {
  const labels: Record<StockTradeStatus, string> = {
    normal: "正常交易",
    suspended: "停牌",
    stale: "行情过期",
    "partial-failure": "部分数据失败"
  };

  return labels[status];
}

export function sourceKindLabel(kind: SourceKind): string {
  const labels: Record<SourceKind, string> = {
    "official-disclosure": "正式公告",
    "authoritative-news": "权威资讯",
    "platform-opinion": "平台观点",
    "unverified-rumor": "未经核实传闻",
    "user-note": "用户补充"
  };

  return labels[kind];
}

export function sourceKindTone(kind: SourceKind): string {
  const tones: Record<SourceKind, string> = {
    "official-disclosure": "border-blue-200 bg-blue-50 text-blue-800",
    "authoritative-news": "border-sky-200 bg-sky-50 text-sky-800",
    "platform-opinion": "border-violet-200 bg-violet-50 text-violet-800",
    "unverified-rumor": "border-amber-200 bg-amber-50 text-amber-800",
    "user-note": "border-slate-200 bg-slate-50 text-slate-700"
  };

  return tones[kind];
}

export function observationStatusLabel(status: ObservationStatus): string {
  const labels: Record<ObservationStatus, string> = {
    occurred: "已发生",
    "not-occurred": "未发生",
    "partially-occurred": "部分发生",
    unknown: "无法判断",
    "not-applicable": "不再适用"
  };

  return labels[status];
}

export function observationStatusTone(status: ObservationStatus): string {
  const tones: Record<ObservationStatus, string> = {
    occurred: "border-emerald-200 bg-emerald-50 text-emerald-800",
    "not-occurred": "border-slate-200 bg-slate-50 text-slate-700",
    "partially-occurred": "border-blue-200 bg-blue-50 text-blue-800",
    unknown: "border-amber-200 bg-amber-50 text-amber-800",
    "not-applicable": "border-zinc-200 bg-zinc-50 text-zinc-600"
  };

  return tones[status];
}
