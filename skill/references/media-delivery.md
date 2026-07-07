# MEDIA 协议文件投递指南（Windows）

## 正确路径格式

```
MEDIA:E:/hermes/profiles/news-collector/cron/output/news-2026-07-01.md
```

### 三条硬规则

1. **盘符+正斜杠** — `E:/path/to/file.md` ✅
   - 不要反斜杠：`E:\path\to\file.md` ❌（Hermes 不识别）
   - 不要 MSYS 路径：`/e/path/to/file.md` ❌（Windows Python 找不到）
2. **英文文件名更稳妥** — `news-2026-07-01.md` ✅
   - 中文文件名 `每日新闻-2026-07-01.md` 偶尔投递失败（Telegram 网关编码问题）
   - 存档用中文名，发送用英文名
3. **仅 Agent 响应有效** — MEDIA 协议只在 LLM Agent 的响应中生效
   - `no_agent=true` cron 的 stdout 直接当文本发送，不支持 MEDIA
   - 需要 MEDIA 交付的 cron 必须用 Agent 模式（`no_agent=false`）

## 支持的文件类型

| 类型 | 扩展名 | 渲染方式 |
|------|--------|---------|
| 图片 | .png .jpg .webp | 内嵌显示为图片 |
| 音频 | .ogg | 语音气泡 |
| 视频 | .mp4 | 内嵌播放 |
| **文档** | **.md .txt .json .csv** | **作为文件附件发送** |

.md 文件没有内嵌预览，但会作为可下载文件附件发送到 Telegram。

## 投递失败排查

| 症状 | 原因 | 修复 |
|------|------|------|
| "Couldn't deliver the file attachment" | 路径格式不对 | 改 `E:/正斜杠/路径.md` |
| 中文文件名投递失败 | 编码问题 | 换英文名 `news-*.md` |
| no_agent cron 输出的 MEDIA: 链接 | no_agent 不支持文件投递 | 改为 Agent 模式 |

## 错误示例

```
MEDIA:E:\hermes\...\每日新闻.md     ❌ 反斜杠
MEDIA:/e/hermes/.../file.md       ❌ MSYS 路径
MEDIA:C:/users/.../file.md        ❌ C 盘不在 allowed directories
```
