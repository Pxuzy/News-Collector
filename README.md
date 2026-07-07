# 📰 News-Collector — 新闻采集 + 简报生成 一站式项目

一个独立自包含的新闻管道项目：**多源采集 → 数据补齐 → 简报生成 → 校验 → 投递**

- 🏗 采集引擎：50 源并行抓取（微博/百度/抖音/头条/知乎/GitHub/HN/arXiv…）
- 🧹 数据补齐：HN Points/Comments、GitHub language/Stars、周榜自动补全
- 📄 简报格式：v23 标准（`**粗体**` + `>` 引用块 + 彩色圆点）
- 🚀 一键全流程：`python scripts/generate_briefing.py`

## 项目结构

```
news-pipeline/
├── multi_source_news.py       ← 采集器入口（50/32源）
├── store.py                   ← DB 查询接口
├── sources/                   ← 各平台抓取模块（11个）
├── data/
│   └── news.db                ← SQLite 数据库
├── scripts/
│   ├── run_collector_silent.py   全量50源采集（no_agent cron 用）
│   ├── run_collector_core.py     核心~30源采集（no_agent cron 用）
│   ├── fix_data_gaps.py          HN/GitHub 数据补齐
│   ├── nb_query.py               DB 查询桥接
│   ├── generate_briefing.py      一键生成简报
│   └── validate_briefing.py      MD文件校验
├── skill/
│   ├── SKILL.md               简报格式规则（v23标准）
│   ├── references/            模板/指南/架构文档
│   └── templates/             生成脚本模板
├── output/                    输出目录（简报.md + 缓存）
├── config/
│   └── watch_keywords.json    监控关键词
├── requirements.txt
└── README.md
```

## 快速开始

### 采集新闻
```bash
# 全量采集（50源，~120s）
python multi_source_news.py --parallel 8 --prune

# 核心采集（~30源，~60s）
python multi_source_news.py --core --parallel 8 --prune
```

### 查询数据
```bash
python scripts/nb_query.py --status
python scripts/nb_query.py --sources weibo,baidu,zhihu
```

### 补齐数据缺口（HN Points + GitHub language + 周榜）
```bash
python scripts/fix_data_gaps.py
```

### 一键全流程（推荐）
```bash
python scripts/generate_briefing.py
```
等价于：采集 → 补齐 → 生成简报 → 校验 → 保存到 output/

### 查看简报
生成的文件在 `output/news-YYYY-MM-DD.md`

## 数据补齐缓存

`output/_data_gaps_cache.json`:
- `hn_comments` → HN Points + Comments（Algolia API）
- `github_language` → 热榜仓库语言 + Stars（GitHub API）
- `github_weekly` → 周榜TOP10（HTML爬取）

## 依赖

- Python 3.10+
- `pip install feedparser httpx beautifulsoup4`
- 各源详见 `requirements.txt`

## 输出格式

v23 标准：`**粗体标题**` + `>` 引用块 + 彩色圆点 + 每条含链接/排名/热度/💡解读
详见 `skill/references/confirmed-format-template.md`
