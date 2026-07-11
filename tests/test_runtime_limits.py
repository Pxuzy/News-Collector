import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core import parse_parallel  # noqa: E402


def test_parse_parallel_clamps_large_values():
    assert parse_parallel("999") == 32


def test_parse_parallel_rejects_non_positive_values():
    assert parse_parallel("0") == 1
    assert parse_parallel("-4") == 1


def test_parse_parallel_uses_default_for_invalid_values():
    assert parse_parallel("not-a-number") == 8
