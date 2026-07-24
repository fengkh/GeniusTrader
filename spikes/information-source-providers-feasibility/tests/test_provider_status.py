from src.providers.base import status_from_http_code
from src.statuses import ProviderStatus


def test_status_mapping_not_bool():
    assert status_from_http_code(200, None) == ProviderStatus.PASS
    assert status_from_http_code(429, None) == ProviderStatus.RATE_LIMITED
    assert status_from_http_code(None, "TIMEOUT") == ProviderStatus.TIMEOUT
