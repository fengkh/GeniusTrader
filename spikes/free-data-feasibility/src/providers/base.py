from __future__ import annotations

import importlib
import importlib.metadata
import inspect
from collections.abc import Callable
from typing import Any

import pandas as pd

from ..capability import (
    capability_record_from_frame,
    classify_exception,
    now_shanghai,
    synthetic_record,
    timed_dataframe_call,
)
from ..models import CapabilityRecord, ProviderResult


class BaseProvider:
    provider_name = "base"
    source_type = "public_library"

    def __init__(self, module: Any | None = None, *, request_interval: float = 1.0) -> None:
        self.request_interval = request_interval
        self.module = module if module is not None else self._import_module()
        self.provider_version = self._version()

    def _import_module(self) -> Any:
        return importlib.import_module(self.provider_name)

    def _version(self) -> str:
        try:
            return importlib.metadata.version(self.provider_name)
        except importlib.metadata.PackageNotFoundError:
            return str(getattr(self.module, "__version__", "unknown"))

    def signatures(self, names: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for name in names:
            function = self._resolve_public_function(name)
            if function is None:
                result[name] = "MISSING"
                continue
            try:
                result[name] = str(inspect.signature(function))
            except (TypeError, ValueError):
                result[name] = "SIGNATURE_UNAVAILABLE"
        return result

    def _resolve_public_function(self, dotted_name: str) -> Callable[..., Any] | None:
        current: Any = self.module
        for part in dotted_name.split("."):
            if part.startswith("_") or not hasattr(current, part):
                return None
            current = getattr(current, part)
        if callable(current):
            return current
        return None

    def _missing(self, capability: str, api_name: str, impacts: list[str], fallback: str) -> ProviderResult:
        return ProviderResult(
            pd.DataFrame(),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability=capability,
                api_name=api_name,
                status="NOT_SUPPORTED",
                error_message=f"{api_name} is not available as a public function in installed package",
                impacts_features=impacts,
                recommended_fallback=fallback,
            ),
        )

    def _call(
        self,
        *,
        capability: str,
        api_name: str,
        parameters: dict[str, Any],
        fields_expected: list[str],
        impacts: list[str],
        fallback: str,
        normalizer: Callable[[pd.DataFrame], pd.DataFrame] | None = None,
        original_units: dict[str, str] | None = None,
        normalized_units: dict[str, str] | None = None,
        retries: int = 1,
    ) -> ProviderResult:
        function = self._resolve_public_function(api_name)
        if function is None:
            record = synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability=capability,
                api_name=api_name,
                status="SOURCE_CHANGED",
                parameters_summary=parameters,
                fields_expected=fields_expected,
                error_message=f"{api_name} public function missing",
                impacts_features=impacts,
                recommended_fallback=fallback,
            )
            return ProviderResult(pd.DataFrame(), record)

        supported_parameters = self._supported_parameters(function, parameters)

        def invoke() -> pd.DataFrame:
            return function(**supported_parameters)

        raw, duration_ms, error = timed_dataframe_call(invoke, retries=retries, interval=self.request_interval)
        if error is not None:
            record = synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability=capability,
                api_name=api_name,
                status=classify_exception(error),
                parameters_summary=supported_parameters,
                fields_expected=fields_expected,
                error_message=str(error),
                impacts_features=impacts,
                recommended_fallback=fallback,
            )
            return ProviderResult(pd.DataFrame(), record)

        try:
            normalized = normalizer(raw) if normalizer else raw
        except Exception as error:  # noqa: BLE001 - normalized into schema status
            record = capability_record_from_frame(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability=capability,
                api_name=api_name,
                frame=raw,
                queried_at=now_shanghai(),
                parameters_summary=supported_parameters,
                fields_expected=fields_expected,
                duration_ms=duration_ms,
                source_type=self.source_type,
                original_units=original_units,
                normalized_units=normalized_units,
                impacts_features=impacts,
                recommended_fallback=fallback,
                status="SCHEMA_MISMATCH",
                error_message=str(error),
                fields_returned=list(map(str, raw.columns)),
            )
            return ProviderResult(pd.DataFrame(), record)

        status = "PASS" if len(normalized) else "PASS_EMPTY"
        record = capability_record_from_frame(
            provider=self.provider_name,
            provider_version=self.provider_version,
            capability=capability,
            api_name=api_name,
            frame=normalized,
            queried_at=now_shanghai(),
            parameters_summary=supported_parameters,
            fields_expected=fields_expected,
            duration_ms=duration_ms,
            source_type=self.source_type,
            original_units=original_units,
            normalized_units=normalized_units,
            impacts_features=impacts,
            recommended_fallback=fallback,
            status=status,  # type: ignore[arg-type]
            fields_returned=list(map(str, raw.columns)),
        )
        return ProviderResult(normalized, record)

    def _supported_parameters(self, function: Callable[..., Any], parameters: dict[str, Any]) -> dict[str, Any]:
        try:
            signature = inspect.signature(function)
        except (TypeError, ValueError):
            return parameters
        if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
            return parameters
        return {key: value for key, value in parameters.items() if key in signature.parameters}

    def health_check(self) -> ProviderResult:
        return ProviderResult(
            pd.DataFrame([{"provider": self.provider_name, "version": self.provider_version}]),
            synthetic_record(
                provider=self.provider_name,
                provider_version=self.provider_version,
                capability="health_check",
                api_name="import",
                status="PASS",
                fields_returned=["provider", "version"],
                recommended_fallback="install package or skip provider",
            ),
        )

    def get_stock_universe(self) -> ProviderResult:
        return self._missing("stock_universe", "not_supported", ["stock_basic"], "try another provider or paid source")

    def get_stock_snapshot(self, symbols: list[str]) -> ProviderResult:
        return self._missing("stock_snapshot", "not_supported", ["today", "watchlist", "stock_detail"], "try another provider")

    def get_daily_history(self, symbol: str, start_date: str, end_date: str, adjust: str) -> ProviderResult:
        return self._missing("daily_history", "not_supported", ["daily_k", "metrics"], "try another provider")

    def get_minute_history(self, symbol: str, start_datetime: str, end_datetime: str, period: str) -> ProviderResult:
        return self._missing("minute_history", "not_supported", ["intraday_chart", "max_intraday_drawdown"], "degrade intraday chart")

    def get_index_history(self, index_code: str, start_date: str, end_date: str) -> ProviderResult:
        return self._missing("index_history", "not_supported", ["relative_index_strength"], "degrade relative index strength")

    def get_industry_boards(self) -> ProviderResult:
        return self._missing("industry_boards", "not_supported", ["board_filter", "relative_industry_strength"], "manual or paid classification")

    def get_concept_boards(self) -> ProviderResult:
        return self._missing("concept_boards", "not_supported", ["board_filter"], "manual or paid classification")

    def get_board_members(self, board_id: str) -> ProviderResult:
        return self._missing("board_members", "not_supported", ["board_filter"], "cache board members from another provider")

    def get_stock_board_memberships(self, symbol: str) -> ProviderResult:
        return self._missing("stock_board_memberships", "not_supported", ["stock_detail", "board_filter"], "build from cached board members")

    def get_stock_status(self, symbol: str) -> ProviderResult:
        return self._missing("stock_status", "not_supported", ["stock_status", "stale_state"], "infer cautiously from snapshot/daily")

    def get_announcements(self, symbol: str, start_date: str, end_date: str) -> ProviderResult:
        return self._missing("announcements", "not_supported", ["information_center", "review_materials"], "manual links or authorized source")

    def close(self) -> None:
        return None
