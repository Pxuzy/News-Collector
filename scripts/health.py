#!/usr/bin/env python
# coding=utf-8
"""
健康看板 v2 — 各源采集状态 + 增量统计 + DB健康
"""
import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from store import _db as get_db, CST

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")


def health_report(days=1):
    conn = get_db()
    cutoff = (datetime.now(CST) - timedelta(days=days)).isoformat()

    sources = conn.execute("""
        SELECT source, COUNT(*) as runs,
               SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) as ok,
               SUM(CASE WHEN status!='ok' THEN 1 ELSE 0 END) as fail,
               ROUND(AVG(CASE WHEN status='ok' THEN duration_ms ELSE NULL END)) as avg_ms
        FROM crawl_log WHERE started_at>=?
        GROUP BY source ORDER BY source
    """, (cutoff,)).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM news_items WHERE last_seen>=? AND COALESCE(is_duplicate,0)=0", (cutoff,)).fetchone()[0]
    new_today = conn.execute("SELECT COUNT(*) FROM news_items WHERE first_seen>=? AND COALESCE(is_duplicate,0)=0", (cutoff,)).fetchone()[0]
    by_source = conn.execute(
        "SELECT source,COUNT(*) as cnt FROM news_items WHERE last_seen>=? AND COALESCE(is_duplicate,0)=0 GROUP BY source ORDER BY cnt DESC",
        (cutoff,)).fetchall()
    by_cat = conn.execute(
        "SELECT category,COUNT(*) as cnt FROM news_items WHERE last_seen>=? AND category!='' AND COALESCE(is_duplicate,0)=0 GROUP BY category ORDER BY cnt DESC",
        (cutoff,)).fetchall()
    db_size = conn.execute("SELECT COUNT(*) FROM news_items").fetchone()[0]
    db_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    # 空热度统计
    empty_heat = conn.execute("SELECT COUNT(*) FROM news_items WHERE (heat='' OR heat='0') AND last_seen>=? AND COALESCE(is_duplicate,0)=0",
                              (cutoff,)).fetchone()[0]
    conn.close()

    lines = [f"# 📊 健康看板 — 最近{days}天\n"]
    lines.append(f"**总新闻**: {total} ({new_today} 新增) | **DB**: {db_size}条 / {db_articles}篇正文 | **空热度**: {empty_heat}\n")
    lines.append("---\n")
    lines.append("### 采集源状态\n")
    lines.append("| 源 | 运行 | ✅成功 | ❌失败 | 平均耗时 |\n")
    lines.append("|---|---|---|---|---|\n")
    for s in sources:
        lines.append(f"| {s['source']} | {s['runs']} | {s['ok']} | {s['fail']} | {s['avg_ms'] or '-'}ms |\n")

    lines.append("\n### 信源产出\n")
    lines.append("| 源 | 条数 |\n|---|---|\n")
    for s in by_source:
        lines.append(f"| {s['source']} | {s['cnt']} |\n")

    if by_cat:
        lines.append("\n### 分类分布\n")
        lines.append("| 分类 | 条数 |\n|---|---|\n")
        for c in by_cat:
            lines.append(f"| {c['category']} | {c['cnt']} |\n")

    return ''.join(lines)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=1)
    p.add_argument("--history", action="store_true")
    p.add_argument("--watch", action="store_true")
    a = p.parse_args()
    print(health_report(days=a.days))
    if a.watch:
        import time
        try:
            while True:
                time.sleep(60)
                print(f"\n--- {datetime.now(CST).isoformat()} ---")
                print(health_report(days=a.days))
        except KeyboardInterrupt:
            pass
