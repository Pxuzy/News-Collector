#!/usr/bin/env python
"""
v23 简报生成模板（2026-07-01）
===============================
严格遵循 confirmed-format-template.md 的 v23 格式输出.
用 `store.query()` 直接查 news.db（比 nb_query.py 更快），
写入 MD 文件 → 清理 \\r → validator 校验 → MEDIA 发送.

使用方法：
  python gen_v23_briefing.py
  # 产出 E:\\hermes\\profiles\\news-collector\\cron\\output\\每日新闻-YYYY-MM-DD.md

字段规则：
  - 一条新闻 = 一个 > 块，字段间用尾部双空格换行
  - 论文 = 每个字段独立 > 块，块间空行隔开
  - 社媒 = 紧凑排列，条目标题 + > 💡 解读
  - GitHub = 日榜#N [owner/repo](url) ⭐ Stars · 语言
  - HN = HN#N [标题](url) Points：xxx · Comments：未获取 · 类型：xxx
"""

import sys, os
sys.path.insert(0, r'E:\hermes\workspace\news-toolkit\scripts')
from store import query

# ── 路径 ──
OUTPUT_DIR = r'E:\hermes\profiles\news-collector\cron\output'
os.makedirs(OUTPUT_DIR, exist_ok=True)

from datetime import date
today = date.today().isoformat()  # 2026-07-01
path = os.path.join(OUTPUT_DIR, f'每日新闻-{today}.md')

L = []  # lines accumulator
def add(text=""):
    L.append(text)

# ════════════════════════════════════════════════
# 数据采集（替换以下占位内容即可）
# 用 store.query() 查 DB，比 nb_query.py 更快
# ════════════════════════════════════════════════
# items, total = query(source='toutiao', days=1, limit=10)
# for i in items: print(i['title'], i.get('heat',''))

# ── 请在下方填入具体内容 ──
# 参考 gen_brief_0701_v3.py 的完整实现

add('📰 **今日热点 · 全源聚合**')
add('')
add(f'📅 `{today}（周三）` · `简报版`')
add('')
add('**数据来源**：头条/微博/知乎/百度/抖音/IT之家/GitHub/HN/arXiv')
add('')

# ── 写入文件 ──
content = '\n'.join(L)
with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
# 清理 \\r
data = open(path, 'rb').read().replace(b'\r', b'')
open(path, 'wb').write(data)
print(f'Done! {len(content)} chars -> {path}')
