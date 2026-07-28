# Production Server Execution Checklist

日期：2026-07-28

本清单用于 Linux 服务器上的真实部署演练。当前 Windows 本地环境未确认 Docker、Bash、`pg_dump`、`pg_restore` 可用，因此本阶段不伪造服务器执行结果。所有命令中的域名、密码、密钥和路径均为占位示例，不得提交真实值。

## 一、服务器前置

```bash
docker --version
docker compose version
git --version
openssl version
```

确认服务器防火墙只开放必要端口，PostgreSQL 不暴露公网。准备域名、HTTPS 证书、受控运维账号和私有部署目录。

## 二、代码与分支

```bash
git clone https://github.com/fengkh/GeniusTrader.git GeniusTrader
cd GeniusTrader
git checkout release/mvp-production-readiness
git status --short
```

## 三、生产环境文件

```bash
cp deploy/production.env.example .local/production.env
chmod 600 .local/production.env
```

编辑 `.local/production.env`，填入强随机 `POSTGRES_PASSWORD`、真实 `APP_ENCRYPTION_KEYS`、正式域名、CORS allowlist、Trusted Hosts 和证书路径。禁止使用示例密码、示例 Fernet Key、通配 CORS 或通配 Trusted Hosts。

生产默认保持：

```bash
MARKET_DATA_PROVIDER_ENABLED=false
MARKET_DATA_SYNC_ENABLED=false
MARKET_DATA_REAL_NETWORK_ENABLED=false
MARKET_DATA_TUSHARE_ENABLED=false
MARKET_DATA_MOCK_ENABLED=false
ANNOUNCEMENT_BSE_ENABLED=false
PUBLIC_REGISTRATION_ENABLED=false
```

CNINFO/SSE 官方公告如需上线，由部署配置显式开启：

```bash
ANNOUNCEMENT_INGESTION_ENABLED=true
ANNOUNCEMENT_REAL_NETWORK_ENABLED=true
ANNOUNCEMENT_CNINFO_ENABLED=true
ANNOUNCEMENT_SSE_ENABLED=true
ANNOUNCEMENT_BSE_ENABLED=false
```

## 四、Compose 配置与启动

```bash
set -a
. ./.local/production.env
set +a
docker compose --env-file .local/production.env -f docker-compose.production.yml config
docker compose --env-file .local/production.env -f docker-compose.production.yml build
docker compose --env-file .local/production.env -f docker-compose.production.yml up -d postgres
docker compose --env-file .local/production.env -f docker-compose.production.yml up -d backend
```

后端容器启动时必须等待数据库健康并执行 Alembic migration；migration 失败必须导致启动失败。

## 五、管理员账户

```bash
docker compose --env-file .local/production.env -f docker-compose.production.yml exec backend python -m app.cli.create_admin
```

管理员密码只能在交互提示中输入，不得写入命令行、Shell 历史、Git、日志或截图。

## 六、前端与 Nginx

```bash
docker compose --env-file .local/production.env -f docker-compose.production.yml up -d frontend nginx
docker compose --env-file .local/production.env -f docker-compose.production.yml ps
```

确认只有 Nginx 暴露 80/443；后端、前端、PostgreSQL 只在 Compose 内部网络可达。

## 七、发布检查

```bash
docker compose --env-file .local/production.env -f docker-compose.production.yml exec backend python -m app.cli.release_check
python scripts/production_smoke.py --base-url https://your-domain.example --timeout 10
```

`release_check` 退出码含义：0 可部署；1 存在阻断项；2 只有 warning，需产品负责人或运维确认。输出不得包含数据库密码、`APP_ENCRYPTION_KEYS`、API Key、Cookie、Session Token 或 CSRF Token。

## 八、备份恢复演练

```bash
mkdir -p /srv/geniustrader/backups
BACKUP_DIR=/srv/geniustrader/backups DATABASE_URL="$DATABASE_URL" sh scripts/backup_postgres.sh
sha256sum /srv/geniustrader/backups/geniustrader-*.dump
createdb geniustrader_restore_drill
RESTORE_DATABASE_URL="postgresql+psycopg://USER:PASSWORD@postgres:5432/geniustrader_restore_drill" \
BACKUP_FILE="/srv/geniustrader/backups/geniustrader-YYYYMMDDTHHMMSSZ.dump" \
sh scripts/restore_postgres.sh
RESTORE_DATABASE_URL="postgresql+psycopg://USER:PASSWORD@postgres:5432/geniustrader_restore_drill" \
sh scripts/verify_restore.sh
dropdb geniustrader_restore_drill
```

核心表计数必须覆盖 `users`、`stocks`、`user_watchlist_items`、`announcement_records`、`information_items`、`daily_reviews`、`ai_tasks`、`stock_daily_snapshots`。行情关闭时 `stock_daily_snapshots=0` 可接受。

## 九、Cron 示例

以下仅为示例，不代表当前必须全部启用：

```cron
# 每周证券主数据人工确认后执行，生产默认不启用 BaoStock。
0 3 * * 0 cd /srv/geniustrader && docker compose --env-file .local/production.env -f docker-compose.production.yml exec -T backend python -m app.cli.sync_security_master --source SSE_SECURITY_MASTER

# 交易日低频公告候选同步，必须幂等，失败不得清空历史。
30 18 * * 1-5 cd /srv/geniustrader && docker compose --env-file .local/production.env -f docker-compose.production.yml exec -T backend python -m app.cli.sync_announcements --source CNINFO

# 运营数据清理，默认先 dry-run。
15 2 * * * cd /srv/geniustrader && docker compose --env-file .local/production.env -f docker-compose.production.yml exec -T backend python -m app.cli.cleanup_operational_data --dry-run
```

行情同步 Cron 当前不启用。只有完成 Provider 授权冻结和 Checkpoint B 后，才允许增加行情同步任务。

## 十、回滚与持久化

```bash
docker compose --env-file .local/production.env -f docker-compose.production.yml restart
docker compose --env-file .local/production.env -f docker-compose.production.yml logs --tail=100 backend
docker compose --env-file .local/production.env -f docker-compose.production.yml logs --tail=100 nginx
```

重启后确认登录、自选股、公告候选、信息中心、每日复盘和站内通知仍可访问。不得把备份文件、生产 `.env`、证书、Provider 响应、用户导入导出文件或日志中的敏感内容提交到 Git。
