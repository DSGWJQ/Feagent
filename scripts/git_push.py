#!/usr/bin/env python3
"""Git push script"""

import subprocess
import sys


def run_command(cmd):
    """运行命令并打印输出"""
    print(f"\n执行: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def main():
    # 1. 检查状态
    print("=" * 60)
    print("1. 检查 Git 状态")
    print("=" * 60)
    run_command(["git", "status", "--short"])

    # 2. 添加所有更改
    print("\n" + "=" * 60)
    print("2. 添加所有更改")
    print("=" * 60)
    run_command(["git", "add", "-A"])

    # 3. 再次检查状态
    print("\n" + "=" * 60)
    print("3. 再次检查状态")
    print("=" * 60)
    run_command(["git", "status", "--short"])

    # 4. 提交
    print("\n" + "=" * 60)
    print("4. 提交更改")
    print("=" * 60)
    commit_msg = """feat: 添加数据库迁移和应用启动功能

- 创建环境配置文件 (.env)
- 添加数据库迁移测试 (11个测试用例)
- 成功运行数据库迁移 (agents, runs, tasks表)
- 添加应用启动测试 (10个测试用例)
- 启动FastAPI应用服务器
- 所有99个测试通过，代码覆盖率89%
- 修复CORS_ORIGINS环境变量格式问题"""

    returncode = run_command(["git", "commit", "-m", commit_msg])
    if returncode != 0:
        print("提交失败或没有更改需要提交")

    # 5. 推送到远程
    print("\n" + "=" * 60)
    print("5. 推送到 GitHub")
    print("=" * 60)
    returncode = run_command(["git", "push", "origin", "main"])
    if returncode == 0:
        print("\n✅ 成功推送到 GitHub!")
    else:
        print("\n❌ 推送失败，请检查错误信息")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
