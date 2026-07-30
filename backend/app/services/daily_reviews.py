import hashlib
import json
import uuid
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.encryption import get_secret_cipher
from app.core.errors import AppError, ErrorCode
from app.core.time import to_timezone, utc_now
from app.models.ai import AITask, AITaskAttempt
from app.models.information import (
    InformationAnalysisVersion,
    InformationContent,
    InformationEntityMention,
    InformationItem,
    InformationSource,
    InformationStockRelation,
    VerificationItem,
)
from app.models.research import ResearchTask
from app.models.review_notification import (
    DailyReview,
    DailyReviewItem,
    DailyReviewVersion,
)
from app.models.stock import Stock
from app.models.tag import UserTag, WatchlistItemTag
from app.models.watchlist import UserWatchlistItem
from app.schemas.daily_review import (
    DailyReviewAIResult,
    DailyReviewDetailOut,
    DailyReviewSummaryOut,
)
from app.services import ai_gateway
from app.services.ai_providers import get_enabled_provider
from app.services.audit import add_audit_log
from app.services.notifications import create_business_event
from app.services.research_tasks import OPEN_RESEARCH_TASK_STATUSES

DAILY_REVIEW_SCHEMA_VERSION = "daily-review-v1"
DAILY_REVIEW_PROMPT_VERSION = "daily-review-prompt-v1"
ACTIVE_DAILY_REVIEW_GENERATION_STATUSES = ("pending", "running")

TRADING_ADVICE_TERMS = [
    "买入",
    "卖出",
    "仓位",
    "目标价",
    "止损",
    "止盈",
    "明日涨停",
    "建议加仓",
    "建议减仓",
]


def _json_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


async def _lock_daily_review_generation(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_date: date,
) -> None:
    lock_digest = hashlib.sha256(f"daily-review:{user_id}:{review_date.isoformat()}".encode()).digest()
    lock_key = int.from_bytes(lock_digest[:8], byteorder="big", signed=True)
    locked = (
        await session.execute(text("SELECT pg_try_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
    ).scalar_one()
    if not locked:
        raise AppError(
            ErrorCode.USER_DAILY_REVIEW_GENERATION_IN_PROGRESS,
            "该日期复盘正在生成中，请稍后查看结果或重试",
            status_code=409,
        )


def _active_generation_timeout_seconds(settings: Settings) -> int:
    return max(settings.ai_request_timeout_seconds * 3, 180)


def _is_stale_generation_task(task: AITask, settings: Settings) -> bool:
    return task.created_at <= utc_now() - timedelta(seconds=_active_generation_timeout_seconds(settings))


async def _active_daily_review_generation_task(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_id: uuid.UUID,
    settings: Settings,
    release_stale: bool,
) -> AITask | None:
    task = (
        await session.execute(
            select(AITask)
            .where(
                AITask.user_id == user_id,
                AITask.task_type == "user_daily_review_generation",
                AITask.target_type == "daily_review",
                AITask.target_id == review_id,
                AITask.status.in_(ACTIVE_DAILY_REVIEW_GENERATION_STATUSES),
            )
            .order_by(AITask.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if task and release_stale and _is_stale_generation_task(task, settings):
        task.status = "failed"
        task.failed_at = utc_now()
        task.error_code = ErrorCode.REVIEW_AI_GENERATION_FAILED.value
        await session.flush()
        return None
    return task


def _raise_generation_in_progress(task: AITask) -> None:
    raise AppError(
        ErrorCode.USER_DAILY_REVIEW_GENERATION_IN_PROGRESS,
        "该日期复盘正在生成中，请稍后查看结果或重试",
        status_code=409,
        details={"ai_task_id": str(task.id), "status": task.status},
    )


def _safe_text(value: str | None, max_length: int = 240) -> str:
    if not value:
        return ""
    text = " ".join(value.split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def default_review_date(settings: Settings) -> date:
    return to_timezone(utc_now(), settings.app_timezone).date()


def _validate_review_date(review_date: date, settings: Settings) -> None:
    if review_date > default_review_date(settings):
        raise AppError(ErrorCode.REVIEW_DATE_INVALID, "复盘日期不能晚于当前日期", status_code=422)


async def _latest_content(session: AsyncSession, item_id: uuid.UUID) -> InformationContent | None:
    return (
        await session.execute(
            select(InformationContent)
            .where(InformationContent.information_item_id == item_id)
            .order_by(InformationContent.content_version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _latest_successful_analysis(
    session: AsyncSession,
    item_id: uuid.UUID,
) -> InformationAnalysisVersion | None:
    return (
        await session.execute(
            select(InformationAnalysisVersion)
            .where(
                InformationAnalysisVersion.information_item_id == item_id,
                InformationAnalysisVersion.analysis_status == "succeeded",
            )
            .order_by(InformationAnalysisVersion.version_number.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _source_for_item(session: AsyncSession, item_id: uuid.UUID) -> InformationSource | None:
    return (
        await session.execute(
            select(InformationSource)
            .where(InformationSource.information_item_id == item_id)
            .order_by(InformationSource.published_at.desc().nullslast(), InformationSource.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _effective_date(item: InformationItem, source: InformationSource | None, settings: Settings) -> date:
    value = source.published_at if source and source.published_at else item.created_at
    return to_timezone(value, settings.app_timezone).date()


async def effective_review_date_for_item(
    session: AsyncSession,
    *,
    item: InformationItem,
    settings: Settings,
) -> date:
    return _effective_date(item, await _source_for_item(session, item.id), settings)


async def _watchlist_maps(session: AsyncSession, user_id: uuid.UUID) -> tuple[dict[uuid.UUID, dict[str, Any]], set[uuid.UUID]]:
    result = await session.execute(
        select(UserWatchlistItem, Stock)
        .join(Stock, Stock.id == UserWatchlistItem.stock_id)
        .where(UserWatchlistItem.user_id == user_id, UserWatchlistItem.archived_at.is_(None))
        .order_by(UserWatchlistItem.sort_order, Stock.exchange, Stock.symbol)
    )
    rows = result.all()
    item_ids = [item.id for item, _stock in rows]
    tag_map: dict[uuid.UUID, list[str]] = defaultdict(list)
    if item_ids:
        tag_rows = await session.execute(
            select(WatchlistItemTag.watchlist_item_id, UserTag.name)
            .join(UserTag, UserTag.id == WatchlistItemTag.tag_id)
            .where(UserTag.user_id == user_id, WatchlistItemTag.watchlist_item_id.in_(item_ids))
            .order_by(UserTag.name)
        )
        for item_id, tag_name in tag_rows.all():
            tag_map[item_id].append(tag_name)
    by_stock: dict[uuid.UUID, dict[str, Any]] = {}
    for item, stock in rows:
        by_stock[item.stock_id] = {
            "watchlist_item_id": str(item.id),
            "stock_id": str(stock.id),
            "symbol": stock.symbol,
            "exchange": stock.exchange,
            "name": stock.name,
            "attention_reason": item.attention_reason,
            "user_tags": tag_map.get(item.id, []),
            "information_item_ids": [],
            "facts": [],
            "opinions": [],
            "rumors": [],
            "risks": [],
            "verification_items": [],
            "observation_conditions": [],
            "limitations": [],
        }
    return by_stock, set(by_stock.keys())


async def _relations_for_item(
    session: AsyncSession,
    item_id: uuid.UUID,
) -> list[tuple[InformationStockRelation, Stock]]:
    return list(
        (
            await session.execute(
                select(InformationStockRelation, Stock)
                .join(Stock, Stock.id == InformationStockRelation.stock_id)
                .where(InformationStockRelation.information_item_id == item_id)
                .order_by(InformationStockRelation.created_at)
            )
        ).all()
    )


async def _entity_mentions_for_item(session: AsyncSession, item_id: uuid.UUID) -> list[InformationEntityMention]:
    return list(
        (
            await session.execute(
                select(InformationEntityMention)
                .where(InformationEntityMention.information_item_id == item_id)
                .order_by(InformationEntityMention.created_at)
            )
        )
        .scalars()
        .all()
    )


async def _verification_items_for_analysis(
    session: AsyncSession,
    item_id: uuid.UUID,
    analysis_version_id: uuid.UUID | None,
) -> list[VerificationItem]:
    statement = select(VerificationItem).where(VerificationItem.information_item_id == item_id)
    if analysis_version_id:
        statement = statement.where(VerificationItem.analysis_version_id == analysis_version_id)
    return list((await session.execute(statement.order_by(VerificationItem.created_at))).scalars().all())


def _claim_items(
    values: list[dict[str, Any]],
    *,
    information_item_id: uuid.UUID,
    analysis_version_id: uuid.UUID,
) -> list[dict[str, Any]]:
    return [
        {
            "claim": _safe_text(value.get("claim")),
            "information_item_id": str(information_item_id),
            "analysis_version_id": str(analysis_version_id),
            "evidence_text": _safe_text(value.get("evidence_text")),
            "confidence": value.get("confidence"),
        }
        for value in values
        if isinstance(value, dict) and value.get("claim")
    ]


def _opinion_items(values: list[dict[str, Any]], *, information_item_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "claim": _safe_text(value.get("claim")),
            "holder": value.get("holder"),
            "rationale": _safe_text(value.get("rationale")),
            "time_horizon": value.get("time_horizon"),
            "information_item_id": str(information_item_id),
            "evidence_text": _safe_text(value.get("evidence_text")),
            "confidence": value.get("confidence"),
        }
        for value in values
        if isinstance(value, dict) and value.get("claim")
    ]


def _rumor_items(values: list[dict[str, Any]], *, information_item_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "claim": _safe_text(value.get("claim")),
            "verification_needed": _safe_text(value.get("verification_needed")),
            "information_item_id": str(information_item_id),
            "evidence_text": _safe_text(value.get("evidence_text")),
            "confidence": value.get("confidence"),
        }
        for value in values
        if isinstance(value, dict) and value.get("claim")
    ]


def _risk_items(values: list[dict[str, Any]], *, information_item_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {
            "description": _safe_text(value.get("description")),
            "source_information_item_id": str(information_item_id),
            "ai_reported_severity": value.get("severity"),
            "system_interpretation": "AI 风险级别仅作原分析展示，系统未据此生成交易动作。",
        }
        for value in values
        if isinstance(value, dict) and value.get("description")
    ]


def _observation_condition(verification: VerificationItem) -> str:
    text = f"{verification.verification_type} {verification.description}".lower()
    if "announcement" in text or "公告" in text:
        return "需要出现正式公告"
    if "approval" in text or "批" in text:
        return "需要确认项目批文"
    if "order" in text or "订单" in text:
        return "需要确认订单"
    if "capacity" in text or "产能" in text:
        return "需要确认产能"
    if "rumor" in text or "传闻" in text:
        return "需要确认传闻是否被证伪"
    return "需要确认事件是否被权威来源支持"


def _has_trading_advice(snapshot: dict[str, Any]) -> bool:
    text = json.dumps(snapshot, ensure_ascii=False)
    return any(term in text for term in TRADING_ADVICE_TERMS)


def _relation_snapshot(relations: list[tuple[InformationStockRelation, Stock]]) -> list[dict[str, Any]]:
    return [
        {
            "relation_id": str(relation.id),
            "stock_id": str(stock.id),
            "symbol": stock.symbol,
            "exchange": stock.exchange,
            "name": stock.name,
            "origin": relation.relation_origin,
            "status": relation.relation_status,
            "type": relation.relation_type,
            "confidence": relation.confidence,
        }
        for relation, stock in relations
    ]


def _research_task_snapshot(task: ResearchTask, settings: Settings) -> dict[str, Any]:
    latest_update = task.updates[-1] if task.updates else None
    return {
        "task_id": str(task.id),
        "stock_id": str(task.stock_id) if task.stock_id else None,
        "stock_symbol": task.stock.symbol if task.stock else None,
        "stock_name": task.stock.name if task.stock else None,
        "task_type": task.task_type,
        "title": _safe_text(task.title, 160),
        "status": task.status,
        "priority": task.priority,
        "source_type": task.source_type,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "evidence_summary": _safe_text(task.current_evidence_summary, 160),
        "resolution_note": _safe_text(task.resolution_note, 160),
        "latest_update": {
            "status": latest_update.new_status,
            "note": _safe_text(latest_update.note, 160),
            "created_at": latest_update.created_at.isoformat(),
        }
        if latest_update
        else None,
        "updated_at": to_timezone(task.updated_at, settings.app_timezone).isoformat(),
    }


async def _research_tasks_for_review(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_date: date,
    settings: Settings,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks = list(
        (
            await session.execute(
                select(ResearchTask)
                .options(selectinload(ResearchTask.stock), selectinload(ResearchTask.updates))
                .where(ResearchTask.user_id == user_id)
                .order_by(ResearchTask.due_date.asc().nullslast(), ResearchTask.updated_at.asc(), ResearchTask.id)
            )
        )
        .scalars()
        .all()
    )
    selected: list[dict[str, Any]] = []
    observation_results: list[dict[str, Any]] = []
    for task in tasks:
        updated_date = to_timezone(task.updated_at, settings.app_timezone).date()
        created_date = to_timezone(task.created_at, settings.app_timezone).date()
        resolved_date = to_timezone(task.resolved_at, settings.app_timezone).date() if task.resolved_at else None
        due_match = task.due_date is not None and task.due_date <= review_date
        changed_today = updated_date == review_date or created_date == review_date or resolved_date == review_date
        if not (due_match or changed_today):
            continue
        entry = _research_task_snapshot(task, settings)
        selected.append(entry)
        if task.task_type == "observation" and task.status not in OPEN_RESEARCH_TASK_STATUSES:
            observation_results.append(
                {
                    "task_id": entry["task_id"],
                    "stock_id": entry["stock_id"],
                    "stock_symbol": entry["stock_symbol"],
                    "title": entry["title"],
                    "status": entry["status"],
                    "resolution_note": entry["resolution_note"],
                    "evidence_summary": entry["evidence_summary"],
                    "resolved_at": task.resolved_at.isoformat() if task.resolved_at else None,
                }
            )
    return selected, observation_results


async def build_rule_snapshot(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_date: date,
    settings: Settings,
) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    watchlist_by_stock, watchlist_stock_ids = await _watchlist_maps(session, user_id)
    information_items = list(
        (
            await session.execute(
                select(InformationItem)
                .where(
                    InformationItem.user_id == user_id,
                    InformationItem.archived_at.is_(None),
                    InformationItem.status != "archived",
                )
                .order_by(InformationItem.created_at, InformationItem.id)
            )
        )
        .scalars()
        .all()
    )
    selected: list[dict[str, Any]] = []
    source_item_ids: list[str] = []
    confirmed_non_watchlist: dict[str, dict[str, Any]] = {}
    unassigned_information: list[dict[str, Any]] = []
    pending_relations: list[dict[str, Any]] = []
    global_verifications: list[dict[str, Any]] = []
    limitations: list[str] = []
    overview = {
        "total_information_count": 0,
        "analyzed_count": 0,
        "pending_analysis_count": 0,
        "failed_analysis_count": 0,
        "important_count": 0,
        "confirmed_stock_relation_count": 0,
        "suggested_stock_relation_count": 0,
        "watchlist_stock_count": len(watchlist_by_stock),
        "verification_item_count": 0,
        "rumor_count": 0,
        "fact_count": 0,
        "opinion_count": 0,
    }

    for item in information_items:
        source = await _source_for_item(session, item.id)
        effective_date = _effective_date(item, source, settings)
        if effective_date != review_date:
            continue
        content = await _latest_content(session, item.id)
        analysis = await _latest_successful_analysis(session, item.id)
        relations = await _relations_for_item(session, item.id)
        entities = await _entity_mentions_for_item(session, item.id)
        confirmed_relations = [(relation, stock) for relation, stock in relations if relation.relation_status == "confirmed"]
        suggested_relations = [(relation, stock) for relation, stock in relations if relation.relation_status == "suggested"]
        rejected_relations = [(relation, stock) for relation, stock in relations if relation.relation_status == "rejected"]
        overview["confirmed_stock_relation_count"] += len(confirmed_relations)
        overview["suggested_stock_relation_count"] += len(suggested_relations)
        if suggested_relations:
            pending_relations.extend(
                {
                    "information_item_id": str(item.id),
                    "relation_id": str(relation.id),
                    "stock_id": str(stock.id),
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "evidence_text": _safe_text(relation.evidence_text),
                    "confidence": relation.confidence,
                }
                for relation, stock in suggested_relations
            )
        if not content:
            inclusion_type = "content_insufficient"
            relation_scope = "unassigned"
            overview["failed_analysis_count"] += 1
            limitations.append(f"信息 {item.id} 缺少可用正文。")
        elif analysis:
            inclusion_type = "analyzed"
            overview["analyzed_count"] += 1
        elif item.status == "analysis_failed":
            inclusion_type = "analysis_failed"
            overview["failed_analysis_count"] += 1
            limitations.append(f"信息 {item.id} 分析失败，仅计入统计和局限性。")
        else:
            inclusion_type = "pending_analysis"
            overview["pending_analysis_count"] += 1
            limitations.append(f"信息 {item.id} 尚未完成 AI 分析。")

        confirmed_watchlist_stocks = [stock for relation, stock in confirmed_relations if stock.id in watchlist_stock_ids]
        confirmed_non_watchlist_stocks = [stock for relation, stock in confirmed_relations if stock.id not in watchlist_stock_ids]
        if confirmed_watchlist_stocks:
            relation_scope = "watchlist_stock"
        elif confirmed_non_watchlist_stocks:
            relation_scope = "confirmed_non_watchlist_stock"
        elif entities:
            relation_scope = "entity_only"
        else:
            relation_scope = "unassigned"
        if suggested_relations and not confirmed_relations:
            inclusion_type = "unconfirmed_relation"
            limitations.append(f"信息 {item.id} 存在待确认股票关系，未进入正式股票分组。")

        overview["total_information_count"] += 1
        if item.is_important:
            overview["important_count"] += 1
        source_item_ids.append(str(item.id))
        structured = analysis.structured_result if analysis else {}
        facts = _claim_items(
            structured.get("facts", []),
            information_item_id=item.id,
            analysis_version_id=analysis.id,
        ) if analysis else []
        opinions = _opinion_items(structured.get("opinions", []), information_item_id=item.id) if analysis else []
        rumors = _rumor_items(structured.get("rumors", []), information_item_id=item.id) if analysis else []
        risks = _risk_items(structured.get("risks", []), information_item_id=item.id) if analysis else []
        verification_rows = await _verification_items_for_analysis(session, item.id, analysis.id if analysis else None)
        verification_items = [
            {
                "verification_item_id": str(verification.id),
                "description": _safe_text(verification.description),
                "verification_type": verification.verification_type,
                "priority": verification.priority,
                "evidence_needed": _safe_text(verification.evidence_needed),
                "status": verification.status,
                "source_information_item_id": str(item.id),
            }
            for verification in verification_rows
        ]
        observation_conditions = sorted({_observation_condition(verification) for verification in verification_rows})
        overview["fact_count"] += len(facts)
        overview["opinion_count"] += len(opinions)
        overview["rumor_count"] += len(rumors)
        overview["verification_item_count"] += len(verification_items)
        global_verifications.extend(verification_items)

        for stock in confirmed_watchlist_stocks:
            section = watchlist_by_stock[stock.id]
            if str(item.id) not in section["information_item_ids"]:
                section["information_item_ids"].append(str(item.id))
            section["facts"].extend(facts)
            section["opinions"].extend(opinions)
            section["rumors"].extend(rumors)
            section["risks"].extend(risks)
            section["verification_items"].extend(verification_items)
            section["observation_conditions"].extend(
                [value for value in observation_conditions if value not in section["observation_conditions"]]
            )
        for stock in confirmed_non_watchlist_stocks:
            key = str(stock.id)
            section = confirmed_non_watchlist.setdefault(
                key,
                {
                    "stock_id": str(stock.id),
                    "symbol": stock.symbol,
                    "exchange": stock.exchange,
                    "name": stock.name,
                    "not_in_watchlist": True,
                    "information_item_ids": [],
                    "facts": [],
                    "opinions": [],
                    "rumors": [],
                    "risks": [],
                    "verification_items": [],
                    "observation_conditions": [],
                    "limitations": ["该股票不在当前自选股中。"],
                },
            )
            section["information_item_ids"].append(str(item.id))
            section["facts"].extend(facts)
            section["opinions"].extend(opinions)
            section["rumors"].extend(rumors)
            section["risks"].extend(risks)
            section["verification_items"].extend(verification_items)
            section["observation_conditions"].extend(observation_conditions)
        if not confirmed_relations:
            unassigned_information.append(
                {
                    "information_item_id": str(item.id),
                    "title": item.title,
                    "status": item.status,
                    "inclusion_type": inclusion_type,
                    "relation_scope": relation_scope,
                    "entity_mentions": [
                        {
                            "entity_type": entity.entity_type,
                            "entity_name": entity.entity_name,
                            "relation": entity.relation,
                        }
                        for entity in entities
                    ],
                }
            )
        selected.append(
            {
                "information_item_id": item.id,
                "analysis_version_id": analysis.id if analysis else None,
                "information_content_id": content.id if content else None,
                "inclusion_type": inclusion_type,
                "inclusion_reason": "纳入指定 review_date 的用户私有信息复盘",
                "effective_date": effective_date,
                "relation_scope": relation_scope,
                "relation_status_snapshot": _relation_snapshot(relations),
                "is_watchlist_related": bool(confirmed_watchlist_stocks),
                "fingerprint": {
                    "item_id": str(item.id),
                    "content_id": str(content.id) if content else None,
                    "analysis_version_id": str(analysis.id) if analysis else None,
                    "relations": _relation_snapshot(relations),
                    "rejected_relation_count": len(rejected_relations),
                },
            }
        )

    if overview["total_information_count"] == 0:
        data_state = "empty"
        limitations.append("当日暂无已保存信息。")
    elif overview["pending_analysis_count"] or overview["failed_analysis_count"] or pending_relations:
        data_state = "partial"
    else:
        data_state = "complete"
    research_tasks, observation_verification_results = await _research_tasks_for_review(
        session,
        user_id=user_id,
        review_date=review_date,
        settings=settings,
    )
    if research_tasks:
        limitations.append("研究事项为用户显式创建或采纳的待办，不代表系统自动核实结论。")
    overview["open_research_task_count"] = len(
        [task for task in research_tasks if task.get("status") in OPEN_RESEARCH_TASK_STATUSES]
    )
    overview["observation_verification_result_count"] = len(observation_verification_results)
    watchlist_sections = [
        section
        for section in watchlist_by_stock.values()
        if section["information_item_ids"]
    ]
    snapshot = {
        "schema_version": DAILY_REVIEW_SCHEMA_VERSION,
        "review_date": review_date.isoformat(),
        "data_state": data_state,
        "generated_at": utc_now().isoformat(),
        "scope_note": "当前复盘仅聚合用户保存和分析的信息，不代表全市场行情复盘。",
        "overview": overview,
        "watchlist_sections": watchlist_sections,
        "confirmed_non_watchlist_sections": list(confirmed_non_watchlist.values()),
        "unassigned_information": unassigned_information,
        "pending_relations": pending_relations,
        "global_verification_items": global_verifications,
        "research_tasks": research_tasks,
        "observation_verification_results": observation_verification_results,
        "limitations": sorted(set(limitations)),
        "source_item_ids": source_item_ids,
        "rule_summary": _rule_summary(review_date, data_state, overview),
    }
    if _has_trading_advice(snapshot):
        raise AppError(ErrorCode.DAILY_REVIEW_GENERATION_FAILED, "规则复盘包含禁止的交易建议表达", status_code=500)
    fingerprint_inputs = {
        "user_id": str(user_id),
        "review_date": review_date.isoformat(),
        "prompt_version": DAILY_REVIEW_PROMPT_VERSION,
        "schema_version": DAILY_REVIEW_SCHEMA_VERSION,
        "items": [item["fingerprint"] for item in selected],
        "research_tasks": [
            {
                "task_id": task["task_id"],
                "status": task["status"],
                "due_date": task["due_date"],
                "updated_at": task["updated_at"],
                "latest_update": task["latest_update"],
            }
            for task in research_tasks
        ],
        "watchlist": [
            {
                "stock_id": section["stock_id"],
                "attention_reason": section["attention_reason"],
                "user_tags": section["user_tags"],
            }
            for section in sorted(watchlist_by_stock.values(), key=lambda value: value["stock_id"])
        ],
    }
    return snapshot, _json_hash(fingerprint_inputs), selected


def _rule_summary(review_date: date, data_state: str, overview: dict[str, Any]) -> str:
    if data_state == "empty":
        return f"{review_date.isoformat()} 当日暂无已保存信息。"
    return (
        f"{review_date.isoformat()} 用户私有信息复盘：纳入信息 {overview['total_information_count']} 条，"
        f"已分析 {overview['analyzed_count']} 条，待分析 {overview['pending_analysis_count']} 条，"
        f"分析失败 {overview['failed_analysis_count']} 条，待核实 {overview['verification_item_count']} 项。"
    )


def _load_json_object(raw: str) -> Any:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
        return parsed


def _parse_ai_review(raw: str) -> DailyReviewAIResult:
    try:
        loaded = _load_json_object(raw)
    except json.JSONDecodeError as exc:
        raise AppError(ErrorCode.AI_SCHEMA_VALIDATION_FAILED, "AI 返回不是有效 JSON", status_code=502) from exc
    try:
        return DailyReviewAIResult.model_validate(loaded)
    except ValidationError as exc:
        raise AppError(
            ErrorCode.AI_SCHEMA_VALIDATION_FAILED,
            "AI 复盘未通过结构化校验",
            status_code=502,
            details={"validation_errors": exc.errors()},
        ) from exc


def _compact_validation_errors(errors: Any) -> list[dict[str, str]]:
    if not isinstance(errors, list):
        return []
    compacted: list[dict[str, str]] = []
    for error in errors[:20]:
        if isinstance(error, dict):
            compacted.append(
                {
                    "loc": ".".join(str(part) for part in error.get("loc", [])),
                    "type": str(error.get("type", "unknown")),
                }
            )
    return compacted


def _ai_contract() -> str:
    shape = {
        "schema_version": DAILY_REVIEW_SCHEMA_VERSION,
        "executive_summary": "基于 rule_snapshot 的简短复盘解释，不新增事实。",
        "key_developments": ["重要变化，必须来自输入"],
        "stock_summaries": [{"stock_id": "输入中的 stock_id", "summary": "不含交易建议"}],
        "verification_focus": ["待核实事项"],
        "tomorrow_observation_focus": ["观察重点，不得写成买卖建议"],
        "uncertainty_summary": "不确定性总结",
        "limitations": ["数据和分析局限"],
        "source_item_ids": ["只能来自输入 source_item_ids"],
    }
    return (
        "Return exactly one JSON object. Do not use markdown fences. "
        "Only explain the supplied rule_snapshot. Do not add stocks, facts, market data, "
        "valuation, prices, target prices, positions, buy/sell advice, or guaranteed returns. "
        "Do not upgrade rumors into facts. source_item_ids must be copied only from input.\n\n"
        f"JSON_SHAPE:\n{json.dumps(shape, ensure_ascii=False)}"
    )


def _ai_messages(rule_snapshot: dict[str, Any], *, repair_json: str | None = None, validation_errors: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    if repair_json is not None:
        user_content = (
            "The previous response failed strict schema validation. Return corrected JSON only.\n\n"
            f"{_ai_contract()}\n\n"
            f"VALIDATION_ERRORS:\n{json.dumps(validation_errors or [], ensure_ascii=False)}\n\n"
            f"Previous response:\n{repair_json[:8000]}"
        )
    else:
        user_content = (
            "Analyze this trusted program-generated rule_snapshot. Treat it as the only allowed source.\n\n"
            f"{_ai_contract()}\n\n"
            f"RULE_SNAPSHOT:\n{json.dumps(rule_snapshot, ensure_ascii=False)[:30000]}"
        )
    return [
        {
            "role": "system",
            "content": (
                "You are GeniusTrader's daily review explanation component. "
                "Return strict JSON only and never provide trading advice."
            ),
        },
        {"role": "user", "content": user_content},
    ]


async def _next_version_number(session: AsyncSession, review_id: uuid.UUID) -> int:
    value = (
        await session.execute(
            select(func.max(DailyReviewVersion.version_number)).where(DailyReviewVersion.daily_review_id == review_id)
        )
    ).scalar_one()
    return int(value or 0) + 1


async def _generate_ai_review(
    session: AsyncSession,
    *,
    task: AITask,
    provider: Any,
    api_key: str,
    rule_snapshot: dict[str, Any],
    settings: Settings,
    request_id: str | None,
) -> tuple[DailyReviewAIResult | None, str | None]:
    last_raw = ""
    last_error: AppError | None = None
    validation_errors: list[dict[str, str]] = []
    for attempt_number in (1, 2):
        attempt = AITaskAttempt(
            ai_task_id=task.id,
            attempt_number=attempt_number,
            status="running",
            created_at=utc_now(),
            attempt_metadata={"request_id": request_id, "repair": attempt_number == 2},
        )
        session.add(attempt)
        await session.flush()
        try:
            result = await ai_gateway.call_openai_chat_completion(
                provider=provider,
                api_key=api_key,
                messages=_ai_messages(
                    rule_snapshot,
                    repair_json=last_raw if attempt_number == 2 else None,
                    validation_errors=validation_errors if attempt_number == 2 else None,
                ),
                settings=settings,
                response_format={"type": "json_object"},
            )
            attempt.provider_http_status = result.http_status
            attempt.duration_ms = result.duration_ms
            attempt.input_tokens = result.input_tokens
            attempt.output_tokens = result.output_tokens
            last_raw = result.content
            parsed = _parse_ai_review(result.content)
            _validate_ai_review(parsed, rule_snapshot)
            attempt.status = "succeeded"
            task.status = "succeeded"
            task.completed_at = utc_now()
            return parsed, provider.model_name
        except AppError as exc:
            attempt.status = "failed"
            attempt.error_code = exc.code.value
            attempt.error_detail_redacted = exc.message
            if exc.code == ErrorCode.AI_SCHEMA_VALIDATION_FAILED:
                details = exc.details if isinstance(exc.details, dict) else {}
                validation_errors = _compact_validation_errors(details.get("validation_errors"))
                if validation_errors:
                    attempt.attempt_metadata = {**attempt.attempt_metadata, "validation_errors": validation_errors}
            last_error = exc
            if exc.code != ErrorCode.AI_SCHEMA_VALIDATION_FAILED or attempt_number == 2:
                break
    task.status = "failed"
    task.failed_at = utc_now()
    task.error_code = last_error.code.value if last_error else ErrorCode.REVIEW_AI_GENERATION_FAILED.value
    return None, provider.model_name


def _validate_ai_review(parsed: DailyReviewAIResult, rule_snapshot: dict[str, Any]) -> None:
    allowed_sources = set(rule_snapshot.get("source_item_ids", []))
    if any(source_id not in allowed_sources for source_id in parsed.source_item_ids):
        raise AppError(ErrorCode.AI_SCHEMA_VALIDATION_FAILED, "AI 复盘引用了输入之外的来源", status_code=502)
    text = parsed.model_dump_json()
    if any(term in text for term in TRADING_ADVICE_TERMS):
        raise AppError(ErrorCode.AI_SCHEMA_VALIDATION_FAILED, "AI 复盘包含交易建议表达", status_code=502)


async def _create_running_daily_review_task(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review: DailyReview,
    fingerprint: str,
    settings: Settings,
) -> tuple[AITask | None, Any | None, str | None]:
    provider = await get_enabled_provider(session, user_id)
    if not provider:
        return None, None, None
    active = await _active_daily_review_generation_task(
        session,
        user_id=user_id,
        review_id=review.id,
        settings=settings,
        release_stale=True,
    )
    if active:
        _raise_generation_in_progress(active)
    now = utc_now()
    task = AITask(
        user_id=user_id,
        task_type="user_daily_review_generation",
        target_type="daily_review",
        target_id=review.id,
        provider_config_id=provider.id,
        status="running",
        prompt_version=DAILY_REVIEW_PROMPT_VERSION,
        schema_version=DAILY_REVIEW_SCHEMA_VERSION,
        input_hash=fingerprint,
        created_at=now,
        started_at=now,
    )
    session.add(task)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(
            ErrorCode.USER_DAILY_REVIEW_GENERATION_IN_PROGRESS,
            "该日期复盘正在生成中，请稍后查看结果或重试",
            status_code=409,
        ) from exc
    await session.commit()
    api_key = get_secret_cipher(settings).decrypt_secret(provider.encrypted_api_key)
    return task, provider, api_key


async def get_daily_review_or_404(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_id: uuid.UUID,
) -> DailyReview:
    review = (
        await session.execute(
            select(DailyReview).where(DailyReview.id == review_id, DailyReview.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not review:
        raise AppError(ErrorCode.DAILY_REVIEW_NOT_FOUND, "每日复盘不存在", status_code=404)
    return review


async def _generate_daily_review_legacy(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_date: date,
    force: bool,
    use_ai: bool,
    settings: Settings,
    request_id: str | None,
) -> DailyReviewDetailOut:
    _validate_review_date(review_date, settings)
    await _lock_daily_review_generation(session, user_id=user_id, review_date=review_date)
    rule_snapshot, fingerprint, selected_items = await build_rule_snapshot(
        session,
        user_id=user_id,
        review_date=review_date,
        settings=settings,
    )
    review = (
        await session.execute(
            select(DailyReview).where(DailyReview.user_id == user_id, DailyReview.review_date == review_date)
        )
    ).scalar_one_or_none()
    if review and review.input_fingerprint == fingerprint and not force and review.current_version_id:
        return await build_daily_review_detail(session, user_id=user_id, review_id=review.id, settings=settings)
    now = utc_now()
    if not review:
        review = DailyReview(
            user_id=user_id,
            review_date=review_date,
            status=rule_snapshot["data_state"],
            input_fingerprint=fingerprint,
            generated_at=now,
        )
        session.add(review)
        await session.flush()
    ai_task: AITask | None = None
    ai_result: DailyReviewAIResult | None = None
    model_name: str | None = None
    generation_mode = "rules_only"
    status = rule_snapshot["data_state"]
    if use_ai and rule_snapshot["data_state"] != "empty":
        ai_task, ai_result, model_name = await _generate_ai_review(
            session,
            user_id=user_id,
            review_id=review.id,
            rule_snapshot=rule_snapshot,
            fingerprint=fingerprint,
            settings=settings,
            request_id=request_id,
        )
        if ai_result:
            generation_mode = "rules_and_ai"
        elif ai_task:
            generation_mode = "rules_with_ai_fallback"
            status = "partial"
            rule_snapshot["limitations"] = sorted(
                set([*rule_snapshot.get("limitations", []), "AI 复盘摘要生成失败，已保留程序聚合结果。"])
            )
    version = DailyReviewVersion(
        daily_review_id=review.id,
        version_number=await _next_version_number(session, review.id),
        status=status,
        generation_mode=generation_mode,
        ai_task_id=ai_task.id if ai_task else None,
        rule_snapshot=rule_snapshot,
        ai_structured_result=ai_result.model_dump(mode="json") if ai_result else None,
        ai_narrative=ai_result.executive_summary if ai_result else rule_snapshot["rule_summary"],
        input_fingerprint=fingerprint,
        prompt_version=DAILY_REVIEW_PROMPT_VERSION if ai_task else None,
        schema_version=DAILY_REVIEW_SCHEMA_VERSION,
        provider_config_id=ai_task.provider_config_id if ai_task else None,
        model_name=model_name,
        generated_at=now,
        created_at=now,
    )
    session.add(version)
    await session.flush()
    for item in selected_items:
        session.add(
            DailyReviewItem(
                daily_review_version_id=version.id,
                information_item_id=item["information_item_id"],
                analysis_version_id=item["analysis_version_id"],
                information_content_id=item["information_content_id"],
                inclusion_type=item["inclusion_type"],
                inclusion_reason=item["inclusion_reason"],
                effective_date=item["effective_date"],
                relation_scope=item["relation_scope"],
                relation_status_snapshot=item["relation_status_snapshot"],
                is_watchlist_related=item["is_watchlist_related"],
                created_at=now,
            )
        )
    review.status = status
    review.current_version_id = version.id
    review.input_fingerprint = fingerprint
    review.generated_at = now
    review.stale_at = None
    event_type = "user_daily_review.partial" if status == "partial" else "user_daily_review.generated"
    severity = "notice" if status == "partial" else "info"
    await create_business_event(
        session,
        user_id=user_id,
        event_type=event_type,
        subject_type="daily_review",
        subject_id=review.id,
        severity=severity,
        payload={
            "review_date": review_date.isoformat(),
            "status": status,
            "version_number": version.version_number,
            **rule_snapshot["overview"],
        },
        source="daily_review_service",
        idempotency_key=f"{event_type}:{review.id}:{version.id}",
        request_id=request_id,
        correlation_id=request_id,
    )
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="daily_review.force_generate" if force else "daily_review.generate",
        target_type="daily_review",
        target_id=review.id,
        result="success",
        request_id=request_id,
        metadata={"review_date": review_date.isoformat(), "status": status, "version_number": version.version_number},
    )
    await session.commit()
    return await build_daily_review_detail(session, user_id=user_id, review_id=review.id, settings=settings)


async def generate_daily_review(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_date: date,
    force: bool,
    use_ai: bool,
    settings: Settings,
    request_id: str | None,
) -> DailyReviewDetailOut:
    _validate_review_date(review_date, settings)
    await _lock_daily_review_generation(session, user_id=user_id, review_date=review_date)
    review = (
        await session.execute(
            select(DailyReview).where(DailyReview.user_id == user_id, DailyReview.review_date == review_date)
        )
    ).scalar_one_or_none()
    if review:
        active = await _active_daily_review_generation_task(
            session,
            user_id=user_id,
            review_id=review.id,
            settings=settings,
            release_stale=True,
        )
        if active:
            _raise_generation_in_progress(active)
    rule_snapshot, fingerprint, selected_items = await build_rule_snapshot(
        session,
        user_id=user_id,
        review_date=review_date,
        settings=settings,
    )
    if review and review.input_fingerprint == fingerprint and not force and review.current_version_id:
        return await build_daily_review_detail(session, user_id=user_id, review_id=review.id, settings=settings)
    now = utc_now()
    if not review:
        review = DailyReview(
            user_id=user_id,
            review_date=review_date,
            status=rule_snapshot["data_state"],
            input_fingerprint=fingerprint,
            generated_at=now,
        )
        session.add(review)
        await session.flush()

    ai_task: AITask | None = None
    ai_result: DailyReviewAIResult | None = None
    model_name: str | None = None
    generation_mode = "rules_only"
    status = rule_snapshot["data_state"]
    if use_ai and rule_snapshot["data_state"] != "empty":
        provider: Any | None = None
        api_key: str | None = None
        ai_task, provider, api_key = await _create_running_daily_review_task(
            session,
            user_id=user_id,
            review=review,
            fingerprint=fingerprint,
            settings=settings,
        )
        if ai_task and provider and api_key:
            try:
                ai_result, model_name = await _generate_ai_review(
                    session,
                    task=ai_task,
                    provider=provider,
                    api_key=api_key,
                    rule_snapshot=rule_snapshot,
                    settings=settings,
                    request_id=request_id,
                )
            except Exception:
                await session.rollback()
                persisted_task = await session.get(AITask, ai_task.id)
                if persisted_task and persisted_task.status in ACTIVE_DAILY_REVIEW_GENERATION_STATUSES:
                    persisted_task.status = "failed"
                    persisted_task.failed_at = utc_now()
                    persisted_task.error_code = ErrorCode.REVIEW_AI_GENERATION_FAILED.value
                    await session.commit()
                raise
            if ai_result:
                generation_mode = "rules_and_ai"
            else:
                generation_mode = "rules_with_ai_fallback"
                status = "partial"
                rule_snapshot["limitations"] = sorted(
                    set([*rule_snapshot.get("limitations", []), "AI 复盘摘要生成失败，已保留程序聚合结果。"])
                )

    version = DailyReviewVersion(
        daily_review_id=review.id,
        version_number=await _next_version_number(session, review.id),
        status=status,
        generation_mode=generation_mode,
        ai_task_id=ai_task.id if ai_task else None,
        rule_snapshot=rule_snapshot,
        ai_structured_result=ai_result.model_dump(mode="json") if ai_result else None,
        ai_narrative=ai_result.executive_summary if ai_result else rule_snapshot["rule_summary"],
        input_fingerprint=fingerprint,
        prompt_version=DAILY_REVIEW_PROMPT_VERSION if ai_task else None,
        schema_version=DAILY_REVIEW_SCHEMA_VERSION,
        provider_config_id=ai_task.provider_config_id if ai_task else None,
        model_name=model_name,
        generated_at=now,
        created_at=now,
    )
    session.add(version)
    await session.flush()
    for item in selected_items:
        session.add(
            DailyReviewItem(
                daily_review_version_id=version.id,
                information_item_id=item["information_item_id"],
                analysis_version_id=item["analysis_version_id"],
                information_content_id=item["information_content_id"],
                inclusion_type=item["inclusion_type"],
                inclusion_reason=item["inclusion_reason"],
                effective_date=item["effective_date"],
                relation_scope=item["relation_scope"],
                relation_status_snapshot=item["relation_status_snapshot"],
                is_watchlist_related=item["is_watchlist_related"],
                created_at=now,
            )
        )
    review.status = status
    review.current_version_id = version.id
    review.input_fingerprint = fingerprint
    review.generated_at = now
    review.stale_at = None
    event_type = "user_daily_review.partial" if status == "partial" else "user_daily_review.generated"
    severity = "notice" if status == "partial" else "info"
    await create_business_event(
        session,
        user_id=user_id,
        event_type=event_type,
        subject_type="daily_review",
        subject_id=review.id,
        severity=severity,
        payload={
            "review_date": review_date.isoformat(),
            "status": status,
            "version_number": version.version_number,
            **rule_snapshot["overview"],
        },
        source="daily_review_service",
        idempotency_key=f"{event_type}:{review.id}:{version.id}",
        request_id=request_id,
        correlation_id=request_id,
    )
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="daily_review.force_generate" if force else "daily_review.generate",
        target_type="daily_review",
        target_id=review.id,
        result="success",
        request_id=request_id,
        metadata={"review_date": review_date.isoformat(), "status": status, "version_number": version.version_number},
    )
    await session.commit()
    return await build_daily_review_detail(session, user_id=user_id, review_id=review.id, settings=settings)


async def _current_version(session: AsyncSession, review: DailyReview) -> DailyReviewVersion | None:
    if not review.current_version_id:
        return None
    return (
        await session.execute(
            select(DailyReviewVersion).where(
                DailyReviewVersion.id == review.current_version_id,
                DailyReviewVersion.daily_review_id == review.id,
            )
        )
    ).scalar_one_or_none()


async def _versions(session: AsyncSession, review_id: uuid.UUID) -> list[DailyReviewVersion]:
    return list(
        (
            await session.execute(
                select(DailyReviewVersion)
                .where(DailyReviewVersion.daily_review_id == review_id)
                .order_by(DailyReviewVersion.version_number.desc())
            )
        )
        .scalars()
        .all()
    )


def _summary_out(
    review: DailyReview,
    version: DailyReviewVersion | None,
    active_task: AITask | None = None,
) -> DailyReviewSummaryOut:
    overview = version.rule_snapshot.get("overview", {}) if version else {}
    return DailyReviewSummaryOut(
        id=review.id,
        user_id=review.user_id,
        review_date=review.review_date,
        status=review.status,
        current_version_id=review.current_version_id,
        current_version_number=version.version_number if version else None,
        generation_mode=version.generation_mode if version else None,
        input_fingerprint=review.input_fingerprint,
        generated_at=review.generated_at,
        stale_at=review.stale_at,
        archived_at=review.archived_at,
        created_at=review.created_at,
        updated_at=review.updated_at,
        overview=overview,
        ai_available=bool(version and version.ai_structured_result),
        generation_in_progress=active_task is not None,
        generation_task_id=active_task.id if active_task else None,
        generation_task_status=active_task.status if active_task else None,
    )


async def _mark_stale(
    session: AsyncSession,
    *,
    review: DailyReview,
    reason: str,
    request_id: str | None,
) -> None:
    if review.status == "stale" or not review.current_version_id or review.archived_at:
        return
    review.status = "stale"
    review.stale_at = utc_now()
    await create_business_event(
        session,
        user_id=review.user_id,
        event_type="user_daily_review.became_stale",
        subject_type="daily_review",
        subject_id=review.id,
        severity="notice",
        payload={"review_date": review.review_date.isoformat(), "reason": reason},
        source="daily_review_stale_detector",
        idempotency_key=f"user_daily_review.became_stale:{review.id}:{review.input_fingerprint}",
        request_id=request_id,
        correlation_id=request_id,
    )


async def ensure_review_stale_state(
    session: AsyncSession,
    *,
    review: DailyReview,
    settings: Settings,
    request_id: str | None,
) -> None:
    if not review.current_version_id or review.status == "stale" or review.archived_at:
        return
    _snapshot, fingerprint, _items = await build_rule_snapshot(
        session,
        user_id=review.user_id,
        review_date=review.review_date,
        settings=settings,
    )
    if review.input_fingerprint and review.input_fingerprint != fingerprint:
        await _mark_stale(session, review=review, reason="input_fingerprint_changed", request_id=request_id)
        await session.commit()


async def mark_reviews_stale_for_date(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_date: date,
    reason: str,
    request_id: str | None,
) -> None:
    review = (
        await session.execute(
            select(DailyReview).where(
                DailyReview.user_id == user_id,
                DailyReview.review_date == review_date,
                DailyReview.archived_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if review:
        await _mark_stale(session, review=review, reason=reason, request_id=request_id)


async def mark_all_reviews_stale_for_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    reason: str,
    request_id: str | None,
) -> None:
    reviews = list(
        (
            await session.execute(
                select(DailyReview).where(
                    DailyReview.user_id == user_id,
                    DailyReview.current_version_id.is_not(None),
                    DailyReview.status != "stale",
                    DailyReview.archived_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for review in reviews:
        await _mark_stale(session, review=review, reason=reason, request_id=request_id)


async def mark_reviews_stale_for_information_item(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    settings: Settings,
    reason: str,
    request_id: str | None,
) -> None:
    item = (
        await session.execute(select(InformationItem).where(InformationItem.id == item_id, InformationItem.user_id == user_id))
    ).scalar_one_or_none()
    if not item:
        return
    review_date = await effective_review_date_for_item(session, item=item, settings=settings)
    await mark_reviews_stale_for_date(
        session,
        user_id=user_id,
        review_date=review_date,
        reason=reason,
        request_id=request_id,
    )


async def list_daily_reviews(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
    settings: Settings,
) -> tuple[list[DailyReviewSummaryOut], int]:
    statement = select(DailyReview).where(DailyReview.user_id == user_id, DailyReview.archived_at.is_(None))
    if status:
        statement = statement.where(DailyReview.status == status)
    if date_from:
        statement = statement.where(DailyReview.review_date >= date_from)
    if date_to:
        statement = statement.where(DailyReview.review_date <= date_to)
    total = (await session.execute(select(func.count()).select_from(statement.order_by(None).subquery()))).scalar_one()
    reviews = list(
        (await session.execute(statement.order_by(DailyReview.review_date.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    summaries: list[DailyReviewSummaryOut] = []
    for review in reviews:
        summaries.append(
            _summary_out(
                review,
                await _current_version(session, review),
                await _active_daily_review_generation_task(
                    session,
                    user_id=user_id,
                    review_id=review.id,
                    settings=settings,
                    release_stale=True,
                ),
            )
        )
    return summaries, total


async def build_daily_review_detail(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_id: uuid.UUID,
    settings: Settings,
    request_id: str | None = None,
) -> DailyReviewDetailOut:
    review = await get_daily_review_or_404(session, user_id=user_id, review_id=review_id)
    await ensure_review_stale_state(session, review=review, settings=settings, request_id=request_id)
    await session.refresh(review)
    versions = await _versions(session, review.id)
    current = next((version for version in versions if version.id == review.current_version_id), None)
    active_task = await _active_daily_review_generation_task(
        session,
        user_id=user_id,
        review_id=review.id,
        settings=settings,
        release_stale=True,
    )
    summary = _summary_out(review, current, active_task)
    return DailyReviewDetailOut(
        **summary.model_dump(),
        current_version=current,
        versions=versions,
    )


async def get_daily_review_version(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_id: uuid.UUID,
    version_id: uuid.UUID,
) -> DailyReviewVersion:
    review = await get_daily_review_or_404(session, user_id=user_id, review_id=review_id)
    version = (
        await session.execute(
            select(DailyReviewVersion).where(
                DailyReviewVersion.id == version_id,
                DailyReviewVersion.daily_review_id == review.id,
            )
        )
    ).scalar_one_or_none()
    if not version:
        raise AppError(ErrorCode.DAILY_REVIEW_VERSION_NOT_FOUND, "每日复盘版本不存在", status_code=404)
    return version


async def archive_daily_review(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    review_id: uuid.UUID,
    archived: bool,
    settings: Settings,
    request_id: str | None,
) -> DailyReviewDetailOut:
    review = await get_daily_review_or_404(session, user_id=user_id, review_id=review_id)
    review.archived_at = utc_now() if archived else None
    await add_audit_log(
        session,
        actor_user_id=user_id,
        action="daily_review.archive" if archived else "daily_review.unarchive",
        target_type="daily_review",
        target_id=review.id,
        result="success",
        request_id=request_id,
    )
    await session.commit()
    return await build_daily_review_detail(session, user_id=user_id, review_id=review.id, settings=settings)
