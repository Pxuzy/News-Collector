# 简报生成后 24 板块完整性检查

生成 MD 文件后，在发送前执行此检查确认所有板块完整。

## 检查命令

```python
path = 'E:/hermes/profiles/news-collector/cron/output/每日新闻-YYYY-MM-DD.md'
data = open(path, 'r', encoding='utf-8').read()
checks = [
    '今日主线', '国内热点', '时政·外交', '财经·商业', '科技·数码',
    '汽车·能源', '娱乐·综艺', '体育·赛事', '社会·民生',
    '国外热点', '社媒热榜', '抖音', '微博热搜', '知乎热榜', '百度热搜',
    'AI·前沿', 'GitHub 趋势', 'HackerNews', '论文·学术',
    '平台统计', '全景判断', '继续跟踪', '风险与机会', '数据缺口'
]
all_ok = True
for c in checks:
    found = c in data
    if not found:
        print(f'  [MISS] {c}')
        all_ok = False
    else:
        print(f'  [OK] {c}')
print()
if all_ok:
    print('✓ All 24 sections present')
else:
    print(f'✗ Missing {sum(1 for c in checks if c not in data)} sections')
```

## 自检项

1. 文件大小 > 20KB（避免空文件或截断）
2. 不含 `\r` 字符（CR）：`b'\r' in open(path, 'rb').read()`
3. 所有板块关键词可匹配（24个关键词全部存在）
4. 无 Markdown 表格（`|` 分隔行）
5. 每条新闻都有 `>` 引用块
6. 链接格式为 `[标题](URL)` 而非裸 URL
