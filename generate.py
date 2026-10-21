#!/usr/bin/env python3
"""
generate.py — 自驾路线图生成器（兼容入口）

一键完成：YAML → resolve → render → HTML

用法:
  python3 generate.py trips/jindongnan.yaml
  python3 generate.py trips/jindongnan.yaml --output mymap.html

等价于:
  python3 resolve.py trips/jindongnan.yaml
  python3 render.py resolved/jindongnan.json --output output/jindongnan.html
"""

import sys
import os
import subprocess

from version import __version__

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESOLVED_DIR = os.path.join(BASE_DIR, 'resolved')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')


def main():
    if '--version' in sys.argv:
        print(f"tumu-roadbook {__version__}")
        return

    if len(sys.argv) < 2:
        print("用法: python3 generate.py trips/xxx.yaml [--output output.html]")
        print("")
        print("等价命令:")
        print("  # 先解析（查坐标、算路、校验）")
        print("  python3 resolve.py trips/xxx.yaml")
        print("  # 再渲染（出 HTML）")
        print("  python3 render.py resolved/xxx.json")
        sys.exit(1)

    yaml_path = sys.argv[1]
    output_path = None
    if '--output' in sys.argv:
        idx = sys.argv.index('--output')
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    if not os.path.exists(yaml_path):
        print(f"❌ 文件不存在: {yaml_path}")
        sys.exit(1)

    # Step 1: Resolve
    resolved_out = None
    if output_path:
        # Custom output → we need a temp resolved path
        base = os.path.splitext(os.path.basename(yaml_path))[0]
        resolved_out = os.path.join(RESOLVED_DIR, f"{base}.json")

    print("=" * 50)
    print("阶段 1/3: 解析 YAML + 算路 + 校验")
    print("=" * 50)
    resolve_args = [sys.executable, os.path.join(BASE_DIR, 'resolve.py'), yaml_path]
    if resolved_out:
        resolve_args.extend(['--output', resolved_out])
    
    r1 = subprocess.run(resolve_args)
    if r1.returncode != 0:
        print("\n❌ resolve.py 失败")
        sys.exit(1)

    # Determine resolved path
    if not resolved_out:
        base = os.path.splitext(os.path.basename(yaml_path))[0]
        resolved_out = os.path.join(RESOLVED_DIR, f"{base}.json")

    # Step 2: Render
    print("")
    print("=" * 50)
    print("阶段 2/3: 渲染 HTML")
    print("=" * 50)
    render_args = [sys.executable, os.path.join(BASE_DIR, 'render.py'), resolved_out]
    if output_path:
        render_args.extend(['--output', output_path])

    r2 = subprocess.run(render_args)
    if r2.returncode != 0:
        print("\n❌ render.py 失败")
        sys.exit(1)

    print("")
    print("=" * 50)
    print("阶段 3/3: 重建路线册首页")
    print("=" * 50)
    r3 = subprocess.run([sys.executable, os.path.join(BASE_DIR, 'build_index.py')])
    if r3.returncode != 0:
        print("\n❌ build_index.py 失败")
        sys.exit(1)

    print("\n✅ 生成完成")


if __name__ == '__main__':
    main()
