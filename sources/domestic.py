"""
国内热点源 — 百度/知乎/头条/微博/澎湃/贴吧/虎扑/IT之家/凤凰/36氪/腾讯/V2EX/少数派/豆瓣
"""
import json
import re
from typing import Optional
from core import fetch, fetch_json, fetch_via_requests, clean_html_text, parse_html, HAS_BS4, DEFAULT_UA
from sources import register

# ─── 百度热搜 ─────────────────────────
@register("baidu", "🔎百度热搜")
def source_baidu() -> tuple[Optional[list[dict]], Optional[str]]:
    html = fetch("https://top.baidu.com/board?tab=realtime")
    if html.startswith('ERROR'):
        return None, "页面获取失败"
    m = re.search(r'<!--s-data:(.*?)-->', html, re.DOTALL)
    if not m:
        return None, "未找到s-data"
    try:
        data = json.loads(m.group(1))
    except Exception:
        return None, "JSON解析失败"
    items = []
    for card in data.get('data', {}).get('cards', []):
        for c in card.get('content', []):
            if c.get('isTop'): continue
            word = c.get('word', '')
            if word:
                desc = c.get('desc', '')
                heat = c.get('hotScore') or c.get('heatScore') or c.get('index') or ''
                items.append({"id": c.get('rawUrl', word), "title": word,
                              "url": c.get('rawUrl', ''), "heat": str(heat) if heat else '',
                              "extra": {"source": "🔎百度", "desc": desc}})
    return items, None

# ─── 知乎热榜 ─────────────────────────
@register("zhihu", "💬知乎热榜")
def source_zhihu() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://www.zhihu.com/api/v3/feed/topstory/hot-list-web?limit=20&desktop=true")
    if not data or 'data' not in data:
        return None, "API无数据"
    items = []
    for k in data.get('data', []):
        target = k.get('target', {})
        title = target.get('title_area', {}).get('text', '')
        url = target.get('link', {}).get('url', '')
        heat = target.get('metrics_area', {}).get('text', '')
        if title:
            items.append({"id": url or title, "title": title, "url": url,
                          "heat": heat, "extra": {"source": "💬知乎"}})
    return items, None

# ─── 今日头条 ─────────────────────────
@register("toutiao", "🧭头条热榜")
def source_toutiao() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc")
    if not data or 'data' not in data:
        return None, "API无数据"
    items = []
    for k in data.get('data', []):
        title = k.get('Title', '')
        if title:
            cid = k.get('ClusterIdStr', '')
            items.append({"id": cid or title, "title": title,
                          "url": f"https://www.toutiao.com/trending/{cid}/",
                          "heat": str(k.get('HotValue', '')), "extra": {"source": "🧭头条"}})
    return items, None

# ─── 微博热搜 ─────────────────────────
@register("weibo", "💬微博热搜")
def source_weibo() -> tuple[Optional[list[dict]], Optional[str]]:
    # 三级降级: Cookie直连 → 微博API → newsnow
    import os as _os
    
    # Tier 1: 有Cookie则直接请求
    weibo_cookie = _os.environ.get("WEIBO_COOKIE") or "SUB=_2AkMWIuNSf8NxqwJRmP8dy2rhaoV2ygrEieKgfhKJJRMxHRl-yT9jqk86tRB6PaLNvQZR6zYUcYVT1zSjoSreQHidcUq7"
    if weibo_cookie:
        url = "https://s.weibo.com/top/summary?cate=realtimehot"
        html = fetch_via_requests(url, headers={
            "User-Agent": DEFAULT_UA,
            "Cookie": weibo_cookie,
            "Referer": url,
        })
        if not html.startswith('ERROR'):
            items = []
            if HAS_BS4:
                soup = parse_html(html)
                for tr in soup.select('#pl_top_realtimehot table tbody tr')[1:]:
                    a = tr.select_one('td.td-02 a')
                    if a and 'javascript:void' not in a.get('href', ''):
                        title = a.text.strip()
                        href = a.get('href', '')
                        heat = tr.select_one('td.td-03')
                        flag = heat.text.strip() if heat else ''
                        if title:
                            items.append({"id": title, "title": title,
                                          "url": f"https://s.weibo.com{href}",
                                          "heat": '', "category": "社会",
                                          "extra": {"source": "💬微博", "flag": flag}})
            else:
                for m in re.finditer(r'<a[^>]+href="(/weibo\?[^"]+)"[^>]*>([^<]+)</a>', html):
                    href, title = m.group(1), m.group(2).strip()
                    if title and 'javascript:void' not in href:
                        items.append({"id": title, "title": title,
                                      "url": f"https://s.weibo.com{href}",
                                      "heat": '', "category": "社会",
                                      "extra": {"source": "💬微博"}})
            if items:
                return items, None

    # Tier 2: 微博API (无需Cookie)
    data = fetch_json("https://weibo.com/ajax/side/hotSearch",
                      headers={"User-Agent": DEFAULT_UA, "Referer": "https://weibo.com/"})
    if data and data.get('data'):
        items = []
        for item in data['data'].get('realtime', []):
            word = item.get('word', '')
            flag = item.get('flag', '')
            raw_hot = item.get('raw_hot', 0)
            if word:
                items.append({"id": f"wb_{item.get('word_scheme', word)}", "title": word,
                              "url": f"https://s.weibo.com/weibo?q={word}",
                              "heat": str(raw_hot) if raw_hot else '',
                              "category": "社会",
                              "extra": {"source": "💬微博", "flag": flag}})
        if items:
            return items, None

    return None, "所有通道都失败"

# ─── 澎湃新闻 ─────────────────────────
@register("thepaper", "📰澎湃热榜")
def source_thepaper() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar")
    if not data or 'data' not in data:
        return None, "API无数据"
    items = []
    for k in data.get('data', {}).get('hotNews', []):
        name = k.get('name', '')
        cid = k.get('contId', '')
        if name:
            items.append({"id": cid or name, "title": name,
                          "url": f"https://www.thepaper.cn/newsDetail_forward_{cid}",
                          "heat": '', "extra": {"source": "📰澎湃"}})
    return items, None

# ─── 贴吧热议 ─────────────────────────
@register("tieba", "💬贴吧热议")
def source_tieba() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://tieba.baidu.com/hottopic/browse/topicList")
    if not data:
        return None, "API无数据"
    inner = data.get('data', {})
    topic_list = []
    for key in ('bang_topic', 'sug_topic', 'manual_topic'):
        section = inner.get(key, {})
        if isinstance(section, dict):
            topic_list.extend(section.get('topic_list', []))
    items = []
    for t in topic_list:
        title = t.get('topic_name', t.get('title', ''))
        url = t.get('topic_url', t.get('url', ''))
        if title:
            items.append({"id": url or title, "title": title, "url": url or '',
                          "heat": '', "extra": {"source": "💬贴吧"}})
    return items, None if items else "贴吧无数据"

# ─── 虎扑 ─────────────────────────────
@register("hupu", "🏀虎扑热帖")
def source_hupu() -> tuple[Optional[list[dict]], Optional[str]]:
    html = fetch("https://bbs.hupu.com/topic-daily-hot")
    if html.startswith('ERROR'):
        return None, "页面获取失败"
    items = []
    for m in re.finditer(r'<li class="bbs-sl-web-post-body">[\s\S]*?<a href="(/[^"]+\.html)"[^>]*class="p-title"[^>]*>([^<]+)</a>', html):
        title = clean_html_text(m.group(2)).strip()
        if title:
            items.append({"id": m.group(1), "title": title,
                          "url": f"https://bbs.hupu.com{m.group(1)}",
                          "heat": '', "extra": {"source": "🏀虎扑"}})
    return items, None if items else "虎扑无数据"

# ─── IT之家 ──────────────────────────
@register("ithome", "🔬IT之家")
def source_ithome() -> tuple[Optional[list[dict]], Optional[str]]:
    html = fetch("https://www.ithome.com/list/")
    if html.startswith('ERROR'):
        return None, "页面获取失败"
    items = []
    ad_words = {"神券", "优惠", "补贴", "京东", "清仓", "发车"}
    if HAS_BS4:
        soup = parse_html(html)
        for li in soup.select('#list > div.fl > ul > li'):
            a = li.select_one('a.t')
            if not a: continue
            url = a.get('href', '')
            title = a.text.strip()
            if url and title and 'lapin' not in url and not any(w in title for w in ad_words):
                items.append({"id": url, "title": title, "url": url,
                              "heat": '', "extra": {"source": "🔬IT之家"}})
    else:
        for m in re.finditer(r'<a[^>]+class="t"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>', html):
            url, title = m.group(1), m.group(2).strip()
            if title and not any(w in title for w in ad_words):
                items.append({"id": url, "title": title, "url": url,
                              "heat": '', "extra": {"source": "🔬IT之家"}})
    return items, None if items else "无数据"

# ─── 凤凰网 ──────────────────────────
@register("ifeng", "🌐凤凰网")
def source_ifeng() -> tuple[Optional[list[dict]], Optional[str]]:
    html = fetch("https://www.ifeng.com/")
    if html.startswith('ERROR'):
        return None, "页面获取失败"
    m = re.search(r'var\s+allData\s*=\s*(\{[\\\s\S]*?\});', html)
    if not m: return None, "未找到allData"
    try: data = json.loads(m.group(1))
    except: return None, "JSON解析失败"
    items = [{"id": n.get('url', ''), "title": n.get('title', ''), "url": n.get('url', ''),
              "heat": '', "extra": {"source": "🌐凤凰"}}
             for n in data.get('hotNews1', []) if n.get('title', '')]
    return items, None

# ─── 36氪 ────────────────────────────
@register("36kr", "🔬36氪快讯")
def source_36kr():
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    CST = _tz(_td(hours=8))
    html = fetch_via_requests("https://www.36kr.com/newsflashes")
    if not html.startswith('ERROR'):
        items = []
        for m in re.finditer(r'class="newsflash-item[\s\S]*?class="item-title"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html):
            u, t = m.group(1), m.group(2).strip()
            if t: items.append({"id": u, "title": t, "url": f"https://www.36kr.com{u}" if u.startswith('/') else u, "heat": '', "extra": {"source": "🔬36氪"}})
        if items: return items, None
    today = _dt.now(CST).strftime('%Y-%m-%d')
    html2 = fetch_via_requests(f"https://36kr.com/hot-list/renqi/{today}/1", headers={"Referer": "https://www.36kr.com/"})
    if not html2.startswith('ERROR'):
        items = [{"id": m.group(1), "title": m.group(2).strip(), "url": m.group(1) if m.group(1).startswith('http') else f"https://36kr.com{m.group(1)}", "heat": '', "extra": {"source": "🔬36氪"}}
                 for m in re.finditer(r'class="article-item-title[^"]*"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html2) if m.group(2).strip()]
        if items: return items, None
    return None, "双通道都失败"

# ─── 腾讯新闻 ────────────────────────
@register("tencent", "🐧腾讯新闻")
def source_tencent() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://i.news.qq.com/web_backend/v2/getTagInfo?tagId=aEWqxLtdgmQ%3D", headers={"Referer": "https://news.qq.com/"})
    if not data or 'data' not in data: return None, "API无数据"
    items = []
    for tab in data['data'].get('tabs', [])[:1]:
        for news in tab.get('articleList', []):
            title = news.get('title', '')
            li = news.get('link_info', {})
            url = li.get('url', '') if isinstance(li, dict) else ''
            if title:
                items.append({"id": news.get('id', title), "title": title, "url": url,
                              "heat": '', "extra": {"source": "🐧腾讯"}})
    return items, None

# ─── V2EX ────────────────────────────
@register("v2ex", "💬V2EX")
def source_v2ex() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://www.v2ex.com/api/topics/hot.json", headers={"User-Agent": DEFAULT_UA})
    if not data or not isinstance(data, list): return None, "API无数据"
    items = [{"id": t.get('id', ''), "title": t.get('title', ''), "url": f"https://www.v2ex.com/t/{t.get('id', '')}",
              "heat": f"{t.get('replies', 0)}回复", "extra": {"source": "💬V2EX"}}
             for t in data if t.get('title', '')]
    return items[:20], None

# ─── 少数派 ──────────────────────────
@register("sspai", "✍️少数派")
def source_sspai() -> tuple[Optional[list[dict]], Optional[str]]:
    try:
        import requests as req
        from core import DEFAULT_UA
        r = req.get("https://sspai.com/api/v1/article/tag/page/get?limit=20&offset=0&tag=%E7%83%AD%E9%97%A8%E6%96%87%E7%AB%A0",
                    headers={"User-Agent": DEFAULT_UA}, timeout=10)
        if r.status_code != 200: return None, "API请求失败"
        data = r.json()
    except Exception as e:
        return None, f"请求失败: {e}"
    if not data or 'data' not in data: return None, "API无数据"
    items = [{"id": a.get('id', ''), "title": a.get('title', ''), "url": f"https://sspai.com/post/{a.get('id', '')}",
              "heat": '', "extra": {"source": "✍️少数派"}}
             for a in data.get('data', []) if a.get('title', '')]
    return items[:20], None

# ─── 豆瓣 ────────────────────────────
@register("douban", "🎬豆瓣热门")
def source_douban() -> tuple[Optional[list[dict]], Optional[str]]:
    data = fetch_json("https://movie.douban.com/j/search_subjects?type=movie&tag=hot&page_limit=20&page_start=0",
                      headers={"User-Agent": DEFAULT_UA, "Referer": "https://movie.douban.com/"})
    if not data or 'subjects' not in data: return None, "豆瓣API失败"
    items = [{"id": m.get('id', ''), "title": m.get('title', ''),
              "url": m.get('url', f"https://movie.douban.com/subject/{m.get('id', '')}/"),
              "heat": m.get('rate', ''), "extra": {"source": "🎬豆瓣"}}
             for m in data.get('subjects', []) if m.get('title', '')]
    return items[:20], None
