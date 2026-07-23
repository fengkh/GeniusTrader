# 后端架构草案

本文记录 GeniusTrader 正式后端第一阶段的工程边界。当前阶段只实现账户认证、自选股基础闭环、股票基础目录、数据库迁移、日志和审计基础，不实现真实行情、公告资讯、AI Gateway、估值、复盘生成、通知编排、微信或 Docker。

## 架构边界

- 前端与后端分离。现有 Next.js Mock 前端仍使用本地 Mock 数据，不会自动连接后端 API。
- 后端使用 FastAPI 提供 `/api/v1` HTTP API。
- 数据库使用 PostgreSQL，本地开发配置来自仓库根目录 `.local/database.env` 或环境变量。
- 数据库结构变更只通过 Alembic 迁移，应用启动时不自动建表或改表。

## FastAPI 模块边界

- `app/api/routes`：HTTP 路由，只处理请求响应、依赖注入和状态码。
- `app/services`：业务规则、事务边界、密码与 Session 操作、自选股归档和恢复规则。
- `app/repositories`：数据库查询。用户私有资源查询必须在 SQL 条件中显式包含 `user_id`。
- `app/models`：SQLAlchemy 2 ORM 模型。
- `app/schemas`：Pydantic 2 请求与响应模型，避免输出密码哈希、Session Token 和敏感字段。
- `app/core`：配置、数据库、时间、错误、日志和安全工具。
- `app/cli`：管理员创建、开发种子和本地启动器。

## 数据库与迁移

第一阶段迁移 `create_core_users_and_watchlist` 创建：

- `users`
- `user_credentials`
- `user_sessions`
- `stocks`
- `watchlist_groups`
- `user_watchlist_items`
- `user_tags`
- `watchlist_item_tags`
- `audit_logs`

所有主键优先使用 UUID；可修改实体包含 `updated_at`；关键唯一性由数据库约束保证。应用和迁移使用项目数据库角色，不使用超级用户运行。

## 配置管理

后端只从环境变量读取配置。本地开发允许加载 `../.local/database.env`，并允许显式环境变量覆盖。可提交的 `backend/.env.example` 只包含占位值。

关键配置包括：

- `APP_ENV`
- `APP_NAME`
- `APP_TIMEZONE`
- `DATABASE_URL`
- `SESSION_COOKIE_NAME`
- `SESSION_TTL_SECONDS`
- `SESSION_COOKIE_SECURE`
- `CORS_ALLOWED_ORIGINS`
- `LOG_LEVEL`

## 时间处理

数据库连接会话使用 UTC 时区，API 输出 timezone-aware ISO 8601 时间。用户展示默认按 Asia/Shanghai 处理。业务日期与技术时间戳分开。

## 用户认证

第一阶段采用数据库 Session 认证：

- 登录成功生成随机不透明 Session Token。
- 浏览器只通过 HttpOnly Cookie 持有 Token。
- 数据库 `user_sessions.token_hash` 只保存 Token 哈希。
- JSON 响应不得返回 Session Token。
- 退出时吊销当前 Session。
- 修改密码后吊销除当前会话外的其他会话。
- 过期、吊销或用户被禁用的 Session 不得继续访问。

密码使用 Argon2id 哈希。连续 5 次登录失败后，凭证短期锁定 15 分钟；该短期锁定使用 `locked_until`，不把用户永久状态改为 `locked`。

## 用户数据隔离

自选股、分组、标签、关注原因和未来用户私有数据均按 `user_id` 隔离。跨用户读取、修改、删除或引用分组/标签必须拒绝，并避免泄露目标 UUID 是否真实存在。

Repository 查询不得先按资源 ID 查出记录后再在 Python 判断归属；必须在 SQL 条件中同时包含资源 ID 和当前 `user_id`。

## 自选股领域

- 每位用户创建时自动拥有“默认分组”。
- 同一用户同一股票只能有一条有效自选股记录。
- 自选股软限制为 200 只，超过返回 `WATCHLIST_LIMIT_EXCEEDED`。
- 删除自选股采用归档策略，不删除股票基础目录和用户标签。
- 归档后重新添加同一股票会恢复原记录，不创建第二条重复记录。
- 用户标签独立于标准行业、标准概念和系统建议，不得混用。

## API 错误规范

业务错误统一返回：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "错误说明",
    "request_id": "..."
  }
}
```

请求参数校验错误也转换为统一结构。内部异常不向客户端返回 Python 堆栈、SQL、数据库连接信息或敏感请求体。

## 请求 ID 与日志

每个请求生成或复用合法 `X-Request-ID`，所有响应返回 `X-Request-ID`。技术日志为结构化 JSON，包含请求 ID、方法、路径、状态码、耗时、用户 ID 和错误码。日志不得记录完整 Cookie、Session Token、密码、密码哈希、数据库连接密码、Authorization 头或未来 AI API Key。

审计日志写入 `audit_logs`，保存操作者、动作、对象、结果、请求 ID 和脱敏 metadata。审计日志和技术日志分开。

## 测试数据库

集成测试优先使用独立数据库 `geniustrader_test`。测试启动前检查数据库名必须以 `_test` 结尾，破坏性清理只作用于测试库。当前项目角色没有创建数据库权限时，不提升权限，不回退清空开发库。

2026-07-23 收尾验收中，`geniustrader_test` 已创建并由 `root` 拥有。完整 pytest 已在测试库实际运行，结果为 `30 passed, 0 failed, 0 skipped`。迁移回滚验证只在 `geniustrader_test` 执行：先降级到 base，确认本阶段业务表移除，再重新升级到 `202607230001 (head)` 并确认核心表恢复。开发库 `geniustrader` 未执行回滚、清表或测试夹具。

## 后续接入方式

- AI Gateway：未来作为独立服务层接入，复用当前用户认证、用户隔离、错误格式、请求 ID 和审计规范；不得让前端接触用户 API Key。
- 信息中心：未来公告、资讯和舆情实体应复用 `user_id` 隔离和来源追踪规则。
- BusinessEvent 与 Notification：未来通知编排消费结构化业务事件，不由复盘、估值或公告模块直接调用外部通道。
- Provider Adapter：未来行情、公告、财务和板块 Provider 通过适配层接入；候选 Provider 未确认前不得硬编码为最终方案。

## 当前未实现能力

- 真实行情 Provider、K线、分时和量化指标入库。
- 公告资讯真实接入和信息中心业务 API。
- AI Gateway、AI 配置加密保存、AI 调用和复盘生成。
- 全市场复盘、估值、通知编排和外部通知通道。
- 微信公众号绑定、OAuth、模板消息或 API 调用。
- Docker、生产部署、邮件找回密码、公开注册和支付。

## 本地与未来生产差异

- 本地 Cookie `Secure=false`，生产必须 `Secure=true` 并使用 HTTPS。
- 本地允许 `localhost` 和 `127.0.0.1:3000` CORS；生产不得默认允许 localhost。
- 本地 `.local/database.env` 被 Git 忽略；生产必须使用环境变量或 Secrets 系统。
- 本地 Windows 使用 `app.cli.run_dev` 启动器兼容 psycopg 异步事件循环；Linux 服务器可使用标准 ASGI 运行方式。

## 第一阶段收尾验收状态

- 分支：`backend/mvp-foundation`。
- 迁移版本：`202607230001 (head)`。
- 测试结果：`30 passed, 0 failed, 0 skipped`。
- 测试库和开发库隔离：测试清理、迁移回滚和重新升级仅作用于 `geniustrader_test`。
- Windows 启动方式：继续优先使用 `python -m app.cli.run_dev`。
- 范围边界：仍未实现真实行情、公告资讯、AI Gateway、估值、复盘、通知编排、微信和 Docker。
## 后端第二阶段补充：信息采集与 AI Gateway

- 新增 `ai_provider_configs`、`ai_tasks`、`ai_task_attempts`、`information_items`、`information_sources`、`information_contents`、`content_fetch_attempts`、`information_analysis_versions`、`information_stock_relations`、`information_entity_mentions`、`verification_items`。
- 路由新增 `/api/v1/ai/providers` 和 `/api/v1/information`，继续使用既有 cookie session、`DataEnvelope`、`AppError` 和 `X-Request-ID`。
- 服务层新增 AI Provider 管理、受控 URL 抓取、HTML 正文提取、AI Gateway 和信息分析编排；当前同步执行，未来可迁移到任务队列。
- 安全边界：AI API Key Fernet/MultiFernet 加密；URL 抓取执行 SSRF 校验；AI Prompt 对第三方文本设置不可信边界；日志和审计元数据脱敏。
- 当前不新增 Redis、Celery、Kafka、Docker、浏览器自动化、全站爬虫、真实行情接入、每日复盘生成或通知业务。
