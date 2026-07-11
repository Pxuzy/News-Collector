"""Tests for _migrate_articles_url_constraint: transaction safety and idempotency."""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import store  # noqa: E402


def _make_legacy_db() -> sqlite3.Connection:
    """Build an in-memory DB whose articles table has the legacy UNIQUE(url) constraint."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE articles (
            id TEXT, source TEXT, title TEXT, url TEXT,
            content TEXT DEFAULT '', summary TEXT DEFAULT '', fetched_at TEXT,
            UNIQUE(url),
            PRIMARY KEY (source, id)
        );
        INSERT INTO articles VALUES ('a1','src','T1','http://x/1','body','','2025-01-01');
        INSERT INTO articles VALUES ('a2','src','T2','http://x/2','body2','','2025-01-02');
    """)
    return c


def test_migration_removes_unique_constraint_and_preserves_rows():
    c = _make_legacy_db()
    store._migrate_articles_url_constraint(c)
    schema = c.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='articles'"
    ).fetchone()
    assert schema and "UNIQUE" not in schema[0].upper()
    rows = c.execute("SELECT * FROM articles ORDER BY id").fetchall()
    assert len(rows) == 2
    assert rows[0]["url"] == "http://x/1"
    assert rows[1]["url"] == "http://x/2"


def test_migration_is_idempotent():
    c = _make_legacy_db()
    store._migrate_articles_url_constraint(c)   # first run
    store._migrate_articles_url_constraint(c)   # second run: no-op
    rows = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    assert rows == 2


def test_migration_is_idempotent_with_orphan_table():
    """A leftover articles_new from a previous crash should be cleaned and migration still works."""
    c = _make_legacy_db()
    c.execute("""CREATE TABLE articles_new (
        id TEXT, source TEXT, title TEXT, url TEXT,
        content TEXT DEFAULT '', summary TEXT DEFAULT '', fetched_at TEXT,
        PRIMARY KEY (source, id)
    )""")
    store._migrate_articles_url_constraint(c)
    schema = c.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='articles'"
    ).fetchone()
    assert schema and "UNIQUE" not in schema[0].upper()
    rows = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    assert rows == 2
    assert not c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles_new'"
    ).fetchone()


def test_migration_skips_when_no_unique_constraint():
    """Modern schema without UNIQUE(url) should be untouched."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE articles (
            id TEXT, source TEXT, title TEXT, url TEXT,
            content TEXT DEFAULT '', summary TEXT DEFAULT '', fetched_at TEXT,
            PRIMARY KEY (source, id)
        );
        INSERT INTO articles VALUES ('a1','src','T1','http://x/1','body','','2025-01-01');
    """)
    store._migrate_articles_url_constraint(c)
    rows = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    assert rows == 1


def test_migration_rolls_back_when_schema_swap_fails():
    """A failed ALTER must preserve the legacy table and remove the temp table."""
    c = _make_legacy_db()

    def deny_alter(action, *args):
        return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_ALTER_TABLE else sqlite3.SQLITE_OK

    c.set_authorizer(deny_alter)
    try:
        try:
            store._migrate_articles_url_constraint(c)
        except sqlite3.DatabaseError:
            pass
    finally:
        c.set_authorizer(None)

    schema = c.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='articles'"
    ).fetchone()
    assert schema and "UNIQUE" in schema[0].upper()
    assert c.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 2
    assert not c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='articles_new'"
    ).fetchone()
