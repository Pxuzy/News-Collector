import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from classifier import classify, classify_batch  # noqa: E402


def test_source_id_fallback_classifies_arxiv_as_ai():
    assert classify("A neutral paper title", source="arxiv") == "AI"


def test_classification_prefers_automotive_over_generic_finance_match():
    assert classify("特斯拉发布AI自动驾驶财报", source="") == "汽车·能源"


def test_classify_batch_uses_explicit_source_id():
    items = [{"title": "A neutral paper title", "extra": {"source": "📜arXiv"}}]
    assert classify_batch(items, source="arxiv")[0]["category"] == "AI"
