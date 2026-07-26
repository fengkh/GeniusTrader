import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  AnnouncementProvider,
  ExternalSource,
  FutureSourceGroup
} from "@/lib/api/types";

export interface ExternalSourceListParams {
  source_category?: string;
  country_code?: string;
  authority_level?: string;
  source_tier?: string;
  enabled?: boolean | null;
  experimental?: boolean | null;
}

export async function listExternalSources(
  params: ExternalSourceListParams = {}
): Promise<ExternalSource[]> {
  return apiRequest<ExternalSource[]>(
    `/external-sources${toQueryString({
      source_category: params.source_category,
      country_code: params.country_code,
      authority_level: params.authority_level,
      source_tier: params.source_tier,
      enabled: params.enabled,
      experimental: params.experimental
    })}`
  );
}

export async function listFutureSourceGroups(): Promise<FutureSourceGroup[]> {
  return apiRequest<FutureSourceGroup[]>("/external-sources/future-groups");
}

export async function listAnnouncementProviders(): Promise<AnnouncementProvider[]> {
  return apiRequest<AnnouncementProvider[]>("/announcement-providers");
}

