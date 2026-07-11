import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import core  # noqa: E402


class _Response:
    def __init__(self, status_code, text="ok"):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status={self.status_code}")


def test_permanent_http_error_is_not_retried(monkeypatch):
    calls = []

    def get(*args, **kwargs):
        calls.append(1)
        return _Response(403, "forbidden")

    monkeypatch.setattr(core.req_lib, "get", get)
    monkeypatch.setattr(core.time, "sleep", lambda _: (_ for _ in ()).throw(AssertionError("slept")))
    result = core.fetch_via_requests("https://example.com")
    assert result.startswith("ERROR: HTTP 403")
    assert len(calls) == 1


def test_transient_http_error_retries_then_succeeds(monkeypatch):
    responses = iter([_Response(503, "busy"), _Response(200, "ok")])
    calls = []

    def get(*args, **kwargs):
        calls.append(1)
        return next(responses)

    monkeypatch.setattr(core.req_lib, "get", get)
    monkeypatch.setattr(core.time, "sleep", lambda _: None)
    assert core.fetch_via_requests("https://example.com") == "ok"
    assert len(calls) == 2


def test_rss_success_with_no_recent_items_is_empty(monkeypatch):
    empty_feed = """<?xml version="1.0"?><rss version="2.0"><channel>
        <title>Example</title>
    </channel></rss>"""
    monkeypatch.setattr(core, "fetch_via_requests", lambda *args, **kwargs: empty_feed)

    items, error = core.rss_to_items("https://example.com/feed.xml", "Example", "📰")

    assert items == []
    assert error is None


def test_rss_success_with_only_stale_items_is_empty(monkeypatch):
    stale_feed = """<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Old item</title><link>https://example.com/old</link>
        <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item>
    </channel></rss>"""
    monkeypatch.setattr(core, "fetch_via_requests", lambda *args, **kwargs: stale_feed)

    items, error = core.rss_to_items("https://example.com/feed.xml", "Example", "📰")

    assert items == []
    assert error is None


def test_tldr_rss_fallback_preserves_empty_status(monkeypatch):
    from sources import ai

    responses = iter([([], None), (None, "RSS获取失败")])
    monkeypatch.setattr(ai, "rss_to_items", lambda *args, **kwargs: next(responses))

    assert ai.source_tldr_ai() == ([], None)
