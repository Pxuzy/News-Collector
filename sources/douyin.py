"""
抖音热榜 — 三层降级策略
"""
from typing import Optional
from core import fetch_json, fetch_via_requests, DEFAULT_UA, HAS_REQUESTS
from sources import register


@register("douyin", "🎵抖音热榜")
def source_douyin() -> tuple[Optional[list[dict]], Optional[str]]:
    # T1: Cookie注入
    try:
        if HAS_REQUESTS:
            import requests as req
            login_resp = req.get("https://login.douyin.com/", timeout=10)
            cookies = "; ".join(f"{c.name}={c.value}" for c in login_resp.cookies)
            if cookies:
                api_url = "https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1"
                resp = req.get(api_url, headers={
                    "User-Agent": DEFAULT_UA, "Cookie": cookies, "Referer": "https://www.douyin.com/"
                }, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    wl = data.get('data', {}).get('word_list', [])
                    if wl:
                        items = [{"id": w.get('sentence_id', w.get('word', '')), "title": w.get('word', ''),
                                  "url": f"https://www.douyin.com/hot/{w.get('sentence_id', '')}",
                                  "heat": str(w.get('hot_value', '')), "extra": {"source": "🎵抖音"}}
                                 for w in wl[:20] if w.get('word', '')]
                        return items, None
    except Exception:
        pass

    # T2: Playwright
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=DEFAULT_UA)
            page.goto('https://www.douyin.com/hot', timeout=30000)
            page.wait_for_timeout(3000)
            entries = page.evaluate('''() => {
                const r = [];
                for (const a of document.querySelectorAll('a[href*="/hot/"]')) {
                    const h = a.querySelector('h1,h2,h3,h4');
                    if (!h) continue;
                    const t = h.textContent.trim();
                    if (t && !t.includes('抖音热榜')) r.push({title: t, url: a.href});
                }
                return r;
            }''')
            browser.close()
            if entries:
                items = [{"id": e['title'], "title": e['title'], "url": e['url'],
                          "heat": '', "extra": {"source": "🎵抖音"}} for e in entries[:20]]
                return items, None
    except Exception:
        pass

    return None, "抖音获取失败"
