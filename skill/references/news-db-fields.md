# news.db 字段映射与已知问题

## 通用

`news.db` 的 `news_items` 表字段：
```
id, source, title, url, heat, category, tags, extra, first_seen, last_seen, seen_count, summary
```

## 各源 heat 字段状态

| 源 | heat 实际内容 | 问题 | 应对 |
|----|-------------|------|------|
| baidu | 两种模式：`store.query()` 返纯数字（如 `39`）；`nb_query.py` 返搜索摘要（200+字） | 接入方式导致 heat 格式不一致；直查时数字是搜索排名编号而非热度值 | 直查模式用 `· 热度：{heat}` 格式（validator 要求每条必含 `热度：` 前缀）；「热搜」等无数字的描述无法通过 validator 检查；MCP hot-news 可补 700万~800万 级排名热度 |
| weibo | 空 / 数字ID | API 返回数字ID（如 7960632）非"万"级热度 | DB 数据写"未获取"；但 **MCP hot-news get_hot_news(platform=weibo) 返回真实 hot_value**（如 132万），优先使用 |
| zhihu | "1223 万热度" 格式 | 标准可用 | 直接使用 |
| douyin | 纯数字串如 `12127398` | 无单位，需自行转为万级 | 转为万级如 `1213万`；URL 用 `douyin.com/hot/...` |
| ithome | 空 | 无热度值 | 写 `热度未获取` |
| hackernews | "873 points" | 标准可用，但 **DB 无 comments/type 字段** | 用 `fix_data_gaps.py --sources hn` 调用 HN Algolia API 补齐 comments（脚本路径 `scripts/fix_data_gaps.py`） |
| github | 纯数字串如 `126584` 或 `⭐126,584` | 真实 Stars 数值，但格式不统一；**DB extra 中无 language 字段** | 用 `fix_data_gaps.py --sources github` 尝试从 GitHub API 获取 language
| aihot / arxiv / huggingface / bbc_world / techmeme | 空 | 均无热度值 | 写 `热度未获取` |
| toutiao / bilibili | 空 | 未存储热度 | 写 `热度未获取` |

## HackerNews 缺失字段

DB 不存储：comments / num_comments / type / hn_url
→ HN 条目统一 `Comments：未获取（DB无此字段）`
→ 类型由生成时根据标题关键词判断

## GitHub extra 字段

`extra` 是 **JSON 字符串**（不是 dict），需 `json.loads()` 解析后才能访问字段。常见结构：
```json
{"info":"⭐14,685","hover":"项目描述文本...","source":"🐙GitHub"}
```

**重要**：
1. `extra` 是字符串不是 dict — 直接 `item.get('extra', {}).get('language')` 会报 AttributeError。必须先 `json.loads(item.get('extra', '{}'))`。
2. `language` 字段**不是稳定存在的**。实测发现 extra 中只有 `info`、`hover`、`source` 三个 key，不包含 `language`。语言数据必须从 `fix_data_gaps.py` 缓存获取（该脚本通过 GitHub API 动态补齐）。
3. `github_weekly` store 源始终返回 0 — **周榜数据不由 store 提供**。`fix_data_gaps.py` 的 `fetch_github_weekly()` 直接从 GitHub Trending Weekly HTML 页面抓取（支持 SSL 重试），写入 `_data_gaps_cache.json`。

**数据补齐管线**：
- 采集器 → `fix_data_gaps.py` → `_data_gaps_cache.json`
- 缓存路径：`E:\\hermes\\profiles\\news-collector\\cron\\output\\_data_gaps_cache.json`
- 缓存结构：`{github_language: {owner/repo: {language, stars, topics}}, github_weekly: [{repo, stars, description}]}`
- 简报 cron 从该缓存读取补齐的 GitHub 语言和周榜，而非从 store 直接取

**预检策略**：
- Stars 字段（`heat`）通常有值 — 有 Stars 即可视为有效条目
- language 作为补充信息，缺失时写 `语言未获取` 并计入数据缺口
- 有效条目 ≥ 5 条即可生成 GitHub 板块，不要求 ≥ 10

## 数据时间

`last_seen` 是 ISO 8601 带时区：`2026-06-30T02:19:32.967164+08:00`
同批采集的各源 last_seen 基本一致，取任意一条即可。

## 预检需知（配合 SKILL.md 第 0 步使用）

生成前必须执行的数据预检清单：
1. **GitHub**: 检查 Stars 字段（`heat`）非空。language 缺失可接受但需在数据缺口中说明
2. **HN**: 检查 `heat` 是否有 Points 值
3. **论文**: 检查 `url` 是否为 arXiv 链接（含 `arxiv.org/abs/`）
4. **国内各子板块**: 检查每个分类是否 ≥ 3 条可用数据
5. **不足处理**: 补充后仍不足的板块保留标题写"数据不足，跳过"，在数据缺口中说明原因
