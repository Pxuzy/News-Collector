#!/usr/bin/env python
"""
Wrapper: 静默运行 news-toolkit 采集器（全量50源），只存库不发送。
no_agent=true 用，直接执行 multi_source_news.py。
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
collector = os.path.join(PROJECT_DIR, "multi_source_news.py")

# 全量50源 + 并行8 + 采集前清理过期数据
result = subprocess.run(
    [sys.executable, collector, "--parallel", "8", "--prune"],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
    cwd=PROJECT_DIR
)

lines = result.stdout.strip().split("\n")

# 统计成功/失败源数
ok_count = sum(1 for line in lines if '"status": "ok"' in line or '✅' in line)
fail_count = sum(1 for line in lines if '"status": "failed"' in line or '❌' in line or '🔴' in line)
error_count = sum(1 for line in lines if '[ERROR]' in line or '[WARNING]' in line)

# 打印所有失败/错误行（最多30行）
error_lines = [line for line in lines if '[ERROR]' in line or '[WARNING]' in line or '❌' in line or '🔴' in line]
for el in error_lines[:30]:
    print(el)

# 打印采集汇总行
summary_lines = [line for line in lines if '采集完成' in line]
for sl in summary_lines:
    print(sl)

if result.returncode != 0:
    print(f"\n❌ 采集进程异常退出 (exit={result.returncode})")
    print(result.stderr[-500:] if result.stderr else "")
    sys.exit(1)

# 如果大量源失败，输出预警
if fail_count > 10:
    print(f"\n⚠️  {fail_count}个源失败，{ok_count}个源成功 — 请检查网络/env")

print(f"\n✅ 采集完成 exit=0 | ✅{ok_count}个源 | ❌{fail_count}个源")

# === 补齐数据缺口 ===
fix_script = os.path.join(SCRIPT_DIR, "fix_data_gaps.py")
if os.path.exists(fix_script):
    try:
        fix_result = subprocess.run(
            [sys.executable, fix_script],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60
        )
        fix_lines = fix_result.stdout.strip().split("\n")
        for fl in fix_lines:
            if '[HN]' in fl or '[GitHub]' in fl or '[Cache]' in fl:
                print(f"  📌 数据补齐: {fl}")
    except Exception as e:
        print(f"  ⚠️ 数据补齐异常: {e}")
