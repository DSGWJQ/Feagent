#!/usr/bin/env python
"""工具配置验证脚本

用于 CI 检查，确保所有工具配置文件有效。

用法:
    python -m scripts.validate_tool_configs
    python -m scripts.validate_tool_configs --dir tools/
    python -m scripts.validate_tool_configs --verbose
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.domain.services.tool_config_loader import ToolConfigLoader  # noqa: E402


def validate_tool_configs(
    directory: str = "tools",
    verbose: bool = False,
) -> tuple[int, int, list[tuple[str, str]]]:
    """验证目录中的所有工具配置文件

    参数:
        directory: 工具配置目录
        verbose: 是否输出详细信息

    返回:
        (成功数, 失败数, 错误列表)
    """
    loader = ToolConfigLoader()
    dir_path = Path(directory)

    if not dir_path.exists():
        print(f"警告: 目录不存在 {directory}")
        return 0, 0, []

    configs, errors = loader.load_from_directory_with_errors(str(dir_path))

    success_count = len(configs)
    fail_count = len(errors)

    if verbose:
        print(f"\n{'=' * 60}")
        print("工具配置验证报告")
        print(f"{'=' * 60}")
        print(f"目录: {directory}")
        print(f"成功: {success_count}")
        print(f"失败: {fail_count}")
        print(f"{'=' * 60}\n")

        if configs:
            print("已验证的工具:")
            for config in configs:
                print(f"  [OK] {config.name} (v{config.version}) - {config.category}")

        if errors:
            print("\n验证失败的文件:")
            for filename, error in errors:
                print(f"  [FAIL] {filename}")
                print(f"    错误: {error}")

    return success_count, fail_count, errors


def main():
    parser = argparse.ArgumentParser(
        description="验证工具配置文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dir",
        default="tools",
        help="工具配置目录 (默认: tools)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="输出详细信息",
    )

    args = parser.parse_args()

    success, fail, errors = validate_tool_configs(
        directory=args.dir,
        verbose=args.verbose,
    )

    # 输出摘要
    print(f"\n工具配置验证完成: {success} 成功, {fail} 失败")

    if fail > 0:
        print("\n错误详情:")
        for filename, error in errors:
            print(f"  - {filename}: {error}")
        sys.exit(1)
    else:
        print("所有配置文件验证通过!")
        sys.exit(0)


if __name__ == "__main__":
    main()
