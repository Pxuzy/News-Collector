#!/usr/bin/env python
"""
正文提取 v3 — trafilatura + requests双引擎 + 降级
"""
import sys
import os
import re
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(__file__))
from core import DEFAULT_UA, fetch_via_requests
from store import _db as get_db

# 不需要提取正文的源
HAS_TRAFILATURA = False
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    pass

UA = DEFAULT_UA
TIMEOUT = 15

# 不需要提取正文的源
SKIP_PATTERNS = [
    re.compile(p) for p in [
        r'douyin\.com', r'weibo\.com/.*weibo\?', r'baidu\.com/s\?',
        r'search\.bilibili', r'zhihu\.com/api', r'toutiao\.com/trending',
        r'tieba\.baidu\.com', r'hupu\.com', r'sspai\.com',
        r'jin10\.com', r'xueqiu\.com/s/', r'nowcoder\.com',
        r'dongqiudi\.com', r'juejin\.cn/post',
    ]
]


def _should_skip(url):
    return any(p.search(url) for p in SKIP_PATTERNS)


def extract(url):
    """三级提取引擎: trafilatura → readability → 正则"""
    if not url or not url.startswith('http') or _should_skip(url):
        return None
    body = None

    # Tier 1: trafilatura (最准)
    if HAS_TRAFILATURA:
        try:
            downloaded = trafilatura.fetch_url(url, timeout=TIMEOUT)
            if downloaded:
                body = trafilatura.extract(downloaded,
                                           include_links=False, include_images=False,
                                           include_tables=False, output_format='txt',
                                           favor_precision=True)
        except Exception:
            pass

    # Tier 2: requests + readability-like正则 (通过 core 统一入口)
    if not body:
        try:
            raw = fetch_via_requests(url, timeout=TIMEOUT)
            if raw and not raw.startswith('ERROR') and len(raw) > 500:
                text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', raw)
                text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text)
                text = re.sub(r'<header[^>]*>[\s\S]*?</header>', '', text)
                text = re.sub(r'<footer[^>]*>[\s\S]*?</footer>', '', text)
                text = re.sub(r'<nav[^>]*>[\s\S]*?</nav>', '', text)
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > 50:
                    body = text[:30000]
        except Exception:
            pass

    return body if body and len(body) > 50 else None


def _gen_summary(text, title):
    """前2句摘要"""
    if not text:
        return ''
    sentences = re.split(r'[。！？\n]', text)
    summary = '。'.join(s.strip() for s in sentences[:2] if s.strip())[:200]
    return summary + ('。' if summary else '')


def run(batch=30, workers=4):
    conn = get_db()
    rows = conn.execute("""
        SELECT n.id, n.source, n.title, n.url FROM news_items n
        LEFT JOIN articles a ON n.url=a.url AND a.content!=''
        WHERE a.url IS NULL AND n.url LIKE 'http%'
        ORDER BY n.heat_score DESC, n.last_seen DESC
        LIMIT ?
    """, (batch,)).fetchall()
    conn.close()

    if not rows:
        print("✅ 全部已提取")
        return

    print(f"📄 待提取: {len(rows)} 条 (引擎:{'trafilatura' if HAS_TRAFILATURA else '正则'})")

    engine_label = "trafilatura" if HAS_TRAFILATURA else "regex"

    def extract_one(r):
        body = extract(r['url'])
        if body:
            time.sleep(0.15)
        return r, body

    ok = 0
    extracted = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {pool.submit(extract_one, r): r for r in rows}
        for fut in as_completed(fut_map):
            r, body = fut.result()
            if body:
                summary = _gen_summary(body, r['title'])
                extracted.append((r, body, summary))
                ok += 1
                print(f"  ✅ [{r['source']}] {r['title'][:40]}... {len(body)}字 ({engine_label})", flush=True)
            else:
                print(f"  ⏭️ [{r['source']}] {r['title'][:40]}...", flush=True)

    if extracted:
        conn2 = get_db()
        try:
            fetched_at = datetime.now(timezone.utc).isoformat()
            conn2.executemany(
                "INSERT OR IGNORE INTO articles(id,source,title,url,content,summary,fetched_at) VALUES(?,?,?,?,?,?,?)",
                [(r['id'], r['source'], r['title'][:500], r['url'], body, summary, fetched_at)
                 for r, body, summary in extracted],
            )
            conn2.executemany(
                "UPDATE news_items SET summary=? WHERE source=? AND id=?",
                [(summary[:500], r['source'], r['id']) for r, _, summary in extracted],
            )
            conn2.commit()
        except Exception:
            conn2.rollback()
            raise
        finally:
            conn2.close()

    print(f"\n✅ {ok}/{len(rows)} 条提取成功 (引擎:{engine_label})")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--batch", type=int, default=30)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--url", help="单URL测试")
    a = p.parse_args()
    if a.url:
        body = extract(a.url)
        print(body[:1000] if body else "❌ 无法提取")
    else:
        run(a.batch, a.workers)
