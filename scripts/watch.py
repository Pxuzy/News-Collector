#!/usr/bin/env python
# coding=utf-8
"""
关键词监控告警 — 配合 Hermes cron 使用
从SQLite查询匹配关键词的新闻，按热度加权排序输出

用法:
    python watch.py --keywords "A股,降准,关税,华为,AI芯片"
    python watch.py --keywords "新能源" --min-heat 1000000
    python watch.py --register "新能源,降息"   # 注册到 Hermes cron
"""
import json
import sys
import os
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from store import _db as get_db, CST, heat_to_score

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
KEYWORDS_FILE = os.path.join(CONFIG_DIR, "watch_keywords.json")


def load_keywords(keywords_file=None):
    """加载关键词列表"""
    if keywords_file and os.path.exists(keywords_file):
        with open(keywords_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    # 默认关键词
    return [
        "A股", "降准", "降息", "关税", "华为", "AI芯片", "大模型",
        "新能源", "光伏", "锂电", "半导体", "芯片", "国产替代",
        "量化", "北上资金", "主力资金", "北向", "外资",
        "政策", "利好", "利空", "暴跌", "暴涨", "熔断",
        "OpenAI", "GPT", "Claude", "Gemini", "特斯拉",
    ]


def match_keywords(items, keywords, min_heat=0):
    """
    匹配关键词，返回评分后的结果
    评分 = 匹配关键词数 × 热度权重
    """
    results = []
    for item in items:
        title = item.get('title', '')
        heat_str = item.get('heat', '') or ''
        heat_val = float(item.get('heat_score') or heat_to_score(heat_str))
        
        # 关键词匹配
        matched = []
        for kw in keywords:
            if kw.lower() in title.lower():
                matched.append(kw)
        
        if not matched:
            continue
        
        # 评分: 匹配词数 × log(热度+1)
        import math
        score = len(matched) * math.log(heat_val + 1) if heat_val > 0 else len(matched)
        
        if heat_val < min_heat:
            continue
        
        results.append({
            'title': title,
            'url': item.get('url', ''),
            'source': item.get('source', ''),
            'heat': heat_str,
            'heat_val': heat_val,
            'matched_keywords': matched,
            'score': round(score, 2),
        })
    
    # 按评分排序
    results.sort(key=lambda x: -x['score'])
    return results


def generate_alert(results, keywords, max_items=10):
    """生成告警Markdown"""
    if not results:
        return None
    
    now = datetime.now(CST).strftime('%Y-%m-%d %H:%M')
    kw_str = ', '.join(keywords[:8])
    if len(keywords) > 8:
        kw_str += f' +{len(keywords)-8}个'
    
    lines = [
        "🚨 **新闻监控告警**",
        f"📅 {now}",
        f"🔍 监控关键词: {kw_str}",
        f"📊 匹配: {len(results)} 条",
        "",
        "---",
        ""
    ]
    
    for i, r in enumerate(results[:max_items], 1):
        kw_tag = ' '.join(f'`{k}`' for k in r['matched_keywords'][:3])
        if len(r['matched_keywords']) > 3:
            kw_tag += f' +{len(r["matched_keywords"])-3}'
        heat = f' [{r["heat"]}]' if r['heat'] else ''
        lines.append(f'### {i}. {r["title"]}{heat}')
        lines.append(f'**来源**: {r["source"]}  **匹配**: {kw_tag}')
        lines.append(f'**链接**: [{r["title"][:30]}...]({r["url"]})')
        lines.append('')
    
    lines.append('---')
    lines.append(f'共 {len(results)} 条匹配 · 展示前 {min(len(results), max_items)} 条')
    
    return '\n'.join(lines)


def check_from_db(keywords, hours=6, min_heat=0):
    """从DB查最近N小时的新闻"""
    conn = get_db()
    cutoff = (datetime.now(CST) - timedelta(hours=hours)).isoformat()
    rows = conn.execute("""
        SELECT source, title, url, heat, heat_score, extra
        FROM news_items
        WHERE last_seen >= ? AND COALESCE(is_duplicate,0)=0
        ORDER BY last_seen DESC
    """, (cutoff,)).fetchall()
    conn.close()
    
    items = [dict(r) for r in rows]
    results = match_keywords(items, keywords, min_heat)
    return results


def main():
    parser = argparse.ArgumentParser(description="关键词监控告警")
    parser.add_argument("--keywords", "-k", help="关键词，逗号分隔")
    parser.add_argument("--keywords-file", "-f", help="从JSON文件加载关键词")
    parser.add_argument("--hours", type=int, default=6, help="回溯小时数")
    parser.add_argument("--min-heat", type=float, default=0, help="最低热度阈值")
    parser.add_argument("--max-items", type=int, default=15, help="最多输出条数")
    parser.add_argument("--save", action="store_true", help="保存到文件")
    parser.add_argument("--register", help="注册关键词到配置文件 (逗号分隔)")
    args = parser.parse_args()

    # 注册关键词
    if args.register:
        keywords = [k.strip() for k in args.register.split(',') if k.strip()]
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(KEYWORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
        print(f"✅ 已注册 {len(keywords)} 个监控关键词到 {KEYWORDS_FILE}")
        print(f"   关键词: {', '.join(keywords)}")
        print("   盘中监控 (9:00-15:00 每30min) 自动生效")
        return
    
    # 加载关键词
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(',') if k.strip()]
    else:
        keywords = load_keywords(args.keywords_file)
    
    if not keywords:
        print("❌ 请指定 --keywords")
        sys.exit(1)
    
    results = check_from_db(keywords, args.hours, args.min_heat)
    alert = generate_alert(results, keywords, args.max_items)
    
    if alert:
        print(alert)
        
        # 保存文件
        if args.save:
            ts = datetime.now(CST).strftime('%Y%m%d_%H%M')
            path = os.path.join(OUTPUT_DIR, f'alert_{ts}.md')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(alert + '\n')
            # 同时写入 latest
            latest = os.path.join(OUTPUT_DIR, 'latest_alert.md')
            with open(latest, 'w', encoding='utf-8') as f:
                f.write(alert + '\n')
            print(f"\n💾 已保存: {path}")
    else:
        print(f"🔍 监控关键词: {', '.join(keywords)}")
        print(f"   最近{args.hours}小时: 0 条匹配")


if __name__ == "__main__":
    main()
