"""
AI/学术源 — arXiv / HuggingFace / AIHOT / TLDR / ProductHunt / Lobsters / Dev.to
"""
import re
from typing import Optional
from core import fetch_json, fetch_via_requests, rss_to_items, clean_html_text
from sources import register


@register("arxiv", "📜arXiv")
def source_arxiv() -> tuple[Optional[list[dict]], Optional[str]]:
    api_url = "https://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=15"
    xml = fetch_via_requests(api_url)
    if xml and not xml.startswith("ERROR"):
        import feedparser

        feed = feedparser.parse(xml)
        items = []
        for entry in feed.entries[:10]:
            title = re.sub(r'\s+', ' ', entry.get('title', '').replace('\n', ' ').strip())
            link = entry.get("link", "")
            summary = clean_html_text(entry.get("summary", ""))[:500]
            categories = [
                tag.get("term")
                for tag in entry.get("tags", [])
                if isinstance(tag, dict) and tag.get("term")
            ][:5]
            if title:
                items.append({"id": entry.get('id', title), "title": title, "url": link,
                              "heat": '', "extra": {"source": "📜arXiv", "summary": summary, "categories": categories}})
        if items:
            return items, None
    return rss_to_items("https://rss.arxiv.org/rss/cs.AI", "arXiv", "📜", 10, 72)


@register("huggingface", "🤗HFPapers")
def source_hf_papers() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://huggingface.co/api/daily_papers?limit=10")
    if not data or not isinstance(data, list):
        return None, "API无数据"
    items = []
    for p in data[:10]:
        paper = p.get('paper', {})
        title = paper.get('title', '')
        url = paper.get('url', '')
        upvotes = p.get('upvotes', 0)
        if title:
            items.append({"id": paper.get('id', title), "title": title, "url": url,
                          "heat": f'🔥+{upvotes}' if upvotes else '', "extra": {"source": "🤗HFPapers"}})
    return items, None


@register("aihot", "🤖AIHOT")
def source_aihot() -> tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://aihot.virxact.com/feed/all.xml", "AIHOT", "🤖", 10, 72)


@register("tldr_ai", "🤖TLDR AI")
def source_tldr_ai() -> tuple[Optional[list[dict]], Optional[str]]:
    for url in ["https://tldr.tech/api/rss/ai", "https://www.tldr.tech/api/rss/ai"]:
        r = rss_to_items(url, "TLDR AI", "🤖", 5, 72)
        if r[0]: return r
    return None, "所有RSS都失败"


@register("producthunt", "🚀ProductHunt")
def source_producthunt() -> tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://www.producthunt.com/feed?category=all", "ProductHunt", "🚀", 10, 48)


@register("lobsters", "🐱Lobsters")
def source_lobsters() -> tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://lobste.rs/rss", "Lobsters", "🐱", 10, 48)


@register("devto", "💻Dev.to")
def source_devto() -> tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://dev.to/feed", "Dev.to", "💻", 10, 48)
