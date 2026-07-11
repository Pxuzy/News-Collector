"""
华尔街见闻
"""
from typing import Optional
from core import fetch_json
from sources import register
import hashlib


def _ws_id(url: str, title: str) -> str:
    """基于 URL 的稳定 ID，防止每次采集生成不同 ID 导致重复"""
    basis = url or title
    return "ws_" + hashlib.md5(basis.encode("utf-8")).hexdigest()[:12]


@register("wallstreetcn", "📈华尔街见闻")
def source_wallstreetcn() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=30")
    if data and 'data' in data:
        items = [{"id": _ws_id(live.get('content_url', ''), live.get('title', '')),
                  "title": live.get('title', ''), "url": live.get('content_url', ''),
                  "heat": '', "extra": {"source": "📈华尔街见闻"}}
                 for live in data.get('data', {}).get('items', []) if live.get('title', '')]
        return items, None
    # 热文降级
    data2 = fetch_json("https://api-one.wallstcn.com/apiv1/content/articles/hot?period=all")
    if data2 and 'data' in data2:
        items = [{"id": _ws_id(a.get('content_urls', {}).get('web_url', ''), a.get('content_title', '')),
                  "title": a.get('content_title', ''),
                  "url": a.get('content_urls', {}).get('web_url', ''),
                  "heat": '', "extra": {"source": "📈华尔街"}}
                 for a in data2['data'].get('articles', []) if a.get('content_title', '')]
        return items, None
    return None, "API无数据"
