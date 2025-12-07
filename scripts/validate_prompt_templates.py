#!/usr/bin/env python3
"""提示词模板校验脚本

功能：
1. 验证所有 YAML 模板文件的格式正确性
2. 验证模板变量声明与实际使用的完整性
3. 检查必需字段是否存在
4. 生成校验报告

使用方式：
    python scripts/validate_prompt_templates.py
    python scripts/validate_prompt_templates.py --verbose
    python scripts/validate_prompt_templates.py --report-json

创建日期：2025-12-07
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ValidationIssue:
    """校验问题"""

    file: str
    level: str  # error, warning, info
    message: str
    field: str | None = None


@dataclass
class ModuleValidationResult:
    """模块校验结果"""

    file_path: str
    module_name: str
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class OverallValidationReport:
    """总体校验报告"""

    total_files: int
    passed_files: int
    failed_files: int
    total_issues: int
    error_count: int
    warning_count: int
    results: list[ModuleValidationResult] = field(default_factory=list)


# 必需字段定义
REQUIRED_FIELDS = ["name", "version", "description", "template", "variables", "applicable_agents"]

# 推荐字段定义
RECOMMENDED_FIELDS = ["metadata", "variable_descriptions", "usage_examples"]


def extract_template_variables(template: str) -> set[str]:
    """从模板中提取变量名"""
    import re

    pattern = re.compile(r"\{(\w+)\}")
    return set(pattern.findall(template))


def validate_yaml_file(file_path: Path) -> ModuleValidationResult:
    """验证单个 YAML 文件"""
    issues: list[ValidationIssue] = []
    module_name = "unknown"

    try:
        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        issues.append(
            ValidationIssue(
                file=str(file_path),
                level="error",
                message=f"YAML 解析错误: {e}",
            )
        )
        return ModuleValidationResult(
            file_path=str(file_path),
            module_name=module_name,
            is_valid=False,
            issues=issues,
        )
    except Exception as e:
        issues.append(
            ValidationIssue(
                file=str(file_path),
                level="error",
                message=f"文件读取错误: {e}",
            )
        )
        return ModuleValidationResult(
            file_path=str(file_path),
            module_name=module_name,
            is_valid=False,
            issues=issues,
        )

    # 检查是否为有效字典
    if not isinstance(data, dict):
        issues.append(
            ValidationIssue(
                file=str(file_path),
                level="error",
                message="YAML 内容必须是字典格式",
            )
        )
        return ModuleValidationResult(
            file_path=str(file_path),
            module_name=module_name,
            is_valid=False,
            issues=issues,
        )

    # 获取模块名
    module_name = data.get("name", "unknown")

    # 1. 检查必需字段
    for field_name in REQUIRED_FIELDS:
        if field_name not in data:
            issues.append(
                ValidationIssue(
                    file=str(file_path),
                    level="error",
                    message=f"缺少必需字段: {field_name}",
                    field=field_name,
                )
            )
        elif data[field_name] is None or (
            isinstance(data[field_name], str) and not data[field_name].strip()
        ):
            issues.append(
                ValidationIssue(
                    file=str(file_path),
                    level="error",
                    message=f"字段 '{field_name}' 不能为空",
                    field=field_name,
                )
            )

    # 2. 检查推荐字段
    for field in RECOMMENDED_FIELDS:
        if field not in data:
            issues.append(
                ValidationIssue(
                    file=str(file_path),
                    level="warning",
                    message=f"建议添加字段: {field}",
                    field=field,
                )
            )

    # 3. 检查版本格式
    version = data.get("version", "")
    if version:
        parts = str(version).split(".")
        if len(parts) != 3:
            issues.append(
                ValidationIssue(
                    file=str(file_path),
                    level="warning",
                    message=f"版本号 '{version}' 不符合语义化版本规范 (x.y.z)",
                    field="version",
                )
            )

    # 4. 检查变量完整性
    template = data.get("template", "")
    declared_vars = set(data.get("variables", []))

    if template:
        template_vars = extract_template_variables(template)

        # 检查模板中使用但未声明的变量
        undeclared = template_vars - declared_vars
        if undeclared:
            issues.append(
                ValidationIssue(
                    file=str(file_path),
                    level="error",
                    message=f"模板中使用但未声明的变量: {sorted(undeclared)}",
                    field="variables",
                )
            )

        # 检查声明但未使用的变量
        unused = declared_vars - template_vars
        if unused:
            issues.append(
                ValidationIssue(
                    file=str(file_path),
                    level="warning",
                    message=f"声明但未在模板中使用的变量: {sorted(unused)}",
                    field="variables",
                )
            )

    # 5. 检查 applicable_agents 是否有效
    agents = data.get("applicable_agents", [])
    valid_agents = {"ConversationAgent", "WorkflowAgent", "CoordinatorAgent"}
    if agents:
        invalid_agents = set(agents) - valid_agents
        if invalid_agents:
            issues.append(
                ValidationIssue(
                    file=str(file_path),
                    level="warning",
                    message=f"未知的 Agent 类型: {sorted(invalid_agents)}",
                    field="applicable_agents",
                )
            )

    # 6. 检查 metadata 结构
    metadata = data.get("metadata", {})
    if metadata and isinstance(metadata, dict):
        if "priority" in metadata:
            priority = metadata["priority"]
            if not isinstance(priority, int) or priority < 1:
                issues.append(
                    ValidationIssue(
                        file=str(file_path),
                        level="warning",
                        message=f"metadata.priority 应该是正整数，当前值: {priority}",
                        field="metadata.priority",
                    )
                )

    # 判断是否通过验证
    has_errors = any(i.level == "error" for i in issues)

    return ModuleValidationResult(
        file_path=str(file_path),
        module_name=module_name,
        is_valid=not has_errors,
        issues=issues,
    )


def validate_all_templates(templates_dir: Path) -> OverallValidationReport:
    """验证目录下所有模板"""
    results: list[ModuleValidationResult] = []

    yaml_files = list(templates_dir.glob("*.yaml")) + list(templates_dir.glob("*.yml"))

    for yaml_file in yaml_files:
        result = validate_yaml_file(yaml_file)
        results.append(result)

    # 统计
    total_files = len(results)
    passed_files = sum(1 for r in results if r.is_valid)
    failed_files = total_files - passed_files

    all_issues = [i for r in results for i in r.issues]
    total_issues = len(all_issues)
    error_count = sum(1 for i in all_issues if i.level == "error")
    warning_count = sum(1 for i in all_issues if i.level == "warning")

    return OverallValidationReport(
        total_files=total_files,
        passed_files=passed_files,
        failed_files=failed_files,
        total_issues=total_issues,
        error_count=error_count,
        warning_count=warning_count,
        results=results,
    )


def print_report(report: OverallValidationReport, verbose: bool = False) -> None:
    """打印校验报告"""
    print("=" * 60)
    print("提示词模板校验报告")
    print("=" * 60)
    print()

    # 总体统计
    print(f"总文件数: {report.total_files}")
    print(f"通过: {report.passed_files}")
    print(f"失败: {report.failed_files}")
    print(
        f"总问题数: {report.total_issues} (错误: {report.error_count}, 警告: {report.warning_count})"
    )
    print()

    # 详细结果
    for result in report.results:
        status = "PASS" if result.is_valid else "FAIL"
        status_color = "\033[92m" if result.is_valid else "\033[91m"
        reset_color = "\033[0m"

        print(f"[{status_color}{status}{reset_color}] {result.module_name} ({result.file_path})")

        if verbose or not result.is_valid:
            for issue in result.issues:
                level_color = "\033[91m" if issue.level == "error" else "\033[93m"
                print(f"  {level_color}{issue.level.upper()}{reset_color}: {issue.message}")
            print()

    # 最终状态
    print("=" * 60)
    if report.failed_files == 0 and report.error_count == 0:
        print("\033[92m所有模板校验通过！\033[0m")
    else:
        print(f"\033[91m校验失败：{report.failed_files} 个文件存在错误\033[0m")


def export_json_report(report: OverallValidationReport, output_path: Path) -> None:
    """导出 JSON 格式报告"""
    data = {
        "summary": {
            "total_files": report.total_files,
            "passed_files": report.passed_files,
            "failed_files": report.failed_files,
            "total_issues": report.total_issues,
            "error_count": report.error_count,
            "warning_count": report.warning_count,
        },
        "results": [
            {
                "file_path": r.file_path,
                "module_name": r.module_name,
                "is_valid": r.is_valid,
                "issues": [
                    {
                        "level": i.level,
                        "message": i.message,
                        "field": i.field,
                    }
                    for i in r.issues
                ],
            }
            for r in report.results
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"JSON 报告已导出到: {output_path}")


def main() -> int:
    """主函数"""
    parser = argparse.ArgumentParser(description="验证提示词模板文件")
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path("docs/prompt_templates"),
        help="模板目录路径",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="显示详细信息",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="导出 JSON 格式报告",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：警告也视为失败",
    )

    args = parser.parse_args()

    # 检查目录是否存在
    if not args.templates_dir.exists():
        print(f"错误：目录不存在 - {args.templates_dir}")
        return 1

    # 执行校验
    report = validate_all_templates(args.templates_dir)

    # 打印报告
    print_report(report, args.verbose)

    # 导出 JSON（如果需要）
    if args.report_json:
        export_json_report(report, args.report_json)

    # 返回退出码
    if args.strict:
        return 0 if report.total_issues == 0 else 1
    else:
        return 0 if report.error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
