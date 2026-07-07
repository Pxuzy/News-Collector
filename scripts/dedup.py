#!/usr/bin/env python
"""跨源去重 — 2-gram Jaccard 相似度"""
import re, json
from collections import defaultdict


def _norm(t):
    t = re.sub(r'^(突发|重磅|快讯|最新|独家|刚刚|现场|直击|大消息)[:：\s]*', '', str(t).lower())
    t = re.sub(r'[\s·,，。！？、；：""''（）【】《》\u200b\u3000\.\!\?\(\)\[\]\-\—\~\～/\\\\]', '', t)
    return t


def _ng(s, n=2):
    return set(s[i:i+n] for i in range(len(s)-n+1))


def dedup(items, threshold=0.5):
    used = set(); result = []; saved = 0
    norms = [(_norm(i.get('title','')), i) for i in items]
    for i, (n, _) in enumerate(norms):
        if i in used or not n: continue
        cluster = [i]; used.add(i)
        for j, (nj, _) in enumerate(norms[i+1:], i+1):
            if j in used or not nj: continue
            ni_ng = _ng(n)
            nj_ng = _ng(nj)
            if ni_ng and nj_ng and len(ni_ng & nj_ng) / len(ni_ng | nj_ng) > threshold:
                cluster.append(j); used.add(j)
        if len(cluster) > 1: saved += len(cluster) - 1
        # 选最佳: 热度高 + 非搜索页优先
        best = max(cluster, key=lambda k: (
            float(re.sub(r'[^\d.]','',str(norms[k][1].get('heat','') or 0)) or 0)
            + (100000 if 'baidu.com/s?wd' not in norms[k][1].get('url','') and 'weibo.com' not in norms[k][1].get('url','') else 0)
        ))
        item = dict(norms[best][1])
        item['_sources'] = sorted(set(norms[k][1].get('source','') for k in cluster))
        result.append(item)
    return result, saved
