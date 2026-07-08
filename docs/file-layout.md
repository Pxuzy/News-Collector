# News-Collector 文件架构说明

本文档记录当前仓库的文件边界和整理规则。目标是让后续新增代码时先放到合适位置，避免 `scripts/` 继续混入一次性脚本、生成物和长期维护代码。

## 当前主流程

```text
multi_source_news.py
  -> sources/
  -> scripts/store.py
  -> data/news.db
  -> scripts/generate_briefing.py
  -> scripts/gen_today_v23_briefing.py
  -> output/news-YYYY-MM-DD.md
  -> scripts/validate_briefing.py
```

## 目录职责

- `multi_source_news.py`：采集 CLI 入口，负责调度来源、写入数据库、输出采集运行结果。
- `sources/`：平台采集适配器。新增来源应在这里用 `@register` 注册。
- `scripts/core.py`：网络请求、RSS、HTML 清理等底层工具。
- `scripts/store.py`：SQLite schema、迁移、写入、查询、来源状态、统计和清理。
- `scripts/classifier.py`、`scripts/dedup.py`：分类、标签和标题去重能力。
- `scripts/generate_briefing.py`：一键流程入口，串起采集、补齐、生成和校验。
- `scripts/gen_today_v23_briefing.py`：当前 v23 简报生成器。
- `scripts/validate_briefing.py`：当前 v23 输出格式校验器。
- `scripts/api.py`、`scripts/briefing_api.py`、`scripts/nb_query.py`、`scripts/query.py`：不同调用方使用的查询入口。
- `scripts/run_collector_silent.py`、`scripts/run_collector_core.py`：cron/no-agent 采集包装。
- `scripts/health.py`、`scripts/watch.py`、`scripts/extractor.py`、`scripts/fix_data_gaps.py`：运维、监控、正文提取和数据补齐辅助入口。
- `skill/`：给新闻简报 skill 使用的说明和格式参考。
- `config/`：配置文件，例如关键词监控配置。
- `data/`：本地 SQLite 数据库和备份，不作为源码维护。
- `logs/`：采集日志，不作为源码维护。
- `output/`：简报、采集结果、缓存和归档生成物，不作为源码维护。
- `docs/`：项目结构、架构和维护说明。

## 已整理的生成脚本

以下脚本属于按日期或时段生成的一次性版本，已从 `scripts/` 移到 `output/archive/generated-scripts/`：

- `gen_briefing_v23.py`
- `gen_evening_recap.py`
- `gen_recap_2026-07-07.py`
- `gen_recap_today.py`

这些文件已经在 `.gitignore` 中被忽略，不是长期维护入口。以后类似临时生成脚本也应放入 `output/archive/generated-scripts/`，不要放回 `scripts/` 根目录。

## 后续整理边界

在不改变功能的前提下，后续可以逐步做这些拆分：

- 将 `scripts/gen_today_v23_briefing.py` 拆成数据读取、选题、文案规则和 Markdown 渲染几个内部模块，但保留原 CLI 入口。
- 将 `scripts/store.py` 拆成 schema、写入、查询和 source_state 模块，但保留 `scripts/store.py` 的对外导出，避免影响现有 import。
- 合并 `run_collector_silent.py` 和 `run_collector_core.py` 的重复包装逻辑，但保留两个现有命令入口。

拆分前应先跑现有命令验证，拆分后至少验证：

```bash
python scripts/nb_query.py --status
python scripts/generate_briefing.py --skip-collect
python scripts/validate_briefing.py output/news-YYYY-MM-DD.md
```
