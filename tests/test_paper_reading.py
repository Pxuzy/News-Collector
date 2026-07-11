import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gen_today_v23_briefing import _paper_cn_reading, paper_dimensions  # noqa: E402


def test_paper_core_idea_is_chinese_and_explains_method_and_goal():
    summary = (
        "We propose a novel framework for proactive agents. "
        "The method improves planning efficiency and reduces inference cost."
    )
    result = _paper_cn_reading("A Benchmark for Proactive Agents", summary)
    assert "核心思路：" in result
    assert "提出" in result or "框架" in result
    assert "效率" in result or "成本" in result
    assert "We propose" not in result


def test_paper_core_idea_does_not_copy_english_sentence():
    summary = (
        "Structure-property relationships are foundational to biology, chemistry and materials. "
        "We introduce a model to improve prediction accuracy."
    )
    result = _paper_cn_reading("Structure Property Model", summary)
    assert "核心思路：" in result
    assert "Structure-property relationships" not in result
    assert "材料" in result or "化学" in result or "生物" in result


def test_paper_dimensions_cover_innovation_meaning_and_followup():
    result = paper_dimensions(
        "A benchmark for proactive agents",
        "We introduce a benchmark and dataset for agents planning real-world tasks.",
    )
    assert set(result) == {"innovation", "meaning", "impact"}
    assert all(result.values())
    assert "创新" in result["innovation"]
    assert "后续" in result["impact"]
