# 新环境安装与运行指南

本文档给新 agent 或新机器使用。目标是先把项目跑通，再做采集、生成和排障。

## 1. 获取项目

如果仓库已经有远程地址：

```powershell
git clone <repo-url> News-Collector
cd News-Collector
```

如果当前只是本地工作区，还没有 `git remote`，就先从现有目录复制或压缩导出项目。复制时不要把临时缓存当成源码依赖：

- 可以复制：`multi_source_news.py`、`sources/`、`scripts/`、`skill/`、`config/`、`docs/`、`README.md`、`requirements.txt`
- 可选复制：`data/news.db`，用于让新环境马上能查询历史数据
- 不必复制：`.ruff_cache/`、`__pycache__/`、`.codegraph/`、`.ai/`、`logs/`、`output/`

如果不复制 `data/news.db`，首次查询会没有历史数据，需要先跑一次采集。

## 2. Python 环境

推荐 Python 3.10 或 3.11。当前已验证环境是 Python 3.11。

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PowerShell 如果禁止激活脚本，可以只在当前窗口放开执行策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 3. 首轮验证

先不要直接全量采集。按下面顺序确认环境：

```powershell
python -m compileall -q multi_source_news.py scripts sources
python scripts\nb_query.py --status
```

如果已有 `data/news.db`，`nb_query.py --status` 应返回 JSON，其中 `status` 为 `ok`。

如果没有数据库，先小范围采集两个相对稳定的源：

```powershell
python multi_source_news.py --source baidu,zhihu --force --parallel 2
python scripts\nb_query.py --status
```

确认数据库可用后，再生成简报：

```powershell
python scripts\generate_briefing.py --skip-collect
python scripts\validate_briefing.py output\news-YYYY-MM-DD.md
```

需要刷新数据时再跑：

```powershell
python multi_source_news.py --core --parallel 8 --prune
python scripts\generate_briefing.py --skip-collect
```

## 4. 常见环境问题

### `ModuleNotFoundError`

通常是依赖没有装到当前 Python：

```powershell
where python
python -m pip --version
python -m pip install -r requirements.txt
```

确保运行脚本和安装依赖用的是同一个 `python`。

### Windows 中文或 emoji 输出乱码

优先在 PowerShell 设置 UTF-8：

```powershell
$env:PYTHONIOENCODING = "utf-8"
chcp 65001
```

项目内主要 CLI 已经尽量重配置 stdout/stderr，但外层终端仍可能影响显示。

### 采集超时或部分源失败

这是正常风险。新闻源依赖外部网站，可能被限流、超时或结构变化。排障时先跑窄源：

```powershell
python multi_source_news.py --source baidu,zhihu --force --parallel 2
```

不要把单个外部源失败当成整个项目不可用。先看 `logs/collector.jsonl` 和 `python scripts\nb_query.py --status`。

### 没有 `data/news.db`

项目会在采集或初始化数据库时创建 SQLite 文件。新环境没有历史数据时，先跑窄源采集：

```powershell
python multi_source_news.py --source baidu,zhihu --force --parallel 2
```

如果只是想验证生成链路，可以从旧环境复制 `data/news.db`。

### Playwright 相关错误

`playwright` 是浏览器自动化依赖，部分增强采集才需要。普通数据库查询和多数采集源不依赖浏览器。

如果确实要用到浏览器采集：

```powershell
python -m playwright install
```

这一步需要联网，受网络和系统权限影响。

### FastAPI API 启动失败

先确认依赖：

```powershell
python -m pip install fastapi uvicorn
```

启动：

```powershell
python scripts\api.py
```

API 不是生成简报的必需入口。简报链路优先使用 `generate_briefing.py`、`gen_today_v23_briefing.py` 和 `validate_briefing.py`。

## 5. 新 agent 的安全工作顺序

1. 先看 `README.md`、`docs/file-layout.md` 和本文件。
2. 先跑 `git status --short`，不要覆盖已有改动。
3. 先跑 `python -m compileall -q multi_source_news.py scripts sources`。
4. 再跑 `python scripts\nb_query.py --status`。
5. 需要采集时先跑 `--source baidu,zhihu --force --parallel 2`。
6. 生成后必须跑 `scripts\validate_briefing.py` 校验输出。

这样即使环境不完整，也能尽快判断问题出在依赖、数据库、网络源还是输出格式。
