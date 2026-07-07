#!/usr/bin/env python
# coding=utf-8
"""
新闻简报生成器 v5.1 — 直接从 SQLite DB 读取数据
不再依赖 JSON 采集报告的格式
"""
import json, sys, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from store import _db as get_db, get_stats, CST
from classifier import classify

TOOLKIT_DIR = Path(__file__).parent.parent
DEFAULT_OUTPUT = TOOLKIT_DIR / "output" / "final_briefing.md"

# 分类展示优先级与标签
CATEGORY_META = [
    ("时政", "🌍 时政·外交"),
    ("财经", "💰 财经·A股"),
    ("AI", "🤖 AI前沿"),
    ("科技", "🔬 科技·产业"),
    ("国际", "🌏 国际新闻"),
    ("社会", "🌞 社会·民生"),
    ("体育", "⚽ 体育·赛事"),
    ("娱乐", "🎬 娱乐·综艺"),
    ("军事", "⚔ 军事·防务"),
    ("健康", "🏥 健康·医疗"),
    ("教育", "📚 教育·考试"),
]

SOURCE_ICONS = {
    "baidu": "🔎百度", "zhihu": "💬知乎", "toutiao": "🧭头条", "weibo": "💬微博",
    "bilibili": "🎮B站", "bilibili_pop": "🎬B站热门", "thepaper": "📰澎湃",
    "tieba": "💬贴吧", "hupu": "🏀虎扑", "douyin": "🎵抖音",
    "ithome": "🔬IT之家", "ifeng": "🌐凤凰", "36kr": "🔬36氪", "tencent": "🐧腾讯",
    "wallstreetcn": "📈华尔街", "xueqiu": "📈雪球", "jin10": "⚡金十",
    "github": "🐙GitHub", "hackernews": "🐱HN",
    "bbc_world": "🌍BBC", "googlenews": "🌍Google", "reuters": "🌍Reuters",
    "guardian": "🌍Guardian", "aljazeera": "🌍AJ", "france24": "🌍F24",
    "aihot": "🤖AIHOT", "huggingface": "🤗HF", "arxiv": "📜arXiv",
    "tldr_ai": "🤖TLDR", "producthunt": "🚀PH", "openai_blog": "🤖OpenAI",
    "techcrunch": "🔥TC", "arstechnica": "🔬Ars", "wired": "⚡Wired",
    "techmeme": "📡TM", "lobsters": "🐱LS", "devto": "💻Dev",
    "juejin": "💎掘金", "v2ex": "💬V2EX", "sspai": "✍️SSPai",
    "douban": "🎬豆瓣", "dongqiudi": "⚽懂球帝", "nowcoder": "💼牛客",
    "tmtpost": "📊钛媒体", "ifanr": "📱APPSO",
    "reddit": "🤖Reddit", "google_blog": "🔵Google",
}


def esc(text):
    return (text or '').replace('\n', ' ').replace('\r', '').strip()


def md_link(title, url):
    title = esc(title)
    url = esc(url)
    return f'[{title}]({url})' if url else title


def fetch_items(hours=24, limit_per_src=8):
    """从 DB 拉取最近 N 小时的新闻"""
    cutoff = (datetime.now(CST) - timedelta(hours=hours)).isoformat()
    conn = get_db()
    rows = conn.execute("""
        SELECT source, title, url, heat, heat_score, category, first_seen, last_seen, seen_count
        FROM news_items
        WHERE last_seen >= ? AND COALESCE(is_duplicate,0)=0
        ORDER BY heat_score DESC, last_seen DESC
    """, (cutoff,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def group_by_category(items):
    """按分类分组，同一分类内按热度排序"""
    groups = {}
    for item in items:
        cat = item.get('category', '') or classify(item.get('title', ''), item.get('source', ''))
        if cat not in groups:
            groups[cat] = []
        groups[cat].append(item)
    return groups


def generate_briefing(output_path, hours=24, top_per_cat=6):
    items = fetch_items(hours=hours)
    if not items:
        print(f"🔍 最近{hours}小时内无新闻数据")
        return

    groups = group_by_category(items)
    cat_map = {c: label for c, label in CATEGORY_META}
    now_str = datetime.now(CST).strftime('%Y-%m-%d %H:%M')

    O = []
    O.append('**📰 今日热点 · 全源聚合**')
    O.append('')
    O.append(f'📅 `{now_str}`   🤖 自动采集 (最近{hours}h)')
    O.append('')

    # 按 CATEGORY_META 顺序输出
    for cat_id, cat_label in CATEGORY_META:
        cat_items = groups.get(cat_id, [])
        if not cat_items:
            continue
        O.append(f'**{cat_label}**')
        O.append('')
        for i, item in enumerate(cat_items[:top_per_cat], 1):
            heat = f' [{item["heat"]}]' if item.get('heat') else ''
            icon = SOURCE_ICONS.get(item.get('source', ''), item.get('source', ''))
            O.append(f'{i}. {md_link(item.get("title", ""), item.get("url", ""))}{heat} — `{icon}`')
            O.append('')

    # 剩余未覆盖的分类（不在 CATEGORY_META 里的）
    extra_cats = set(groups.keys()) - {c for c, _ in CATEGORY_META}
    if extra_cats:
        O.append('**📎 其他**')
        O.append('')
        for cat in extra_cats:
            for item in groups[cat][:6]:
                O.append(f'- {md_link(item.get("title", ""), item.get("url", ""))}')
                O.append('')

    # 统计
    stats = get_stats(days=hours // 24 + 1)
    O.append('**📊 平台统计**')
    O.append('')
    if stats.get('by_source'):
        for s in stats['by_source'][:15]:
            bar = '█' * min(s['count'] // 2, 20)
            O.append(f'- {s["source"]:15s} `{bar}` `{s["count"]}条`')
    O.append('')
    O.append(f'> 📦 共 **{len(items)}** 条 | **{sum(1 for _ in groups)}** 个分类')

    result = '\n'.join(O)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result)
    print(f"✅ 简报已生成: {output_path}  ({len(items)}条, {sum(1 for _ in groups)}个分类)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="新闻简报生成器 v5.1")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出MD路径")
    parser.add_argument("--hours", type=int, default=24, help="回溯小时数")
    args = parser.parse_args()
    generate_briefing(args.output, hours=args.hours)
