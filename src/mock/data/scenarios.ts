import { SCENARIOS } from "@/lib/constants";
import type {
  AbnormalEvent,
  BoardTag,
  ChartSet,
  DailyKLinePoint,
  DataSourceStatus,
  GeniusMockData,
  GroupPerformance,
  InfoItem,
  IntradayPoint,
  MarketSnapshot,
  MiniTrendPoint,
  ObservationCondition,
  PendingTask,
  QuantMetric,
  ReviewSummary,
  ScenarioId,
  SentimentItem,
  Stock
} from "@/mock/types";

const tradeDate = "2026-07-22";
const generatedAt = "2026-07-22 15:48";
const normalUpdatedAt = "2026-07-22 15:36";
const staleUpdatedAt = "2026-07-21 15:38";

const baseSourceStatuses: DataSourceStatus[] = [
  {
    label: "日级行情",
    source: "模拟行情源（供应商未定）",
    status: "normal",
    updatedAt: normalUpdatedAt,
    message: "收盘后日级快照已更新，页面不承诺实时行情。"
  },
  {
    label: "公告与资讯",
    source: "模拟公告资讯池",
    status: "normal",
    updatedAt: "2026-07-22 15:20",
    message: "正式披露、权威资讯和平台观点已分层标记。"
  },
  {
    label: "舆情收件箱",
    source: "用户手动录入的模拟链接",
    status: "normal",
    updatedAt: "2026-07-22 14:55",
    message: "外部讨论以链接和用户补充文本为主。"
  },
  {
    label: "AI复盘",
    source: "OpenAI Compatible Mock Gateway",
    status: "normal",
    updatedAt: "2026-07-22 15:42",
    message: "AI结果仅用于摘要和判断，不生成行情数字。"
  }
];

function market(
  changePercent: number | null,
  overrides: Partial<MarketSnapshot> = {}
): MarketSnapshot {
  return {
    source: "模拟行情源（供应商未定）",
    dataTime: tradeDate,
    updatedAt: normalUpdatedAt,
    status: "normal",
    open: 18.42,
    high: 19.68,
    low: 18.12,
    close: 19.31,
    changePercent,
    amplitude: 8.4,
    volume: "1.28亿股",
    turnoverAmount: "24.6亿元",
    turnoverRate: 7.82,
    totalMarketCap: "386亿元",
    floatMarketCap: "214亿元",
    recentPerformance: "近5日 +7.6%，近20日 +12.4%",
    relativeSectorStrength: "强于所属板块 +2.1pct",
    relativeIndexStrength: "强于沪深300 +4.6pct",
    ...overrides
  };
}

function board(name: string, type: BoardTag["type"]): BoardTag {
  const source =
    type === "dynamic-theme" ? "模拟规则/AI建议（待用户确认）" : "模拟标准分类源（供应商未定）";

  return { name, type, source, updatedAt: normalUpdatedAt };
}

function makeMiniTrend(start: number, deltas: Array<number | null>): MiniTrendPoint[] {
  return deltas.map((delta, index) => ({
    day: `D-${19 - index}`,
    close: delta === null ? null : Number((start + delta).toFixed(2))
  }));
}

function makeIntraday(
  previousClose: number,
  offsets: number[],
  volumeSeed: number
): IntradayPoint[] {
  const base = Date.UTC(2026, 6, 22, 1, 30) / 1000;
  let cumulative = 0;

  return offsets.map((offset, index) => {
    const price = Number((previousClose + offset).toFixed(2));
    cumulative += price;

    return {
      time: base + index * 15 * 60,
      price,
      avgPrice: Number((cumulative / (index + 1)).toFixed(2)),
      volume: volumeSeed + index * 680 + (index % 3) * 520
    };
  });
}

function makeDailyKLines(startClose: number, trend: number): DailyKLinePoint[] {
  const rows: DailyKLinePoint[] = [];

  for (let index = 0; index < 60; index += 1) {
    const wave = Math.sin(index / 3.6) * 0.48 + Math.cos(index / 5.2) * 0.22;
    const close = Number((startClose + index * trend + wave).toFixed(2));
    const open = Number((close - trend * 0.6 + Math.sin(index / 2) * 0.18).toFixed(2));
    const high = Number((Math.max(open, close) + 0.28 + (index % 4) * 0.05).toFixed(2));
    const low = Number((Math.min(open, close) - 0.26 - (index % 5) * 0.04).toFixed(2));
    const volume = 16000 + index * 260 + (index % 7) * 820;
    const date = new Date(Date.UTC(2026, 4, 25 + index));

    rows.push({
      time: date.toISOString().slice(0, 10),
      open,
      high,
      low,
      close,
      volume
    });
  }

  return rows.map((row, index, allRows) => ({
    ...row,
    ma5: movingAverage(allRows, index, 5),
    ma10: movingAverage(allRows, index, 10),
    ma20: movingAverage(allRows, index, 20)
  }));
}

function movingAverage(rows: DailyKLinePoint[], index: number, size: number): number | undefined {
  if (index + 1 < size) {
    return undefined;
  }

  const slice = rows.slice(index + 1 - size, index + 1);
  const sum = slice.reduce((total, row) => total + row.close, 0);
  return Number((sum / size).toFixed(2));
}

function chartSet(
  previousClose: number | null,
  intradayOffsets: number[],
  dailyStart: number,
  dailyTrend: number,
  overrides: Partial<ChartSet> = {}
): ChartSet {
  const hasPreviousClose = previousClose !== null;

  return {
    status: hasPreviousClose ? "normal" : "empty",
    dataTime: tradeDate,
    updatedAt: normalUpdatedAt,
    previousClose,
    intraday: hasPreviousClose ? makeIntraday(previousClose, intradayOffsets, 6800) : [],
    dailyK: hasPreviousClose ? makeDailyKLines(dailyStart, dailyTrend) : [],
    ...overrides
  };
}

function quantMetrics(values: {
  p5: string | null;
  p10: string | null;
  p20: string | null;
  distanceHigh20: string | null;
  industryStrength: string | null;
  indexStrength: string | null;
  volumePercentile: number | null;
  amountPercentile: number | null;
  turnoverPercentile: number | null;
  amplitudePercentile: number | null;
  closePosition: number | null;
  maxDrawdown: string | null;
}): QuantMetric[] {
  return [
    metric("p5", "5日涨跌幅", values.p5, "近5个交易日", "trend", parseSigned(values.p5), direction(values.p5), "短线动量"),
    metric("p10", "10日涨跌幅", values.p10, "近10个交易日", "trend", parseSigned(values.p10), direction(values.p10), "中短期表现"),
    metric("p20", "20日涨跌幅", values.p20, "近20个交易日", "trend", parseSigned(values.p20), direction(values.p20), "阶段趋势"),
    metric("dist20h", "距20日最高点", values.distanceHigh20, "20日高点", "strength", strengthFromSigned(values.distanceHigh20), direction(values.distanceHigh20), "越接近高点越强"),
    metric("relIndustry", "相对行业板块强度", values.industryStrength, "所属行业板块", "strength", strengthFromSigned(values.industryStrength), direction(values.industryStrength), "程序计算相对强弱"),
    metric("relIndex", "相对主要指数强度", values.indexStrength, "沪深300模拟指数", "strength", strengthFromSigned(values.indexStrength), direction(values.indexStrength), "程序计算相对强弱"),
    metric("volPct", "成交量历史分位", percent(values.volumePercentile), "近60日", "percentile", values.volumePercentile, undefined, "量能位置"),
    metric("amountPct", "成交额历史分位", percent(values.amountPercentile), "近60日", "percentile", values.amountPercentile, undefined, "成交额位置"),
    metric("turnoverPct", "换手率历史分位", percent(values.turnoverPercentile), "近60日", "percentile", values.turnoverPercentile, undefined, "换手活跃度"),
    metric("amplitudePct", "振幅历史分位", percent(values.amplitudePercentile), "近60日", "percentile", values.amplitudePercentile, undefined, "波动位置"),
    metric("closePos", "日内收盘位置", percent(values.closePosition), "当日高低区间", "percentile", values.closePosition, undefined, "收盘靠近高低点的位置"),
    metric("maxDrawdown", "最大日内回撤", values.maxDrawdown, "当日最高价至最低后回撤", "strength", strengthFromSigned(values.maxDrawdown), direction(values.maxDrawdown), "盘中风险暴露")
  ];
}

function metric(
  id: string,
  label: string,
  value: string | null,
  benchmark: string,
  visualType: QuantMetric["visualType"],
  visualValue: number | null,
  metricDirection: QuantMetric["direction"],
  status: string
): QuantMetric {
  return {
    id,
    label,
    value,
    benchmark,
    visualType,
    visualValue,
    direction: metricDirection,
    status,
    dataTime: "2026-07-22 15:36"
  };
}

function parseSigned(value: string | null): number | null {
  if (!value) {
    return null;
  }

  return Number(value.replace("%", "").replace("+", ""));
}

function strengthFromSigned(value: string | null): number | null {
  const parsed = parseSigned(value);

  if (parsed === null || Number.isNaN(parsed)) {
    return null;
  }

  return Math.max(0, Math.min(100, 50 + parsed * 7));
}

function direction(value: string | null): QuantMetric["direction"] {
  const parsed = parseSigned(value);

  if (parsed === null || Number.isNaN(parsed)) {
    return undefined;
  }

  if (parsed > 0) {
    return "up";
  }

  if (parsed < 0) {
    return "down";
  }

  return "flat";
}

function percent(value: number | null): string | null {
  return value === null ? null : `${value}%`;
}

const abnormalEvents: AbnormalEvent[] = [
  {
    id: "abn-001",
    stockId: "gt-solar",
    stockName: "澜海光伏",
    type: "放量突破",
    severity: "high",
    ruleCategory: "historical-percentile",
    evidence: "成交额处于近60个交易日高分位，收盘价突破近20日区间上沿。",
    benchmark: "股票自身近60日成交额分位与近20日价格区间",
    actualData: "成交额 24.6亿元；近60日分位 92%；收盘 +4.82%",
    ruleVersion: "mock-rule-v1",
    dataTime: "2026-07-22 15:36"
  },
  {
    id: "abn-002",
    stockId: "gt-cloud",
    stockName: "星云软件",
    type: "板块背离",
    severity: "medium",
    ruleCategory: "relative",
    evidence: "软件服务板块上涨，但个股收跌并放大换手。",
    benchmark: "所属板块表现与沪深300",
    actualData: "个股 -2.36%；软件服务板块 +1.12%；换手率 6.48%",
    ruleVersion: "mock-rule-v1",
    dataTime: "2026-07-22 15:36"
  },
  {
    id: "abn-003",
    stockId: "gt-consumer",
    stockName: "山海消费",
    type: "尾盘异动",
    severity: "low",
    ruleCategory: "official-fixed",
    evidence: "尾盘成交显著放大，价格回收日内跌幅。",
    benchmark: "收盘前30分钟成交占比",
    actualData: "尾盘成交占全天 28%；收盘 +1.05%",
    ruleVersion: "mock-rule-v1",
    dataTime: "2026-07-22 15:36"
  }
];

const infoItems: InfoItem[] = [
  {
    id: "info-001",
    stockIds: ["gt-solar"],
    title: "澜海光伏发布模拟重大合同公告",
    sourceName: "模拟交易所公告",
    sourceKind: "official-disclosure",
    publishedAt: "2026-07-22 12:05",
    collectedAt: "2026-07-22 12:18",
    linkLabel: "原始链接（模拟）",
    summary: "公司公告称拟签署海外组件供货合同，公告正文和AI摘要分开展示。",
    status: "normal"
  },
  {
    id: "info-002",
    stockIds: ["gt-cloud"],
    title: "软件服务行业政策讨论升温",
    sourceName: "模拟权威资讯",
    sourceKind: "authoritative-news",
    publishedAt: "2026-07-22 10:30",
    collectedAt: "2026-07-22 10:55",
    linkLabel: "原始链接（模拟）",
    summary: "行业资讯提到信创订单节奏变化，未直接构成个股业绩事实。",
    status: "normal"
  },
  {
    id: "info-003",
    stockIds: ["gt-consumer"],
    title: "消费复苏主题被多平台讨论",
    sourceName: "模拟新闻网页",
    sourceKind: "platform-opinion",
    publishedAt: "2026-07-22 09:40",
    collectedAt: "2026-07-22 10:12",
    linkLabel: "原始链接（模拟）",
    summary: "平台观点认为暑期消费主题热度提升，需与正式经营数据分开展示。",
    status: "normal"
  }
];

const sentiments: SentimentItem[] = [
  {
    id: "sent-001",
    stockId: "gt-solar",
    platform: "雪球",
    author: "模拟博主A",
    sourceKind: "platform-opinion",
    title: "讨论光储出海订单弹性",
    heatChange: "热度较昨日 +36%",
    summary: "观点偏乐观，但部分内容依赖未核实渠道传闻。",
    verifyStatus: "pending",
    collectedAt: "2026-07-22 14:20"
  },
  {
    id: "sent-002",
    stockId: "gt-material",
    platform: "小红书",
    author: "模拟博主B",
    sourceKind: "unverified-rumor",
    title: "材料涨价传闻扩散",
    heatChange: "热度较昨日 +72%",
    summary: "存在价格传闻，尚未发现正式披露或权威资讯确认。",
    verifyStatus: "needs-user-input",
    collectedAt: "2026-07-22 13:50"
  }
];

const observations: ObservationCondition[] = [
  {
    id: "obs-001",
    stockId: "gt-solar",
    stockName: "澜海光伏",
    content: "若成交额继续高于20日均值，观察突破是否有效。",
    status: "occurred",
    evidence: "今日成交额明显放大，收盘站上模拟突破位。",
    reviewDate: "2026-07-21",
    verificationDate: "2026-07-22"
  },
  {
    id: "obs-002",
    stockId: "gt-cloud",
    stockName: "星云软件",
    content: "观察政策资讯是否带动板块内同步走强。",
    status: "not-occurred",
    evidence: "板块上涨但个股收跌，未形成同步确认。",
    reviewDate: "2026-07-21",
    verificationDate: "2026-07-22"
  },
  {
    id: "obs-003",
    stockId: "gt-consumer",
    stockName: "山海消费",
    content: "关注消费主题热度能否转化为成交活跃。",
    status: "partially-occurred",
    evidence: "尾盘成交放大，但全天量能仍未明显超过历史高分位。",
    reviewDate: "2026-07-21",
    verificationDate: "2026-07-22"
  },
  {
    id: "obs-004",
    stockId: "gt-material",
    stockName: "北辰材料",
    content: "确认材料价格传闻是否有权威来源。",
    status: "unknown",
    evidence: "当前资讯源部分失败，暂无法判断。",
    reviewDate: "2026-07-21",
    verificationDate: "2026-07-22"
  },
  {
    id: "obs-005",
    stockId: "gt-suspend",
    stockName: "停牌样本",
    content: "观察盘中换手是否继续异常。",
    status: "not-applicable",
    evidence: "今日停牌，原观察条件不再适用。",
    reviewDate: "2026-07-21",
    verificationDate: "2026-07-22"
  }
];

const successfulOverallReview: ReviewSummary = {
  status: "success",
  title: "AI整体复盘摘要（模拟）",
  summary:
    "今日自选股分化明显，强势集中在光伏和部分消费主题，软件服务出现板块与个股背离。待核实信息主要来自社交平台传闻，需优先寻找正式披露或权威资讯交叉验证。",
  modelName: "mock-openai-compatible-model",
  generatedAt: "2026-07-22 15:42",
  taskType: "整体复盘生成",
  isOriginalAiVersion: true,
  sourceLayers: ["客观行情", "正式公告", "权威资讯", "平台观点", "未经核实传闻"]
};

function stockReview(stockName: string): ReviewSummary {
  return {
    status: "manual-edited",
    title: `${stockName} 当日复盘（模拟）`,
    summary:
      "客观行情与公告先行展示，AI仅基于已标注材料生成解释。用户已补充人工修订，保留原始AI版本和人工版本摘要。",
    modelName: "mock-openai-compatible-model",
    generatedAt: "2026-07-22 15:41",
    taskType: "单股复盘生成",
    isOriginalAiVersion: false,
    sourceLayers: ["客观行情", "外部事实", "AI判断", "用户笔记"],
    manualRevision: "用户修订：继续观察量能是否能维持，不作为买卖建议。"
  };
}

const baseStocks: Stock[] = [
  {
    id: "gt-solar",
    code: "SH600001",
    name: "澜海光伏",
    market: "上交所主板",
    tradeStatus: "normal",
    statusLabel: "正常交易",
    personalGroups: ["高景气赛道", "重点观察"],
    standardIndustries: [board("电力设备", "standard-industry")],
    conceptBoards: [board("光伏设备", "concept-board"), board("储能", "concept-board")],
    dynamicThemes: [board("光储出海", "dynamic-theme")],
    userTags: [
      { label: "政策敏感", kind: "user" },
      { label: "观察放量", kind: "user" }
    ],
    focusReason: "跟踪海外订单改善和板块相对强弱。",
    focusLogicChange: "关注逻辑由单纯政策预期转向订单验证和成交持续性。",
    marketSnapshot: market(4.82),
    miniTrend: makeMiniTrend(17.2, [-0.4, -0.35, -0.2, 0.1, 0.22, 0.18, 0.34, 0.46, 0.6, 0.72, 0.68, 0.9, 1.08, 1.16, 1.24, 1.4, 1.58, 1.72, 1.86, 2.11]),
    chartSet: chartSet(18.42, [0.02, 0.08, 0.18, 0.12, 0.34, 0.48, 0.42, 0.66, 0.82, 0.75, 0.92, 1.08, 1.0, 1.15, 1.22, 0.89], 15.6, 0.055),
    quantMetrics: quantMetrics({
      p5: "+7.6%",
      p10: "+9.8%",
      p20: "+12.4%",
      distanceHigh20: "-1.9%",
      industryStrength: "+2.1%",
      indexStrength: "+4.6%",
      volumePercentile: 88,
      amountPercentile: 92,
      turnoverPercentile: 76,
      amplitudePercentile: 81,
      closePosition: 87,
      maxDrawdown: "-3.1%"
    }),
    abnormalEvents: abnormalEvents.filter((event) => event.stockId === "gt-solar"),
    infoTimeline: infoItems.filter((item) => item.stockIds.includes("gt-solar")),
    sentimentItems: sentiments.filter((item) => item.stockId === "gt-solar"),
    todayReview: stockReview("澜海光伏"),
    observations: observations.filter((item) => item.stockId === "gt-solar"),
    reviewHistory: [
      {
        id: "rev-001-ai",
        date: "2026-07-22",
        type: "ai-original",
        title: "AI原始版本",
        summary: "识别到放量突破和重大合同公告，但提示舆情传闻需核实。"
      },
      {
        id: "rev-001-manual",
        date: "2026-07-22",
        type: "manual-revision",
        title: "人工修订版本",
        summary: "补充对量能连续性的观察，删除任何买卖倾向表述。"
      }
    ],
    userNotes: ["模拟用户笔记：下次复盘重点看公告后成交是否回落。"]
  },
  {
    id: "gt-cloud",
    code: "SZ300002",
    name: "星云软件",
    market: "深交所创业板",
    tradeStatus: "normal",
    statusLabel: "正常交易",
    personalGroups: ["AI应用", "观察池"],
    standardIndustries: [board("计算机", "standard-industry")],
    conceptBoards: [board("信创", "concept-board"), board("软件服务", "concept-board")],
    dynamicThemes: [board("政策催化", "dynamic-theme")],
    userTags: [{ label: "板块背离", kind: "user" }],
    focusReason: "观察政策资讯与订单节奏是否形成共振。",
    focusLogicChange: "今日出现板块上涨但个股走弱，关注逻辑需重新验证。",
    marketSnapshot: market(-2.36, {
      open: 42.4,
      high: 42.8,
      low: 39.9,
      close: 40.18,
      amplitude: 6.9,
      volume: "4280万股",
      turnoverAmount: "17.3亿元",
      turnoverRate: 6.48,
      totalMarketCap: "512亿元",
      floatMarketCap: "276亿元",
      recentPerformance: "近5日 -3.2%，近20日 +4.1%",
      relativeSectorStrength: "弱于所属板块 -3.48pct",
      relativeIndexStrength: "弱于沪深300 -1.9pct"
    }),
    miniTrend: makeMiniTrend(41.8, [0.6, 0.4, 0.7, 0.3, 0.1, -0.2, 0.05, -0.35, -0.48, -0.2, -0.55, -0.72, -0.8, -1.0, -0.92, -1.12, -1.3, -1.48, -1.6, -1.62]),
    chartSet: chartSet(41.15, [0.12, 0.04, -0.18, -0.32, -0.28, -0.46, -0.64, -0.82, -0.71, -0.9, -0.75, -0.88, -0.96, -1.02, -0.86, -0.97], 39.4, 0.018),
    quantMetrics: quantMetrics({
      p5: "-3.2%",
      p10: "-1.4%",
      p20: "+4.1%",
      distanceHigh20: "-8.6%",
      industryStrength: "-3.5%",
      indexStrength: "-1.9%",
      volumePercentile: 64,
      amountPercentile: 58,
      turnoverPercentile: 71,
      amplitudePercentile: 69,
      closePosition: 18,
      maxDrawdown: "-6.8%"
    }),
    abnormalEvents: abnormalEvents.filter((event) => event.stockId === "gt-cloud"),
    infoTimeline: infoItems.filter((item) => item.stockIds.includes("gt-cloud")),
    sentimentItems: [],
    todayReview: stockReview("星云软件"),
    observations: observations.filter((item) => item.stockId === "gt-cloud"),
    reviewHistory: [
      {
        id: "rev-002-ai",
        date: "2026-07-22",
        type: "ai-original",
        title: "AI原始版本",
        summary: "提示政策资讯与价格表现背离，建议列入待验证事项。"
      }
    ],
    userNotes: ["模拟用户笔记：先看后续公告和订单数据，避免只看讨论热度。"]
  },
  {
    id: "gt-material",
    code: "SH688003",
    name: "北辰材料",
    market: "上交所科创板",
    tradeStatus: "normal",
    statusLabel: "正常交易",
    personalGroups: ["周期观察"],
    standardIndustries: [board("基础化工", "standard-industry")],
    conceptBoards: [board("新材料", "concept-board")],
    dynamicThemes: [board("材料涨价链", "dynamic-theme")],
    userTags: [{ label: "待核实传闻", kind: "user" }],
    focusReason: "跟踪材料价格传闻与真实公告之间的差异。",
    focusLogicChange: "今日新增传闻，尚未找到正式来源。",
    marketSnapshot: market(0.68, {
      open: 27.5,
      high: 28.1,
      low: 26.8,
      close: 27.84,
      amplitude: 4.7,
      volume: "2160万股",
      turnoverAmount: "6.0亿元",
      turnoverRate: 3.14,
      totalMarketCap: "198亿元",
      floatMarketCap: "126亿元",
      recentPerformance: "近5日 +1.8%，近20日 -2.2%",
      relativeSectorStrength: "略强于所属板块 +0.4pct",
      relativeIndexStrength: "强于沪深300 +0.6pct"
    }),
    miniTrend: makeMiniTrend(27.9, [-0.1, -0.22, -0.18, -0.04, 0.02, -0.08, 0.12, 0.24, 0.05, 0.18, 0.1, 0.28, 0.36, 0.22, 0.31, 0.44, 0.38, 0.5, 0.42, -0.06]),
    chartSet: chartSet(27.65, [0.02, 0.1, 0.18, 0.12, 0.22, 0.28, 0.18, 0.32, 0.41, 0.33, 0.24, 0.2, 0.12, 0.16, 0.22, 0.19], 26.7, 0.006),
    quantMetrics: quantMetrics({
      p5: "+1.8%",
      p10: "+0.9%",
      p20: "-2.2%",
      distanceHigh20: "-4.2%",
      industryStrength: "+0.4%",
      indexStrength: "+0.6%",
      volumePercentile: 43,
      amountPercentile: 39,
      turnoverPercentile: 35,
      amplitudePercentile: 48,
      closePosition: 55,
      maxDrawdown: "-4.0%"
    }),
    abnormalEvents: [],
    infoTimeline: [],
    sentimentItems: sentiments.filter((item) => item.stockId === "gt-material"),
    todayReview: stockReview("北辰材料"),
    observations: observations.filter((item) => item.stockId === "gt-material"),
    reviewHistory: [],
    userNotes: ["模拟用户笔记：价格传闻不要当事实，需要正式信息交叉验证。"]
  },
  {
    id: "gt-consumer",
    code: "SZ000004",
    name: "山海消费",
    market: "深交所主板",
    tradeStatus: "normal",
    statusLabel: "正常交易",
    personalGroups: ["消费复苏"],
    standardIndustries: [board("食品饮料", "standard-industry")],
    conceptBoards: [board("新零售", "concept-board")],
    dynamicThemes: [board("暑期消费", "dynamic-theme")],
    userTags: [{ label: "尾盘观察", kind: "user" }],
    focusReason: "观察消费热度是否形成业绩验证线索。",
    focusLogicChange: "今日尾盘回收跌幅，但仍需确认是否只是短线情绪。",
    marketSnapshot: market(1.05, {
      open: 12.26,
      high: 12.68,
      low: 12.02,
      close: 12.55,
      amplitude: 5.3,
      volume: "5380万股",
      turnoverAmount: "6.7亿元",
      turnoverRate: 4.92,
      totalMarketCap: "142亿元",
      floatMarketCap: "88亿元",
      recentPerformance: "近5日 +2.4%，近20日 +1.7%",
      relativeSectorStrength: "强于所属板块 +0.8pct",
      relativeIndexStrength: "强于沪深300 +1.0pct"
    }),
    miniTrend: makeMiniTrend(12.1, [0.05, 0.02, 0.08, 0.12, 0.1, 0.16, 0.2, 0.18, 0.22, 0.24, 0.28, 0.3, 0.27, 0.31, 0.34, 0.38, 0.42, 0.39, 0.45, 0.47]),
    chartSet: chartSet(12.42, [0.01, -0.03, -0.09, -0.12, -0.08, -0.02, 0.03, 0.05, 0.01, 0.08, 0.12, 0.09, 0.1, 0.15, 0.11, 0.13], 11.9, 0.012),
    quantMetrics: quantMetrics({
      p5: "+2.4%",
      p10: "+1.1%",
      p20: "+1.7%",
      distanceHigh20: "-2.7%",
      industryStrength: "+0.8%",
      indexStrength: "+1.0%",
      volumePercentile: 52,
      amountPercentile: 49,
      turnoverPercentile: 58,
      amplitudePercentile: 57,
      closePosition: 72,
      maxDrawdown: "-3.4%"
    }),
    abnormalEvents: abnormalEvents.filter((event) => event.stockId === "gt-consumer"),
    infoTimeline: infoItems.filter((item) => item.stockIds.includes("gt-consumer")),
    sentimentItems: [],
    todayReview: stockReview("山海消费"),
    observations: observations.filter((item) => item.stockId === "gt-consumer"),
    reviewHistory: [
      {
        id: "rev-004-manual",
        date: "2026-07-21",
        type: "manual-revision",
        title: "昨日人工版本",
        summary: "记录观察条件：消费热度是否带来成交活跃。"
      }
    ],
    userNotes: ["模拟用户笔记：看后续是否有正式经营数据。"]
  },
  {
    id: "gt-suspend",
    code: "BJ830005",
    name: "停牌样本",
    market: "北交所",
    tradeStatus: "suspended",
    statusLabel: "停牌",
    personalGroups: ["事件观察"],
    standardIndustries: [board("机械设备", "standard-industry")],
    conceptBoards: [board("专用设备", "concept-board")],
    dynamicThemes: [],
    userTags: [{ label: "停牌", kind: "user" }],
    focusReason: "观察复牌后公告事项和成交恢复情况。",
    focusLogicChange: "今日停牌，盘中交易类观察条件不再适用。",
    marketSnapshot: market(null, {
      status: "normal",
      open: null,
      high: null,
      low: null,
      close: null,
      amplitude: null,
      volume: null,
      turnoverAmount: null,
      turnoverRate: null,
      totalMarketCap: "56亿元",
      floatMarketCap: "31亿元",
      recentPerformance: "停牌，暂无当日涨跌",
      relativeSectorStrength: "停牌不可比",
      relativeIndexStrength: "停牌不可比",
      statusMessage: "停牌股票保留历史记录，当前日内行情为空。"
    }),
    miniTrend: makeMiniTrend(8.5, [0.02, 0.0, -0.03, -0.02, 0.04, 0.05, 0.02, 0.0, null, null, null, null, null, null, null, null, null, null, null, null]),
    chartSet: chartSet(null, [], 0, 0, {
      status: "empty",
      message: "停牌样本没有当日分时或K线更新，保留历史自选股记录。"
    }),
    quantMetrics: quantMetrics({
      p5: nullValue(),
      p10: nullValue(),
      p20: nullValue(),
      distanceHigh20: nullValue(),
      industryStrength: nullValue(),
      indexStrength: nullValue(),
      volumePercentile: null,
      amountPercentile: null,
      turnoverPercentile: null,
      amplitudePercentile: null,
      closePosition: null,
      maxDrawdown: null
    }),
    abnormalEvents: [],
    infoTimeline: [],
    sentimentItems: [],
    todayReview: stockReview("停牌样本"),
    observations: observations.filter((item) => item.stockId === "gt-suspend"),
    reviewHistory: [],
    userNotes: ["模拟用户笔记：复牌后再更新观察条件。"]
  }
];

function nullValue(): string | null {
  return null;
}

const groupPerformance: GroupPerformance[] = [
  {
    name: "电力设备",
    kind: "sector",
    stockCount: 1,
    averageChange: 4.82,
    highlight: "受模拟重大合同公告影响，强于主要指数。"
  },
  {
    name: "AI应用",
    kind: "user-group",
    stockCount: 1,
    averageChange: -2.36,
    highlight: "出现板块上涨但个股走弱的背离。"
  },
  {
    name: "消费复苏",
    kind: "user-group",
    stockCount: 1,
    averageChange: 1.05,
    highlight: "尾盘成交活跃，但量能仍需连续验证。"
  }
];

const pendingTasks: PendingTask[] = [
  {
    id: "task-sentiment",
    label: "待处理舆情",
    count: 2,
    targetHref: "/information",
    status: "normal"
  },
  {
    id: "task-reviews",
    label: "未完成单股复盘",
    count: 1,
    targetHref: "/watchlist",
    status: "normal"
  },
  {
    id: "task-verify",
    label: "待核实信息",
    count: 2,
    targetHref: "/information",
    status: "normal"
  }
];

function cloneStocks(): Stock[] {
  return baseStocks.map((stock) => ({
    ...stock,
    personalGroups: [...stock.personalGroups],
    standardIndustries: stock.standardIndustries.map((item) => ({ ...item })),
    conceptBoards: stock.conceptBoards.map((item) => ({ ...item })),
    dynamicThemes: stock.dynamicThemes.map((item) => ({ ...item })),
    userTags: [...stock.userTags],
    marketSnapshot: { ...stock.marketSnapshot },
    miniTrend: stock.miniTrend.map((item) => ({ ...item })),
    chartSet: {
      ...stock.chartSet,
      intraday: stock.chartSet.intraday.map((item) => ({ ...item })),
      dailyK: stock.chartSet.dailyK.map((item) => ({ ...item }))
    },
    quantMetrics: stock.quantMetrics.map((item) => ({ ...item })),
    abnormalEvents: stock.abnormalEvents.map((event) => ({ ...event })),
    infoTimeline: stock.infoTimeline.map((item) => ({ ...item })),
    sentimentItems: stock.sentimentItems.map((item) => ({ ...item })),
    todayReview: { ...stock.todayReview, sourceLayers: [...stock.todayReview.sourceLayers] },
    observations: stock.observations.map((item) => ({ ...item })),
    reviewHistory: stock.reviewHistory.map((item) => ({ ...item })),
    userNotes: [...stock.userNotes]
  }));
}

function createBaseData(scenarioId: ScenarioId): GeniusMockData {
  const scenario = SCENARIOS.find((item) => item.id === scenarioId) ?? SCENARIOS[0];
  const stocks = cloneStocks();

  return {
    scenarioId,
    scenarioName: scenario.name,
    scenarioDescription: scenario.description,
    roleHint: scenarioId === "admin" ? "admin" : "user",
    tradeDate,
    generatedAt,
    sourceStatuses: baseSourceStatuses.map((status) => ({ ...status })),
    dashboardSummary: {
      total: stocks.length,
      rising: 3,
      falling: 1,
      suspended: 1,
      dataIssues: 0,
      averageChange: 1.05
    },
    stocks,
    majorAbnormalEvents: abnormalEvents.map((event) => ({ ...event })),
    majorInfoItems: infoItems.map((item) => ({ ...item })),
    groupPerformance: groupPerformance.map((item) => ({ ...item })),
    sentimentChanges: sentiments.map((item) => ({ ...item })),
    pendingVerification: sentiments.filter((item) => item.verifyStatus !== "verified"),
    overallReview: { ...successfulOverallReview },
    pendingTasks: pendingTasks.map((task) => ({ ...task })),
    observationsForToday: observations.map((item) => ({ ...item }))
  };
}

function applyStale(data: GeniusMockData): GeniusMockData {
  return {
    ...data,
    sourceStatuses: data.sourceStatuses.map((status) => {
      if (status.label === "日级行情") {
        return {
          ...status,
          status: "stale",
          updatedAt: staleUpdatedAt,
          message: "行情快照仍停留在上一交易日，请注意数据过期。"
        };
      }

      if (status.label === "舆情收件箱") {
        return {
          ...status,
          status: "syncing",
          message: "模拟同步中，已有舆情记录仍可查看。"
        };
      }

      return status;
    }),
    dashboardSummary: {
      ...data.dashboardSummary,
      dataIssues: 2
    },
    stocks: data.stocks.map((stock, index) => ({
      ...stock,
      tradeStatus: index < 2 ? "stale" : stock.tradeStatus,
      statusLabel: index < 2 ? "行情过期" : stock.statusLabel,
      marketSnapshot: {
        ...stock.marketSnapshot,
        status: index < 2 ? "stale" : stock.marketSnapshot.status,
        updatedAt: index < 2 ? staleUpdatedAt : stock.marketSnapshot.updatedAt,
        statusMessage:
          index < 2
            ? "该股票行情快照过期，仍展示最近一次可用模拟数据。"
            : stock.marketSnapshot.statusMessage
      },
      chartSet: {
        ...stock.chartSet,
        status: index < 2 ? "stale" : stock.chartSet.status,
        updatedAt: index < 2 ? staleUpdatedAt : stock.chartSet.updatedAt,
        message:
          index < 2
            ? "图表为最近一次可用模拟数据，数据状态为过期。"
            : stock.chartSet.message
      }
    }))
  };
}

function applyPartialFailure(data: GeniusMockData): GeniusMockData {
  return {
    ...data,
    sourceStatuses: data.sourceStatuses.map((status) => {
      if (status.label === "公告与资讯") {
        return {
          ...status,
          status: "partial-failure",
          message: "部分资讯源解析失败，已保留可用公告和原始链接。"
        };
      }

      if (status.label === "舆情收件箱") {
        return {
          ...status,
          status: "failure",
          message: "一个舆情来源完全失败，需要用户补充文字或截图说明。"
        };
      }

      return status;
    }),
    dashboardSummary: {
      ...data.dashboardSummary,
      dataIssues: 2
    },
    stocks: data.stocks.map((stock) =>
      stock.id === "gt-material"
        ? {
            ...stock,
            tradeStatus: "partial-failure",
            statusLabel: "部分数据失败",
            marketSnapshot: {
              ...stock.marketSnapshot,
              status: "partial-failure",
              volume: null,
              turnoverAmount: null,
              turnoverRate: null,
              statusMessage:
                "成交量、成交额和换手率缺失，价格字段仍来自最近可用模拟快照。"
            },
            chartSet: {
              ...stock.chartSet,
              status: "partial-failure",
              message: "分时价格可用，但成交量字段部分缺失。",
              intraday: stock.chartSet.intraday.map((item, index) => ({
                ...item,
                volume: index % 4 === 0 ? null : item.volume
              })),
              dailyK: stock.chartSet.dailyK.map((item, index) => ({
                ...item,
                volume: index > 45 ? null : item.volume
              }))
            },
            quantMetrics: stock.quantMetrics.map((metricItem) =>
              ["volPct", "amountPct", "turnoverPct"].includes(metricItem.id)
                ? {
                    ...metricItem,
                    value: null,
                    visualValue: null,
                    status: "量能相关字段缺失，暂不计算"
                  }
                : metricItem
            ),
            todayReview: {
              ...stock.todayReview,
              summary:
                "确定性价格字段可查看，但量能和舆情解析材料不完整。AI判断应降低置信度并列入待核实。"
            }
          }
        : stock
    ),
    majorInfoItems: [
      ...data.majorInfoItems,
      {
        id: "info-failed-001",
        stockIds: ["gt-material"],
        title: "材料价格传闻页面解析失败",
        sourceName: "模拟外部网页",
        sourceKind: "unverified-rumor",
        publishedAt: "未知",
        collectedAt: "2026-07-22 13:58",
        linkLabel: "原始链接待用户补充",
        summary: "无法自动获取完整内容，需用户补充摘要后再进入AI分析。",
        status: "failure"
      }
    ],
    pendingTasks: data.pendingTasks.map((task) =>
      task.id === "task-verify" ? { ...task, count: 3, status: "partial-failure" } : task
    )
  };
}

function applyAiFailure(data: GeniusMockData): GeniusMockData {
  const failedReview: ReviewSummary = {
    status: "failed",
    title: "AI复盘生成失败（模拟）",
    summary:
      "AI调用失败，页面仍展示行情、公告、舆情原始记录、K线、分时和程序计算指标。",
    modelName: "mock-openai-compatible-model",
    generatedAt: "2026-07-22 15:42",
    taskType: "复盘生成",
    isOriginalAiVersion: false,
    sourceLayers: ["客观行情", "外部事实", "用户笔记"],
    failureReason: "模拟错误：模型响应超时或结构化输出校验失败。"
  };

  return {
    ...data,
    sourceStatuses: data.sourceStatuses.map((status) =>
      status.label === "AI复盘"
        ? {
            ...status,
            status: "ai-failure",
            message: "AI调用失败，确定性行情、图表和程序计算指标不受影响。"
          }
        : status
    ),
    overallReview: failedReview,
    stocks: data.stocks.map((stock) => ({
      ...stock,
      todayReview: stock.id === "gt-solar" || stock.id === "gt-material" ? failedReview : stock.todayReview
    })),
    pendingTasks: data.pendingTasks.map((task) =>
      task.id === "task-reviews" ? { ...task, count: 3, status: "ai-failure" } : task
    )
  };
}

function applyEmptyUser(data: GeniusMockData): GeniusMockData {
  return {
    ...data,
    sourceStatuses: data.sourceStatuses.map((status) => ({
      ...status,
      status: status.label === "AI复盘" ? "empty" : status.status,
      message:
        status.label === "AI复盘"
          ? "暂无自选股，整体复盘尚未开始。"
          : status.message
    })),
    dashboardSummary: {
      total: 0,
      rising: 0,
      falling: 0,
      suspended: 0,
      dataIssues: 0,
      averageChange: null
    },
    stocks: [],
    majorAbnormalEvents: [],
    majorInfoItems: [],
    groupPerformance: [],
    sentimentChanges: [],
    pendingVerification: [],
    overallReview: {
      status: "not-started",
      title: "暂无整体复盘",
      summary: "新用户还没有自选股，请先添加股票或查看CSV导入说明。",
      modelName: "未调用",
      generatedAt: "未生成",
      taskType: "整体复盘生成",
      isOriginalAiVersion: false,
      sourceLayers: []
    },
    pendingTasks: [
      {
        id: "task-empty-watchlist",
        label: "待添加自选股",
        count: 1,
        targetHref: "/watchlist",
        status: "empty"
      }
    ],
    observationsForToday: []
  };
}

export function getScenarioData(scenarioId: ScenarioId): GeniusMockData {
  const data = createBaseData(scenarioId);

  if (scenarioId === "stale") {
    return applyStale(data);
  }

  if (scenarioId === "partial-failure") {
    return applyPartialFailure(data);
  }

  if (scenarioId === "ai-failure") {
    return applyAiFailure(data);
  }

  if (scenarioId === "empty-user") {
    return applyEmptyUser(data);
  }

  if (scenarioId === "admin") {
    return {
      ...data,
      sourceStatuses: data.sourceStatuses.map((status) => ({
        ...status,
        message: `${status.message} 管理员Mock身份仅改变页面可见入口。`
      }))
    };
  }

  return data;
}
