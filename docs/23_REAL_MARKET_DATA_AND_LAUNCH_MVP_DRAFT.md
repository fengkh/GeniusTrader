# 第七阶段：真实每日行情与可上线 MVP 草案

日期：2026-07-28

本文件记录第七阶段 Checkpoint A 和 Release Gate 的离线工程基线。当前没有真实 Tushare Token，也没有完成商业授权确认，因此本阶段只完成可离线实现，不执行真实行情联网 Smoke，不把任何 Provider 写成生产正式来源。

## 一、阶段拆分

Checkpoint A：无 Token 工程实现。

- 建立 `MarketDataProvider` 抽象、Tushare Adapter 骨架和测试用 Mock Provider。
- 新增行情数据迁移、同步服务、API、管理员页面和 CLI。
- 前端接入真实行情 API 契约；没有真实快照时展示 `unavailable`，不回退为 Mock 行情。
- 补充 BSE 公告 Provider 骨架和官方来源登记。
- 补充生产 Docker、运行手册、备份和恢复脚本。
- 新增生产发布门禁：`python -m app.cli.release_check` 只读检查生产配置、数据库迁移、管理员账户、Provider 授权、备份状态和私人测试版功能矩阵。
- 新增行情 Provider 技术 Smoke：`python -m app.cli.market_data_provider_smoke`。缺少 Token 时必须退出码 3；技术可达不代表生产授权。

Checkpoint B：真实 Provider 与授权验收。

- 用户本地配置真实 Token 后，才执行低频联网 Smoke。
- 联网 Smoke 只能证明技术可达，不能证明生产授权成立。
- 商业使用、登录用户展示、服务端缓存、历史留存、移动端展示和再分发必须获得书面确认后才能把来源标记为生产可用。

## 二、Provider 授权模型

`authorization_status` 取值：

- `unverified`
- `personal_development_only`
- `commercial_evaluation`
- `commercially_authorized`
- `prohibited`
- `expired`

`usage_scope` 取值：

- `local_development`
- `internal_testing`
- `private_beta`
- `public_display`
- `redistribution`
- `derived_data_display`

Tushare 当前默认登记为：

- `source_code=TUSHARE_PRO`
- `source_type=third_party_data_service`
- `authorization_status=unverified`
- `usage_scope=[local_development, internal_testing]`
- `production_enabled=false`

禁止将 Tushare 当前状态描述为交易所官方行情、已获商业授权、可公开再分发或实时行情。

## 三、行情数据边界

当前只设计收盘后日级快照和最近完整交易日能力。页面可以展示最新可用快照、来源、交易日、获取时间、授权状态和新鲜度状态，但不承诺实时行情、盘口、五档、自动分钟刷新、全市场行情宽度或估值数据。

内部单位固定为：

- 价格：人民币元/股。
- `pct_change`：百分比数值，例如 `1.25` 表示 `1.25%`。
- `volume`：股。
- `amount`：人民币元。
- `market_value`：人民币元。
- `trade_date`：Asia/Shanghai 市场交易日。

Provider 原始单位必须在 normalization 层统一转换，前端不得自行猜测手、股、千元或万元。

## 四、数据失败降级

无 Token、Provider 关闭、真实网络关闭、授权不足、来源结构变化、网络失败、数据不足和部分字段缺失都必须有明确状态。失败不得清空历史快照，不得创建虚假股票，不得自动生成 AI 解释，不得产生交易建议。

无经授权真实行情时，前端必须展示“暂无经授权的真实行情数据。”或等价 `unavailable` 状态，不得展示模拟价格、随机涨跌幅、虚假分时图或虚假 K 线。

## 五、前端页面接入范围

- `/today`：接入行情状态和当前用户自选股日级快照汇总；无数据时展示 unavailable、授权待确认和同步状态。
- `/watchlist`：接入当前用户自选股与行情快照；移动端保持紧凑扫描列表。
- `/watchlist/[stockId]`：接入单股日级快照；无真实历史图表数据时隐藏或展示未开放状态。
- `/settings/market-data`：管理员可查看数据源、Provider 状态、最近同步和手动同步入口。
- `/market-review/[date]`：生产发布收口中安全关闭，不展示早期 Mock 全市场复盘、市场宽度、估值区间或模拟行情数字。

这些页面不得把证券主数据误写为行情，不得在生产构建中展示 Mock 行情。

## 六、Release Gate 行情关闭策略

生产默认配置必须保持：

- `MARKET_DATA_PROVIDER_ENABLED=false`
- `MARKET_DATA_SYNC_ENABLED=false`
- `MARKET_DATA_REAL_NETWORK_ENABLED=false`
- `MARKET_DATA_TUSHARE_ENABLED=false`
- `MARKET_DATA_MOCK_ENABLED=false`
- `MARKET_DATA_TUSHARE_AUTHORIZATION_STATUS=unverified`

在没有书面商业授权前，即使本地拥有个人 Token，也不得把行情 Provider 标记为 `production_enabled=true`，不得持久化生产行情，不得公开展示快照、K 线、分时、量化指标或估值数据。行情功能关闭不得影响登录、自选股、官方公告、信息中心、用户自带 AI、每日复盘和站内通知。

## 七、官方公告上线策略

生产首版只允许 CNINFO 和 SSE_DISCLOSURE 由管理员或部署配置显式启用。BSE_DISCLOSURE 继续保留为候选来源，真实 Smoke、授权、稳定列表、PDF 策略和字段覆盖完成前默认关闭。

公告同步只能通过现有幂等 CLI 或管理员手动入口低频触发；不得在 Web 进程中启动无限循环，不得自动 AI 分析、自动导入候选或自动通知。候选仍需用户审核后进入 InformationItem。

## 八、仍待确认

- Tushare 或其他行情 Provider 的生产授权、展示、缓存、历史留存和再分发权限。
- SH/SZ/BJ 真实行情覆盖范围、字段可用性、单位口径和延迟。
- 分时、K 线、指数、板块、财务和估值数据的正式来源。
- 真实 Provider 联网 Smoke 和上线前授权冻结。

## 九、第八阶段研究工作台边界

- 模块化研究工作台不得把证券主数据、自选股、公告或研究事项包装为真实行情；没有经授权真实行情快照时，今日页、自选股扫描器和个股研究档案均显示 `unavailable`。
- `/today/overview`、`/watchlist/scanner` 和 `/stocks/{stock_id}/research-dossier` 可以在行情关闭状态下继续提供研究待办、官方信息、研究事项、观察条件和复盘状态。
- 行情缺失不得阻塞公告候选审核、信息分析、研究事项创建、观察条件验证、每日复盘或站内通知。

## 2026-07-30 免费行情双源验证修订

第九阶段真实行情方案调整为：

- `BAOSTOCK`：9D 起作为 SH/SZ 五日试运行主路由，仅低频日线快照，非官方、非实时、未商业授权。
- `AKSHARE_SINA_DAILY`：9D 起作为 BJ 低频样本候选路由，真实 dry-run 成功后才允许有限持久化。
- `AKSHARE_EASTMONEY`：降级为诊断和显式交叉验证来源，不再作为默认持久化路由。
- `TUSHARE_PRO`：保留为可选 Provider，缺少 Token 不再阻塞免费行情验证。

AKShare `stock_zh_a_hist` 字段标准化口径：`日期 -> trade_date`，`股票代码 -> provider_symbol`，`开盘/收盘/最高/最低 -> open/close/high/low`，`成交量 -> volume` 且原始单位为“手”、内部单位为“股”、乘数 100，`成交额 -> amount` 且原始和内部单位均为人民币元，`涨跌幅 -> pct_change`，`涨跌额 -> change`，`换手率 -> turnover_rate`。`total_market_value`、`circulating_market_value`、`pe_ttm`、`pb` 当前保持 null 并进入缺失字段，不抓取额外不稳定接口，不由 AI 补齐。

2026-07-30 本地真实 Smoke 结果：AKShare dry-run 对 `600519.SH`、`300750.SZ`、`688981.SH`、`920000.BJ` 在 `2026-07-29` 返回 `pass`，四只股票均关联现有 `stock.id`，未创建股票。后续有限持久化连续返回 `network_error`，未产生 `AKSHARE_EASTMONEY` 快照；当时页面展示已入库真实快照仍为 P1 待补验。

2026-07-31 Checkpoint 9C 修复：`market_data_provider_smoke --persist` 改为复用同一次 AKShare fetch/normalize/validate 结果，网络请求完成后才进入短数据库写入阶段，避免 persist 二次联网。新增脱敏阶段日志和最多三次网络重试。当天本地真实 dry-run 在 `stock_fetch` 阶段仍三次返回脱敏 `ProxyError`，单命令清空代理变量后未改变，因此 9C 当时的真实持久化和页面快照验收仍保持 P1 待补验。

2026-07-31 Checkpoint 9D 收口：目标交易日按交易日历优先验证 `2026-07-30`；Provider 只返回 `2026-07-29` 时标记 `source_lag`，不得把旧日期称为最近完整交易日。`BAOSTOCK` 对 `600519.SH`、`300750.SZ`、`688981.SH` 的 dry-run、有限持久化和重复幂等通过；`AKSHARE_SINA_DAILY` 对 `920000.BJ` 的 dry-run、有限持久化和重复幂等通过；`AKSHARE_EASTMONEY` 升级后仍为脱敏 `ProxyError`，记录为诊断不可用。第九阶段可以进入 SH/SZ 五日试运行，BJ 可作为本地低频样本纳入试运行观察，但不得宣称沪深京生产覆盖。
- AI 分析、每日复盘和研究事项不得生成、补全或覆盖价格、成交量、成交额、财务、估值、K 线、分时或涨跌幅数字。
- 完成 9D 分市场低频真实 Smoke 后，本阶段仍不新增行情图表、实时行情、全市场行情复盘、估值中心或生产行情展示。

## 十、第九阶段 V0.3 日常真实数据试点补充

- 行情同步范围收窄为当前用户自选股或显式指定的既有 `stock_id` 列表；没有范围时不得默认同步全部 A 股证券目录。
- Tushare 仍是开发候选 Provider。未检测到本地 `.local/market-data.env` Token 时，真实联网 Smoke 标记为 `blocked_by_local_credential`，不阻塞离线工程验收，也不得伪造联网成功。
- 技术 Smoke 默认使用最近完整交易日和四只样本股：`600519.SH`、`300750.SZ`、`688981.SH`、`920000.BJ`；输出只允许包含脱敏状态、字段覆盖、单位说明、延迟和错误摘要，不输出 Token 或完整原始响应。
- `/today`、`/watchlist` 和 `/watchlist/[stockId]` 可以展示已入库真实日级快照、缺失字段、覆盖数量、涨跌分布、来源和交易日；`partial` 表示已有部分快照字段但必须展示缺失项。
- `/watchlist` 的行情筛选和排序只基于后端已入库日级快照；无快照不得按 `0` 价格或 `0%` 涨跌参与排序。
- 个股详情真实快照区不展示分时、K 线、盘口、估值模型或 AI 推测数字；PE/PB 如来自 Provider 字段，只能作为原始快照字段展示，不得生成估值结论。
- 公告同步 CLI 可以低频 dry-run，但 dry-run 不创建公告记录、候选、信息条目、AI 任务、BusinessEvent 或 Notification。
- 日常试点报告只保存在 Git 忽略的 `tmp/pilot/`，模板见 `docs/templates/daily-pilot-report.example.md`。
