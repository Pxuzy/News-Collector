#!/usr/bin/env python
# coding=utf-8
"""
Telegram 新闻简报专用数据接口 v1.0

为 telegram-news-briefing skill 提供一站式数据查询。
整合 store 层 + classifier 分类映射 + 源元数据。

用法:
  python briefing_api.py --status                  # 数据概览
  python briefing_api.py --groups domestic         # 国内分组
  python briefing_api.py --groups intl,ai          # 国际+AI
  python briefing_api.py --groups all              # 全量
  python briefing_api.py --sections                # 按简报7板块输出
"""
import sys, os, json
from datetime import datetime, timezone, timedelta

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
for path in (SCRIPT_DIR, PROJECT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)
from store import batch_query, query_by_categories, get_stats, heat_to_score, normalize_heat, _db
from sources import get_source_cn, get_group_sources, all_group_names
from classifier import (
    BRIEFING_CATEGORIES, CATEGORY_MAP,
    map_to_briefing_category, briefing_section_sort_key
)

CST = timezone(timedelta(hours=8))
TOOLKIT = PROJECT_DIR
DB = os.path.join(TOOLKIT, "data", "news.db")
FRESH_HOURS = 2


# ─── 公共: 条目格式化 ───

def format_item(item: dict) -> dict:
    """格式化单条新闻为简报可用格式

    补全字段:
    - source_cn: 来源中文名
    - briefing_category: 简报分类 (7板块)
    - heat_display: 标准化热力显示
    - rank_info: 排名信息 (从extra解析)
    """
    item = dict(item)
    src = item.get("source", "")
    item["source_cn"] = get_source_cn(src)

    # 简报分类
    raw_cat = item.get("category", "")
    item["briefing_category"] = map_to_briefing_category(raw_cat)

    # 标准化热力
    raw_heat = item.get("heat", "")
    item["heat_display"] = normalize_heat(raw_heat)
    item["heat_score"] = int(item.get("heat_score") or heat_to_score(raw_heat))

    # 排名信息: 尝试从 extra 的 index/rank 字段提取
    extra_raw = item.get("extra", "{}")
    try:
        extra = json.loads(extra_raw) if isinstance(extra_raw, str) else extra_raw
    except (json.JSONDecodeError, TypeError):
        extra = {}
    item["rank"] = extra.get("index", extra.get("rank", ""))
    item["extra_obj"] = extra

    return item


# ─── 数据新鲜度 ───

def is_fresh(source: str = None) -> bool:
    """检查数据是否够新鲜 (< FRESH_HOURS 小时)"""
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


def db_timestamp() -> str:
    """DB中最新的数据时间"""
    c = _db()
    try:
        row = c.execute("SELECT MAX(last_seen) as ts FROM news_items WHERE COALESCE(is_duplicate,0)=0").fetchone()
        return row["ts"] if row and row["ts"] else ""
    finally:
        c.close()


# ─── 分组查询 ───

def get_group_news(group: str, days: int = 1, limit: int = 15) -> list[dict]:
    """获取指定分组的新闻，返回格式化后的条目列表"""
    sources = get_group_sources(group)
    if not sources:
        return []
    result = batch_query(sources, days=days, limit=limit)
    items = []
    for src_list in result.values():
        for item in src_list:
            items.append(format_item(item))
    # 按热力降序
    items.sort(key=lambda x: int(x.get("heat_score") or _safe_heat_int(x.get("heat", "0"))), reverse=True)
    return items


def get_grouped_news(groups: list[str] = None, days: int = 1, limit: int = 15) -> dict[str, list[dict]]:
    """获取多个分组的新闻，返回 {group: [items]}"""
    if groups is None:
        groups = ["domestic", "intl", "ai"]
    result = {}
    for g in groups:
        items = get_group_news(g, days=days, limit=limit)
        result[g] = items
    return result


# ─── 简报7板块查询 ───

def get_section_news(days: int = 1, limit: int = 15) -> dict[str, list[dict]]:
    """按简报7板块查询，返回 {板块名: [items]}

    直接查DB中 category 字段，然后映射到 7 板块。
    不依赖分组，对所有源有效。
    """
    # 需要查的原始 category 列表
    raw_categories = list(CATEGORY_MAP.keys())

    # 按原始类别查
    raw_results = query_by_categories(raw_categories, days=days, limit=limit*2)

    # 合并到简报板块
    sections: dict[str, list[dict]] = {c: [] for c in BRIEFING_CATEGORIES}
    for raw_cat, items in raw_results.items():
        briefing_cat = map_to_briefing_category(raw_cat)
        for item in items:
            fmt = format_item(item)
            sections[briefing_cat].append(fmt)

    # 各板块去重+排序+截断
    for cat in sections:
        seen = set()
        unique = []
        for item in sections[cat]:
            key = item.get("id", "") or item.get("url", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(item)
        unique.sort(key=lambda x: int(x.get("heat_score") or _safe_heat_int(x.get("heat", "0"))), reverse=True)
        sections[cat] = unique[:limit]

    return sections


# ─── 数据概览 ───

def get_overview(days: int = 1) -> dict:
    """数据概览 — 各分组条数、新鲜度、分类分布"""
    stats = get_stats(days=days)

    # 分组统计
    group_counts = {}
    for g in all_group_names():
        sources = get_group_sources(g)
        src_set = set(sources)
        count = sum(1 for s in stats.get("by_source", []) if s["source"] in src_set)
        group_counts[g] = count

    # 简报板块统计
    section_counts = {}
    for raw_cat, mapping in CATEGORY_MAP.items():
        briefing_cat = mapping
        section_counts[briefing_cat] = section_counts.get(briefing_cat, 0) + 1

    # 按分类统计
    by_briefing_cat = {}
    for src in stats.get("by_category", []):
        bc = map_to_briefing_category(src["category"])
        by_briefing_cat[bc] = by_briefing_cat.get(bc, 0) + src["count"]

    return {
        "fresh": is_fresh(),
        "db_timestamp": db_timestamp(),
        "total": stats.get("total", 0),
        "new_today": stats.get("new", 0),
        "days": days,
        "by_group": group_counts,
        "by_briefing_category": by_briefing_cat,
        "crawl_stats": stats.get("crawl_stats", []),
    }


# ─── CLI ───

def _safe_heat_int(heat_val) -> int:
    """安全地将热力值转为整数用于排序"""
    try:
        s = str(heat_val).strip()
        if not s or len(s) > 30:
            return 0
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def cli():
    import argparse
    parser = argparse.ArgumentParser(description="简报数据接口")
    parser.add_argument("--status", action="store_true", help="数据概览")
    parser.add_argument("--groups", type=str, help="分组名(逗号分隔), 如 domestic,intl,ai")
    parser.add_argument("--sections", action="store_true", help="按简报7板块输出")
    parser.add_argument("--days", type=int, default=1, help="最近N天 (默认1)")
    parser.add_argument("--limit", type=int, default=15, help="每组/板块返回条数 (默认15)")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    args = parser.parse_args()

    if args.status:
        data = get_overview(days=args.days)
    elif args.sections:
        data = get_section_news(days=args.days, limit=args.limit)
    elif args.groups:
        groups = [g.strip() for g in args.groups.split(",")]
        data = get_grouped_news(groups=groups, days=args.days, limit=args.limit)
    else:
        parser.print_help()
        return

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    cli()
