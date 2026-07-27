# 外部信息源与公告候选收件箱试点草案

日期：2026-07-24

本文记录第六阶段“外部信息源基础架构与上市公司公告候选收件箱试点”的产品和技术基线。当前能力仅为实验性试点，不代表任何数据源已经成为 V1 正式生产 Provider。

## 6A 前置补充：证券主数据与真实自选股

2026-07-26 真实 CNINFO 低频 Smoke 返回 `network_error`，未产生真实候选、未导入 InformationItem，也未触发 AI 或通知。后续公告真实 Smoke、候选 PDF、公告导入和公告 AI 闭环补验，必须等待 A 股证券主数据与真实自选股闭环完成后再继续。

公告股票匹配必须读取真实 `stocks` 和当前用户自选股，不得依赖硬编码 4 只开发种子，不得在匹配失败时创建虚假股票。证券目录同步本身不得自动触发公告同步、AI 分析、BusinessEvent 或 Notification。

所有公告相关页面必须显示：

```text
当前公告同步功能处于实验阶段，数据来源、完整性、及时性、稳定性及使用授权尚未最终确认。
```

公告候选详情页必须显示：

```text
公告内容来自公开来源。当前功能处于实验阶段，系统不保证数据完整性、及时性或长期可用性。原文、版权及使用权限以来源网站及相关授权为准。
```

## 一、阶段定位

本阶段建立两层能力：

1. 外部信息源注册基础设施：记录来源身份、类别、权威层级、地域、访问方式、授权状态、再展示状态、商业使用状态、健康状态和实验状态。
2. 上市公司公告候选收件箱试点：仅针对当前用户自选股，由用户手动发起同步、用户人工审核、用户主动导入为正式 InformationItem。

本阶段不实现政府政策自动采集、国际机构自动同步、财经媒体自动采集、后台定时任务、全市场公告库、自动 AI 分析、自动通知或自动每日复盘。

## 二、总体链路

```text
当前用户自选股
  -> 用户手动发起公告同步
  -> 实验性 AnnouncementProvider
  -> 公告元数据标准化
  -> 去重与股票匹配
  -> 用户私有公告候选
  -> 用户查看、忽略、恢复或导入
  -> 按需提取公告 PDF 正文
  -> 创建正式 InformationItem
  -> 用户主动调用已有 AI 分析
  -> 进入已有每日复盘与站内通知体系
```

公告候选不是复盘输入。只有用户导入后的 InformationItem 才能进入信息中心、AI 分析和每日复盘材料。

## 三、外部来源注册表

正式表：`external_sources`

核心字段：

- `source_code`
- `display_name`
- `publisher_name`
- `source_category`
- `authority_level`
- `source_tier`
- `jurisdiction`
- `country_code`
- `region_code`
- `city_code`
- `official_domain`
- `access_mode`
- `content_language`
- `provider_adapter`
- `authorization_status`
- `redistribution_status`
- `commercial_use_status`
- `legal_review_status`
- `health_status`
- `enabled`
- `experimental`
- `limitations`

`source_tier` 是系统对来源类型和权威层级的分层，不等于具体事件真实，也不等于投资影响判断。AI 不得仅因 S 级来源推导利好、利空、情绪方向或交易结论。

## 四、来源分类枚举

`source_category` 至少支持：

- `exchange_announcement`
- `company_disclosure`
- `government_policy`
- `government_notice`
- `regulator_release`
- `regulator_enforcement`
- `central_bank_release`
- `statistics_release`
- `international_official`
- `multilateral_organization`
- `licensed_financial_media`
- `public_financial_media`
- `company_news`
- `rss`
- `public_web`
- `user_submitted`
- `social_media`
- `unknown`

`authority_level` 至少支持：

- `exchange`
- `company`
- `central_government`
- `ministry`
- `national_regulator`
- `provincial_government`
- `provincial_department`
- `municipal_government`
- `municipal_department`
- `international_regulator`
- `central_bank`
- `multilateral_organization`
- `licensed_media`
- `public_media`
- `user`
- `social`
- `unknown`

`source_tier` 支持：

- `s`：交易所、监管机构、政府正式文件、公司正式公告等原始权威来源。
- `a`：国际官方机构、中央银行、多边组织。
- `b`：经过授权接入的专业财经媒体。
- `c`：普通财经媒体、上市公司官网新闻。
- `d`：自媒体、社交平台、用户提交线索。
- `unknown`：无法确认来源。

## 五、授权和访问状态

`access_mode` 至少支持：

- `official_api`
- `public_endpoint`
- `rss`
- `public_html`
- `licensed_api`
- `manual_url`
- `manual_text`
- `unavailable`

授权类状态：

- `authorization_status`：`testing_only`、`unclear`、`review_required`、`approved`、`prohibited`
- `redistribution_status`：`unclear`、`metadata_only`、`excerpt_allowed`、`full_text_allowed`、`prohibited`
- `commercial_use_status`：`unclear`、`review_required`、`approved`、`prohibited`
- `legal_review_status`：`not_started`、`pending`、`reviewed`、`blocked`

默认不得写成 `approved`。`prohibited` 或 `blocked` 来源不得进行真实同步。公开可访问不等于允许商业使用、长期留存、全文解析、AI 摘要或再展示。

## 六、初始注册来源

本阶段仅在迁移中幂等注册两个实验来源：

CNINFO：

- `source_category=exchange_announcement`
- `authority_level=exchange`
- `source_tier=s`
- `access_mode=public_endpoint`
- `provider_adapter=cninfo`
- `enabled=false`
- `experimental=true`
- `authorization_status=review_required`
- `redistribution_status=unclear`
- `commercial_use_status=unclear`
- `legal_review_status=pending`

SSE_DISCLOSURE：

- `source_category=exchange_announcement`
- `authority_level=exchange`
- `source_tier=s`
- `access_mode=public_endpoint`
- `provider_adapter=sse`
- `enabled=false`
- `experimental=true`
- `authorization_status=review_required`
- `redistribution_status=unclear`
- `commercial_use_status=unclear`
- `legal_review_status=pending`

二者均为实验候选，不是正式生产供应商。深交所、北交所、政府机构、国际机构和财经媒体不得在本阶段注册为可用 Provider。

## 七、未来来源预留

以下仅作为文档和枚举预留，不创建可用 Provider，不创建真实数据表：

- 国内政府和监管机构：国务院、国家发改委、工信部、财政部、商务部、国资委、中国人民银行、证监会、金融监管总局、国家统计局、海关总署、国家能源局、国家药监局、省级政府、市级政府。
- 国际官方来源：SEC、Federal Reserve、ECB、IMF、World Bank、BIS、OECD。
- 授权财经媒体：Bloomberg、Reuters、Financial Times、Wall Street Journal、Nikkei Asia。

Bloomberg、Reuters 等媒体必须通过授权接口或内容合作接入，不得通过普通网页爬取替代授权。国内市级以上政府来源未来应使用白名单，不做全国政府网站无差别全量扫描。

## 八、未来模型草案

以下模型仅为 Pydantic 草案和文档设计，不创建数据库表：

`GovernmentDocumentDraft`：

- `external_source_id`
- `provider_document_id`
- `title`
- `normalized_title`
- `document_number`
- `issuing_authorities`
- `authority_level`
- `jurisdiction`
- `document_type`
- `published_at`
- `effective_at`
- `expires_at`
- `policy_status`
- `policy_topics`
- `affected_regions`
- `affected_industries`
- `mentioned_companies`
- `related_symbols`
- `source_url`
- `attachment_urls`
- `interpretation_url`
- `is_policy_interpretation`
- `supersedes_document_id`
- `data_completeness`
- `missing_fields`

`InternationalOfficialDocumentDraft`：

- `external_source_id`
- `provider_document_id`
- `title`
- `issuing_organization`
- `jurisdiction`
- `country_code`
- `document_type`
- `published_at`
- `effective_at`
- `source_url`
- `attachment_urls`
- `topics`
- `affected_countries`
- `affected_industries`
- `mentioned_companies`
- `related_symbols`
- `sanctions_or_controls`
- `language`
- `translated_summary`
- `translation_status`
- `data_completeness`

`LicensedMediaItemDraft`：

- `external_source_id`
- `provider_item_id`
- `title`
- `published_at`
- `updated_at`
- `author`
- `source_url`
- `language`
- `licensed_summary`
- `licensed_excerpt`
- `full_text_available`
- `full_text_storage_allowed`
- `ai_processing_allowed`
- `redistribution_allowed`
- `related_symbols`
- `related_entities`
- `content_hash`
- `license_reference`

政策征求意见稿、政策解读、领导讲话、正式规范性文件、行政处罚和统计发布必须区分。原始语言和 AI 翻译必须分开。媒体标题和链接可访问不等于允许建立商业新闻数据库。

## 九、公告领域表

本阶段新增正式表：

- `announcement_records`：公共公告元数据记录，不包含用户处理状态。
- `user_announcement_candidates`：用户私有公告候选，保存审核、忽略、恢复、导入和 PDF 提取状态。
- `provider_sync_runs`：用户手动发起的 Provider 同步运行记录。
- `provider_sync_states`：按用户、来源、能力和范围保存游标及健康状态。
- `information_ingestion_links`：记录公告候选导入 InformationItem 的幂等关系。

公共公告记录和用户候选必须分离。同一公告可以成为多个用户的候选；A 用户忽略、查看、提取或导入不影响 B 用户。

## 十、功能开关

新增配置：

- `EXTERNAL_SOURCE_REGISTRY_ENABLED`
- `ANNOUNCEMENT_INGESTION_ENABLED`
- `ANNOUNCEMENT_REAL_NETWORK_ENABLED`
- `ANNOUNCEMENT_CNINFO_ENABLED`
- `ANNOUNCEMENT_SSE_ENABLED`
- `ANNOUNCEMENT_DOCUMENT_EXTRACTION_ENABLED`
- `ANNOUNCEMENT_MAX_SYMBOLS_PER_RUN`
- `ANNOUNCEMENT_MAX_RECORDS_PER_RUN`
- `ANNOUNCEMENT_MAX_REQUESTS_PER_RUN`
- `ANNOUNCEMENT_REQUEST_DELAY_MS`
- `ANNOUNCEMENT_REQUEST_TIMEOUT_SECONDS`
- `ANNOUNCEMENT_MAX_RESPONSE_BYTES`
- `ANNOUNCEMENT_MAX_PDF_BYTES`
- `ANNOUNCEMENT_MAX_PDF_PAGES`
- `ANNOUNCEMENT_SYNC_LOOKBACK_DAYS`

开发默认值：

- `EXTERNAL_SOURCE_REGISTRY_ENABLED=true`
- 公告同步、真实网络、CNINFO、SSE、PDF 提取默认全部关闭。
- 单次最多 20 只股票、50 条公告、30 次请求。
- 请求间隔默认 1000ms。
- 最近同步窗口默认 7 天。

本地实验配置放在被 Git 忽略的 `.local/announcement.env`。不得输出该文件真实内容。前端展示同步限制时必须读取公告 Provider 能力接口返回的非敏感 `limits`，不得硬编码开发默认值；2026-07-26/27 本地真实 Smoke 使用的实验限制为单次最多 4 只股票、20 条公告。生产环境即使误配真实网络开关，也必须阻止公告真实同步。

## 十一、Provider 接口

Provider 基础层在 `backend/app/providers/` 下：

```text
providers/
  base.py
  statuses.py
  external_sources.py
  announcements/
    base.py
    models.py
    registry.py
    cninfo.py
    sse.py
    normalization.py
    classification.py
    deduplication.py
    document_extraction.py
```

业务服务不得直接依赖 CNINFO 或上交所实现，必须通过 Provider 注册表取得适配器。Provider 状态包括 `pass`、`partial`、`data_insufficient`、`not_available`、`network_error`、`timeout`、`rate_limited`、`access_denied`、`source_changed`、`parse_error`、`content_unavailable`、`legal_hold`、`disabled`。

测试不得访问真实网络，必须 mock Provider。

## 十二、人工同步范围

用户只能同步本人当前自选股，或者从本人自选股中手动选择部分股票。不得全市场扫描，不得多年历史扫描，不得后台轮询。

同步输入：

- 来源代码
- 日期范围
- 是否使用当前自选股
- 可选股票 ID 列表

同步限制：

- 日期范围不得超过系统上限。
- 股票数量不得超过配置上限。
- 无自选股时返回 `data_insufficient`，不调用 Provider。
- 同一用户同一时刻不得并发启动多个公告同步运行。
- 不同用户运行和候选互相隔离。
- 页面请求进行期间必须显示同步中状态并禁用“同步公告候选”按钮，防止重复点击；该前端状态只作为交互保护，不替代后端 `ANNOUNCEMENT_SYNC_ALREADY_RUNNING` 并发防护。

## 十三、公告标准化

公告标准化输出至少包含：

- 来源代码
- Provider 公告 ID
- 标题和标准化标题
- 公告类型
- 分类依据
- 发布时间
- 公司名称
- 股票代码
- 市场
- 来源页面 URL
- PDF 或附件 URL
- 是否 PDF
- 是否更正公告
- 原始元数据哈希
- 去重键
- 数据完整度
- 缺失字段
- 采集时间

公告分类使用确定性标题规则，仅用于信息整理，不是投资判断。更正公告必须优先识别，且不得与原公告混淆。

## 十四、去重和匹配

去重优先使用：

1. 来源和 Provider 公告 ID；
2. 来源和去重键；
3. 来源 URL、标题、发布时间、股票代码和 PDF URL 形成的稳定哈希。

重复同步不得创建新的 `announcement_records`，只更新 `last_seen_at` 和必要元数据；同一用户不得重复创建候选；不同用户可以拥有各自候选。

股票匹配只使用已有股票和当前用户自选股：

- 精确证券代码匹配；
- Provider 元数据匹配；
- 精确公司名称匹配；
- 歧义名称标记为候选，不创建虚假股票；
- 未匹配记录只保留公共公告记录，不创建用户候选。

## 十五、PDF 按需提取

PDF 提取默认关闭，用户在候选详情页主动触发。

边界：

- 只处理公开 HTTP/HTTPS URL；
- 校验域名、重定向、大小、Content-Type、PDF 签名和页数；
- 使用 `pypdf` 提取文本层；
- 不做 OCR；
- 不长期保存原始 PDF 文件；
- 不提供本地 PDF 再下载服务；
- 不在错误响应、日志或 API 中返回完整 PDF 文本；
- 扫描件、表格和复杂版式必须显示局限。

完整 PDF 可访问或可解析不等于允许全文留存、再展示、AI 摘要或商业使用。

## 十六、导入模式

用户可以将公告候选主动导入为正式 InformationItem，支持：

- `metadata_only`：只导入标题、来源、发布时间、股票匹配、原始链接和 PDF 链接等元数据，不补写正文。
- `extracted_document`：在 PDF 提取开关开启且提取成功时，将提取文本作为 `provider_document` 内容版本保存。
- `user_supplemented`：保存用户补充文本，内容来源为 `user_correction`。

导入必须幂等，同一用户同一候选重复导入返回既有 InformationItem。导入后 InformationItem 默认 `source_type=announcement`、`status=ready`、`is_important=false`。系统不得自动分析、自动标记重要或自动发送通知。

## 十七、AI 分析边界

导入后复用已有接口：

```text
POST /api/v1/information/{item_id}/analyze
```

不得创建公告专用 AI 绕过链路。AI 只能基于已保存文本和元数据进行事实、观点、传闻、风险和待核实事项分析。

AI 不得：

- 补写公告正文；
- 生成公告中不存在的金额、日期、主体、市场或财务数据；
- 把元数据导入当作完整公告正文；
- 把标题分类当作完整事实；
- 自动判断利好、利空、买入、卖出、目标价或收益；
- 声称已核实公告外事实；
- 仅因来源等级决定情绪方向。

## 十八、复盘和通知边界

公告候选：

- 不属于每日复盘输入；
- 不创建 BusinessEvent；
- 不创建 Notification；
- 不自动触发 AI；
- 不自动标记 important。

导入后的 InformationItem：

- 可以触发相关日期每日复盘 stale；
- 用户主动分析后可进入下一次复盘；
- 可复用既有信息通知逻辑；
- 不新增公告专属即时通知。

“不自动通知”在本阶段指不创建 `announcement.imported`、`announcement.candidate_created` 或其他公告专属 BusinessEvent / Notification。若导入后的 InformationItem 改变了既有每日复盘输入，已有复盘领域规则可以产生一次 `user_daily_review.became_stale` 事件和对应站内通知；这属于每日复盘 stale 通知，不属于公告导入通知。重复导入幂等返回既有 InformationItem，不得重复产生 stale 通知；没有既有复盘时，不得虚构 stale 事件。

## 十九、用户隔离

必须满足：

- 用户 A 看不到用户 B 的同步运行；
- 用户 A 看不到用户 B 的候选；
- 用户 A 不能处理用户 B 的候选；
- 用户 A 不能提取用户 B 候选的 PDF；
- 用户 A 不能导入用户 B 的候选；
- A dismiss 不影响 B；
- 同一公告可以分别成为 A 和 B 的候选；
- A 导入不为 B 导入；
- `announcement_records` 可共享但不包含用户状态；
- `information_ingestion_links` 严格按用户隔离；
- 仅知道 UUID 不能越权。

管理员通过普通用户 API 也不能读取其他用户候选。

## 二十、前端页面

新增页面：

- `/settings/sources`：展示外部来源注册表、公告 Provider 状态和未来来源分组。不得提供同步按钮或 Provider 编辑能力。
- `/information/announcements`：公告候选收件箱，包含实验说明、手动同步入口、来源状态、当前 Provider 同步限制、筛选区、候选列表和基础操作。`reviewed` 与 `dismissed` 候选必须提供“恢复待处理”入口，`pending` 不显示该入口，`imported` 不允许恢复。
- `/information/announcements/[candidateId]`：候选详情，包含详细实验说明、来源授权状态、匹配依据、PDF 状态、状态恢复、导入模式和跳转 InformationItem 的入口。状态操作期间按钮禁用，成功后刷新状态，失败时使用现有错误反馈。

移动端要求：

- 不新增第六个底部导航；
- 信息中心入口保持清晰；
- 同步表单完整可操作；
- 候选列表单屏约 3 条；
- 长标题换行；
- 来源等级和授权状态不拥挤；
- 操作按钮可点击。

## 二十一、API

新增 API：

- `GET /api/v1/external-sources`
- `GET /api/v1/external-sources/future-groups`
- `GET /api/v1/announcement-providers`
- `POST /api/v1/announcement-sync-runs`
- `GET /api/v1/announcement-sync-runs`
- `GET /api/v1/announcement-sync-runs/{run_id}`
- `GET /api/v1/announcement-candidates`
- `GET /api/v1/announcement-candidates/{candidate_id}`
- `PATCH /api/v1/announcement-candidates/{candidate_id}`
- `POST /api/v1/announcement-candidates/{candidate_id}/extract-document`
- `POST /api/v1/announcement-candidates/{candidate_id}/import`

所有写请求必须通过既有 Session 和 CSRF 校验。错误响应使用统一错误结构，不返回堆栈、完整 Provider 响应、PDF 文本、Cookie、Header、数据库内部错误或密钥。

## 二十二、错误码

新增错误码：

- `EXTERNAL_SOURCE_NOT_FOUND`
- `EXTERNAL_SOURCE_DISABLED`
- `EXTERNAL_SOURCE_LEGAL_HOLD`
- `EXTERNAL_SOURCE_AUTHORIZATION_REQUIRED`
- `ANNOUNCEMENT_FEATURE_DISABLED`
- `ANNOUNCEMENT_REAL_NETWORK_DISABLED`
- `ANNOUNCEMENT_PROVIDER_DISABLED`
- `ANNOUNCEMENT_PROVIDER_NOT_FOUND`
- `ANNOUNCEMENT_PROVIDER_UNAVAILABLE`
- `ANNOUNCEMENT_PROVIDER_RATE_LIMITED`
- `ANNOUNCEMENT_PROVIDER_SOURCE_CHANGED`
- `ANNOUNCEMENT_SYNC_ALREADY_RUNNING`
- `ANNOUNCEMENT_SYNC_LIMIT_EXCEEDED`
- `ANNOUNCEMENT_SYNC_FAILED`
- `ANNOUNCEMENT_CANDIDATE_NOT_FOUND`
- `ANNOUNCEMENT_ALREADY_IMPORTED`
- `ANNOUNCEMENT_DOCUMENT_UNAVAILABLE`
- `ANNOUNCEMENT_DOCUMENT_TOO_LARGE`
- `ANNOUNCEMENT_DOCUMENT_TOO_MANY_PAGES`
- `ANNOUNCEMENT_DOCUMENT_PARSE_FAILED`
- `ANNOUNCEMENT_DOCUMENT_TEXT_UNAVAILABLE`
- `ANNOUNCEMENT_IMPORT_MODE_INVALID`

## 二十三、日志和审计

允许日志字段：

- `request_id`
- `user_id`
- `source_code`
- `sync_run_id`
- `candidate_id`
- `announcement_record_id`
- `status`
- `request_count`
- `record_count`
- `latency`
- `error_code`

禁止日志字段：

- 完整 Provider 响应；
- 完整网页正文；
- 完整 PDF；
- 完整 PDF 文本；
- Cookie；
- Session Token；
- AI Key；
- `APP_ENCRYPTION_KEYS`；
- 数据库密码；
- 第三方敏感 Header。

审计至少覆盖人工发起同步、查看运行、标记候选已查看、忽略、恢复、提取 PDF、导入公告、导入失败和因法律状态阻止同步。

## 二十四、验收基线

第六阶段完成条件：

- `external_sources` 注册表完成；
- CNINFO 和 SSE_DISCLOSURE 幂等注册且默认关闭；
- 未实现来源不会显示为可用；
- 功能开关默认关闭；
- production 阻止真实网络同步；
- 人工同步可用且限定当前用户自选股；
- 公告标准化、分类、去重和股票匹配可用；
- 用户候选收件箱可用；
- 用户隔离有效；
- PDF 只按需提取；
- 不长期保存原始 PDF；
- 用户主动导入 InformationItem；
- 不自动调用 AI；
- 不自动通知；
- 导入后已有复盘 stale 正常；
- 原有测试继续通过；
- 新增测试通过；
- 文档与实现一致；
- 无 P0/P1 问题；
- 无敏感信息泄露。

## 二十五、后续阶段顺序

推荐后续顺序：

1. 上市公司公告候选收件箱试点。
2. 国内政府与国际官方来源可行性 Spike。
3. 国内政府政策候选收件箱。
4. 国际官方信息候选收件箱。
5. 授权财经媒体商业和法律评估。
6. 获得授权后才开发媒体 Provider。
7. 自动调度最后实施。

不得把政府政策自动采集、市级政府全量监控、SEC/Fed/ECB 自动同步、Bloomberg 或 Reuters 接入、财经新闻自动采集、后台定时任务、自动公告通知、全市场公告监控、Provider 商业授权、微信、行情和估值写成本阶段已完成。

## 二十六、2026-07-26 真实 Smoke 收口记录

2026-07-26 在本地私人测试环境对 CNINFO 执行低频真实 Smoke，范围限定为当前用户自选股、最近 7 个自然日、最多 10 条记录。实际返回结果为 `network_error`，未产生真实公告候选、未导入 InformationItem，也未触发 AI 分析或站内通知。

本次已验证：

- 网络失败时，后端以失败状态降级并保留可追溯同步记录，页面可继续展示失败状态和后续操作入口。
- 失败场景没有创建公告记录、用户候选、InformationItem、AI 任务或通知，符合无副作用要求。
- 相同参数再次同步未产生重复业务数据；由于本次返回 0 条候选，该结论仅覆盖失败降级和零数据幂等，不代表真实候选去重已完成产品验收。
- Provider 健康状态能够记录 `network_error`，后续可据此提示来源不可达。

仍待 Provider 可达后补充人工验收：

- 真实候选列表生成、筛选和状态流转。
- 真实 PDF 按需提取、大小限制、页数限制、签名和 Content-Type 记录。
- 真实候选导入 InformationItem、重复导入幂等和复盘 stale。
- 导入后由用户主动触发既有 AI 分析闭环。

因此，CNINFO 当前仍是实验候选来源，不是已冻结的 V1 生产数据供应商；第六阶段不得写成已经完成真实 Provider 端到端产品验收。
## 2026-07-26 6A.1 前置收口状态

证券目录前置闭环已形成本地可用目录：SH 来自 `SSE_SECURITY_MASTER`，BJ 来自 `BSE_SECURITY_MASTER` 官方新旧代码对照表，SZ 由非官方 `BAOSTOCK_DEVELOPMENT_FALLBACK` 在 development 环境补足。`SZSE_SECURITY_MASTER` 官方接口仍为 HTTP 500 / `network_error`，Provider 未冻结。公告真实 Smoke、真实候选、PDF、导入和 AI 闭环仍等待 `/watchlist` 真实页面人工验收后恢复，不得在本阶段继续扩大。
