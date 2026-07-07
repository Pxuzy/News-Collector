"""国外科技博客源 — OpenAI / Google / TechCrunch / Ars / Wired / Techmeme"""
from typing import Optional, Tuple
from core import rss_to_items
from sources import register


@register("openai_blog", "🤖OpenAI Blog")
def source_openai() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://openai.com/news/rss.xml", "OpenAI", "🤖", 10, 72)


@register("google_blog", "🔵Google Blog")
def source_google_blog() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://developers.googleblog.com/feeds/posts/default",
                        "Google Blog", "🔵", 10, 72)


@register("techcrunch", "🔥TechCrunch")
def source_techcrunch() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://techcrunch.com/feed/", "TechCrunch", "🔥", 10, 48)


@register("arstechnica", "🔬Ars Technica")
def source_arstechnica() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://feeds.arstechnica.com/arstechnica/index",
                        "Ars Technica", "🔬", 10, 48)


@register("wired", "⚡Wired")
def source_wired() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://www.wired.com/feed/rss", "Wired", "⚡", 10, 48)


@register("techmeme", "📡Techmeme")
def source_techmeme() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://www.techmeme.com/feed.xml", "Techmeme", "📡", 10, 48)
