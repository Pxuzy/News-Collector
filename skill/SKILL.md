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
last_updated: 2026-07-13
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

## 采集失败与发布判定

- `generate_briefing.py` 将采集和数据补齐视为尽力而为步骤：某些源失败时仍继续使用已经写入 SQLite 的数据生成简报，并在日志中披露失败。只有简报生成失败，或 `validate_briefing.py`、普通质量门禁、严格模板门禁任一失败，才阻断临时文件发布并返回非零。这样既不会因为单个外部源短暂不可用而丢失整版简报，也不会降低正式交付的三重质量门禁。

- 所有 Markdown 链接的 URL 必须经过统一编码：空格和非 ASCII 字符使用百分号编码，保留协议、查询参数和路径结构；不能直接把微博等来源的原始中文查询 URL 拼入 Markdown。

不再维护无引用模板；新增格式规则写入 `skill/references/`，不要新增 `skill/templates/`。

## v23 格式底线

- 不使用 `#` / `##` / `###` 标题。
- 不使用 `---` 分隔线、表格、代码块。
- 每条新闻需要链接、来源/排名、热度、解读。
- 文件只用 LF 换行。

格式细节以 `skill/references/confirmed-format-template.md` 和 `scripts/validate_briefing.py` 为准。

## GitHub 描述质量规则

- GitHub 日榜、周榜和编辑推荐中的项目简介必须使用中文，不能直接输出 API 返回的英文 `description`。
- 中文简介必须与仓库实际用途一致；不能因为命中宽泛关键词（例如 `claude code`）就把代码审查工具误写成求职工具。
- 生成器应优先使用仓库级准确映射，再使用有边界的关键词兜底；无法确认用途时明确写“需结合 README 核验”，不得编造功能。
- 交付前人工检查 GitHub 栏目，质量脚本通过不等于已经完成语义检查。
- HN 和论文标题必须优先转换为中文；未知英文标题使用中文保守兜底，不能把整句英文直接放进标题或解读字段。
- 当 HN 标题只能退化为「技术社区讨论：原文标题见链接」时，必须在 `add_hn_item()` 中追加中文序号，避免同一板块的事件、影响和解读字段完全重复并触发严格模板门禁；原始标题通过链接保留。
- 国外热点标题也必须经过离线中文化；无法翻译时使用带序号的中文占位，不能把 Reuters/BBC 等源的英文标题直接输出。
- 简报版次按中国标准时间动态生成：11:00 前为早间版，11:00–15:59 为午间版，16:00 后为晚间版，不能把早晨采集结果固定标成晚间版。
- HN 的事件和讨论信号字段也要使用中文，`points`/`Comments` 等字段应转换为“积分/评论”。
- 推荐 AI 动态若来自 HN，也必须复用 HN 中文标题转换逻辑，不直接输出英文标题。
- GitHub 推荐、日榜、周榜和“机会”栏目只保留 Stars 不低于 100,000 的项目；低于门槛时显示数据缺口，不用中小项目凑数。

## 今日要点事件级去重

- `unique()` 的 URL、标题相似度和公共 2-gram 去重不足以处理“台风巴威实时路径 / 巴威路线东移”这类同事件短标题；今日要点和今日主线必须调用 `dedup_event_items()`。
- 事件去重应先建立候选池，再做事件聚类，最后从未重复的不同事件补位；不能先截取 5/6 条再去重，否则同一事件会占满今日要点。
- 泛类词（如“台风”“救援”“事故”）只有在候选池能唯一推断出具体事件词时才能作为桥接；无法唯一推断时不得把不同事件合并。
- 交付前人工检查 `📌 今日要点`：同一事件最多保留一个代表条目，并重新运行 validate、普通质量门禁和 `--strict`。
