# News-Collector

多源新闻采集与 v23 简报生成项目。

主流程只有一条：

`multi_source_news.py` -> `data/news.db` -> `scripts/generate_briefing.py` -> `output/news-YYYY-MM-DD.md` -> `scripts/validate_briefing.py`

## 目录职责

```text
News-Collector/
├── multi_source_news.py          采集入口，调度 sources 并写入 SQLite
├── sources/                      平台采集适配器，统一通过 @register 注册
├── scripts/
│   ├── core.py                   网络请求、RSS、HTML 清理等基础能力
│   ├── store.py                  SQLite schema、写入、查询、去重状态
│   ├── classifier.py             分类与标签
│   ├── dedup.py                  标题相似度去重工具
│   ├── structured_log.py         控制台与 JSONL 日志
│   ├── generate_briefing.py      一键流程：采集/补齐/生成/校验
│   ├── gen_today_v23_briefing.py v23 简报生成器
│   ├── validate_briefing.py      简报格式校验
│   ├── fix_data_gaps.py          HN/GitHub 数据补齐
│   ├── nb_query.py               Hermes/CLI 查询桥接
│   ├── query.py                  人工查询 CLI
│   ├── api.py                    FastAPI 查询接口
│   ├── briefing_api.py           简报用结构化查询接口
│   ├── health.py                 健康看板
│   ├── watch.py                  关键词监控
│   ├── extractor.py              正文提取辅助脚本
│   ├── run_collector_silent.py   全量 cron 包装
│   └── run_collector_core.py     核心源 cron 包装
├── skill/
│   ├── SKILL.md                  简报生成规则
│   └── references/               v23 格式、校验、数据字段说明
├── data/news.db                  SQLite 数据库
├── output/                       生成简报、采集报告和缓存
├── docs/file-layout.md           文件架构与整理边界说明
├── docs/setup.md                 新环境安装、运行和排障说明
├── docs/docker.md                Docker 部署说明
├── Dockerfile                    容器镜像构建文件
├── docker-compose.yml            Docker Compose 服务定义
├── config/watch_keywords.json    监控关键词
└── requirements.txt
```

## 常用命令

新机器或新 agent 接手时，先看 `docs/setup.md`。
Docker 部署见 `docs/docker.md`。

```bash
python multi_source_news.py --parallel 8 --prune
python multi_source_news.py --core --parallel 8 --prune
python scripts/generate_briefing.py
python scripts/gen_today_v23_briefing.py
python scripts/validate_briefing.py output/news-YYYY-MM-DD.md
python scripts/nb_query.py --status
```

## Docker

```bash
docker compose build
docker compose run --rm app python multi_source_news.py --source baidu,zhihu --force --parallel 2
docker compose run --rm app python scripts/generate_briefing.py --skip-collect
docker compose up -d api
```

## 新文件归类规则

更完整的目录边界见 `docs/file-layout.md`。

- 新平台采集源放到 `sources/`，并在模块内用 `@register` 注册。
- 数据库 schema、写入、查询、去重状态放到 `scripts/store.py`。
- 简报格式与内容生成只走 `scripts/gen_today_v23_briefing.py`。
- 一键执行流程只放到 `scripts/generate_briefing.py`。
- 给 Hermes/CLI/HTTP 调用的查询入口分别放到 `nb_query.py`、`query.py`、`api.py`、`briefing_api.py`。
- cron 包装只保留 `run_collector_silent.py` 和 `run_collector_core.py`。
- 生成物只进 `output/`，不要把生成物当源码维护。
- 不再新增无引用模板；格式规则写到 `skill/references/`。

## 输出格式

当前标准是 v23：粗体栏目标题、引用块字段、彩色圆点、每条包含链接/来源排名/热度/解读。格式细节以 `skill/references/confirmed-format-template.md` 和 `scripts/validate_briefing.py` 为准。
