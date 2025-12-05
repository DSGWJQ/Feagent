#!/usr/bin/env python
"""节点定义 YAML 校验脚本

用法：
    python scripts/validate_node_definitions.py                    # 校验所有节点
    python scripts/validate_node_definitions.py definitions/nodes/llm.yaml  # 校验单个文件
    python scripts/validate_node_definitions.py --strict           # 严格模式（警告也报错）

示例输出：
    ✅ llm.yaml - Valid
    ❌ invalid.yaml - Invalid (2 errors)
       - name: Missing required field
       - version: Invalid format
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.domain.services.node_yaml_validator import NodeYamlValidator  # noqa: E402


def validate_file(validator: NodeYamlValidator, file_path: Path, strict: bool = False) -> bool:
    """校验单个文件

    参数：
        validator: 校验器实例
        file_path: 文件路径
        strict: 是否严格模式

    返回：
        是否通过校验
    """
    result = validator.validate_yaml_file(file_path)

    if result.is_valid and (not strict or len(result.warnings) == 0):
        print(f"[PASS] {file_path.name} - Valid")
        if result.warnings:
            for warning in result.warnings:
                print(f"   [WARN] {warning.field}: {warning.message}")
        return True
    else:
        error_count = len(result.errors)
        warning_count = len(result.warnings)
        status = f"Invalid ({error_count} errors"
        if warning_count > 0:
            status += f", {warning_count} warnings"
        status += ")"
        print(f"[FAIL] {file_path.name} - {status}")

        for error in result.errors:
            print(f"   [ERROR] {error.field}: {error.message}")
            if error.suggestion:
                print(f"      Hint: {error.suggestion}")

        for warning in result.warnings:
            print(f"   [WARN] {warning.field}: {warning.message}")

        return False


def validate_directory(
    validator: NodeYamlValidator, dir_path: Path, strict: bool = False
) -> tuple[int, int]:
    """校验目录下所有 YAML 文件

    参数：
        validator: 校验器实例
        dir_path: 目录路径
        strict: 是否严格模式

    返回：
        (通过数, 失败数)
    """
    passed = 0
    failed = 0

    yaml_files = list(dir_path.glob("*.yaml")) + list(dir_path.glob("*.yml"))

    if not yaml_files:
        print(f"[WARN] No YAML files found in {dir_path}")
        return 0, 0

    print(f"\nValidating {len(yaml_files)} files in {dir_path}\n")
    print("-" * 60)

    for yaml_file in sorted(yaml_files):
        if validate_file(validator, yaml_file, strict):
            passed += 1
        else:
            failed += 1

    return passed, failed


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Validate node definition YAML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_node_definitions.py
  python scripts/validate_node_definitions.py definitions/nodes/llm.yaml
  python scripts/validate_node_definitions.py --strict
  python scripts/validate_node_definitions.py --dir definitions/tools
        """,
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="YAML file to validate (optional, defaults to all in definitions/nodes/)",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="definitions/nodes",
        help="Directory to validate (default: definitions/nodes)",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Strict mode: treat warnings as errors"
    )
    parser.add_argument("--schema", type=str, help="Path to JSON Schema file (optional)")

    args = parser.parse_args()

    # 创建校验器
    schema_path = Path(args.schema) if args.schema else None
    validator = NodeYamlValidator(schema_path=schema_path)

    print("=" * 60)
    print("Feagent Node Definition Validator")
    print("=" * 60)

    if args.file:
        # 校验单个文件
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"[ERROR] File not found: {file_path}")
            sys.exit(1)

        print(f"\nValidating: {file_path}\n")
        success = validate_file(validator, file_path, args.strict)
        sys.exit(0 if success else 1)
    else:
        # 校验目录
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"[ERROR] Directory not found: {dir_path}")
            sys.exit(1)

        passed, failed = validate_directory(validator, dir_path, args.strict)

        print("-" * 60)
        print(f"\nSummary: {passed} passed, {failed} failed")

        if failed > 0:
            print("\nHint: Run with --strict to also check warnings")
            sys.exit(1)
        else:
            print("\nAll validations passed!")
            sys.exit(0)


if __name__ == "__main__":
    main()
