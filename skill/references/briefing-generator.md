#!/usr/bin/env python
"""
完整简报生成器 — 符合 v17 规范的单脚本实现。

使用方式：
    cd /e/hermes/profiles/news-collector && python scripts/gen_v17_briefing.py

输出：
    E:\\hermes\\profiles\\news-collector\\cron\\output\\每日新闻-YYYY-MM-DD-v17.md

包含：
    - 数据预检（第 0 步）
    - GitHub 日榜 + 周榜
    - 国内 7 子板块
    - 4 行带标签解读（📌事件/🌊影响/👀后续/💡建议）
    - 国外/AI/HN/论文/社媒榜
    - 收尾 5 栏目
    - 数据缺口

完整脚本路径：E:\\hermes\\profiles\\news-collector\\scripts\\gen_v17_briefing.py
