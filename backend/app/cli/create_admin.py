import asyncio
import getpass
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.core.database import AsyncSessionLocal
from app.core.errors import AppError, ErrorCode
from app.services.users import create_user


async def _create_admin() -> int:
    username = input("管理员用户名: ").strip()
    display_name = input("显示名称（可留空）: ").strip() or None
    password = getpass.getpass("管理员密码: ")
    password_confirm = getpass.getpass("再次输入管理员密码: ")
    if password != password_confirm:
        print("密码输入不一致", file=sys.stderr)
        return 2
    async with AsyncSessionLocal() as session:
        try:
            user = await create_user(
                session,
                username=username,
                display_name=display_name,
                password=password,
                role="admin",
                must_change_password=False,
                actor_user_id=None,
                request_id="cli.create_admin",
            )
            await session.commit()
        except AppError as exc:
            await session.rollback()
            if exc.code == ErrorCode.USERNAME_ALREADY_EXISTS:
                print("用户名已存在，未创建新管理员", file=sys.stderr)
                return 3
            print(f"创建失败: {exc.code.value} {exc.message}", file=sys.stderr)
            return 4
        except SQLAlchemyError:
            await session.rollback()
            print("创建失败: 数据库暂时不可用", file=sys.stderr)
            return 5
    print(f"创建成功: username={user.username} role={user.role} user_id={user.id}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_create_admin()))


if __name__ == "__main__":
    main()
