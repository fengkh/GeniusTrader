import { apiRequest, toQueryString } from "@/lib/api/client";
import type { Page, UUID, WatchlistItemRead } from "@/lib/api/types";

export interface WatchlistListParams {
  group_id?: UUID;
  tag_id?: UUID;
  q?: string;
  include_archived?: boolean;
  limit?: number;
  offset?: number;
}

export async function listWatchlistItems(
  params: WatchlistListParams = {}
): Promise<Page<WatchlistItemRead>> {
  return apiRequest<Page<WatchlistItemRead>>(
    `/watchlist${toQueryString({
      group_id: params.group_id,
      tag_id: params.tag_id,
      q: params.q,
      include_archived: params.include_archived,
      limit: params.limit ?? 100,
      offset: params.offset ?? 0
    })}`
  );
}

