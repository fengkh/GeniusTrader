# 第九阶段：真实数据接入与日常使用闭环 V0.3

日期：2026-07-30

## 一、阶段定位

第九阶段的目标是把“真实证券目录 + 当前用户真实自选股 + 官方公告候选 + 用户主动 AI 分析 + 每日复盘 + 站内通知”的日常路径，与经授权后的真实日级行情快照能力衔接起来。

本阶段不是全市场行情平台，也不是交易系统。它只验证当前用户自选股范围内的低频、日级、收盘后数据使用闭环。

## 二、明确范围

本阶段允许：

- 读取本地 `.local/market-data.env` 或进程环境中的行情 Provider 凭证状态，但不得打印 Token。
- 完善 Tushare 技术候选 Provider 的低频 Smoke、字段可用性、单位归一化和错误降级。
- 将行情同步范围限定为当前用户自选股或显式指定的既有股票 ID。
- 在 `/today`、`/watchlist`、`/watchlist/[stockId]` 和 `/settings/market-data` 展示真实日级快照状态。
- 在自选股扫描器中按已入库日级快照筛选上涨、下跌、有行情和无行情，并按涨跌幅、成交额、换手率等字段排序。
- 为公告同步 CLI 增加 watchlist 范围、低频、dry-run 和 max-records 边界。
- 输出本地每日试点报告模板，供人工记录日常验证结果。

本阶段不允许：

- 实现实时行情、分钟行情、分时图、盘口、Level-2 或自动分钟刷新。
- 实现全市场行情、全市场复盘、估值中心、财务估值模型或价格目标。
- 实现交易、荐股、买卖点、仓位、收益预测或跟单。
- 默认全市场同步行情或公告。
- 在无授权或无 Token 时使用 Mock、0 值或 AI 补造行情数字。
- 在自动测试中访问真实行情、真实公告或真实 AI 网络。

## 三、行情数据口径

- 只使用最近完整交易日或用户明确指定交易日的日级快照。
- 当前真实 Provider 仍是候选技术适配，不代表生产授权成立。
- Tushare Token 缺失时，Provider Smoke 必须返回可识别的 `not_configured` 状态，不得阻塞其他离线验收。
- 技术 Smoke 成功只代表技术可达，不代表商业授权、公开展示、缓存、历史留存或再分发权利成立。
- 内部单位保持统一：价格为元/股，涨跌幅为百分比数值，成交量为股，成交额和市值为人民币元。
- Provider 原始单位必须在归一化层转换，前端不得猜测单位。
- 每个快照必须展示来源、交易日、获取时间、数据完整度、新鲜度状态和缺失字段。

## 四、同步边界

行情同步默认不再扫描全市场。合法范围只有：

- 当前管理员或触发用户的自选股；
- 用户显式传入的既有 `stock_id` 列表。

没有范围时，同步必须拒绝并返回明确错误，不得读取全部 A 股目录作为默认同步池。

公告同步 CLI 默认也采用 watchlist 范围，并支持 `--dry-run` 与 `--max-records`。dry-run 可以记录 Provider 返回统计，但不得创建公告记录、候选、信息条目、AI 任务、BusinessEvent 或 Notification。

## 五、页面行为

### `/today`

- 展示业务日期、行情交易日、行情覆盖数量、暂无行情数量、上涨/下跌/持平分布。
- 优先股票列表可以展示真实日级收盘价、涨跌幅、成交额、换手率、来源和交易日。
- 行情缺失或部分失败时，公告、研究事项、复盘和通知入口继续可用。

### `/watchlist`

- 保持紧凑扫描列表。
- 新增行情筛选：全部行情、上涨、下跌、有行情、无行情。
- 新增排序：关注分、涨跌幅、成交额、换手率、公告候选、打开事项、最新信息、股票代码。
- “有行情”表示已有日级快照，`partial` 仍属于有行情但必须显示缺失字段。
- “无行情”不得把缺失快照显示为 0 元或 0%。

### `/watchlist/[stockId]`

- 在股票身份之后展示“真实日级行情快照”。
- 该区域只展示程序入库的单日快照，不展示分时、K 线、盘口、估值模型或 AI 推测数字。
- 缺失字段必须显式列出。
- AI 分析和复盘不得覆盖该区域的原始行情快照。

### `/settings/market-data`

- 管理员手动同步默认使用当前自选股范围。
- 同步结果展示收到、创建、更新、未变化和失败数量。
- 缺 Token、权限不足、真实网络关闭或 Provider 失败时，不得清空历史快照。

## 六、AI 与事实边界

- AI 不得生成、补全或修改行情、成交量、成交额、换手率、市值、PE/PB、涨跌幅或日期。
- AI 可以在复盘中解释程序已经提供的结构化数据，但必须标记为分析或判断。
- 没有行情快照时，复盘材料只能说明“暂无经授权的真实行情数据”，不得推测价格走势。

## 七、人工每日试点报告

每日试点报告保存在本地 `tmp/pilot/`，该目录必须被 Git 忽略。报告只记录脱敏统计、状态和人工结论，不保存 Token、Cookie、Session、完整第三方正文、完整 AI Prompt 或真实私密正文。

示例模板见：

- `docs/templates/daily-pilot-report.example.md`

## 八、待真实凭证补验

由于当前仓库未检测到 `.local/market-data.env` 中的真实 Tushare Token，本阶段真实联网 Smoke 标记为 `blocked_by_local_credential`。待用户在本地安全配置 Token 后，需要补验：

- 四只样本股：`600519.SH`、`300750.SZ`、`688981.SH`、`920000.BJ`。
- 最近完整交易日解析。
- 字段覆盖：OHLC、涨跌幅、成交量、成交额、换手率、市值、PE/PB。
- SH/SZ/BJ 覆盖差异。
- 权限不足、字段缺失、网络失败、限流和源结构变化。
- 技术 Smoke 成功后仍需单独完成生产授权确认。

## 九、验收结论口径

第九阶段可以在“无真实 Token 条件下完成离线工程与产品边界验收”，但不得写成“真实 Provider 产品验收完成”。真实 Provider 可达性、授权、字段覆盖和生产上线仍待补验。

## 十、2026-07-31 免费行情分市场路由调整

产品决策更新：Tushare Token 不再作为第九阶段真实行情联网 Smoke 的前置条件。第九阶段五日试运行不再要求单一免费 Provider 覆盖 SH/SZ/BJ，改为按市场显式路由：SH/SZ 使用 `BAOSTOCK`，BJ 使用 `AKSHARE_SINA_DAILY`，`AKSHARE_EASTMONEY` 降级为诊断和显式交叉验证来源；Tushare 保留为可选 Provider。

Provider 状态：

- `BAOSTOCK`：SH/SZ 五日试运行主路由；`authorization_status=unverified`，`production_enabled=false`，`is_official=false`，仅 `local_development` 和 `internal_testing`。
- `AKSHARE_SINA_DAILY`：BJ 低频样本候选路由；`authorization_status=unverified`，`production_enabled=false`，`is_official=false`，仅 `local_development` 和 `internal_testing`。
- `AKSHARE_EASTMONEY`：诊断和显式交叉验证来源；`authorization_status=unverified`，`production_enabled=false`，`is_official=false`，仅 `local_development` 和 `internal_testing`。
- `TUSHARE_PRO`：继续 `authorization_status=unverified`，`production_enabled=false`，缺 Token 不阻塞免费行情验证。

真实执行记录：

- 已将后端 venv 中 `akshare` 从 `1.17.75` 升级到 `1.18.74`，并保留 `baostock==0.9.3`。
- 本地 stocks 已有 `600519.SH`、`300750.SZ`、`688981.SH` 和 BJ 样本 `920000.BJ`，均未创建新股票。
- 目标交易日按交易日历优先验证 `2026-07-30`；Provider 最新可用日早于目标日时标记 `source_lag`，不得把旧日期称为最近完整交易日。
- `AKSHARE_EASTMONEY` 升级后对 `600519.SH` 的 `2026-07-30` dry-run 仍返回脱敏 `ProxyError`，记录为 `diagnostic_unavailable`，不阻塞 SH/SZ 五日试运行。
- `BAOSTOCK` 对 `600519.SH`、`300750.SZ`、`688981.SH` 的 `2026-07-30` dry-run、有限持久化和重复幂等通过，source_code 为 `BAOSTOCK`。
- `AKSHARE_SINA_DAILY` 对 `920000.BJ` 的 `2026-07-30` dry-run、有限持久化和重复幂等通过，source_code 为 `AKSHARE_SINA_DAILY`。
- 每条快照保存实际 `source_code`，同一业务日期下可存在不同来源；单条快照不得混合多个 Provider 字段。

不得把上述技术验证写成生产授权完成，也不得把 AKShare/Eastmoney/Sina/BaoStock 描述为官方、实时或商业授权行情。第九阶段可进入 SH/SZ 五日试运行；BJ 可作为本地低频样本纳入观察，但不能宣称沪深京生产覆盖。
