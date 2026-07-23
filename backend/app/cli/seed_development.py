import asyncio
import sys
from datetime import date

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.stock import Stock
from app.repositories.stocks import get_stock_by_symbol_exchange

SEED_STOCKS = [
    {
        "symbol": "600519",
        "exchange": "SH",
        "name": "贵州茅台",
        "market": "A_SHARE",
        "list_date": date(2001, 8, 27),
    },
    {
        "symbol": "000001",
        "exchange": "SZ",
        "name": "平安银行",
        "market": "A_SHARE",
        "list_date": date(1991, 4, 3),
    },
    {
        "symbol": "300750",
        "exchange": "SZ",
        "name": "宁德时代",
        "market": "A_SHARE",
        "list_date": date(2018, 6, 11),
    },
    {
        "symbol": "688981",
        "exchange": "SH",
        "name": "中芯国际",
        "market": "A_SHARE",
        "list_date": date(2020, 7, 16),
    },
]


async def _seed() -> int:
    settings = get_settings()
    if settings.app_env.lower() != "development":
        print("开发种子只能在 development 环境运行", file=sys.stderr)
        return 2
    created = 0
    async with AsyncSessionLocal() as session:
        try:
            for row in SEED_STOCKS:
                existing = await get_stock_by_symbol_exchange(
                    session,
                    symbol=row["symbol"],
                    exchange=row["exchange"],
                )
                if existing:
                    continue
                session.add(
                    Stock(
                        symbol=row["symbol"],
                        exchange=row["exchange"],
                        name=row["name"],
                        market=row["market"],
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
    print(f"开发种子完成: created={created} total={len(SEED_STOCKS)}")
    print("说明: 仅为开发基础目录，不构成推荐，不包含真实行情、板块、AI或估值数据。")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_seed()))


if __name__ == "__main__":
    main()
