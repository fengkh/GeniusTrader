"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Edit3,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Trash2,
  X
} from "lucide-react";

import { useAuth } from "@/components/auth/AuthProvider";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/status/EmptyState";
import { ErrorState } from "@/components/status/ErrorState";
import { LoadingSkeleton } from "@/components/status/LoadingSkeleton";
import { humanizeApiError } from "@/lib/api/errors";
import { getWatchlistMarketSnapshots } from "@/lib/api/market-data";
import { getSecurityMasterStatus } from "@/lib/api/security-master";
import { searchStocks } from "@/lib/api/stocks";
import type {
  DecimalValue,
  SecurityMasterStatus,
  StockRead,
  UserTagRead,
  WatchlistMarketSnapshot,
  WatchlistGroupRead,
  WatchlistItemRead
} from "@/lib/api/types";
import {
  createWatchlistGroup,
  createWatchlistItem,
  createWatchlistTag,
  deleteWatchlistItem,
  listWatchlistGroups,
  listWatchlistItems,
  listWatchlistTags,
  updateWatchlistItem
} from "@/lib/api/watchlist";

const ALL = "__all__";

const boardLabels: Record<string, string> = {
  main_board: "主板",
  star_board: "科创板",
  chinext: "创业板",
  bse: "北交所",
  unknown: "未知板块"
};

const exchangeLabels: Record<string, string> = {
  SH: "上交所",
  SZ: "深交所",
  BJ: "北交所"
};

const listingStatusLabels: Record<string, string> = {
  pending_listing: "待上市",
  active: "正常上市",
  suspended: "停牌",
  risk_warning: "风险警示",
  delisting_period: "退市整理",
  delisted: "已退市",
  unknown: "状态未知"
};

export default function WatchlistPage() {
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<WatchlistItemRead[]>([]);
  const [groups, setGroups] = useState<WatchlistGroupRead[]>([]);
  const [tags, setTags] = useState<UserTagRead[]>([]);
  const [marketSnapshots, setMarketSnapshots] = useState<Record<string, WatchlistMarketSnapshot>>({});
  const [securityStatus, setSecurityStatus] = useState<SecurityMasterStatus | null>(null);
  const [query, setQuery] = useState("");
  const [groupId, setGroupId] = useState(ALL);
  const [tagId, setTagId] = useState(ALL);
  const [exchange, setExchange] = useState(ALL);
  const [board, setBoard] = useState(ALL);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [panel, setPanel] = useState<"add" | "edit" | null>(null);
  const [editingItem, setEditingItem] = useState<WatchlistItemRead | null>(null);

  const loadData = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [watchlistPage, groupRows, tagRows, status, snapshotRows] = await Promise.all([
        listWatchlistItems({ limit: 100 }),
        listWatchlistGroups(),
        listWatchlistTags(),
        getSecurityMasterStatus(),
        getWatchlistMarketSnapshots()
      ]);
      setItems(watchlistPage.items);
      setGroups(groupRows);
      setTags(tagRows);
      setMarketSnapshots(Object.fromEntries(snapshotRows.map((row) => [row.watchlist_item_id, row])));
      setSecurityStatus(status);
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!authLoading) {
      const timer = window.setTimeout(() => {
        void loadData();
      }, 0);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [authLoading, loadData]);

  const availableBoards = useMemo(
    () => Array.from(new Set(items.map((item) => item.stock.board))).sort(),
    [items]
  );
  const availableExchanges = useMemo(
    () => Array.from(new Set(items.map((item) => item.stock.exchange))).sort(),
    [items]
  );
  const filteredItems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return items.filter((item) => {
      const stock = item.stock;
      const matchesQuery =
        !normalizedQuery ||
        stock.code.toLowerCase().includes(normalizedQuery) ||
        stock.symbol.toLowerCase().includes(normalizedQuery) ||
        stock.short_name.toLowerCase().includes(normalizedQuery) ||
        (stock.full_name ?? "").toLowerCase().includes(normalizedQuery) ||
        (item.attention_reason ?? "").toLowerCase().includes(normalizedQuery);
      const matchesGroup = groupId === ALL || item.group?.id === groupId;
      const matchesTag = tagId === ALL || item.tags.some((tag) => tag.id === tagId);
      const matchesExchange = exchange === ALL || stock.exchange === exchange;
      const matchesBoard = board === ALL || stock.board === board;
      return matchesQuery && matchesGroup && matchesTag && matchesExchange && matchesBoard;
    });
  }, [board, exchange, groupId, items, query, tagId]);

  function openEdit(item: WatchlistItemRead) {
    setEditingItem(item);
    setPanel("edit");
    setMessage(null);
  }

  function closePanel() {
    setPanel(null);
    setEditingItem(null);
  }

  if (!user && !authLoading) {
    return (
      <EmptyState
        title="需要登录"
        description="真实自选股管理读取当前用户数据，请先登录私人测试版账户。"
        action={
          <Link
            href="/login?redirect=/watchlist"
            className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
          >
            去登录
          </Link>
        }
      />
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="真实自选股闭环"
        title="自选股"
        description="证券基本信息来自证券目录同步；行情区域仅显示已入库的真实日级快照。"
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => {
                setPanel("add");
                setMessage(null);
              }}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white hover:bg-slate-800"
              type="button"
            >
              <Plus className="h-4 w-4" />
              添加自选股
            </button>
            <button
              onClick={() => void loadData()}
              className="focus-ring inline-flex h-9 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              type="button"
            >
              <RefreshCw className="h-4 w-4" />
              刷新
            </button>
          </div>
        }
      />

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
        <div className="flex gap-2">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0" />
          <p>
            证券基本信息来自证券目录同步；行情区域仅显示后端已入库的真实日级快照。暂无快照时显示空状态；
            页面不会使用虚构价格、K线或分时图，也不会基于股票代码临时创建不存在的股票。
          </p>
        </div>
      </section>

      {securityStatus ? <SecurityDirectoryNotice status={securityStatus} /> : null}
      {message ? <StatusMessage text={message} /> : null}
      {error ? <ErrorState title="自选股加载失败" description={error} /> : null}
      {loading || authLoading ? <LoadingSkeleton lines={8} /> : null}

      {!loading && !authLoading ? (
        <>
          <section className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm lg:p-4">
            <div className="grid gap-3 lg:grid-cols-[1.3fr_150px_150px_150px_150px_auto] lg:items-end">
              <label className="block">
                <span className="text-xs font-semibold text-slate-500">搜索</span>
                <span className="relative mt-1 block">
                  <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    className="focus-ring h-9 w-full rounded-md border border-slate-300 pl-9 pr-3 text-sm"
                    placeholder="代码、symbol、简称、关注原因"
                  />
                </span>
              </label>
              <FilterSelect label="分组" value={groupId} onChange={setGroupId}>
                <option value={ALL}>全部分组</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect label="标签" value={tagId} onChange={setTagId}>
                <option value={ALL}>全部标签</option>
                {tags.map((tag) => (
                  <option key={tag.id} value={tag.id}>
                    {tag.name}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect label="交易所" value={exchange} onChange={setExchange}>
                <option value={ALL}>全部交易所</option>
                {availableExchanges.map((item) => (
                  <option key={item} value={item}>
                    {exchangeLabel(item)}
                  </option>
                ))}
              </FilterSelect>
              <FilterSelect label="板块" value={board} onChange={setBoard}>
                <option value={ALL}>全部板块</option>
                {availableBoards.map((item) => (
                  <option key={item} value={item}>
                    {boardLabel(item)}
                  </option>
                ))}
              </FilterSelect>
              <button
                onClick={() => {
                  setQuery("");
                  setGroupId(ALL);
                  setTagId(ALL);
                  setExchange(ALL);
                  setBoard(ALL);
                }}
                className="focus-ring h-9 rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
                type="button"
              >
                清除筛选
              </button>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              当前显示 {filteredItems.length} / {items.length} 只；行情为空时明确显示“暂无经授权的真实行情数据。”。
            </p>
          </section>

          {items.length === 0 ? (
            <EmptyState
              title="暂无自选股"
              description="请先通过本地证券目录搜索真实股票，再加入自选股。若搜索结果很少，请管理员先同步真实 A 股证券目录。"
              action={
                <button
                  onClick={() => setPanel("add")}
                  className="focus-ring inline-flex h-10 items-center rounded-md bg-slate-900 px-4 text-sm font-semibold text-white"
                  type="button"
                >
                  添加自选股
                </button>
              }
            />
          ) : filteredItems.length === 0 ? (
            <EmptyState title="没有匹配的自选股" description="请调整搜索、分组、标签、交易所或板块筛选条件。" />
          ) : (
            <>
              <DesktopWatchlistTable items={filteredItems} marketSnapshots={marketSnapshots} onEdit={openEdit} />
              <MobileWatchlistList items={filteredItems} marketSnapshots={marketSnapshots} />
            </>
          )}
        </>
      ) : null}

      {panel === "add" ? (
        <AddWatchlistPanel
          existingItems={items}
          groups={groups}
          tags={tags}
          onClose={closePanel}
          onSaved={async (savedMessage) => {
            setMessage(savedMessage);
            closePanel();
            await loadData();
          }}
        />
      ) : null}
      {panel === "edit" && editingItem ? (
        <EditWatchlistPanel
          item={editingItem}
          groups={groups}
          tags={tags}
          onClose={closePanel}
          onSaved={async (savedMessage) => {
            setMessage(savedMessage);
            closePanel();
            await loadData();
          }}
        />
      ) : null}
    </div>
  );
}

function SecurityDirectoryNotice({ status }: { status: SecurityMasterStatus }) {
  const seedOnly = status.total_count <= 4 && status.development_seed_count === status.total_count;
  return (
    <section
      className={`rounded-lg border p-4 text-sm leading-6 ${
        seedOnly ? "border-rose-200 bg-rose-50 text-rose-950" : "border-slate-200 bg-white text-slate-700"
      }`}
    >
      <div className="flex gap-2">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <p className="font-semibold">
            {seedOnly ? "当前证券目录仍为开发样本" : "证券目录状态"}
          </p>
          <p className="mt-1">
            股票总数 {status.total_count}，正常上市 {status.active_count}，
            development_seed {status.development_seed_count}，最近同步{" "}
            {formatTime(status.last_synced_at) ?? "暂无"}。
          </p>
          {status.data_gaps.length > 0 ? (
            <ul className="mt-2 space-y-1 text-xs">
              {status.data_gaps.map((gap) => (
                <li key={gap}>{gap}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function DesktopWatchlistTable({
  items,
  marketSnapshots,
  onEdit
}: {
  items: WatchlistItemRead[];
  marketSnapshots: Record<string, WatchlistMarketSnapshot>;
  onEdit: (item: WatchlistItemRead) => void;
}) {
  return (
    <section className="hidden overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm lg:block">
      <div className="grid grid-cols-[1.25fr_0.85fr_0.9fr_0.9fr_1.1fr_1fr_1.2fr_0.9fr] border-b border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-500">
        <span>股票</span>
        <span>最新价 / 涨跌</span>
        <span>板块</span>
        <span>上市状态</span>
        <span>行情数据状态</span>
        <span>分组 / 标签</span>
        <span>关注原因</span>
        <span>操作</span>
      </div>
      {items.map((item) => {
        const market = marketSnapshots[item.id];
        return (
          <div
            key={item.id}
            className="grid grid-cols-[1.25fr_0.85fr_0.9fr_0.9fr_1.1fr_1fr_1.2fr_0.9fr] items-center gap-3 border-b border-slate-100 px-4 py-3 last:border-b-0"
          >
            <StockIdentity stock={item.stock} />
            <MarketPriceCell market={market} />
            <p className="text-sm text-slate-700">{boardLabel(item.stock.board)}</p>
            <StatusPill value={listingStatusLabel(item.stock.listing_status)} tone={statusTone(item.stock.listing_status)} />
            <MarketStatusCell market={market} />
            <div className="min-w-0 text-xs leading-5 text-slate-600">
              <p className="font-medium text-slate-800">{item.group?.name ?? "未分组"}</p>
              <p className="truncate">{item.tags.length ? item.tags.map((tag) => tag.name).join("；") : "无标签"}</p>
            </div>
            <p className="line-clamp-2 text-sm leading-6 text-slate-700">{item.attention_reason || "未填写"}</p>
            <div className="flex flex-wrap gap-2">
              <Link
                href={`/watchlist/${item.stock.id}`}
                className="focus-ring inline-flex h-8 items-center justify-center rounded-md bg-slate-900 px-2 text-xs font-semibold text-white hover:bg-slate-800"
              >
                详情
              </Link>
              <button
                onClick={() => onEdit(item)}
                className="focus-ring inline-flex h-8 items-center justify-center gap-1 rounded-md border border-slate-300 px-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                type="button"
              >
                <Edit3 className="h-3.5 w-3.5" />
                编辑
              </button>
            </div>
          </div>
        );
      })}
    </section>
  );
}

function MobileWatchlistList({
  items,
  marketSnapshots
}: {
  items: WatchlistItemRead[];
  marketSnapshots: Record<string, WatchlistMarketSnapshot>;
}) {
  return (
    <section className="grid gap-2 lg:hidden">
      {items.map((item) => {
        const market = marketSnapshots[item.id];
        const snapshot = market?.snapshot;
        return (
          <Link
            key={item.id}
            href={`/watchlist/${item.stock.id}`}
            className="focus-ring grid min-h-[86px] grid-cols-[minmax(0,1fr)_96px] gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-left shadow-sm active:bg-slate-50"
          >
            <div className="min-w-0">
              <div className="flex min-w-0 items-center gap-2">
                <p className="truncate text-sm font-semibold text-slate-950">{displayName(item.stock)}</p>
                <span className="shrink-0 text-[11px] text-slate-500">{item.stock.code}</span>
                <StatusPill value={listingStatusLabel(item.stock.listing_status)} tone={statusTone(item.stock.listing_status)} />
              </div>
              <p className="mt-1 truncate text-[11px] text-slate-600">
                {exchangeLabel(item.stock.exchange)} / {boardLabel(item.stock.board)} / {item.group?.name ?? "未分组"}
              </p>
              <p className="mt-1 truncate text-[11px] text-slate-500">
                {item.tags.length ? item.tags.slice(0, 2).map((tag) => tag.name).join("；") : "无标签"}
                {item.tags.length > 2 ? ` +${item.tags.length - 2}` : ""}
              </p>
              <p className="mt-1 truncate text-[11px] text-slate-500">{market?.message ?? "暂无经授权的真实行情数据。"}</p>
            </div>
            <div className="flex min-w-0 flex-col items-end justify-between">
              <div className="text-right">
                <p className="text-sm font-semibold text-slate-950">{snapshot?.close ? formatDecimal(snapshot.close) : "暂无"}</p>
                <p className={`text-xs font-semibold ${changeTone(snapshot?.pct_change ?? null)}`}>
                  {formatChange(snapshot?.pct_change ?? null)}
                </p>
              </div>
              <span className={`rounded-md border px-2 py-0.5 text-[10px] font-semibold ${marketStatusTone(market?.status)}`}>
                {marketStatusLabel(market?.status)}
              </span>
            </div>
          </Link>
        );
      })}
    </section>
  );
}

function MarketPriceCell({ market }: { market: WatchlistMarketSnapshot | undefined }) {
  const snapshot = market?.snapshot;
  return (
    <div className="text-sm leading-5">
      <p className="font-semibold text-slate-950">{snapshot?.close ? formatDecimal(snapshot.close) : "暂无"}</p>
      <p className={`text-xs font-semibold ${changeTone(snapshot?.pct_change ?? null)}`}>
        {formatChange(snapshot?.pct_change ?? null)}
      </p>
    </div>
  );
}

function MarketStatusCell({ market }: { market: WatchlistMarketSnapshot | undefined }) {
  return (
    <div className="text-xs leading-5 text-slate-600">
      <StatusPill value={marketStatusLabel(market?.status)} tone={marketStatusPillTone(market?.status)} />
      <p className="mt-1">
        {market?.snapshot ? `${market.snapshot.source_code} / ${market.snapshot.trade_date}` : "暂无经授权的真实行情数据。"}
      </p>
    </div>
  );
}

function AddWatchlistPanel({
  existingItems,
  groups,
  tags,
  onClose,
  onSaved
}: {
  existingItems: WatchlistItemRead[];
  groups: WatchlistGroupRead[];
  tags: UserTagRead[];
  onClose: () => void;
  onSaved: (message: string) => Promise<void>;
}) {
  const [stockQuery, setStockQuery] = useState("");
  const [results, setResults] = useState<StockRead[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockRead | null>(null);
  const [selectedGroupId, setSelectedGroupId] = useState(groups.find((group) => group.is_default)?.id ?? "");
  const [newGroupName, setNewGroupName] = useState("");
  const [tagText, setTagText] = useState("");
  const [attentionReason, setAttentionReason] = useState("");
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const alreadyAdded = selectedStock
    ? existingItems.some((item) => item.stock.id === selectedStock.id)
    : false;

  async function handleSearch() {
    const q = stockQuery.trim();
    if (!q) {
      setResults([]);
      setError("请输入股票代码、symbol、简称、全称、拼音、拼音首字母或历史简称。");
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const page = await searchStocks({ q, limit: 20 });
      setResults(page.items);
      if (page.items.length === 0) {
        setError("没有在本地证券目录中找到匹配股票，请确认管理员已同步真实证券目录。");
      }
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSearching(false);
    }
  }

  async function handleSave() {
    if (!selectedStock) {
      setError("请先从搜索结果中选择一只股票。");
      return;
    }
    if (alreadyAdded) {
      await onSaved("该股票已在自选股中，本次未重复创建。");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const groupId = await resolveGroupId(groups, selectedGroupId, newGroupName);
      const tagIds = await resolveTagIds(tags, tagText);
      await createWatchlistItem({
        stock_id: selectedStock.id,
        group_id: groupId,
        attention_reason: attentionReason.trim() || null,
        tag_ids: tagIds
      });
      await onSaved("自选股已添加。");
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <PanelFrame title="添加自选股" onClose={onClose}>
      <div className="grid gap-4">
        <div>
          <label className="text-sm font-medium text-slate-700">股票搜索</label>
          <div className="mt-1 flex gap-2">
            <input
              value={stockQuery}
              onChange={(event) => setStockQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  void handleSearch();
                }
              }}
              className="focus-ring h-10 min-w-0 flex-1 rounded-md border border-slate-300 px-3 text-sm"
              placeholder="600519、600519.SH、贵州茅台、gzmt"
            />
            <button
              onClick={() => void handleSearch()}
              disabled={searching}
              className="focus-ring inline-flex h-10 items-center gap-2 rounded-md bg-slate-900 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
              type="button"
            >
              <Search className="h-4 w-4" />
              {searching ? "搜索中" : "搜索"}
            </button>
          </div>
        </div>

        <div className="max-h-64 overflow-y-auto rounded-md border border-slate-200">
          {results.map((stock) => (
            <button
              key={stock.id}
              onClick={() => setSelectedStock(stock)}
              className={`block w-full border-b border-slate-100 p-3 text-left last:border-b-0 hover:bg-slate-50 ${
                selectedStock?.id === stock.id ? "bg-blue-50" : "bg-white"
              }`}
              type="button"
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold text-slate-950">{displayName(stock)}</p>
                <span className="text-xs text-slate-500">{stock.symbol}</span>
                <StatusPill value={listingStatusLabel(stock.listing_status)} tone={statusTone(stock.listing_status)} />
              </div>
              <p className="mt-1 text-xs leading-5 text-slate-600">
                {exchangeLabel(stock.exchange)} / {boardLabel(stock.board)} / 来源 {stock.source_code} / 同步{" "}
                {formatTime(stock.last_synced_at) ?? "暂无"}
              </p>
            </button>
          ))}
          {results.length === 0 ? (
            <p className="p-3 text-sm leading-6 text-slate-500">搜索结果会显示在这里。用户不能手写不存在的股票。</p>
          ) : null}
        </div>

        <WatchlistFields
          groups={groups}
          selectedGroupId={selectedGroupId}
          newGroupName={newGroupName}
          tagText={tagText}
          attentionReason={attentionReason}
          onGroupChange={setSelectedGroupId}
          onNewGroupNameChange={setNewGroupName}
          onTagTextChange={setTagText}
          onAttentionReasonChange={setAttentionReason}
        />

        {alreadyAdded ? (
          <p className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">该股票已在自选股中，确认后不会重复创建。</p>
        ) : null}
        {error ? <ErrorState title="无法添加自选股" description={error} /> : null}
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="focus-ring h-10 rounded-md border border-slate-300 px-4 text-sm font-semibold text-slate-700"
            type="button"
          >
            取消
          </button>
          <button
            onClick={() => void handleSave()}
            disabled={saving}
            className="focus-ring h-10 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
            type="button"
          >
            {saving ? "保存中" : "确认添加"}
          </button>
        </div>
      </div>
    </PanelFrame>
  );
}

function EditWatchlistPanel({
  item,
  groups,
  tags,
  onClose,
  onSaved
}: {
  item: WatchlistItemRead;
  groups: WatchlistGroupRead[];
  tags: UserTagRead[];
  onClose: () => void;
  onSaved: (message: string) => Promise<void>;
}) {
  const [selectedGroupId, setSelectedGroupId] = useState(item.group?.id ?? groups.find((group) => group.is_default)?.id ?? "");
  const [newGroupName, setNewGroupName] = useState("");
  const [tagText, setTagText] = useState(item.tags.map((tag) => tag.name).join("；"));
  const [attentionReason, setAttentionReason] = useState(item.attention_reason ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const resolvedGroupId = await resolveGroupId(groups, selectedGroupId, newGroupName);
      const tagIds = await resolveTagIds(tags, tagText);
      await updateWatchlistItem(item.id, {
        group_id: resolvedGroupId,
        attention_reason: attentionReason.trim() || null,
        tag_ids: tagIds
      });
      await onSaved("自选股已更新。");
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setSaving(true);
    setError(null);
    try {
      await deleteWatchlistItem(item.id);
      await onSaved("自选股已移除。");
    } catch (caught) {
      setError(humanizeApiError(caught));
    } finally {
      setSaving(false);
    }
  }

  return (
    <PanelFrame title="编辑自选股" onClose={onClose}>
      <div className="grid gap-4">
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <StockIdentity stock={item.stock} />
          <p className="mt-2 text-xs text-slate-500">
            {exchangeLabel(item.stock.exchange)} / {boardLabel(item.stock.board)} / 来源 {item.stock.source_code}
          </p>
        </div>
        <WatchlistFields
          groups={groups}
          selectedGroupId={selectedGroupId}
          newGroupName={newGroupName}
          tagText={tagText}
          attentionReason={attentionReason}
          onGroupChange={setSelectedGroupId}
          onNewGroupNameChange={setNewGroupName}
          onTagTextChange={setTagText}
          onAttentionReasonChange={setAttentionReason}
        />
        {error ? <ErrorState title="无法更新自选股" description={error} /> : null}
        <div className="flex flex-wrap justify-between gap-2">
          <button
            onClick={() => void handleDelete()}
            disabled={saving}
            className="focus-ring inline-flex h-10 items-center gap-2 rounded-md border border-rose-300 px-4 text-sm font-semibold text-rose-700 disabled:cursor-not-allowed disabled:text-rose-300"
            type="button"
          >
            <Trash2 className="h-4 w-4" />
            移除
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="focus-ring h-10 rounded-md border border-slate-300 px-4 text-sm font-semibold text-slate-700"
              type="button"
            >
              取消
            </button>
            <button
              onClick={() => void handleSave()}
              disabled={saving}
              className="focus-ring h-10 rounded-md bg-slate-900 px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-400"
              type="button"
            >
              {saving ? "保存中" : "保存"}
            </button>
          </div>
        </div>
      </div>
    </PanelFrame>
  );
}

function WatchlistFields({
  groups,
  selectedGroupId,
  newGroupName,
  tagText,
  attentionReason,
  onGroupChange,
  onNewGroupNameChange,
  onTagTextChange,
  onAttentionReasonChange
}: {
  groups: WatchlistGroupRead[];
  selectedGroupId: string;
  newGroupName: string;
  tagText: string;
  attentionReason: string;
  onGroupChange: (value: string) => void;
  onNewGroupNameChange: (value: string) => void;
  onTagTextChange: (value: string) => void;
  onAttentionReasonChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">分组</span>
          <select
            value={selectedGroupId}
            onChange={(event) => onGroupChange(event.target.value)}
            className="focus-ring mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
          >
            {groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">新分组</span>
          <input
            value={newGroupName}
            onChange={(event) => onNewGroupNameChange(event.target.value)}
            className="focus-ring mt-1 h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
            placeholder="可选，填写后优先使用"
          />
        </label>
      </div>
      <label className="block">
        <span className="text-sm font-medium text-slate-700">标签</span>
        <input
          value={tagText}
          onChange={(event) => onTagTextChange(event.target.value)}
          className="focus-ring mt-1 h-10 w-full rounded-md border border-slate-300 px-3 text-sm"
          placeholder="多个标签使用英文或中文分号分隔"
        />
      </label>
      <label className="block">
        <span className="text-sm font-medium text-slate-700">关注原因</span>
        <textarea
          value={attentionReason}
          onChange={(event) => onAttentionReasonChange(event.target.value)}
          className="focus-ring mt-1 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          placeholder="记录个人关注逻辑，不影响证券主数据"
        />
      </label>
    </div>
  );
}

function PanelFrame({
  title,
  onClose,
  children
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-end bg-slate-950/30 p-4 sm:items-center sm:justify-center">
      <section className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              仅保存当前用户的分组、标签和关注原因；不会修改股票名称、交易所、板块或上市状态。
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
        {children}
      </section>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  children
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="focus-ring mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-2 text-sm text-slate-800"
      >
        {children}
      </select>
    </label>
  );
}

function StockIdentity({ stock }: { stock: StockRead }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-2">
        <p className="truncate font-semibold text-slate-950">{displayName(stock)}</p>
        <span className="shrink-0 text-xs text-slate-500">{stock.symbol}</span>
      </div>
      <p className="mt-1 truncate text-xs text-slate-500">{stock.full_name ?? stock.name}</p>
    </div>
  );
}

function StatusPill({
  value,
  tone
}: {
  value: string;
  tone: "slate" | "emerald" | "amber" | "rose";
}) {
  const tones = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-800",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    rose: "border-rose-200 bg-rose-50 text-rose-800"
  };
  return <span className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${tones[tone]}`}>{value}</span>;
}

function StatusMessage({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm font-medium text-emerald-900">
      {text}
    </div>
  );
}

async function resolveGroupId(
  groups: WatchlistGroupRead[],
  selectedGroupId: string,
  newGroupName: string
): Promise<string | null> {
  const trimmed = newGroupName.trim();
  if (!trimmed) {
    return selectedGroupId || null;
  }
  const existing = groups.find((group) => group.name === trimmed);
  if (existing) {
    return existing.id;
  }
  const created = await createWatchlistGroup(trimmed);
  return created.id;
}

async function resolveTagIds(tags: UserTagRead[], tagText: string): Promise<string[]> {
  const names = splitTagNames(tagText);
  const ids: string[] = [];
  for (const name of names) {
    const existing = tags.find((tag) => tag.name === name);
    if (existing) {
      ids.push(existing.id);
    } else {
      const created = await createWatchlistTag(name);
      ids.push(created.id);
    }
  }
  return ids;
}

function splitTagNames(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[;；]/)
        .map((item) => item.trim())
        .filter(Boolean)
    )
  );
}

function displayName(stock: StockRead): string {
  return stock.short_name || stock.name;
}

function boardLabel(value: string): string {
  return boardLabels[value] ?? value;
}

function exchangeLabel(value: string): string {
  return exchangeLabels[value] ?? value;
}

function listingStatusLabel(value: string): string {
  return listingStatusLabels[value] ?? value;
}

function statusTone(value: string): "slate" | "emerald" | "amber" | "rose" {
  if (value === "active") {
    return "emerald";
  }
  if (value === "suspended" || value === "risk_warning" || value === "pending_listing") {
    return "amber";
  }
  if (value === "delisted" || value === "delisting_period") {
    return "rose";
  }
  return "slate";
}

function marketStatusLabel(value: string | undefined): string {
  if (value === "available") {
    return "行情可用";
  }
  if (value === "stale") {
    return "数据过期";
  }
  if (value === "partial") {
    return "部分缺失";
  }
  return "暂无授权行情";
}

function marketStatusPillTone(value: string | undefined): "slate" | "emerald" | "amber" | "rose" {
  if (value === "available") {
    return "emerald";
  }
  if (value === "stale" || value === "partial") {
    return "amber";
  }
  return "slate";
}

function marketStatusTone(value: string | undefined): string {
  if (value === "available") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (value === "stale" || value === "partial") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function formatDecimal(value: DecimalValue): string {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value);
  }
  return numberValue.toFixed(2);
}

function formatChange(value: DecimalValue | null): string {
  if (value === null) {
    return "暂无涨跌";
  }
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) {
    return String(value);
  }
  const direction = numberValue > 0 ? "上涨" : numberValue < 0 ? "下跌" : "持平";
  const prefix = numberValue > 0 ? "+" : "";
  return `${prefix}${numberValue.toFixed(2)}% ${direction}`;
}

function changeTone(value: DecimalValue | null): string {
  if (value === null) {
    return "text-slate-500";
  }
  const numberValue = Number(value);
  if (numberValue > 0) {
    return "text-red-600";
  }
  if (numberValue < 0) {
    return "text-emerald-700";
  }
  return "text-slate-600";
}

function formatTime(value: string | null): string | null {
  if (!value) {
    return null;
  }
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  } catch {
    return value;
  }
}
