from datetime import date, datetime
from uuid import UUID

from app.schemas.common import OrmModel


class StockRead(OrmModel):
    id: UUID
    symbol: str
    code: str
    exchange: str
    name: str
    market: str
    board: str
    security_type: str
    short_name: str
    full_name: str | None
    english_name: str | None
    listing_status: str
    listed_at: date | None
    delisted_at: date | None
    aliases: list[str]
    pinyin: str | None
    pinyin_initials: str | None
    source_code: str
    source_record_id: str | None
    source_updated_at: datetime | None
    last_synced_at: datetime | None
    data_completeness: str
    is_searchable: bool
    list_status: str
    list_date: date | None
    delist_date: date | None
    currency: str
    data_source: str
    created_at: datetime
    updated_at: datetime
