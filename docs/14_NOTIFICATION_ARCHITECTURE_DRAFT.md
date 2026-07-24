# 通知架构草案

本文定义 GeniusTrader 第一版站内通知和未来外部通知通道的产品与领域边界。第四阶段已实现真实 `in_app` 站内通知、偏好和投递记录；仍不创建外部通道接口、SDK、后台调度或真实微信公众号接入。

## 架构链路

```text
Business module
  -> BusinessEvent
  -> NotificationOrchestrator
  -> Notification
  -> NotificationPreference
  -> NotificationDelivery
  -> ChannelAdapter
```

- 业务模块只产生业务事件，不直接发送通知。
- 通知编排器负责偏好判断、严重度判断、摘要策略、去重、免打扰和通道选择。
- `Notification` 是用户可见的站内通知。
- `NotificationDelivery` 是某一通道的投递尝试记录。
- `ChannelAdapter` 是未来外部通道适配层。

## 通道范围

| 通道 | 当前状态 | 说明 |
| --- | --- | --- |
| `in_app` | 第四阶段真实实现 | 站内通知中心、顶部铃铛未读数和站内通知偏好 |
| `wechat_official_account` | 仅预留和 Mock 状态 | 不实现 OAuth、扫码、SDK、模板消息或 API 调用 |
| `email` | 预留 | 不属于当前 MVP 接入能力 |
| `web_push` | 预留 | 不属于当前 MVP 接入能力 |
| `mobile_push` | 预留 | 不属于当前 MVP 接入能力 |

每日复盘、用户复盘、估值、公告或行情模块不得直接调用微信公众号 API。微信公众号失败不得影响全市场复盘、用户复盘、行情计算、估值计算、公告展示或站内通知。

## 当前正式业务事件目录

| 事件类型 | 触发模块 | 默认严重度 | 默认频率 | 目标页面 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| `user_daily_review.generated` | 用户每日复盘 | info | immediate | `/reviews/{review_id}` | 已实现 |
| `user_daily_review.partial` | 用户每日复盘 | notice | immediate | `/reviews/{review_id}` | 已实现 |
| `user_daily_review.failed` | 用户每日复盘 | important | immediate | `/reviews` | 错误码和事件目录保留，规则保存失败才触发 |
| `user_daily_review.became_stale` | 用户每日复盘 | notice | immediate | `/reviews/{review_id}` | 已实现 |
| `information.high_priority_detected` | 信息中心 | notice | immediate | `/information/{item_id}` | 已实现 |
| `information.verification_required` | 信息中心 | notice | daily_digest | `/information/{item_id}` | 已实现事件；默认不创建单条即时通知 |
| `ai_task.failed` | 信息中心 AI 分析 | notice | immediate | `/information/{item_id}` | 已实现 |

第四阶段真实 severity 仅使用 `info`、`notice` 和 `important`。严重度由程序规则决定，AI 不能提升严重度。

## 未来业务事件目录草案

| 事件类型 | 触发模块 | 默认严重度 | 站内默认 | 微信允许 | 默认频率 | 摘要收纳 | 去重规则 | 目标页面 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `market_daily_review.generated` | 全市场复盘 | notice | 是 | 是 | daily_digest | 是 | 同用户同日期一条 | `/market-review/[date]` |
| `market_daily_review.partial` | 全市场复盘 | notice | 是 | 是 | daily_digest | 是 | 同用户同日期一条 | `/market-review/[date]` |
| `market_daily_review.failed` | 全市场复盘 | important | 是 | 否 | immediate | 否 | 同用户同日期一条 | `/reviews` |
| `board.heat_state_changed` | 板块热度 | notice | 是 | 是 | daily_digest | 是 | 同板块同日期一条 | `/market-review/[date]` |
| `watch_candidate.updated` | 次日观察候选 | notice | 是 | 是 | daily_digest | 是 | 同日期候选摘要一条 | `/market-review/[date]` |
| `user_daily_review.generated` | 用户整体复盘 | notice | 是 | 是 | daily_digest | 是 | 同用户同日期一条 | `/today` |
| `stock_daily_review.generated` | 单股复盘 | info | 是 | 否 | daily_digest | 是 | 同用户同股票同日期一条 | `/watchlist/[stockId]` |
| `watchlist.abnormal_event.detected` | 自选股行情 | notice | 是 | 是 | daily_digest | 是 | 同用户同股票同规则同日期一条 | `/watchlist/[stockId]` |
| `announcement.major_collected` | 公告资讯 | important | 是 | 是 | immediate | 否 | 同公告多 Provider 合并一条 | `/watchlist/[stockId]` |
| `info.item_needs_verification` | 信息中心 | notice | 是 | 否 | daily_digest | 是 | 同链接或同来源摘要一条 | `/information` |
| `observation.condition_verified` | 观察条件 | important | 是 | 是 | immediate | 否 | 同观察条件同验证日一条 | `/today` |
| `valuation.updated` | 估值中心 | info | 是 | 否 | daily_digest | 是 | 同用户同股票同日期一条 | `/watchlist/[stockId]` |
| `valuation.unavailable` | 估值中心 | notice | 是 | 否 | daily_digest | 是 | 同用户同股票同日期一条 | `/watchlist/[stockId]` |
| `system.data_source_degraded` | 系统 | critical | 管理员 | 否 | immediate | 否 | 同数据源同时间窗一条 | `/settings` |
| `system.account_security` | 系统 | critical | 是 | 是 | immediate | 否 | 同账户同事件一条 | `/settings` |

未来草案中可能讨论 `critical`，但第四阶段真实实现不使用 `critical`。普通股票涨跌不属于严重通知。严重度由程序决定，AI 不能提升严重度。

## 默认通知策略

- 站内通知默认开启。
- 微信默认关闭，且当前不接入；未来必须完成绑定和关注后才允许发送。
- `daily_digest` 当前表示不创建单条即时站内通知，不代表已实现定时摘要。
- 普通资讯、普通异动、普通板块和普通估值更新进入摘要。
- 重大公告立即通知。
- 停牌、复牌等重要状态变化立即通知。
- 高严重度观察条件立即通知。
- 普通估值更新不立即通知；估值变为不可用进入摘要。
- 数据源降级默认仅管理员可见。
- 用户可以关闭非必要通知。
- 免打扰时间当前只保存，为未来外部推送预留；站内通知不延后显示。

## 通知状态

- `unread`：未读。
- `read`：已读。
- `archived`：已归档。
- `expired`：已过期。
- 数据源降级、AI 摘要失败和微信失败是页面或未来投递状态，不属于第四阶段 `notifications.status` 的正式枚举。

## 未来微信绑定流程

该流程仅作为未来方案，不在当前 Mock 原型中实现。

1. 用户已登录。
2. 用户进入设置中的通知设置。
3. 用户发起绑定。
4. 系统创建一次性 `state`。
5. 用户扫码或授权。
6. 回调到后端。
7. 后端校验 `state`、当前用户和回调来源。
8. 后端获取 OpenID，必要时获取 UnionID。
9. 写入 `UserExternalIdentity`。
10. 用户确认通知偏好。
11. 绑定完成。

OpenID 不能作为系统用户主键；微信字段不得进入 `users` 表；同一用户可有多个通道身份；`provider_account_id + provider_user_id` 应唯一；UnionID 可选。

## 用户每日复盘当前通知流

1. 用户生成用户私有信息每日复盘。
2. 服务端保存复盘版本和状态。
3. 产生 `user_daily_review.generated`。
4. 创建站内通知。
5. 读取通知偏好。
6. 创建 `in_app` 投递记录并标记 `delivered`。
7. 用户点击后进入 `/reviews/{review_id}`。
8. 微信通道当前不发送。

微信摘要可以包含计数、事件名称、业务日期和目标页面提示；不得包含完整自选股清单、API Key、敏感账户信息、交易动作、仓位、收益保证、强推荐或保证性表述。

## 幂等与去重

默认幂等键字段：

- `event_type`
- `user_id`
- `subject_id`
- `channel`
- `template_version`
- `business_date`

同一公告来自多个 Provider 时，对同一用户合并为一条通知。普通资讯、普通异动、普通板块和普通估值更新按用户和日期进入摘要。重试同一投递记录不得创建重复通知。

## 失败处理

- 微信失败时，站内通知仍然存在。
- 未绑定时外部通道跳过。
- 用户关闭通知时外部通道跳过。
- 取消关注或授权失效时外部通道阻塞。
- 模板无效时投递失败并记录错误代码。
- 瞬时网络错误允许有限重试。
- 参数错误不得无限重试。
- 达到最大重试后保留失败状态。
- 通知失败不得阻断复盘、估值、行情和公告。
- AI 失败时使用规则模板摘要。

## 安全要求

- AppSecret、Token、EncodingAESKey 和模板密钥只能来自 Secrets 或环境变量，不得进入 Git、日志、前端或 Mock 数据。
- OpenID/UnionID 只作为外部身份字段。
- 日志必须脱敏。
- 通知必须校验用户隔离。
- 深链不得包含 userId、OpenID、Token、API Key 或可复用凭证。
- 用户可解绑或撤销外部通知授权。
- 删除账户或个人数据时必须处理外部身份、通知和投递记录。
- 外部投递记录需要保留期限和自动清理策略。
- 不得进行未经授权的营销发送。
- 微信消息必须最小披露。
