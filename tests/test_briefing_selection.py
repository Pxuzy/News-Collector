import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import gen_today_v23_briefing as briefing  # noqa: E402


def _item(key: str, category: str) -> dict:
    return {
        "title": key,
        "url": f"https://example.com/{key}",
        "source": "baidu",
        "category": category,
        "canonical_key": key,
    }


def test_main_items_use_category_fallback_when_keyword_hits_are_sparse(monkeypatch):
    monkeypatch.setattr(briefing, "query_hotlist_for_title", lambda *args: [])
    monkeypatch.setattr(
        briefing,
        "query_hotlist",
        lambda category, limit: [_item(f"{category}-{i}", category) for i in range(min(limit, 2))],
    )
    monkeypatch.setattr(briefing, "query_categories", lambda *args: [])

    result = briefing.select_main_items(5)

    assert len(result) == 5
    assert any(item["category"] == "综合" for item in result)


def test_social_domestic_section_keeps_broad_hotlist_categories(monkeypatch):
    def hotlist(category, limit):
        return [_item(f"{category}-1", category)]

    monkeypatch.setattr(briefing, "query_hotlist", hotlist)
    monkeypatch.setattr(briefing, "query_source", lambda *args: [])
    monkeypatch.setattr(briefing, "search_titles", lambda *args: [])

    sections = briefing.domestic_sections()
    social = next(items for _, key, items in sections if key == "社会·民生")

    assert {item["category"] for item in social} >= {"社会", "综合", "教育", "健康"}
