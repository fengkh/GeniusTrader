import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  MarketDataStatus,
  MarketDataSyncPayload,
  MarketDataSyncRun,
  Page,
  StockMarketSnapshot,
  WatchlistMarketSnapshot
} from "@/lib/api/types";

export async function getMarketDataStatus(): Promise<MarketDataStatus> {
  return apiRequest<MarketDataStatus>("/market-data/status");
}

export async function getStockMarketSnapshot(stockId: string): Promise<StockMarketSnapshot> {
  return apiRequest<StockMarketSnapshot>(`/stocks/${stockId}/market-snapshot`);
}

export async function getWatchlistMarketSnapshots(): Promise<WatchlistMarketSnapshot[]> {
  return apiRequest<WatchlistMarketSnapshot[]>("/watchlist/market-snapshots");
}

export async function startMarketDataSync(
  payload: MarketDataSyncPayload
): Promise<MarketDataSyncRun> {
  return apiRequest<MarketDataSyncRun>("/admin/market-data/sync", {
    method: "POST",
    body: JSON.stringify({
      source_code: payload.source_code ?? "BAOSTOCK",
      sync_mode: payload.sync_mode ?? "latest_completed_trade_day",
      trade_date: payload.trade_date ?? null,
      lookback_days: payload.lookback_days ?? 1,
      stock_ids: payload.stock_ids ?? [],
      use_current_watchlist: payload.use_current_watchlist ?? true,
      dry_run: payload.dry_run ?? false
    })
  });
}

export async function listMarketDataSyncRuns(
  params: { limit?: number; offset?: number } = {}
): Promise<Page<MarketDataSyncRun>> {
  return apiRequest<Page<MarketDataSyncRun>>(
    `/admin/market-data/sync-runs${toQueryString({
      limit: params.limit ?? 10,
      offset: params.offset ?? 0
    })}`
  );
}
