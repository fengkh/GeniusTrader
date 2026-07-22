import { FlaskConical } from "lucide-react";

export function SimulatedDataBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-700">
      <FlaskConical className="h-3.5 w-3.5 text-blue-700" />
      {compact ? "模拟数据" : "模拟数据，非实时行情"}
    </span>
  );
}
