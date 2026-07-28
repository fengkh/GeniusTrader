# 生产部署运行手册草案

日期：2026-07-28

本文件记录 GeniusTrader 可上线 MVP 的生产部署草案。当前仅作为第七阶段 Checkpoint A 的离线工程基线，未完成真实 Provider 授权冻结。

## 一、部署形态

- 前端：Next.js production build。
- 后端：FastAPI + Uvicorn。
- 数据库：PostgreSQL 持久化卷。
- 入口：Nginx 反向代理终止 HTTPS 并转发到 Compose 内部前后端服务。
- 迁移：后端容器启动前执行 Alembic upgrade。

## 二、生产默认要求

- `APP_ENV=production`。
- 必须使用 HTTPS。
- `SESSION_COOKIE_SECURE=true`。
- `CORS_ALLOWED_ORIGINS` 必须是域名白名单。
- `TRUSTED_HOSTS` 必须是域名白名单。
- `APP_ENCRYPTION_KEYS` 必填，不得进入 Git。
- 数据库不得暴露公网。
- 不开放公众注册。
- Provider 默认关闭。
- 未确认 `commercially_authorized` 的行情 Provider 不得在 production 启用。
- `BSE_DISCLOSURE` 默认关闭，完成真实 Smoke 和授权复核前不得生产启用。
- `DEBUG=false`、`PUBLIC_REGISTRATION_ENABLED=false`。
- `CORS_ALLOWED_ORIGINS` 和 `TRUSTED_HOSTS` 禁止通配。
- 管理员账户通过既有 bootstrap CLI 或人工安全流程创建。
- 日志不得打印密码、API Key、Cookie、Session Token、CSRF Token、数据库密码或完整 Provider 响应。

## 三、环境文件

`deploy/production.env.example` 只提供占位模板。实际生产环境文件必须保存在服务器私有位置，并确保不被 Git 跟踪。

本阶段不创建真实 `.env`，不写入真实数据库密码、`APP_ENCRYPTION_KEYS`、Tushare Token 或 AI Key。

## 四、容器与网络

`docker-compose.production.yml` 提供前端、后端、PostgreSQL 和 Nginx 反向代理的组合示例。数据库、后端和前端只暴露给 Compose 内部网络，外部只暴露 Nginx 的 HTTP/HTTPS 入口。

生产部署前应检查：

- `docker compose config` 可通过。
- `python -m app.cli.release_check` 不存在 fail 项；warning 项需人工确认。
- `python scripts/production_smoke.py --base-url https://your-domain.example` 完成基础 HTTP Smoke。
- 后端 `/api/v1/health/live` 可访问。
- 后端 `/api/v1/health/ready` 可访问。
- 前端可访问并能完成登录。
- 容器重启后数据库数据仍保留。

## 五、Provider 上线门槛

即使真实 Provider 技术 Smoke 成功，也只能说明技术可达。生产上线前必须完成授权冻结，并将 Provider 的 `authorization_status`、`usage_scope` 和 `production_enabled` 与书面授权一致。

未经确认时，页面可以展示“开发验证来源，尚未确认公开展示授权”，但不得展示为正式生产行情源。

## 六、生产发布门禁

后端生产启动会拒绝明显不安全配置，包括缺少或占位 `APP_ENCRYPTION_KEYS`、不安全 Cookie、通配 CORS/Trusted Hosts、localhost 数据库、示例数据库密码、公开注册开启、BaoStock development fallback 启用、BSE_DISCLOSURE 启用、Mock 行情启用、未授权行情网络启用。

服务器部署前还必须运行 `python -m app.cli.release_check`，确认数据库连通、Alembic 版本、管理员账户、证券主数据、公告来源、行情授权状态、备份状态和临时目录状态。该 CLI 不输出密钥，只输出 `configured/not_configured` 或脱敏状态。
