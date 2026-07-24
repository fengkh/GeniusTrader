# GeniusTrader Backend

FastAPI 后端已经覆盖基础工程、PostgreSQL 迁移、数据库 Session 认证、管理员创建用户、股票基础目录、用户自选股基础闭环、受控信息采集、AI Gateway、结构化信息分析、用户每日复盘、业务事件和站内通知。

当前不包含真实行情 Provider、公告资讯 Provider、估值后端、全市场真实复盘、自动调度、任务队列、微信、邮件、Web Push、移动 Push、Docker 或生产部署。

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

最近一次第四阶段开发中验收结果：`55 passed, 0 failed, 0 skipped`。pytest 配置禁用本地 cacheprovider，仅避免 Windows/本地沙箱写入 `.pytest_cache` 时卡住，不跳过任何测试。

## 本地端口

- 前端 Mock：`http://127.0.0.1:3000`
- 后端 API：`http://127.0.0.1:8000`
- PostgreSQL：`127.0.0.1:5432`

前端 `/login`、`/information`、`/information/[itemId]`、`/settings/ai`、`/reviews`、`/reviews/[reviewId]`、`/notifications` 和 `/settings/notifications` 的站内通知部分连接本地后端。`/today`、`/watchlist`、`/watchlist/[stockId]`、`/market-review/[date]`、估值中心和微信公众号区域仍保持 Mock。

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

登录成功还会生成独立 CSRF Token：后端保存 CSRF Token 哈希，并向浏览器设置非 HttpOnly、SameSite=Lax 的 CSRF Cookie。除登录外，`POST`、`PUT`、`PATCH` 和 `DELETE` 请求必须携带 `X-CSRF-Token` 请求头。退出登录会同时清理 Session Cookie 和 CSRF Cookie。

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

### 用户每日复盘

- `GET /api/v1/reviews`
- `POST /api/v1/reviews`
- `GET /api/v1/reviews/{review_id}`
- `PATCH /api/v1/reviews/{review_id}`
- `POST /api/v1/reviews/{review_id}/regenerate`
- `GET /api/v1/reviews/{review_id}/versions`
- `GET /api/v1/reviews/{review_id}/versions/{version_id}`

复盘业务日期为 `review_date`，按 `Asia/Shanghai` 解释。信息归属日期优先使用来源 `published_at`，缺失时使用信息创建时间。复盘只聚合当前用户保存的信息、最新成功分析版本、confirmed 股票关系、自选股、关注原因、用户标签和待核实事项，不代表全市场行情复盘。

常用手工请求示例使用占位值：

```powershell
# 生成当日或指定历史日期复盘。未配置 AI 时会生成 rules_only 规则复盘。
Invoke-RestMethod -Method Post -WebSession $session -Headers $headers -Uri http://127.0.0.1:8000/api/v1/reviews -ContentType "application/json" -Body '{"review_date":"YYYY-MM-DD","use_ai":true,"force":false}'

# force 重新生成，旧版本保留。
Invoke-RestMethod -Method Post -WebSession $session -Headers $headers -Uri "http://127.0.0.1:8000/api/v1/reviews/REVIEW_ID_PLACEHOLDER/regenerate?use_ai=true"

# 查看版本列表。
Invoke-RestMethod -Method Get -WebSession $session -Uri http://127.0.0.1:8000/api/v1/reviews/REVIEW_ID_PLACEHOLDER/versions
```

AI 失败时不会删除规则复盘，版本会以 `rules_with_ai_fallback` 保存，复盘状态为 `partial`。

### 站内通知

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `GET /api/v1/notifications/{notification_id}`
- `PATCH /api/v1/notifications/{notification_id}`
- `POST /api/v1/notifications/mark-all-read`
- `GET /api/v1/notification-preferences`
- `PUT /api/v1/notification-preferences`

当前真实通道仅为 `in_app`。`daily_digest` 当前表示不产生单条即时站内通知，而是进入每日复盘或摘要边界；没有自动定时任务，也没有真实微信推送。

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
- 当时仍未实现：真实行情、公告资讯、AI Gateway、估值、复盘生成、通知编排、微信、Docker 和前端真实 API 接入；后续阶段已补充 AI Gateway、信息中心、用户每日复盘和站内通知。
## Phase 2: Information Intake And AI Analysis

This backend stage adds:

- encrypted per-user OpenAI-compatible AI Provider configuration;
- controlled single-URL public content fetching with SSRF-oriented validation, redirect limits, content-type limits, timeout limits, and max-byte limits;
- manual information intake and URL information intake;
- content versions, fetch attempts, AI tasks, AI task attempts, structured analysis versions, stock relations, entity mentions, and verification items;
- strict structured AI analysis validation with one repair attempt;
- tests that mock all AI calls and do not contact real AI services.

Runtime configuration additions:

- `APP_ENCRYPTION_KEYS`: comma-separated Fernet keys. The first key encrypts new secrets; all keys decrypt existing secrets.
- `CSRF_COOKIE_NAME`: browser-readable CSRF cookie name. Default: `geniustrader_csrf`.
- `AI_REQUEST_TIMEOUT_SECONDS`, `AI_MAX_INPUT_CHARS`, `AI_MAX_OUTPUT_TOKENS`, `AI_MAX_RETRIES`.
- `CONTENT_FETCH_TIMEOUT_SECONDS`, `CONTENT_FETCH_MAX_BYTES`, `CONTENT_FETCH_MAX_REDIRECTS`, `CONTENT_ALLOWED_TYPES`.
- `ALLOW_PRIVATE_AI_BASE_URL`: development-only escape hatch for local AI-compatible endpoints.
- `INFORMATION_MAX_MANUAL_TEXT_CHARS`.

Generate a local Fernet key with:

```powershell
.\.venv-backend\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store local secrets outside Git, for example in `.local/app.env`.

Start the local development server on Windows with the project helper so psycopg uses a compatible asyncio selector loop:

```powershell
.\.venv-backend\Scripts\python.exe -m app.cli.run_dev --no-reload --host 127.0.0.1 --port 8000
```

Manual API smoke examples use placeholders only:

```powershell
# 1. Login with a locally created test account and keep the session cookie.
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
Invoke-RestMethod -Method Post -WebSession $session -Uri http://127.0.0.1:8000/api/v1/auth/login -ContentType "application/json" -Body '{"username":"TEST_USERNAME","password":"TEST_PASSWORD"}'
$csrf = ($session.Cookies.GetCookies("http://127.0.0.1:8000") | Where-Object { $_.Name -eq "geniustrader_csrf" }).Value
$headers = @{ "X-CSRF-Token" = $csrf }

# 2. Create an AI Provider. Do not paste real secrets into shared logs.
Invoke-RestMethod -Method Post -WebSession $session -Headers $headers -Uri http://127.0.0.1:8000/api/v1/ai/providers -ContentType "application/json" -Body '{"provider_name":"Local compatible model","base_url":"https://AI_BASE_URL_PLACEHOLDER/v1","model_name":"MODEL_NAME_PLACEHOLDER","api_key":"API_KEY_PLACEHOLDER","enabled":true}'

# 3. Submit manual information text.
Invoke-RestMethod -Method Post -WebSession $session -Headers $headers -Uri http://127.0.0.1:8000/api/v1/information/manual -ContentType "application/json" -Body '{"title":"示例信息","text":"这是一段用户手动补充的公开信息摘要。","source_type":"user_note"}'

# 4. Submit a public URL for controlled fetch.
Invoke-RestMethod -Method Post -WebSession $session -Headers $headers -Uri http://127.0.0.1:8000/api/v1/information/url -ContentType "application/json" -Body '{"url":"https://example.com/article","source_type":"news","fetch_now":true}'

# 5. Analyze an information item after replacing ITEM_ID_PLACEHOLDER.
Invoke-RestMethod -Method Post -WebSession $session -Headers $headers -Uri http://127.0.0.1:8000/api/v1/information/ITEM_ID_PLACEHOLDER/analyze -ContentType "application/json" -Body '{"force":false}'

# 6. Confirm or reject an AI suggested stock relation after replacing IDs.
Invoke-RestMethod -Method Patch -WebSession $session -Headers $headers -Uri http://127.0.0.1:8000/api/v1/information/ITEM_ID_PLACEHOLDER/stock-relations/RELATION_ID_PLACEHOLDER -ContentType "application/json" -Body '{"relation_status":"confirmed"}'

# 7. View information detail.
Invoke-RestMethod -Method Get -WebSession $session -Uri http://127.0.0.1:8000/api/v1/information/ITEM_ID_PLACEHOLDER
```
