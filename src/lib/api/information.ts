import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  ApiMessage,
  InformationContent,
  InformationDetail,
  InformationSourceType,
  InformationStockRelation,
  InformationSummary,
  Page,
  UUID
} from "@/lib/api/types";

export interface InformationListParams {
  q?: string;
  status?: string;
  source_type?: InformationSourceType | "";
  stock_id?: UUID;
  is_important?: boolean | null;
  is_read?: boolean | null;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export interface ManualInformationPayload {
  title?: string | null;
  text: string;
  source_type: InformationSourceType;
  source_name?: string | null;
  published_at?: string | null;
  user_note?: string | null;
  related_stock_ids?: UUID[];
  analyze_now?: boolean;
}

export interface UrlInformationPayload {
  url: string;
  source_type: InformationSourceType;
  user_note?: string | null;
  related_stock_ids?: UUID[];
  fetch_now?: boolean;
}

export async function listInformation(
  params: InformationListParams = {}
): Promise<Page<InformationSummary>> {
  return apiRequest<Page<InformationSummary>>(
    `/information${toQueryString({
      q: params.q,
      status: params.status,
      source_type: params.source_type,
      stock_id: params.stock_id,
      is_important: params.is_important,
      is_read: params.is_read,
      date_from: params.date_from,
      date_to: params.date_to,
      limit: params.limit ?? 20,
      offset: params.offset ?? 0
    })}`
  );
}

export async function getInformationItem(itemId: UUID): Promise<InformationDetail> {
  return apiRequest<InformationDetail>(`/information/${itemId}`);
}

export async function createManualInformation(
  payload: ManualInformationPayload
): Promise<InformationDetail> {
  return apiRequest<InformationDetail>("/information/manual", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function createUrlInformation(payload: UrlInformationPayload): Promise<InformationDetail> {
  return apiRequest<InformationDetail>("/information/url", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function patchInformationItem(
  itemId: UUID,
  payload: {
    title?: string | null;
    user_note?: string | null;
    is_important?: boolean;
    is_read?: boolean;
    archived?: boolean;
  }
): Promise<InformationDetail> {
  return apiRequest<InformationDetail>(`/information/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function addInformationContent(
  itemId: UUID,
  payload: { title?: string | null; text: string }
): Promise<InformationContent> {
  return apiRequest<InformationContent>(`/information/${itemId}/content`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function fetchInformationItem(itemId: UUID): Promise<InformationDetail> {
  return apiRequest<InformationDetail>(`/information/${itemId}/fetch`, {
    method: "POST"
  });
}

export async function analyzeInformationItem(
  itemId: UUID,
  force = false
): Promise<InformationDetail> {
  return apiRequest<InformationDetail>(`/information/${itemId}/analyze`, {
    method: "POST",
    body: JSON.stringify({ force })
  });
}

export async function addStockRelation(
  itemId: UUID,
  payload: { stock_id: UUID; relation_type?: string; evidence_text?: string | null }
): Promise<InformationStockRelation> {
  return apiRequest<InformationStockRelation>(`/information/${itemId}/stock-relations`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function patchStockRelation(
  itemId: UUID,
  relationId: UUID,
  payload: {
    stock_id?: UUID;
    relation_type?: string;
    relation_status?: "confirmed" | "rejected";
    evidence_text?: string | null;
  }
): Promise<InformationStockRelation> {
  return apiRequest<InformationStockRelation>(
    `/information/${itemId}/stock-relations/${relationId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload)
    }
  );
}

export async function deleteStockRelation(
  itemId: UUID,
  relationId: UUID
): Promise<ApiMessage> {
  return apiRequest<ApiMessage>(`/information/${itemId}/stock-relations/${relationId}`, {
    method: "DELETE"
  });
}
