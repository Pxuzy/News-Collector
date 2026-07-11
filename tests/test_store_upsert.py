import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import store


def test_upsert_is_idempotent_for_same_source_id(monkeypatch, tmp_path):
    db_path = tmp_path / "news.db"
    monkeypatch.setattr(store, "DB", str(db_path))
    store.init_db()
    item = {"id": "1", "title": "测试新闻", "url": "https://example.com/1", "heat": "10"}
    assert store.upsert_news([item], "test") == (1, 0)
    assert store.upsert_news([item], "test") == (0, 1)
    conn = store._db()
    row = conn.execute("SELECT seen_count FROM news_items WHERE source='test' AND id='1'").fetchone()
    conn.close()
    assert row["seen_count"] == 2
