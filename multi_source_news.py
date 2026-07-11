#!/usr/bin/env python
# coding=utf-8
"""
多源新闻聚合采集器 v5.0 — 增量采集 + 分类 + 保留策略
"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
for path in (SCRIPTS_DIR, PROJECT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)
from core import CST, get_interval, parse_parallel  # noqa: E402
from store import (  # noqa: E402
    filter_due_sources,
    init_db,
    log_crawl,
    prune,
    sync_source_catalog,
    upsert_news,
    cross_source_dedup,
    vacuum,
)
from sources import all_sources, core_sources  # noqa: E402
from classifier import classify_batch  # noqa: E402
from structured_log import setup_logger, log_crawl_event  # noqa: E402

OUTPUT_DIR = os.path.join(PROJECT_DIR, 'output', 'collector_runs')
LOG_DIR = os.path.join(PROJECT_DIR, 'logs')

# 结构化日志
log = setup_logger("collector", log_dir=LOG_DIR)


def collect_one(src_id, label, func):
    """采集单个源 — 返回增量统计"""
    start = time.time()
    try:
        items, err = func()
        elapsed = time.time() - start
        duration_ms = int(elapsed * 1000)
        if items is not None and items:
            # 空热度 fallback: 用列表位置生成伪热度
            for i, item in enumerate(items):
                if not item.get('heat'):
                    item['heat'] = str(max(1, len(items) - i))

            # AI 自动分类 + 标签
            items = classify_batch(items, source=src_id)
            new, updated = upsert_news(items, src_id)
            log_crawl(src_id, 'ok', len(items), duration_ms=duration_ms,
                      interval_seconds=get_interval(src_id), label=label)
            log_crawl_event(src_id, 'ok', len(items), duration_ms, new=new, updated=updated)
            return {"label": label, "count": len(items), "new": new, "updated": updated, "status": "ok"}
        elif items == []:
            log_crawl(src_id, 'empty', 0, err or "源返回空列表", duration_ms=duration_ms,
                      interval_seconds=get_interval(src_id), label=label)
            log.warning(f"  {label} ⚠️ 空结果 ({elapsed:.1f}s)")
            return {"label": label, "count": 0, "status": "empty", "error": err or "empty result"}
        else:
            log_crawl(src_id, 'failed', 0, err, duration_ms=duration_ms,
                      interval_seconds=get_interval(src_id), label=label)
            log.warning(f"  {label} ❌ {err} ({elapsed:.1f}s)")
            return {"label": label, "count": 0, "status": "failed", "error": err}
    except Exception as e:
        elapsed = time.time() - start
        duration_ms = int(elapsed * 1000)
        log_crawl(src_id, 'error', 0, str(e), duration_ms=duration_ms,
                  interval_seconds=get_interval(src_id), label=label)
        log.error(f"  {label} 🔴 {e} ({elapsed:.1f}s)")
        return {"label": label, "count": 0, "status": "error", "error": str(e)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="多源新闻聚合采集器 v5.0")
    parser.add_argument("--core", action="store_true", help="只采集核心源")
    parser.add_argument("--source", help="逗号分隔的源 ID；优先于 --core")
    parser.add_argument("--parallel", type=lambda value: parse_parallel(value, default=6), default=6,
                        help="并行数 (默认6，范围1-32)")
    parser.add_argument("--prune", action="store_true", help="采集前清理过期数据")
    parser.add_argument("--vacuum", action="store_true", help="采集后 VACUUM 回收空间")
    parser.add_argument("--force", action="store_true", help="忽略 source_state 的 next_run_at")
    args = parser.parse_args()

    registry = all_sources()
    init_db()
    sync_source_catalog(
        (sid, label, get_interval(sid))
        for sid, (label, _func) in registry.items()
    )

    if args.source:
        requested = [s.strip() for s in args.source.split(",") if s.strip()]
        missing = [sid for sid in requested if sid not in registry]
        for sid in missing:
            log.warning(f"未知 source: {sid}")
        target_ids = [sid for sid in requested if sid in registry]
    else:
        target_ids = core_sources() if args.core else list(registry.keys())

    due_ids, skipped_sources = filter_due_sources(target_ids, force=args.force)
    targets = {sid: registry[sid] for sid in due_ids if sid in registry}

    # 可选的保留策略清理
    if args.prune:
        pruned = prune()
        if pruned["removed"] > 0:
            log.info(f"🧹 清理 {pruned['removed']} 条过期数据")

    log.info(f"{'='*50}")
    log.info(f"采集 v5.0 | 目标: {len(targets)}个源 | 跳过: {len(skipped_sources)} | 并行: {args.parallel}")
    for sid in target_ids[:5]:
        interval = get_interval(sid)
        if interval <= 120:
            log.info(f"  ⚡ {sid}: 每{interval}s")
        elif interval <= 600:
            log.info(f"  🔄 {sid}: 每{interval//60}min")
        else:
            log.info(f"  🐢 {sid}: 每{interval//60}min")
    if len(target_ids) > 5:
        log.info(f"  ... 还有{len(target_ids)-5}个源")
    log.info(f"{'='*50}")

    results = {
        sid: {
            "label": registry[sid][0],
            "count": 0,
            "status": "skipped",
            "next_run_at": next_run_at,
        }
        for sid, next_run_at in skipped_sources.items()
        if sid in registry
    }
    if targets:
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            fut_map = {pool.submit(collect_one, sid, label, func): sid
                       for sid, (label, func) in targets.items()}
            for fut in as_completed(fut_map):
                sid = fut_map[fut]
                results[sid] = fut.result()

    ok = sum(1 for r in results.values() if r['status'] == 'ok')
    failed = sum(1 for r in results.values() if r['status'] in ('failed', 'error'))
    empty = sum(1 for r in results.values() if r['status'] == 'empty')
    skipped = sum(1 for r in results.values() if r['status'] == 'skipped')
    total = sum(r.get('count', 0) for r in results.values())
    total_new = sum(r.get('new', 0) for r in results.values())
    total_updated = sum(r.get('updated', 0) for r in results.values())

    # 跨源去重
    deduped = cross_source_dedup(delay_minutes=1440, threshold=0.45) if targets else 0
    if deduped > 0:
        log.info(f"🧹 跨源去重: 标记了 {deduped} 条重复")

    # 保存JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report = {
        "version": "5.0",
        "timestamp": datetime.now(CST).isoformat(),
        "summary": {"ok": ok, "failed": failed, "total": total,
                    "new": total_new, "updated": total_updated,
                    "deduped": deduped, "skipped": skipped, "empty": empty},
        "sources": results,
    }
    ts = datetime.now(CST).strftime('%Y%m%d_%H%M')
    out = os.path.join(OUTPUT_DIR, f"news_v5.0_{ts}.json")
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 清理7天前的旧JSON
    cutoff = time.time() - 7 * 86400
    for fname in os.listdir(OUTPUT_DIR):
        if fname.endswith('.json') and fname.startswith('news_v'):
            fpath = os.path.join(OUTPUT_DIR, fname)
            if os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)

    if targets and not args.source:
        # latest.json
        latest = os.path.join(PROJECT_DIR, "output", "latest_news.json")
        os.makedirs(os.path.dirname(latest), exist_ok=True)
        with open(latest, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # 健康看板
        try:
            from health import health_report
            hp = health_report()
            with open(os.path.join(PROJECT_DIR, "output", "health_status.md"), 'w', encoding='utf-8') as f:
                f.write(hp + '\n')
        except Exception:
            pass
    else:
        if args.source:
            log.info("指定 source 模式，跳过全局 latest_news.json 更新")
        else:
            log.info("本次无实际采集源，跳过 latest_news.json 与 health_status.md 更新")

    # 可选 VACUUM
    if args.vacuum:
        try:
            vacuum()
            log.info("🧹 VACUUM 完成")
        except Exception as e:
            log.warning(f"VACUUM 失败: {e}")

    log.info(f"{'='*50}")
    log.info(f"采集完成: ✅{ok}个源  ❌{failed}失败  ⏭️{skipped}跳过  📦{total}条(+{total_new}新/+{total_updated}更新)  🧹去重{deduped}  {out}")
    log.info(f"{'='*50}")
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
