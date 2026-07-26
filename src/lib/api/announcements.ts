import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  AnnouncementCandidateDetail,
  AnnouncementCandidateSummary,
  AnnouncementDocumentExtractResult,
  AnnouncementImportResult,
  Page,
  ProviderSyncRun,
  UUID
} from "@/lib/api/types";

export interface AnnouncementCandidateListParams {
  status?: string;
  source_code?: string;
  stock_id?: UUID;
  announcement_type?: string;
  date_from?: string;
  date_to?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export interface AnnouncementSyncPayload {
  source_code: string;
  date_from: string;
  date_to: string;
  stock_ids?: UUID[];
  use_current_watchlist: boolean;
}

export interface AnnouncementImportPayload {
  import_mode: "metadata_only" | "extracted_document" | "user_supplemented";
  title_override?: string | null;
  user_note?: string | null;
  supplemented_text?: string | null;
}

export async function startAnnouncementSyncRun(
  payload: AnnouncementSyncPayload
): Promise<ProviderSyncRun> {
  return apiRequest<ProviderSyncRun>("/announcement-sync-runs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function listAnnouncementSyncRuns(
  params: { limit?: number; offset?: number } = {}
): Promise<Page<ProviderSyncRun>> {
  return apiRequest<Page<ProviderSyncRun>>(
    `/announcement-sync-runs${toQueryString({
      limit: params.limit ?? 10,
      offset: params.offset ?? 0
    })}`
  );
}

export async function listAnnouncementCandidates(
  params: AnnouncementCandidateListParams = {}
): Promise<Page<AnnouncementCandidateSummary>> {
  return apiRequest<Page<AnnouncementCandidateSummary>>(
    `/announcement-candidates${toQueryString({
      status: params.status,
      source_code: params.source_code,
      stock_id: params.stock_id,
      announcement_type: params.announcement_type,
      date_from: params.date_from,
      date_to: params.date_to,
      q: params.q,
      limit: params.limit ?? 20,
      offset: params.offset ?? 0
    })}`
  );
}

export async function getAnnouncementCandidate(
  candidateId: UUID
): Promise<AnnouncementCandidateDetail> {
  return apiRequest<AnnouncementCandidateDetail>(`/announcement-candidates/${candidateId}`);
}

export async function patchAnnouncementCandidate(
  candidateId: UUID,
  status: "pending" | "reviewed" | "dismissed"
): Promise<AnnouncementCandidateDetail> {
  return apiRequest<AnnouncementCandidateDetail>(`/announcement-candidates/${candidateId}`, {
    method: "PATCH",
    body: JSON.stringify({ status })
  });
}

export async function extractAnnouncementDocument(
  candidateId: UUID
): Promise<AnnouncementDocumentExtractResult> {
  return apiRequest<AnnouncementDocumentExtractResult>(
    `/announcement-candidates/${candidateId}/extract-document`,
    { method: "POST" }
  );
}

export async function importAnnouncementCandidate(
  candidateId: UUID,
  payload: AnnouncementImportPayload
): Promise<AnnouncementImportResult> {
  return apiRequest<AnnouncementImportResult>(`/announcement-candidates/${candidateId}/import`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
