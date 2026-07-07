# Cron 多脚本分步生成模式（2026-07-03 验证）

## 适用场景

当单个生成脚本因包含大量中文内容（800+行、65K+字节）导致 `write_file` 流超时或 `terminal` 执行缓存溢出时，将生成流程拆为多个 Python 脚本依次执行。

## 推荐拆分方案（4部分）

```
gen_part1_data.py     → 纯数据采集，存临时 JSON
gen_part2_briefing.py → 文件头 + 🧭今日主线 + 🏮国内热点（7子板块）
gen_part3_briefing.py → 🌏国外热点 + 🔥社媒热榜 + 🤖AI·前沿
gen_part4_briefing.py → 🐙GitHub日榜+周榜 + 🐱HN + 📜论文 + 📊收尾5栏目
```

## 数据传递

Part1 将查询结果保存为 JSON：
```python
import json, tempfile
tmpfile = os.path.join(os.path.dirname(OUTPUT), '_briefing_data.json')
with open(tmpfile, 'w', encoding='utf-8') as f:
    json.dump(data_package, f, ensure_ascii=False, default=str)
```

后续 Part2/3/4 读取该 JSON：
```python
with open('_briefing_data.json', 'r', encoding='utf-8') as f:
    D = json.load(f)
baidu = D['baidu']
# ... 使用数据
```

## 文件写入策略

- Part1：只写临时 JSON，不碰目标 MD 文件
- Part2：`open(path, 'w', ...)` 创建新文件（写标题+主线+国内）
- Part3：`open(path, 'w', ...)` 重写整个文件（保留 Part2 内容，追加国外+社媒+AI）
- Part4：`open(path, 'w', ...)` 重写整个文件（追加 GitHub+HN+论文+收尾）

每个脚本独立的 `add()` / `lines` 构建器，从 `open(path, 'r')` 读取已有内容基准，追加新行后 `open(path, 'w')` 完整重写。

## 注意事项

1. **每部分末尾清理 `\r`**：`data = open(path, 'rb').read().replace(b'\r', b''); open(path, 'wb').write(data)`
2. **HN 链接直接从 DB 取**：不要硬编码，从 `item['url']` 读取
3. **语法预检**：每部分写入前 `python -c "compile(open('script.py').read(), 'script.py', 'exec')"`
4. **临时 JSON 约 150-300KB**，生成后无需清理（下次运行自动覆盖）
5. **文件命名**：`news-YYYY-MM-DD.md`，避免后缀变体
