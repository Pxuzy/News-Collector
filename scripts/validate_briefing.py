#!/usr/bin/env python3
"""校验 Telegram 新闻简报是否适合推送。"""
from __future__ import annotations

import re
import sys
from pathlib import Path


LINK_RE = re.compile(r"\[[^\]\n]+\]\((https?://[^)\s]+|链接未获取)\)")
REPEATED_URL_RE = re.compile(r"\]\((https?://[^)\s]+)\)\s*\(\1\)")
ANY_REPEATED_URL_RE = re.compile(r"\]\((https?://[^)\s]+)\)\s*\(https?://[^)\s]+\)")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
ITEM_LINE_RE = re.compile(r"^\s*(?:-|•)\s*(#\d+|(?:抖音|微博|知乎|百度|GitHub|HN)#\d+|📜|🔴|🟡|🟢)")
NON_NEWS_LINE_RE = re.compile(r"^\s*(?:-|•)\s*(?:🔴\s*风险|🟢\s*机会)：")
MARKDOWN_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
OLD_HOTLIST_RE = re.compile(r"^\s*-\s+#\d+\s+\[")
PART_TITLE_RE = re.compile(r"今日热点\s*·\s*全源聚合\s*\(\d+/\d+\)")
BARE_CONFIDENCE_RE = re.compile(r"^\s*✅\s*(高|中|低)\s*$")
FIELD_EMOJI_RE = re.compile(r"^\s*(📌|🌊|👀|💡|✅)\s")
GENERIC_BAD_INSIGHTS = (
    "它解决的核心问题需要结合 README 和 issue 进一步核实",
    "这条在 HackerNews 获得高讨论度，适合看工程实践、社区争议和真实使用经验",
    "试图解决相关 AI 或工程研究问题",
    "关注 Agent/模型能力边界的人",
    "热榜反映平台用户即时关注",
    "适合观察传播情绪、争议点和后续回应",
    "抖音的传播点通常在画面感和情绪触发",
    "短视频语境会优先放大现场片段",
    "这条在抖音上升温",
    "微博更容易形成实时围观和话题接力",
    "微博场景下要把热度和事实进展分开看",
    "这类微博热搜常由媒体报道",
    "知乎的价值在于把问题拆开讨论",
    "知乎热榜更适合看长回答如何补充背景",
    "这条在知乎发酵",
    "百度热搜更多体现主动搜索需求",
    "百度侧的高位排名说明大量用户正在找入口和解释",
    "搜索热度上升时",
)


def has_link(line: str) -> bool:
    return bool(LINK_RE.search(line))


def validate(text: str) -> list[str]:
    errors: list[str] = []
    lines = text.splitlines()

    # 检查文件是否包含 \r（Windows 换行符，Telegram 渲染异常）
    if "\r" in text:
        errors.append("文件包含 \\r（Windows 换行符），Telegram 渲染会异常。必须只用 \\n（LF）换行。")

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            errors.append(f"第 {idx} 行：不能出现代码围栏")
        if stripped == "---":
            errors.append(f"第 {idx} 行：不要使用 --- 分隔线")
        if MARKDOWN_HEADING_RE.match(line):
            errors.append(f"第 {idx} 行：Telegram 输出不要依赖 #/##/### 标题")
        if OLD_HOTLIST_RE.match(line):
            errors.append(f"第 {idx} 行：热榜不要使用旧样式 '- #排名'，请使用 '• 平台#排名'")
        if REPEATED_URL_RE.search(line):
            errors.append(f"第 {idx} 行：Markdown 链接后重复了裸 URL")
        if ANY_REPEATED_URL_RE.search(line):
            errors.append(f"第 {idx} 行：Markdown 链接后不要再附加裸 URL")
        if PART_TITLE_RE.search(line):
            errors.append(f"第 {idx} 行：不要输出今日热点分段标题 (2/3)，分段直接从栏目标题开始")
        if BARE_CONFIDENCE_RE.match(line):
            errors.append(f"第 {idx} 行：可信度不能只写 ✅ 高/中/低，请写 ✅ 可信度：高/中/低")
        if TABLE_SEPARATOR_RE.match(line):
            errors.append(f"第 {idx} 行：不能使用 Markdown 表格分隔行")
        if stripped.startswith("|") and stripped.endswith("|"):
            errors.append(f"第 {idx} 行：不能使用 Markdown 表格行")
        for phrase in GENERIC_BAD_INSIGHTS:
            if phrase in line:
                errors.append(f"第 {idx} 行：解读过于模板化，请改成针对当前条目的具体分析")
        # 检查字段符号是否单独成行（应该是 📌 事件：xxx 在同一行）
        if stripped in ("📌", "🌊", "👀", "💡", "✅"):
            errors.append(f"第 {idx} 行：字段符号「{stripped}」单独成行。字段符号和文字应在同一行（如 '  📌 事件：xxx'）")
        # 检查字段之间是否有空行分隔（连续两个字段行之间不能没有空行）
        if idx > 1 and FIELD_EMOJI_RE.match(line):
            prev = lines[idx - 2].strip()
            if prev and FIELD_EMOJI_RE.match(prev):
                errors.append(f"第 {idx} 行：字段行之间缺少空行分隔（{prev[:20]}... 和 {line.strip()[:20]}... 之间应有空行）")

    item_indexes: list[int] = []
    for idx, line in enumerate(lines, 1):
        if NON_NEWS_LINE_RE.match(line):
            continue
        is_item_line = ITEM_LINE_RE.match(line)
        if is_item_line:
            item_indexes.append(idx - 1)
        if is_item_line and not has_link(line):
            errors.append(f"第 {idx} 行：条目缺少 Markdown 链接")

    for start in item_indexes:
        block_lines = [lines[start]]
        for next_line in lines[start + 1 : start + 12]:
            if ITEM_LINE_RE.match(next_line) or next_line.startswith("#"):
                break
            block_lines.append(next_line)
        block = "\n".join(block_lines)
        first = lines[start]

        if "GitHub#" in first and "Stars" not in block and "⭐" not in block and "热度" not in block:
            errors.append(f"第 {start + 1} 行：GitHub 条目缺少 Stars 字段")
        if "GitHub#" in first:
            for required in ("📌 项目", "🧩 是干嘛的", "🔥 为什么热", "👀 后续看"):
                if required not in block:
                    errors.append(f"第 {start + 1} 行：GitHub 条目缺少 {required} 字段")
        if "HN#" in first:
            if "Points" not in block and "points" not in block:
                errors.append(f"第 {start + 1} 行：HN 条目缺少 Points 字段")
            if "Comments" not in block and "comments" not in block:
                errors.append(f"第 {start + 1} 行：HN 条目缺少 Comments 字段")
            if "💡 解读" not in block:
                errors.append(f"第 {start + 1} 行：HN 条目缺少 💡 解读")
        if "📜" in first or "arXiv#" in first:
            for required in ("核心贡献", "工程价值", "局限", "💡 解读"):
                if required not in block:
                    errors.append(f"第 {start + 1} 行：论文条目缺少 {required} 字段")
        if any(token in first for token in ("#1", "抖音#", "微博#", "知乎#", "百度#")):
            if any(platform in block for platform in ("抖音", "微博", "知乎", "百度")) and "热度" not in block:
                errors.append(f"第 {start + 1} 行：社媒热榜条目缺少热度字段")

        # ── 质量规则增强（用户明确要求的质量标准）──
        is_github = "GitHub#" in first
        is_hn = "HN#" in first
        is_paper = "📜" in first

        # 检查国内热点条目是否有 💡 解读
        # 只检查明确属于国内热点子栏目的条目（含"国内"上下文标记），不检查国外栏目
        if not is_github and not is_hn and not is_paper:
            domestic_markers = ("🌞", "🔬", "🎬", "⚽", "🚗", "🏮", "时政", "外交", "社会", "民生", "科技", "数码", "娱乐", "综艺", "体育", "赛事", "汽车", "能源")
            skip_markers = ("🌏", "🌍", "国际", "国外")
            has_domestic = any(dmarker in block for dmarker in domestic_markers)
            has_skip = any(smarker in block for smarker in skip_markers)
            if has_domestic and not has_skip:
                if "💡" not in block:
                    errors.append(f"第 {start + 1} 行：国内热点条目缺少 💡 解读")

        # 检查社媒热榜条目是否有 💡 解读
        if any(p in first for p in ("抖音#", "微博#", "知乎#", "百度#", "B站#")):
            if "💡 解读" not in block:
                errors.append(f"第 {start + 1} 行：社媒热榜条目缺少 💡 解读")

        # 检查 GitHub 🧩 是否太短（至少 3 行或 60 字）
        if is_github:
            zhuai_lines = [line_text for line_text in block_lines if "🧩 是干嘛的" in line_text]
            if zhuai_lines:
                zhuai_text = zhuai_lines[0].split("🧩 是干嘛的")[-1].strip()
                if len(zhuai_text) < 40:
                    errors.append(f"第 {start + 1} 行：GitHub 🧩 太短（{len(zhuai_text)}字），至少写 2-5 句")

        # 检查所有条目是否有热度值或平台排名（国内热点条目）
        if not is_github and not is_hn and not is_paper:
            if any(m in block for m in ("🌞", "🔬", "🎬", "⚽", "🌏", "🌍")):
                if "热度" not in block and "排名未获取" not in block and "热度未获取" not in block:
                    if "来源：" not in block or ("·" not in block and "热度" not in block):
                        errors.append(f"第 {start + 1} 行：条目缺少热度值或平台排名")

    return errors


def read_text_auto(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：validate_briefing.py <简报文件.md>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    text = read_text_auto(path)
    errors = validate(text)
    if errors:
        print("未通过")
        for error in errors:
            print(f"- {error}")
        return 1

    print("通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
