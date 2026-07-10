"""
GitHub Trending — bs4解析, 修复SVG泄漏
"""
from typing import Optional
from core import fetch_via_requests, clean_html_text, parse_html, HAS_BS4, DEFAULT_UA
from sources import register


@register("github", "🐙GitHub趋势")
def source_github() -> tuple[Optional[list[dict]], Optional[str]]:
    html = fetch_via_requests("https://github.com/trending?spoken_language_code=",
                              {"User-Agent": DEFAULT_UA, "Accept": "text/html,application/xhtml+xml"})
    if html.startswith('ERROR'):
        return None, "页面获取失败"
    items = []
    if HAS_BS4:
        soup = parse_html(html)
        for article in soup.select('main .Box div[data-hpc] article'):
            a = article.select_one('h2 a')
            if not a: continue
            title = clean_html_text(a.text.replace('\n', '').strip())
            href = a.get('href', '')
            se = article.select_one('[href$=stargazers]')
            stars = clean_html_text(se.text.replace('\n', '').replace(' ', '')) if se else ''
            desc = article.select_one('p')
            desc_t = desc.text.strip() if desc else ''
            if href and title:
                items.append({"id": href.strip('/'), "title": title,
                              "url": f"https://github.com{href.strip()}",
                              "heat": f"⭐{stars}" if stars else '',
                              "extra": {"source": "🐙GitHub", "hover": desc_t[:200], "desc": desc_t[:200]}})
    else:
        import re
        for m in re.finditer(r'<article[^>]*>[\s\S]*?<h2[^>]*>[\s\S]*?<a\s+href="(/[^"]+)"[^>]*>([\s\S]*?)</a>', html):
            title = clean_html_text(m.group(2).replace('\n', '').replace(' ', ''))
            if title:
                items.append({"id": m.group(1).strip('/'), "title": title,
                              "url": f"https://github.com{m.group(1).strip()}",
                              "heat": '', "extra": {"source": "🐙GitHub"}})
    return items, None if items else "GitHub无数据"
