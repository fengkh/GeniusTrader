import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  ApiMessage,
  Page,
  UserTagRead,
  UUID,
  WatchlistGroupRead,
  WatchlistItemPayload,
  WatchlistItemRead,
  WatchlistItemUpdatePayload
} from "@/lib/api/types";

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

export async function listWatchlistGroups(): Promise<WatchlistGroupRead[]> {
  return apiRequest<WatchlistGroupRead[]>("/watchlist/groups");
}

export async function createWatchlistGroup(name: string): Promise<WatchlistGroupRead> {
  return apiRequest<WatchlistGroupRead>("/watchlist/groups", {
    method: "POST",
    body: JSON.stringify({ name })
  });
}

export async function listWatchlistTags(): Promise<UserTagRead[]> {
  return apiRequest<UserTagRead[]>("/watchlist/tags");
}

export async function createWatchlistTag(name: string): Promise<UserTagRead> {
  return apiRequest<UserTagRead>("/watchlist/tags", {
    method: "POST",
    body: JSON.stringify({ name })
  });
}

export async function createWatchlistItem(payload: WatchlistItemPayload): Promise<WatchlistItemRead> {
  return apiRequest<WatchlistItemRead>("/watchlist", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      tag_ids: payload.tag_ids ?? []
    })
  });
}

export async function updateWatchlistItem(
  itemId: UUID,
  payload: WatchlistItemUpdatePayload
): Promise<WatchlistItemRead> {
  return apiRequest<WatchlistItemRead>(`/watchlist/${itemId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function deleteWatchlistItem(itemId: UUID): Promise<void> {
  await apiRequest<ApiMessage>(`/watchlist/${itemId}`, {
    method: "DELETE"
  });
}
