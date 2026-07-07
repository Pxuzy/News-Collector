---
name: news-pipeline
title: 📰 新闻全管道 — 采集→补齐→简报→校验→投递
description: 独立自包含的新闻管道项目。采集引擎 + 数据补齐 + v23简报生成 + 校验 + MEDIA投递，全部在一个项目里。
triggers:
  - 新闻
  - 热点
  - 今日热点
  - 新闻简报
  - 今天有哪些热门新闻
  - 日报
  - 热榜
  - GitHub 趋势
  - HackerNews
  - HN
  - 论文
  - AI 前沿
last_updated: 2026-07-04-v1
---

# 📰 news-pipeline — 新闻全管道

独立自包含项目：`E:\hermes\workspace\News-Collector\`

## 全链路

当用户问「今天有哪些热门新闻」时自动执行：

```
① 检查 news.db 新鲜度
② 数据过期 → multi_source_news.py 采集
③ fix_data_gaps.py 补齐（HN/GitHub）
④ 查询全平台数据
⑤ 生成 v23 格式 .md 简报
⑥ validate_briefing.py 校验
⑦ MEDIA 发送文件
```

全程不提问确认，一次性交付。

## 项目结构

```
news-pipeline/
├── multi_source_news.py      ← 采集器（50/32源）
├── store.py                  ← DB 查询
├── sources/                  ← 各平台源模块
├── data/news.db              ← SQLite 数据库
├── scripts/
│   ├── run_collector_silent.py    ← 全量采集包装
│   ├── run_collector_core.py      ← 核心采集包装
│   ├── fix_data_gaps.py           ← 数据补齐
│   ├── nb_query.py                ← DB 桥接
│   ├── generate_briefing.py       ← 一键全流程
│   └── validate_briefing.py       ← 校验
├── skill/                     ← 简报格式规则
│   ├── SKILL.md
│   ├── references/            ← 模板/指南
│   └── templates/             ← 生成脚本模板
└── output/                    ← 简报输出
```

## 快速命令

```bash
# 一键全流程（推荐）
cd E:/hermes/workspace/news-pipeline
python scripts/generate_briefing.py

# 或分步
python multi_source_news.py --core --parallel 8 --prune   # 采集
python scripts/fix_data_gaps.py                            # 补齐
python scripts/nb_query.py --sources all --limit 10        # 查询
python scripts/validate_briefing.py output/news-*.md       # 校验
```

## 格式规则（v23）

- **禁止** `#`/`##`/`###` ATX 标题 → 改用 `**粗体标题**`
- **禁止** `---` 分隔线、表格、代码块
- 每条新闻用 **1 个 `>` 引用块**，字段间尾部双空格换行
- 论文例外：各字段独立 `>` 块
- 文件只含 `\\n`（LF），不含 `\\r`（CR）
- 所有条目必须有链接、排名、热度、💡解读

详见 `skill/references/confirmed-format-template.md`

## Cron

| 任务 | 模式 | 脚本位置 |
|------|------|---------|
| news-toolkit-collector (55 6,18) | no_agent | profiles/scripts/run_collector_silent.py |
| news-toolkit-core-collector (55 12) | no_agent | profiles/scripts/run_collector_core.py |
| enhanced-news-briefing (0 7,13) | Agent | prompt 驱动 |
| evening-news-recap (0 19) | Agent | prompt 驱动 |
