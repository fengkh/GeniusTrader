from datetime import date, datetime
from uuid import UUID

from app.schemas.common import OrmModel


class StockRead(OrmModel):
    id: UUID
    symbol: str
    exchange: str
    name: str
    market: str
    list_status: str
    list_date: date | None
    delist_date: date | None
    currency: str
    data_source: str
    created_at: datetime
    updated_at: datetime
