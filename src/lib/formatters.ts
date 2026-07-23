import type {
  BoardStage,
  CapabilityStatus,
  DataStatus,
  MarketReviewStatus,
  NotificationFrequency,
  NotificationSeverity,
  NotificationState,
  NotificationType,
  ObservationStatus,
  SourceKind,
  StockTradeStatus,
  ValuationAvailability,
  ValuationConfidence
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

export function boardStageLabel(stage: BoardStage | "stock-observation"): string {
  const labels: Record<BoardStage | "stock-observation", string> = {
    "new-start": "新启动",
    accelerating: "加速",
    "sustained-strong": "持续强势",
    "high-divergence": "高位分化",
    retreat: "退潮",
    repair: "修复",
    "insufficient-data": "数据不足",
    "stock-observation": "个股观察"
  };

  return labels[stage];
}

export function capabilityStatusLabel(status: CapabilityStatus): string {
  const labels: Record<CapabilityStatus, string> = {
    complete: "完整",
    "partial-available": "部分可用",
    "sample-calculation": "样本计算",
    "provider-degraded": "数据源降级",
    empty: "暂无数据"
  };

  return labels[status];
}

export function marketReviewStatusLabel(status: MarketReviewStatus): string {
  const labels: Record<MarketReviewStatus, string> = {
    complete: "完整复盘",
    partial: "部分数据复盘",
    "provider-degraded": "数据源降级",
    "ai-summary-failed": "AI摘要失败",
    failed: "复盘生成失败",
    "not-generated": "尚未生成"
  };

  return labels[status];
}

export function notificationSeverityLabel(severity: NotificationSeverity): string {
  const labels: Record<NotificationSeverity, string> = {
    info: "普通",
    notice: "提醒",
    important: "重要",
    critical: "严重"
  };

  return labels[severity];
}

export function notificationSeverityTone(severity: NotificationSeverity): string {
  const tones: Record<NotificationSeverity, string> = {
    info: "border-slate-200 bg-slate-50 text-slate-700",
    notice: "border-blue-200 bg-blue-50 text-blue-800",
    important: "border-amber-200 bg-amber-50 text-amber-800",
    critical: "border-rose-200 bg-rose-50 text-rose-800"
  };

  return tones[severity];
}

export function notificationStateLabel(state: NotificationState): string {
  const labels: Record<NotificationState, string> = {
    unread: "未读",
    read: "已读",
    archived: "已归档",
    expired: "已过期",
    "data-source-degraded": "数据源降级",
    "ai-summary-failed": "AI摘要失败",
    "wechat-failed": "微信发送失败"
  };

  return labels[state];
}

export function notificationTypeLabel(type: NotificationType): string {
  const labels: Record<NotificationType, string> = {
    "daily-review": "每日复盘",
    announcement: "公告资讯",
    anomaly: "交易异动",
    observation: "观察条件",
    valuation: "估值",
    system: "系统"
  };

  return labels[type];
}

export function notificationFrequencyLabel(frequency: NotificationFrequency): string {
  const labels: Record<NotificationFrequency, string> = {
    immediate: "立即",
    "daily-digest": "每日摘要",
    "weekly-digest": "每周摘要",
    disabled: "关闭"
  };

  return labels[frequency];
}

export function valuationConfidenceLabel(confidence: ValuationConfidence): string {
  const labels: Record<ValuationConfidence, string> = {
    high: "高",
    medium: "中",
    low: "低",
    unavailable: "不可用"
  };

  return labels[confidence];
}

export function valuationAvailabilityLabel(availability: ValuationAvailability): string {
  const labels: Record<ValuationAvailability, string> = {
    available: "可用",
    partial: "部分可用",
    unavailable: "不可估",
    stale: "财务数据过期"
  };

  return labels[availability];
}
