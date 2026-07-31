# 免费行情 Provider 验证记录

日期：2026-07-31

## 一、定位

本文件记录第九阶段免费行情开发源验证。免费源只用于本地开发、内部测试和五日试运行观察，不代表生产授权、交易所官方行情、实时行情、商业授权或投资建议来源。

## 二、当前 Provider 角色

| source_code | 当前角色 | authorization_status | production_enabled | is_official | 使用范围 |
| --- | --- | --- | --- | --- | --- |
| `BAOSTOCK` | SH/SZ 五日试运行主路由 | `unverified` | `false` | `false` | `local_development`, `internal_testing` |
| `AKSHARE_SINA_DAILY` | BJ 低频样本候选路由 | `unverified` | `false` | `false` | `local_development`, `internal_testing` |
| `AKSHARE_EASTMONEY` | 诊断和显式交叉验证来源 | `unverified` | `false` | `false` | `local_development`, `internal_testing` |
| `TUSHARE_PRO` | 可选开发候选 Provider | `unverified` | `false` | `false` | `local_development`, `internal_testing` |

第九阶段不再要求单个免费 Provider 同时覆盖 SH/SZ/BJ。页面和 API 允许不同股票使用不同 `source_code`；同一条快照不得混合多个来源字段。

## 三、字段与单位

`BAOSTOCK` 标准化：

- `open/high/low/close -> open/high/low/close`，单位为人民币元/股。
- `preclose -> pre_close`。
- `change` 由程序按 `close - pre_close` 计算。
- `pctChg -> pct_change`，内部为百分数数值。
- `volume -> volume`，内部单位为股。
- `amount -> amount`，内部单位为人民币元。
- `turn -> turnover_rate`，若原始值为小数比例则在归一化层转换为百分数数值。
- 估值和市值字段缺失保持 null，不由 AI 补齐。

`AKSHARE_SINA_DAILY` 标准化：

- 使用 `stock_zh_a_daily`，BJ 代码映射示例：`920000.BJ -> bj920000`。
- `date/open/high/low/close/volume/amount/turnover` 映射为内部快照字段。
- `pre_close` 取前一条实际交易日 `close`。
- `change` 和 `pct_change` 由程序计算。
- `volume` 和 `amount` 按当前接口返回单位保存，本轮样本使用 multiplier=1。
- `turnover_rate` 若为小数比例则转换为百分数数值。
- 估值和市值字段缺失保持 null，不由 AI 补齐。

`AKSHARE_EASTMONEY` 历史标准化口径保留用于诊断：成交量“手 -> 股”乘 100，成交额保持人民币元，估值和市值缺失保持 null。该来源不再作为默认持久化路由。

## 四、交易日和新鲜度

2026-07-31 上午执行本地验收时，交易日历目标优先验证 `2026-07-30`。Provider 最新可用日早于交易日历目标时标记 `source_lag`，不得把旧日期反向称为最近完整交易日。

建议状态：

- `current`：Provider 包含目标最近完整交易日。
- `source_lag`：Provider 最新日期早于交易日历目标。
- `unavailable`：请求失败或无数据。
- `partial`：仅部分必需字段存在。

## 五、真实 Smoke 结果

AKShare 升级：

- 升级前版本：`1.17.75`。
- 升级后版本：`1.18.74`。
- `AKSHARE_EASTMONEY` 对 `600519.SH`、`2026-07-30` dry-run 仍返回脱敏 `ProxyError`，记录为 `diagnostic_unavailable`。
- Eastmoney 结果不再阻塞 SH/SZ 五日试运行。

BaoStock SH/SZ：

- 样本：`600519.SH`、`300750.SZ`、`688981.SH`。
- 目标交易日：`2026-07-30`。
- dry-run：`pass`。
- 持久化：创建 3 条 `BAOSTOCK` 快照。
- 重复持久化：`created=0`，`unchanged=3`。
- 股票创建：无。
- AI、ResearchTask、BusinessEvent、Notification：无。

AKShare Sina BJ：

- 样本：`920000.BJ`。
- 目标交易日：`2026-07-30`。
- dry-run：`pass`。
- 最终 Provider：`AKSHARE_SINA_DAILY`。
- 持久化：创建 1 条 `AKSHARE_SINA_DAILY` 快照。
- 重复持久化：最终 `created=0`，`unchanged=1`。
- 腾讯 BJ 候选：未执行；Sina 已满足本轮 BJ 低频样本需求。
- 股票创建：无。
- AI、ResearchTask、BusinessEvent、Notification：无。

## 六、Checkpoint 9C 历史观察

9C 曾发现 `AKSHARE_EASTMONEY` 在 `stock_fetch` 阶段三次失败，脱敏错误类型为 `ProxyError`，清空进程代理变量后结果未改变。9C 同时修复了 `market_data_provider_smoke --persist` 的链路，使其统一为 `fetch -> normalize -> validate -> optional persist`，并确保网络请求发生在短数据库事务之前。

9D 采用分市场路由后，Eastmoney 的网络不稳定保留为诊断结果，不再作为第九阶段整体 P1 阻塞。

## 七、生产闸门

生产环境必须继续拒绝：

- `MARKET_DATA_AKSHARE_ENABLED=true`
- `MARKET_DATA_AKSHARE_SINA_ENABLED=true`
- `MARKET_DATA_BAOSTOCK_ENABLED=true`
- `MARKET_DATA_MOCK_ENABLED=true`
- 未授权真实行情网络或同步开关

正式上线仍需要完成行情来源授权、展示权、缓存、历史留存、再分发和稳定性确认。
