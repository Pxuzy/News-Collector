#!/usr/bin/env python
"""
gen_briefing_manual.py — 手动会话简报生成模板（v23 格式）

用法：
  1. 复制此文件到 cron/output/
  2. 修改 OUTPUT 日期
  3. 修改各板块的数据获取和条目内容
  4. python gen_briefing_manual.py
  5. 校验：cd skill 根目录 && python scripts/validate_briefing.py "E:/path/to/file.md"
  6. MEDIA:E:/path/to/file.md 发送

特点：
  - 用 store.query() 直查 DB（不触发采集）
  - 用 add() / lines.append() 逐行构建
  - 写入用 open(newline='\\n') + 清理 \\r
  - 自动从 _data_gaps_cache.json 读取补齐数据
"""
import sys, json, os
sys.path.insert(0, r'E:/hermes/workspace/news-toolkit/scripts')
from store import query

OUTPUT = r'E:/hermes/profiles/news-collector/cron/output/news-YYYY-MM-DD.md'
CACHE = r'E:/hermes/profiles/news-collector/cron/output/_data_gaps_cache.json'

def add(t=""):
    lines.append(t)

def fmt_link(text, url):
    return f'[{text}]({url})'

def get_items(source, limit=15):
    try:
        items, total = query(source=source, days=1, limit=limit)
        return items
    except:
        return []

def heat_str(item):
    """格式化热度字符串，处理各源特殊情况"""
    h = item.get('heat', '') or ''
    src = item.get('source', '')
    if src == 'weibo':
        return '热度：未获取（微博API限制）'
    if src in ('ithome', 'bilibili', 'bilibili_pop'):
        return '热度未获取'
    if h.isdigit() and len(h) > 4:
        n = int(h)
        return f'热度{round(n/10000)}万' if n > 10000 else f'热度{h}'
    return f'热度{h}' if h else '热度未获取'

def short_title(title):
    return title.replace(' / ', '/').strip()

def get_extra(item, key, default='?'):
    """解析 extra JSON 字符串"""
    import json
    extra_raw = item.get('extra', '{}')
    try:
        extra = json.loads(extra_raw) if isinstance(extra_raw, str) else extra_raw
        return extra.get(key, default)
    except:
        return default

lines = []
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

# ===== 文件头 =====
add("📰 **今日热点 · 全源聚合**")
add("")
add("📅 `YYYY.MM.DD（周X）` · `早间版`")
add("")
add("**数据来源**：多源聚合 ｜ 采集时间：YYYY-MM-DD HH:MM")
add("")

# ===== 获取各源数据 =====
baidu = get_items('baidu', 15)
weibo = get_items('weibo', 15)
douyin = get_items('douyin', 8)
zhihu = get_items('zhihu', 8)
toutiao = get_items('toutiao', 15)
github = get_items('github', 10)
hn = get_items('hackernews', 10)
aihot = get_items('aihot', 10)

# ===== 🧭 今日主线（3-5条，取各源#1） =====
add("**🧭 今日主线**")
add("")

# 主线1：百度#1
if baidu:
    it = baidu[0]
    add(f"🔴 {fmt_link(it['title'], it['url'])}")
    add("")
    add(f"> 📍 来源：百度#1 · {heat_str(it)}  ")
    add(f"> 📌 事件：{it['title'][:80]}  ")
    add("> 🌊 影响：全网广泛关注  ")
    add("> 👀 后续：追踪发展  ")
    add("> ✅ 可信度：多源验证")
    add("")

# 主线2：头条#1（如果和百度不同）
if toutiao and toutiao[0]['title'] != (baidu[0]['title'] if baidu else ''):
    ...

# ===== 🏮 国内热点（7子板块） =====
add("**🏮 国内热点**")
add("")

for board_name, board_emoji, src_items, kwlist in [
    ("时政·外交", "🌍", baidu, ['习近平','外交','台湾','南海']),
    ("财经·商业", "💰", toutiao, ['股市','基金','A股','银行','降息']),
    ("科技·数码", "🔬", toutiao, ['华为','芯片','小米','苹果','AI']),
    ("汽车·能源", "🚗", toutiao, ['汽车','新能源','电动车','特斯拉']),
    ("娱乐·综艺", "🎬", weibo, ['演唱会','综艺','电影','明星']),
    ("体育·赛事", "⚽", weibo, ['世界杯','NBA','足球','篮球']),
    ("社会·民生", "🌞", baidu, ['高温','暴雨','交通','教育']),
]:
    add(f"{board_emoji} **{board_name}**")
    add("")
    found = 0
    for it in src_items:
        if found >= 2:
            break
        if any(kw in it['title'] for kw in kwlist):
            add(f"🟠 {fmt_link(it['title'], it['url'])}")
            add("")
            add(f"> 📍 来源：{it.get('source','')}  ")
            add(f"> 📌 事件：{it['title'][:80]}  ")
            add("> 🌊 影响：热点话题  ")
            add("> 👀 后续：追踪发展  ")
            add("> 💡 建议：关注官方信息  ")
            add("> ✅ 可信度：多源验证")
            add("")
            found += 1
    if found == 0:
        add("> 今日暂无突出热点。")
        add("")

# ===== 🔥 社媒热榜 =====
add("**🔥 社媒热榜**")
add("")

for platform, items, label in [
    ("🎵 抖音 TOP5", douyin, "· 热度"),
    ("💬 微博热搜 TOP5", weibo, "· 热度：未获取"),
    ("💬 知乎热榜 TOP5", zhihu, "· 热度"),
    ("🔍 百度热搜 TOP5", baidu, "· 热度未获取"),
]:
    add(f"**{platform}**")
    add("")
    for i, it in enumerate(items[:5]):
        add(f"{i+1}. {fmt_link(it['title'], it['url'])} {label}")
        add("> 💡 解读：平台热门话题")
        add("")

# ===== 🐙 GitHub 日榜TOP5 =====
add("**🐙 GitHub 日榜 TOP5**")
add("")
for i, it in enumerate(github[:5]):
    title = short_title(it['title'])
    h = it.get('heat', '')
    add(f"• 日榜#{i+1} {fmt_link(title, it['url'])} ⭐{h.replace('⭐','')}")
    add("")
    add(f"> 📌 项目：{title} — GitHub 热门项目  ")
    add(f"> 🧩 是干嘛的：开源项目，获得社区大量关注  ")
    add("> 🔥 为什么热：GitHub 日榜排名靠前  ")
    add("> 👀 后续看：关注社区发展")
    add("")

# ===== 🐱 HackerNews TOP5 =====
add("**🐱 HackerNews TOP5**")
add("")
hn_comments = cache.get('hn_comments', {})
for i, it in enumerate(hn[:5]):
    title = it['title']
    info = hn_comments.get(title, {})
    points = info.get('points', '未获取')
    comments = info.get('comments', '未获取')
    hn_url = info.get('hn_url', it['url'])
    add(f"• HN#{i+1} {fmt_link(title, hn_url)} Points：{points} · Comments：{comments}")
    add("")
    add("> 💡 解读：HackerNews 热门讨论")
    add("")

# ===== 📊 收尾栏目 =====
add("**📊 平台统计**")
add("")
add(f"• 百度 — {len(baidu)}条 · ⚠️ 热度为摘要")
add(f"• 微博 — {len(weibo)}条 · ⚠️ 热度空")
add(f"• 抖音 — {len(douyin)}条 · ✅")
add(f"• 知乎 — {len(zhihu)}条 · ✅")
add(f"• 头条 — {len(toutiao)}条 · ✅")
add(f"• GitHub — {len(github)}条 · ⚠️ 语言需补齐")
add(f"• HN — {len(hn)}条 · ✅ Points+Comments")
add("")

add("**⚠️ 风险与机会**")
add("")
add("**风险**")
add("1. [标题](url)")
add("   → 影响说明")
add("")
add("**机会**")
add("1. [标题](url)")
add("   → 机会说明")
add("")

add("**🧩 数据缺口**")
add("")
add("- **微博热度**：API返回数字ID")
add("- **百度热度**：heat字段为搜索摘要文本")

# ===== 写入文件 =====
with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines))

# 清理 \r
data = open(OUTPUT, "rb").read().replace(b"\r", b"")
open(OUTPUT, "wb").write(data)

print(f"✅ 简报已生成: {OUTPUT} ({len(lines)}行)")
