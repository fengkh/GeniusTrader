import type { DataStatus, MiniTrendPoint } from "@/mock/types";

const toneMap = {
  up: "text-red-600",
  down: "text-emerald-700",
  flat: "text-slate-600",
  missing: "text-slate-500"
};

export function MiniTrendLine({
  points,
  changePercent,
  status,
  label,
  compact = false
}: {
  points: MiniTrendPoint[];
  changePercent: number | null;
  status: DataStatus;
  label?: string;
  compact?: boolean;
}) {
  const width = 86;
  const height = 28;
  const padding = 2;
  const validValues = points
    .map((point) => point.close)
    .filter((value): value is number => value !== null && Number.isFinite(value));

  const tone =
    changePercent === null
      ? "missing"
      : changePercent > 0
        ? "up"
        : changePercent < 0
          ? "down"
          : "flat";
  const stroke = tone === "up" ? "#dc2626" : tone === "down" ? "#047857" : "#475569";
  const trendText =
    label ??
    (status === "stale"
      ? "20日走势过期"
      : status === "partial-failure" || status === "failure"
        ? "20日走势缺失"
        : changePercent === null
          ? "暂无走势"
          : changePercent > 0
            ? "20日上行"
            : changePercent < 0
              ? "20日下行"
              : "20日持平");

  if (validValues.length < 2) {
    return (
      <div className="w-[86px] text-right">
        <div className="flex h-5 items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 text-[10px] text-slate-500">
          暂无
        </div>
        {compact ? null : (
          <p className="mt-1 truncate text-[10px] leading-3 text-slate-500">{trendText}</p>
        )}
      </div>
    );
  }

  const min = Math.min(...validValues);
  const max = Math.max(...validValues);
  const spread = max - min || 1;
  const step = points.length > 1 ? width / (points.length - 1) : width;
  const path = points.reduce<{ commands: string[]; drawing: boolean }>(
    (accumulator, point, index) => {
      if (point.close === null || !Number.isFinite(point.close)) {
        return { commands: accumulator.commands, drawing: false };
      }

      const x = Number((index * step).toFixed(2));
      const y = Number(
        (padding + ((max - point.close) / spread) * (height - padding * 2)).toFixed(2)
      );
      const command = accumulator.drawing ? "L" : "M";

      return {
        commands: [...accumulator.commands, `${command}${x},${y}`],
        drawing: true
      };
    },
    { commands: [], drawing: false }
  ).commands.join(" ");

  return (
    <div className="w-[86px] text-right">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={compact ? "h-5 w-[86px]" : "h-7 w-[86px]"}
        role="img"
        aria-label={trendText}
      >
        <path
          d={path}
          fill="none"
          stroke={stroke}
          strokeDasharray={status === "stale" || status === "partial-failure" ? "4 3" : undefined}
          strokeLinecap="round"
          strokeWidth="2"
        />
      </svg>
      {compact ? null : (
        <p className={`mt-1 truncate text-[10px] leading-3 ${toneMap[tone]}`}>{trendText}</p>
      )}
    </div>
  );
}
