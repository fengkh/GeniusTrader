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
  exchange: string;
  name: string;
  market: string;
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
  | "ai_task.failed";

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
