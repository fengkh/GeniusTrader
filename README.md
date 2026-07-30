# GeniusTrader

## Phase 8 Scope Note

Phase 8 adds the modular watchlist research workbench V0.2. It introduces user-private `research_tasks` and `research_task_updates`, `/today/overview`, `/watchlist/scanner`, `/stocks/{stock_id}/research-dossier`, and `/information/tasks`. AI can suggest research tasks and observation conditions, but only an explicit user action creates or updates tasks. This phase does not add AI chat, conversation threads, trading advice, real Provider networking, automatic scheduling, or production deployment changes.

See `docs/28_MODULAR_RESEARCH_WORKBENCH_V02_DRAFT.md` for the detailed scope.

## Fullstack Phase 6A Scope Note

Phase 6A adds the A-share security master prerequisite for real watchlist management. It introduces a `SecurityMasterProvider` abstraction, local `stocks` master-data sync, admin-only manual sync, stock search, and `/watchlist` real API management. SSE, SZSE, and BSE remain candidate security-directory sources under development feature flags; BaoStock is only a non-official development supplement. This phase does not add real quotes, minute bars, K-lines, financials, valuation, automatic security-directory scheduling, automatic announcement sync, WeChat, or trading.

The watchlist boundary text is: `证券基本信息来自证券目录同步；行情、财务、估值和技术指标仍未接入真实数据。`

See `docs/22_SECURITY_MASTER_AND_REAL_WATCHLIST_DRAFT.md` for the detailed 6A product and technical boundary.

2026-07-26 6A.1 update: local development security master validation now has SSE official SH coverage, BSE official BJ code mapping coverage, and `BAOSTOCK_DEVELOPMENT_FALLBACK` as a non-official development-only SZ supplement. SZSE official directory remains unresolved and no provider is frozen for production.

## Fullstack Phase 6 Scope Note

The sixth phase adds an experimental external source registry and a manually triggered listed-company announcement candidate inbox. CNINFO and SSE disclosure are registered as disabled experimental sources only; they are not confirmed production data providers. Announcement sync, real network access, provider adapters, and PDF extraction are all feature-flagged and default off. Announcement candidates do not trigger AI, BusinessEvent, Notification, or daily review generation until the user explicitly imports a candidate into InformationItem and then uses existing flows.

See `docs/21_EXTERNAL_SOURCES_AND_ANNOUNCEMENT_INGESTION_DRAFT.md` for the detailed product and technical boundary.

GeniusTrader 是一套面向 A 股个人研究场景的自选股复盘与多源舆情管理平台。第一版聚焦“A 股自选股复盘闭环”，帮助用户管理自选股、追踪行情与公告资讯、整理舆情线索，并使用用户自带的 AI API 生成可追溯的每日复盘。

当前仓库已进入第七阶段发布收口：Mock 前端原型、FastAPI 后端基础工程、受控信息采集与 AI Gateway、信息中心前端真实 API 联调、用户私有信息每日复盘、BusinessEvent、站内通知、公告候选收件箱和 `/watchlist` 真实自选股管理已建立。生产发布默认关闭未获授权真实行情和 Mock 行情；无授权行情时页面显示“暂无经授权的真实行情数据。”，不展示模拟价格、K 线、分时或 AI 生成行情数字。

## 明确边界

- GeniusTrader 不是证券交易系统。
- 第一版不接入券商账户。
- 第一版不提供自动下单、买卖点、跟单、荐股、收益预测或收益承诺。
- 当前仓库不得存储真实 API Key、密码、Cookie、Token 或真实用户数据。
- AI 只用于文本理解、摘要、分类和复盘辅助，不得编造行情数字或替代程序计算。

## 文档目录

- `docs/00_PRODUCT_CONTEXT.md`：产品上下文与已确认决策。
- `docs/01_PRODUCT_BRIEF.md`：第一版产品简介。
- `docs/02_PRD_V1_DRAFT.md`：第一版 PRD 草案。
- `docs/03_PAGE_MAP.md`：页面信息架构。
- `docs/04_USER_FLOWS.md`：核心用户流程。
- `docs/05_DATA_SOURCE_MATRIX.md`：数据来源矩阵建议。
- `docs/06_AI_TASK_SPEC.md`：AI 任务说明。
- `docs/07_DOMAIN_MODEL_DRAFT.md`：领域模型初稿。
- `docs/08_SECURITY_REQUIREMENTS.md`：安全要求。
- `docs/09_MVP_ACCEPTANCE_DRAFT.md`：MVP 验收草案。
- `docs/10_OPEN_QUESTIONS.md`：待产品负责人确认的问题。
- `docs/11_DEVELOPMENT_ROADMAP.md`：下一阶段路线图。
- `docs/12_DECISION_LOG.md`：产品决策日志。
- `docs/13_GLOSSARY.md`：术语表。
- `docs/16_BACKEND_ARCHITECTURE_DRAFT.md`：后端架构草案。
- `docs/17_INFORMATION_AI_ARCHITECTURE_DRAFT.md`：受控信息采集与 AI 分析架构草案。
- `docs/18_FRONTEND_INFORMATION_INTEGRATION_DRAFT.md`：信息中心前端真实 API 联调草案。
- `docs/19_DAILY_REVIEW_NOTIFICATION_ARCHITECTURE_DRAFT.md`：用户每日复盘与站内通知架构草案。
- `docs/20_INFORMATION_PROVIDER_FEASIBILITY_DRAFT.md`：官方公告与财经资讯数据源可行性 Spike 草案。
- `docs/21_EXTERNAL_SOURCES_AND_ANNOUNCEMENT_INGESTION_DRAFT.md`：外部来源与公告候选收件箱试点草案。
- `docs/22_SECURITY_MASTER_AND_REAL_WATCHLIST_DRAFT.md`：A 股证券主数据与真实自选股闭环草案。
- `docs/23_REAL_MARKET_DATA_AND_LAUNCH_MVP_DRAFT.md`：真实行情候选与可上线 MVP 草案。
- `docs/24_PRODUCTION_DEPLOYMENT_RUNBOOK_DRAFT.md`：生产部署运行手册草案。
- `docs/25_OPERATIONS_AND_BACKUP_DRAFT.md`：运维、备份与恢复草案。
- `docs/26_MARKET_DATA_PROVIDER_AUTHORIZATION_CHECKLIST_DRAFT.md`：行情 Provider 授权确认清单。
- `docs/27_PRODUCTION_SERVER_EXECUTION_CHECKLIST.md`：Linux 服务器发布执行清单。
- `docs/28_MODULAR_RESEARCH_WORKBENCH_V02_DRAFT.md`：模块化自选股研究工作台 V0.2 草案。

## 当前状态

当前已存在 Next.js 前端与 FastAPI 后端工程。认证、AI Provider、信息中心、用户每日复盘、站内通知、公告候选和 `/watchlist` 自选股管理走本地真实 API；今日、个股详情和行情设置页只消费真实行情状态契约。真实行情、估值、全市场复盘、外部通知和正式生产数据 Provider 尚未授权上线；未确认的数据供应商不得写死；不得提交真实 API Key、数据库密码、Cookie、Token、AI Key 或 `APP_ENCRYPTION_KEYS`。

前端本地联调使用根目录 `.env.local` 中的：

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

后端本地密钥放在被 Git 忽略的 `.local/app.env`，只用于本机加密用户 AI Provider Key。

## Backend Phase 2 Scope Note

The backend second phase adds controlled information intake, encrypted user AI Provider configuration, AI Gateway metadata logging, and structured information analysis. It does not add broker access, trading, full-site social crawling, real market-data provider selection, real AI calls in tests, or production deployment.

## Frontend Phase 3 Scope Note

The third frontend integration phase connects authentication, AI Provider settings, and the information center to the local FastAPI backend.

## Fullstack Phase 4 Scope Note

The fourth phase adds user-private daily reviews, review versions, BusinessEvent records, real in-app notifications, notification preferences, and frontend integration for `/reviews`, `/reviews/[reviewId]`, `/notifications`, and the in-app section of `/settings/notifications`. It still does not add real market data providers, full-market review backend, valuation backend, schedulers, task queues, WeChat, email, Web Push, or mobile Push.
