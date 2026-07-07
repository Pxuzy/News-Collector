"""
B站 — 热搜词 + 热门视频
"""
from typing import Optional
from urllib.parse import quote
from core import fetch_json, DEFAULT_UA
from sources import register


@register("bilibili", "🎮B站热搜")
def source_bilibili() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://s.search.bilibili.com/main/hotword?limit=30")
    if not data or 'list' not in data:
        return None, "API无数据"
    items = []
    for k in data['list']:
        title = k.get('show_name', '') or k.get('keyword', '')
        kw = k.get('keyword', title)
        if title:
            items.append({"id": kw or title, "title": title,
                          "url": f"https://search.bilibili.com/all?keyword={quote(kw)}",
                          "heat": str(k.get('score', 0)), "extra": {"source": "🎮B站"}})
    return items[:30], None


@register("bilibili_pop", "🎬B站热门")
def source_bilibili_popular() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://api.bilibili.com/x/web-interface/popular",
                      headers={"Referer": "https://www.bilibili.com/", "User-Agent": DEFAULT_UA})
    if not data or data.get('code') != 0:
        return None, "popular API失败"
    items = []
    for v in data.get('data', {}).get('list', []):
        title, bvid = v.get('title', ''), v.get('bvid', '')
        stat = v.get('stat', {})
        owner = v.get('owner', {}).get('name', '')
        info = f"{owner} · {_fmt(stat.get('view', 0))}播放" if owner else ''
        if title:
            items.append({"id": bvid or title, "title": title,
                          "url": f"https://www.bilibili.com/video/{bvid}" if bvid else '',
                          "heat": info, "extra": {"source": "🎬B站热门"},
                          "pubDate": v.get('pubdate', 0) * 1000})
    return items, None if items else "热门无数据"


def _fmt(n: int) -> str:
    return f"{n // 10000}w+" if n >= 10000 else str(n)
