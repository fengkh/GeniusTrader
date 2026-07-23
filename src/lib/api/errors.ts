export interface ApiErrorBody {
  code: string;
  message: string;
  request_id: string;
  details?: unknown;
}

export class ApiError extends Error {
  code: string;
  requestId: string;
  status: number;
  details?: unknown;

  constructor(error: ApiErrorBody, status: number) {
    super(error.message);
    this.name = "ApiError";
    this.code = error.code;
    this.requestId = error.request_id;
    this.status = status;
    this.details = error.details;
  }
}

export function humanizeApiError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.message}（${error.code}，请求ID：${error.requestId}）`;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "请求失败，请稍后重试";
}
