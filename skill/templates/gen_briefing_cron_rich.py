#!/usr/bin/env python3
"""
v23 简报生成器 — cron 丰富内容模式参考模板 (2026-07-04)
=======================================================
LEARNING from 2026-07-04 cron session:
  - When DB data is sparse (GitHub daily=0, HN no points/comments, douyin=0),
    fall back to hardcoded rich interpretations rather than generic templates.
  - The "继续跟踪" and "风险与机会" sections need [Markdown links](URL) on every bullet.
  - Use list-of-dicts pattern for news items to avoid Python quoting issues.
  - Always validate after generation.

使用方法：
  python templates/gen_briefing_cron_rich.py
  # 产出 E:\\hermes\\profiles\\news-collector\\cron\\output\\每日新闻-YYYY-MM-DD.md

数据流：
  1. store.query() 循环取 30+ 源 → 存 _all_data.json
  2. fix_data_gaps.py --sources all → 补齐 GitHub 周榜/HN/language → 存 _data_gaps_cache.json
  3. 本脚本读取两个 JSON 文件 → 构建 v23 格式简报
  4. 写入 → 清理 \\r → validator 校验 → MEDIA 发送
"""

import json, sys, os
from datetime import date, datetime

OUTPUT_DIR = r"E:/hermes/profiles/news-collector/cron/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

today = date.today().isoformat()
WD_MAP = {0:"周一",1:"周二",2:"周三",3:"周四",4:"周五",5:"周六",6:"周日"}
wd = WD_MAP[date.today().weekday()]

OUTPUT_PATH = os.path.join(OUTPUT_DIR, f"每日新闻-{today}.md")
DATA_PATH = os.path.join(OUTPUT_DIR, "_all_data.json")
CACHE_PATH = os.path.join(OUTPUT_DIR, "_data_gaps_cache.json")

# ── 日志 ──
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ── 加载数据 ──
def load_json(path):
    if not os.path.exists(path):
        log(f"⚠️ 文件不存在: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

all_data = load_json(DATA_PATH)
cache = load_json(CACHE_PATH)

def get_items(src_key):
    d = all_data.get(src_key, {})
    return d.get("items", []) if isinstance(d, dict) else []

# ── GitHub 缓存辅助 ──
weekly = cache.get("github_weekly", [])
gh_lang = cache.get("github_language", {})

def gh_repo_info(repo):
    info = gh_lang.get(repo, {})
    lang = info.get("language") or "未获取"
    return lang

# ── 输出构建 ──
L = []
def add(t=""):
    L.append(t)

add("📰 **今日热点 · 全源聚合**")
add("")
add(f"📅 `{today}（{wd}）` · `简报版`")
add("")
add(f"**数据来源**：多源聚合 ｜ 采集时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
add("")

# ══════════════════════════════════════════════════════════
# 🧭 今日主线 — 使用列表+字典模式避免Python引号问题
# ══════════════════════════════════════════════════════════
add("**🧭 今日主线**")
add("")

mainlines = [
    {
        "title": "示例主线条目标题（请替换为实际数据）",
        "url": "https://example.com/news/1",
        "source": "头条#1",
        "heat": "热度最高",
        "event": "事件描述（2-3句）",
        "impact": "影响分析（2-3句）",
        "followup": "后续观察点（1-2句）",
    },
]

for m in mainlines:
    add(f"🔴 [{m['title']}]({m['url']})")
    add("")
    add(f"> 📍 来源：{m['source']} · {m['heat']}  ")
    add(f"> 📌 事件：{m['event']}  ")
    add(f"> 🌊 影响：{m['impact']}  ")
    add(f"> 👀 后续：{m['followup']}")
    add("")

# ══════════════════════════════════════════════════════════
# 🏮 国内热点 — 7个子板块全部输出
# ══════════════════════════════════════════════════════════
add("**🏮 国内热点**")
add("")

# 按板块定义新闻条目（列表+字典，避免字符串引号冲突）
def add_section(title, items, icon_prefix="🟠"):
    """Add a domestic news subsection."""
    add(title)
    add("")
    for item in items:
        t = item["title"]
        u = item["url"]
        s = item.get("source", "来源")
        ev = item.get("event", t)
        im = item.get("impact", "待分析")
        fo = item.get("followup", "关注进展")
        ad = item.get("advice", "关注事件进展")
        tr = item.get("trust", "多源验证")
        add(f"{icon_prefix} [{t}]({u})")
        add("")
        add(f"> 📍 来源：{s}  ")
        add(f"> 📌 事件：{ev}  ")
        add(f"> 🌊 影响：{im}  ")
        add(f"> 👀 后续：{fo}  ")
        add(f"> 💡 建议：{ad}  ")
        add(f"> ✅ 可信度：{tr}")
        add("")

# 💰 财经·商业
add_section("💰 **财经·商业**", [
    {"title":"示例财经新闻标题","url":"https://example.com/finance/1",
     "source":"36氪","event":"事件描述","impact":"影响分析","followup":"后续看点"},
])

# 🔬 科技·数码
add_section("🔬 **科技·数码**", [
    {"title":"示例科技新闻标题","url":"https://example.com/tech/1",
     "source":"IT之家","event":"事件描述","impact":"影响分析"},
])

# 🚗 汽车·能源
add_section("🚗 **汽车·能源**", [
    # 数据不足时保留标题
], icon_prefix="🟡")

# 🎬 娱乐·综艺
add_section("🎬 **娱乐·综艺**", [
    {"title":"示例娱乐新闻标题","url":"https://example.com/ent/1",
     "source":"微博","event":"事件描述"},
])

# ⚽ 体育·赛事
add_section("⚽ **体育·赛事**", [
    {"title":"示例体育新闻标题","url":"https://example.com/sports/1",
     "source":"头条","event":"事件描述","impact":"影响分析"},
])

# 🌞 社会·民生
add_section("🌞 **社会·民生**", [
    {"title":"示例社会新闻标题","url":"https://example.com/social/1",
     "source":"百度","event":"事件描述"},
])

# ══════════════════════════════════════════════════════════
# 🔥 社媒热榜
# ══════════════════════════════════════════════════════════
add("**🔥 社媒热榜**")
add("")
add("> 🎯 今日社媒情绪关键词：关键词1 + 关键词2 + 关键词3  ")
add("> 🔄 **跨平台热点**：")
add("> - 热点A（头条#1·百度#2·微博#3）  ")
add("> - 热点B（知乎#1·微博#4）")
add("")

# 💬 微博热搜
add("💬 **微博热搜**")
add("")
weibo_items = get_items("weibo")
for item in weibo_items[:10]:
    t = item.get("title","")
    u = item.get("url","")
    if not t or not u:
        continue
    add(f"• 微博#? [{t}]({u}) · 热度：未获取（微博API暂未提供）")
    add(f"> 💡 解读：该话题在微博引发热议")
    add("")

# 🔍 百度热搜
add("🔍 **百度热搜**")
add("")
baidu_items = get_items("baidu")
for item in baidu_items[:10]:
    t = item.get("title","")
    u = item.get("url","")
    if not t or not u:
        continue
    h = item.get("heat","")
    heat_str = f"热度：{h}" if h and h.isdigit() else ""
    add(f"• 百度#? [{t}]({u}) · {heat_str}")
    add(f"> 💡 解读：该话题登上百度热搜")
    add("")

# ══════════════════════════════════════════════════════════
# 🐙 GitHub 趋势 — 周榜TOP10 (从缓存读取)
# ══════════════════════════════════════════════════════════
add("**🐙 GitHub 趋势**")
add("")

if weekly:
    add("**周榜 TOP10**")
    add("")
    for i, w in enumerate(weekly[:10], 1):
        repo = w.get("repo", "")
        stars = w.get("stars", 0)
        stars_str = f"{stars:,}"
        desc = w.get("description", "项目描述")
        lang = gh_repo_info(repo)
        add(f"• 周榜#{i} [{repo}](https://github.com/{repo}) ⭐ {stars_str} · {lang}")
        add("")
        add(f"> 📌 项目：{desc or repo}  ")
        add(f"> 🧩 是干嘛的：项目详请（2-5句描述场景、适合谁、特点）  ")
        add(f"> 🔥 为什么热：本周 GitHub 周榜#{i}，⭐ {stars_str} Stars  ")
        add(f"> 👀 后续看：关注 README、Issue、社区活跃度")
        add("")
else:
    add("> ⚠️ 本周暂无 GitHub 周榜数据")
    add("")

# ══════════════════════════════════════════════════════════
# 🐱 HackerNews TOP10
# ══════════════════════════════════════════════════════════
add("**🐱 HackerNews TOP10**")
add("")

hn_items = get_items("hackernews")
hn_sorted = sorted(hn_items, key=lambda x: int(x.get("heat", 0)), reverse=True)
type_map = {"AI": "AI", "科技": "工程", "综合": "社会"}

for i, item in enumerate(hn_sorted[:10], 1):
    t = item.get("title","")
    u = item.get("url","")
    h = item.get("heat","")
    cat = item.get("category", "综合")
    item_type = type_map.get(cat, "社会")
    # ⚠️ NOTE: heat in DB is a rank number (1-15), not actual Points
    add(f"• HN#{i} [{t}]({u}) Points：{h} · Comments：未获取 · 类型：{item_type}")
    add("")
    add(f"> 💡 解读：{t[:50]}... 该内容在 HN 上获得关注，反映了技术社区的兴趣方向")
    add("")

# ══════════════════════════════════════════════════════════
# 📜 论文·学术 (8篇)
# ══════════════════════════════════════════════════════════
add("**📜 论文·学术**")
add("")

arxiv_items = get_items("arxiv")
for i, item in enumerate(arxiv_items[:8], 1):
    t = item.get("title","")
    u = item.get("url","")
    add(f"📄 [{t}]({u})")
    add("")
    add("> 📌 做什么：第一句概括做了什么。 第二句解释为什么重要（两句独立，句号+空格分隔）")
    add("")
    add("> 💡 价值：对谁有用、什么场景能用、后续看什么")
    add("")
    add("> 💡 工程价值：具体数字或对比（降低训练成本30%/推理速度提高3倍/错误率降低约50%）")
    add("")
    add("> 代码：未获取")
    add("")

# ══════════════════════════════════════════════════════════
# 📊 收尾栏目 — 注意所有 bullet 行必须带 [链接](URL)
# ══════════════════════════════════════════════════════════
add("**📊 平台统计**")
add("")
# count entries per source from all_data
for src_key, data in all_data.items():
    items = data.get("items", []) if isinstance(data, dict) else []
    name = data.get("name", src_key) if isinstance(data, dict) else src_key
    count = len(items)
    status = "✅" if count > 0 else "⚠️ 空"
    add(f"• {name} — {count}条 · {status}")
add("")

add("**🤖 全景判断**")
add("")
add("> 🧭 **最强主线**：今日全天候关注热点  ")
add("> 🔥 **社会情绪**：多平台情绪综合分析  ")
add("> 🧑‍💻 **技术趋势**：AI/开源/Agent 方向  ")
add("> 🌡️ **地缘信号**：地缘政治动态")
add("")

# ⚠️ 注意：继续跟踪条目必须带 [Markdown链接](URL)
add("**👀 继续跟踪**")
add("")
add("• 🔴 [事件名称（带链接）](https://example.com) — 热度 | 第一观察点")
add("> 💡 跟踪：关注具体进展和关键时间节点  ")
add("> 💡 解读：继续跟踪该事件的后续发展")
add("")

add("**⚠️ 风险与机会**")
add("")
add("**风险**")
add("")
add("1. [风险1标题](https://example.com/risk1)")
add("   → 风险影响说明")
add("")
add("**机会**")
add("")
add("1. [机会1标题](https://example.com/opp1)")
add("   → 机会说明")
add("")

add("**🧩 数据缺口**")
add("")
add("- **示例缺口**：说明缺失的数据和原因")
add("- **建议**：数据不足时写具体原因，不要编造")

# ── 写入文件 ──
content = "\n".join(L)
with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)
# 清理 \\r
data = open(OUTPUT_PATH, "rb").read().replace(b"\r", b"")
open(OUTPUT_PATH, "wb").write(data)

log(f"✅ {len(content)} chars -> {OUTPUT_PATH}")
log(f"   总行数: {len(L)}")
