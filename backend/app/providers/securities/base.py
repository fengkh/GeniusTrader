from abc import ABC, abstractmethod

from app.providers.securities.models import (
    SecurityMasterCapability,
    SecurityMasterQuery,
    SecurityMasterRecord,
    SecurityMasterResult,
)


class SecurityMasterProvider(ABC):
    source_code: str

    @abstractmethod
    def capabilities(self) -> list[SecurityMasterCapability]:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> SecurityMasterResult:
        raise NotImplementedError

    @abstractmethod
    async def list_securities(self, query: SecurityMasterQuery) -> SecurityMasterResult:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw_record: dict) -> SecurityMasterRecord:
        raise NotImplementedError

    def build_next_cursor(self, result: SecurityMasterResult) -> str | None:
        return result.next_cursor
