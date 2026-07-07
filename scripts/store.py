#!/usr/bin/env python
"""
持久化存储层 v5.0 — SQLite + FTS5 + 保留策略 + 分类
"""
import json
import os
import sqlite3
import re
import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CST = timezone(timedelta(hours=8))
DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news.db")
RETENTION_DAYS = 30  # 新闻保留天数
MAX_ARTICLES = 500   # 最大正文数


def _db():
    if DB != ':memory:':
        os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    if DB != ':memory:':
        c.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON")
    return c


def _now() -> str:
    return datetime.now(CST).isoformat()


def _column_names(c, table: str) -> set[str]:
    return {row["name"] for row in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_column(c, table: str, name: str, ddl: str):
    if name not in _column_names(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db():
    c = _db()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS news_items (
            id TEXT, source TEXT, title TEXT, url TEXT,
            heat TEXT DEFAULT '', heat_score INTEGER DEFAULT 0,
            category TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            extra TEXT DEFAULT '{}',
            first_seen TEXT, last_seen TEXT, seen_count INTEGER DEFAULT 1,
            summary TEXT DEFAULT '',
            published_at TEXT DEFAULT '',
            canonical_key TEXT DEFAULT '',
            is_duplicate INTEGER DEFAULT 0,
            duplicate_of TEXT DEFAULT '',
            PRIMARY KEY (source, id)
        );
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT, source TEXT, title TEXT, url TEXT UNIQUE,
            content TEXT DEFAULT '', summary TEXT DEFAULT '', fetched_at TEXT,
            PRIMARY KEY (source, id)
        );
        CREATE TABLE IF NOT EXISTS crawl_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT, source TEXT, status TEXT,
            count INTEGER DEFAULT 0, duration_ms INTEGER DEFAULT 0, error TEXT
        );

        -- 增量追踪: 每条新闻的内容指纹, 用于检测重复/变更
        CREATE TABLE IF NOT EXISTS fingerprints (
            hash TEXT PRIMARY KEY, source TEXT, news_id TEXT,
            title TEXT, first_seen TEXT, last_updated TEXT
        );
        CREATE TABLE IF NOT EXISTS source_state (
            source TEXT PRIMARY KEY,
            label TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            interval_seconds INTEGER DEFAULT 300,
            status TEXT DEFAULT 'new',
            last_success_at TEXT,
            last_error_at TEXT,
            next_run_at TEXT,
            fail_streak INTEGER DEFAULT 0,
            ok_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            avg_duration_ms INTEGER DEFAULT 0,
            last_error TEXT DEFAULT ''
        );

        -- 索引
        DROP INDEX IF EXISTS idx_news_last_seen;
        DROP INDEX IF EXISTS idx_news_source;
        DROP INDEX IF EXISTS idx_ns;
        DROP INDEX IF EXISTS idx_sr;
        DROP INDEX IF EXISTS idx_cat;
        DROP INDEX IF EXISTS idx_heat;
        CREATE INDEX IF NOT EXISTS idx_source_state_next ON source_state(enabled, next_run_at);
    """)

    for name, ddl in {
        "heat_score": "INTEGER DEFAULT 0",
        "published_at": "TEXT DEFAULT ''",
        "canonical_key": "TEXT DEFAULT ''",
        "is_duplicate": "INTEGER DEFAULT 0",
        "duplicate_of": "TEXT DEFAULT ''",
    }.items():
        _ensure_column(c, "news_items", name, ddl)

    c.executescript("""
        CREATE INDEX IF NOT EXISTS idx_news_seen ON news_items(last_seen);
        CREATE INDEX IF NOT EXISTS idx_news_source_seen ON news_items(source, last_seen);
        CREATE INDEX IF NOT EXISTS idx_news_category_seen ON news_items(category, last_seen);
        CREATE INDEX IF NOT EXISTS idx_news_heat_score ON news_items(heat_score DESC, last_seen DESC);
        CREATE INDEX IF NOT EXISTS idx_news_canonical ON news_items(canonical_key);
        CREATE INDEX IF NOT EXISTS idx_news_duplicate ON news_items(is_duplicate, duplicate_of);
    """)

    fts_available = True
    try:
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS news_fts USING fts5(
                title, source,
                content='news_items',
                content_rowid='rowid',
                tokenize='unicode61'
            )
        """)
    except sqlite3.OperationalError:
        fts_available = False

    if fts_available:
        c.executescript("""
            DROP TRIGGER IF EXISTS news_ai;
            DROP TRIGGER IF EXISTS news_ad;
            DROP TRIGGER IF EXISTS news_au;
            CREATE TRIGGER news_ai AFTER INSERT ON news_items BEGIN
                INSERT INTO news_fts(rowid, title, source)
                VALUES (new.rowid, new.title, new.source);
            END;
            CREATE TRIGGER news_ad AFTER DELETE ON news_items BEGIN
                INSERT INTO news_fts(news_fts, rowid, title, source)
                VALUES ('delete', old.rowid, old.title, old.source);
            END;
            CREATE TRIGGER news_au AFTER UPDATE ON news_items BEGIN
                INSERT INTO news_fts(news_fts, rowid, title, source)
                VALUES ('delete', old.rowid, old.title, old.source);
                INSERT INTO news_fts(rowid, title, source)
                VALUES (new.rowid, new.title, new.source);
            END;
        """)
        try:
            fts_count = c.execute("SELECT COUNT(*) FROM news_fts").fetchone()[0]
            item_count = c.execute("SELECT COUNT(*) FROM news_items").fetchone()[0]
            if fts_count != item_count:
                c.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")
        except sqlite3.OperationalError:
            pass

    rows = c.execute("""
        SELECT rowid, title, url, heat, heat_score, canonical_key
        FROM news_items
        WHERE heat_score IS NULL OR heat_score=0 OR canonical_key='' OR canonical_key IS NULL
    """).fetchall()
    for row in rows:
        c.execute(
            "UPDATE news_items SET heat_score=?, canonical_key=? WHERE rowid=?",
            (heat_to_score(row["heat"]), _canonical_key(row["title"], row["url"]), row["rowid"])
        )
    c.commit()
    c.close()


def _fingerprint(title, url):
    """生成内容指纹用于增量追踪"""
    raw = (title or '') + (url or '')
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(str(url).strip())
        query = [
            (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in {"spm", "from", "share"}
        ]
        return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))
    except Exception:
        return str(url).strip()


def _canonical_key(title: str, url: str) -> str:
    basis = _normalize_url(url) or re.sub(r"\s+", "", (title or "").lower())
    return hashlib.sha1(basis.encode("utf-8")).hexdigest() if basis else ""


def _published_at(item: dict) -> str:
    value = item.get("published_at") or item.get("published") or item.get("pubDate") or ""
    if isinstance(value, (int, float)):
        # Some video APIs return milliseconds.
        if value > 10_000_000_000:
            value = value / 1000
        try:
            return datetime.fromtimestamp(value, CST).isoformat()
        except Exception:
            return ""
    return str(value or "")


def upsert_news(items, source):
    """插入/更新新闻, 返回 (新条数, 更新条数)  — try/finally 保底关闭连接"""
    now = _now()
    new = 0
    updated = 0
    c = _db()
    try:
        for item in items:
            iid, title, url = str(item.get('id','')), str(item.get('title','')), str(item.get('url','') or '')
            if not iid or not title:
                iid = url or title
                if not iid: continue
            raw_heat = str(item.get('heat') or item.get('extra',{}).get('info','') or '')
            heat = normalize_heat(raw_heat)
            heat_score = heat_to_score(raw_heat or heat)
            category = item.get('category', '')
            tags = json.dumps(item.get('tags', []), ensure_ascii=False)
            extra = json.dumps(item.get('extra',{}), ensure_ascii=False)
            fp = _fingerprint(title, url)
            canonical_key = _canonical_key(title, url)
            published_at = _published_at(item)

            # 已存在? 用指纹判断是否真的更新了
            existing = c.execute("SELECT seen_count,title,heat FROM news_items WHERE source=? AND id=?",
                                (source, iid)).fetchone()
            if existing:
                c.execute("""UPDATE news_items SET last_seen=?, seen_count=seen_count+1,
                             heat=CASE WHEN ?!='' THEN ? ELSE heat END,
                             heat_score=CASE WHEN ?>0 THEN ? ELSE heat_score END,
                             title=CASE WHEN ?!='' THEN ? ELSE title END,
                             url=CASE WHEN ?!='' THEN ? ELSE url END,
                             category=CASE WHEN ?!='' THEN ? ELSE category END,
                             tags=?, extra=?, published_at=CASE WHEN ?!='' THEN ? ELSE published_at END,
                             canonical_key=?, is_duplicate=0, duplicate_of=''
                             WHERE source=? AND id=?""",
                          (now, heat, heat, heat_score, heat_score, title, title,
                           url, url, category, category, tags, extra,
                           published_at, published_at, canonical_key, source, iid))
                updated += 1
            else:
                c.execute("""INSERT INTO news_items(id,source,title,url,heat,heat_score,category,tags,extra,
                             first_seen,last_seen,seen_count,published_at,canonical_key,is_duplicate,duplicate_of)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,?,0,'')""",
                          (iid, source, title, url, heat, heat_score, category, tags,
                           extra, now, now, published_at, canonical_key))
                new += 1

            # 更新指纹
            c.execute("""INSERT INTO fingerprints(hash,source,news_id,title,first_seen,last_updated)
                         VALUES(?,?,?,?,?,?) ON CONFLICT(hash) DO UPDATE SET
                         last_updated=excluded.last_updated, title=excluded.title""",
                      (fp, source, iid, title[:100], now, now))

        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
    return new, updated


def sync_source_catalog(sources):
    """Upsert enabled source metadata into source_state."""
    c = _db()
    try:
        for source, label, interval_seconds in sources:
            c.execute("""
                INSERT INTO source_state(source,label,enabled,interval_seconds)
                VALUES(?,?,1,?)
                ON CONFLICT(source) DO UPDATE SET
                    label=excluded.label,
                    enabled=1,
                    interval_seconds=excluded.interval_seconds
            """, (source, label, int(interval_seconds or 300)))
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def filter_due_sources(source_ids, force=False):
    """Return (due_ids, skipped_map) where skipped_map is {source: next_run_at}."""
    if force:
        return list(source_ids), {}
    c = _db()
    try:
        now = _now()
        due, skipped = [], {}
        for source in source_ids:
            row = c.execute(
                "SELECT enabled,next_run_at FROM source_state WHERE source=?",
                (source,)
            ).fetchone()
            if row and row["enabled"] == 0:
                skipped[source] = "disabled"
            elif not row or not row["next_run_at"] or row["next_run_at"] <= now:
                due.append(source)
            else:
                skipped[source] = row["next_run_at"]
        return due, skipped
    finally:
        c.close()


def record_source_result(source, status, count=0, duration_ms=0, error=None,
                         interval_seconds=None, label=None):
    c = _db()
    try:
        now = _now()
        interval = int(interval_seconds or 300)
        row = c.execute("SELECT * FROM source_state WHERE source=?", (source,)).fetchone()
        fail_streak = int(row["fail_streak"] or 0) if row else 0
        ok_count = int(row["ok_count"] or 0) if row else 0
        fail_count = int(row["fail_count"] or 0) if row else 0
        avg_duration = int(row["avg_duration_ms"] or 0) if row else 0

        if status == "ok":
            fail_streak = 0
            ok_count += 1
            avg_duration = duration_ms if avg_duration == 0 else int(avg_duration * 0.8 + duration_ms * 0.2)
            next_run_at = (datetime.now(CST) + timedelta(seconds=interval)).isoformat()
            last_success_at, last_error_at, last_error = now, (row["last_error_at"] if row else None), ""
        else:
            fail_streak += 1
            fail_count += 1
            backoff = min(max(interval, 60) * (2 ** min(fail_streak - 1, 4)), 3600)
            next_run_at = (datetime.now(CST) + timedelta(seconds=backoff)).isoformat()
            last_success_at = row["last_success_at"] if row else None
            last_error_at, last_error = now, str(error or "")[:500]

        c.execute("""
            INSERT INTO source_state(
                source,label,enabled,interval_seconds,status,last_success_at,last_error_at,
                next_run_at,fail_streak,ok_count,fail_count,avg_duration_ms,last_error
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source) DO UPDATE SET
                label=excluded.label,
                interval_seconds=excluded.interval_seconds,
                status=excluded.status,
                last_success_at=excluded.last_success_at,
                last_error_at=excluded.last_error_at,
                next_run_at=excluded.next_run_at,
                fail_streak=excluded.fail_streak,
                ok_count=excluded.ok_count,
                fail_count=excluded.fail_count,
                avg_duration_ms=excluded.avg_duration_ms,
                last_error=excluded.last_error
        """, (
            source, label or source, 1, interval, status, last_success_at, last_error_at,
            next_run_at, fail_streak, ok_count, fail_count, avg_duration, last_error
        ))
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def log_crawl(source, status, count, error=None, duration_ms=0,
              interval_seconds=None, label=None):
    c = _db()
    try:
        c.execute("INSERT INTO crawl_log(started_at,source,status,count,duration_ms,error) VALUES(?,?,?,?,?,?)",
                  (_now(), source, status, count, duration_ms, error))
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
    record_source_result(source, status, count, duration_ms, error, interval_seconds, label)


def build_query_params(keyword=None, days=None, source=None, category=None, include_duplicates=False):
    """构建统一的 query WHERE 条件和参数列表 (共享给 store.query 和 api.py)"""
    params = []
    where = []
    if not include_duplicates:
        where.append("COALESCE(is_duplicate,0)=0")
    if keyword:
        where.append("title LIKE ?")
        params.append(f"%{keyword}%")
    if days is not None:
        where.append("last_seen >= ?")
        params.append((datetime.now(CST) - timedelta(days=days)).isoformat())
    if source:
        where.append("source = ?")
        params.append(source)
    if category:
        where.append("category = ?")
        params.append(category)
    w = " AND ".join(where) if where else "1=1"
    return w, params


def query(keyword=None, days=None, source=None, category=None, limit=50, offset=0):
    """增强查询 — 支持 category 过滤, 支持热度排序"""
    c = _db()
    w, params = build_query_params(keyword, days, source, category)
    rows = c.execute(f"SELECT * FROM news_items WHERE {w} ORDER BY heat_score DESC, last_seen DESC LIMIT ? OFFSET ?",
                     params+[limit, offset]).fetchall()
    total = c.execute(f"SELECT COUNT(*) FROM news_items WHERE {w}", params).fetchone()[0]
    c.close()
    return [dict(r) for r in rows], total


def batch_query(sources: list[str], days: int = 1, limit: int = 15) -> dict[str, list[dict]]:
    """批量多源查询 — 返回 {source: [items]}"""
    c = _db()
    try:
        cutoff = (datetime.now(CST) - timedelta(days=days)).isoformat()
        result = {}
        for src in sources:
            rows = c.execute(
                "SELECT * FROM news_items WHERE source=? AND last_seen>=? AND COALESCE(is_duplicate,0)=0 ORDER BY heat_score DESC, last_seen DESC LIMIT ?",
                (src, cutoff, limit)
            ).fetchall()
            result[src] = [dict(r) for r in rows]
        return result
    finally:
        c.close()


def query_by_categories(categories: list[str], days: int = 1, limit: int = 15) -> dict[str, list[dict]]:
    """按分类列表批量查询 — 返回 {category: [items]}"""
    c = _db()
    try:
        cutoff = (datetime.now(CST) - timedelta(days=days)).isoformat()
        result = {}
        for cat in categories:
            rows = c.execute(
                "SELECT * FROM news_items WHERE category=? AND last_seen>=? AND COALESCE(is_duplicate,0)=0 ORDER BY heat_score DESC, last_seen DESC LIMIT ?",
                (cat, cutoff, limit)
            ).fetchall()
            result[cat] = [dict(r) for r in rows]
        return result
    finally:
        c.close()


def normalize_heat(heat_str: str) -> str:
    """统一热力值格式:
    - 纯数字 → 带万单位 (如 12127398 → 1213万)
    - 已有单位 → 保留原样
    - 空/长文本 → 返回空
    """
    if not heat_str:
        return ""
    s = str(heat_str).strip()
    if len(s) > 50:
        return ""  # 百度这种长文本摘要, 不是热度值
    # 纯数字 → 转万
    if s.isdigit():
        n = int(s)
        if n >= 10000:
            return f"{round(n/10000)}万"
        return str(n)
    # 已有单位
    if any(u in s for u in ["万", "亿", "k", "K", "万热度", "points", "点"]):
        return s
    # 可能是数字字符串
    try:
        n = int(float(s))
        if n >= 10000:
            return f"{round(n/10000)}万"
        return str(n)
    except ValueError:
        return s[:30]  # 截断防止长文本


def heat_to_score(heat_str: str) -> int:
    """Convert mixed heat labels into a sortable integer score."""
    if not heat_str:
        return 0
    s = str(heat_str).strip().replace(",", "")
    if not s or len(s) > 80:
        return 0

    # Prefer the first numeric token and a nearby unit.
    m = re.search(r"([-+]?\d+(?:\.\d+)?)\s*([亿萬万wWkK%]?)", s)
    if not m:
        return 0
    try:
        value = float(m.group(1))
    except ValueError:
        return 0

    unit = m.group(2)
    if unit in ("亿",):
        value *= 100_000_000
    elif unit in ("万", "萬", "w", "W"):
        value *= 10_000
    elif unit in ("k", "K"):
        value *= 1_000
    elif unit == "%":
        value *= 100
    return max(0, int(value))


def fts_search(query, limit=20):
    """FTS5全文搜索"""
    c = _db()
    try:
        rows = c.execute("""SELECT n.* FROM news_fts f
                            JOIN news_items n ON n.rowid = f.rowid
                            WHERE news_fts MATCH ? AND COALESCE(n.is_duplicate,0)=0
                            ORDER BY rank LIMIT ?""",
                        (query, limit)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        # fallback: LIKE 搜索
        c2 = _db()
        try:
            rows = c2.execute(
                "SELECT * FROM news_items WHERE title LIKE ? AND COALESCE(is_duplicate,0)=0 ORDER BY last_seen DESC LIMIT ?",
                (f"%{query}%", limit)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            c2.close()
    finally:
        c.close()


def get_stats(days=7):
    """增强统计 — 含分类分布和增量统计"""
    c = _db()
    cutoff = (datetime.now(CST)-timedelta(days=days)).isoformat()
    by_source = [dict(r) for r in c.execute(
        "SELECT source,COUNT(*) as count,MAX(last_seen) as last FROM news_items WHERE last_seen>=? AND COALESCE(is_duplicate,0)=0 GROUP BY source ORDER BY count DESC",
        (cutoff,)).fetchall()]
    by_category = [dict(r) for r in c.execute(
        "SELECT category,COUNT(*) as count FROM news_items WHERE last_seen>=? AND category!='' AND COALESCE(is_duplicate,0)=0 GROUP BY category ORDER BY count DESC",
        (cutoff,)).fetchall()]
    crawl_stats = [dict(r) for r in c.execute(
        "SELECT source,SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) as ok_count,SUM(CASE WHEN status!='ok' THEN 1 ELSE 0 END) as fail_count FROM crawl_log WHERE started_at>=? GROUP BY source",
        (cutoff,)).fetchall()]
    total = c.execute("SELECT COUNT(*) FROM news_items WHERE last_seen>=? AND COALESCE(is_duplicate,0)=0", (cutoff,)).fetchone()[0]
    new_today = c.execute("SELECT COUNT(*) FROM news_items WHERE first_seen>=? AND COALESCE(is_duplicate,0)=0", (cutoff,)).fetchone()[0]
    c.close()
    return {"total": total, "new": new_today, "days": days,
            "by_source": by_source, "by_category": by_category, "crawl_stats": crawl_stats}


def prune(days=RETENTION_DAYS):
    """数据保留策略 — 清理过期数据"""
    c = _db()
    try:
        cutoff = (datetime.now(CST)-timedelta(days=days)).isoformat()
        # 只清理 seen_count=1 或重复标记的过期老数据
        removed = c.execute(
            "DELETE FROM news_items WHERE last_seen<? AND (seen_count=1 OR COALESCE(is_duplicate,0)=1)",
            (cutoff,)
        ).rowcount
        kept_old = c.execute("SELECT COUNT(*) FROM news_items WHERE last_seen<?", (cutoff,)).fetchone()[0]
        # 限制正文表大小
        c.execute("DELETE FROM articles WHERE rowid NOT IN (SELECT rowid FROM articles ORDER BY fetched_at DESC LIMIT ?)",
                  (MAX_ARTICLES,))
        # 清理旧日志
        c.execute("DELETE FROM crawl_log WHERE started_at<?", (cutoff,))
        # 清理旧指纹
        c.execute("DELETE FROM fingerprints WHERE last_updated<?", (cutoff,))
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
    return {"removed": removed, "kept_old": kept_old}


def cross_source_dedup(delay_minutes=5, threshold=0.45) -> int:
    """
    跨源去重: 对最近 delay_minutes 内采集的新闻,
    跨源标题相似的只把非最佳项标记为重复, 不删除原始记录.
    返回标记数.
    """
    from dedup import _ng, _norm
    c = _db()
    try:
        cutoff = (datetime.now(CST) - timedelta(minutes=delay_minutes)).isoformat()
        raw_rows = c.execute(
            """SELECT rowid, source, id, title, heat, heat_score, url
               FROM news_items
               WHERE last_seen>=? AND COALESCE(is_duplicate,0)=0""",
            (cutoff,)
        ).fetchall()
        rows = [dict(r) for r in raw_rows]
        if len(rows) < 2:
            return 0

        used = set()
        marked = 0
        norms = [(_norm(r.get("title", "")), r) for r in rows]
        for i, (base_norm, base_row) in enumerate(norms):
            if i in used or not base_norm:
                continue
            base_ng = _ng(base_norm)
            cluster = [i]
            for j, (next_norm, next_row) in enumerate(norms[i + 1:], i + 1):
                if j in used or not next_norm or next_row["source"] == base_row["source"]:
                    continue
                next_ng = _ng(next_norm)
                if base_ng and next_ng and len(base_ng & next_ng) / len(base_ng | next_ng) > threshold:
                    cluster.append(j)

            if len(cluster) < 2:
                continue
            for idx in cluster:
                used.add(idx)

            best_idx = max(cluster, key=lambda k: (
                int(rows[k].get("heat_score") or heat_to_score(rows[k].get("heat", ""))),
                0 if "baidu.com/s?wd" in (rows[k].get("url") or "") else 1,
                rows[k].get("last_seen", ""),
            ))
            best = rows[best_idx]
            duplicate_of = f"{best['source']}|{best['id']}"
            for idx in cluster:
                if idx == best_idx:
                    c.execute("UPDATE news_items SET is_duplicate=0, duplicate_of='' WHERE rowid=?",
                              (rows[idx]["rowid"],))
                    continue
                c.execute("UPDATE news_items SET is_duplicate=1, duplicate_of=? WHERE rowid=?",
                          (duplicate_of, rows[idx]["rowid"]))
                marked += 1
        c.commit()
        return marked
    except Exception:
        c.rollback()
        return 0
    finally:
        c.close()


def vacuum():
    """回收 DB 空间 — VACUUM"""
    c = _db()
    try:
        c.executescript("VACUUM;")
    finally:
        c.close()


def update_summary(source, news_id, summary):
    """更新摘要缓存"""
    c = _db()
    try:
        c.execute("UPDATE news_items SET summary=? WHERE source=? AND id=?", (summary[:500], source, news_id))
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
