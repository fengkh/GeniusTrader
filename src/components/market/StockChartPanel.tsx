"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
  type MouseEventParams,
  type Time,
  type UTCTimestamp
} from "lightweight-charts";

import { EmptyState } from "@/components/status/EmptyState";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import { formatNumber, formatPercent, trendTone } from "@/lib/formatters";
import type { DailyKLinePoint, Stock } from "@/mock/types";

type ChartTab = "intraday" | "daily";
type DayRange = 20 | 60 | 120;

export function StockChartPanel({ stock }: { stock: Stock }) {
  const [tab, setTab] = useState<ChartTab>("intraday");
  const [range, setRange] = useState<DayRange>(60);
  const latestIntraday = stock.chartSet.intraday[stock.chartSet.intraday.length - 1];
  const high =
    stock.chartSet.intraday.length > 0
      ? Math.max(...stock.chartSet.intraday.map((point) => point.price))
      : stock.marketSnapshot.high;
  const low =
    stock.chartSet.intraday.length > 0
      ? Math.min(...stock.chartSet.intraday.map((point) => point.price))
      : stock.marketSnapshot.low;

  const visibleDaily = useMemo(() => {
    if (range === 20) {
      return stock.chartSet.dailyK.slice(-20);
    }

    return stock.chartSet.dailyK;
  }, [range, stock.chartSet.dailyK]);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-slate-950">分时与日K走势</h2>
            <StatusTag status={stock.chartSet.status} />
            <SimulatedDataBadge compact />
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            图表为确定性本地Mock数据，不代表实时行情；图表组件由 TradingView Lightweight Charts 提供。
          </p>
          {stock.chartSet.message ? (
            <p className="mt-2 rounded-md bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
              {stock.chartSet.message}
            </p>
          ) : null}
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4 lg:min-w-[430px]">
          <ChartStat label="最高价" value={formatNumber(high)} />
          <ChartStat label="最低价" value={formatNumber(low)} />
          <ChartStat label="最新价" value={formatNumber(latestIntraday?.price ?? stock.marketSnapshot.close)} />
          <ChartStat
            label="当前涨跌幅"
            value={formatPercent(stock.marketSnapshot.changePercent)}
            tone={trendTone(stock.marketSnapshot.changePercent)}
          />
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <div className="inline-flex rounded-md border border-slate-300 bg-slate-50 p-1">
          <ChartTabButton active={tab === "intraday"} onClick={() => setTab("intraday")}>
            分时
          </ChartTabButton>
          <ChartTabButton active={tab === "daily"} onClick={() => setTab("daily")}>
            日K
          </ChartTabButton>
        </div>
        {tab === "daily" ? (
          <div className="inline-flex rounded-md border border-slate-300 bg-white p-1">
            {[20, 60, 120].map((item) => (
              <button
                key={item}
                onClick={() => setRange(item as DayRange)}
                className={`h-8 rounded px-3 text-xs font-semibold ${
                  range === item ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
                type="button"
              >
                {item}日
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {tab === "intraday" ? (
        stock.chartSet.intraday.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              title="暂无分时数据"
              description="当前Mock股票没有可展示的分时数据，页面不会补造行情。"
            />
          </div>
        ) : (
          <IntradayChart stock={stock} />
        )
      ) : visibleDaily.length === 0 ? (
        <div className="mt-4">
          <EmptyState
            title="暂无日K数据"
            description="当前Mock股票没有可展示的日K数据，页面不会补造行情。"
          />
        </div>
      ) : (
        <>
          <DailyChart rows={visibleDaily} />
          {range === 120 ? (
            <p className="mt-2 text-xs text-amber-700">
              Mock第一阶段主要提供近60日样本，120日按钮用于验证控件与空缺提示。
            </p>
          ) : null}
        </>
      )}

      <p className="mt-3 text-xs leading-5 text-slate-500">
        数据时间：{stock.chartSet.dataTime}；更新时间：{stock.chartSet.updatedAt}；TradingView
        Lightweight Charts 仅提供图表组件，行情数据为本地模拟。
      </p>
    </section>
  );
}

function IntradayChart({ stock }: { stock: Stock }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [hoverText, setHoverText] = useState("移动到图表上查看时间、价格、均价和成交量");

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 320,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#334155"
      },
      grid: {
        vertLines: { color: "#eef2f7" },
        horzLines: { color: "#eef2f7" }
      },
      rightPriceScale: {
        borderColor: "#e2e8f0",
        scaleMargins: { top: 0.08, bottom: 0.3 }
      },
      timeScale: {
        borderColor: "#e2e8f0",
        timeVisible: true,
        secondsVisible: false
      }
    });

    const priceSeries = chart.addSeries(LineSeries, {
      color: "#1d4ed8",
      lineWidth: 2,
      priceLineVisible: false
    });
    priceSeries.setData(
      stock.chartSet.intraday.map((point) => ({
        time: point.time as UTCTimestamp,
        value: point.price
      }))
    );

    const avgSeries = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false
    });
    avgSeries.setData(
      stock.chartSet.intraday.map((point) => ({
        time: point.time as UTCTimestamp,
        value: point.avgPrice
      }))
    );

    if (stock.chartSet.previousClose !== null) {
      const reference = chart.addSeries(LineSeries, {
        color: "#94a3b8",
        lineStyle: LineStyle.Dashed,
        lineWidth: 1,
        priceLineVisible: false
      });
      reference.setData(
        stock.chartSet.intraday.map((point) => ({
          time: point.time as UTCTimestamp,
          value: stock.chartSet.previousClose ?? point.price
        }))
      );
    }

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#cbd5e1",
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      priceScaleId: "volume"
    });
    volumeSeries.setData(
      stock.chartSet.intraday
        .filter((point) => point.volume !== null)
        .map((point) => ({
          time: point.time as UTCTimestamp,
          value: point.volume ?? 0,
          color: "#cbd5e1"
        }))
    );
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.78, bottom: 0 }
    });

    chart.subscribeCrosshairMove((param: MouseEventParams<Time>) => {
      if (!param.time) {
        setHoverText("移动到图表上查看时间、价格、均价和成交量");
        return;
      }

      const matched = stock.chartSet.intraday.find((point) => point.time === param.time);
      if (!matched) {
        return;
      }

      const time = new Date(matched.time * 1000).toISOString().slice(11, 16);
      setHoverText(
        `${time} 价格 ${matched.price.toFixed(2)} / 均价 ${matched.avgPrice.toFixed(2)} / 成交量 ${
          matched.volume === null ? "暂无" : matched.volume.toLocaleString("zh-CN")
        }`
      );
    });

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
    };
  }, [stock.chartSet.intraday, stock.chartSet.previousClose]);

  return (
    <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
        <span className="font-semibold text-blue-700">价格线</span>
        <span className="font-semibold text-amber-600">均价线</span>
        <span className="font-semibold text-slate-500">昨收参考线</span>
        <span>{hoverText}</span>
      </div>
      <div ref={containerRef} className="h-[300px] w-full md:h-[340px]" />
    </div>
  );
}

function DailyChart({ rows }: { rows: DailyKLinePoint[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [hoverText, setHoverText] = useState("移动到图表上查看日期、OHLC和成交量");

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 340,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#334155"
      },
      grid: {
        vertLines: { color: "#eef2f7" },
        horzLines: { color: "#eef2f7" }
      },
      rightPriceScale: {
        borderColor: "#e2e8f0",
        scaleMargins: { top: 0.08, bottom: 0.28 }
      },
      timeScale: {
        borderColor: "#e2e8f0"
      }
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#dc2626",
      downColor: "#047857",
      borderUpColor: "#dc2626",
      borderDownColor: "#047857",
      wickUpColor: "#dc2626",
      wickDownColor: "#047857"
    });
    candleSeries.setData(
      rows.map((row) => ({
        time: row.time,
        open: row.open,
        high: row.high,
        low: row.low,
        close: row.close
      }))
    );

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#cbd5e1",
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      priceScaleId: "volume"
    });
    volumeSeries.setData(
      rows
        .filter((row) => row.volume !== null)
        .map((row) => ({
          time: row.time,
          value: row.volume ?? 0,
          color: row.close >= row.open ? "#fecaca" : "#bbf7d0"
        }))
    );
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 }
    });

    addMaSeries(chart, rows, "ma5", "#2563eb");
    addMaSeries(chart, rows, "ma10", "#d97706");
    addMaSeries(chart, rows, "ma20", "#7c3aed");

    chart.subscribeCrosshairMove((param: MouseEventParams<Time>) => {
      if (!param.time) {
        setHoverText("移动到图表上查看日期、OHLC和成交量");
        return;
      }

      const time = String(param.time);
      const matched = rows.find((row) => row.time === time);
      if (!matched) {
        return;
      }

      setHoverText(
        `${matched.time} 开 ${matched.open.toFixed(2)} 高 ${matched.high.toFixed(2)} 低 ${matched.low.toFixed(
          2
        )} 收 ${matched.close.toFixed(2)} 量 ${matched.volume === null ? "暂无" : matched.volume.toLocaleString("zh-CN")}`
      );
    });

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
    };
  }, [rows]);

  return (
    <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
        <span className="font-semibold text-blue-700">MA5</span>
        <span className="font-semibold text-amber-600">MA10</span>
        <span className="font-semibold text-violet-700">MA20</span>
        <span>{hoverText}</span>
      </div>
      <div ref={containerRef} className="h-[320px] w-full md:h-[360px]" />
    </div>
  );
}

function addMaSeries(
  chart: ReturnType<typeof createChart>,
  rows: DailyKLinePoint[],
  key: "ma5" | "ma10" | "ma20",
  color: string
) {
  const series = chart.addSeries(LineSeries, {
    color,
    lineWidth: 1,
    priceLineVisible: false
  });
  series.setData(
    rows
      .filter((row) => row[key] !== undefined)
      .map((row) => ({
        time: row.time,
        value: row[key] ?? row.close
      }))
  );
}

function ChartTabButton({
  active,
  onClick,
  children
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`h-8 rounded px-3 text-sm font-semibold ${
        active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
      }`}
      type="button"
    >
      {children}
    </button>
  );
}

function ChartStat({
  label,
  value,
  tone = "text-slate-900"
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${tone}`}>{value}</p>
    </div>
  );
}
