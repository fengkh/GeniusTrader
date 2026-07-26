# 用户每日复盘与站内通知架构草案

## 第六阶段补充：公告候选与复盘通知边界

- 公告候选不是每日复盘输入，不创建 `BusinessEvent`，不创建 `Notification`，不自动 AI 分析。
- 用户导入公告候选后生成的 InformationItem 可以触发相关日期每日复盘 stale，并可在用户主动 AI 分析后进入下一次复盘材料。
- 公告导入不新增公告专属即时通知；如导入后的 InformationItem 经过既有信息分析流程形成重要信息或待核实事项，才复用既有通知策略。
- `daily_digest` 偏好仍表示不创建单条即时通知，不代表已实现定时摘要调度。
- 公告 Provider 失败、PDF 提取失败或候选为空不得导致复盘、通知中心或已有 InformationItem 页面不可用。

本文记录第四阶段“用户每日复盘、业务事件与站内通知真实闭环”的实现边界。

## 实现边界

- 已实现真实 API：`/api/v1/reviews`、`/api/v1/reviews/{review_id}`、`/api/v1/notifications`、`/api/v1/notification-preferences`。
- 前端真实页面：`/reviews`、`/reviews/[reviewId]`、`/notifications`、`/settings/notifications` 的站内通知部分。
- 继续保持 Mock：`/today`、`/watchlist`、`/watchlist/[stockId]`、`/market-review/[date]`、估值中心、微信公众号状态和微信消息预览。
- 未实现：真实行情 Provider、全市场真实复盘、估值后端、自动调度、任务队列、微信公众号、邮件、Web Push 和移动 Push。

## 用户每日复盘边界

当前阶段实现的是“用户私有信息每日复盘”，不是全市场行情复盘。复盘只能基于当前用户保存的信息、最新成功信息分析版本、用户确认的股票关系、自选股、关注原因、用户标签和待核实事项。

不得生成市场涨跌家数、指数表现、板块涨幅、成交额、K 线结论、技术指标、估值结论、买卖建议、仓位建议、目标价格或收益预测。

页面必须提示：“当前复盘仅聚合用户保存和分析的信息，不代表全市场行情复盘。”

## 业务日期口径

- 复盘业务日期字段为 `review_date`，不是 `trade_date`。
- 时区按 `Asia/Shanghai`。
- `information_source.published_at` 存在时，转换到 `Asia/Shanghai` 后取日期。
- `published_at` 不存在时，使用 `information_item.created_at` 转换后的本地日期。
- 用户补充正文、强制重新分析和重新生成不改变信息原始归属日期。
- 当前阶段不引入交易日历，用户可以手动选择历史日期生成复盘。

## 信息纳入规则

纳入基础范围：

- 当前用户的数据；
- 未归档信息；
- 业务日期等于 `review_date`；
- 有可用正文版本。

已分析信息只使用最新成功 `information_analysis_version`。旧失败版本保留但不进入复盘内容。

未分析、分析失败、抓取失败但无正文、正在分析或内容不足的信息可以进入统计、局限和不可用列表，但不得生成 AI 事实结论。

股票关系处理：

- `confirmed`：可用于股票分组和自选股复盘。
- `suggested`：只进入“待确认关联”，不得作为正式归属。
- `rejected`：不得进入股票复盘，历史记录保留。
- confirmed 但股票不在自选股：进入“其他已确认关联股票”，不得伪装成自选股。
- AI 未匹配成功的实体只进入实体提及，不创建虚假股票。

## rule_snapshot

服务端先生成确定性 `rule_snapshot`，AI 只能解释它。结构至少包含：

- `schema_version`
- `review_date`
- `data_state`
- `generated_at`
- `scope_note`
- `overview`
- `watchlist_sections`
- `confirmed_non_watchlist_sections`
- `unassigned_information`
- `pending_relations`
- `global_verification_items`
- `limitations`
- `source_item_ids`
- `rule_summary`

`overview` 至少统计总信息数、已分析数、待分析数、分析失败数、重要信息数、confirmed/suggested 股票关系数、自选股数量、待核实数量、事实数量、观点数量和传闻数量。

`source_item_ids` 是来源追溯边界，复盘详情页应能跳转到 `/information/[itemId]`。

## AI 复盘层

AI 任务类型为 `user_daily_review_generation`。AI 输入只包含程序整理后的 `rule_snapshot`，不得直接重新分析完整网页原文。

AI 输出 Schema：

- `schema_version`
- `executive_summary`
- `key_developments`
- `stock_summaries`
- `verification_focus`
- `tomorrow_observation_focus`
- `uncertainty_summary`
- `limitations`
- `source_item_ids`

要求：

- 严格 Pydantic 校验，不允许未知字段静默进入。
- 允许一次 JSON repair。
- 第二次失败后使用规则复盘降级。
- `source_item_ids` 必须来自输入。
- 不得新增股票、事实、行情、财务、估值或价格数字。
- 不得把传闻升级为事实。
- 不得生成买入、卖出、仓位、目标价、收益预测或保证性表述。

## 复盘版本和幂等

- `daily_reviews` 以 `user_id + review_date` 唯一。
- 每次 force 重新生成创建新的 `daily_review_versions`，旧版本保留。
- `current_version_id` 指向当前版本。
- `input_fingerprint` 至少包含用户、日期、纳入信息、内容版本、最新成功分析版本、股票关系、自选股关注原因、用户标签、Prompt 版本和 Schema 版本。
- 输入未变化且非 force 时返回已有当前版本，不重复调用 AI，不重复生成通知。
- 输入变化时标记 `stale`，不自动覆盖旧版本。

## 复盘状态

- `complete`：规则结构完整，AI 成功，或未启用 AI 且规则复盘完整。
- `partial`：存在待分析、分析失败、内容不足、未确认关系，或 AI 摘要失败但规则复盘成功。
- `empty`：当日没有可纳入信息，仍可生成空复盘。
- `failed`：规则结构或保存失败；AI 失败不得直接导致 failed。
- `stale`：生成后输入指纹变化，需要用户主动重新生成。

## stale 检测

以下操作应使相关日期复盘变为 `stale`：

- 创建新的同日信息；
- 同日信息新增成功分析版本；
- 同日信息补充或修正正文；
- 股票关系确认或驳回导致 confirmed 关系变化；
- 信息归档或取消归档；
- 用户自选股添加、移除、关注原因或标签变化；
- 获取复盘详情时重新计算 input_fingerprint 发现变化。

`stale` 只提示“需要重新生成”，不删除历史版本，不自动覆盖。

## BusinessEvent

当前正式事件目录：

| 事件类型 | 触发条件 | 默认 severity | 目标 |
| --- | --- | --- | --- |
| `user_daily_review.generated` | 复盘 `complete` 或 `empty` | `info` | `/reviews/{review_id}` |
| `user_daily_review.partial` | 规则复盘成功但存在不完整状态 | `notice` | `/reviews/{review_id}` |
| `user_daily_review.failed` | 规则结构或保存失败 | `important` | `/reviews` |
| `user_daily_review.became_stale` | 已有复盘输入变化 | `notice` | `/reviews/{review_id}` |
| `information.high_priority_detected` | 用户将与自选股 confirmed 关联的信息标为重要 | `notice` | `/information/{item_id}` |
| `information.verification_required` | 最新成功分析包含高优先级待核实项且关联自选股 | `notice` | `/information/{item_id}` |
| `ai_task.failed` | 信息分析最终失败 | `notice` | `/information/{item_id}` |

severity 由程序规则决定，AI 风险级别不得直接映射为系统通知严重度。

## Notification Orchestrator

链路：

```text
BusinessEvent -> NotificationOrchestrator -> Notification -> NotificationDelivery(in_app)
```

- 当前只真实支持 `in_app`。
- `Notification` 保存标题、摘要、事件类型、severity、状态、目标对象和 deep_link。
- 通知摘要不得包含完整私人正文、API Key、Session Token、Cookie、数据库密码或完整 Prompt。
- `NotificationDelivery` 当前只记录站内投递，通常立即为 `delivered`。
- `daily_digest` 当前表示不创建单条即时站内通知，相关材料进入每日复盘或摘要边界；当前不实现调度发送。
- `quiet_hours` 当前只保存，为未来外部推送使用；站内通知不延迟显示。

## 通知偏好

当前 `notification_preferences` 仅支持：

- channel：`in_app`
- frequency：`immediate`、`daily_digest`、`disabled`
- minimum_severity：`info`、`notice`、`important`

用户只能读取和修改自己的偏好。前端不得提交 `user_id` 或外部通道配置。

## 用户隔离和安全

- 每个复盘、事件、通知和偏好查询必须绑定当前 `user_id`。
- 仅知道 UUID 不得读取或修改其他用户数据。
- 管理员通过普通用户接口也不得读取其他用户私人复盘。
- 日志和审计只记录 ID、状态、错误码、数量和脱敏元数据。
- pytest 中全部 AI 调用使用 Mock，不调用真实用户 Provider。

## 未来扩展边界

- 自动定时生成每日复盘需要独立调度方案，不属于当前阶段。
- 微信、邮件、Web Push 和移动 Push 需要独立 ChannelAdapter、用户授权、模板、安全和退订方案。
- 全市场复盘、行情、板块热度和估值仍依赖真实数据供应商确认，不得从本阶段实现倒推出已完成。

## 第五阶段公告与资讯 Provider Spike 影响

- 用户每日复盘当前仍只聚合已属于当前用户、目标业务日期且可追溯的信息中心数据；第五阶段 Spike 不直接向复盘输入写入任何生产数据。
- 未来公告 Provider 输出进入信息中心后，复盘规则聚合必须保留来源 ID、原始链接、发布时间、采集时间、公告类型、证券关系和数据完整度。
- 自动资讯采集未冻结前，复盘材料继续以用户提交 URL、用户补充文本和已有受控抓取结果为主。
- PDF 或资讯正文解析失败时，复盘可引用公告元数据和来源链接，并在局限说明中标记“正文不可用”或“来源授权未确认”，不得由 AI 补造原文。
- Provider 同步失败可以产生业务事件和站内通知候选，但通知内容只应包含脱敏摘要、来源状态和跳转链接，不得包含完整第三方正文、PDF 全文、Cookie、API Key 或访问凭证。
