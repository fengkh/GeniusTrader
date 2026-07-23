# GeniusTrader 信息采集与 AI 分析架构草案

本文记录后端第二阶段“受控信息采集、AI Gateway 与结构化舆情分析闭环”的实现边界。

## 范围

- 支持用户手动录入文本。
- 支持用户提交单个公开 URL，并由后端执行受控抓取。
- 支持用户配置 OpenAI Compatible AI Provider。
- 支持通过统一 AI Gateway 对已保存文本生成结构化分析。
- 支持保存内容版本、抓取尝试、AI 任务、AI 调用尝试、分析版本、股票关联、实体提及和待核实事项。

不包含：真实行情接入、真实公告资讯 Provider 选型、全站社交平台爬虫、登录抓取、验证码绕过、浏览器自动化抓取、真实 AI 自动化测试、每日复盘生成、通知中心真实业务或前端 API 联调。

## 受控抓取

抓取器仅允许 `http` 和 `https`，并执行以下限制：

- URL 不得包含用户名或密码。
- DNS/IP 不得指向私有、回环、链路本地、多播、保留或未指定地址。
- 每次重定向都必须重新校验。
- 限制最大重定向次数、超时时间、最大响应字节数和允许内容类型。
- 不携带用户 Cookie，不登录，不执行 JavaScript，不抓取二级链接，不使用代理。

抓取失败时保存失败状态和尝试记录，不删除信息条目。

## AI Provider 与密钥

用户 API Key 使用 `APP_ENCRYPTION_KEYS` 提供的 Fernet/MultiFernet 加密保存：

- 第一把密钥用于新密文。
- 所有配置密钥用于解密历史密文。
- API 响应、审计日志和 AI 调用日志不得返回或记录完整 API Key。
- 同一用户最多只能启用一个 AI Provider。

## AI Gateway

AI Gateway 第一版只支持 OpenAI Compatible Chat Completions。调用日志只保存任务类型、模型、时间、Token、耗时、成功/失败状态、错误码、输出结构校验状态和关联业务结果 ID。

默认不长期保存完整原始输入、完整第三方正文、完整 Prompt、API Key 或模型隐藏推理。

## 结构化分析

AI 分析输入必须把第三方内容放入明确的不可信内容边界内。输出必须通过严格 schema 校验，字段包括：

- 内容类型；
- 摘要；
- 事实；
- 观点；
- 传闻；
- 情绪；
- 证据强度；
- 不确定性；
- 来源可信度；
- 关键主张；
- 股票提及；
- 实体提及；
- 风险；
- 待核实事项；
- 时间范围；
- 限制说明。

首次结构化校验失败时可请求一次修复；第二次仍失败则保存失败分析版本。AI 不得生成行情、K 线、公告原文、股票基础数据或交易建议。

## 降级策略

- URL 抓取失败：保留条目，展示失败状态，允许用户补充正文。
- 内容为空：禁止 AI 分析，提示补充正文。
- AI Provider 缺失：提示先配置模型，不影响信息查看。
- AI 调用失败：保存失败任务和失败分析版本，不覆盖原文。
- AI 结构校验失败：最多修复一次，仍失败则进入 `analysis_failed`。
- AI 建议股票关联：默认为 `suggested`，用户确认后才进入确认关系。

## 数据表

- `ai_provider_configs`
- `ai_tasks`
- `ai_task_attempts`
- `information_items`
- `information_sources`
- `information_contents`
- `content_fetch_attempts`
- `information_analysis_versions`
- `information_stock_relations`
- `information_entity_mentions`
- `verification_items`

