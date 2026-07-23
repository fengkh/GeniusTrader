# GeniusTrader

GeniusTrader 是一套面向 A 股个人研究场景的自选股复盘与多源舆情管理平台。第一版聚焦“A 股自选股复盘闭环”，帮助用户管理自选股、追踪行情与公告资讯、整理舆情线索，并使用用户自带的 AI API 生成可追溯的每日复盘。

当前仓库已进入分阶段实现：Mock 前端原型、FastAPI 后端基础工程、受控信息采集与 AI Gateway 后端已建立；当前阶段正在进行 `/login`、`/information`、`/information/[itemId]` 和 `/settings/ai` 的前端真实 API 联调。

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

## 当前状态

当前已存在 Next.js Mock 前端与 FastAPI 后端工程。仍保持以下边界：行情、复盘、估值、通知真实业务和数据 Provider 尚未接入；未确认的数据供应商不得写死；不得提交真实 API Key、数据库密码、Cookie、Token、AI Key 或 `APP_ENCRYPTION_KEYS`。

前端本地联调使用根目录 `.env.local` 中的：

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

后端本地密钥放在被 Git 忽略的 `.local/app.env`，只用于本机加密用户 AI Provider Key。

## Backend Phase 2 Scope Note

The backend second phase adds controlled information intake, encrypted user AI Provider configuration, AI Gateway metadata logging, and structured information analysis. It does not add broker access, trading, full-site social crawling, real market-data provider selection, real AI calls in tests, or production deployment.

## Frontend Phase 3 Scope Note

The third frontend integration phase connects authentication, AI Provider settings, and the information center to the local FastAPI backend. `/today`, `/watchlist`, stock detail, market review, reviews, notifications, and notification settings remain Mock pages in this phase.
