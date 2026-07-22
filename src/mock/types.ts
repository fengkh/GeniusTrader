import type { LucideIcon } from "lucide-react";

export type ScenarioId =
  | "normal"
  | "stale"
  | "partial-failure"
  | "ai-failure"
  | "empty-user"
  | "admin";

export type MockRole = "user" | "admin";

export type DataStatus =
  | "normal"
  | "syncing"
  | "stale"
  | "partial-failure"
  | "failure"
  | "empty"
  | "ai-failure";

export type StockTradeStatus =
  | "normal"
  | "suspended"
  | "stale"
  | "partial-failure";

export type SourceKind =
  | "official-disclosure"
  | "authoritative-news"
  | "platform-opinion"
  | "unverified-rumor"
  | "user-note";

export type ObservationStatus =
  | "occurred"
  | "not-occurred"
  | "partially-occurred"
  | "unknown"
  | "not-applicable";

export type BoardType = "standard-industry" | "concept-board" | "dynamic-theme";

export type ChartDataStatus = "normal" | "stale" | "partial-failure" | "empty";

export type QuantVisualType = "percentile" | "strength" | "trend";

export interface ScenarioOption {
  id: ScenarioId;
  name: string;
  description: string;
}

export interface NavigationItem {
  href: string;
  label: string;
  shortLabel?: string;
  icon: LucideIcon;
}

export interface DataSourceStatus {
  label: string;
  source: string;
  status: DataStatus;
  updatedAt: string;
  message: string;
}

export interface MarketSnapshot {
  source: string;
  dataTime: string;
  updatedAt: string;
  status: DataStatus;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  changePercent: number | null;
  amplitude: number | null;
  volume: string | null;
  turnoverAmount: string | null;
  turnoverRate: number | null;
  totalMarketCap: string | null;
  floatMarketCap: string | null;
  recentPerformance: string;
  relativeSectorStrength: string;
  relativeIndexStrength: string;
  statusMessage?: string;
}

export interface ClassificationTag {
  label: string;
  kind: "standard" | "suggestion" | "user";
  detail?: string;
}

export interface BoardTag {
  name: string;
  type: BoardType;
  source: string;
  updatedAt: string;
}

export interface AbnormalEvent {
  id: string;
  stockId: string;
  stockName: string;
  type: string;
  severity: "high" | "medium" | "low";
  ruleCategory: "official-fixed" | "historical-percentile" | "relative";
  evidence: string;
  benchmark: string;
  actualData: string;
  ruleVersion: string;
  dataTime: string;
}

export interface InfoItem {
  id: string;
  stockIds: string[];
  title: string;
  sourceName: string;
  sourceKind: SourceKind;
  publishedAt: string;
  collectedAt: string;
  linkLabel: string;
  summary: string;
  status: DataStatus;
}

export interface SentimentItem {
  id: string;
  stockId: string;
  platform: string;
  author: string;
  sourceKind: SourceKind;
  title: string;
  heatChange: string;
  summary: string;
  verifyStatus: "pending" | "verified" | "rejected" | "needs-user-input";
  collectedAt: string;
}

export interface ReviewSummary {
  status: "success" | "failed" | "manual-edited" | "not-started";
  title: string;
  summary: string;
  modelName: string;
  generatedAt: string;
  taskType: string;
  isOriginalAiVersion: boolean;
  sourceLayers: string[];
  manualRevision?: string;
  failureReason?: string;
}

export interface ObservationCondition {
  id: string;
  stockId?: string;
  stockName?: string;
  content: string;
  status: ObservationStatus;
  evidence: string;
  reviewDate: string;
  verificationDate: string;
}

export interface ReviewVersion {
  id: string;
  date: string;
  type: "ai-original" | "manual-revision";
  title: string;
  summary: string;
}

export interface MiniTrendPoint {
  day: string;
  close: number | null;
}

export interface IntradayPoint {
  time: number;
  price: number;
  avgPrice: number;
  volume: number | null;
}

export interface DailyKLinePoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  ma5?: number;
  ma10?: number;
  ma20?: number;
}

export interface ChartSet {
  status: ChartDataStatus;
  dataTime: string;
  updatedAt: string;
  message?: string;
  previousClose: number | null;
  intraday: IntradayPoint[];
  dailyK: DailyKLinePoint[];
}

export interface QuantMetric {
  id: string;
  label: string;
  value: string | null;
  benchmark: string;
  visualType: QuantVisualType;
  visualValue: number | null;
  direction?: "up" | "down" | "flat";
  status: string;
  dataTime: string;
}

export interface Stock {
  id: string;
  code: string;
  name: string;
  market: string;
  tradeStatus: StockTradeStatus;
  statusLabel: string;
  personalGroups: string[];
  standardIndustries: BoardTag[];
  conceptBoards: BoardTag[];
  dynamicThemes: BoardTag[];
  userTags: ClassificationTag[];
  focusReason: string;
  focusLogicChange: string;
  marketSnapshot: MarketSnapshot;
  miniTrend: MiniTrendPoint[];
  chartSet: ChartSet;
  quantMetrics: QuantMetric[];
  abnormalEvents: AbnormalEvent[];
  infoTimeline: InfoItem[];
  sentimentItems: SentimentItem[];
  todayReview: ReviewSummary;
  observations: ObservationCondition[];
  reviewHistory: ReviewVersion[];
  userNotes: string[];
}

export interface DashboardSummary {
  total: number;
  rising: number;
  falling: number;
  suspended: number;
  dataIssues: number;
  averageChange: number | null;
}

export interface GroupPerformance {
  name: string;
  kind: "sector" | "user-group";
  stockCount: number;
  averageChange: number | null;
  highlight: string;
}

export interface PendingTask {
  id: string;
  label: string;
  count: number;
  targetHref: string;
  status: DataStatus;
}

export interface GeniusMockData {
  scenarioId: ScenarioId;
  scenarioName: string;
  scenarioDescription: string;
  roleHint: MockRole;
  tradeDate: string;
  generatedAt: string;
  sourceStatuses: DataSourceStatus[];
  dashboardSummary: DashboardSummary;
  stocks: Stock[];
  majorAbnormalEvents: AbnormalEvent[];
  majorInfoItems: InfoItem[];
  groupPerformance: GroupPerformance[];
  sentimentChanges: SentimentItem[];
  pendingVerification: SentimentItem[];
  overallReview: ReviewSummary;
  pendingTasks: PendingTask[];
  observationsForToday: ObservationCondition[];
}
