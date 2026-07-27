import asyncio
import sys
from datetime import date

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.stock import Stock
from app.providers.securities.normalization import normalize_board, normalize_symbol, pinyin_fields
from app.repositories.stocks import get_stock_by_symbol_exchange

SEED_STOCKS = [
    {
        "code": "600519",
        "exchange": "SH",
        "name": "贵州茅台",
        "market": "A_SHARE",
        "board": "main_board",
        "list_date": date(2001, 8, 27),
    },
    {
        "code": "000001",
        "exchange": "SZ",
        "name": "平安银行",
        "market": "A_SHARE",
        "board": "main_board",
        "list_date": date(1991, 4, 3),
    },
    {
        "code": "300750",
        "exchange": "SZ",
        "name": "宁德时代",
        "market": "A_SHARE",
        "board": "chinext",
        "list_date": date(2018, 6, 11),
    },
    {
        "code": "688981",
        "exchange": "SH",
        "name": "中芯国际",
        "market": "A_SHARE",
        "board": "star_board",
        "list_date": date(2020, 7, 16),
    },
]


async def _seed() -> int:
    settings = get_settings()
    if settings.app_env.lower() != "development":
        print("开发种子只能在 development 环境运行", file=sys.stderr)
        return 2
    created = 0
    updated = 0
    async with AsyncSessionLocal() as session:
        try:
            for row in SEED_STOCKS:
                pinyin, initials = pinyin_fields(row["name"])
                full_symbol = normalize_symbol(row["code"], row["exchange"])
                existing = await get_stock_by_symbol_exchange(
                    session,
                    symbol=row["code"],
                    exchange=row["exchange"],
                )
                if existing:
                    changed = False
                    if existing.source_code == "development_seed":
                        updates = {
                            "code": row["code"],
                            "exchange": row["exchange"],
                            "name": row["name"],
                            "market": row["market"],
                            "board": row.get("board") or normalize_board(None, exchange=row["exchange"], code=row["code"]),
                            "security_type": "common_stock",
                            "short_name": row["name"],
                            "full_name": row["name"],
                            "listing_status": "active",
                            "listed_at": row["list_date"],
                            "aliases": existing.aliases or [row["name"]],
                            "pinyin": pinyin,
                            "pinyin_initials": initials,
                            "source_record_id": existing.source_record_id or full_symbol,
                            "data_completeness": existing.data_completeness or "partial",
                            "is_searchable": True,
                            "list_status": "listed",
                            "list_date": row["list_date"],
                            "currency": "CNY",
                        }
                    else:
                        updates = {
                            "aliases": existing.aliases or [row["name"]],
                            "pinyin": existing.pinyin or pinyin,
                            "pinyin_initials": existing.pinyin_initials or initials,
                        }
                    for attr, value in updates.items():
                        if getattr(existing, attr) != value:
                            setattr(existing, attr, value)
                            changed = True
                    if not existing.data_source:
                        existing.data_source = "development_seed"
                        changed = True
                    if existing.source_code == "development_seed" and not existing.last_synced_at:
                        existing.last_synced_at = None
                    if changed:
                        updated += 1
                    continue
                session.add(
                    Stock(
                        symbol=full_symbol,
                        code=row["code"],
                        exchange=row["exchange"],
                        name=row["name"],
                        market=row["market"],
                        board=row.get("board") or normalize_board(None, exchange=row["exchange"], code=row["code"]),
                        security_type="common_stock",
                        short_name=row["name"],
                        full_name=row["name"],
                        listing_status="active",
                        listed_at=row["list_date"],
                        aliases=[row["name"]],
                        pinyin=pinyin,
                        pinyin_initials=initials,
                        source_code="development_seed",
                        source_record_id=full_symbol,
                        last_synced_at=None,
                        data_completeness="partial",
                        is_searchable=True,
                        list_status="listed",
                        list_date=row["list_date"],
                        currency="CNY",
                        data_source="development_seed",
                    )
                )
                created += 1
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            print("开发种子写入失败: 数据库暂时不可用", file=sys.stderr)
            return 3
    print(f"开发种子完成: created={created} updated={updated} total={len(SEED_STOCKS)}")
    print("说明: 仅为开发基础目录，不构成推荐，不包含真实行情、板块、AI或估值数据。")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_seed()))


if __name__ == "__main__":
    main()
