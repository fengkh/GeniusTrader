import { apiRequest, toQueryString } from "@/lib/api/client";
import type { Page, StockRead } from "@/lib/api/types";

export interface StockListParams {
  q?: string;
  exchange?: string;
  board?: string;
  listing_status?: string;
  limit?: number;
  offset?: number;
}

export async function listStocks(params: StockListParams = {}): Promise<Page<StockRead>> {
  return apiRequest<Page<StockRead>>(
    `/stocks${toQueryString({
      q: params.q,
      exchange: params.exchange,
      board: params.board,
      listing_status: params.listing_status,
      limit: params.limit ?? 20,
      offset: params.offset ?? 0
    })}`
  );
}

export async function searchStocks(params: StockListParams = {}): Promise<Page<StockRead>> {
  return apiRequest<Page<StockRead>>(
    `/stocks/search${toQueryString({
      q: params.q,
      exchange: params.exchange,
      board: params.board,
      listing_status: params.listing_status,
      limit: params.limit ?? 20,
      offset: params.offset ?? 0
    })}`
  );
}

export async function getStock(stockId: string): Promise<StockRead> {
  return apiRequest<StockRead>(`/stocks/${stockId}`);
}
