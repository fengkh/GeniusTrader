import { apiRequest, toQueryString } from "@/lib/api/client";
import type {
  DailyReviewDetail,
  DailyReviewGeneratePayload,
  DailyReviewStatus,
  DailyReviewSummary,
  DailyReviewVersion,
  Page,
  UUID
} from "@/lib/api/types";

export interface DailyReviewListParams {
  status?: DailyReviewStatus | "";
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

export async function listDailyReviews(
  params: DailyReviewListParams = {}
): Promise<Page<DailyReviewSummary>> {
  return apiRequest<Page<DailyReviewSummary>>(
    `/reviews${toQueryString({
      status: params.status,
      date_from: params.date_from,
      date_to: params.date_to,
      limit: params.limit ?? 20,
      offset: params.offset ?? 0
    })}`
  );
}

export async function generateDailyReview(
  payload: DailyReviewGeneratePayload
): Promise<DailyReviewDetail> {
  return apiRequest<DailyReviewDetail>("/reviews", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getDailyReview(reviewId: UUID): Promise<DailyReviewDetail> {
  return apiRequest<DailyReviewDetail>(`/reviews/${reviewId}`);
}

export async function regenerateDailyReview(
  reviewId: UUID,
  useAi = true
): Promise<DailyReviewDetail> {
  return apiRequest<DailyReviewDetail>(
    `/reviews/${reviewId}/regenerate${toQueryString({ use_ai: useAi })}`,
    {
      method: "POST"
    }
  );
}

export async function archiveDailyReview(
  reviewId: UUID,
  archived: boolean
): Promise<DailyReviewDetail> {
  return apiRequest<DailyReviewDetail>(`/reviews/${reviewId}`, {
    method: "PATCH",
    body: JSON.stringify({ archived })
  });
}

export async function listDailyReviewVersions(
  reviewId: UUID
): Promise<DailyReviewVersion[]> {
  return apiRequest<DailyReviewVersion[]>(`/reviews/${reviewId}/versions`);
}
