"""
国际新闻源 — HackerNews / BBC / Guardian / Reuters 等
"""
from typing import Optional
from core import fetch, rss_to_items, parse_html, HAS_BS4
from sources import register


@register("hackernews", "🐱HackerNews")
def source_hackernews() -> tuple[Optional[list[dict]], Optional[str]]:
    html = fetch("https://news.ycombinator.com/")
    if html.startswith('ERROR'):
        return rss_to_items("https://hnrss.org/frontpage?count=15", "Hacker News", "🐱", 15, 48)
    items = []
    if HAS_BS4:
        soup = parse_html(html)
        for row in soup.select('.athing'):
            a = row.select_one('.titleline a')
            title = a.text.strip() if a else ''
            iid = row.get('id', '')
            # Score — 在 .athing 的下一个兄弟 .subtext 里
            subtext = row.find_next_sibling('tr')
            if subtext:
                subtext = subtext.select_one('td.subtext')
            se = subtext.select_one('.score') if subtext else None
            score = se.text.strip() if se else ''
            # Comments — 从 subtext 里最后一个 <a>（href 含 item?id=）提取
            comments = ''
            if subtext:
                all_links = subtext.select('a[href*="item?id="]')
                if all_links:
                    last_link = all_links[-1]
                    comments_text = last_link.text.strip()
                    # "123 comments" → "123"
                    import re
                    cm = re.search(r'(\d[\d,]*)\s*comment', comments_text)
                    if cm:
                        comments = cm.group(1)
            if title and iid:
                items.append({"id": iid, "title": title,
                              "url": f"https://news.ycombinator.com/item?id={iid}",
                              "heat": score, "extra": {"source": "🐱HN", "comments": comments}})
    return items[:20], None if items else "HN无数据"


@register("bbc_world", "🌍BBC World")
def source_bbc_world() -> tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://feeds.bbci.co.uk/news/world/rss.xml", "BBC World", "🌍", 10, 48)


@register("guardian", "🌍TheGuardian")
def source_guardian() -> tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://www.theguardian.com/world/rss", "The Guardian", "🌍", 10, 48)


@register("aljazeera", "🌍AlJazeera")
def source_aljazeera() -> tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://www.aljazeera.com/xml/rss/all.xml", "Al Jazeera", "🌍", 10, 48)


@register("reuters", "🌍Reuters")
def source_reuters() -> tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items(
        "https://news.google.com/rss/search?q=site:reuters.com&hl=en-US&gl=US&ceid=US:en",
        "Reuters", "🌍", 10, 48
    )


@register("france24", "🌍France24")
def source_france24() -> tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items(
        "https://news.google.com/rss/search?q=site:france24.com&hl=en-US&gl=US&ceid=US:en",
        "France24", "🌍", 10, 48
    )
