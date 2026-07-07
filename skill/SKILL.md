---
name: news-collector
title: 新闻采集与 v23 简报生成
description: 多源新闻采集、SQLite 入库、数据补齐、v23 Markdown 简报生成与校验。
triggers:
  - 新闻
  - 热点
  - 今日热点
  - 新闻简报
  - 日报
  - 热榜
  - GitHub 趋势
  - HackerNews
  - HN
  - 论文
  - AI 前沿
last_updated: 2026-07-08
---

# News-Collector

项目根目录：`E:/hermes/workspace/News-Collector`

## 主流程

```text
multi_source_news.py
-> data/news.db
-> scripts/fix_data_gaps.py
-> scripts/gen_today_v23_briefing.py
-> output/news-YYYY-MM-DD.md
-> scripts/validate_briefing.py
```

推荐入口：

```bash
python scripts/generate_briefing.py
```

只用现有数据库生成当天 v23 简报：

```bash
python scripts/gen_today_v23_briefing.py
python scripts/validate_briefing.py output/news-YYYY-MM-DD.md
```

## 文件归类

- `sources/`：平台采集适配器，使用 `@register` 注册。
- `scripts/store.py`：SQLite schema、写入、查询、状态与去重。
- `scripts/core.py`：请求、RSS、HTML 基础工具。
- `scripts/classifier.py`：分类和标签。
- `scripts/generate_briefing.py`：一键流程编排。
- `scripts/gen_today_v23_briefing.py`：唯一 v23 简报生成器。
- `scripts/validate_briefing.py`：唯一格式校验器。
- `skill/references/`：格式、字段和操作说明。
- `output/`：生成物和缓存，不当作源码维护。

不再维护无引用模板；新增格式规则写入 `skill/references/`，不要新增 `skill/templates/`。

## v23 格式底线

- 不使用 `#` / `##` / `###` 标题。
- 不使用 `---` 分隔线、表格、代码块。
- 每条新闻需要链接、来源/排名、热度、解读。
- 文件只用 LF 换行。

格式细节以 `skill/references/confirmed-format-template.md` 和 `scripts/validate_briefing.py` 为准。
