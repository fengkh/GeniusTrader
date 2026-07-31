export type UUID = string;

export type UserRole = "admin" | "user";

export interface CurrentUser {
  id: UUID;
  username: string;
  display_name: string;
  role: UserRole;
  status: string;
  must_change_password: boolean;
}

export interface Page<T> {
  items: T[];
  limit: number;
  offset: number;
  total: number;
}

export interface ApiMessage {
  message: string;
}

export interface ExternalSource {
  id: UUID;
  source_code: string;
  display_name: string;
  publisher_name: string;
  source_category: string;
  authority_level: string;
  source_tier: string;
  jurisdiction: string | null;
  country_code: string | null;
  region_code: string | null;
  city_code: string | null;
  official_domain: string | null;
  access_mode: string;
  content_language: string;
  provider_adapter: string | null;
  authorization_status: string;
  redistribution_status: string;
  commercial_use_status: string;
  legal_review_status: string;
  health_status: string;
  enabled: boolean;
  experimental: boolean;
  limitations: string[];
  created_at: string;
  updated_at: string;
}

export interface AnnouncementProvider {
  source_code: string;
  provider_adapter: string;
  implemented: boolean;
  enabled_by_config: boolean;
  experimental: boolean;
  experimental_limited: boolean;
  capabilities: string[];
  limitations: string[];
  limits: {
    max_symbols_per_run: number;
    max_records_per_run: number;
    sync_lookback_days: number;
  };
}

export interface FutureSourceGroup {
  group: string;
  examples: string[];
  status: string;
}

export interface LoginResponse {
  user: CurrentUser;
  must_change_password: boolean;
}

export interface AuthUserResponse {
  user: CurrentUser;
}

export interface AIProvider {
  id: UUID;
  provider_name: string;
  api_style: "openai_chat_completions";
  base_url: string;
  model_name: string;
  enabled: boolean;
  api_key_configured: boolean;
  api_key_masked: string | null;
  request_timeout_seconds: number | null;
  max_output_tokens: number | null;
  last_test_status: string | null;
  last_tested_at: string | null;
  last_error_code: string | null;
  created_at: string;
  updated_at: string;
}

export interface AIProviderPayload {
  provider_name: string;
  base_url: string;
  model_name: string;
  api_key?: string;
  enabled: boolean;
  request_timeout_seconds?: number | null;
  max_output_tokens?: number | null;
}

export interface AIProviderTestResult {
  provider_id: UUID;
  status: string;
  error_code: string | null;
  tested_at: string;
}

export type InformationSourceType =
  | "announcement"
  | "news"
  | "social"
  | "analyst_opinion"
  | "user_note"
  | "unknown";

export interface InformationSummary {
  id: UUID;
  input_type: "manual_text" | "public_url";
  status: string;
  source_type: InformationSourceType;
  title: string | null;
  user_note: string | null;
  is_important: boolean;
  is_read: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InformationSource {
  id: UUID;
  original_url: string | null;
  normalized_url: string | null;
  source_name: string | null;
  author: string | null;
  published_at: string | null;
  fetched_at: string | null;
  http_status: number | null;
  content_type: string | null;
  fetch_status: string;
}

export interface InformationContent {
  id: UUID;
  content_version: number;
  content_origin: string;
  extracted_title: string | null;
  extracted_text: string;
  content_hash: string;
  character_count: number;
  extraction_method: string;
  extraction_status: string;
  created_at: string;
}

export interface InformationAnalysis {
  id: UUID;
  version_number: number;
  schema_version: string;
  prompt_version: string;
  provider_config_id: UUID | null;
  model_name: string | null;
  analysis_status: string;
  structured_result: Record<string, unknown>;
  input_content_hash: string | null;
  created_at: string;
}

export interface InformationStockRelation {
  id: UUID;
  stock_id: UUID;
  relation_origin: string;
  relation_status: "suggested" | "confirmed" | "rejected";
  relation_type: string;
  confidence: number | null;
  evidence_text: string | null;
  reviewed_at: string | null;
}

export interface InformationEntityMention {
  id: UUID;
  entity_type: string;
  entity_name: string;
  relation: string | null;
  confidence: number | null;
  evidence_text: string | null;
  origin: string;
  status: string;
}

export interface VerificationItem {
  id: UUID;
  description: string;
  verification_type: string;
  status: string;
  priority: string | null;
  evidence_needed: string | null;
  user_note: string | null;
  resolved_at: string | null;
}

export interface InformationDetail extends InformationSummary {
  sources: InformationSource[];
  current_content: InformationContent | null;
  latest_analysis: InformationAnalysis | null;
  analysis_versions: InformationAnalysis[];
  stock_relations: InformationStockRelation[];
  entity_mentions: InformationEntityMention[];
  verification_items: VerificationItem[];
  latest_ai_task_status: string | null;
}

export interface StockRead {
  id: UUID;
  symbol: string;
  code: string;
  exchange: string;
  name: string;
  market: string;
  board: string;
  security_type: string;
  short_name: string;
  full_name: string | null;
  english_name: string | null;
  listing_status: string;
  listed_at: string | null;
  delisted_at: string | null;
  aliases: string[];
  pinyin: string | null;
  pinyin_initials: string | null;
  source_code: string;
  source_record_id: string | null;
  source_updated_at: string | null;
  last_synced_at: string | null;
  data_completeness: string;
  is_searchable: boolean;
  list_status: string;
  list_date: string | null;
  delist_date: string | null;
  currency: string;
  data_source: string;
  created_at: string;
  updated_at: string;
}

export interface WatchlistGroupRead {
  id: UUID;
  name: string;
  sort_order: number;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserTagRead {
  id: UUID;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface WatchlistItemRead {
  id: UUID;
  stock: StockRead;
  group: WatchlistGroupRead | null;
  tags: UserTagRead[];
  attention_reason: string | null;
  notes: string | null;
  sort_order: number;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WatchlistItemPayload {
  stock_id: UUID;
  group_id?: UUID | null;
  attention_reason?: string | null;
  notes?: string | null;
  tag_ids?: UUID[];
}

export interface WatchlistItemUpdatePayload {
  group_id?: UUID | null;
  attention_reason?: string | null;
  notes?: string | null;
  sort_order?: number | null;
  tag_ids?: UUID[] | null;
}

export interface SecurityMasterProvider {
  source_code: string;
  display_name: string;
  implemented: boolean;
  enabled_by_config: boolean;
  official: boolean;
  capabilities: string[];
  limitations: string[];
}

export interface SecurityMasterSyncRun {
  id: UUID;
  triggered_by_user_id: UUID;
  source_code: string;
  status: string;
  exchanges: string[];
  request_count: number;
  received_count: number;
  created_count: number;
  updated_count: number;
  unchanged_count: number;
  deactivated_count: number;
  failure_count: number;
  started_at: string;
  completed_at: string | null;
  error_code: string | null;
  error_summary: string | null;
  metrics: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SecurityMasterStatus {
  total_count: number;
  by_exchange: Record<string, number>;
  by_board: Record<string, number>;
  active_count: number;
  development_seed_count: number;
  seed_covered_count: number;
  last_synced_at: string | null;
  sources: string[];
  data_gaps: string[];
  latest_sync_status: string | null;
  latest_sync_run: SecurityMasterSyncRun | null;
}

export type DecimalValue = string | number;

export interface MarketDataProvider {
  source_code: string;
  display_name: string;
  implemented: boolean;
  enabled_by_config: boolean;
  source_type: string;
  authorization_status: string;
  usage_scope: string[];
  production_enabled: boolean;
  capabilities: string[];
  limitations: string[];
}

export interface MarketDataSource {
  id: UUID;
  source_code: string;
  display_name: string;
  source_type: string;
  authorization_status: string;
  usage_scope: string[];
  production_enabled: boolean;
  capabilities: string[];
  last_health_status: string;
  last_health_checked_at: string | null;
  limitations: string[];
  created_at: string;
  updated_at: string;
}

export interface MarketDataSyncRun {
  id: UUID;
  source_code: string;
  trigger_type: string;
  sync_mode: string;
  status: string;
  requested_trade_date: string | null;
  resolved_trade_date: string | null;
  lookback_days: number;
  requested_symbol_count: number;
  received_count: number;
  created_count: number;
  updated_count: number;
  unchanged_count: number;
  failure_count: number;
  error_code: string | null;
  error_summary: string | null;
  metrics: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarketDataStatus {
  sources: MarketDataSource[];
  providers: MarketDataProvider[];
  latest_trade_date: string | null;
  latest_source_code: string | null;
  latest_fetched_at: string | null;
  latest_sync_status: string | null;
  latest_sync_run: MarketDataSyncRun | null;
  production_authorization_pending: boolean;
  user_notice: string;
  data_gaps: string[];
}

export interface StockDailySnapshot {
  id: UUID;
  stock_id: UUID;
  source_code: string;
  trade_date: string;
  open: DecimalValue | null;
  high: DecimalValue | null;
  low: DecimalValue | null;
  close: DecimalValue | null;
  pre_close: DecimalValue | null;
  change: DecimalValue | null;
  pct_change: DecimalValue | null;
  volume: DecimalValue | null;
  amount: DecimalValue | null;
  turnover_rate: DecimalValue | null;
  volume_ratio: DecimalValue | null;
  total_market_value: DecimalValue | null;
  circulating_market_value: DecimalValue | null;
  pe_ttm: DecimalValue | null;
  pb: DecimalValue | null;
  is_trading: boolean | null;
  data_completeness: string;
  source_updated_at: string | null;
  fetched_at: string;
  limitations: string[];
  created_at: string;
  updated_at: string;
}

export type MarketSnapshotStatus = "available" | "stale" | "source_lag" | "partial" | "unavailable";

export interface StockMarketSnapshot {
  stock: StockRead;
  snapshot: StockDailySnapshot | null;
  status: MarketSnapshotStatus;
  latest_completed_trade_date: string | null;
  source_code: string | null;
  authorization_status: string | null;
  production_enabled: boolean;
  data_completeness: string | null;
  missing_fields: string[];
  message: string;
  unit_notes: Record<string, string>;
}

export interface WatchlistMarketSnapshot {
  watchlist_item_id: UUID;
  stock: StockRead;
  snapshot: StockDailySnapshot | null;
  status: MarketSnapshotStatus;
  data_completeness: string | null;
  missing_fields: string[];
  message: string;
}

export type ResearchTaskType = "verification" | "observation" | "follow_up" | "missing_document" | "user_note";
export type ResearchTaskStatus =
  | "pending"
  | "monitoring"
  | "confirmed"
  | "disproved"
  | "partially_confirmed"
  | "unable_to_determine"
  | "no_longer_applicable"
  | "dismissed";
export type ResearchTaskPriority = "low" | "medium" | "high";
export type ResearchTaskSourceType = "user" | "information_analysis" | "daily_review" | "announcement" | "system_rule";

export interface ResearchTaskUpdate {
  id: UUID;
  task_id: UUID;
  user_id: UUID;
  previous_status: string | null;
  new_status: string;
  note: string | null;
  evidence_information_item_id: UUID | null;
  evidence_analysis_version_id: UUID | null;
  evidence_daily_review_version_id: UUID | null;
  created_by: string;
  created_at: string;
}

export interface ResearchTask {
  id: UUID;
  user_id: UUID;
  stock_id: UUID | null;
  stock: StockRead | null;
  task_type: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  source_type: string;
  source_information_item_id: UUID | null;
  source_analysis_version_id: UUID | null;
  source_daily_review_id: UUID | null;
  source_daily_review_version_id: UUID | null;
  due_date: string | null;
  current_evidence_summary: string | null;
  resolution_note: string | null;
  created_by: string;
  deduplication_key: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  updates: ResearchTaskUpdate[];
}

export interface ResearchTaskPayload {
  stock_id?: UUID | null;
  task_type?: ResearchTaskType;
  title: string;
  description: string;
  status?: ResearchTaskStatus;
  priority?: ResearchTaskPriority;
  source_type?: ResearchTaskSourceType;
  source_information_item_id?: UUID | null;
  source_analysis_version_id?: UUID | null;
  source_daily_review_id?: UUID | null;
  source_daily_review_version_id?: UUID | null;
  due_date?: string | null;
  current_evidence_summary?: string | null;
  suggestion_identifier?: string | null;
}

export interface ResearchTaskStatusPayload {
  status: ResearchTaskStatus;
  note?: string | null;
  evidence_information_item_id?: UUID | null;
  evidence_analysis_version_id?: UUID | null;
  evidence_daily_review_version_id?: UUID | null;
}

export interface TodayOverviewStats {
  business_date: string;
  watchlist_count: number;
  market_trade_date: string | null;
  market_snapshot_count: number;
  market_data_available_count: number;
  market_data_unavailable_count: number;
  gainers_count: number;
  decliners_count: number;
  unchanged_count: number;
  stocks_with_new_information: number;
  new_announcement_candidate_count: number;
  pending_announcement_candidate_count: number;
  stale_review_count: number;
  open_research_task_count: number;
  due_observation_count: number;
  information_needing_analysis_count: number;
  latest_review_status: string | null;
  market_data_status: string;
}

export interface PriorityStock {
  stock_id: UUID;
  symbol: string;
  name: string;
  priority_score: number;
  priority_reasons: string[];
  new_information_count: number;
  pending_candidate_count: number;
  open_task_count: number;
  due_observation_count: number;
  review_status: string | null;
  close: DecimalValue | null;
  pct_change: DecimalValue | null;
  amount: DecimalValue | null;
  turnover_rate: DecimalValue | null;
  trade_date: string | null;
  source_code: string | null;
  freshness_status: MarketSnapshotStatus | null;
  latest_market_snapshot: WatchlistMarketSnapshot | null;
}

export interface TodayActionItem {
  count: number;
  target_url: string;
  severity: "info" | "notice" | "important";
  title: string;
}

export interface TodayObservationCondition {
  task_id: UUID;
  stock: StockRead | null;
  title: string;
  due_date: string | null;
  status: string;
  source_review: string | null;
}

export interface LatestReview {
  review_id: UUID | null;
  review_date: string | null;
  status: string | null;
  stale: boolean;
  version: number | null;
  generation_in_progress: boolean;
}

export interface TodayOverview {
  overview: TodayOverviewStats;
  priority_stocks: PriorityStock[];
  action_items: TodayActionItem[];
  observation_conditions: TodayObservationCondition[];
  latest_review: LatestReview;
}

export interface WatchlistScannerRow {
  watchlist_item_id: UUID;
  stock_id: UUID;
  symbol: string;
  name: string;
  exchange: string;
  group: WatchlistGroupRead | null;
  tags: UserTagRead[];
  focus_reason: string | null;
  latest_market_snapshot: WatchlistMarketSnapshot | null;
  trade_date: string | null;
  close: DecimalValue | null;
  change: DecimalValue | null;
  pct_change: DecimalValue | null;
  volume: DecimalValue | null;
  amount: DecimalValue | null;
  turnover_rate: DecimalValue | null;
  source_code: string | null;
  freshness_status: MarketSnapshotStatus | null;
  new_information_count: number;
  official_announcement_count_7d: number;
  pending_candidate_count: number;
  open_verification_count: number;
  open_observation_count: number;
  high_priority_task_count: number;
  review_status: string | null;
  latest_review_date: string | null;
  stale: boolean;
  last_information_at: string | null;
  attention_score: number;
  attention_reasons: string[];
}

export interface WatchlistScanner {
  items: WatchlistScannerRow[];
  total: number;
}

export interface WatchlistProfile {
  group: WatchlistGroupRead | null;
  tags: UserTagRead[];
  focus_reason: string | null;
  user_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface StockCurrentState {
  new_information_count: number;
  pending_candidate_count: number;
  open_task_count: number;
  observation_count: number;
  latest_review_status: string | null;
  stale: boolean;
}

export interface OfficialInformation {
  id: UUID;
  title: string | null;
  source_type: string;
  status: string;
  is_important: boolean;
  created_at: string;
  target_url: string;
}

export interface TimelineEntry {
  event_type: string;
  occurred_at: string;
  title: string;
  summary: string;
  source_label: string;
  target_url: string;
  confidence: string | null;
  data_completeness: string | null;
  created_by: string;
}

export interface ReviewHistory {
  review_id: UUID;
  review_date: string;
  status: string;
  stale: boolean;
  version_count: number;
  latest_version: number | null;
  target_url: string;
}

export interface StockResearchDossier {
  identity: StockRead;
  watchlist_profile: WatchlistProfile;
  market_snapshot: StockMarketSnapshot;
  current_state: StockCurrentState;
  official_information: OfficialInformation[];
  research_tasks: ResearchTask[];
  timeline: TimelineEntry[];
  review_history: ReviewHistory[];
  data_boundaries: string[];
}

export interface MarketDataSyncPayload {
  source_code?: string;
  sync_mode?: "latest_completed_trade_day" | "selected_trade_date" | "optional_backfill";
  trade_date?: string | null;
  lookback_days?: number;
  stock_ids?: UUID[];
  use_current_watchlist?: boolean;
  dry_run?: boolean;
}

export interface ProviderSyncRun {
  id: UUID;
  external_source_id: UUID;
  capability: string;
  triggered_by_user_id: UUID;
  status: string;
  date_from: string;
  date_to: string;
  requested_symbols: string[];
  request_count: number;
  success_count: number;
  failure_count: number;
  record_count: number;
  candidate_count: number;
  created_record_count: number;
  updated_record_count: number;
  duplicate_record_count: number;
  error_code: string | null;
  error_summary: string | null;
  metrics: Record<string, unknown>;
  provider_metadata: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
  created_at: string;
  experimental_notice: string;
}

export interface AnnouncementCandidateSummary {
  id: UUID;
  announcement_record_id: UUID;
  sync_run_id: UUID | null;
  status: string;
  match_type: string;
  matched_stock_id: UUID | null;
  matched_watchlist_item_id: UUID | null;
  title: string;
  announcement_type: string;
  announcement_type_confidence: number;
  published_at: string | null;
  company_name: string | null;
  stock_symbols: string[];
  source_code: string;
  source_display_name: string;
  source_tier: string;
  authorization_status: string;
  data_completeness: string;
  missing_fields: string[];
  is_pdf: boolean;
  document_url: string | null;
  document_extract_status: string;
  document_page_count: number | null;
  document_character_count: number | null;
  created_at: string;
  updated_at: string;
  experimental_notice: string;
}

export interface AnnouncementCandidateDetail extends AnnouncementCandidateSummary {
  normalized_title: string;
  announcement_type_basis: Record<string, unknown>;
  exchange: string | null;
  source_page_url: string;
  attachment_urls: string[];
  is_correction: boolean;
  corrected_announcement_id: string | null;
  raw_metadata_hash: string;
  deduplication_key: string;
  fetched_at: string;
  first_seen_at: string;
  last_seen_at: string;
  source_authority_level: string;
  source_access_mode: string;
  redistribution_status: string;
  commercial_use_status: string;
  legal_review_status: string;
  source_limitations: string[];
  match_evidence: Record<string, unknown>;
  document_extracted_at: string | null;
  document_limitations: string[];
  reviewed_at: string | null;
  dismissed_at: string | null;
  imported_at: string | null;
  information_item_id: UUID | null;
  detail_notice: string;
}

export interface AnnouncementDocumentExtractResult {
  candidate_id: UUID;
  document_extract_status: string;
  document_extracted_at: string | null;
  page_count: number | null;
  character_count: number | null;
  limitations: string[];
  experimental_notice: string;
}

export interface AnnouncementImportResult {
  candidate_id: UUID;
  information_item_id: UUID;
  import_mode: string;
  already_imported: boolean;
  created_at: string;
}

export type DailyReviewStatus = "complete" | "partial" | "empty" | "failed" | "stale";
export type DailyReviewGenerationMode =
  | "rules_only"
  | "rules_and_ai"
  | "rules_with_ai_fallback";

export interface DailyReviewVersion {
  id: UUID;
  daily_review_id: UUID;
  version_number: number;
  status: DailyReviewStatus;
  generation_mode: DailyReviewGenerationMode;
  ai_task_id: UUID | null;
  rule_snapshot: Record<string, unknown>;
  ai_structured_result: Record<string, unknown> | null;
  ai_narrative: string | null;
  input_fingerprint: string;
  prompt_version: string | null;
  schema_version: string;
  provider_config_id: UUID | null;
  model_name: string | null;
  generated_at: string;
  created_at: string;
}

export interface DailyReviewSummary {
  id: UUID;
  user_id: UUID;
  review_date: string;
  status: DailyReviewStatus;
  current_version_id: UUID | null;
  current_version_number: number | null;
  generation_mode: DailyReviewGenerationMode | null;
  input_fingerprint: string | null;
  generated_at: string | null;
  stale_at: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
  overview: Record<string, unknown>;
  ai_available: boolean;
  generation_in_progress: boolean;
  generation_task_id: UUID | null;
  generation_task_status: string | null;
}

export interface DailyReviewDetail extends DailyReviewSummary {
  current_version: DailyReviewVersion | null;
  versions: DailyReviewVersion[];
}

export interface DailyReviewGeneratePayload {
  review_date?: string | null;
  force?: boolean;
  use_ai?: boolean;
}

export type NotificationEventType =
  | "user_daily_review.generated"
  | "user_daily_review.partial"
  | "user_daily_review.failed"
  | "user_daily_review.became_stale"
  | "information.high_priority_detected"
  | "information.verification_required"
  | "ai_task.failed"
  | "research_task.created"
  | "research_task.status_changed"
  | "research_task.due"
  | "observation_condition.due";

export type InAppNotificationSeverity = "info" | "notice" | "important";
export type InAppNotificationStatus = "unread" | "read" | "archived" | "expired";
export type NotificationAction = "mark_read" | "mark_unread" | "archive" | "unarchive";
export type NotificationFrequency = "immediate" | "daily_digest" | "disabled";

export interface InAppNotification {
  id: UUID;
  user_id: UUID;
  event_id: UUID;
  event_type: NotificationEventType;
  title: string;
  summary: string;
  severity: InAppNotificationSeverity;
  target_type: string;
  target_id: UUID;
  deep_link: string;
  status: InAppNotificationStatus;
  created_at: string;
  updated_at: string;
  read_at: string | null;
  archived_at: string | null;
  expires_at: string | null;
}

export interface NotificationUnreadCount {
  unread_count: number;
}

export interface NotificationPreference {
  id: UUID;
  user_id: UUID;
  event_type: NotificationEventType;
  channel: "in_app";
  enabled: boolean;
  frequency: NotificationFrequency;
  minimum_severity: InAppNotificationSeverity;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface NotificationPreferenceUpdateItem {
  event_type: NotificationEventType;
  enabled: boolean;
  frequency: NotificationFrequency;
  minimum_severity: InAppNotificationSeverity;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  timezone?: string;
}
