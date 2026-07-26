import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExternalSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_code: str
    display_name: str
    publisher_name: str
    source_category: str
    authority_level: str
    source_tier: str
    jurisdiction: str | None
    country_code: str | None
    region_code: str | None
    city_code: str | None
    official_domain: str | None
    access_mode: str
    content_language: str
    provider_adapter: str | None
    authorization_status: str
    redistribution_status: str
    commercial_use_status: str
    legal_review_status: str
    health_status: str
    enabled: bool
    experimental: bool
    limitations: list[str]
    created_at: datetime
    updated_at: datetime


class AnnouncementProviderOut(BaseModel):
    source_code: str
    provider_adapter: str
    implemented: bool
    enabled_by_config: bool
    experimental: bool
    experimental_limited: bool = False
    capabilities: list[str]
    limitations: list[str]


class FutureSourceGroupOut(BaseModel):
    group: str
    examples: list[str]
    status: str

