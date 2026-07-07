#!/usr/bin/env python
"""v23 canonical 新闻简报生成模板
用法: python templates/gen_md_briefing.py
输出: cron/output/每日新闻-YYYY-MM-DD.md
格式: **粗体标题** + > 引用块 + 彩色圆点 + 尾部双空格换行
"""
import os

OUTPUT_DIR = r"E:\hermes\profiles\news-collector\cron\output"
DATE_STR = "2026-07-01"
WEEKDAY = "周三"
EDITION = "凌晨版"

lines = []
def add(t=""):
    lines.append(t)

# === 文件头 ===
add("📰 **今日热点 · 全源聚合**")
add("")
add("📅 `" + DATE_STR + "（" + WEEKDAY + "）` · `" + EDITION + "`")
add("")
add("**数据来源**：头条/微博/知乎/百度/抖音/IT之家/Reuters/HN/GitHub/arXiv/AIHOT")
add("")

# === 🧭 今日主线 ===
add("**🧭 今日主线**")
add("")

# 数据元组列表（避免中文引号嵌套问题）
items = []

for dot, title, url, source, event, impact, followup in items:
    add(f"{dot} [{title}]({url})")
    add("")
    add(f"> 📍 来源：{source}  ")
    add(f"> 📌 事件：{event}  ")
    add(f"> 🌊 影响：{impact}  ")
    add(f"> 👀 后续：{followup}")
    add("")

# === 写入方法 ===
output_path = os.path.join(OUTPUT_DIR, f"每日新闻-{DATE_STR}.md")
content = "\n".join(lines)

with open(output_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(content)

# 清理 \r
with open(output_path, "rb") as f:
    data = f.read()
data = data.replace(b"\r", b"")
with open(output_path, "wb") as f:
    f.write(data)

print(f"✅ 简报已生成：{output_path}")
print(f"  {len(lines)} 行，{len(content)} 字符")
