#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v23 简报生成器 — cron 模式参考模板 (2026-07-01)
================================================
严格遵循 confirmed-format-template.md 的 v23 格式输出。
用 store.query() 直接查 news.db（比 nb_query.py 更快），
写入 MD 文件 → 清理 \r → validator 校验 → MEDIA 发送。

使用方法：
  python templates/gen_briefing_cron.py
  # 产出 E:\hermes\profiles\news-collector\cron\output\每日新闻-YYYY-MM-DD.md

编写通则：
  - 所有数据采集在脚本顶部一次性完成
  - 用 add() 函数逐行构建输出行列表
  - 使用列表 + for 循环减少重复
  - 写入时用 open(path, "w", encoding="utf-8", newline="\n")
  - 写入后清理 \r 字符
"""

import sys, os, json
sys.path.insert(0, r'E:\hermes\workspace\news-toolkit\scripts')
from store import query
from datetime import date

# ── 配置 ──
OUTPUT_DIR = r'E:\hermes\profiles\news-collector\cron\output'
os.makedirs(OUTPUT_DIR, exist_ok=True)
today = date.today().isoformat()  # e.g. 2026-07-01
WD_MAP = {0:'周一',1:'周二',2:'周三',3:'周四',4:'周五',5:'周六',6:'周日'}
wd = WD_MAP[date.today().weekday()]
path = os.path.join(OUTPUT_DIR, f'每日新闻-{today}.md')

# ── 数据采集（示例：单源采集）──
# def fetch(source, limit=20):
#     items, total = query(source=source, days=1, limit=limit)
#     return items, total
#
# items, total = fetch('baidu', 15)
# for item in items:
#     print(f"  {item['title'][:50]} | heat={item.get('heat','')[:30]}")

# ── 输出构建 ──
L = []
def add(t=''):
    L.append(t)

# ── 写入以下为实际内容占位 ──

add('📰 **今日热点 · 全源聚合**')
add('')
add(f'📅 `{today}（{wd}）` · `简报版`')
add('')
add('**数据来源**：头条/微博/知乎/百度/抖音/IT之家/GitHub/HN/arXiv  ｜ 采集时间：YYYY-MM-DD HH:MM')
add('')

# --- 在下方填充具体栏目内容 ---
# 参考 confirmed-format-template.md 中的v23格式

add('**🧭 今日主线**')
add('')

# 示例条目格式：
# add('🔴 [标题](URL)')
# add('')
# add('> 📍 来源：头条#1 · 热度2074万  ')
# add('> 📌 事件：发生了什么（2-3句）  ')
# add('> 🌊 影响：对谁有影响（2-3句）  ')
# add('> 👀 后续：下一步看什么（1-2句）')

add('**🏮 国内热点**')
add('')
add('🌍 **时政·外交**')
add('')
add('💰 **财经·商业**')
add('')
add('🔬 **科技·数码**')
add('')
add('🚗 **汽车·能源**')
add('')
add('🎬 **娱乐·综艺**')
add('')
add('⚽ **体育·赛事**')
add('')
add('🌞 **社会·民生**')
add('')

add('**🌏 国外热点**')
add('')
add('**🔥 社媒热榜**')
add('')
add('🎵 **抖音 TOP10**')
add('')
add('💬 **微博热搜**')
add('')
add('💬 **知乎热榜**')
add('')
add('🔍 **百度热搜**')
add('')

add('**🤖 AI·前沿**')
add('')
add('**🐙 GitHub 趋势**')
add('')
add('**🐱 HackerNews TOP10**')
add('')
add('**📜 论文·学术**')
add('')

add('**📊 平台统计**')
add('')
add('**🤖 全景判断**')
add('')
add('**👀 继续跟踪**')
add('')
add('**⚠️ 风险与机会**')
add('')
add('**🧩 数据缺口**')

# ── 写入文件 ──
content = '\n'.join(L)
with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
# 清理 \r
data = open(path, 'rb').read().replace(b'\r', b'')
open(path, 'wb').write(data)
print(f'Done! {len(content)} chars -> {path}')
print(f'Total lines: {len(L)}')
