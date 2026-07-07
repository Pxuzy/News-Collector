# Cron 自动化管线架构（2026-07-02 更新 — 4 任务分流版）

## 架构概览

```
                    ┌─────────────────────────────────────────┐
                    │  run_collector_silent.py (全量50源)       │
                    │  schedule: 55 6,18 * * *                 │
                    │  → 采集 + fix_data_gaps.py               │
                    └──────────────┬──────────────────────────┘
                                   │  06:55 / 18:55
                    ┌─────────────────────────────────────────┐
                    │  run_collector_core.py (核心~30源)       │
                    │  schedule: 55 12 * * *                   │
                    │  → 采集 + fix_data_gaps.py               │
                    └──────────────┬──────────────────────────┘
                                   │  12:55
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │  news.db (SQLite)                       │
                    │  + _data_gaps_cache.json (补齐数据)      │
                    └──────────────┬──────────────────────────┘
                                   │  5 分钟后
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    enhanced-news-briefing   enhanced-news-briefing  evening-news-recap
     (07:00, 标准简报)         (13:00, 标准简报)      (19:00, 今日回顾)
```

**核心原则**：采集器在简报前 5 分钟执行，采集后自动运行 `fix_data_gaps.py` 补齐 HN Points/Comments 和 GitHub language/Stars，写入 `_data_gaps_cache.json` 供 Agent 简报使用。

## 采集器分流策略（2026-07-02）

- **全量 50 源**（~120s）：早晚各一次（06:55/18:55），保持数据完整
- **核心 ~30 源**（~60s）：午间一次（12:55），快速刷新支撑午报
- 采集后自动执行 `fix_data_gaps.py`（~15s），补齐 HN + GitHub 字段

## Cron 任务配置

### news-toolkit-collector（全量采集器）

```
job_id:     3b81c8249ae6
schedule:   55 6,18 * * *        (06:55 / 18:55)
script:     run_collector_silent.py
no_agent:   true                 (纯脚本)
deliver:    local                (静默不推送)
workdir:    E:\hermes\workspace\news-toolkit
```

- 包装脚本：`E:\hermes\profiles\news-collector\scripts\run_collector_silent.py`
- 采集命令：`multi_source_news.py --parallel 8 --prune`
- 采集后自动运行同目录下的 `fix_data_gaps.py` 补齐数据
- ⚠️ 依赖：Hermes-agent venv 需装 `feedparser`

### news-toolkit-core-collector（核心采集器 — 2026-07-02 新增）

```
job_id:     04f0cb066b59
schedule:   55 12 * * *        (12:55)
script:     run_collector_core.py
no_agent:   true
deliver:    local
workdir:    E:\hermes\workspace\news-toolkit
```

- 包装脚本：`E:\hermes\profiles\news-collector\scripts\run_collector_core.py`
- 采集命令：`multi_source_news.py --core --parallel 8 --prune`
- 仅核心 ~30 源（排除长尾 RSS），速度快约 1 倍
- 采集后自动运行 `fix_data_gaps.py`

### enhanced-news-briefing（标准简报）

```
job_id:     6970ccabcd23
schedule:   0 7,13 * * *        (07:00 / 13:00)
mode:       Agent (LLM)
no_agent:   false
deliver:    origin
attach_to_session: true
```

**产出**：v23 格式完整标准简报（主线/国内7子板块/社媒4平台/GitHub/HN/论文/收尾）

### evening-news-recap（晚间回顾 — 2026-07-02 新增）

```
job_id:     96f910e6268d
schedule:   0 19 * * *         (19:00)
mode:       Agent (LLM)
no_agent:   false
deliver:    origin
attach_to_session: true
```

**产出**：今日回顾模式，与标准简报不同：
- 🧭 今日最重要的 5 件事（完整字段）
- 🏮 今日国内焦点（3 大块，精简条目）
- 🌏 今日国际/财经要闻
- 🔥 今日热榜焦点（只选最火 3-5 条）+ 🤖 今日 AI
- 📊 今日数据 + 👀 明天值得关注
- 整体 25-35 条，突出回顾感和前瞻性

## Agent prompt 精简原则

prompt 应控制在 2000-3000 字符，按 4 段结构：
1. **数据获取**：检查新鲜度 → 采集/直查。提示读取 `_data_gaps_cache.json` 补齐字段
2. **板块清单**：按顺序列出 + 各板块字段要点
3. **格式规则**：禁止 #/表格/代码块，论文独立 > 块等
4. **交付检查**：写入 → 校验 → MEDIA → 一句话回复

## 源名称完整映射表

news.db `source` 字段 → enhanced_news `src_name` 字段（用于分类/渲染）：

### 国内平台 (domestic_sources)

| news.db source | icon | src_name | 来源 |
|---|---|---|---|
| `baidu` | 🔎 | 百度 | 百度热搜 |
| `weibo` | 💬 | 微博 | 微博热搜 |
| `douyin` | 🎵 | 抖音 | 抖音热榜 |
| `toutiao` | 📰 | 头条 | 头条热榜 |
| `zhihu` | 💬 | 知乎 | 知乎热榜 |
| `bilibili` | 🎮 | B站 | B站热搜 |
| `bilibili_pop` | 🎮 | B站 | B站热门视频 |
| `ithome` | 💻 | IT之家 | IT之家 |
| `thepaper` | 📰 | 澎湃 | 澎湃热榜 |
| `36kr` | 📈 | 36氪 | 36氪 |
| `tencent` | 🐧 | 腾讯新闻 | 腾讯新闻 |
| `hupu` | 🏀 | 虎扑 | 虎扑热帖 |
| `tieba` | 💬 | 贴吧 | 贴吧热议 |
| `sspai` | 📱 | 少数派 | 少数派 |
| `v2ex` | 💻 | V2EX | V2EX |
| `douban` | 🎬 | 豆瓣 | 豆瓣热门 |
| `dongqiudi` | ⚽ | 懂球帝 | 懂球帝 |
| `nowcoder` | 💻 | 牛客 | 牛客 |
| `juejin` | 💎 | 掘金 | 掘金 |
| `wallstreetcn` | 💰 | 华尔街见闻 | 华尔街见闻 |
| `jin10` | 💰 | 金十数据 | 金十数据 |
| `xueqiu` | 💰 | 雪球 | 雪球 |

### 国际/技术 (intl_sources)

| news.db source | icon | src_name | 来源 |
|---|---|---|---|
| `hackernews` | 🐱 | Hacker News | Hacker News |
| `github` | 🐙 | GitHub | GitHub Trending (daily) |
| `aihot` | 🤖 | AIHOT | AIHOT |
| `arxiv` | 📜 | arXiv | arXiv 论文 |
| `bbc_world` | 🌍 | BBC World | BBC World News |
| `guardian` | 🌍 | The Guardian World | The Guardian |
| `reuters` | 🌍 | Reuters | Reuters |
| `aljazeera` | 🌍 | Al Jazeera | Al Jazeera |
| `france24` | 🌍 | France 24 | France 24 |
| `producthunt` | 🚀 | Product Hunt | Product Hunt |
| `devto` | 💻 | Dev.to | Dev.to |
| `lobsters` | 🐱 | Lobsters | Lobsters |
| `googlenews` | 🌐 | 国际 | Google News 聚合 |
| `googlenews_cn` | 🌐 | 国际 | Google News 中文 |
| `googlenews_tech` | 🌐 | 国际 | Google News 科技 |
| `googlenews_business` | 💰 | 国际 | Google News 商业 |
| `techcrunch` | 🔬 | TechCrunch | TechCrunch |
| `techmeme` | 🔬 | Techmeme | Techmeme |
| `wired` | 🔬 | Wired | Wired |
| `tmtpost` | 💡 | 钛媒体 | 钛媒体 |
| `openai_blog` | 🤖 | AIHOT | OpenAI 博客 |
| `google_blog` | 🤖 | AIHOT | Google 博客 |
| `appso` | 📱 | APPSO | APPSO/爱范儿 |

### 关键映射逻辑

1. **B站合并**：`bilibili` 和 `bilibili_pop` 都映射到 `B站`，enhanced_news 在渲染时自动合并
2. **AIHOT 聚合**：`aihot`、`openai_blog`、`google_blog` 都映射到 `AIHOT`，在 AI 圈热点栏目中按关键词匹配
3. **Google News 系列**：`googlenews_*` 映射为 `国际`，在 intl 分类中按内容关键词进一步拆分为国际/财经/科技
4. **未映射的源**：不在 SRC_MAP 中的源默认使用 `(🌐, '国际')` 降级

## enhanced_news 源分类逻辑 (build lines 964-968)

```python
domestic_sources = {'微博','B站','百度','抖音','头条','IT之家'}
intl_sources = {'GitHub','GitHub周榜','AIHOT','arXiv','国际','BBC','卫报','半岛',
                 '法广','路透','Al Jazeera','France 24','BBC Top News','BBC World',
                 'BBC Chinese','The Guardian World','Reuters','Hacker News',
                 'Product Hunt','Dev.to','Lobsters'}

domestic_items = [it for it in items if it.get('src_name','') in domestic_sources]
intl_items = [it for it in items if it.get('src_name','') in intl_sources]
```

注意：只有 `domestic_sources` 和 `intl_sources` 中的 src_name 会被 `classify_items` 处理。其他源（如 `少数派`、`掘金`、`懂球帝`）会被归入 `misc`，在 `render_section` 渲染国内/国际板块时不会出现，但会进入 `render_heat_ranking` 和 `platform_stats`。

## 各源 heat 字段格式

| source | heat 格式 | 示例 | heat_int 转换 |
|---|---|---|---|
| baidu | 两种：store.query() 返纯数字（如 39）；nb_query.py 返搜索摘要 | 39 / "2026年欧洲高温背景下..." | → 0 或 级数编号 |
| weibo | 空字符串 | "" | → 0 |
| douyin | 纯数字ID | "12127398" | → 12127398 |
| toutiao | 纯数字热度 | "18774447" | → 18774447 |
| github | ⭐N,N | "⭐16,770" | → 16770 |
| hackernews | "N points" | "873 points" | → 873 |
| arxiv | 空字符串 | "" | → 0 |
| bilibili | 分数/空 | "0.0" | → 0 |

## 已知限制

0. **⚠️ Cron 环境缺少 feedparser（2026-07-02 修复）**：Hermes-agent venv (`E:\hermes\hermes-agent\venv\`) 缺少 `feedparser` 模块，导致 cron 运行的 `run_collector_silent.py` 子进程执行 `multi_source_news.py` 时 22 个 RSS/Feed 源（BBC/Reuters/Al Jazeera/arXiv/Reddit/TechCrunch/Wired/Google News 等）全部失败。修复：`/e/hermes/hermes-agent/venv/Scripts/python.exe -m pip install feedparser`。每次 Hermes-agent venv 重建后需重新安装。如新增 RSS 源，先用该 venv Python 测试 `import feedparser`。

1. **GitHub 周榜从 enhanced_news 补充**
2. **百度热度双模式**：`nb_query.py` 模式百度 `heat` 字段被摘要文本占据；`store.query()` 直接查则返回纯数字（搜索排名编号，非真实热度值）。两种模式都无法直接获取百度真实热度。在百度热榜 source_line 中必须包含 `热度：N` 格式才能通过 validator 检查，纯「热搜」文字无法通过。
3. **微博无热度**：微博 `heat` 为空，所有微博条目显示 `热度：未获取`。
4. **IT之家 0 热度**：B站和 IT 之家的热度值始终为 0。
5. **模板化 💡 解读**：Cron 模式使用 enhanced_news 内置的 `make_commentary()` / `social_commentary()` 模板，而非 LLM 实时生成。解读质量低于手动会话模式。

## fix_data_gaps 数据补齐（2026-07-02 新增）

两个采集器脚本（`run_collector_silent.py` / `run_collector_core.py`）在采集完成后自动运行 `fix_data_gaps.py`：

| 缺口 | 补齐方式 | API | 缓存路径 |
|------|---------|-----|---------|
| HN Points/Comments | Algolia API 实时抓取前 15 条 | `hn.algolia.com` | `_data_gaps_cache.json` |
| GitHub language/Stars | GitHub API 查询指定仓库 | `api.github.com` | `_data_gaps_cache.json` |

**Agent 简报 prompt 中应包含**：读取 `E:/hermes/profiles/news-collector/cron/output/_data_gaps_cache.json` 以获取补齐后的 HN/GitHub 字段，避免 DB 数据缺字段。

缓存文件路径：`cron/output/_data_gaps_cache.json`
补齐脚本：`scripts/fix_data_gaps.py`

## 手动会话模式 vs Cron 模式

本架构主要描述 Cron 自动管线。当会话中用户问"看看今天有哪些热点新闻"时，走的是**手动快速扫一眼模式**：

| 维度 | Manual 快速扫一眼 | Cron 自动推送 |
|------|------------------|---------------|
| 数据获取 | 跳过 nb_query，直接 `store.query()` 查国内核心源 | nb_query.py 循环 45 源 |
| 时效 | 数据过期时 `store.query()` 直接返回旧数据，不触发采集 | 自动跑 multi_source_news.py 刷新 |
| 输出 | 精简字段（标题+来源+热度），1-3 行/条 | 完整模板（📌🌊👀💡✅ 全字段） |
| 速度 | 毫秒级 | ~60-120s（含采集时间） |

**触发词映射**：
- **"看看今天有哪些热点新闻" / "今天有啥热点" / "看看今天的新闻"** → 快速扫一眼
- **"今日热点" / "新闻日报" / "新闻简报"** → 完整简报模式

### nb_query.py 超时兜底（手动会话用）

手动会话中 `nb_query.py` 因触发采集而超时时，用直接 `store.query()` 兜底：

```python
import sys
sys.path.insert(0, r'E:\\hermes\\workspace\\news-toolkit\\scripts')
from store import query

# 快速扫一眼：只查核心国内源 + 技术源
sources = ['baidu','weibo','douyin','toutiao','zhihu',
           'github','hackernews','aihot','arxiv']
for src in sources:
    items, total = query(source=src, days=1, limit=8)
    for it in items:
        db_src = it['source']  # 'baidu', 不是 '_query_source'
        # 用 SRC_MAP 映射为 src_name
```

**注意**：`store.query()` 的 `source` 参数只接受单源字符串。多源必须循环调用。返回的 item 用 `it['source']`（不是 `'_query_source'`，后者只有 nb_query.py 才加）。

## 修改指南

- **改采集时机**：`cronjob(action='update', job_id='3b81c8249ae6', schedule='...')` 全量采集；`job_id='04f0cb066b59'` 核心采集
- **改采集源范围**：编辑 `run_collector_silent.py` vs `run_collector_core.py` 中 `--core` 参数
- **改简报推送时机**：`job_id='6970ccabcd23'` 标准简报；`job_id='96f910e6268d'` 晚间回顾
- **改简报 prompt**：`cronjob(action='update', job_id='...', prompt='...')`
- **改数据补齐**：编辑 `scripts/fix_data_gaps.py`

## Cron Troubleshooting: 交互环境 vs Cron 结果不一致的排查方法

当手动运行脚本成功（如 50 源采集）但 cron 运行失败（如 26/53 分）时，按以下步骤排查：

### 第一步：对比原始数据输出

不要只看摘要，直接对比 cron 产出和手动产出的 JSON 文件中每个 source 的 status 和 error：

```python
# 对比两个 JSON 中同一 source 的 status 和 error 字段
import json
with open('cron_output.json') as f: c = json.load(f)
with open('manual_output.json') as f: m = json.load(f)
for name in sorted(c['sources']):
    cs, ms = c['sources'][name], m['sources'].get(name, {})
    if cs.get('status') != ms.get('status'):
        print(f'DISCREPANCY: {name}')
        print(f'  Cron:   {cs.get("status")} {cs.get("error","")}')
        print(f'  Manual: {ms.get("status")} {ms.get("error","")}')
```

### 第二步：识别错误模式

如果多个源报同一错误（如 "No module named 'X'"），表明是**依赖缺失**而非网络问题。如果 cron 独有错误是 "RSS获取失败" 之类，检查 cron Python 是否有 feedparser。

### 第三步：确定 cron 使用的 Python

cron 使用 Hermes-agent venv 的 Python（`E:\hermes\hermes-agent\venv\Scripts\python.exe`），与交互式会话的 Python 可能不同。在 no_agent=true 脚本中内省：

```python
import sys; print(sys.executable); print(sys.path[:3])
```

### 第四步：比对模块可用性

```bash
/E/hermes/hermes-agent/venv/Scripts/python.exe -c "import feedparser; print('OK')"
python -c "import feedparser; print('OK')"
```

### 第五步：在 cron 环境下直接验证修复

用 Hermes-agent venv 的 Python 运行采集器，确认修复有效再部署到 cron：

```bash
/E/hermes/hermes-agent/venv/Scripts/python.exe -c "
import subprocess, sys
result = subprocess.run(
    [sys.executable, 'E:/hermes/workspace/news-toolkit/scripts/multi_source_news.py', '--parallel', '8', '--prune'],
    capture_output=True, text=True, timeout=300
)
for line in result.stdout.split(chr(10)):
    if '\u91c7\u96c6\u5b8c\u6210' in line or 'No module' in line:
        print(line)
"
```

### 典型场景速查

| 症状 | 排查方向 | 常见根因 |
|------|---------|---------|
| cron 独有模块缺失（No module named X） | 对比 venv vs 交互 Python 模块列表 | cron 使用的 Hermes-agent venv 缺包 |
| cron 独有网络超时 | 检查 cron 环境变量/proxy | 环境变量未继承 |
| cron 输出为空或截断 | 检查 no_agent 脚本的最后输出行数 | 包装脚本只打印最后 N 行 |
| cron 与交互采集数相同但内容不同 | 对比 JSON 中每个 source 的 count | 数据新鲜度窗口不同 |
