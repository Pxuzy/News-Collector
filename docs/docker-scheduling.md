# Docker 定时采集与清理

这个仓库的 Docker 采集入口分三类，分别对应“你要求时立即采集”“按固定时间窗口采集”和“定时清理”。

## 入口职责

- `manual-collect`：手动采集入口。适合你临时要求“现在抓取新闻”时使用，默认 `COLLECT_FORCE=1`，会忽略 `source_state.next_run_at` 立即刷新目标源。
- `scheduler`：定时采集入口。默认 `COLLECT_FORCE=0`，只在设定时间点触发，并继续使用 `source_state.next_run_at` 跳过未到期源，避免重复请求外部站点。
- `maintenance`：手动清理入口。只执行保留策略清理和可选 `VACUUM`，不触发采集。
- `maintenance-scheduler`：定时清理入口。默认每天 03:30 执行保留策略清理和 `VACUUM`。

默认配置见 `.env.example`：

```text
COLLECT_SCHEDULE=08:30,12:30,18:30,22:30
MAINTENANCE_SCHEDULE=03:30
RETENTION_DAYS=30
COLLECT_PARALLEL=8
COLLECT_FORCE=0
COLLECT_VACUUM=0
MAX_ARTICLES=500
```

## 启动定时服务

同时启动 API、定时采集和定时清理：

```powershell
docker compose --profile schedule up -d api scheduler maintenance-scheduler
```

查看状态和日志：

```powershell
docker compose ps
docker compose logs -f scheduler maintenance-scheduler
```

## 手动采集

立即采集全部启用源：

```powershell
docker compose --profile manual run --rm manual-collect
```

立即采集指定源：

```powershell
$env:COLLECT_SOURCE = "baidu,zhihu"
docker compose --profile manual run --rm manual-collect
```

立即采集核心源：

```powershell
$env:COLLECT_CORE = "1"
docker compose --profile manual run --rm manual-collect
```

## 只清理不采集

手动执行一次清理：

```powershell
docker compose --profile maintenance run --rm maintenance
```

## 快速验证定时入口

不等待下一个时间点，按定时任务配置跑一次：

```powershell
docker compose --profile schedule run --rm scheduler python scripts/scheduled_collector.py --once
```

## 冗余控制

长期运行的 `scheduler` 不建议设置 `COLLECT_FORCE=1`。正常定时模式应保持 `COLLECT_FORCE=0`，这样每个时间点只负责触发一次检查，真正是否采集由每个源的 `source_state.next_run_at` 决定。需要立刻刷新时再使用 `manual-collect`。
