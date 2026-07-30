# 模块化自选股研究工作台 V0.2 草案

## 阶段定位

第八阶段将 GeniusTrader 从“信息中心 + 自选股 + 每日复盘”的分散页面，收口为模块化研究工作台。目标是让用户围绕自选股完成“发现信号、生成待办、跟踪观察、验证结果、进入下一次复盘”的闭环。

本阶段不新增 AI 聊天、自由问答、对话线程、消息表、交易建议、自动买卖点、自动调度、真实 Provider 联网 Smoke 或生产部署能力。

## 新增模块

- 今日研究总览：展示业务日期、自选股研究状态、优先股票、待处理事项、到期观察条件和最新复盘状态。
- 自选股扫描器：按新增信息、公告候选、打开研究事项、观察条件和复盘 stale 状态计算关注分。
- 个股研究档案：聚合股票身份、用户关注逻辑、当前研究状态、官方信息、研究事项、时间线和复盘历史。
- 研究事项中心：管理待核实、观察条件、后续跟进、缺少材料和用户笔记。
- 观察条件闭环：状态支持 `pending`、`monitoring`、`confirmed`、`disproved`、`partially_confirmed`、`unable_to_determine`、`no_longer_applicable`、`dismissed`。

## 数据边界

- `research_tasks` 和 `research_task_updates` 是用户私有数据。
- AI 分析和每日复盘只能提出建议，不自动创建研究事项。
- 用户显式创建、采纳或更新研究事项后，结果才进入后续每日复盘的 `rule_snapshot`。
- 任务来源必须可追溯到用户、信息分析、每日复盘、公告或系统规则。
- 任务和观察条件不得包含交易指令、目标价、仓位、收益预测或自动买卖建议。

## 后端 API

- `GET /api/v1/today/overview`
- `GET /api/v1/watchlist/scanner`
- `GET /api/v1/stocks/{stock_id}/research-dossier`
- `GET /api/v1/research-tasks`
- `POST /api/v1/research-tasks`
- `GET /api/v1/research-tasks/{task_id}`
- `PATCH /api/v1/research-tasks/{task_id}`
- `POST /api/v1/research-tasks/{task_id}/status`
- `POST /api/v1/research-tasks/{task_id}/updates`
- `DELETE /api/v1/research-tasks/{task_id}`：软忽略为 `dismissed`。

## AI Schema 扩展

信息分析结构保留旧字段，并增加：

- `confirmed_facts`
- `key_changes`
- `affected_dimensions`
- `relation_to_focus_reason`
- `open_questions`
- `suggested_research_tasks`
- `suggested_observation_conditions`
- `source_coverage`

这些字段只作为结构化建议和解释材料，不自动写入 `research_tasks`。

## 页面承载

- `/today`：研究总览，不展示 Mock 行情，不新增 AI 聊天。
- `/watchlist`：真实自选股管理 + 扫描器信号。
- `/watchlist/[stockId]`：个股研究档案。
- `/information/tasks`：信息中心下的研究事项中心，不新增一级导航。
- `/reviews/[reviewId]`：展示复盘建议采纳入口，用户点击后才创建研究事项。

## 验收重点

- 今日总览、扫描器和个股档案均按当前用户隔离。
- 无行情、无公告、AI 失败或数据部分缺失时，页面分区降级。
- 观察条件状态更新后进入下一次每日复盘规则快照。
- 同一 AI 或复盘建议重复采纳保持幂等，不重复创建研究事项。
- 前端不出现聊天输入框、自由问答、对话历史或消息线程。
- 后端测试不调用真实 AI、真实行情、真实公告网络或真实 Provider。
