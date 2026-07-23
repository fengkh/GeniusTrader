# 本地 PostgreSQL 数据库设置

本文记录 GeniusTrader 当前本地开发数据库发现、初始化和连接验证结果。本文档不得记录真实生产密码；本地开发密码也只使用 `PASSWORD_PLACEHOLDER` 表示。

## 检测结果

| 项目 | 结果 |
| --- | --- |
| PostgreSQL 版本 | PostgreSQL 17.10 |
| `psql.exe` 路径 | `D:\apps\postgreSQL\bin\psql.exe` |
| PostgreSQL 安装目录 | `D:\apps\postgreSQL` |
| 数据目录 | `D:\apps\postgreSQL\data` |
| Windows 服务名称 | `postgresql-x64-17` |
| Windows 服务状态 | `Running` |
| 本地数据库名称 | `geniustrader` |
| 本地开发角色名称 | `root` |
| 本地连接地址 | `127.0.0.1:5432/geniustrader` |
| 当前本地配置文件 | `.local/database.env` |
| 可提交示例文件 | `docs/examples/database.env.example` |

## 本地连接字符串格式

```text
DATABASE_URL=postgresql+psycopg://root:PASSWORD_PLACEHOLDER@127.0.0.1:5432/geniustrader
APP_TIMEZONE=Asia/Shanghai
```

`PASSWORD_PLACEHOLDER` 仅表示本地开发密码占位。简单弱口令只允许用于当前本地开发环境，不得描述为生产环境安全配置。

生产环境必须更换强密码，使用最小权限账号，并通过密钥系统或环境变量管理敏感配置。

## 验证命令

以下命令仅展示验证方式，不包含真实密码。

```powershell
$env:PGPASSWORD = "PASSWORD_PLACEHOLDER"
& "D:\apps\postgreSQL\bin\psql.exe" -h 127.0.0.1 -p 5432 -U root -d geniustrader -c "SELECT current_database(), current_user;"
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
```

最终验证已确认：

- `current_database = geniustrader`
- `current_user = root`
- `server_encoding = UTF8`
- `timezone = Asia/Shanghai`
- `root` 不是 PostgreSQL 超级用户
- `root` 可在 `public` schema 创建、写入、查询并删除本轮专用测试表

## 服务管理命令

查看服务状态：

```powershell
Get-Service -Name postgresql-x64-17
```

启动服务：

```powershell
Start-Service -Name postgresql-x64-17
```

停止服务：

```powershell
Stop-Service -Name postgresql-x64-17
```

如果启动或停止需要管理员权限，请使用管理员 PowerShell 执行，不要绕过 Windows 权限控制。

## 安全说明

- 本文档不得记录真实生产密码。
- `.local/database.env` 必须被 Git 忽略。
- 不得提交真实 `.env`、真实用户数据、数据库备份或本地凭据。
- 不得将 PostgreSQL 认证方式改为 `trust`。
- 不得擅自修改 `pg_hba.conf`。
- 不得删除或重建现有数据库集群。
- 不得把本地开发角色设置为超级用户。
