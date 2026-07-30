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
  q?: string;
  group_id?: UUID | "";
  tag_id?: UUID | "";
  sort?: "attention" | "name" | "last_information_at";
} = {}): Promise<WatchlistScanner> {
  return apiRequest<WatchlistScanner>(
    `/watchlist/scanner${toQueryString({
      q: params.q,
      group_id: params.group_id,
      tag_id: params.tag_id,
      sort: params.sort ?? "attention"
    })}`
  );
}

export async function getStockResearchDossier(stockId: UUID): Promise<StockResearchDossier> {
  return apiRequest<StockResearchDossier>(`/stocks/${stockId}/research-dossier`);
}
