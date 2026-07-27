# A 股证券主数据与真实自选股闭环草案

日期：2026-07-26

本文记录第六阶段前置子阶段 6A 的产品和技术基线。6A 的目标是在继续公告真实 Smoke 之前，先建立可追溯的 A 股证券主数据、本地股票搜索和真实用户自选股管理闭环。

本阶段页面必须显示：

```text
证券基本信息来自证券目录同步；行情、财务、估值和技术指标仍未接入真实数据。
```

## 一、阶段定位

证券主数据是股票身份目录，不是行情、财务、估值或投资建议。它为自选股、公告匹配、信息关联和后续复盘提供稳定的 `stock.id`、`symbol`、交易所、板块、上市状态、来源和同步时间。

完成真实证券目录前，不继续公告真实网络 Smoke、公告 PDF 提取、公告导入或公告 AI 产品验收。

## 二、证券范围

MVP 默认仅纳入上交所主板 A 股、科创板、深交所主板 A 股、创业板和北交所普通股票。

暂不纳入 B 股、ETF、LOF、REITs、债券、可转债、期权、指数、港股、美股和新三板非北交所挂牌证券。数据模型可以保留 `security_type`，但普通搜索默认只返回 A 股普通股票。

## 三、数据来源原则

官方来源优先级为上交所、深交所、北交所公开证券目录。BaoStock 只能作为开发环境补充或交叉核验来源，不得标记为官方来源，也不得替代正式授权判断。

SSE、SZSE 和 BSE 当前均为候选证券目录来源，不代表 V1 已冻结生产 Provider。真实网络验证必须记录 `pass`、`partial`、`data_insufficient`、`network_error`、`access_denied`、`source_changed` 等状态；来源失败不得清空既有 `stocks`。

## 四、SecurityMasterProvider

后端使用 `SecurityMasterProvider` 抽象隔离来源差异，至少包含：

- `source_code`
- `capabilities()`
- `health_check()`
- `list_securities(query)`
- `normalize(raw_record)`
- `build_next_cursor(result)`

`SecurityMasterQuery` 包含交易所、证券类型、上市状态、游标和最大记录数。`SecurityMasterRecord` 统一输出 `symbol`、`code`、`exchange`、`market`、`board`、`security_type`、`short_name`、`full_name`、上市状态、上市日期、退市日期、历史简称、哈希、采集时间、完整度和缺失字段。

Provider 不传播原始字段到业务层，不保存完整第三方响应，不使用 Cookie、代理、浏览器自动化或验证码绕过。

## 五、stocks 主数据

`stocks` 保留稳定 `id`，并扩展为证券主数据表。核心字段包括：

- `code`
- `symbol`
- `exchange`
- `market`
- `board`
- `security_type`
- `short_name`
- `full_name`
- `english_name`
- `listing_status`
- `listed_at`
- `delisted_at`
- `aliases`
- `pinyin`
- `pinyin_initials`
- `source_code`
- `source_record_id`
- `source_updated_at`
- `last_synced_at`
- `data_completeness`
- `is_searchable`
- `created_at`
- `updated_at`

`symbol` 全局唯一，格式如 `600519.SH`、`000001.SZ`、`688981.SH`、`835185.BJ`。`exchange + code` 也必须唯一。股票简称不能作为唯一标识。

## 六、交易所、板块和上市状态

交易所统一使用 `SH`、`SZ`、`BJ`。板块至少支持 `main_board`、`star_board`、`chinext`、`bse` 和 `unknown`。

上市状态至少支持 `pending_listing`、`active`、`suspended`、`risk_warning`、`delisting_period`、`delisted` 和 `unknown`。默认搜索只返回 `active`、`suspended`、`risk_warning` 且 `is_searchable=true` 的 A 股普通股票。

ST 和 *ST 真实简称应保留，不得被自动清洗为普通简称。

## 七、改名、历史简称和退市

股票改名不得创建新的 `stock.id`。同步到新简称时，旧简称进入 `aliases`。退市股票保留主数据和历史引用，不删除用户历史自选股、公告、资讯、复盘和笔记。

“是否显示已退市股票”仍只是用户界面过滤偏好，不代表完整停牌、退市和名称变更生命周期口径已经冻结。

## 八、开发种子迁移

现有开发种子记录必须保留 `stock.id`，并通过 legacy `data_source=development_seed` 保留原始迁移来源。真实来源同步相同 `symbol` 时更新原记录的当前主数据字段和 `source_code`，不重复创建 `600519.SH`、`688981.SH`、`000001.SZ` 或 `300750.SZ`。

仍未被真实来源覆盖的 seed 不能显示为“真实目录已同步”。

## 九、同步实体

`security_master_sync_runs` 记录管理员人工同步运行，包含触发用户、来源、交易所、状态、请求数、接收数、新增数、更新数、不变数、失败数、开始和结束时间、错误码、错误摘要和脱敏指标。

`security_source_records` 记录来源侧证券记录，包含股票、来源代码、来源证券 ID、来源 symbol、来源名称、元数据哈希、首次和最后发现时间、来源状态。

同步运行不保存完整第三方响应、Cookie、用户自选股备注或密钥。

## 十、管理员人工同步

证券目录同步仅管理员可触发，必须通过 CSRF 校验，并仅允许 development 环境在显式开关开启后访问真实网络。production 默认阻止真实同步。

同一来源同时最多一个 `running`。同步请求在数据库事务外访问来源，标准化后再 upsert `stocks` 和 `security_source_records`。部分失败记录为 `partial` 或具体失败状态；失败不得清空既有 `stocks`，不得自动修改用户自选股，不得自动触发公告同步、AI、BusinessEvent 或通知。

不设置自动证券目录调度。

## 十一、本地股票搜索

`GET /api/v1/stocks/search` 只查询本地 `stocks`，用户搜索时不访问第三方来源。支持 6 位代码、完整 `symbol`、股票简称、公司全称、拼音、拼音首字母和历史简称。

搜索排序优先精确代码、完整 `symbol` 和正常上市状态。默认最多返回 20 条，支持稳定分页。`q` 为空时不返回全量数千条股票。

`GET /api/v1/stocks/{stock_id}` 返回本地证券基本信息，不返回行情、财务、估值、K 线或 AI 结果。

## 十二、真实自选股

添加自选股时客户端只能提交 `stock_id`。`stock_id` 必须存在且 `is_searchable=true`，用户不得手写不存在的股票代码或名称来创建股票。

同一用户同一股票唯一，重复添加幂等。每位用户最多 200 只自选股。用户可以维护个人分组、用户标签和关注原因，这些用户字段不修改证券主数据。

用户隔离必须严格生效，管理员通过普通用户 API 也不能读取或修改其他用户自选股。

## 十三、页面承载

`/watchlist` 接真实 API，展示股票代码、简称、交易所、板块、上市状态、来源、分组、标签、关注原因和添加时间。页面提供本地股票搜索、添加、编辑、移除和目录不足提示。

`/settings/security-master` 仅管理员可见，展示交易所和板块数量、active 数量、development_seed 数量、最近同步、来源、数据缺口和手动同步入口。

移动端自选股以紧凑扫描列表呈现；桌面端以紧凑表格或行列表呈现。

## 十四、公告匹配衔接

公告股票匹配必须读取真实 `stocks`，不得依赖硬编码 4 只开发种子。CNINFO 或其他公告来源中的股票代码只能匹配已有 `stock.id`；不得创建虚假股票。非当前用户自选股不生成用户候选。

当前阶段仍不继续公告真实 Smoke，待证券目录和真实自选股闭环验收后再恢复。

## 十五、测试和验收

自动测试使用 fixture 或 Mock Provider，不访问真实网络。测试覆盖 Provider 样本标准化、upsert、seed 覆盖、网络失败不清空、搜索、空搜索限制、不可搜索股票拒绝、重复自选股幂等、200 只上限、用户隔离、管理员权限、CSRF 和 production 阻止同步。

真实人工验收应小样本验证 SSE、SZSE、BSE，记录来源状态、sync run 统计、证券总数、交易所数量、active 数量、development_seed 数量、seed 覆盖结果、搜索结果和自选股闭环。网络失败必须作为真实结果记录，不得用代理、Cookie、验证码绕过或浏览器自动化强行获取。
## 2026-07-26 6A.1 收口结果

- 当前开发库证券目录同步结果：总计 6136 条，SH 2009 条，SZ 3879 条，BJ 248 条；active 5929 条；`development_seed` 当前 source 数为 0，legacy `data_source=development_seed` 覆盖计数为 4。
- `SSE_SECURITY_MASTER` 通过上交所官方分页接口读取主板与科创板，真实验证 2009 条，包含 `600519.SH` 和 `688981.SH`。Provider 未冻结为生产正式来源。
- `SZSE_SECURITY_MASTER` 仍返回 HTTP 500 / `network_error`，未写入股票，官方深市目录来源仍待真实数据开发前继续确认。
- `BSE_SECURITY_MASTER` 改用北交所官方新旧代码对照表，真实验证 248 条；当前代码使用 920 前缀 `.BJ`，旧代码进入 alias / previous symbol，不为新旧代码创建两个股票。
- `BAOSTOCK_DEVELOPMENT_FALLBACK` 已作为可选依赖和开发补充来源验证，最近交易日为 2026-07-24，仅 development 环境显式启用；本次用于补足 SZ 本地目录，包含 `000001.SZ` 和 `300750.SZ`，不得描述为深交所官方来源。
- 来源优先级确定为：官方交易所目录 > 经过验证的官方公开页面 > `BAOSTOCK_DEVELOPMENT_FALLBACK` > `development_seed`。低优先级来源只补缺和记录冲突，不覆盖高优先级官方字段。
- 同步完整度门槛已加入：SSE 必须覆盖主板、科创板及探针；SZ/开发补充必须覆盖主板、创业板及探针；BSE 必须有 BJ 记录和 920 当前代码。未达门槛时 run 不得为 `complete`。
- 本阶段仍未接入真实行情、财务、估值、K 线或实时价格。公告真实 Smoke 仍暂停，待真实自选股页面人工验收通过后再继续。
