import pytest

from src.url_utils import assert_public_url, normalize_url


def test_url_normalization_removes_tracking_params():
    url = normalize_url("HTTPS://Example.COM/a?utm_source=x&b=2&a=1#frag")
    assert url == "https://example.com/a?a=1&b=2"


def test_private_url_blocked():
    with pytest.raises(ValueError):
        assert_public_url("http://127.0.0.1/internal")
