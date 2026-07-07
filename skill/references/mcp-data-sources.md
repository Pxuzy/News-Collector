# MCP 数据源参考（采集于 2026-06-29 首轮工作）

本文件记录 hot-news MCP 服务器 (mcp_hot_news_*) 各平台数据源的实际返回特征，帮助后续会话快速判断哪些源可用、哪些是模拟数据、字段如何映射。

## 国内平台

| 平台 | 数据质量 | 字段特征 | 备注 |
|------|---------|---------|------|
| **微博热搜** | 真实 | hot_value=热度数值, rank=排名, url=微博搜索链接 | 热度值可靠，链接可用 |
| **百度热搜** | 真实 | hot_value=热度数值(700万~800万), rank=排名, url=百度搜索链接 | 热度值可靠，description 含事件摘要 |
| **抖音热点** | 真实 | hot_value=热度数值(百万~千万级), rank=排名 | url 为抖音搜索链接，非原始榜单页 |
| **今日头条** | 真实 | hot_value=热度数值(千万级), rank=排名 | url 含超长追踪参数，可直接使用 |
| **B站热门** | 真实 | hot_value=热度数值, rank=排名 | url 为 B站搜索链接，非原始榜单页 |
| **IT之家** | 真实 | hot_value=0(不可用), rank=排名, url=IT之家文章链接 | **热度值始终返回 0，不能用作排序依据**；链接和描述可用 |
| **知乎热榜** | ⚠️ 模拟数据 | hot_value=800~1000, description="这是知乎热榜的模拟热点内容" | `source` 字段标注 "(模拟数据)"。**不可用** |
| **虎扑热帖** | ⚠️ 模拟数据 | 同上模式 | **不可用** |
| **豆瓣热门** | ⚠️ 模拟数据 | 同上模式 | **不可用** |

## 全球/国际平台

| 平台 | 数据质量 | 字段特征 | 备注 |
|------|---------|---------|------|
| **Trendshift Daily** | 真实（GitHub） | hot_value=**语言**(如"Python"/"TypeScript"), rank=排名, description=项目描述 | **注意：hot_value 存的是编程语言，不是热度数值**。Stars 数/今日增长不可用 |
| **Trendshift Weekly** | 真实（GitHub） | 规则同上 | 同上 |
| **Google Trends** | ⚠️ 模拟数据 | hot_value=800~1000 | source 标注 "(模拟数据)"，**不可用** |
| **NewsAPI** | ⚠️ 模拟数据 | 同上模式 | **不可用** |
| **Reddit** | ⚠️ 模拟数据 | 同上模式 | **不可用** |
| **Twitter/X** | ⚠️ 模拟数据 | 同上模式 | **不可用** |

## 数据源要点总结

1. **可用的国内真实源**：微博、百度、抖音、头条、B站、IT之家（IT之家热度值不可用，但文章链接和描述可用）
2. **不可用的源**：知乎、虎扑、豆瓣、Google Trends、NewsAPI、Reddit、Twitter/X——一律返回模拟数据，必须标注在数据缺口
3. **GitHub Trending（Trendshift）字段怪癖**：
   - `hot_value` 字段存储的是**编程语言**（如 "Python"），不是 Stars 数
   - 没有 Stars 数字段、没有今日增长字段
   - description 可用且有价值
   - 周榜（Trendshift Weekly）和日榜（Trendshift Daily）内容不同，实际生成时**同时使用两条**（日榜前10 + 周榜前10，去重）。
4. **缺失的源类型**：
   - HackerNews：无 MCP 数据源接入
   - arXiv/论文：无 MCP 数据源接入
   - Twitter/X 趋势：模拟数据
5. **数据缺口处理**：不可用的源和缺失的指标（Stars数、HN Points/Comments）必须显式写入 `🧩 数据缺口` 栏目，不可省略

## GitHub 条目字段规范

从 Trendshift 获取的 GitHub 数据缺 Stars 数，因此：

1. **优先从 news.db 数据库获取（推荐）**  
   `python scripts/nb_query.py --sources github --limit 10`  
   自动管理 2 小时新鲜度，返回真实 Stars 数值（含 heat 字段）。
2. 桥接成功后使用真实 Stars（如 `⭐ 14,782`）
3. 桥接失败时 Stars 写 `Stars未获取`
4. 语言从 hot_value 读取
5. 描述从 description 读取
6. 必须补写 `🧩 是干嘛的` 字段（validator 会检查此项且要求至少 40 字）

## 🔧 数据缺口弥补方案

**首选：从 news-toolkit 数据库获取（推荐）**

DB 位置：`E:\\hermes\\workspace\\news-toolkit\\data\\news.db`
桥接脚本：`scripts/nb_query.py`（自动管理 2 小时新鲜度）

```bash
# 查 GitHub（含真实 Stars）
python scripts/nb_query.py --sources github --limit 10

# 查 HN（含 Points）
python scripts/nb_query.py --sources hackernews --limit 10

# 查论文（含 arXiv 摘要）
python scripts/nb_query.py --sources arxiv --limit 10

# 查国际新闻
python scripts/nb_query.py --sources bbc_world,googlenews,reuters --limit 10

# 查 AIHOT
python scripts/nb_query.py --sources aihot --limit 10
```

详见 `references/news-toolkit-integration.md`。
