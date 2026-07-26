from httpx import AsyncClient

from app.core.errors import AppError, ErrorCode
from app.core.url_security import ValidatedUrl
from app.services.content_fetcher import FetchResult
from tests.conftest import create_user, login, unique_username


async def _login_user(client: AsyncClient, db_session):
    username = unique_username("url")
    await create_user(db_session, username=username, password="Password12345")
    response = await login(client, username=username, password="Password12345")
    assert response.status_code == 200


def _allow_example_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.information.validate_public_content_url",
        lambda url: ValidatedUrl(original_url=url, normalized_url=url, host="example.com"),
    )


async def test_public_url_fetch_success_uses_controlled_fetcher(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    _allow_example_url(monkeypatch)

    async def fake_fetch(url, settings):
        del settings
        assert url == "https://example.com/article"
        return FetchResult(
            final_url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            body_text="""
                <html><head><title>公告摘要</title><meta property="og:site_name" content="示例新闻"/></head>
                <body><article><p>上市公司发布重要公告，用户需要区分正式事实和平台观点。</p></article></body></html>
            """,
            response_bytes=200,
        )

    monkeypatch.setattr("app.services.information.fetch_public_content", fake_fetch)
    response = await client.post(
        "/api/v1/information/url",
        json={"url": "https://example.com/article", "source_type": "news", "fetch_now": True},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "ready"
    assert data["sources"][0]["fetch_status"] == "succeeded"
    assert data["current_content"]["content_origin"] == "fetched_page"


async def test_duplicate_url_is_rejected(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    _allow_example_url(monkeypatch)

    async def fake_fetch(url, settings):
        del settings
        return FetchResult(
            final_url=url,
            status_code=200,
            content_type="text/plain",
            body_text="足够长的公开网页正文，用于模拟单 URL 受控抓取成功。",
            response_bytes=80,
        )

    monkeypatch.setattr("app.services.information.fetch_public_content", fake_fetch)
    first = await client.post("/api/v1/information/url", json={"url": "https://example.com/a"})
    second = await client.post("/api/v1/information/url", json={"url": "https://example.com/a"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "INFORMATION_DUPLICATE"


async def test_private_url_is_blocked_before_fetch(client: AsyncClient, db_session):
    await _login_user(client, db_session)

    response = await client.post("/api/v1/information/url", json={"url": "http://127.0.0.1/private"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "URL_PRIVATE_ADDRESS_BLOCKED"


async def test_fetch_failure_leaves_information_item_visible(client: AsyncClient, db_session, monkeypatch):
    await _login_user(client, db_session)
    _allow_example_url(monkeypatch)

    async def fake_fetch(url, settings):
        del url, settings
        raise AppError(ErrorCode.CONTENT_FETCH_TIMEOUT, "timeout", status_code=504)

    monkeypatch.setattr("app.services.information.fetch_public_content", fake_fetch)
    response = await client.post("/api/v1/information/url", json={"url": "https://example.com/timeout"})

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "fetch_failed"
    assert data["current_content"] is None
