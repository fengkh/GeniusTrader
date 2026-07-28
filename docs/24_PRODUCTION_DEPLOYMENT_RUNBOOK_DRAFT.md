# 生产部署运行手册草案

日期：2026-07-28

本文件记录 GeniusTrader 可上线 MVP 的生产部署草案。当前仅作为第七阶段 Checkpoint A 的离线工程基线，未完成真实 Provider 授权冻结。

## 一、部署形态

- 前端：Next.js production build。
- 后端：FastAPI + Uvicorn。
- 数据库：PostgreSQL 持久化卷。
- 入口：反向代理终止 HTTPS 并转发到前后端服务。
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
- 管理员账户通过既有 bootstrap CLI 或人工安全流程创建。
- 日志不得打印密码、API Key、Cookie、Session Token、CSRF Token、数据库密码或完整 Provider 响应。

## 三、环境文件

`deploy/production.env.example` 只提供占位模板。实际生产环境文件必须保存在服务器私有位置，并确保不被 Git 跟踪。

本阶段不创建真实 `.env`，不写入真实数据库密码、`APP_ENCRYPTION_KEYS`、Tushare Token 或 AI Key。

## 四、容器与网络

`docker-compose.production.yml` 提供前端、后端、PostgreSQL 和 Nginx 反向代理的组合示例。数据库只暴露给 Compose 内部网络，外部只暴露 HTTP/HTTPS 入口。

生产部署前应检查：

- `docker compose config` 可通过。
- 后端 `/api/v1/health/live` 可访问。
- 后端 `/api/v1/health/ready` 可访问。
- 前端可访问并能完成登录。
- 容器重启后数据库数据仍保留。

## 五、Provider 上线门槛

即使真实 Provider 技术 Smoke 成功，也只能说明技术可达。生产上线前必须完成授权冻结，并将 Provider 的 `authorization_status`、`usage_scope` 和 `production_enabled` 与书面授权一致。

未经确认时，页面可以展示“开发验证来源，尚未确认公开展示授权”，但不得展示为正式生产行情源。

