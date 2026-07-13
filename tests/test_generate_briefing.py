import os
from pathlib import Path

import gen_today_v23_briefing as briefing_generator
import generate_briefing as briefing


def test_md_link_percent_encodes_spaces_and_unicode_in_url():
    item = {"title": "微博条目", "url": "https://s.weibo.com/weibo?q=中餐厅 张雅琪"}

    assert briefing_generator.md_link(item) == (
        "[微博条目](https://s.weibo.com/weibo?q=%E4%B8%AD%E9%A4%90%E5%8E%85%20%E5%BC%A0%E9%9B%85%E7%90%AA)"
    )


def test_partial_collection_failure_does_not_block_valid_briefing(monkeypatch, tmp_path):
    root = tmp_path / "News-Collector"
    (root / "scripts").mkdir(parents=True)
    (root / "output").mkdir()
    (root / "scripts" / "gen_today_v23_briefing.py").write_text("# test generator\n")
    monkeypatch.setattr(briefing, "ROOT", str(root))
    monkeypatch.setattr(briefing.sys, "argv", ["generate_briefing.py"])

    calls = []

    def fake_run(cmd, timeout=120):
        calls.append(cmd)
        command = str(cmd[1]) if len(cmd) > 1 else ""
        if command.endswith("multi_source_news.py"):
            return False
        if command.endswith("gen_today_v23_briefing.py"):
            Path(os.environ["BRIEFING_OUTPUT_PATH"]).write_text("valid briefing\n")
        return True

    monkeypatch.setattr(briefing, "run", fake_run)

    assert briefing.main() == 0
    output_files = list((root / "output").glob("news-*.md"))
    assert len(output_files) == 1
    assert output_files[0].read_text() == "valid briefing\n"
    assert any(str(call[1]).endswith("multi_source_news.py") for call in calls)


def test_validation_failure_still_blocks_briefing(monkeypatch, tmp_path):
    root = tmp_path / "News-Collector"
    (root / "scripts").mkdir(parents=True)
    (root / "output").mkdir()
    (root / "scripts" / "gen_today_v23_briefing.py").write_text("# test generator\n")
    monkeypatch.setattr(briefing, "ROOT", str(root))
    monkeypatch.setattr(briefing.sys, "argv", ["generate_briefing.py", "--skip-collect"])

    def fake_run(cmd, timeout=120):
        command = str(cmd[1]) if len(cmd) > 1 else ""
        if command.endswith("gen_today_v23_briefing.py"):
            Path(os.environ["BRIEFING_OUTPUT_PATH"]).write_text("invalid briefing\n")
        return not command.endswith("validate_briefing.py")

    monkeypatch.setattr(briefing, "run", fake_run)

    assert briefing.main() == 1
    assert not list((root / "output").glob("news-*.md"))