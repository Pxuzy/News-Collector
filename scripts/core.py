#!/usr/bin/env python
# coding=utf-8
"""
核心模块 — 借鉴 newsnow (ourongxing) 的 fetch + type 层
"""
import json, re, time, os
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

CST = timezone(timedelta(hours=8))

# ─── 自适应采集间隔 (秒) ──
SOURCE_INTERVALS: dict[str, int] = {
    # ─── 国内热点（高频容易被反爬，300-600s 合理） ───
    "baidu": 300, "zhihu": 300, "toutiao": 300, "weibo": 300,
    "bilibili": 300, "douyin": 300,
    "thepaper": 300, "tieba": 300, "hupu": 300, "ithome": 300,
    "ifeng": 300, "36kr": 300, "tencent": 300,
    "juejin": 300, "sspai": 300, "v2ex": 300, "douban": 600,
    # ─── 财经（盘中需要相对高频） ───
    "wallstreetcn": 180, "xueqiu": 180, "jin10": 120,
    # ─── 国际新闻（变化慢，适当低频） ───
    "bbc_world": 600, "guardian": 600, "reuters": 600,
    "aljazeera": 600, "france24": 600,
    "googlenews": 300, "googlenews_cn": 300, "googlenews_tech": 300, "googlenews_business": 300,
    # ─── AI/学术（日更为主） ───
    "huggingface": 1800, "aihot": 600, "arxiv": 3600,
    "tldr_ai": 1800, "lobsters": 600, "devto": 600,
    "openai_blog": 1800, "google_blog": 1800,
    # ─── 开发社区（变化快但价值分散） ───
    "hackernews": 300, "reddit": 300, "github": 600,
    # ─── 国际科技 ───
    "techcrunch": 600, "arstechnica": 600, "wired": 600, "techmeme": 600,
    # ─── 国内科技 ───
    "tmtpost": 600,
    # ─── 小众/其他 ───
    "bilibili_pop": 300,
    "nowcoder": 300, "dongqiudi": 300, "producthunt": 1800,
}


def get_interval(source: str) -> int:
    """获取源的推荐采集间隔"""
    return SOURCE_INTERVALS.get(source, 300)


# ─── 统一 Fetch 层 ──
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

HAS_REQUESTS = False
try:
    import requests as req_lib
    HAS_REQUESTS = True
except ImportError:
    pass

PROXY = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or ""
PROXY_CONFIG = {"http": PROXY, "https": PROXY} if PROXY else None

HAS_BS4 = False
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    pass


def fetch(url: str, headers: Optional[dict] = None, timeout: int = 12, retries: int = 2) -> str:
    """urllib版请求 — clean fetch like ofetch"""
    if headers is None:
        headers = {"User-Agent": DEFAULT_UA, "Accept": "text/html,application/json,*/*"}
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
            else:
                return f'ERROR: {e}'
    return 'ERROR: max retries'


def fetch_json(url: str, headers: Optional[dict] = None, timeout: int = 12) -> Optional[dict | list]:
    """Fetch JSON — 同 ofetch 的模式"""
    data = fetch(url, headers, timeout)
    if data and not data.startswith('ERROR'):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return None
    return None


def fetch_via_requests(url: str, headers: Optional[dict] = None, timeout: int = 12) -> str:
    """requests版请求 (功能更强, 处理Cookie/重定向更好)"""
    if not HAS_REQUESTS:
        return fetch(url, headers, timeout)
    if headers is None:
        headers = {"User-Agent": DEFAULT_UA}
    try:
        r = req_lib.get(url, headers=headers, timeout=timeout,
                        proxies=PROXY_CONFIG, allow_redirects=True)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return f'ERROR: {e}'


# ─── RSS 解析器 ──
def rss_to_items(url: str, source_name: str, icon: str, limit: int = 10,
                 hours: int = 48, extra_headers: Optional[dict] = None) -> tuple[Optional[list[dict]], Optional[str]]:
    import feedparser
    headers = {"User-Agent": DEFAULT_UA}
    if extra_headers:
        headers.update(extra_headers)
    html = fetch_via_requests(url, headers)
    if html.startswith('ERROR'):
        return None, f"RSS获取失败"
    feed = feedparser.parse(html)
    now = datetime.now(timezone.utc)
    items = []
    for e in feed.entries[:limit]:
        t, l = e.get('title', ''), e.get('link', '')
        pub = e.get('published_parsed')
        if pub and datetime.fromtimestamp(__import__('time').mktime(pub), tz=timezone.utc) < now - timedelta(hours=hours):
            continue
        if t:
            items.append({"id": l or t, "title": t, "url": l or '',
                          "heat": '', "extra": {"source": f"{icon}{source_name}"}})
    return (items[:limit], None) if items else (None, "RSS无数据")


# ─── HTML 清理工具 ──
def clean_html_text(text: Optional[str]) -> str:
    """去掉HTML标签和多余的空白"""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_html(html: str, parser: str = 'html.parser') -> Optional[object]:
    """统一HTML解析入口 — 同 newsnow 用 cheerio 的模式"""
    if not HAS_BS4:
        return None
    return BeautifulSoup(html, parser)
