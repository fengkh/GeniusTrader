"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  ChevronRight,
  FileSpreadsheet,
  Filter,
  Minus,
  Plus,
  Search,
  X
} from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { MiniTrendLine } from "@/components/market/MiniTrendLine";
import { EmptyState } from "@/components/status/EmptyState";
import { SimulatedDataBadge } from "@/components/status/SimulatedDataBadge";
import { StatusTag } from "@/components/status/StatusTag";
import { formatNumber, formatPercent, tradeStatusLabel, trendTone } from "@/lib/formatters";
import { useMockState } from "@/lib/mock-state";
import type { BoardTag, BoardType, Stock } from "@/mock/types";

const ALL_GROUP = "全部分组";
const ALL_TAG = "全部标签";
const ALL_BOARD = "全部板块";

const boardTypeLabels: Record<BoardType, string> = {
  "standard-industry": "标准行业",
  "concept-board": "概念板块",
  "dynamic-theme": "动态题材"
};

export default function WatchlistPage() {
  const { data } = useMockState();
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState(ALL_GROUP);
  const [tag, setTag] = useState(ALL_TAG);
  const [boardType, setBoardType] = useState<BoardType>("standard-industry");
  const [selectedBoard, setSelectedBoard] = useState(ALL_BOARD);
  const [boardSearch, setBoardSearch] = useState("");
  const [filterPanelOpen, setFilterPanelOpen] = useState(false);
  const [panel, setPanel] = useState<"add" | "csv" | null>(null);

  const groups = useMemo(
    () => [ALL_GROUP, ...Array.from(new Set(data.stocks.flatMap((stock) => stock.personalGroups)))],
    [data.stocks]
  );
  const tags = useMemo(
    () => [ALL_TAG, ...Array.from(new Set(data.stocks.flatMap((stock) => stock.userTags.map((item) => item.label))))],
    [data.stocks]
  );
  const boardStats = useMemo(() => getBoardStats(data.stocks, boardType), [boardType, data.stocks]);
  const visibleBoardStats = useMemo(() => {
    const normalized = boardSearch.trim().toLowerCase();

    return boardStats.filter((item) => normalized.length === 0 || item.name.toLowerCase().includes(normalized));
  }, [boardSearch, boardStats]);

  const filteredStocks = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return data.stocks.filter((stock) => {
      const matchesQuery =
        normalizedQuery.length === 0 ||
        stock.name.toLowerCase().includes(normalizedQuery) ||
        stock.code.toLowerCase().includes(normalizedQuery);
      const matchesGroup = group === ALL_GROUP || stock.personalGroups.includes(group);
      const matchesTag = tag === ALL_TAG || stock.userTags.some((item) => item.label === tag);
      const matchesBoard =
        selectedBoard === ALL_BOARD ||
        boardsByType(stock, boardType).some((board) => board.name === selectedBoard);

      return matchesQuery && matchesGroup && matchesTag && matchesBoard;
    });
  }, [boardType, data.stocks, group, query, selectedBoard, tag]);

  const filtersActive =
    query.trim().length > 0 || group !== ALL_GROUP || tag !== ALL_TAG || selectedBoard !== ALL_BOARD;

  function clearFilters() {
    setQuery("");
    setGroup(ALL_GROUP);
    setTag(ALL_TAG);
    setSelectedBoard(ALL_BOARD);
    setBoardSearch("");
  }

  function chooseBoardType(nextType: BoardType) {
    setBoardType(nextType);
    setSelectedBoard(ALL_BOARD);
    setBoardSearch("");
  }

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="自选股扫描"
        title="自选股"
        description="紧凑查看自选股，支持搜索、个人分组、用户标签与板块筛选。添加与导入仍为Mock说明流程。"
        actions={
          <>
            <button
              onClick={() => setPanel("add")}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800"
              type="button"
            >
              <Plus className="h-4 w-4" />
              添加
            </button>
            <button
              onClick={() => setPanel("csv")}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              type="button"
            >
              <FileSpreadsheet className="h-4 w-4" />
              CSV
            </button>
          </>
        }
      />

      <section className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm lg:p-4">
        <div className="flex flex-wrap items-center gap-2">
          <SimulatedDataBadge />
          <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
            基础信息：模拟资料库；行情：本地Mock快照
          </span>
          <span className="text-xs text-slate-500">
            共 {filteredStocks.length} / {data.stocks.length} 只
          </span>
          {filtersActive ? (
            <button
              onClick={clearFilters}
              className="focus-ring ml-auto h-8 rounded-md border border-slate-300 px-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              type="button"
            >
              清除筛选
            </button>
          ) : null}
        </div>

        <div className="mt-3 flex gap-2 lg:hidden">
          <label className="relative block min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="focus-ring h-9 w-full rounded-md border border-slate-300 pl-9 pr-3 text-sm"
              placeholder="搜索名称/代码"
            />
          </label>
          <button
            onClick={() => setFilterPanelOpen((value) => !value)}
            className="focus-ring inline-flex h-9 items-center gap-1 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700"
            type="button"
          >
            <Filter className="h-4 w-4" />
            更多
          </button>
        </div>

        <BoardQuickList
          boardStats={visibleBoardStats}
          selectedBoard={selectedBoard}
          onSelect={setSelectedBoard}
          className="mt-3 lg:hidden"
        />

        {filterPanelOpen ? (
          <div className="mt-3 rounded-md border border-slate-200 bg-slate-50 p-3 lg:hidden">
            <FilterControls
              group={group}
              groups={groups}
              tag={tag}
              tags={tags}
              boardType={boardType}
              boardSearch={boardSearch}
              onGroupChange={setGroup}
              onTagChange={setTag}
              onBoardTypeChange={chooseBoardType}
              onBoardSearchChange={setBoardSearch}
            />
          </div>
        ) : null}

        <div className="mt-3 hidden gap-3 lg:grid lg:grid-cols-[1.3fr_150px_150px]">
          <label className="relative block">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="focus-ring h-10 w-full rounded-md border border-slate-300 pl-9 pr-3 text-sm"
              placeholder="搜索股票名称或代码"
            />
          </label>
          <Select value={group} values={groups} onChange={setGroup} />
          <Select value={tag} values={tags} onChange={setTag} />
        </div>

        <div className="mt-3 hidden rounded-md border border-slate-200 bg-slate-50 p-3 lg:block">
          <FilterControls
            group={group}
            groups={groups}
            tag={tag}
            tags={tags}
            boardType={boardType}
            boardSearch={boardSearch}
            onGroupChange={setGroup}
            onTagChange={setTag}
            onBoardTypeChange={chooseBoardType}
            onBoardSearchChange={setBoardSearch}
            compactDesktop
          />
          <BoardQuickList
            boardStats={visibleBoardStats}
            selectedBoard={selectedBoard}
            onSelect={setSelectedBoard}
            className="mt-3"
          />
        </div>
      </section>

      {data.stocks.length === 0 ? (
        <EmptyState
          title="暂无自选股"
          description="这是新用户空数据场景。添加股票和CSV导入按钮会打开Mock说明，不会连接真实数据源或解析真实文件。"
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <button
                onClick={() => setPanel("add")}
                className="focus-ring h-10 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
                type="button"
              >
                添加股票
              </button>
              <button
                onClick={() => setPanel("csv")}
                className="focus-ring h-10 rounded-md border border-slate-300 px-4 text-sm font-semibold text-slate-700"
                type="button"
              >
                CSV导入说明
              </button>
            </div>
          }
        />
      ) : filteredStocks.length === 0 ? (
        <EmptyState title="没有匹配的股票" description="请调整搜索、分组、用户标签或板块筛选条件。" />
      ) : (
        <>
          <DesktopWatchlistTable stocks={filteredStocks} />
          <MobileWatchlistList stocks={filteredStocks} />
        </>
      )}

      {panel ? <MockPanel panel={panel} onClose={() => setPanel(null)} /> : null}
    </div>
  );
}

function FilterControls({
  group,
  groups,
  tag,
  tags,
  boardType,
  boardSearch,
  onGroupChange,
  onTagChange,
  onBoardTypeChange,
  onBoardSearchChange,
  compactDesktop = false
}: {
  group: string;
  groups: string[];
  tag: string;
  tags: string[];
  boardType: BoardType;
  boardSearch: string;
  onGroupChange: (value: string) => void;
  onTagChange: (value: string) => void;
  onBoardTypeChange: (value: BoardType) => void;
  onBoardSearchChange: (value: string) => void;
  compactDesktop?: boolean;
}) {
  return (
    <div className={compactDesktop ? "grid gap-3 lg:grid-cols-[1fr_1fr_1.4fr]" : "grid gap-3"}>
      <div className="grid grid-cols-2 gap-2">
        <Select value={group} values={groups} onChange={onGroupChange} />
        <Select value={tag} values={tags} onChange={onTagChange} />
      </div>
      <div className="flex rounded-md border border-slate-300 bg-white p-1">
        {(Object.keys(boardTypeLabels) as BoardType[]).map((type) => (
          <button
            key={type}
            onClick={() => onBoardTypeChange(type)}
            className={`h-8 flex-1 rounded px-2 text-xs font-semibold ${
              boardType === type ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
            }`}
            type="button"
          >
            {boardTypeLabels[type]}
          </button>
        ))}
      </div>
      <label className="relative block">
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
        <input
          value={boardSearch}
          onChange={(event) => onBoardSearchChange(event.target.value)}
          className="focus-ring h-9 w-full rounded-md border border-slate-300 bg-white pl-9 pr-3 text-sm"
          placeholder="搜索板块名称"
        />
      </label>
    </div>
  );
}

function BoardQuickList({
  boardStats,
  selectedBoard,
  onSelect,
  className
}: {
  boardStats: Array<{ name: string; type: BoardType; count: number }>;
  selectedBoard: string;
  onSelect: (value: string) => void;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="flex gap-2 overflow-x-auto pb-1">
        <BoardChip active={selectedBoard === ALL_BOARD} onClick={() => onSelect(ALL_BOARD)}>
          {ALL_BOARD}
        </BoardChip>
        {boardStats.map((item) => (
          <BoardChip key={`${item.type}-${item.name}`} active={selectedBoard === item.name} onClick={() => onSelect(item.name)}>
            {item.name} · {item.count}
          </BoardChip>
        ))}
      </div>
    </div>
  );
}

function BoardChip({
  active,
  onClick,
  children
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`focus-ring h-8 shrink-0 rounded-md border px-3 text-xs font-semibold ${
        active
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
      }`}
      type="button"
    >
      {children}
    </button>
  );
}

function DesktopWatchlistTable({ stocks }: { stocks: Stock[] }) {
  return (
    <section className="hidden rounded-lg border border-slate-200 bg-white shadow-sm lg:block">
      <div className="grid grid-cols-[1.35fr_1fr_1fr_1fr_1fr_0.9fr_0.65fr] border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-500">
        <span>股票</span>
        <span>最新价 / 涨跌</span>
        <span>主要板块</span>
        <span>核心异动</span>
        <span>相对板块表现</span>
        <span>数据状态</span>
        <span>详情</span>
      </div>
      {stocks.map((stock) => (
        <div
          key={stock.id}
          className="grid grid-cols-[1.35fr_1fr_1fr_1fr_1fr_0.9fr_0.65fr] items-center gap-3 border-b border-slate-100 px-4 py-3 last:border-b-0"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate font-semibold text-slate-950">{stock.name}</p>
              <span className="shrink-0 text-xs text-slate-500">{stock.code}</span>
            </div>
            <p className="mt-1 truncate text-xs text-slate-500">{stock.market}</p>
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-950">{formatNumber(stock.marketSnapshot.close)}</p>
            <p className={`mt-1 text-xs font-semibold ${trendTone(stock.marketSnapshot.changePercent)}`}>
              {changeText(stock)}
            </p>
          </div>
          <div className="text-xs leading-5 text-slate-700">
            <p className="font-semibold">{primaryIndustry(stock)}</p>
            <p className="truncate text-slate-500">{primaryThemeOrConcept(stock)}</p>
          </div>
          <p className="line-clamp-2 text-xs leading-5 text-slate-700">{primaryAbnormal(stock)}</p>
          <p className="line-clamp-2 text-xs leading-5 text-slate-700">
            {stock.marketSnapshot.relativeSectorStrength}
          </p>
          <StatusTag status={stock.marketSnapshot.status} label={tradeStatusLabel(stock.tradeStatus)} />
          <Link
            href={`/watchlist/${stock.id}`}
            className="focus-ring inline-flex h-8 items-center justify-center rounded-md border border-slate-300 px-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            详情
          </Link>
        </div>
      ))}
    </section>
  );
}

function MobileWatchlistList({ stocks }: { stocks: Stock[] }) {
  return (
    <section className="grid gap-2 lg:hidden">
      {stocks.map((stock) => (
        <Link
          key={stock.id}
          href={`/watchlist/${stock.id}`}
          className="focus-ring grid h-[96px] grid-cols-[minmax(0,1fr)_92px] gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm active:bg-slate-50"
        >
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <p className="truncate text-sm font-semibold text-slate-950">{stock.name}</p>
              <span className="shrink-0 text-[11px] text-slate-500">{stock.code}</span>
              <ChevronRight className="ml-auto h-4 w-4 shrink-0 text-slate-400" />
            </div>
            <div className="mt-1 flex min-w-0 items-center gap-1.5">
              <span className="truncate text-[11px] font-medium text-slate-600">
                {primaryIndustry(stock)}
              </span>
              <span className="text-[11px] text-slate-300">/</span>
              <span className="truncate text-[11px] text-slate-600">{primaryThemeOrConcept(stock)}</span>
            </div>
            <div className="mt-1.5 flex min-w-0 items-center gap-1.5">
              <CompactLabels stock={stock} />
            </div>
            <p className="mt-1 truncate text-[11px] text-slate-500">{primaryAbnormal(stock)}</p>
          </div>
          <div className="flex flex-col items-end justify-between">
            <StatusTag status={stock.marketSnapshot.status} label={shortTradeStatus(stock)} />
            <div className="text-right">
              <p className="text-sm font-semibold text-slate-950">{formatNumber(stock.marketSnapshot.close)}</p>
              <p className={`mt-0.5 inline-flex items-center gap-1 text-xs font-semibold ${trendTone(stock.marketSnapshot.changePercent)}`}>
                <ChangeIcon stock={stock} />
                {changeText(stock)}
              </p>
            </div>
            <MiniTrendLine
              points={stock.miniTrend}
              changePercent={stock.marketSnapshot.changePercent}
              status={stock.marketSnapshot.status}
              compact
            />
          </div>
        </Link>
      ))}
    </section>
  );
}

function CompactLabels({ stock }: { stock: Stock }) {
  const labels = [
    ...stock.standardIndustries.map((item) => item.name),
    ...stock.conceptBoards.map((item) => item.name),
    ...stock.dynamicThemes.map((item) => item.name),
    ...stock.userTags.map((item) => item.label)
  ];
  const visible = labels.slice(0, 2);
  const hiddenCount = Math.max(0, labels.length - visible.length);

  return (
    <>
      {visible.map((label) => (
        <span
          key={label}
          className="max-w-[80px] truncate rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
        >
          {label}
        </span>
      ))}
      {hiddenCount > 0 ? (
        <span className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
          +{hiddenCount}
        </span>
      ) : null}
    </>
  );
}

function Select({
  value,
  values,
  onChange
}: {
  value: string;
  values: string[];
  onChange: (value: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="focus-ring h-9 min-w-0 rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-800"
    >
      {values.map((item) => (
        <option key={item}>{item}</option>
      ))}
    </select>
  );
}

function MockPanel({
  panel,
  onClose
}: {
  panel: "add" | "csv";
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-end bg-slate-950/30 p-4 sm:items-center sm:justify-center">
      <section className="w-full max-w-xl rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">
              {panel === "add" ? "添加股票（Mock）" : "CSV导入（Mock）"}
            </h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              本轮只展示入口和规则说明，不校验真实股票代码，不解析真实文件。
            </p>
          </div>
          <button
            onClick={onClose}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50"
            type="button"
            aria-label="关闭"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {panel === "add" ? (
          <div className="mt-4 grid gap-3">
            <label className="block">
              <span className="text-sm font-medium text-slate-700">股票代码</span>
              <input
                className="mt-1 h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
                placeholder="例如 SH600001（模拟）"
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium text-slate-700">关注原因</span>
              <textarea
                className="mt-1 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                placeholder="记录个人关注逻辑（不会保存）"
              />
            </label>
            <button className="h-10 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white" type="button">
              显示添加结果示例
            </button>
          </div>
        ) : (
          <div className="mt-4 space-y-3 text-sm leading-6 text-slate-700">
            <p>CSV字段：stock_code 必填；group、tags、focus_reason 选填。</p>
            <p>多个标签使用英文分号或中文分号分隔。单条错误不应导致整个文件导入失败。</p>
            <div className="rounded-md bg-slate-50 p-3 font-mono text-xs text-slate-700">
              stock_code,group,tags,focus_reason
              <br />
              SH600001,重点观察,政策敏感;观察放量,跟踪模拟订单改善
            </div>
            <button
              className="h-10 rounded-md border border-slate-300 px-4 text-sm font-semibold text-slate-700"
              type="button"
            >
              CSV模板下载示例（Mock）
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

function getBoardStats(stocks: Stock[], type: BoardType) {
  const counts = new Map<string, { name: string; type: BoardType; count: number }>();

  stocks.forEach((stock) => {
    boardsByType(stock, type).forEach((board) => {
      const existing = counts.get(board.name);
      counts.set(board.name, {
        name: board.name,
        type: board.type,
        count: (existing?.count ?? 0) + 1
      });
    });
  });

  return Array.from(counts.values()).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh-CN"));
}

function boardsByType(stock: Stock, type: BoardType): BoardTag[] {
  if (type === "standard-industry") {
    return stock.standardIndustries;
  }

  if (type === "concept-board") {
    return stock.conceptBoards;
  }

  return stock.dynamicThemes;
}

function primaryIndustry(stock: Stock): string {
  return stock.standardIndustries[0]?.name ?? "暂无行业";
}

function primaryThemeOrConcept(stock: Stock): string {
  return stock.dynamicThemes[0]?.name ?? stock.conceptBoards[0]?.name ?? "暂无题材";
}

function primaryAbnormal(stock: Stock): string {
  if (stock.tradeStatus === "suspended") {
    return "停牌：当日交易指标为空";
  }

  return stock.abnormalEvents[0]?.type ?? "未触发重大异动";
}

function shortTradeStatus(stock: Stock): string {
  if (stock.tradeStatus === "partial-failure") {
    return "部分失败";
  }

  if (stock.tradeStatus === "stale") {
    return "过期";
  }

  return tradeStatusLabel(stock.tradeStatus);
}

function changeText(stock: Stock): string {
  const value = stock.marketSnapshot.changePercent;

  if (value === null) {
    return "暂无涨跌";
  }

  const word = value > 0 ? "上涨" : value < 0 ? "下跌" : "持平";
  return `${formatPercent(value)} ${word}`;
}

function ChangeIcon({ stock }: { stock: Stock }) {
  const value = stock.marketSnapshot.changePercent;

  if (value === null || value === 0) {
    return <Minus className="h-3.5 w-3.5" />;
  }

  if (value > 0) {
    return <ArrowUpRight className="h-3.5 w-3.5" />;
  }

  return <ArrowDownRight className="h-3.5 w-3.5" />;
}
