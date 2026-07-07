"""
华尔街见闻
"""
from typing import Optional
from core import fetch_json
from sources import register


@register("wallstreetcn", "📈华尔街见闻")
def source_wallstreetcn() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=30")
    if data and 'data' in data:
        items = [{"id": l.get('id', ''), "title": l.get('title', ''), "url": l.get('content_url', ''),
                  "heat": '', "extra": {"source": "📈华尔街见闻"}}
                 for l in data.get('data', {}).get('items', []) if l.get('title', '')]
        return items, None
    # 热文降级
    data2 = fetch_json("https://api-one.wallstcn.com/apiv1/content/articles/hot?period=all")
    if data2 and 'data' in data2:
        items = [{"id": a.get('content_title', ''), "title": a.get('content_title', ''),
                  "url": a.get('content_urls', {}).get('web_url', ''),
                  "heat": '', "extra": {"source": "📈华尔街"}}
                 for a in data2['data'].get('articles', []) if a.get('content_title', '')]
        return items, None
    return None, "API无数据"
