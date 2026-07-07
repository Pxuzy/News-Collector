# 中文ASCII双引号导致Python SyntaxError 的修复方法

## 问题现象

当生成MD简报的 Python 脚本中包含中文文本时，如果文本内有 ASCII 双引号 `"` (U+0022)，例如：

- 「杀回楼市」「真兜底」「996」
- 「死亡之组团灭」「德国队已解散」

使用 `lines.append("...text with "quotes"...")` 时，内部的双引号会提前截断 Python 字符串，导致 `SyntaxError: invalid syntax`。

## 根本原因

中文文本中的引号有时候是 ASCII 双引号 `"` (U+0022) 而非中文全角引号 `""` (U+201C/U+201D)。write_file 工具写入时可能自动将 Unicode 引号转为 ASCII 引号。

## 修复方法

### 方法一：单引号包裹（推荐）

```python
# 错误：双引号字符串内的 " 会被误解
lines.append("事件：用户称"杀回楼市"引发关注")

# 正确：改用单引号包裹
lines.append('事件：用户称"杀回楼市"引发关注')
```

### 方法二：元组列表 + 循环（适合大量数据）

```python
data = [
    ('标题', '来源', '事件：这里可以包含"引号"'),
    ('标题2', '来源2', '事件2'),
]
for t, s, e in data:
    L.append(f'🟠 [{t}](url)')
    L.append(f'> 📍 来源：{s}')
    L.append(f'> 📌 事件：{e}')
```

### 方法三：数据驱动（最安全）

将文本数据放在单独的数据结构中（列表、元组、字典），用循环写入 lines，避免在字符串字面量中嵌套引号。

## 预检

写入脚本前预检语法：
```bash
python -c "compile(open('script.py').read(), 'script.py', 'exec')"
```

注意：`write_file` 的 lint 检查可能误报 SyntaxError。直接用 `python script.py` 运行验证最可靠。

## f-string 表达式内反斜杠限制 (Python 3.11)

**注意**：这是一个与中文引号问题不同的 SyntaxError，但同样在生成脚本时高频触发。

### 问题

Python <3.12 禁止在 f-string 的 `{}` 表达式部分使用反斜杠。以下写法会报错：

```python
# ❌ SyntaxError: f-string expression part cannot include a backslash
add(f"🟠 {fmt_link('电动汽车\"最严国标\"来了', url)}")
```

这里的 `\"` 在 f-string 的 `{}` 表达式内，Python 解析器会拒绝。

### 修复方法

**方法一：将内容存入变量**（推荐）
```python
_ev = '电动汽车\u201c最严国标\u201d来了'
add(f"🟠 {fmt_link(_ev, url)}")
```

**方法二：用 Unicode 左右引号代替 `\"`**
```python
# \u201c = "  \u201d = "
fmt_link('电动汽车\u201c最严国标\u201d正式实施', url)
```

**方法三：改用普通字符串拼接**
```python
add("🟠 " + fmt_link('电动汽车"最严国标"来了', url))
```

### 预检

写入脚本前必须运行：
```bash
python -c "compile(open('script.py').read(), 'script.py', 'exec')"
```

注意：`write_file` 的 lint 检查**不**可靠，直接 `python script.py` 运行验证最准确。
