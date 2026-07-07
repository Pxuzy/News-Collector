# Cron 采集器包装脚本说明

## 用途

`scripts/run_collector_silent.py` 是 `news-toolkit-collector` cron 任务的包装脚本，
以 `no_agent=true` 模式运行，不依赖 LLM API。

## 触发链

```
news-toolkit-collector（08:55 / 20:55）
  ↓ no_agent=true
  run_collector_silent.py
    ↓ subprocess
    multi_source_news.py（默认全量 50 源）
      ↓ 入库
      news.db
         ↓ 5 分钟后
enhanced-news-briefing（09:00 / 21:00）
```

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 超时 | 300 秒 | 全量 50 源平均 120 秒，留余量 |
| 采集模式 | 默认（无 flag） | = 全量 50 源；`--core` = 32 核心源 |
| 工作目录 | `E:\hermes\workspace\news-toolkit` | multi_source_news.py 所在目录 |

## 已知问题

- 3-5 个源偶尔超时（RSS/V2EX 等），不影响整体采集结果
- `--core` vs 全量：全量多约 18 个源（Reddit/Lobsters/Googlenews 类），耗时翻倍
