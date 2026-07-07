"""
新增源 P0 — 雪球 / 金十 / 掘金 / 懂球帝 / 牛客
参考 newsnow (ourongxing) 的 API 端点实现
"""
from typing import Optional
import json, re, time
from core import fetch_json, fetch_via_requests, rss_to_items, DEFAULT_UA
from sources import register


# ═══════════════════════════════════════════════
# 之前已添加的源
# ═══════════════════════════════════════════════

from typing import Optional, Tuple

@register("reddit", "🤖Reddit热帖")
def source_reddit() -> Tuple[Optional[list[dict]], Optional[str]]:
    # 改用 RSS with timeout control
    items, err = rss_to_items("https://www.reddit.com/r/all/hot/.rss?limit=15",
                              "Reddit Hot", "🤖", 15, 48,
                              extra_headers={"User-Agent": DEFAULT_UA + "; RedditBot/1.0"})
    if items:
        for item in items:
            item["category"] = "国际"
        return items, None
    return None, err or "RSS失败"


@register("googlenews", "🌍GoogleNews")
def source_googlenews() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items("https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
                        "Google News", "🌍", 15, 48)


@register("googlenews_cn", "🌍GoogleNews中国")
def source_googlenews_cn() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items(
        "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZxYUdjU0FtVnVHZ0pWVXlnQVAB?hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "Google News CN", "🌍", 10, 48)


@register("googlenews_tech", "🌍GoogleNews科技")
def source_googlenews_tech() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items(
        "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
        "Google News Tech", "🌍", 10, 48)


@register("googlenews_business", "🌍GoogleNews财经")
def source_googlenews_business() -> Tuple[Optional[list[dict]], Optional[str]]:
    return rss_to_items(
        "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
        "Google News Business", "🌍", 10, 48)


# ═══════════════════════════════════════════════
# P0: 新增 5 个高价值源
# ═══════════════════════════════════════════════

@register("xueqiu", "📈雪球热股")
def source_xueqiu() -> Tuple[Optional[list[dict]], Optional[str]]:
    """雪球热门股票 — 需要先拿 cookie"""
    # Step 1: 先请求首页拿 cookie
    try:
        import requests as req
        sess = req.Session()
        sess.get("https://xueqiu.com/hq",
                 headers={"User-Agent": DEFAULT_UA, "Accept": "text/html"},
                 timeout=10)
        # Step 2: 用拿到的 cookie 请求热股API
        url = "https://stock.xueqiu.com/v5/stock/hot_stock/list.json?size=20&_type=10&type=10"
        r = sess.get(url, headers={"User-Agent": DEFAULT_UA, "Referer": "https://xueqiu.com/hq"},
                     timeout=10)
        if r.status_code != 200:
            return None, f"雪球API {r.status_code}"
        data = r.json()
    except Exception as e:
        return None, f"请求失败: {e}"

    items = []
    for item in data.get('data', {}).get('items', []):
        if item.get('ad'): continue  # 跳过广告
        code = item.get('code', '')
        name = item.get('name', '')
        percent = item.get('percent', 0)
        exchange = item.get('exchange', '')
        if name:
            items.append({"id": f"xueqiu_{code}", "title": name,
                          "url": f"https://xueqiu.com/s/{code}",
                          "heat": f"{percent}%", "category": "财经",
                          "extra": {"source": "📈雪球", "percent": percent, "exchange": exchange}})
    return items, None if items else "无数据"


@register("jin10", "⚡金十快讯")
def source_jin10() -> Tuple[Optional[list[dict]], Optional[str]]:
    """金十数据 — 财经实时快讯"""
    ts = int(time.time() * 1000)
    raw = fetch_via_requests(f"https://www.jin10.com/flash_newest.js?t={ts}",
                              headers={"User-Agent": DEFAULT_UA, "Referer": "https://www.jin10.com/"})
    if not raw or raw.startswith('ERROR'):
        return None, "获取失败"
    # 去掉变量声明和末尾分号
    text = re.sub(r'^var\s+newest\s*=\s*', '', raw)
    text = re.sub(r';*\s*$', '', text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, "JSON解析失败"
    items = []
    for k in data[:20]:
        d = k.get('data', {})
        title = d.get('title', '') or d.get('content', '') or d.get('vip_title', '')
        content = d.get('content', '') or ''
        if not title:
            continue
        # 去掉 <b> 标签
        title = re.sub(r'</?b>', '', title)
        content = re.sub(r'</?b>', '', content)
        # 如果有【标题】格式的，提取
        m = re.match(r'^【([^】]*)】(.*)', title)
        if m:
            clean_title = m.group(1)
            desc = m.group(2)
        else:
            clean_title = title[:40]
            desc = content[:100]
        kid = k.get('id', str(ts))
        items.append({"id": f"jin10_{kid}", "title": clean_title,
                      "url": f"https://flash.jin10.com/detail/{kid}",
                      "heat": "⭐" if k.get('important') else '',
                      "category": "财经",
                      "extra": {"source": "⚡金十", "desc": desc[:100]}})
    return items[:15], None if items else "无数据"


@register("juejin", "💎掘金热榜")
def source_juejin() -> Tuple[Optional[list[dict]], Optional[str]]:
    """掘金开发者热榜"""
    data = fetch_json("https://api.juejin.cn/content_api/v1/content/article_rank?category_id=1&type=hot&spider=0",
                      headers={"User-Agent": DEFAULT_UA, "Referer": "https://juejin.cn/"})
    if not data or 'data' not in data:
        return None, "API无数据"
    items = []
    for item in data['data']:
        c = item.get('content', {})
        title = c.get('title', '')
        cid = c.get('content_id', '')
        if title:
            items.append({"id": f"juejin_{cid}", "title": title,
                          "url": f"https://juejin.cn/post/{cid}",
                          "heat": '', "category": "科技",
                          "extra": {"source": "💎掘金"}})
    return items, None if items else "无数据"


@register("dongqiudi", "⚽懂球帝")
def source_dongqiudi() -> Tuple[Optional[list[dict]], Optional[str]]:
    """懂球帝体育新闻"""
    data = fetch_json("https://api.dongqiudi.com/app/tabs/web/1.json",
                      headers={"User-Agent": DEFAULT_UA})
    if not data or 'articles' not in data:
        return None, "API无数据"
    items = []
    for a in data['articles'][:15]:
        title = a.get('title', '')
        aid = a.get('id', '')
        share = a.get('share', '') or a.get('url', '') or f"https://www.dongqiudi.com/article/{aid}"
        category = a.get('category', '体育')
        if title:
            items.append({"id": f"dqd_{aid}", "title": title, "url": share,
                          "heat": '', "category": "体育",
                          "extra": {"source": "⚽懂球帝", "sport": category}})
    return items, None if items else "无数据"


@register("nowcoder", "💼牛客热帖")
def source_nowcoder() -> Tuple[Optional[list[dict]], Optional[str]]:
    """牛客网求职/笔试热帖"""
    ts = int(time.time() * 1000)
    data = fetch_json(f"https://gw-c.nowcoder.com/api/sparta/hot-search/top-hot-pc?size=20&_={ts}&t=",
                      headers={"User-Agent": DEFAULT_UA})
    if not data or 'data' not in data:
        return None, "API无数据"
    items = []
    for k in data['data'].get('result', []):
        title = k.get('title', '')
        kid = k.get('id', '')
        ktype = k.get('type', 0)
        uuid = k.get('uuid', '')
        if not title:
            continue
        if ktype == 74:
            url = f"https://www.nowcoder.com/feed/main/detail/{uuid}"
            nid = uuid
        elif ktype == 0:
            url = f"https://www.nowcoder.com/discuss/{kid}"
            nid = kid
        else:
            url = f"https://www.nowcoder.com/"
            nid = kid
        items.append({"id": f"nc_{nid}", "title": title, "url": url,
                      "heat": '', "category": "科技",
                      "extra": {"source": "💼牛客"}})
    return items, None if items else "无数据"
