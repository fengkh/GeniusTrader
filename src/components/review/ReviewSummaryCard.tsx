import { FilePenLine, RotateCcw } from "lucide-react";

import { ErrorState } from "@/components/status/ErrorState";
import type { ReviewSummary } from "@/mock/types";

export function ReviewSummaryCard({ review }: { review: ReviewSummary }) {
  if (review.status === "failed") {
    return (
      <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4">
        <ErrorState
          title={review.title}
          description={review.failureReason ?? review.summary}
        />
        <div className="flex flex-wrap gap-2">
          <button className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">
            <RotateCcw className="h-4 w-4" />
            重新生成
          </button>
          <button className="focus-ring inline-flex h-9 items-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-medium text-white hover:bg-slate-800">
            <FilePenLine className="h-4 w-4" />
            手写复盘
          </button>
        </div>
        <p className="text-xs text-slate-500">
          按钮仅用于 Mock 流程表达，本轮不实现真实AI调用或保存。
        </p>
      </div>
    );
  }

  return (
    <article className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold text-blue-700">AI判断 · 模拟</p>
          <h3 className="mt-1 text-base font-semibold text-slate-950">{review.title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-700">{review.summary}</p>
        </div>
        <div className="rounded-md bg-slate-50 p-3 text-xs leading-5 text-slate-600 sm:w-56">
          <p>模型：{review.modelName}</p>
          <p>任务：{review.taskType}</p>
          <p>生成：{review.generatedAt}</p>
          <p>{review.isOriginalAiVersion ? "AI原始版本" : "人工修订版本"}</p>
        </div>
      </div>
      {review.manualRevision ? (
        <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm leading-6 text-emerald-900">
          {review.manualRevision}
        </p>
      ) : null}
      {review.sourceLayers.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {review.sourceLayers.map((layer) => (
            <span
              key={layer}
              className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700"
            >
              {layer}
            </span>
          ))}
        </div>
      ) : null}
    </article>
  );
}
