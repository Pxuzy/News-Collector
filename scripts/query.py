#!/usr/bin/env python
# coding=utf-8
"""
新闻查询 CLI — python query.py --keyword "A股" --days 7 --source baidu
"""
import argparse
import sys
import os

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from store import query, get_stats


def fmt_time(ts):
    if not ts:
        return ''
    return ts[:16].replace('T', ' ')


def main():
    parser = argparse.ArgumentParser(description="新闻历史查询")
    parser.add_argument("--keyword", "-k", help="搜索关键词")
    parser.add_argument("--days", "-d", type=int, default=None, help="最近N天")
    parser.add_argument("--source", "-s", help="来源过滤 (如 baidu, weibo)")
    parser.add_argument("--limit", "-l", type=int, default=30, help="返回条数")
    parser.add_argument("--offset", "-o", type=int, default=0)
    parser.add_argument("--stats", action="store_true", help="显示统计概览")
    parser.add_argument("--csv", action="store_true", help="CSV格式输出")
    args = parser.parse_args()

    if args.stats:
        s = get_stats(args.days or 7)
        print(f"📊 最近{s['days']}天统计")
        print(f"   总条数: {s['total']}")
        print()
        print(f"   {'源':15s} {'条数':>6s}  {'最后采集':16s}")
        print(f"   {'-'*15} {'-'*6}  {'-'*16}")
        for src in s['by_source']:
            print(f"   {src['source']:15s} {src['count']:6d}  {fmt_time(src['last'])}")
        if s['crawl_stats']:
            print()
            print(f"   采集健康度 (最近{s['days']}天):")
            for cs in s['crawl_stats']:
                total_c = cs['ok_count'] + cs['fail_count']
                rate = cs['ok_count'] / total_c * 100 if total_c > 0 else 0
                bar = '🟢' * cs['ok_count'] + '🔴' * cs['fail_count']
                print(f"   {cs['source']:15s} {bar}  {rate:.0f}%")
        return

    if not args.keyword and not args.days and not args.source:
        # 默认显示最近1天
        args.days = 1

    rows, total = query(
        keyword=args.keyword,
        days=args.days,
        source=args.source,
        limit=args.limit,
        offset=args.offset
    )

    if not rows:
        print("🔍 没有匹配的新闻")
        return

    if args.csv:
        import csv
        writer = csv.writer(sys.stdout)
        writer.writerow(["source", "title", "url", "heat", "first_seen", "last_seen", "seen_count"])
        for r in rows:
            writer.writerow([r['source'], r['title'], r['url'], r['heat'],
                            fmt_time(r['first_seen']), fmt_time(r['last_seen']), r['seen_count']])
        return

    print(f"🔍 找到 {total} 条结果 (显示 {len(rows)} 条)")
    if args.keyword:
        print(f"   关键词: {args.keyword}")
    print()

    current_source = None
    for r in rows:
        source = r['source']
        if source != current_source:
            print(f"── {source} ──")
            current_source = source
        heat = f" [{r['heat']}]" if r['heat'] else ""
        seen = f" (x{r['seen_count']})" if r['seen_count'] > 1 else ""
        print(f"  {r['title']}{heat}")
        print(f"  {r['url']}")
        print(f"  {fmt_time(r['last_seen'])}{seen}")
        print()


if __name__ == "__main__":
    main()
