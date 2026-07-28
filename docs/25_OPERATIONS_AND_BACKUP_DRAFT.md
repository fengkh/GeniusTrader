# 运维、备份与恢复草案

日期：2026-07-28

本文件记录第七阶段 Checkpoint A 的运维边界。当前不引入 Celery、Kafka 或常驻进程内调度；自动任务由外部 Cron 或运维系统调用 CLI。

## 一、CLI 任务

可由系统 Cron 调用的 CLI：

- `python -m app.cli.sync_security_master`
- `python -m app.cli.sync_market_data`
- `python -m app.cli.sync_announcements`
- `python -m app.cli.cleanup_operational_data`

CLI 必须支持明确退出码、结构化摘要日志、`job_run_id` 或对应运行记录 ID、错误码和脱敏输出。没有真实行情 Token 时，`sync_market_data` 应返回非零退出码和 `MARKET_DATA_PROVIDER_NOT_CONFIGURED`，不得产生部分行情、不得破坏历史数据。

## 二、任务边界

- 不在应用进程内硬编码调度频率。
- 不自动触发 AI。
- 不自动创建交易建议。
- 不因公告或行情失败阻断登录、自选股、信息中心、复盘历史等其他页面。
- 生产环境中未授权 Provider 默认关闭。

## 三、备份

`scripts/backup_postgres.sh` 使用 `pg_dump` 生成 PostgreSQL 备份文件。备份输出目录必须被 Git 忽略，备份文件不得提交。

备份文件应只保存在受控服务器目录，访问权限应限制为运维账号。备份日志不得输出数据库密码。

## 四、恢复演练

`scripts/restore_postgres.sh` 应恢复到独立临时数据库，不得直接破坏开发主库或生产主库。`scripts/verify_restore.sh` 用于核对核心表计数和 Alembic 版本。

恢复演练步骤：

1. 对源库执行备份。
2. 创建独立恢复库。
3. 恢复备份。
4. 执行 `alembic current` 或等价版本检查。
5. 核对核心表数量。
6. 删除临时恢复库。

## 五、清理策略

`cleanup_operational_data` 默认 dry-run。正式执行必须显式传入执行参数，并只清理审计、安全目录同步运行、行情同步运行等运营记录，不删除业务主体数据、历史复盘、用户笔记、公告候选、行情历史快照或用户自选股。

具体保留期限仍需产品负责人和数据治理确认。

