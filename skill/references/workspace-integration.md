# Workspace 集成指南（已废弃）

> ⚠️ **2026-06-30 起废弃**。`news-toolkit` 项目已取代此项目作为主数据源。
>
> 替代方案：
> - **`news-toolkit` DB**（主）：`python scripts/nb_query.py --sources all`
> - **旧版 enhanced_news.py**（备选）：`python E:\hermes\workspace\news-aggregator-skill\scripts\enhanced_news.py`

## 仅有的保留场景

| 场景 | 命令 |
|------|------|
| news-toolkit 依赖未安装 | `python E:\hermes\workspace\news-aggregator-skill\scripts\enhanced_news.py` |
| 需要验证某个单独源的数据 | `python scripts/nb_query.py --sources github,hackernews --refresh` |
| 快速查看旧版输出格式 | 运行 `enhanced_news.py` 看 Markdown 输出 |

**不要**在此文件中查询工作流细节。详见 `references/news-toolkit-integration.md`。
