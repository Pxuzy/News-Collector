#!/usr/bin/env python
"""
一键全流程：采集 → 补齐 → 生成简报 → 校验 → 输出
用法: python scripts/generate_briefing.py [--core] [--skip-collect]
"""
import datetime
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def step(msg):
    print(f"\n{'='*50}")
    print(f"  {msg}")
    print(f"{'='*50}")

def as_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""

def run(cmd, timeout=120):
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=ROOT,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = as_text(exc.stdout)
        stderr = as_text(exc.stderr)
        for line in stdout.strip().split('\n'):
            if line.strip():
                print(f"  {line.strip()}")
        print(f"  ❌ 超时: {timeout}s")
        tail = (stderr or stdout)[-500:]
        if tail:
            print(f"  {tail}")
        return False
    for line in (result.stdout or "").strip().split('\n'):
        if line.strip():
            print(f"  {line.strip()}")
    if result.returncode != 0:
        print(f"  ❌ 失败: {(result.stderr or result.stdout or '')[-500:]}")
        return False
    return True

def main():
    import argparse
    parser = argparse.ArgumentParser(description='一键全流程：采集→补齐→生成→校验')
    parser.add_argument('--core', action='store_true', help='只跑核心源（更快）')
    parser.add_argument('--skip-collect', action='store_true', help='跳过采集（使用现有DB数据）')
    args = parser.parse_args()

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"\n📰 News-Collector 全流程 | {timestamp}")
    print(f"   项目路径: {ROOT}")
    # Collection and gap-filling are best-effort because a partial run can
    # still leave enough fresh data for a valid briefing. Only generation and
    # the three delivery gates decide whether the briefing is publishable.
    success = True

    # 1. 采集
    if not args.skip_collect:
        collector = os.path.join(ROOT, 'multi_source_news.py')
        cmd = [sys.executable, collector, '--parallel', '8', '--prune']
        if args.core:
            cmd.append('--core')
        step("① 采集新闻")
        if not run(cmd, timeout=180):
            print("  ⚠️ 采集部分失败，继续执行补齐和生成...")
    else:
        step("① 跳过采集（--skip-collect）")

    # 2. 数据补齐
    step("② 补齐数据缺口")
    fix = os.path.join(ROOT, 'scripts', 'fix_data_gaps.py')
    if not run([sys.executable, fix], timeout=180):
        print("  ⚠️ 数据补齐失败，继续生成已有数据简报...")

    # 3. 生成简报（调用 nb_query 获取数据 + Python 生成）
    step("③ 生成简报")
    today = datetime.date.today().strftime('%Y-%m-%d')
    output_path = os.path.join(ROOT, 'output', f'news-{today}.md')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    temp_output_path = os.path.join(
        ROOT, 'output', f'.news-{today}-{os.getpid()}.md.tmp'
    )
    if os.path.exists(temp_output_path):
        os.unlink(temp_output_path)
    
    gen = os.path.join(ROOT, 'scripts', 'gen_today_v23_briefing.py')
    if os.path.exists(gen):
        old_output_path = os.environ.get('BRIEFING_OUTPUT_PATH')
        os.environ['BRIEFING_OUTPUT_PATH'] = temp_output_path
        generated = run([sys.executable, gen], timeout=60)
        if old_output_path is None:
            os.environ.pop('BRIEFING_OUTPUT_PATH', None)
        else:
            os.environ['BRIEFING_OUTPUT_PATH'] = old_output_path
        if not generated:
            success = False
    else:
        success = False
        print("  ⚠️ 简报生成器不存在，需手工生成")
        print(f"  输出路径: {output_path}")

    # 4. 校验
    step("④ 校验简报")
    if os.path.exists(temp_output_path):
        validator = os.path.join(ROOT, 'scripts', 'validate_briefing.py')
        if not run([sys.executable, validator, temp_output_path], timeout=10):
            success = False
        quality = os.path.join(ROOT, 'scripts', 'check_briefing_quality.py')
        if not run([sys.executable, quality, temp_output_path], timeout=30):
            success = False
        if not run([sys.executable, quality, temp_output_path, '--strict'], timeout=30):
            success = False
        if success:
            os.replace(temp_output_path, output_path)
            print(f"\n  ✅ 简报文件: {output_path}")
        else:
            print("\n  ❌ 校验未全部通过，临时简报不会发布")
    else:
        success = False
        print(f"  ⚠️ 简报文件未生成: {output_path}")

    step("✅ 全流程完成")
    if os.path.exists(temp_output_path):
        try:
            os.unlink(temp_output_path)
        except OSError:
            pass
    return 0 if success else 1

if __name__ == '__main__':
    raise SystemExit(main())
