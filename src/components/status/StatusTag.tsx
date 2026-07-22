import { AlertCircle, CheckCircle2, Clock3, Loader2 } from "lucide-react";

import { statusLabel, statusTone } from "@/lib/formatters";
import type { DataStatus } from "@/mock/types";

const iconMap = {
  normal: CheckCircle2,
  syncing: Loader2,
  stale: Clock3,
  "partial-failure": AlertCircle,
  failure: AlertCircle,
  empty: Clock3,
  "ai-failure": AlertCircle
};

export function StatusTag({
  status,
  label
}: {
  status: DataStatus;
  label?: string;
}) {
  const Icon = iconMap[status];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium ${statusTone(
        status
      )}`}
    >
      <Icon className={status === "syncing" ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
      {label ?? statusLabel(status)}
    </span>
  );
}
