# 数据访问模式总结

本 skill 有两种数据获取方式，分别适用于不同场景。

## 方式一：nb_query.py（推荐，自动管理新鲜度）

```bash
# 查看数据状态
python scripts/nb_query.py --status

# 查全量数据（自动检查 < 2h 新鲜度，过期自动采集）
python scripts/nb_query.py --sources all --limit 30

# 查特定源
python scripts/nb_query.py --sources weibo,baidu,zhihu --limit 10

# 强制刷新
python scripts/nb_query.py --sources all --refresh
```

**输出格式**：单源或多源输出略有不同。
- `--sources all` → 返回 `{items: [...], total: N, meta: {...}}` 
- `--sources src1,src2` → 返回 `{src1: [...], src2: [...], meta: {...}}`

**注意**：`--sources all` 返回的 items 是一个扁平数组。`--sources src1,src2` 返回的是按 source 分组的字典。

## 方式二：store.query()（当 nb_query 超时或管道解析失败的兜底）

当 nb_query.py 数据过期触发采集（~60s）导致超时，或管道传输 JSON 被 `[nb_query]` 前缀行阻断时，直接调用 store 层：

```python
import sys
sys.path.insert(0, r'E:\hermes\workspace\news-toolkit\scripts')
from store import query

# 单源查询（store.query 仅支持单源）
items, total = query(source='baidu', days=1, limit=10)

# 多源需循环
for src in ['toutiao', 'weibo', 'zhihu', 'douyin']:
    items, total = query(source=src, days=1, limit=10)
```

**注意**：`items` 中的 `source` 字段是 news.db 的内部源名（如 `'baidu'`），不是显示名（如 `'百度'`）。

## 各源 heat 字段处理

| 源 | heat 内容 | 处理方式 |
|----|----------|---------|
| baidu | 200+字搜索摘要 | 截断30字+...，或直接省略数值 |
| weibo | 数字ID | 写"热度未获取（微博API返回热度为数字ID）" |
| zhihu | "xxx 万热度" | 直接使用 |
| douyin | 纯数字 | 转为万级（12127398→1213万） |
| toutiao | "xxx万"格式 | 直接使用 |
| ithome/bilibili | 空 | 写"热度未获取" |
| hackernews | "xxx points" | 直接使用 |
| github | "⭐xxx,xxx"或纯数字 | 加⭐前缀使用 |

## 已知问题

1. **nb_query 输出含前缀行**：输出以 `[nb_query] Data is fresh...` 开头，后面才是 JSON。解析JSON时需要跳过第一行。
2. **管道传输大JSON会失败**：当 items 过多时（如 `--limit 30` + `--sources all` 返回1000+条），管道 `| python -c` 可能解析失败。建议保存到文件后再处理。
3. **store.query() 只能单源**：不支持逗号分隔的多源查询。
4. **数据新鲜度2小时**：`multi_source_news.py --core` 采集约60秒，全量约120秒。
