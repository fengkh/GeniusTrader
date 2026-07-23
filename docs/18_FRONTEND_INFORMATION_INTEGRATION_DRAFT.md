# 前端信息中心联调草案

本文记录 GeniusTrader 第三阶段“用户认证、AI 配置与信息中心前端真实 API 联调”的实现边界。

## 范围

- `/login` 接入后端 Session Cookie 登录。
- `/information` 接入后端信息条目列表、筛选、手动文本录入、单 URL 录入和关联股票搜索。
- `/information/[itemId]` 接入信息详情、来源记录、正文版本、AI 分析版本、股票关联建议确认/拒绝、补充正文、重新抓取、分析和归档。
- `/settings/ai` 接入用户 AI Provider 配置、更新、测试和删除。
- 全局前端 API client 使用 `NEXT_PUBLIC_API_BASE_URL`、`credentials: "include"` 和 `X-CSRF-Token`。

## 明确不包含

- 不接入真实行情、真实公告资讯 Provider、真实数据库以外的数据源或真实前端权限系统。
- 不开发每日复盘、全市场复盘、估值、通知真实业务、微信公众号或外部推送。
- `/today`、`/watchlist`、`/watchlist/[stockId]`、`/market-review/[date]`、`/reviews`、`/notifications` 和 `/settings/notifications` 继续保持 Mock。

## 安全边界

- 前端不读取完整 API Key，不通过浏览器直接调用第三方 AI。
- Session Token 只在 HttpOnly Cookie 中保存；前端不使用 localStorage 或 sessionStorage 保存 Session、密码或 AI Key。
- 后端登录成功同时设置 HttpOnly Session Cookie 和非 HttpOnly、SameSite=Lax 的 CSRF Cookie。
- 前端写请求从 CSRF Cookie 读取 token，并通过 `X-CSRF-Token` 请求头回传。
- AI 调用日志仍只保存任务元数据，不长期保存完整输入、完整第三方正文、完整 Prompt、API Key 或模型隐藏推理。

## 页面状态

- 未登录：真实联调页展示登录入口或由 API client 跳转 `/login`。
- 空数据：信息中心和 AI 配置页展示可操作空状态。
- 加载中：列表、详情和配置列表使用模块级加载状态。
- 部分失败：抓取失败或 AI 失败只影响对应模块，来源、正文和人工关联仍可查看。
- 完全失败：API 不可用时展示统一错误信息和后端 `request_id`。

## 本地配置

- 根目录 `.env.local` 使用 `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`。
- `.local/app.env` 存放本地 `APP_ENCRYPTION_KEYS`，不得提交。
- 可提交的 `.env.example` 只包含非敏感公开配置示例。
