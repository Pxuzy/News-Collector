#!/usr/bin/env python
# coding=utf-8
"""
简报质量检查 v1.0 — 检测模板化/机械重复内容占比

用法:
    python scripts/check_briefing_quality.py output/news-2026-07-10.md

返回:
    - 模板化条目比例 (template_ratio)
    - 每类模板的细项统计
    - 劣质条目列表 (可导入 gen_today_v23_briefing.py 作为质量门禁)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


# ── 模板模式定义 ──────────────────────────────────────────────

# 模板化的事件描述 — desc_for() 退化为 fallback_event
PATTERN_FALLBACK_EVENT = re.compile(
    r'围绕["“](.+?)["”]的最新进展成为.+?热点'
)
PATTERN_FALLBACK_EVENT_V2 = re.compile(
    r'["“](.+?)["”]进入今日热点列表'
)

# 模板化的影响描述 — SECTION_WORDING 的固定文本
PATTERN_GENERIC_IMPACTS = [
    re.compile(r'它直接关系公共安全、生活成本或社会情绪'),
    re.compile(r'它会影响投资者风险偏好、产业链预期'),
    re.compile(r'它反映技术产品、平台生态或产业链变化'),
    re.compile(r'它会影响汽车产业链、能源价格'),
    re.compile(r'它主要影响社交平台讨论、粉丝传播'),
    re.compile(r'赛事结果会影响球队士气、球员声量'),
    re.compile(r'它会影响开发者工具链、企业采购'),
    re.compile(r'这类国际事件主要影响安全预期'),
    re.compile(r'这类事件会影响安全预期'),
    re.compile(r'这更偏 AI 公司人才与组织口碑'),
    re.compile(r'重点在算力供给、成本结构和产业链'),
    re.compile(r'它可能影响模型能力、开发者工具链'),
]

# 模板化的后续描述
PATTERN_GENERIC_FOLLOWUPS = [
    re.compile(r'看官方通报、救援或整改进展'),
    re.compile(r'看后续公告、市场成交变化'),
    re.compile(r'看产品细节、真实评测'),
    re.compile(r'看车企公告、交付数据'),
    re.compile(r'看当事方回应、平台二次传播'),
    re.compile(r'看赛后复盘、伤病情况'),
    re.compile(r'看官方发布、独立评测'),
    re.compile(r'看官方通报、当事国回应'),
    re.compile(r'看官方后续说明、相关国家'),
]

# 模板化的解读
PATTERN_GENERIC_INSIGHTS = [
    re.compile(r'民生热点要优先看事实核验'),
    re.compile(r'财经类热点容易被情绪放大'),
    re.compile(r'科技热点要看落地路径'),
    re.compile(r'汽车能源热点需要同时看需求'),
    re.compile(r'娱乐热点传播快、衰减也快'),
    re.compile(r'体育热点的核心不是比分本身'),
    re.compile(r'AI热点需要区分研究进展'),
    re.compile(r'国际新闻要优先核实事实链'),
    re.compile(r'这不是单条新闻热度'),
]

# 完全相同的可信度后缀
PATTERN_CREDIBILITY_FIXED = re.compile(
    r'✅ 可信度：来自采集库，需结合原始链接继续核验'
)


def gather_news_blocks(text: str) -> list[dict]:
    """将简报解析为新闻条目列表，识别每个 > 块属于哪条新闻。"""
    lines = text.split("\n")
    blocks: list[dict] = []
    current = None

    for i, line in enumerate(lines):
        # 检测新闻标题行（带颜色圆点或 📄/• 开头的条目）
        title_match = re.match(
            r'^([🔴🟠🟢🔵🟣📄]|•\s)', line
        )
        if title_match and "http" in line:
            if current:
                blocks.append(current)
            current = {
                "title_line": line,
                "line_num": i + 1,
                "quote_lines": [],
                "text": [],
            }

        if current and line.startswith(">"):
            current["quote_lines"].append(line.strip())
            current["text"].append(line)

    if current:
        blocks.append(current)

    return blocks


def check_block(block: dict) -> dict:
    """检查单个新闻条目中的模板化内容。"""
    result = {
        "fallback_event": False,
        "generic_impact": False,
        "generic_followup": False,
        "generic_insight": False,
        "fixed_credibility": False,
        "flags": [],
    }

    quote_text = "\n".join(block.get("quote_lines", []))

    # 1. 检查 fallback event
    if PATTERN_FALLBACK_EVENT.search(quote_text) or PATTERN_FALLBACK_EVENT_V2.search(quote_text):
        result["fallback_event"] = True
        result["flags"].append("event_fallback")

    # 2. 检查通用 impact
    for pat in PATTERN_GENERIC_IMPACTS:
        if pat.search(quote_text):
            result["generic_impact"] = True
            result["flags"].append("impact_generic")
            break

    # 3. 检查通用 followup
    for pat in PATTERN_GENERIC_FOLLOWUPS:
        if pat.search(quote_text):
            result["generic_followup"] = True
            result["flags"].append("followup_generic")
            break

    # 4. 检查通用 insight
    for pat in PATTERN_GENERIC_INSIGHTS:
        if pat.search(quote_text):
            result["generic_insight"] = True
            result["flags"].append("insight_generic")
            break

    # 5. 检查固定可信度
    if PATTERN_CREDIBILITY_FIXED.search(quote_text):
        result["fixed_credibility"] = True
        result["flags"].append("credibility_fixed")

    # 综合判定：任意 3 个以上模板标记 => "重度模板"
    result["template_level"] = (
        "heavy" if len(result["flags"]) >= 4
        else "medium" if len(result["flags"]) >= 2
        else "light" if result["flags"]
        else "clean"
    )

    return result


def check_file(filepath: str) -> dict:
    """对整份简报执行质量检查，返回结构化报告。"""
    text = Path(filepath).read_text(encoding="utf-8")
    blocks = gather_news_blocks(text)

    total = len(blocks)
    results = []
    fallback_count = 0
    generic_impact_count = 0
    generic_followup_count = 0
    generic_insight_count = 0
    heavy_count = 0
    medium_count = 0
    light_count = 0
    clean_count = 0

    for block in blocks:
        check = check_block(block)
        results.append({"title": block["title_line"][:60], **check})
        if check["fallback_event"]:
            fallback_count += 1
        if check["generic_impact"]:
            generic_impact_count += 1
        if check["generic_followup"]:
            generic_followup_count += 1
        if check["generic_insight"]:
            generic_insight_count += 1
        if check["template_level"] == "heavy":
            heavy_count += 1
        elif check["template_level"] == "medium":
            medium_count += 1
        elif check["template_level"] == "light":
            light_count += 1
        else:
            clean_count += 1

    # 计算占比
    def ratio(n):
        return round(n / total * 100, 1) if total else 0

    report = {
        "file": filepath,
        "total_news_items": total,
        "template_stats": {
            "fallback_event_ratio": ratio(fallback_count),
            "fallback_event_count": fallback_count,
            "generic_impact_ratio": ratio(generic_impact_count),
            "generic_followup_ratio": ratio(generic_followup_count),
            "generic_insight_ratio": ratio(generic_insight_count),
            "fixed_credibility_ratio": ratio(
                sum(1 for r in results if r["fixed_credibility"])
            ),
        },
        "template_levels": {
            "heavy_template_count": heavy_count,
            "heavy_template_ratio": ratio(heavy_count),
            "medium_template_count": medium_count,
            "medium_template_ratio": ratio(medium_count),
            "light_template_count": light_count,
            "clean_count": clean_count,
        },
        "flagged_items": [
            r["title"] for r in results if r["template_level"] == "heavy"
        ],
    }

    # 综合评分 (0-100, 越高越好)
    score = 100.0
    score -= report["template_stats"]["fallback_event_ratio"] * 0.8
    score -= report["template_stats"]["generic_impact_ratio"] * 0.6
    score -= report["template_stats"]["generic_followup_ratio"] * 0.4
    score -= report["template_stats"]["generic_insight_ratio"] * 0.4
    score = max(0, round(score, 1))
    report["quality_score"] = score

    return report


def print_report(report: dict) -> None:
    """友好打印质量报告。"""
    print(f"\n{'='*55}")
    print(f"  📊 简报质量检查报告")
    print(f"  {'='*55}")
    print(f"  文件: {report['file']}")
    print(f"  新闻条目总数: {report['total_news_items']}")
    print(f"  综合质量评分: {report['quality_score']}/100")
    print()

    # 评分等级
    if report["quality_score"] >= 80:
        grade = "✅ 良好"
    elif report["quality_score"] >= 60:
        grade = "⚠️ 一般"
    else:
        grade = "❌ 差 — 模板化严重"
    print(f"  等级: {grade}")
    print()

    print(f"  📈 模板统计:")
    ts = report["template_stats"]
    print(f"    · fallback_event (事件描述模板):    {ts['fallback_event_count']:>3}/{report['total_news_items']:>3} ({ts['fallback_event_ratio']}%)")
    print(f"    · generic_impact (影响描述模板):     {ts['generic_impact_ratio']}%")
    print(f"    · generic_followup (后续描述模板):   {ts['generic_followup_ratio']}%")
    print(f"    · generic_insight (解读模板):        {ts['generic_insight_ratio']}%")
    print(f"    · fixed_credibility (固定可信度):     {ts['fixed_credibility_ratio']}%")
    print()

    tl = report["template_levels"]
    print(f"  🏷️  条目质量分布:")
    print(f"    · 重度模板 (≥4项): {tl['heavy_template_count']} ({tl['heavy_template_ratio']}%)")
    print(f"    · 中度模板 (2-3项): {tl['medium_template_count']}")
    print(f"    · 轻度模板 (1项):   {tl['light_template_count']}")
    print(f"    · 无模板:            {tl['clean_count']}")
    print()

    if report["flagged_items"]:
        print(f"  🚩 重度模板条目 (建议优先改进):")
        for title in report["flagged_items"][:10]:
            print(f"    · {title[:55]}...")
        print()

    print(f"  {'='*55}")

    # 质量门禁判定
    if report["quality_score"] < 50:
        print("  ❌ 质量门禁: FAIL (评分<50，建议修复后再发布)")
    elif report["quality_score"] < 70:
        print("  ⚠️ 质量门禁: WARN (评分<70，建议检查模板条目)")
    else:
        print("  ✅ 质量门禁: PASS")
    print(f"  {'='*55}\n")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/check_briefing_quality.py <简报.md>")
        return 1

    filepath = sys.argv[1]
    if not Path(filepath).exists():
        print(f"文件不存在: {filepath}")
        return 1

    report = check_file(filepath)
    print_report(report)
    return 0 if report["quality_score"] >= 50 else 1


if __name__ == "__main__":
    raise SystemExit(main())
