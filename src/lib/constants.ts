import { CalendarClock, Home, Inbox, MoreHorizontal, Settings, Star } from "lucide-react";

import type { NavigationItem, ScenarioOption } from "@/mock/types";

export const APP_NAME = "GeniusTrader";

export const MOCK_DISCLOSURE =
  "当前为 Mock 原型，所有行情、资讯、舆情与 AI 内容均为模拟数据，不代表实时行情或投资建议。";

export const DESKTOP_NAV_ITEMS: NavigationItem[] = [
  { href: "/today", label: "今日", icon: Home },
  { href: "/watchlist", label: "自选股", icon: Star },
  { href: "/information", label: "信息中心", icon: Inbox },
  { href: "/reviews", label: "复盘历史", icon: CalendarClock },
  { href: "/settings", label: "设置", icon: Settings }
];

export const MOBILE_NAV_ITEMS: NavigationItem[] = [
  { href: "/today", label: "今日", shortLabel: "今日", icon: Home },
  { href: "/watchlist", label: "自选股", shortLabel: "自选", icon: Star },
  { href: "/information", label: "信息中心", shortLabel: "信息", icon: Inbox },
  { href: "/reviews", label: "复盘历史", shortLabel: "复盘", icon: CalendarClock },
  { href: "/settings", label: "更多", shortLabel: "更多", icon: MoreHorizontal }
];

export const SCENARIOS: ScenarioOption[] = [
  {
    id: "normal",
    name: "正常",
    description: "多数数据正常，含上涨、下跌、停牌、公告、异动与复盘。"
  },
  {
    id: "stale",
    name: "数据过期",
    description: "行情快照停留在上一交易日，页面展示过期提醒。"
  },
  {
    id: "partial-failure",
    name: "部分失败",
    description: "部分股票或资讯源失败，其他模块继续展示。"
  },
  {
    id: "ai-failure",
    name: "AI失败",
    description: "AI复盘生成失败，确定性行情和公告仍可查看。"
  },
  {
    id: "empty-user",
    name: "空用户",
    description: "新用户没有自选股，展示引导和空状态。"
  },
  {
    id: "admin",
    name: "管理员",
    description: "切换为管理员展示身份，设置页显示管理员入口。"
  }
];
