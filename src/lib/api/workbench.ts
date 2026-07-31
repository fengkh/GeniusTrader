import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  StockResearchDossier,
  TodayOverview,
  UUID,
  WatchlistScanner
} from "@/lib/api/types";

export async function getTodayOverview(businessDate?: string): Promise<TodayOverview> {
  return apiRequest<TodayOverview>(
    `/today/overview${toQueryString({
      business_date: businessDate
    })}`
  );
}

export async function getWatchlistScanner(params: {
  keyword?: string;
  group_id?: UUID | "";
  tag_id?: UUID | "";
  market_data_available?: boolean;
  market_movement?: "up" | "down" | "unchanged";
  exchange?: string;
  sort?:
    | "attention_score"
    | "attention"
    | "symbol"
    | "name"
    | "last_information_at"
    | "pending_candidate_count"
    | "open_task_count"
    | "latest_review_date"
    | "pct_change"
    | "amount"
    | "turnover_rate";
} = {}): Promise<WatchlistScanner> {
  return apiRequest<WatchlistScanner>(
    `/watchlist/scanner${toQueryString({
      keyword: params.keyword,
      group_id: params.group_id,
      tag_id: params.tag_id,
      market_data_available: params.market_data_available,
      market_movement: params.market_movement,
      exchange: params.exchange,
      sort: params.sort ?? "attention_score"
    })}`
  );
}

export async function getStockResearchDossier(stockId: UUID): Promise<StockResearchDossier> {
  return apiRequest<StockResearchDossier>(`/stocks/${stockId}/research-dossier`);
}
