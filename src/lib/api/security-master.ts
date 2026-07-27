import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  Page,
  SecurityMasterProvider,
  SecurityMasterStatus,
  SecurityMasterSyncRun
} from "@/lib/api/types";

export interface SecurityMasterSyncPayload {
  source_code: string;
  exchanges?: string[];
  force?: boolean;
}

export async function getSecurityMasterStatus(): Promise<SecurityMasterStatus> {
  return apiRequest<SecurityMasterStatus>("/security-master/status");
}

export async function listSecurityMasterProviders(): Promise<SecurityMasterProvider[]> {
  return apiRequest<SecurityMasterProvider[]>("/security-master/providers");
}

export async function startSecurityMasterSync(
  payload: SecurityMasterSyncPayload
): Promise<SecurityMasterSyncRun> {
  return apiRequest<SecurityMasterSyncRun>("/admin/security-master/sync", {
    method: "POST",
    body: JSON.stringify({
      source_code: payload.source_code,
      exchanges: payload.exchanges ?? [],
      force: payload.force ?? false
    })
  });
}

export async function listSecurityMasterSyncRuns(
  params: { limit?: number; offset?: number } = {}
): Promise<Page<SecurityMasterSyncRun>> {
  return apiRequest<Page<SecurityMasterSyncRun>>(
    `/admin/security-master/sync-runs${toQueryString({
      limit: params.limit ?? 10,
      offset: params.offset ?? 0
    })}`
  );
}
