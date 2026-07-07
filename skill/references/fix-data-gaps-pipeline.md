# fix_data_gaps 数据补齐管线（2026-07-02 v2）

## 作用

采集器入库后，news.db 的部分字段是空的或不完整的。`fix_data_gaps.py` 从外部 API 动态补齐这些缺口，写入 `_data_gaps_cache.json`，供 Agent 简报生成时读取。

## 补齐范围

| 缺口 | DB 现状 | 补齐方式 | API |
|------|---------|---------|-----|
| HN Points/Comments | `hackernews` 源 `heat` 存的是 points 但未格式化 `comments` | Algolia API 实时抓取前 15 条 | `hn.algolia.com` |
| GitHub language/Stars | GitHub 采集器不存 `language`，`extra` JSON 只有 `info`(Stars) 和 `hover`(描述) | GitHub API 查指定仓库 | `api.github.com/repos/{repo}` |
| GitHub 周榜 | `github_weekly` store 源为 0（采集器未实现） | 直接爬 GitHub Trending Weekly 页面 | `github.com/trending?since=weekly` |

## 工作流

```python
采集器完成 (run_collector_silent.py / run_collector_core.py)
  ↓ 自动调用
fix_data_gaps.py --sources all
  │
  ├── fetch_hn_comments()        → Algolia API → hn_comments[]
  │
  ├── get_trending_repos_from_db()  → store.query('github')
  │     ↓ 读取 DB 中实际 trending repos
  │   fetch_all_github_repos()   → GitHub API → github_language{}
  │
  └── fetch_github_weekly()      → 爬 gh trending weekly → github_weekly[]
        ↓ 补 language（不在日榜中的新仓库）
      fetch_all_github_repos()   → 追加到 github_language{}
        ↓
  _data_gaps_cache.json ← 所有数据
```

### GitHub 补齐为什么是动态的（v2 核心改进）

**v1**：写死了 10 个仓库如 `simplex-chat/simplex-chat`，和每日实际热榜完全不搭边。

**v2**：从 news.db 读取当天实际 trending repos → 只补语言/Stars → 写入缓存。

```python
def get_trending_repos_from_db(limit=10):
    """从 news.db 读取实际 GitHub 日榜热 repo"""
    conn = sqlite3.connect(NEWS_DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT title, url FROM news_items
        WHERE source = 'github'
        ORDER BY first_seen DESC LIMIT ?
    """, (limit,))
    # 从 title 提取 owner/repo 格式
    ...
```

### 周榜爬取的注意事项

1. **分块读取**：GitHub Trending Weekly 页面 > 600KB，`urllib.request.urlopen().read()` 会 `IncompleteRead`。必须分 64KB chunks 读取后拼接。
2. **SSL 重试**：Anaconda Python 连接 GitHub 间歇 `SSLEOFError`，需 3 次重试 + 3s 退避。
3. **只匹配 `<h2>` 内链接**：GitHub 页面内还有 `sponsors/xxx`、`/trending/xxx` 等非仓库链接。必须限定 `href` 在 `<h2>` 标签内。

### 缓存文件的使用

简报 cron 的 Agent prompt 中应包含：

> 读取 `E:/hermes/profiles/news-collector/cron/output/_data_gaps_cache.json` 获取补齐后的 HN Points/Comments 和 GitHub language/Stars。

GitHub 条目的 `extra` 字段是 JSON 字符串，需要 `json.loads()` 解析。解析后也**没有 `language`**——语言必须从缓存读取。

## 路径

- 补齐脚本：`E:/hermes/profiles/news-collector/scripts/fix_data_gaps.py`
- 缓存文件：`E:/hermes/profiles/news-collector/cron/output/_data_gaps_cache.json`
- 采集包装脚本：`E:/hermes/profiles/news-collector/scripts/run_collector_silent.py`
- 核心采集包装：`E:/hermes/profiles/news-collector/scripts/run_collector_core.py`

## 已知限制

1. **GitHub API 限速**：未认证请求 60 次/小时。当前日榜 5 个 + 周榜 5 个 = 10 次，在限额内。
2. **SSL 间歇失败**：Anaconda Python 的 `urllib` 连接 GitHub 偶发 SSL EOF，重试 3 次后仍失败则跳过该仓库，不阻塞整体流程。
