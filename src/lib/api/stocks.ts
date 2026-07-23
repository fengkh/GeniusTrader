import { apiRequest, toQueryString } from "@/lib/api/client";
import type { Page, StockRead } from "@/lib/api/types";

export interface StockListParams {
  q?: string;
  limit?: number;
  offset?: number;
}

export async function listStocks(params: StockListParams = {}): Promise<Page<StockRead>> {
  return apiRequest<Page<StockRead>>(
    `/stocks${toQueryString({
      q: params.q,
      limit: params.limit ?? 20,
      offset: params.offset ?? 0
    })}`
  );
}
