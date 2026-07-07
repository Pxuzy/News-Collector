# news-toolkit 数据库集成指南

## 项目信息

- **位置**: `E:\hermes\workspace\news-toolkit`
- **DB**: `data/news.db` — SQLite，50+ 源，1354+ 条（截至 2026-06-30）
- **采集器**: `scripts/multi_source_news.py`（并行 6 线程，自动写入 DB）
- **桥接脚本**: `scripts/nb_query.py`（自动管理 2 小时新鲜度）

## 核心工作流

**原则**：先查 DB，再决定要不要抓。不每次重新跑采集。

```
你要简报
  ↓
python scripts/nb_query.py --sources <分组> --limit <N>
  ├─ DB 数据 < 2 小时 → 直接返回 JSON
  └─ DB 数据 > 2 小时 → 先跑 multi_source_news.py → 再返回 JSON
  ↓
拿到 items[] → 走 telegram-news-briefing 分段格式输出
```

## 桥接脚本 nb_query.py 用法

```
python scripts/nb_query.py --status                           # 数据库统计
python scripts/nb_query.py --sources all --limit 30           # 全量数据
python scripts/nb_query.py --sources weibo,baidu --limit 10   # 特定源
python scripts/nb_query.py --sources domestic                 # 国内源分组
python scripts/nb_query.py --sources intl                     # 国际源分组
python scripts/nb_query.py --sources ai                       # AI/学术源分组
python scripts/nb_query.py --sources all --refresh            # 强制刷新+查
python scripts/nb_query.py --category 社会 --limit 10         # 按分类过滤
```

### 源分组

| 分组 | 包含的源 |
|------|---------|
| `domestic` | baidu, weibo, douyin, toutiao, zhihu, bilibili, bilibili_pop, thepaper, tieba, hupu, ithome, ifeng, 36kr, tencent, v2ex, sspai, douban |
| `intl` | hackernews, reddit, github, bbc_world, guardian, aljazeera, reuters, france24, googlenews 系列 |
| `ai` | aihot, huggingface, arxiv, tldr_ai, producthunt, lobsters, devto, openai_blog, techcrunch, techmeme, arstechnica, wired, tmtpost, juejin, wallstreetcn, jin10, xueqiu 等 |
| `all` | 上述全部 |

## 输出 JSON 格式

```json
{
  "meta": {
    "db_path": "E:\\...\\news.db",
    "fresh_hours": 2,
    "refreshed": false,
    "returned": 30
  },
  "total": 872,
  "items": [
    {
      "source": "weibo",
      "title": "标题",
      "url": "https://...",
      "heat": "热度值或摘要",
      "category": "综合/科技/社会/财经/AI/国际/体育/娱乐/时政/健康/教育",
      "first_seen": "2026-06-30T02:19:32+08:00",
      "last_seen": "2026-06-30T02:19:32+08:00",
      "seen_count": 1,
      "tags": "[]"
    }
  ]
}
```

## 分类说明

`news.db` 已由 `classifier.py` 自动分类。各分类含义：

| 分类 | 说明 |
|------|------|
| 综合 | 未进入特定分类的热榜条目 |
| 科技 | 科技/数码/互联网 |
| 社会 | 社会民生/公共事件 |
| 财经 | 财经/商业/市场 |
| AI | AI/大模型/机器学习 |
| 国际 | 国际政治/外交/军事 |
| 体育 | 体育赛事/运动 |
| 娱乐 | 综艺/影视/明星 |
| 时政 | 政治/政策/法规 |
| 健康 | 医疗/健康/疫情 |
| 教育 | 教育/高考/学术 |

## 常见问题

### Q: 数据不够新鲜怎么办？
A: `nb_query.py` 自动检测。加 `--refresh` 强制重新采集。

### Q: 某个源在 DB 里没有？
A: 检查 `--status` 输出中的 by_source 列表。如果缺失，先确认 `multi_source_news.py` 的 sources 注册表中是否有该源。

### Q: 想查历史数据？
A: `store.query()` 支持 keyword/days/source/category 过滤。直接跑：
```python
python -c "import sys; sys.path.insert(0, r'E:\\hermes\\workspace\\news-toolkit\\scripts'); from store import query; rows,total=query(keyword='DeepSeek', days=7); [print(r['title']) for r in rows]"
```

## 废弃的源

以下旧方法已不再使用：
- ~~`scripts/fetch_workspace_sources.py`~~ → 用 `nb_query.py`
- ~~`E:\hermes\workspace\news-aggregator-skill\scripts\enhanced_news.py`~~ → 用 `nb_query.py`
- ~~MCP hot-news 作为主数据源~~ → 仅作备选
