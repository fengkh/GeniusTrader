from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.market_data import StockMarketSnapshotOut, WatchlistMarketSnapshotOut
from app.schemas.research import ResearchTaskOut
from app.schemas.stock import StockRead
from app.schemas.watchlist import UserTagRead, WatchlistGroupRead


class TodayOverviewStats(BaseModel):
    business_date: date
    watchlist_count: int
    market_trade_date: date | None = None
    market_snapshot_count: int = 0
    market_data_available_count: int = 0
    market_data_unavailable_count: int = 0
    gainers_count: int = 0
    decliners_count: int = 0
    unchanged_count: int = 0
    stocks_with_new_information: int
    new_announcement_candidate_count: int
    pending_announcement_candidate_count: int
    stale_review_count: int
    open_research_task_count: int
    due_observation_count: int
    information_needing_analysis_count: int
    latest_review_status: str | None
    market_data_status: str


class PriorityStockOut(BaseModel):
    stock_id: UUID
    symbol: str
    name: str
    priority_score: int
    priority_reasons: list[str]
    new_information_count: int
    pending_candidate_count: int
    open_task_count: int
    due_observation_count: int
    review_status: str | None
    close: Decimal | None = None
    pct_change: Decimal | None = None
    amount: Decimal | None = None
    turnover_rate: Decimal | None = None
    trade_date: date | None = None
    source_code: str | None = None
    freshness_status: str | None = None
    latest_market_snapshot: WatchlistMarketSnapshotOut | None


class TodayActionItemOut(BaseModel):
    count: int
    target_url: str
    severity: Literal["info", "notice", "important"]
    title: str


class TodayObservationConditionOut(BaseModel):
    task_id: UUID
    stock: StockRead | None
    title: str
    due_date: date | None
    status: str
    source_review: str | None


class LatestReviewOut(BaseModel):
    review_id: UUID | None
    review_date: date | None
    status: str | None
    stale: bool
    version: int | None
    generation_in_progress: bool


class TodayOverviewOut(BaseModel):
    overview: TodayOverviewStats
    priority_stocks: list[PriorityStockOut]
    action_items: list[TodayActionItemOut]
    observation_conditions: list[TodayObservationConditionOut]
    latest_review: LatestReviewOut


class WatchlistScannerRowOut(BaseModel):
    watchlist_item_id: UUID
    stock_id: UUID
    symbol: str
    name: str
    exchange: str
    group: WatchlistGroupRead | None
    tags: list[UserTagRead]
    focus_reason: str | None
    latest_market_snapshot: WatchlistMarketSnapshotOut | None
    trade_date: date | None = None
    close: Decimal | None = None
    change: Decimal | None = None
    pct_change: Decimal | None = None
    volume: Decimal | None = None
    amount: Decimal | None = None
    turnover_rate: Decimal | None = None
    source_code: str | None = None
    freshness_status: str | None = None
    new_information_count: int
    official_announcement_count_7d: int
    pending_candidate_count: int
    open_verification_count: int
    open_observation_count: int
    high_priority_task_count: int
    review_status: str | None
    latest_review_date: date | None
    stale: bool
    last_information_at: datetime | None
    attention_score: int
    attention_reasons: list[str]


class WatchlistScannerOut(BaseModel):
    items: list[WatchlistScannerRowOut]
    total: int


class WatchlistProfileOut(BaseModel):
    group: WatchlistGroupRead | None
    tags: list[UserTagRead]
    focus_reason: str | None
    user_notes: str | None
    created_at: datetime
    updated_at: datetime


class StockCurrentStateOut(BaseModel):
    new_information_count: int
    pending_candidate_count: int
    open_task_count: int
    observation_count: int
    latest_review_status: str | None
    stale: bool


class OfficialInformationOut(BaseModel):
    id: UUID
    title: str | None
    source_type: str
    status: str
    is_important: bool
    created_at: datetime
    target_url: str


class TimelineEntryOut(BaseModel):
    event_type: str
    occurred_at: datetime
    title: str
    summary: str
    source_label: str
    target_url: str
    confidence: str | None
    data_completeness: str | None
    created_by: str


class ReviewHistoryOut(BaseModel):
    review_id: UUID
    review_date: date
    status: str
    stale: bool
    version_count: int
    latest_version: int | None
    target_url: str


class StockResearchDossierOut(BaseModel):
    identity: StockRead
    watchlist_profile: WatchlistProfileOut
    market_snapshot: StockMarketSnapshotOut
    current_state: StockCurrentStateOut
    official_information: list[OfficialInformationOut]
    research_tasks: list[ResearchTaskOut]
    timeline: list[TimelineEntryOut]
    review_history: list[ReviewHistoryOut]
    data_boundaries: list[str]


class SuggestedTaskOut(BaseModel):
    identifier: str
    task_type: str
    title: str
    reason: str
    priority: str
    related_fact_indexes: list[int]
    suggested_due_date: date | None = None
    raw: dict[str, Any] = {}
