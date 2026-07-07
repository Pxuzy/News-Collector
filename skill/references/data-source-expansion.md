# 数据源扩展调研（2026-06-29）

> ⚠️ **注意**：本节描述的源大部分已被 `news-toolkit` DB 覆盖。
> 优先从 DB 获取（`nb_query.py --sources ai,techcrunch,openai`），DB 没有才手动抓取。

## 用户要求的泛AI/科技信息源

### 国外源

| 源 | 状态 | 获取方式 | 备注 |
|----|------|---------|------|
| OpenAI 官方博客 | ✅ 可访问 | `https://openai.com/blog/rss.xml` (RSS) | 621KB XML，内容完整 |
| Anthropic 官方博客 | ⚠️ 需验证 | `https://www.anthropic.com/research/rss.xml` | RSS路径可能不同 |
| Google AI 博客 | ⚠️ 需验证 | `https://blog.google/technology/ai/rss/` | 可能返回HTML而非RSS |
| Hacker News | ✅ 已有 | `fetch_hackernews()` - Algolia API | points+comments完整 |
| TechCrunch | ❌ 超时 | `https://techcrunch.com/feed/` | 代理环境超时 |
| Ars Technica | ✅ 可访问 | `https://feeds.arstechnica.com/arstechnica/index` (RSS) | 76KB XML |
| Wired | ⚠️ 需验证 | `https://www.wired.com/feed/rss` | 可能需Playwright |
| MIT Tech Review | ⚠️ 需验证 | `https://www.technologyreview.com/feed/` | 可能需Playwright |
| Techmeme | ⚠️ 需验证 | `https://www.techmeme.com/` | 非标准RSS，需网页抓取 |
| Grok API (X平台) | ❌ 需API key | xAI API | 需配置 `XAI_API_KEY` |

### 国内源

| 源 | 状态 | 获取方式 | 备注 |
|----|------|---------|------|
| IT之家 | ✅ 已有 | `fetch_ithome()` - RSS | 链接+描述可用，热度=0 |
| 36氪 | ✅ 可访问 | `https://36kr.com/feed` (RSS) | 122KB RSS，内容完整 |
| 虎嗅 | ❌ 超时 | `https://www.huxiu.com/rss/0.xml` | 代理环境超时 |
| 钛媒体 | ✅ 可访问 | `https://www.tmtpost.com/rss.xml` (RSS) | 259KB RSS |
| 机器之心 | ⚠️ 可访问但非标准 | `https://www.jiqizhixin.com/rss` | 返回HTML 6KB，需解析 |
| 量子位 | ✅ 可访问 | `https://www.qbitai.com/feed` (RSS) | 64KB RSS |
| APPSO（爱范儿） | ✅ 可访问 | `https://www.ifanr.com/feed` (RSS) | 442KB RSS |
| 硅星人 | ⚠️ 需网页抓取 | `https://www.svr.vc/` | 无标准RSS |

## 实现方案

### 方案 A：RSS 直接抓取（推荐，适用于可访问源）
使用 `fetch_rss()` 通用函数，传入 RSS URL 和源名称即可。

已验证可用的 RSS：
```python
RSS_SOURCES = {
    'openai': 'https://openai.com/blog/rss.xml',
    '36kr': 'https://36kr.com/feed',
    'tmtpost': 'https://www.tmtpost.com/rss.xml',
    'qbitai': 'https://www.qbitai.com/feed',
    'appsotech': 'https://www.ifanr.com/feed',
    'arstechnica': 'https://feeds.arstechnica.com/arstechnica/index',
}
```

### 方案 B：Playwright 抓取（适用于超时/无RSS源）
使用 `fetch_generic_playwright.py` 通过浏览器渲染获取内容。

适用源：虎嗅、TechCrunch、Wired、MIT Tech Review、硅星人

### 方案 C：Grok API（需配置）
需环境变量 `XAI_API_KEY`，调用 xAI 搜索 API 获取 X 平台实时内容。

## 扩展脚本

已创建 `scripts/fetch_extended_sources.py`，支持：
```bash
python scripts/fetch_extended_sources.py --source all --limit 10
python scripts/fetch_extended_sources.py --source openai,36kr --limit 5
```

注意：RSS 抓取在代理环境下部分源超时，需增加 timeout 或使用 Playwright fallback。
