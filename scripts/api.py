"""
news-toolkit HTTP API — FastAPI 服务
提供 RESTful 查询接口给外部消费

启动: PYTHONPATH=scripts python -m uvicorn api:app --host 0.0.0.0 --port 8899
"""
import os
import sys
from datetime import datetime
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
for path in (SCRIPT_DIR, PROJECT_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import JSONResponse
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from store import _db as get_db, fts_search, get_stats, query  # noqa: E402
from core import CST  # noqa: E402
from sources import all_sources, core_sources, disabled_sources  # noqa: E402
from classifier import classify  # noqa: E402

app = FastAPI(title="news-toolkit API", version="2.0",
              description="多源新闻聚合查询接口")

@app.get("/api/news")
def list_news(
    keyword: Optional[str] = Query(None, description="关键词"),
    category: Optional[str] = Query(None, description="分类"),
    source: Optional[str] = Query(None, description="信源"),
    days: int = Query(1, description="最近N天", ge=0, le=365),
    limit: int = Query(50, description="条数", ge=1, le=200),
    offset: int = Query(0, description="偏移", ge=0),
):
    """查询新闻列表 — 支持 keyword/category/source 筛选"""
    items, total = query(keyword=keyword, days=days, source=source,
                         category=category, limit=limit, offset=offset)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@app.get("/api/news/{news_id}")
def get_news(news_id: str, source: str = Query("", description="信源(必填)")):
    """获取单条新闻详情"""
    if not source:
        return JSONResponse({"error": "source is required"}, status_code=400)
    c = get_db()
    row = c.execute("SELECT * FROM news_items WHERE source=? AND id=?", (source, news_id)).fetchone()
    if not row:
        c.close()
        return JSONResponse({"error": "not found"}, status_code=404)
    # 查正文
    article = c.execute("SELECT * FROM articles WHERE source=? AND id=?", (source, news_id)).fetchone()
    c.close()
    result = dict(row)
    if article:
        result["article"] = dict(article)
    return result


@app.get("/api/search")
def search(q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
           limit: int = Query(20, ge=1, le=100)):
    """全文搜索 (FTS5)"""
    results = fts_search(q, limit)
    return {"query": q, "total": len(results), "items": results}


@app.get("/api/sources")
def list_sources():
    """列出所有已注册信源"""
    reg = all_sources()
    core = core_sources()
    return {
        "total": len(reg),
        "core": len(core),
        "core_sources": core,
        "all_sources": {k: v[0] for k, v in reg.items()},
        "disabled_sources": disabled_sources(),
    }


@app.get("/api/stats")
def stats(days: int = Query(7, description="统计天数", ge=0, le=365)):
    """采集统计"""
    return get_stats(days=days)


@app.get("/api/classify")
def classify_title(title: str = Query(..., min_length=1, max_length=500, description="新闻标题")):
    """AI分类测试"""
    cat = classify(title)
    return {"title": title, "category": cat}


@app.get("/health")
def health():
    """健康检查"""
    c = get_db()
    total = c.execute("SELECT COUNT(*) FROM news_items WHERE COALESCE(is_duplicate,0)=0").fetchone()[0]
    start_of_day = datetime.now(CST).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today = c.execute(
        "SELECT COUNT(*) FROM news_items WHERE first_seen>=? AND COALESCE(is_duplicate,0)=0",
        (start_of_day,)
    ).fetchone()[0]
    c.close()
    return {
        "status": "ok", "version": "2.0",
        "items_total": total, "items_today": today,
        "sources_total": len(all_sources()),
        "timestamp": datetime.now(CST).isoformat(),
    }


def main():
    """直接启动"""
    if not HAS_FASTAPI:
        print("❌ FastAPI 未安装: pip install fastapi uvicorn")
        return
    import uvicorn
    print("🚀 news-toolkit API v2.0")
    print("   http://localhost:8899/docs  (Swagger)")
    print("   http://localhost:8899/health")
    uvicorn.run(app, host="0.0.0.0", port=8899)


if __name__ == "__main__":
    main()
