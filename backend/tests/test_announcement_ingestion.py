from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

import app.providers.announcements.document_extraction as document_extraction
import app.providers.base as provider_base
import app.services.announcement_ingestion as announcement_service
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.time import utc_now
from app.core.url_security import ValidatedUrl
from app.models.ai import AITask
from app.models.external_source import (
    AnnouncementRecord,
    ExternalSource,
    InformationIngestionLink,
    ProviderSyncRun,
    UserAnnouncementCandidate,
)
from app.models.information import (
    InformationContent,
    InformationItem,
    InformationStockRelation,
)
from app.models.review_notification import (
    BusinessEvent,
    DailyReview,
    DailyReviewVersion,
    Notification,
)
from app.models.stock import Stock
from app.providers.announcements.classification import classify_announcement
from app.providers.announcements.document_extraction import ExtractedAnnouncementDocument
from app.providers.announcements.models import NormalizedAnnouncement, ProviderResult
from app.providers.base import ProviderHttpResult
from app.providers.statuses import ProviderStatus
from tests.conftest import create_user, login, seed_stock, unique_username

pytestmark = pytest.mark.asyncio

CN_TZ = ZoneInfo("Asia/Shanghai")


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeAnnouncementProvider:
    def __init__(
        self,
        *,
        records: list[NormalizedAnnouncement] | None = None,
        status: ProviderStatus = ProviderStatus.PASS,
        errors: list[dict[str, str]] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.records = records or []
        self.status = status
        self.errors = errors or []
        self.raises = raises

    async def list_announcements(self, query):
        if self.raises:
            raise self.raises
        return ProviderResult(
            status=self.status,
            records=self.records,
            next_cursor=_cursor_for(self.records),
            errors=self.errors,
            metrics={"fake_provider": True, "symbol_count": len(query.symbols)},
            provider_metadata={"adapter": "fake", "redacted": True},
            request_count=1,
            success_count=1 if self.status in {ProviderStatus.PASS, ProviderStatus.PARTIAL} else 0,
            failure_count=0 if self.status in {ProviderStatus.PASS, ProviderStatus.PARTIAL} else 1,
        )


def _cursor_for(records: list[NormalizedAnnouncement]) -> str | None:
    if not records:
        return None
    latest = records[0]
    return f"{latest.published_at.isoformat() if latest.published_at else ''}|{latest.provider_announcement_id or ''}"


def _record(
    *,
    provider_id: str = "fake-1",
    symbol: str = "600519.SH",
    title: str = "Alpha Tech annual report",
    company_name: str = "Alpha Tech",
    source_page_url: str = "https://www.cninfo.com.cn/new/disclosure/detail",
    document_url: str | None = "https://static.cninfo.com.cn/finalpage/fake.pdf",
    published_on: date | None = None,
) -> NormalizedAnnouncement:
    published_on = published_on or date.today()
    published_at = datetime.combine(published_on, time(15, 30), tzinfo=CN_TZ)
    return NormalizedAnnouncement(
        source_code="CNINFO",
        provider_announcement_id=provider_id,
        title=title,
        normalized_title=title.lower(),
        announcement_type="periodic_report",
        announcement_type_confidence=0.9,
        announcement_type_basis={"method": "test_fixture", "not_investment_judgment": True},
        published_at=published_at,
        company_name=company_name,
        stock_symbols=[symbol],
        exchange=symbol.split(".")[1],
        source_page_url=source_page_url,
        document_url=document_url,
        attachment_urls=[document_url] if document_url else [],
        is_pdf=bool(document_url),
        is_correction=False,
        corrected_announcement_id=None,
        raw_metadata_hash=f"raw-{provider_id}",
        deduplication_key=f"dedupe-{provider_id}",
        data_completeness="complete" if document_url else "usable",
        missing_fields=[] if document_url else ["document_url"],
        fetched_at=utc_now(),
    )


def _enable_flags(monkeypatch, **overrides: str) -> None:
    values = {
        "APP_ENV": "development",
        "ANNOUNCEMENT_INGESTION_ENABLED": "true",
        "ANNOUNCEMENT_REAL_NETWORK_ENABLED": "true",
        "ANNOUNCEMENT_CNINFO_ENABLED": "true",
        "ANNOUNCEMENT_SYNC_LOOKBACK_DAYS": "30",
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _patch_provider(monkeypatch, provider: FakeAnnouncementProvider) -> None:
    monkeypatch.setattr(announcement_service, "get_announcement_provider", lambda source_code, settings: provider)
    monkeypatch.setattr(announcement_service, "is_provider_enabled", lambda source_code, settings: True)


async def _login_user(client: AsyncClient, db_session, *, prefix: str = "ann"):
    user = await create_user(db_session, username=unique_username(prefix), password="Password12345")
    response = await login(client, username=user.username, password="Password12345")
    assert response.status_code == 200
    return user


async def _add_watchlist_stock(client: AsyncClient, db_session, *, symbol: str = "600519", exchange: str = "SH"):
    stock = await seed_stock(db_session, symbol=symbol, exchange=exchange, name="Alpha Tech")
    response = await client.post("/api/v1/watchlist", json={"stock_id": str(stock.id), "attention_reason": "test"})
    assert response.status_code == 201
    return stock


async def _enable_source(db_session, *, source_code: str = "CNINFO", **overrides) -> ExternalSource:
    source = (
        await db_session.execute(select(ExternalSource).where(ExternalSource.source_code == source_code))
    ).scalar_one()
    source.enabled = overrides.pop("enabled", True)
    source.authorization_status = overrides.pop("authorization_status", "testing_only")
    source.redistribution_status = overrides.pop("redistribution_status", "metadata_only")
    source.commercial_use_status = overrides.pop("commercial_use_status", "review_required")
    source.legal_review_status = overrides.pop("legal_review_status", "pending")
    for key, value in overrides.items():
        setattr(source, key, value)
    await db_session.commit()
    await db_session.refresh(source)
    return source


async def _sync_candidate(client: AsyncClient, db_session, monkeypatch, *, provider_id: str = "fake-1"):
    _enable_flags(monkeypatch)
    await _enable_source(db_session)
    _patch_provider(monkeypatch, FakeAnnouncementProvider(records=[_record(provider_id=provider_id)]))
    response = await client.post(
        "/api/v1/announcement-sync-runs",
        json={
            "source_code": "CNINFO",
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
            "use_current_watchlist": True,
        },
    )
    assert response.status_code == 201
    candidate = (await db_session.execute(select(UserAnnouncementCandidate))).scalar_one()
    return candidate, response.json()["data"]


async def test_external_source_registry_defaults_and_provider_catalog(client: AsyncClient, db_session):
    await _login_user(client, db_session)

    sources = await client.get("/api/v1/external-sources")
    assert sources.status_code == 200
    by_code = {item["source_code"]: item for item in sources.json()["data"]}
    assert {"CNINFO", "SSE_DISCLOSURE"} <= set(by_code)
    assert by_code["CNINFO"]["enabled"] is False
    assert by_code["CNINFO"]["experimental"] is True
    assert by_code["CNINFO"]["source_tier"] == "s"
    assert by_code["CNINFO"]["authorization_status"] == "review_required"

    providers = await client.get("/api/v1/announcement-providers")
    assert providers.status_code == 200
    catalog = {item["source_code"]: item for item in providers.json()["data"]}
    assert catalog["CNINFO"]["implemented"] is True
    assert catalog["CNINFO"]["enabled_by_config"] is False
    assert catalog["SZSE_DISCLOSURE"]["implemented"] is False
    assert catalog["BSE_DISCLOSURE"]["enabled_by_config"] is False

    future = await client.get("/api/v1/external-sources/future-groups")
    assert future.status_code == 200
    assert all("implemented" not in item for item in future.json()["data"])


async def test_sync_guards_default_disabled_source_disabled_production_and_legal_hold(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    payload = {
        "source_code": "CNINFO",
        "date_from": date.today().isoformat(),
        "date_to": date.today().isoformat(),
        "use_current_watchlist": True,
    }

    disabled = await client.post("/api/v1/announcement-sync-runs", json=payload)
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "ANNOUNCEMENT_FEATURE_DISABLED"

    _enable_flags(monkeypatch)
    source_disabled = await client.post("/api/v1/announcement-sync-runs", json=payload)
    assert source_disabled.status_code == 403
    assert source_disabled.json()["error"]["code"] == "EXTERNAL_SOURCE_DISABLED"

    await _enable_source(db_session, authorization_status="prohibited")
    prohibited = await client.post("/api/v1/announcement-sync-runs", json=payload)
    assert prohibited.status_code == 403
    assert prohibited.json()["error"]["code"] == "EXTERNAL_SOURCE_AUTHORIZATION_REQUIRED"

    await _enable_source(db_session, legal_review_status="blocked")
    blocked = await client.post("/api/v1/announcement-sync-runs", json=payload)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "EXTERNAL_SOURCE_LEGAL_HOLD"

    await _enable_source(db_session, health_status="legal_hold")
    health_hold = await client.post("/api/v1/announcement-sync-runs", json=payload)
    assert health_hold.status_code == 403
    assert health_hold.json()["error"]["code"] == "EXTERNAL_SOURCE_LEGAL_HOLD"

    await _enable_source(db_session)
    _enable_flags(monkeypatch, APP_ENV="production")
    production = await client.post("/api/v1/announcement-sync-runs", json=payload)
    assert production.status_code == 403
    assert production.json()["error"]["code"] == "ANNOUNCEMENT_REAL_NETWORK_DISABLED"


async def test_sync_creates_shared_records_private_candidates_and_no_side_effects(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    await _add_watchlist_stock(client, db_session)
    _enable_flags(monkeypatch)
    await _enable_source(db_session)
    _patch_provider(
        monkeypatch,
        FakeAnnouncementProvider(
            records=[
                _record(provider_id="match-1", symbol="600519.SH"),
                _record(provider_id="unmatched-1", symbol="300750.SZ", company_name="Other Co"),
            ]
        ),
    )

    response = await client.post(
        "/api/v1/announcement-sync-runs",
        json={
            "source_code": "CNINFO",
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
            "use_current_watchlist": True,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "complete"
    assert data["record_count"] == 2
    assert data["candidate_count"] == 1
    assert data["experimental_notice"]

    assert (await db_session.execute(select(func.count()).select_from(AnnouncementRecord))).scalar_one() == 2
    assert (await db_session.execute(select(func.count()).select_from(UserAnnouncementCandidate))).scalar_one() == 1
    assert (await db_session.execute(select(func.count()).select_from(Stock))).scalar_one() == 1
    assert (await db_session.execute(select(func.count()).select_from(InformationItem))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(BusinessEvent))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(Notification))).scalar_one() == 0

    candidates = await client.get("/api/v1/announcement-candidates")
    assert candidates.status_code == 200
    candidate = candidates.json()["data"]["items"][0]
    assert candidate["match_type"] == "exact_symbol"
    assert candidate["source_tier"] == "s"
    assert candidate["experimental_notice"]

    detail = await client.get(f"/api/v1/announcement-candidates/{candidate['id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["detail_notice"]
    assert detail.json()["data"]["match_evidence"]["matched_symbol"] == "600519.SH"


async def test_deduplication_and_user_candidate_isolation(client: AsyncClient, db_session, monkeypatch):
    user_a = await _login_user(client, db_session, prefix="ann_a")
    stock = await _add_watchlist_stock(client, db_session)
    candidate_a, first_run = await _sync_candidate(client, db_session, monkeypatch, provider_id="shared-1")

    second_run = await client.post(
        "/api/v1/announcement-sync-runs",
        json={
            "source_code": "CNINFO",
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
            "use_current_watchlist": True,
        },
    )
    assert second_run.status_code == 201
    assert first_run["created_record_count"] == 1
    assert second_run.json()["data"]["duplicate_record_count"] == 1
    assert (await db_session.execute(select(func.count()).select_from(AnnouncementRecord))).scalar_one() == 1

    await client.post("/api/v1/auth/logout")
    user_b = await _login_user(client, db_session, prefix="ann_b")
    assert user_a.id != user_b.id
    add_b = await client.post("/api/v1/watchlist", json={"stock_id": str(stock.id), "attention_reason": "test-b"})
    assert add_b.status_code == 201
    _enable_flags(monkeypatch)
    _patch_provider(monkeypatch, FakeAnnouncementProvider(records=[_record(provider_id="shared-1")]))

    sync_b = await client.post(
        "/api/v1/announcement-sync-runs",
        json={
            "source_code": "CNINFO",
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
            "use_current_watchlist": True,
        },
    )
    assert sync_b.status_code == 201
    assert (await db_session.execute(select(func.count()).select_from(AnnouncementRecord))).scalar_one() == 1
    assert (await db_session.execute(select(func.count()).select_from(UserAnnouncementCandidate))).scalar_one() == 2
    assert (await client.get(f"/api/v1/announcement-candidates/{candidate_a.id}")).status_code == 404
    assert (await client.patch(f"/api/v1/announcement-candidates/{candidate_a.id}", json={"status": "dismissed"})).status_code == 404
    _enable_flags(monkeypatch, ANNOUNCEMENT_DOCUMENT_EXTRACTION_ENABLED="true")
    assert (await client.post(f"/api/v1/announcement-candidates/{candidate_a.id}/extract-document")).status_code == 404
    assert (
        await client.post(
            f"/api/v1/announcement-candidates/{candidate_a.id}/import",
            json={"import_mode": "metadata_only"},
        )
    ).status_code == 404

    own_candidates = await client.get("/api/v1/announcement-candidates")
    assert own_candidates.json()["data"]["total"] == 1
    candidate_b = own_candidates.json()["data"]["items"][0]
    assert candidate_b["id"] != str(candidate_a.id)


async def test_metadata_import_is_idempotent_and_does_not_auto_analyze_or_notify(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    await _add_watchlist_stock(client, db_session)
    candidate, _run = await _sync_candidate(client, db_session, monkeypatch)

    imported = await client.post(
        f"/api/v1/announcement-candidates/{candidate.id}/import",
        json={"import_mode": "metadata_only", "user_note": "manual review"},
    )

    assert imported.status_code == 201
    data = imported.json()["data"]
    assert data["already_imported"] is False
    info_id = data["information_item_id"]

    duplicate = await client.post(
        f"/api/v1/announcement-candidates/{candidate.id}/import",
        json={"import_mode": "metadata_only"},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["data"]["already_imported"] is True
    assert duplicate.json()["data"]["information_item_id"] == info_id

    item = (await db_session.execute(select(InformationItem).where(InformationItem.id == info_id))).scalar_one()
    content = (
        await db_session.execute(select(InformationContent).where(InformationContent.information_item_id == item.id))
    ).scalar_one()
    relation = (
        await db_session.execute(select(InformationStockRelation).where(InformationStockRelation.information_item_id == item.id))
    ).scalar_one()
    link = (await db_session.execute(select(InformationIngestionLink))).scalar_one()
    await db_session.refresh(candidate)

    assert item.source_type == "announcement"
    assert item.status == "ready"
    assert item.is_important is False
    assert content.content_origin == "user_input"
    assert relation.relation_origin == "rule"
    assert relation.relation_status == "confirmed"
    assert link.import_mode == "metadata_only"
    assert candidate.status == "imported"
    assert (await db_session.execute(select(func.count()).select_from(InformationItem))).scalar_one() == 1
    assert (await db_session.execute(select(func.count()).select_from(InformationIngestionLink))).scalar_one() == 1
    assert (await db_session.execute(select(func.count()).select_from(InformationStockRelation))).scalar_one() == 1
    assert (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one() == 0
    assert (await db_session.execute(select(func.count()).select_from(Notification))).scalar_one() == 0


async def test_announcement_import_marks_existing_review_stale_without_auto_regeneration(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    await _add_watchlist_stock(client, db_session)
    review_date = date.today()
    generated = await client.post("/api/v1/reviews", json={"review_date": review_date.isoformat(), "use_ai": False})
    assert generated.status_code == 201
    review_id = generated.json()["data"]["id"]
    first_version_id = generated.json()["data"]["current_version_id"]
    first_fingerprint = generated.json()["data"]["input_fingerprint"]
    assert generated.json()["data"]["status"] == "empty"

    candidate, _run = await _sync_candidate(client, db_session, monkeypatch, provider_id="stale-import-1")
    ai_before = (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one()

    imported = await client.post(
        f"/api/v1/announcement-candidates/{candidate.id}/import",
        json={"import_mode": "metadata_only"},
    )

    assert imported.status_code == 201
    review = (await db_session.execute(select(DailyReview).where(DailyReview.id == review_id))).scalar_one()
    versions = (
        await db_session.execute(select(DailyReviewVersion).where(DailyReviewVersion.daily_review_id == review.id))
    ).scalars().all()
    stale_events = (
        await db_session.execute(select(BusinessEvent).where(BusinessEvent.event_type == "user_daily_review.became_stale"))
    ).scalars().all()
    assert review.status == "stale"
    assert review.stale_at is not None
    assert str(review.current_version_id) == first_version_id
    assert review.input_fingerprint == first_fingerprint
    assert len(versions) == 1
    assert len(stale_events) == 1
    assert (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one() == ai_before


async def test_document_extraction_and_extracted_document_import_are_opt_in(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    await _add_watchlist_stock(client, db_session)
    candidate, _run = await _sync_candidate(client, db_session, monkeypatch, provider_id="pdf-1")

    disabled = await client.post(f"/api/v1/announcement-candidates/{candidate.id}/extract-document")
    assert disabled.status_code == 403
    assert disabled.json()["error"]["code"] == "ANNOUNCEMENT_FEATURE_DISABLED"

    async def fake_extract(document_url: str, *, official_domain: str | None, settings):
        assert "cninfo.com.cn" in document_url
        assert official_domain == "cninfo.com.cn"
        return ExtractedAnnouncementDocument(
            text="Extracted announcement text is available for this user initiated import.",
            page_count=2,
            character_count=69,
            content_type="application/pdf",
            response_bytes=1024,
            limitations=["fixture only"],
        )

    _enable_flags(monkeypatch, ANNOUNCEMENT_DOCUMENT_EXTRACTION_ENABLED="true")
    monkeypatch.setattr(announcement_service, "extract_announcement_pdf", fake_extract)

    extracted = await client.post(f"/api/v1/announcement-candidates/{candidate.id}/extract-document")
    assert extracted.status_code == 200
    assert extracted.json()["data"]["document_extract_status"] == "succeeded"
    assert extracted.json()["data"]["page_count"] == 2

    imported = await client.post(
        f"/api/v1/announcement-candidates/{candidate.id}/import",
        json={"import_mode": "extracted_document"},
    )
    assert imported.status_code == 201
    info_id = imported.json()["data"]["information_item_id"]
    content = (
        await db_session.execute(select(InformationContent).where(InformationContent.information_item_id == info_id))
    ).scalar_one()
    await db_session.refresh(candidate)
    assert content.content_origin == "provider_document"
    assert content.extraction_method == "announcement_pdf_pypdf"
    assert candidate.document_extract_status == "succeeded"
    assert (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one() == 0


async def test_pdf_document_security_limits_are_enforced_with_fixtures(monkeypatch):
    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class FakeReader:
        def __init__(self, _stream, texts: list[str] | None = None) -> None:
            self.pages = [FakePage(text) for text in (texts or ["usable extracted announcement text"])]

    monkeypatch.setattr(
        document_extraction,
        "validate_public_content_url",
        lambda url: ValidatedUrl(original_url=url, normalized_url=url, host="static.cninfo.com.cn"),
    )
    _enable_flags(
        monkeypatch,
        ANNOUNCEMENT_DOCUMENT_EXTRACTION_ENABLED="true",
        ANNOUNCEMENT_MAX_PDF_BYTES="64",
        ANNOUNCEMENT_MAX_PDF_PAGES="1",
    )
    settings = get_settings()

    async def response(
        *,
        content: bytes = b"%PDF-1.4 fixture",
        content_type: str | None = "application/pdf",
        error_code: str | None = None,
        status_code: int | None = 200,
    ) -> ProviderHttpResult:
        return ProviderHttpResult(
            url="https://static.cninfo.com.cn/finalpage/fake.pdf",
            status_code=status_code,
            elapsed_ms=1,
            content_type=content_type,
            response_bytes=len(content),
            text=None,
            content=content,
            error_code=error_code,
        )

    async def too_large(*args, **kwargs):
        return await response(error_code="MAX_BYTES_EXCEEDED")

    monkeypatch.setattr(document_extraction, "provider_http_request", too_large)
    with pytest.raises(AppError) as too_large_error:
        await document_extraction.extract_announcement_pdf(
            "https://static.cninfo.com.cn/finalpage/fake.pdf",
            official_domain="cninfo.com.cn",
            settings=settings,
        )
    assert too_large_error.value.code == ErrorCode.ANNOUNCEMENT_DOCUMENT_TOO_LARGE

    async def wrong_type(*args, **kwargs):
        return await response(content_type="text/html", content=b"%PDF-1.4 fixture")

    monkeypatch.setattr(document_extraction, "provider_http_request", wrong_type)
    with pytest.raises(AppError) as wrong_type_error:
        await document_extraction.extract_announcement_pdf(
            "https://static.cninfo.com.cn/finalpage/fake.pdf",
            official_domain="cninfo.com.cn",
            settings=settings,
        )
    assert wrong_type_error.value.code == ErrorCode.ANNOUNCEMENT_DOCUMENT_UNAVAILABLE

    async def invalid_signature(*args, **kwargs):
        return await response(content=b"not a pdf")

    monkeypatch.setattr(document_extraction, "provider_http_request", invalid_signature)
    with pytest.raises(AppError) as invalid_signature_error:
        await document_extraction.extract_announcement_pdf(
            "https://static.cninfo.com.cn/finalpage/fake.pdf",
            official_domain="cninfo.com.cn",
            settings=settings,
        )
    assert invalid_signature_error.value.code == ErrorCode.ANNOUNCEMENT_DOCUMENT_PARSE_FAILED

    import pypdf

    async def valid_pdf(*args, **kwargs):
        return await response()

    monkeypatch.setattr(document_extraction, "provider_http_request", valid_pdf)
    monkeypatch.setattr(pypdf, "PdfReader", lambda stream: FakeReader(stream, ["page one text", "page two text"]))
    with pytest.raises(AppError) as too_many_pages_error:
        await document_extraction.extract_announcement_pdf(
            "https://static.cninfo.com.cn/finalpage/fake.pdf",
            official_domain="cninfo.com.cn",
            settings=settings,
        )
    assert too_many_pages_error.value.code == ErrorCode.ANNOUNCEMENT_DOCUMENT_TOO_MANY_PAGES

    monkeypatch.setattr(pypdf, "PdfReader", lambda stream: FakeReader(stream, [""]))
    with pytest.raises(AppError) as text_unavailable_error:
        await document_extraction.extract_announcement_pdf(
            "https://static.cninfo.com.cn/finalpage/fake.pdf",
            official_domain="cninfo.com.cn",
            settings=settings,
        )
    assert text_unavailable_error.value.code == ErrorCode.ANNOUNCEMENT_DOCUMENT_TEXT_UNAVAILABLE

    monkeypatch.setattr(
        pypdf,
        "PdfReader",
        lambda stream: FakeReader(stream, ["This announcement text is intentionally long enough for extraction."]),
    )
    extracted = await document_extraction.extract_announcement_pdf(
        "https://static.cninfo.com.cn/finalpage/fake.pdf",
        official_domain="cninfo.com.cn",
        settings=settings,
    )
    assert extracted.page_count == 1
    assert extracted.character_count >= 20
    assert any("PDF" in limitation for limitation in extracted.limitations)


async def test_provider_http_request_blocks_private_redirect(monkeypatch):
    class FakeCookies:
        def clear(self) -> None:
            return None

    class FakeRedirectResponse:
        is_redirect = True
        status_code = 302
        headers = {"location": "http://127.0.0.1/private.pdf", "content-type": "text/html"}
        url = "https://www.cninfo.com.cn/start"

        async def aiter_bytes(self):
            yield b""

    class FakeResponseContext:
        async def __aenter__(self):
            return FakeRedirectResponse()

        async def __aexit__(self, exc_type, exc, traceback):
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            self.cookies = FakeCookies()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        def stream(self, *args, **kwargs):
            return FakeResponseContext()

    monkeypatch.setattr(
        provider_base,
        "validate_public_content_url",
        lambda url: ValidatedUrl(original_url=url, normalized_url=url, host="www.cninfo.com.cn"),
    )
    monkeypatch.setattr(provider_base.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(AppError) as error:
        await provider_base.provider_http_request(
            "GET",
            "https://www.cninfo.com.cn/start",
            timeout_seconds=1,
            max_bytes=1024,
        )
    assert error.value.code == ErrorCode.URL_REDIRECT_BLOCKED


async def test_user_supplemented_import_requires_text_and_preserves_user_origin(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    await _add_watchlist_stock(client, db_session)
    candidate, _run = await _sync_candidate(client, db_session, monkeypatch, provider_id="supplemented-1")

    empty_text = await client.post(
        f"/api/v1/announcement-candidates/{candidate.id}/import",
        json={"import_mode": "user_supplemented", "supplemented_text": "   "},
    )
    assert empty_text.status_code == 422
    assert empty_text.json()["error"]["code"] == "INFORMATION_CONTENT_REQUIRED"

    imported = await client.post(
        f"/api/v1/announcement-candidates/{candidate.id}/import",
        json={
            "import_mode": "user_supplemented",
            "supplemented_text": "User supplied announcement excerpt for review only.",
        },
    )
    assert imported.status_code == 201
    content = (
        await db_session.execute(
            select(InformationContent).where(
                InformationContent.information_item_id == imported.json()["data"]["information_item_id"]
            )
        )
    ).scalar_one()
    assert content.content_origin == "user_correction"
    assert (await db_session.execute(select(func.count()).select_from(AITask))).scalar_one() == 0


async def test_sync_limits_provider_failures_and_rate_limited_status(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    await _add_watchlist_stock(client, db_session, symbol="600519", exchange="SH")
    await _add_watchlist_stock(client, db_session, symbol="300750", exchange="SZ")
    await _enable_source(db_session)

    _enable_flags(monkeypatch, ANNOUNCEMENT_MAX_SYMBOLS_PER_RUN="1")
    _patch_provider(monkeypatch, FakeAnnouncementProvider(records=[_record()]))
    limited = await client.post(
        "/api/v1/announcement-sync-runs",
        json={
            "source_code": "CNINFO",
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
            "use_current_watchlist": True,
        },
    )
    assert limited.status_code == 422
    assert limited.json()["error"]["code"] == "ANNOUNCEMENT_SYNC_LIMIT_EXCEEDED"

    _enable_flags(monkeypatch, ANNOUNCEMENT_MAX_SYMBOLS_PER_RUN="5")
    _patch_provider(monkeypatch, FakeAnnouncementProvider(raises=RuntimeError("provider blew up")))
    failed = await client.post(
        "/api/v1/announcement-sync-runs",
        json={
            "source_code": "CNINFO",
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
            "use_current_watchlist": False,
            "stock_ids": [],
        },
    )
    assert failed.status_code == 201
    assert failed.json()["data"]["status"] == "data_insufficient"

    failed_with_stock = await client.post(
        "/api/v1/announcement-sync-runs",
        json={
            "source_code": "CNINFO",
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
            "use_current_watchlist": True,
        },
    )
    assert failed_with_stock.status_code == 502
    assert failed_with_stock.json()["error"]["code"] == "ANNOUNCEMENT_SYNC_FAILED"
    latest_run = (
        await db_session.execute(select(ProviderSyncRun).order_by(ProviderSyncRun.started_at.desc()).limit(1))
    ).scalar_one()
    assert latest_run.status == "failed"
    assert latest_run.error_summary == "RuntimeError"

    _patch_provider(
        monkeypatch,
        FakeAnnouncementProvider(
            status=ProviderStatus.RATE_LIMITED,
            errors=[{"code": "ANNOUNCEMENT_PROVIDER_RATE_LIMITED", "summary": "rate limited"}],
        ),
    )
    rate_limited = await client.post(
        "/api/v1/announcement-sync-runs",
        json={
            "source_code": "CNINFO",
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
            "use_current_watchlist": True,
        },
    )
    assert rate_limited.status_code == 201
    assert rate_limited.json()["data"]["status"] == "rate_limited"
    assert rate_limited.json()["data"]["error_code"] == "ANNOUNCEMENT_PROVIDER_RATE_LIMITED"


async def test_normalization_classification_is_not_investment_judgment():
    correction = classify_announcement("\u5173\u4e8e\u66f4\u6b63\u5e74\u5ea6\u62a5\u544a\u7684\u516c\u544a")
    unknown = classify_announcement("Plain title without known announcement keywords")

    assert correction.category == "correction"
    assert correction.basis["not_investment_judgment"] is True
    assert unknown.category == "other"
    assert unknown.basis["not_investment_judgment"] is True
