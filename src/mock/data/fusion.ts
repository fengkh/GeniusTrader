import type {
  BusinessEventMock,
  ExternalIdentityMock,
  MarketDailyReview,
  NotificationDeliveryMock,
  NotificationMock,
  NotificationPreferenceMock,
  ReviewSummary,
  ScenarioId,
  StockValuation
} from "@/mock/types";

const tradeDate = "2026-07-22";
const generatedAt = "2026-07-22 16:08";

const marketAiSummary: ReviewSummary = {
  status: "success",
  title: "AI全市场复盘摘要（模拟）",
  summary:
    "程序计算显示样本市场宽度偏弱，但光伏设备和银行板块仍保持相对强度。AI仅解释程序结果和外部事实，不生成指数、排行、估值或候选数量。",
  modelName: "mock-openai-compatible-model",
  generatedAt,
  taskType: "全市场复盘摘要",
  isOriginalAiVersion: true,
  sourceLayers: ["程序计算", "正式公告", "权威资讯", "AI解释"]
};

const ruleMarketSummary: ReviewSummary = {
  ...marketAiSummary,
  status: "failed",
  title: "规则模板全市场摘要（AI失败回退）",
  summary:
    "AI摘要失败，页面使用规则模板展示程序计算结果：样本市场宽度偏弱，热点集中度提升，候选仅用于次日观察。",
  modelName: "未使用",
  isOriginalAiVersion: false,
  failureReason: "模拟错误：AI结构化输出校验失败。"
};

export function getValuationForStock(stockId: string, scenarioId: ScenarioId): StockValuation | undefined {
  const base = valuationByStockId[stockId];

  if (!base) {
    return undefined;
  }

  if (scenarioId === "stale" && stockId !== "gt-loss") {
    return {
      ...base,
      availability: base.availability === "unavailable" ? "unavailable" : "stale",
      confidence: base.confidence === "high" ? "medium" : base.confidence,
      dataStatus: "stale",
      valuationDate: "2026-07-21",
      dataTime: "2026-07-21 16:10",
      missingInputs: [...base.missingInputs, "财务数据已过期，真实口径待供应商确认"],
      explanation: `${base.explanation} 当前为过期财务样本，估值置信度已下调。`
    };
  }

  if (scenarioId === "partial-failure" && (stockId === "gt-material" || stockId === "gt-cloud")) {
    return {
      ...base,
      availability: "partial",
      confidence: "low",
      dataStatus: "partial-failure",
      ps: stockId === "gt-cloud" ? null : base.ps,
      pe: stockId === "gt-material" ? null : base.pe,
      scenarios: [],
      missingInputs: [
        ...base.missingInputs,
        stockId === "gt-cloud" ? "收入增速字段缺失" : "行业周期分位和可比公司倍数字段缺失"
      ],
      pricePosition: "暂不展示区间位置",
      explanation: "供应商字段部分失败，页面保留市场价格和已知财务字段，不补造估值区间。"
    };
  }

  if (scenarioId === "ai-failure") {
    return {
      ...base,
      explanation: `${base.explanation} AI解释失败时，估值区间和倍数仍来自程序计算，并使用规则模板说明。`
    };
  }

  return {
    ...base,
    scenarios: base.scenarios.map((item) => ({
      ...item,
      assumptions: [...item.assumptions]
    })),
    assumptions: [...base.assumptions],
    missingInputs: [...base.missingInputs]
  };
}

export function getMarketDailyReview(scenarioId: ScenarioId): MarketDailyReview {
  const review: MarketDailyReview = {
    id: `market-review-${tradeDate}`,
    date: tradeDate,
    status: "complete",
    capabilityStatus: "sample-calculation",
    generatedAt,
    dataStatus: "normal",
    dataSources: ["模拟行情快照", "模拟行业分类", "模拟公告资讯", "本地程序计算"],
    capabilityNotes: [
      "全市场字段来自本地确定性Mock，不代表真实行情。",
      "真实数据供应商、板块口径和指标阈值仍需在真实数据开发前确认。"
    ],
    overview: "样本市场宽度偏弱，热点集中在少数板块；次日候选仅作为观察清单，不构成交易建议。",
    breadth: {
      rising: 2206,
      falling: 3048,
      flat: 186,
      suspended: 64,
      limitUp: 54,
      limitDown: 18,
      medianChangePercent: -0.42,
      ma20AboveRatio: 44,
      totalAmount: "8,420亿元",
      amountChangePercent: 6.8,
      newHigh20: 132,
      newLow20: 89
    },
    indexPerformance: [
      {
        code: "000001.SH",
        name: "上证指数",
        changePercent: 0.28,
        amount: "3,120亿元",
        style: "大盘价值",
        note: "权重稳定，样本市场宽度一般。"
      },
      {
        code: "399006.SZ",
        name: "创业板指",
        changePercent: -0.74,
        amount: "1,580亿元",
        style: "成长风格",
        note: "成长股分化，量能未同步放大。"
      },
      {
        code: "000300.SH",
        name: "沪深300",
        changePercent: 0.16,
        amount: "2,760亿元",
        style: "核心资产",
        note: "相对平稳，用作个股强弱基准之一。"
      }
    ],
    hotBoards: boardHeatRecords,
    continuousStrongBoards: boardHeatRecords.filter((board) => board.stage === "sustained-strong"),
    retreatBoards: boardHeatRecords.filter((board) => board.stage === "retreat" || board.stage === "high-divergence"),
    boardCandidates,
    stockCandidates,
    aiSummary: marketAiSummary
  };

  if (scenarioId === "stale") {
    return {
      ...review,
      status: "partial",
      capabilityStatus: "provider-degraded",
      dataStatus: "stale",
      generatedAt: "2026-07-21 16:05",
      overview: "行情快照过期，仍展示上一交易日可用样本；次日候选仅保留观察意义。",
      capabilityNotes: [...review.capabilityNotes, "行情和部分板块热度停留在上一交易日。"],
      hotBoards: review.hotBoards.map((board) => ({
        ...board,
        dataStatus: "stale",
        dataCompleteness: "过期样本",
        dataGaps: [...board.dataGaps, "今日最新行情未确认"]
      }))
    };
  }

  if (scenarioId === "partial-failure") {
    return {
      ...review,
      status: "partial",
      capabilityStatus: "partial-available",
      dataStatus: "partial-failure",
      overview: "行业板块样本仍可用，概念板块和部分成交额字段缺失；候选排序已标记数据完整度。",
      capabilityNotes: [...review.capabilityNotes, "概念板块样本缺失，动态题材仅保留用户侧观察。"],
      hotBoards: review.hotBoards.map((board) =>
        board.type === "concept-board"
          ? {
              ...board,
              dataStatus: "partial-failure",
              amountPercentile: null,
              totalScore: null,
              dataCompleteness: "概念板块字段缺失",
              dataGaps: [...board.dataGaps, "概念成分股覆盖不足", "成交额分位暂不可算"]
            }
          : board
      )
    };
  }

  if (scenarioId === "ai-failure") {
    return {
      ...review,
      status: "ai-summary-failed",
      capabilityStatus: "sample-calculation",
      aiSummary: ruleMarketSummary,
      overview: "程序计算结果正常，AI摘要失败后使用规则模板说明。"
    };
  }

  if (scenarioId === "empty-user") {
    return {
      ...review,
      overview: "即使新用户没有自选股，市场复盘样本仍可查看；个人整体复盘需要先建立自选股。",
      stockCandidates: [],
      boardCandidates: review.boardCandidates.slice(0, 2)
    };
  }

  if (scenarioId === "admin") {
    return {
      ...review,
      capabilityNotes: [...review.capabilityNotes, "管理员Mock身份可见系统级数据源降级通知。"]
    };
  }

  return review;
}

export function getBusinessEvents(scenarioId: ScenarioId): BusinessEventMock[] {
  const base: BusinessEventMock[] = [
    event("evt-market-review", "market_daily_review.generated", "market-review", "全市场每日复盘", "notice", "daily-digest", true, true, true, "/market-review/2026-07-22"),
    event("evt-board-stage", "board.heat_state_changed", "market-review", "光伏设备", "notice", "daily-digest", true, true, true, "/market-review/2026-07-22"),
    event("evt-candidates", "watch_candidate.updated", "market-review", "次日观察候选", "notice", "daily-digest", true, true, true, "/market-review/2026-07-22"),
    event("evt-user-review", "user_daily_review.generated", "user-review", "我的自选股整体复盘", "notice", "daily-digest", true, true, true, "/today"),
    event("evt-announcement", "announcement.major_collected", "announcement-info", "澜海光伏重大合同公告", "important", "immediate", true, true, false, "/watchlist/gt-solar"),
    event("evt-anomaly", "watchlist.abnormal_event.detected", "watchlist-quote", "澜海光伏放量突破", "notice", "daily-digest", true, true, true, "/watchlist/gt-solar"),
    event("evt-observation", "observation.condition_verified", "observation", "昨日观察条件验证", "important", "immediate", true, true, false, "/today"),
    event("evt-valuation", "valuation.updated", "valuation", "澜海光伏估值样本更新", "info", "daily-digest", true, false, true, "/watchlist/gt-solar")
  ];

  if (scenarioId === "admin") {
    return [
      ...base,
      event("evt-system-provider", "system.data_source_degraded", "system", "数据源降级", "critical", "immediate", true, false, false, "/settings")
    ];
  }

  if (scenarioId === "partial-failure") {
    return [
      ...base,
      event("evt-wechat-failed", "notification.delivery_failed", "system", "微信公众号发送失败", "notice", "daily-digest", true, false, true, "/notifications")
    ];
  }

  return base;
}

export function getNotifications(scenarioId: ScenarioId): NotificationMock[] {
  if (scenarioId === "empty-user") {
    return [];
  }

  const items: NotificationMock[] = [
    notification("ntf-001", "daily-review", "notice", "unread", "今日全市场复盘已生成", "市场宽度偏弱，光伏设备和银行样本相对强；次日候选仅用于观察。", "/market-review/2026-07-22", "normal", "站内通知正常", "evt-market-review"),
    notification("ntf-002", "announcement", "important", "unread", "澜海光伏收录重大公告", "正式披露优先展示，AI摘要不得覆盖公告原文和发布时间。", "/watchlist/gt-solar", "normal", "站内通知正常", "evt-announcement"),
    notification("ntf-003", "anomaly", "notice", "read", "澜海光伏触发放量突破", "程序规则触发，正常价格成交异常进入日终摘要。", "/watchlist/gt-solar", "normal", "已读", "evt-anomaly"),
    notification("ntf-004", "observation", "important", "unread", "昨日观察条件需要验证", "部分条件已发生，部分条件无法判断，结果会进入下一次复盘材料。", "/today", "normal", "站内通知正常", "evt-observation"),
    notification("ntf-005", "valuation", "info", "archived", "估值样本已更新", "估值区间来自程序模型，不是事实、目标价或收益保证。", "/watchlist/gt-solar", "normal", "已归档", "evt-valuation"),
    notification("ntf-006", "system", "notice", "expired", "过期通知样本", "该通知已超过保留展示期，仅用于原型状态验证。", "/notifications", "normal", "已过期", "evt-market-review")
  ];

  if (scenarioId === "partial-failure") {
    return [
      notification("ntf-pf-001", "system", "notice", "wechat-failed", "微信公众号发送失败", "站内通知已正常创建，微信公众号通道失败不影响复盘和估值页面。", "/notifications", "partial-failure", "WeChat delivery failed mock", "evt-wechat-failed"),
      notification("ntf-pf-002", "daily-review", "notice", "data-source-degraded", "市场复盘部分数据可用", "概念板块缺失，行业样本仍可查看，候选已标记数据完整度。", "/market-review/2026-07-22", "partial-failure", "站内通知正常", "evt-market-review"),
      ...items.slice(1, 4)
    ];
  }

  if (scenarioId === "stale") {
    return [
      notification("ntf-stale-001", "daily-review", "notice", "data-source-degraded", "市场复盘使用过期行情", "行情停留在上一交易日，页面展示最近可用样本并降低结论置信度。", "/market-review/2026-07-22", "stale", "站内通知正常", "evt-market-review"),
      ...items.slice(1, 5)
    ];
  }

  if (scenarioId === "ai-failure") {
    return [
      notification("ntf-ai-001", "daily-review", "notice", "ai-summary-failed", "AI摘要失败，规则摘要已可用", "程序计算市场复盘正常，AI失败后使用规则模板生成站内摘要。", "/market-review/2026-07-22", "ai-failure", "站内通知正常", "evt-market-review"),
      ...items.slice(1, 5)
    ];
  }

  if (scenarioId === "admin") {
    return [
      notification("ntf-admin-001", "system", "critical", "unread", "管理员数据源降级通知", "系统级数据源异常仅管理员可见，不向普通用户暴露运维细节。", "/settings", "partial-failure", "站内通知正常", "evt-system-provider"),
      ...items
    ];
  }

  return items;
}

export function getNotificationPreferences(scenarioId: ScenarioId): NotificationPreferenceMock[] {
  const wechatBound = scenarioId !== "empty-user";

  return [
    pref("pref-in-all", "in_app", "*", true, "immediate", "info", true, "22:30-08:00"),
    pref("pref-daily", "in_app", "market_daily_review.generated", true, "daily-digest", "info", true, "22:30-08:00"),
    pref("pref-ann", "in_app", "announcement.major_collected", true, "immediate", "notice", false),
    pref("pref-anomaly", "in_app", "watchlist.abnormal_event.detected", true, "daily-digest", "notice", true),
    pref("pref-observation", "in_app", "observation.condition_verified", true, "immediate", "important", false),
    pref("pref-valuation", "in_app", "valuation.updated", true, "daily-digest", "info", true),
    pref("pref-wechat-daily", "wechat_official_account", "market_daily_review.generated", wechatBound && scenarioId === "normal", "daily-digest", "notice", true),
    pref("pref-wechat-ann", "wechat_official_account", "announcement.major_collected", wechatBound && scenarioId === "normal", "immediate", "important", false)
  ];
}

export function getExternalIdentities(scenarioId: ScenarioId): ExternalIdentityMock[] {
  if (scenarioId === "empty-user") {
    return [];
  }

  const bindStatus =
    scenarioId === "partial-failure"
      ? "channel-unavailable"
      : scenarioId === "stale"
        ? "authorization-invalid"
        : scenarioId === "ai-failure"
          ? "bound-unsubscribed"
          : "bound-subscribed";

  return [
    {
      id: "ext-wechat-001",
      provider: "wechat_official_account",
      providerAccountId: "mock-official-account",
      providerUserId: "mock-openid-redacted",
      unionId: "mock-unionid-optional",
      bindStatus,
      boundAt: "2026-07-20 09:15",
      updatedAt: "2026-07-22 15:50"
    }
  ];
}

export function getNotificationDeliveries(scenarioId: ScenarioId): NotificationDeliveryMock[] {
  const normal: NotificationDeliveryMock[] = [
    delivery("dlv-001", "ntf-001", "in_app", "sent", "market_daily_review.generated:user-001:market:in_app:v1:2026-07-22", "站内通知已创建"),
    delivery("dlv-002", "ntf-001", "wechat_official_account", scenarioId === "normal" ? "sent" : "skipped", "market_daily_review.generated:user-001:market:wechat:v1:2026-07-22", scenarioId === "normal" ? "微信摘要已发送（Mock）" : "微信通道未启用或状态不可用")
  ];

  if (scenarioId === "partial-failure") {
    return [
      ...normal,
      {
        ...delivery("dlv-pf-001", "ntf-pf-001", "wechat_official_account", "failed", "notification.delivery_failed:user-001:wechat:wechat:v1:2026-07-22", "微信公众号通道发送失败，不影响站内通知"),
        errorCode: "MOCK_WECHAT_CHANNEL_FAILED"
      }
    ];
  }

  return normal;
}

const marketPricingBoundary =
  "市场价格和市值是交易形成的市场定价；成交量、成交额和换手率只能表示关注度与流动性，不能直接证明内在价值。估值是模型估计，不是事实、建议或保证。";

const valuationByStockId: Record<string, StockValuation> = {
  "gt-solar": {
    availability: "available",
    method: "pe-stable",
    methodLabel: "稳定盈利股 PE 估值样本",
    valuationDate: tradeDate,
    financialPeriod: "2026Q1 模拟财报",
    currentPrice: "19.3元",
    marketCap: "386亿元",
    pe: "18x",
    pb: "2.4x",
    ps: "2.1x",
    confidence: "medium",
    modelLabel: "PE倍数区间",
    pricePosition: "当前价格位于基础情景区间中段",
    scenarios: [
      scenario("pessimistic", "保守", "16-18元", "-17% 至 -7%", ["盈利增速放缓", "行业倍数下修"]),
      scenario("base", "基础", "18-22元", "-7% 至 +14%", ["订单逐步兑现", "行业倍数保持中性"]),
      scenario("optimistic", "乐观", "22-25元", "+14% 至 +29%", ["海外订单超预期", "利润率改善"])
    ],
    assumptions: ["使用程序读取的模拟价格、市值和财务字段。", "倍数口径和可比公司选择仍待真实数据开发前确认。"],
    missingInputs: [],
    dataStatus: "normal",
    dataTime: generatedAt,
    source: "本地Mock估值字段",
    explanation: "估值区间用于展示方法边界，AI只能解释假设，不能生成行情或估值数字。",
    boundaryNote: marketPricingBoundary
  },
  "gt-cloud": {
    availability: "available",
    method: "ps-growth",
    methodLabel: "成长股 PS 估值样本",
    valuationDate: tradeDate,
    financialPeriod: "2026Q1 模拟财报",
    currentPrice: "40.2元",
    marketCap: "512亿元",
    pe: null,
    pb: "5.8x",
    ps: "9.6x",
    confidence: "low",
    modelLabel: "PS倍数区间",
    pricePosition: "当前价格接近乐观情景下沿",
    scenarios: [
      scenario("pessimistic", "保守", "28-34元", "-30% 至 -15%", ["收入增速下调", "订单确认延后"]),
      scenario("base", "基础", "34-41元", "-15% 至 +2%", ["收入维持中速增长", "费用率稳定"]),
      scenario("optimistic", "乐观", "41-49元", "+2% 至 +22%", ["AI应用收入加速", "续费率改善"])
    ],
    assumptions: ["亏损或高成长阶段不直接使用PE。", "PS倍数对收入增速和续费质量敏感。"],
    missingInputs: ["真实收入拆分和续费率字段待确认"],
    dataStatus: "normal",
    dataTime: generatedAt,
    source: "本地Mock估值字段",
    explanation: "成长股估值置信度较低，页面以区间和假设展示，不输出确定结论。",
    boundaryNote: marketPricingBoundary
  },
  "gt-material": {
    availability: "available",
    method: "cyclical-low-confidence",
    methodLabel: "周期股低置信度估值样本",
    valuationDate: tradeDate,
    financialPeriod: "2026Q1 模拟财报",
    currentPrice: "27.8元",
    marketCap: "198亿元",
    pe: "42x",
    pb: "1.9x",
    ps: "1.4x",
    confidence: "low",
    modelLabel: "周期倍数参考",
    pricePosition: "区间参考价值较弱",
    scenarios: [
      scenario("pessimistic", "保守", "20-24元", "-28% 至 -14%", ["材料价格回落", "库存周期转弱"]),
      scenario("base", "基础", "24-30元", "-14% 至 +8%", ["价格横盘", "产能利用率稳定"]),
      scenario("optimistic", "乐观", "30-35元", "+8% 至 +26%", ["涨价被订单验证", "库存周期修复"])
    ],
    assumptions: ["周期行业倍数波动大，不能单独依赖静态PE。", "传闻不作为估值输入事实。"],
    missingInputs: ["行业周期分位口径待确认"],
    dataStatus: "normal",
    dataTime: generatedAt,
    source: "本地Mock估值字段",
    explanation: "周期股估值只展示低置信度参考，需正式价格和财务数据验证。",
    boundaryNote: marketPricingBoundary
  },
  "gt-consumer": {
    availability: "available",
    method: "dividend",
    methodLabel: "分红收益率估值样本",
    valuationDate: tradeDate,
    financialPeriod: "2026Q1 模拟财报",
    currentPrice: "12.6元",
    marketCap: "142亿元",
    pe: "16x",
    pb: "2.2x",
    ps: "1.8x",
    dividendYield: "3.2%",
    confidence: "medium",
    modelLabel: "分红收益率区间",
    pricePosition: "当前价格位于基础情景区间下半部",
    scenarios: [
      scenario("pessimistic", "保守", "10-12元", "-20% 至 -4%", ["分红率下调", "消费恢复慢于预期"]),
      scenario("base", "基础", "12-15元", "-4% 至 +20%", ["分红率维持", "需求温和恢复"]),
      scenario("optimistic", "乐观", "15-17元", "+20% 至 +35%", ["现金流改善", "分红稳定性提升"])
    ],
    assumptions: ["分红方案以模拟历史为基础。", "正式分红预案仍需公告确认。"],
    missingInputs: [],
    dataStatus: "normal",
    dataTime: generatedAt,
    source: "本地Mock估值字段",
    explanation: "分红方法强调现金回报假设，不能替代正式财报和公告。",
    boundaryNote: marketPricingBoundary
  },
  "gt-bank": {
    availability: "available",
    method: "pb-roe-bank",
    methodLabel: "银行 PB-ROE 估值样本",
    valuationDate: tradeDate,
    financialPeriod: "2026Q1 模拟财报",
    currentPrice: "6.4元",
    marketCap: "2,180亿元",
    pe: "5.8x",
    pb: "0.72x",
    ps: null,
    dividendYield: "4.6%",
    confidence: "medium",
    modelLabel: "PB-ROE 匹配区间",
    pricePosition: "当前价格接近基础情景中位",
    scenarios: [
      scenario("pessimistic", "保守", "5.5-6.1元", "-14% 至 -5%", ["净息差继续承压", "资产质量折价扩大"]),
      scenario("base", "基础", "6.1-7.0元", "-5% 至 +9%", ["ROE维持稳定", "PB折价维持中性"]),
      scenario("optimistic", "乐观", "7.0-7.8元", "+9% 至 +22%", ["不良压力缓和", "分红稳定性提升"])
    ],
    assumptions: ["银行使用PB与ROE匹配关系，不直接套用成长股倍数。", "资产质量字段口径待真实供应商确认。"],
    missingInputs: ["真实不良率和拨备覆盖字段待确认"],
    dataStatus: "normal",
    dataTime: generatedAt,
    source: "本地Mock估值字段",
    explanation: "银行估值以PB-ROE为主，AI只解释适用原因和风险。",
    boundaryNote: marketPricingBoundary
  },
  "gt-loss": {
    availability: "unavailable",
    method: "unavailable",
    methodLabel: "亏损股暂不可估",
    valuationDate: tradeDate,
    financialPeriod: "2026Q1 模拟财报",
    currentPrice: "8.7元",
    marketCap: "74亿元",
    pe: null,
    pb: "3.6x",
    ps: "12.8x",
    confidence: "unavailable",
    modelLabel: "暂无适用模型",
    pricePosition: null,
    scenarios: [],
    assumptions: ["亏损且收入质量字段不足，MVP不补造估值区间。"],
    missingInputs: ["归母净利润为负", "可比倍数和收入质量字段不足"],
    dataStatus: "empty",
    dataTime: generatedAt,
    source: "本地Mock估值字段",
    explanation: "当前样本不可估，页面应显示不可用原因，而不是给出伪精确区间。",
    boundaryNote: marketPricingBoundary
  },
  "gt-suspend": {
    availability: "unavailable",
    method: "unavailable",
    methodLabel: "停牌样本估值暂不展示",
    valuationDate: tradeDate,
    financialPeriod: "2026Q1 模拟财报",
    currentPrice: null,
    marketCap: "56亿元",
    pe: null,
    pb: null,
    ps: null,
    confidence: "unavailable",
    modelLabel: "暂无适用模型",
    pricePosition: null,
    scenarios: [],
    assumptions: ["停牌样本保留历史记录，但当前价格和图表缺失。"],
    missingInputs: ["当日市场价格为空", "估值触发条件不足"],
    dataStatus: "empty",
    dataTime: generatedAt,
    source: "本地Mock估值字段",
    explanation: "停牌状态下不补造估值区间。",
    boundaryNote: marketPricingBoundary
  }
};

const boardHeatRecords = [
  {
    id: "board-solar",
    name: "光伏设备",
    type: "concept-board" as const,
    change1d: 2.8,
    change3d: 6.4,
    change5d: 9.2,
    consecutiveRisingDays: 3,
    risingRatio: 76,
    limitUpCount: 6,
    amountPercentile: 88,
    relativeIndexStrength: "+2.6pct",
    stage: "accelerating" as const,
    ranking: 1,
    rankingChange: 4,
    totalScore: 86,
    dataCompleteness: "完整样本",
    dataStatus: "normal" as const,
    components: [
      component("涨跌表现", "+2.8%", "1日/3日/5日收益", 82, "短线强于主要指数"),
      component("成交活跃", "88%", "近60日成交额分位", 88, "量能显著放大"),
      component("成分扩散", "76%", "成员上涨比例", 76, "板块内部扩散较好")
    ],
    hotStocks: [
      hotStock("gt-solar", "SH600001", "澜海光伏", 4.8, 8.6, 12.4, 3, "+2.1pct", 88, 92, 76, true, "系统角色建议：领涨样本", "放量突破且公告催化明确", "medium", "模拟重大合同公告", "成交额高分位后需验证持续性"),
      hotStock(undefined, "SZ002601", "光储样本A", 3.2, 7.1, 10.5, 2, "+0.9pct", 74, 80, 69, true, "系统角色建议：跟随样本", "强于板块但成交未居前", "low", "光储出海讨论", "样本非用户自选股")
    ],
    trendSummary: "光伏设备连续走强，成交额分位和成员上涨比例同步抬升。",
    continuity: "连续3日跑赢沪深300，仍需观察成交额是否维持高分位。",
    leadingStocks: ["澜海光伏"],
    followUpCandidates: ["光储样本A"],
    riskStocks: ["高位放量回落样本"],
    catalyst: "模拟重大合同公告与行业资讯共振。",
    pendingVerification: ["海外订单持续性", "板块成交额是否继续扩散"],
    dataGaps: [],
    updatedAt: generatedAt
  },
  {
    id: "board-bank",
    name: "银行",
    type: "standard-industry" as const,
    change1d: 1.1,
    change3d: 2.4,
    change5d: 3.8,
    consecutiveRisingDays: 4,
    risingRatio: 68,
    limitUpCount: 0,
    amountPercentile: 61,
    relativeIndexStrength: "+0.8pct",
    stage: "sustained-strong" as const,
    ranking: 2,
    rankingChange: 1,
    totalScore: 72,
    dataCompleteness: "完整样本",
    dataStatus: "normal" as const,
    components: [
      component("稳态表现", "+3.8%", "5日收益", 68, "连续性较好"),
      component("成交活跃", "61%", "近60日成交额分位", 61, "量能温和"),
      component("相对强度", "+0.8pct", "相对沪深300", 58, "防御风格偏强")
    ],
    hotStocks: [
      hotStock("gt-bank", "SH601006", "衡岳银行", 1.6, 3.1, 4.5, 4, "+0.5pct", 55, 63, 42, true, "系统角色建议：中军样本", "市值大且连续稳定强于指数", "medium", "分红稳定讨论", "弹性弱，更多体现风格防御")
    ],
    trendSummary: "银行板块连续性较好，表现偏稳，不以涨停数量驱动。",
    continuity: "连续4日温和走强，关注是否仍强于主要指数。",
    leadingStocks: ["衡岳银行"],
    followUpCandidates: ["分红稳定样本"],
    riskStocks: ["净息差敏感样本"],
    catalyst: "市场风格偏防御，分红稳定性被讨论。",
    pendingVerification: ["真实资产质量字段", "分红预期是否有公告支撑"],
    dataGaps: ["银行细分财务字段待真实供应商验证"],
    updatedAt: generatedAt
  },
  {
    id: "board-software",
    name: "软件服务",
    type: "concept-board" as const,
    change1d: 0.9,
    change3d: -0.7,
    change5d: -2.2,
    consecutiveRisingDays: 1,
    risingRatio: 42,
    limitUpCount: 1,
    amountPercentile: 57,
    relativeIndexStrength: "-0.4pct",
    stage: "high-divergence" as const,
    ranking: 7,
    rankingChange: -3,
    totalScore: 48,
    dataCompleteness: "部分样本",
    dataStatus: "normal" as const,
    components: [
      component("涨跌表现", "+0.9%", "1日收益", 54, "指数层面不弱"),
      component("成分扩散", "42%", "成员上涨比例", 42, "内部明显分化"),
      component("相对强度", "-0.4pct", "相对沪深300", 46, "未跑赢主要基准")
    ],
    hotStocks: [
      hotStock("gt-cloud", "SZ300002", "星云软件", -2.4, -1.1, -3.2, 0, "-3.5pct", 64, 58, 71, false, "系统角色建议：风险样本", "板块上涨但个股收跌", "low", "政策讨论升温", "价格和板块方向背离")
    ],
    trendSummary: "软件服务热度来自资讯讨论，但成员分化明显。",
    continuity: "缺少连续性，暂不进入强势延续列表。",
    leadingStocks: ["政策样本股"],
    followUpCandidates: [],
    riskStocks: ["星云软件"],
    catalyst: "行业政策讨论升温。",
    pendingVerification: ["政策资讯能否转化为订单事实"],
    dataGaps: ["概念成分完整性待确认"],
    updatedAt: generatedAt
  },
  {
    id: "board-material",
    name: "新材料",
    type: "concept-board" as const,
    change1d: -1.8,
    change3d: -4.6,
    change5d: -7.2,
    consecutiveRisingDays: 0,
    risingRatio: 24,
    limitUpCount: 0,
    amountPercentile: 39,
    relativeIndexStrength: "-2.0pct",
    stage: "retreat" as const,
    ranking: 11,
    rankingChange: -6,
    totalScore: 31,
    dataCompleteness: "部分样本",
    dataStatus: "normal" as const,
    components: [
      component("涨跌表现", "-1.8%", "1日收益", 31, "转弱"),
      component("成交活跃", "39%", "近60日成交额分位", 39, "量能未验证"),
      component("成分扩散", "24%", "成员上涨比例", 24, "扩散弱")
    ],
    hotStocks: [
      hotStock("gt-material", "SH688003", "北辰材料", 0.7, 0.8, 1.8, 1, "+0.4pct", 43, 39, 35, false, "系统角色建议：修复样本", "弱板块内相对抗跌", "low", "材料涨价传闻", "传闻未经正式来源确认")
    ],
    trendSummary: "新材料板块处于退潮状态，少数个股相对抗跌。",
    continuity: "缺少连续上涨，成交额分位偏低。",
    leadingStocks: [],
    followUpCandidates: ["北辰材料"],
    riskStocks: ["材料涨价链高波动样本"],
    catalyst: "材料涨价传闻扩散。",
    pendingVerification: ["材料价格传闻是否有权威来源"],
    dataGaps: ["传闻不作为事实输入"],
    updatedAt: generatedAt
  }
];

const boardCandidates = [
  candidate("cand-board-solar", "board", "光伏设备", undefined, "program-ranking", "量能分位、成员上涨比例和连续性同步改善。", "accelerating", "/market-review/2026-07-22"),
  candidate("cand-board-bank", "board", "银行", undefined, "program-ranking", "连续强于指数，风格偏防御。", "sustained-strong", "/market-review/2026-07-22")
];

const stockCandidates = [
  candidate("cand-stock-solar", "stock", "澜海光伏", "SH600001", "program-ranking", "板块强势且个股放量突破，但需验证公告后成交持续性。", "stock-observation", "/watchlist/gt-solar"),
  candidate("cand-stock-bank", "stock", "衡岳银行", "SH601006", "program-ranking", "银行板块中军样本，连续性较好但弹性有限。", "stock-observation", "/watchlist/gt-bank"),
  candidate("cand-stock-cloud-risk", "stock", "星云软件", "SZ300002", "ai-explanation", "AI解释板块与个股背离原因，但候选性质为风险观察。", "stock-observation", "/watchlist/gt-cloud")
];

function event(
  id: string,
  eventType: BusinessEventMock["eventType"],
  category: BusinessEventMock["category"],
  subjectName: string,
  severity: BusinessEventMock["severity"],
  defaultFrequency: BusinessEventMock["defaultFrequency"],
  inAppDefault: boolean,
  wechatAllowed: boolean,
  digestIncluded: boolean,
  targetHref: string
): BusinessEventMock {
  return {
    id,
    eventType,
    category,
    subjectId: id.replace("evt-", ""),
    subjectName,
    businessDate: tradeDate,
    triggerModule: category,
    severity,
    defaultFrequency,
    inAppDefault,
    wechatAllowed,
    digestIncluded,
    dedupeKey: `${eventType}:user-001:${subjectName}:${tradeDate}`,
    targetHref
  };
}

function notification(
  id: string,
  type: NotificationMock["type"],
  severity: NotificationMock["severity"],
  state: NotificationMock["state"],
  title: string,
  summary: string,
  targetHref: string,
  dataStatus: NotificationMock["dataStatus"],
  serviceStatus: string,
  sourceEventId: string
): NotificationMock {
  return {
    id,
    type,
    severity,
    state,
    title,
    summary,
    createdAt: generatedAt,
    targetHref,
    dataStatus,
    serviceStatus,
    sourceEventId
  };
}

function pref(
  id: string,
  channel: NotificationPreferenceMock["channel"],
  eventType: string,
  enabled: boolean,
  frequency: NotificationPreferenceMock["frequency"],
  minSeverity: NotificationPreferenceMock["minSeverity"],
  digestIncluded: boolean,
  quietHours?: string
): NotificationPreferenceMock {
  return {
    id,
    channel,
    eventType,
    enabled,
    frequency,
    minSeverity,
    digestIncluded,
    quietHours
  };
}

function delivery(
  id: string,
  notificationId: string,
  channel: NotificationDeliveryMock["channel"],
  status: NotificationDeliveryMock["status"],
  idempotencyKey: string,
  message: string
): NotificationDeliveryMock {
  return {
    id,
    notificationId,
    channel,
    status,
    idempotencyKey,
    attemptedAt: generatedAt,
    message
  };
}

function scenario(
  name: "pessimistic" | "base" | "optimistic",
  label: string,
  priceRange: string,
  impliedSpace: string,
  assumptions: string[]
) {
  return { name, label, priceRange, impliedSpace, assumptions };
}

function component(label: string, value: string, benchmark: string, score: number, note: string) {
  return { label, value, benchmark, score, note };
}

function hotStock(
  stockId: string | undefined,
  code: string,
  name: string,
  change1d: number,
  change3d: number,
  change5d: number,
  consecutiveRisingDays: number,
  relativeBoardStrength: string,
  volumePercentile: number,
  amountPercentile: number,
  turnoverPercentile: number,
  nearHigh20: boolean,
  roleSuggestion: string,
  roleBasis: string,
  confidence: "high" | "medium" | "low" | "unavailable",
  coreDriver: string,
  riskPenalty: string
) {
  return {
    stockId,
    code,
    name,
    change1d,
    change3d,
    change5d,
    consecutiveRisingDays,
    relativeBoardStrength,
    volumePercentile,
    amountPercentile,
    turnoverPercentile,
    nearHigh20,
    roleSuggestion,
    roleBasis,
    confidence,
    coreDriver,
    riskPenalty,
    updatedAt: generatedAt
  };
}

function candidate(
  id: string,
  subjectType: "board" | "stock",
  subjectName: string,
  subjectCode: string | undefined,
  source: "program-ranking" | "ai-explanation" | "rule-template",
  reason: string,
  stage: "new-start" | "accelerating" | "sustained-strong" | "high-divergence" | "retreat" | "repair" | "insufficient-data" | "stock-observation",
  targetHref: string
) {
  return {
    id,
    subjectType,
    subjectName,
    subjectCode,
    source,
    reason,
    stage,
    continuationConditions: ["数据继续完整", "相对强弱不明显转弱", "公告或资讯事实不被反证"],
    invalidationConditions: ["成交额分位快速回落", "板块成员扩散失败", "出现正式反向信息"],
    riskNotes: ["仅用于观察，不提供交易动作。", "Mock字段不代表真实行情。"],
    pendingVerification: ["真实供应商口径", "成分股覆盖完整性"],
    dataCompleteness: "Mock完整",
    targetHref
  };
}
