import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from store import _canonical_key, _normalize_url  # noqa: E402


def test_normalize_url_removes_tracking_parameters():
    assert _normalize_url("https://Example.com/story/?utm_source=x&id=7#section") == "https://example.com/story?id=7"


def test_canonical_key_is_stable_for_tracking_variants():
    first = _canonical_key("title", "https://example.com/story?utm_source=a")
    second = _canonical_key("title", "https://example.com/story?utm_source=b")
    assert first == second
