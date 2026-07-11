# Docker 部署指南

本文档说明如何用 Docker 运行 News-Collector。Docker 只作为部署外壳，不改变现有 Python 入口。

## 文件说明

- `Dockerfile`：构建 Python 3.11 运行环境并安装 `requirements.txt`。
- `.dockerignore`：排除本地数据库、输出、日志、缓存和私有环境文件，避免打进镜像。
- `docker-compose.yml`：提供这些服务：
  - `app`：一次性命令容器，用于初始化、采集、生成、校验。
  - `api`：FastAPI 查询服务，默认监听 `8899`。
  - `manual-collect`：手动采集入口，默认强制刷新。
  - `scheduler`：定时采集入口，默认尊重 `source_state.next_run_at`。
  - `maintenance`：手动清理入口。
  - `maintenance-scheduler`：定时清理入口。

Compose 会把这些目录挂载到容器内，容器重建不会丢数据：

```text
./data        -> /app/data
./output      -> /app/output
./logs        -> /app/logs
./cron/output -> /app/cron/output
```

## 构建镜像

```powershell
docker compose build
```

默认构建会使用较稳的 pip 镜像源和更长超时时间，避免 `pypi.org` 或
`files.pythonhosted.org` 在本机网络下超时。需要切回官方源或使用其它源时，可以通过环境变量覆盖：

```powershell
$env:PIP_INDEX_URL = "https://pypi.org/simple"
$env:PIP_DEFAULT_TIMEOUT = "180"
$env:PIP_RETRIES = "10"
docker compose build
```

如果构建失败，优先检查：

- Docker Desktop 是否已启动。
- 当前目录是否是项目根目录。
- 网络是否能访问 Python 镜像、Debian apt 源和 pip 源。

## 首次初始化

新环境如果没有 `data/news.db`，先初始化数据库表：

```powershell
docker compose run --rm app python -c "from store import init_db; init_db()"
```

然后检查状态：

```powershell
docker compose run --rm app python scripts/nb_query.py --status
```

如果状态命令返回空数据但没有报错，说明数据库结构已经正常。

## 小范围采集验证

不要第一次就跑全量采集。先采集两个相对稳定的源：

```powershell
docker compose run --rm app python multi_source_news.py --source baidu,zhihu --force --parallel 2
docker compose run --rm app python scripts/nb_query.py --status
```

外部新闻源可能超时或失败。只要数据库能写入、状态能查询，就说明容器运行链路是通的。

## 生成简报

已有数据后生成并校验简报：

```powershell
docker compose run --rm app python scripts/generate_briefing.py --skip-collect
docker compose run --rm app python scripts/validate_briefing.py output/news-YYYY-MM-DD.md
```

如果需要刷新核心源后再生成：

```powershell
docker compose run --rm app python multi_source_news.py --core --parallel 8 --prune
docker compose run --rm app python scripts/generate_briefing.py --skip-collect
```

## 启动 API

```powershell
docker compose up -d api
```

访问（仅限宿主机本地，供 Hermes 使用）：

```text
http://localhost:8899/health
http://localhost:8899/docs
http://localhost:8899/api/stats
```

查看日志：

```powershell
docker compose logs -f api
```

停止：

```powershell
docker compose down
```

## 手动采集和定时任务

Docker 手动采集、定时采集和清理入口见 `docs/docker-scheduling.md`。常用命令：

```powershell
docker compose --profile manual run --rm manual-collect
docker compose --profile schedule up -d api scheduler maintenance-scheduler
docker compose --profile maintenance run --rm maintenance
```

这些入口默认读取 `.env` 或 `.env.example` 中列出的变量，例如 `COLLECT_SCHEDULE`、`COLLECT_SOURCE`、`COLLECT_CORE`、`COLLECT_FORCE`、`COLLECT_VACUUM`、`RETENTION_DAYS`、`MAX_ARTICLES` 和 SQLite 超时配置。

## 复制旧数据

如果你想让新容器直接使用旧环境数据，把旧的 `data/news.db` 放到项目根目录的 `data/news.db`。容器会通过 volume 读取它。

不要把 `data/news.db` 打进镜像。数据库属于运行数据，应放在 volume 或宿主机目录里。

## 常见问题

### `docker compose build` 下载失败

这是网络或 Docker 源问题，不是项目代码问题。可以换网络、配置 Docker 镜像源，或在能联网的机器上先构建镜像再导出。

### `dockerDesktopLinuxEngine` 不存在

如果看到类似错误：

```text
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
```

通常是 Docker Desktop 没有启动，或 Linux engine 还没有就绪。先打开 Docker Desktop，等状态变成 running 后再执行：

```powershell
docker compose build
```

### `C:\Users\<user>\.docker\config.json: Access is denied`

这通常是当前终端或 agent 沙箱没有权限读取 Docker 本地配置。可以在普通 PowerShell 里运行 Docker 命令，或检查 `.docker` 目录权限。

### `nb_query.py --status` 报 `no such table`

说明数据库文件不存在或还没有初始化。先运行：

```powershell
docker compose run --rm app python -c "from store import init_db; init_db()"
```

### API 容器启动后 `/health` 失败

先看日志：

```powershell
docker compose logs api
```

常见原因是依赖没装完整、数据库目录权限异常，或宿主机端口 `8899` 被占用。

### 采集部分源失败

新闻源依赖外部网站，超时、限流、页面结构变化都可能发生。先用窄源验证容器本身：

```powershell
docker compose run --rm app python multi_source_news.py --source baidu,zhihu --force --parallel 2
```

再查看 `logs/collector.jsonl`。
