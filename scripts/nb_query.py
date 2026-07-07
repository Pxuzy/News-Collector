#!/usr/bin/env python
# coding=utf-8
"""
news-toolkit 数据库查询桥接脚本

用法：
  python nb_query.py --status                          # 数据库统计
  python nb_query.py --sources weibo,baidu --limit 10  # 查特定源
  python nb_query.py --source weibo --limit 10         # 单源
  python nb_query.py --all --limit 30                  # 全部源（最近）
  python nb_query.py --refresh                         # 强制刷新采集
  python nb_query.py --category 时政 --limit 10        # 按分类查

自动检查: 数据 < 2 小时直接用，否则先跑采集再查。
输出: JSON 到 stdout，供 Hermes 解析。
"""
import sys
import os
import json
import subprocess
from datetime import datetime, timezone, timedelta

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CST = timezone(timedelta(hours=8))
TOOLKIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(TOOLKIT, "data", "news.db")
sys.path.insert(0, os.path.join(TOOLKIT, "scripts"))
from store import query, get_stats, _db

FRESH_HOURS = 2  # 数据有效窗口

# ─── 源分组 ───
DOMESTIC_SOURCES = ["baidu", "weibo", "douyin", "toutiao", "zhihu",
                    "bilibili", "bilibili_pop", "thepaper", "tieba", "hupu",
                    "ithome", "ifeng", "36kr", "tencent", "v2ex", "sspai", "douban"]

INTL_SOURCES = ["hackernews", "reddit", "github",
                "bbc_world", "guardian", "aljazeera", "reuters", "france24",
                "googlenews", "googlenews_cn", "googlenews_tech", "googlenews_business"]

AI_ACADEMIC_SOURCES = ["aihot", "huggingface", "arxiv", "tldr_ai",
                       "producthunt", "lobsters", "devto",
                       "openai_blog", "techcrunch", "techmeme", "arstechnica",
                       "wired", "tmtpost", "juejin", "nowcoder", "dongqiudi",
                       "wallstreetcn", "jin10", "xueqiu",
                       "google_blog", "appso"]

SOURCE_GROUPS = {
    "domestic": DOMESTIC_SOURCES,
    "intl": INTL_SOURCES,
    "ai": AI_ACADEMIC_SOURCES,
    "all": DOMESTIC_SOURCES + INTL_SOURCES + AI_ACADEMIC_SOURCES,
}


def get_timestamp():
    """DB 中最新数据的时间"""
    c = _db()
    try:
        row = c.execute("SELECT MAX(last_seen) as ts FROM news_items").fetchone()
        return row["ts"] if row and row["ts"] else None
    finally:
        c.close()


def is_fresh(source=None):
    """检查数据是否够新鲜"""
    c = _db()
    try:
        cutoff = (datetime.now(CST) - timedelta(hours=FRESH_HOURS)).isoformat()
        if source:
            row = c.execute(
                "SELECT COUNT(*) as cnt FROM news_items WHERE source=? AND last_seen>=? AND COALESCE(is_duplicate,0)=0",
                (source, cutoff)
            ).fetchone()
            return row["cnt"] > 0 if row else False
        else:
            row = c.execute(
                "SELECT COUNT(*) as cnt FROM news_items WHERE last_seen>=? AND COALESCE(is_duplicate,0)=0",
                (cutoff,)
            ).fetchone()
            return row["cnt"] > 0 if row else False
    finally:
        c.close()


def run_collection(sources=None, timeout=180):
    """运行 multi_source_news.py 采集"""
    cmd = [sys.executable, os.path.join(TOOLKIT, "multi_source_news.py"), "--force"]
    if sources:
        cmd.extend(["--source", ",".join(sources)])
    else:
        cmd.append("--core")
    print(f"[nb_query] Running: {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=TOOLKIT,
    )
    if result.returncode != 0:
        print(f"[nb_query] Collector stderr: {result.stderr[:500]}", file=sys.stderr)
        return False
    print(f"[nb_query] Collector stdout: {result.stdout[:500]}", file=sys.stderr)
    return True


def resolve_sources(source_names):
    """解析输入为源列表"""
    if not source_names:
        return None  # 全量

    resolved = []
    for name in source_names:
        name = name.strip().lower()
        if name in SOURCE_GROUPS:
            resolved.extend(SOURCE_GROUPS[name])
        else:
            resolved.append(name)
    return list(set(resolved))


def output_result(items, total, meta):
    """统一 JSON 输出"""
    result = {
        "meta": meta,
        "total": total,
        "items": items,
        "timestamp": datetime.now(CST).isoformat(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="news-toolkit 数据库查询桥接")
    parser.add_argument("--status", action="store_true", help="数据库统计")
    parser.add_argument("--refresh", action="store_true", help="强制刷新后查询")
    parser.add_argument("--sources", help="源列表逗号分隔，支持分组名 (domestic/intl/ai/all)")
    parser.add_argument("--source", help="单源")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--category", help="分类过滤")
    parser.add_argument("--days", type=int, default=1, help="最近N天 (默认1)")
    parser.add_argument("--all", action="store_true", help="全部源")
    args = parser.parse_args()

    # ── status 模式 ──
    if args.status:
        s = get_stats(args.days)
        ts = get_timestamp()
        fresh = is_fresh()
        result = {
            "status": "ok",
            "db_path": DB,
            "total": s["total"],
            "new_today": s["new"],
            "last_update": ts,
            "fresh": fresh,
            "fresh_hours": FRESH_HOURS,
            "by_source": s["by_source"],
            "by_category": s.get("by_category", []),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # ── 解析请求的源 ──
    source_names = []
    if args.sources:
        source_names = [s.strip() for s in args.sources.split(",")]
    if args.source:
        source_names.append(args.source)
    if args.all:
        source_names.append("all")

    sources = resolve_sources(source_names)

    # ── 检查是否需要刷新 ──
    needs_refresh = args.refresh
    stale_sources = []
    if not needs_refresh and sources:
        # 检查每个源是否都新鲜
        all_fresh = all(is_fresh(s) for s in sources)
        if not all_fresh:
            stale_sources = [s for s in sources if not is_fresh(s)]
            print(f"[nb_query] Stale sources ({len(stale_sources)}): {stale_sources[:5]}...",
                  file=sys.stderr)
            needs_refresh = True
    elif not needs_refresh and sources is None:
        # 检查整体是否新鲜
        if not is_fresh():
            print("[nb_query] All data stale, need refresh", file=sys.stderr)
            needs_refresh = True

    # ── 刷新采集 ──
    refreshed = False
    if needs_refresh:
        print(f"[nb_query] Refreshing data (sources={'core' if not sources else sources[:5]}...)",
              file=sys.stderr)
        ok = run_collection(stale_sources if stale_sources else None)
        if ok:
            refreshed = True
            print("[nb_query] Collection OK", file=sys.stderr)
        else:
            print("[nb_query] Collection FAILED, using stale data", file=sys.stderr)
    else:
        print(f"[nb_query] Data is fresh (within {FRESH_HOURS}h), using DB directly",
              file=sys.stderr)

    # ── 查询数据 ──
    all_results = []
    total_all = 0
    per_source_limit = max(1, min(args.limit, 50))

    if sources:
        for src in sources:
            items, total = query(source=src, days=args.days,
                                 category=args.category, limit=per_source_limit)
            for it in items:
                it["_query_source"] = src
            all_results.extend(items)
            total_all += total
    else:
        items, total_all = query(days=args.days, category=args.category,
                                 limit=args.limit)
        all_results = items

    meta = {
        "db_path": DB,
        "fresh_hours": FRESH_HOURS,
        "refreshed": refreshed,
        "requested_sources": source_names,
        "resolved_sources_count": len(sources) if sources else "all",
        "returned": len(all_results),
    }
    output_result(all_results, total_all, meta)


if __name__ == "__main__":
    main()
