from enum import StrEnum


class ProviderStatus(StrEnum):
    PASS = "pass"
    PARTIAL = "partial"
    DATA_INSUFFICIENT = "data_insufficient"
    NOT_AVAILABLE = "not_available"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    ACCESS_DENIED = "access_denied"
    SOURCE_CHANGED = "source_changed"
    PARSE_ERROR = "parse_error"
    CONTENT_UNAVAILABLE = "content_unavailable"
    LEGAL_HOLD = "legal_hold"
    DISABLED = "disabled"


TERMINAL_FAILURES = {
    ProviderStatus.ACCESS_DENIED,
    ProviderStatus.NOT_AVAILABLE,
    ProviderStatus.LEGAL_HOLD,
    ProviderStatus.DISABLED,
}


def status_from_http_error(status_code: int | None, error_code: str | None) -> ProviderStatus:
    if error_code == "TIMEOUT":
        return ProviderStatus.TIMEOUT
    if error_code == "MAX_BYTES_EXCEEDED":
        return ProviderStatus.SOURCE_CHANGED
    if error_code:
        return ProviderStatus.NETWORK_ERROR
    if status_code == 429:
        return ProviderStatus.RATE_LIMITED
    if status_code in {401, 403}:
        return ProviderStatus.ACCESS_DENIED
    if status_code and 500 <= status_code < 600:
        return ProviderStatus.NETWORK_ERROR
    return ProviderStatus.NETWORK_ERROR

