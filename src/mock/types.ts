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

export type CapabilityStatus =
  | "complete"
  | "partial-available"
  | "sample-calculation"
  | "provider-degraded"
  | "empty";

export type MarketReviewStatus =
  | "complete"
  | "partial"
  | "provider-degraded"
  | "ai-summary-failed"
  | "failed"
  | "not-generated";

export type BoardStage =
  | "new-start"
  | "accelerating"
  | "sustained-strong"
  | "high-divergence"
  | "retreat"
  | "repair"
  | "insufficient-data";

export type CandidateSource = "program-ranking" | "ai-explanation" | "rule-template";

export type ValuationMethod =
  | "pe-stable"
  | "pb-roe-bank"
  | "ps-growth"
  | "dividend"
  | "cyclical-low-confidence"
  | "unavailable";

export type ValuationConfidence = "high" | "medium" | "low" | "unavailable";

export type ValuationAvailability = "available" | "partial" | "unavailable" | "stale";

export type NotificationSeverity = "info" | "notice" | "important" | "critical";

export type NotificationType =
  | "daily-review"
  | "announcement"
  | "anomaly"
  | "observation"
  | "valuation"
  | "system";

export type NotificationState =
  | "unread"
  | "read"
  | "archived"
  | "expired"
  | "data-source-degraded"
  | "ai-summary-failed"
  | "wechat-failed";

export type NotificationFrequency = "immediate" | "daily-digest" | "weekly-digest" | "disabled";

export type NotificationChannel =
  | "in_app"
  | "wechat_official_account"
  | "email"
  | "web_push"
  | "mobile_push";

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

export interface MarketBreadth {
  rising: number;
  falling: number;
  flat: number;
  suspended: number;
  limitUp: number;
  limitDown: number;
  medianChangePercent: number | null;
  ma20AboveRatio: number | null;
  totalAmount: string | null;
  amountChangePercent: number | null;
  newHigh20: number;
  newLow20: number;
}

export interface IndexPerformance {
  code: string;
  name: string;
  changePercent: number | null;
  amount: string | null;
  style: string;
  note: string;
}

export interface BoardHeatComponent {
  label: string;
  value: string | null;
  benchmark: string;
  score: number | null;
  note: string;
}

export interface BoardHotStock {
  stockId?: string;
  code: string;
  name: string;
  change1d: number | null;
  change3d: number | null;
  change5d: number | null;
  consecutiveRisingDays: number | null;
  relativeBoardStrength: string | null;
  volumePercentile: number | null;
  amountPercentile: number | null;
  turnoverPercentile: number | null;
  nearHigh20: boolean | null;
  roleSuggestion: string;
  roleBasis: string;
  confidence: ValuationConfidence;
  coreDriver: string;
  riskPenalty: string;
  updatedAt: string;
}

export interface WatchCandidate {
  id: string;
  subjectType: "board" | "stock";
  subjectName: string;
  subjectCode?: string;
  source: CandidateSource;
  reason: string;
  stage: BoardStage | "stock-observation";
  continuationConditions: string[];
  invalidationConditions: string[];
  riskNotes: string[];
  pendingVerification: string[];
  dataCompleteness: string;
  targetHref: string;
}

export interface BoardHeatRecord {
  id: string;
  name: string;
  type: BoardType;
  change1d: number | null;
  change3d: number | null;
  change5d: number | null;
  consecutiveRisingDays: number | null;
  risingRatio: number | null;
  limitUpCount: number | null;
  amountPercentile: number | null;
  relativeIndexStrength: string | null;
  stage: BoardStage;
  ranking: number;
  rankingChange: number | null;
  totalScore: number | null;
  dataCompleteness: string;
  dataStatus: DataStatus;
  components: BoardHeatComponent[];
  hotStocks: BoardHotStock[];
  trendSummary: string;
  continuity: string;
  leadingStocks: string[];
  followUpCandidates: string[];
  riskStocks: string[];
  catalyst: string;
  pendingVerification: string[];
  dataGaps: string[];
  updatedAt: string;
}

export interface MarketDailyReview {
  id: string;
  date: string;
  status: MarketReviewStatus;
  capabilityStatus: CapabilityStatus;
  generatedAt: string;
  dataStatus: DataStatus;
  dataSources: string[];
  capabilityNotes: string[];
  overview: string;
  breadth: MarketBreadth;
  indexPerformance: IndexPerformance[];
  hotBoards: BoardHeatRecord[];
  continuousStrongBoards: BoardHeatRecord[];
  retreatBoards: BoardHeatRecord[];
  boardCandidates: WatchCandidate[];
  stockCandidates: WatchCandidate[];
  aiSummary: ReviewSummary;
}

export interface ValuationScenario {
  name: "pessimistic" | "base" | "optimistic";
  label: string;
  priceRange: string;
  impliedSpace: string;
  assumptions: string[];
}

export interface StockValuation {
  availability: ValuationAvailability;
  method: ValuationMethod;
  methodLabel: string;
  valuationDate: string;
  financialPeriod: string;
  currentPrice: string | null;
  marketCap: string | null;
  pe: string | null;
  pb: string | null;
  ps: string | null;
  dividendYield?: string | null;
  confidence: ValuationConfidence;
  modelLabel: string;
  pricePosition: string | null;
  scenarios: ValuationScenario[];
  assumptions: string[];
  missingInputs: string[];
  dataStatus: DataStatus;
  dataTime: string;
  source: string;
  explanation: string;
  boundaryNote: string;
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
  valuation?: StockValuation;
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

export interface BusinessEventMock {
  id: string;
  eventType: string;
  category:
    | "market-review"
    | "user-review"
    | "watchlist-quote"
    | "announcement-info"
    | "observation"
    | "valuation"
    | "system";
  subjectId: string;
  subjectName: string;
  businessDate: string;
  triggerModule: string;
  severity: NotificationSeverity;
  defaultFrequency: NotificationFrequency;
  inAppDefault: boolean;
  wechatAllowed: boolean;
  digestIncluded: boolean;
  dedupeKey: string;
  targetHref: string;
}

export interface NotificationMock {
  id: string;
  type: NotificationType;
  severity: NotificationSeverity;
  state: NotificationState;
  title: string;
  summary: string;
  createdAt: string;
  targetHref: string;
  dataStatus: DataStatus;
  serviceStatus: string;
  sourceEventId: string;
}

export interface NotificationPreferenceMock {
  id: string;
  channel: NotificationChannel;
  eventType: string;
  enabled: boolean;
  frequency: NotificationFrequency;
  minSeverity: NotificationSeverity;
  digestIncluded: boolean;
  quietHours?: string;
}

export interface ExternalIdentityMock {
  id: string;
  provider: "wechat_official_account";
  providerAccountId: string;
  providerUserId: string;
  unionId?: string;
  bindStatus: "unbound" | "bound-subscribed" | "bound-unsubscribed" | "authorization-invalid" | "channel-unavailable";
  boundAt?: string;
  updatedAt: string;
}

export interface NotificationDeliveryMock {
  id: string;
  notificationId: string;
  channel: NotificationChannel;
  status: "pending" | "sent" | "failed" | "skipped" | "blocked";
  idempotencyKey: string;
  attemptedAt: string;
  errorCode?: string;
  message: string;
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
  marketDailyReview: MarketDailyReview;
  businessEvents: BusinessEventMock[];
  notifications: NotificationMock[];
  notificationPreferences: NotificationPreferenceMock[];
  externalIdentities: ExternalIdentityMock[];
  notificationDeliveries: NotificationDeliveryMock[];
}
