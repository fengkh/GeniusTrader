# GeniusTrader

GeniusTrader 是一套面向 A 股个人研究场景的自选股复盘与多源舆情管理平台。第一版聚焦“A 股自选股复盘闭环”，帮助用户管理自选股、追踪行情与公告资讯、整理舆情线索，并使用用户自带的 AI API 生成可追溯的每日复盘。

当前仓库处于产品设计与文档基线阶段，尚未开始前端、后端、数据库或部署工程开发。本仓库当前只应保存产品文档、需求说明和基础仓库配置。

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

## 当前状态

本仓库尚未初始化任何业务工程。后续只有在产品文档基线获得确认后，才能进入技术方案、工程初始化和代码开发阶段。
## Backend Phase 2 Scope Note

The backend second phase adds controlled information intake, encrypted user AI Provider configuration, AI Gateway metadata logging, and structured information analysis. It does not add broker access, trading, full-site social crawling, real market-data provider selection, real AI calls in tests, or production deployment.
