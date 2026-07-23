# GeniusTrader Backend

FastAPI 后端第一阶段只覆盖基础工程、PostgreSQL 迁移、数据库 Session 认证、管理员创建用户、股票基础目录和用户自选股基础闭环。

当前不包含真实行情 Provider、公告资讯 Provider、AI Gateway、估值、复盘生成、通知编排、微信、Docker 或前端真实 API 接入。

## Windows PowerShell 本地运行

以下命令均在 `backend/` 目录执行。

### 1. 创建虚拟环境

```powershell
python -m venv .venv-backend
```

### 2. 安装依赖

```powershell
.\.venv-backend\Scripts\python.exe -m pip install --upgrade pip
.\.venv-backend\Scripts\python.exe -m pip install -e ".[dev]"
```

### 3. 配置读取

后端通过环境变量读取配置。本地开发会自动加载仓库根目录下被 Git 忽略的：

```text
../.local/database.env
```

不要把真实数据库密码复制到 `backend/.env` 或其他可提交文件。`backend/.env.example` 只包含占位值。

### 4. 执行迁移

```powershell
.\.venv-backend\Scripts\python.exe -m alembic upgrade head
.\.venv-backend\Scripts\python.exe -m alembic current
```

应用启动时不会自动修改数据库结构，所有结构变更必须走 Alembic。

### 5. 创建管理员

```powershell
.\.venv-backend\Scripts\python.exe -m app.cli.create_admin
```

该命令交互输入用户名和隐藏密码，不支持通过命令行参数传入密码。创建成功只输出用户名、角色和用户 ID。

### 6. 运行开发种子

```powershell
.\.venv-backend\Scripts\python.exe -m app.cli.seed_development
```

种子命令只在 `development` 环境运行，幂等创建 4 只开发用股票基础目录，不创建真实行情、板块、AI 配置、微信身份或估值结果。

### 7. 启动 FastAPI

Windows 本地推荐使用项目启动器，以兼容 psycopg 异步连接所需的 Selector event loop：

```powershell
.\.venv-backend\Scripts\python.exe -m app.cli.run_dev
```

单进程验证可用：

```powershell
.\.venv-backend\Scripts\python.exe -m app.cli.run_dev --no-reload
```

接口文档：

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

### 8. 测试数据库

集成测试只允许在独立测试库 `geniustrader_test` 上执行破坏性清理。若测试库不存在，测试会安全跳过需要数据库的用例，不会清空开发库 `geniustrader`。

如当前 `root` 项目角色没有 `CREATEDB` 权限，请由 PostgreSQL 管理员一次性执行：

```powershell
& "D:\apps\postgreSQL\bin\psql.exe" -h 127.0.0.1 -U postgres -d postgres -c "CREATE DATABASE geniustrader_test OWNER root;"
```

管理员密码应交互输入，不得写入仓库、脚本或日志。

2026-07-23 收尾验收中，`geniustrader_test` 已创建并由 `root` 拥有；完整集成测试已在该测试库实际运行，不再因测试库不存在而跳过核心用例。测试库迁移回滚和重新升级仅在 `geniustrader_test` 执行，未回滚或清理开发库 `geniustrader`。

### 9. 运行测试和检查

```powershell
.\.venv-backend\Scripts\python.exe -m pytest -q
.\.venv-backend\Scripts\python.exe -m ruff check . --no-cache
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP "geniustrader-backend-pycache"
.\.venv-backend\Scripts\python.exe -m compileall app tests
```

最近一次收尾验收结果：`30 passed, 0 failed, 0 skipped`。pytest 配置禁用本地 cacheprovider，仅避免 Windows/本地沙箱写入 `.pytest_cache` 时卡住，不跳过任何测试。

## 本地端口

- 前端 Mock：`http://127.0.0.1:3000`
- 后端 API：`http://127.0.0.1:8000`
- PostgreSQL：`127.0.0.1:5432`

当前前端仍使用本地 Mock 数据，不会自动连接本后端。

## API 边界

### 健康检查

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`

### 认证

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/change-password`

认证使用数据库 Session。浏览器只持有随机不透明 Token 的 HttpOnly Cookie；数据库只保存 Token 哈希；JSON 响应不返回 Session Token。

### 管理员

- `POST /api/v1/admin/users`

仅管理员可创建普通用户。创建用户会自动创建“默认分组”，并记录审计日志。公开注册不属于当前阶段。

### 股票基础目录

- `GET /api/v1/stocks`
- `GET /api/v1/stocks/{stock_id}`

只返回本地 `stocks` 表基础信息，不返回行情、K线、板块、估值或 AI 结果。

### 自选股、分组和标签

- `GET /api/v1/watchlist`
- `POST /api/v1/watchlist`
- `GET /api/v1/watchlist/{item_id}`
- `PATCH /api/v1/watchlist/{item_id}`
- `DELETE /api/v1/watchlist/{item_id}`
- `GET /api/v1/watchlist/groups`
- `POST /api/v1/watchlist/groups`
- `PATCH /api/v1/watchlist/groups/{group_id}`
- `DELETE /api/v1/watchlist/groups/{group_id}`
- `GET /api/v1/watchlist/tags`
- `POST /api/v1/watchlist/tags`
- `PATCH /api/v1/watchlist/tags/{tag_id}`
- `DELETE /api/v1/watchlist/tags/{tag_id}`

`DELETE /api/v1/watchlist/{item_id}` 采用归档策略，设置 `archived_at`，不删除 `stocks` 或用户标签。归档后重新 `POST` 同一股票会恢复原记录，使用新的分组、关注原因、备注和标签，不创建第二条重复记录。

已归档自选股默认不允许 `PATCH` 修改。重复删除已归档记录保持幂等；跨用户 UUID 不会泄露真实归属。

## 统一错误格式

```json
{
  "error": {
    "code": "WATCHLIST_LIMIT_EXCEEDED",
    "message": "自选股数量已达到上限",
    "request_id": "..."
  }
}
```

所有错误响应包含 `request_id`，响应头包含 `X-Request-ID`。内部异常、SQL、数据库连接信息、密码、Cookie 和 Session Token 不返回客户端。

## 第一阶段收尾验收记录

- 测试数据库：`geniustrader_test`，与开发库 `geniustrader` 隔离。
- 测试库迁移版本：`202607230001 (head)`。
- 迁移回滚：仅在 `geniustrader_test` 执行 `downgrade base` 后重新 `upgrade head`；业务表可移除并恢复。
- 完整 pytest：`30 passed, 0 failed, 0 skipped`。
- Windows 本地启动：继续使用 `.\.venv-backend\Scripts\python.exe -m app.cli.run_dev`。
- 当前仍未实现：真实行情、公告资讯、AI Gateway、估值、复盘生成、通知编排、微信、Docker 和前端真实 API 接入。
