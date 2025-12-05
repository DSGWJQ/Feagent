"""通用节点 YAML 规范校验器 (Node YAML Validator)

业务定义：
- 校验 YAML 节点定义文件是否符合通用规范
- 支持 JSON Schema 验证
- 提供语法检查、约束验证、嵌套深度检查
- 支持文件和目录批量校验

设计原则：
- 严格模式：默认严格校验所有字段
- 兼容模式：支持旧格式的警告级别兼容
- 详细报告：提供精确的错误位置和修复建议

使用示例：
    validator = NodeYamlValidator()
    result = validator.validate_yaml_file("definitions/nodes/llm.yaml")
    if not result.is_valid:
        for error in result.errors:
            print(f"{error.field}: {error.message}")
"""

import ast
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

# JSON Schema 路径
SCHEMA_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "definitions"
    / "schemas"
    / "node_definition_schema.json"
)

# 最大嵌套深度
MAX_NESTED_DEPTH = 5


class ErrorSeverity(str, Enum):
    """错误严重级别"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """校验错误

    属性：
        field: 字段路径
        message: 错误消息
        severity: 严重级别
        suggestion: 修复建议
    """

    field: str
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """校验结果

    属性：
        is_valid: 是否有效（无 ERROR 级别错误）
        errors: 错误列表
        warnings: 警告列表
        node_name: 节点名称
    """

    is_valid: bool = True
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    node_name: str | None = None

    def add_error(self, error: ValidationError) -> None:
        """添加错误"""
        if error.severity == ErrorSeverity.ERROR:
            self.errors.append(error)
            self.is_valid = False
        elif error.severity == ErrorSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.warnings.append(error)


@dataclass
class NodeYamlSchema:
    """节点 YAML Schema 定义

    用于描述 YAML 节点定义的结构。
    """

    name: str
    kind: str
    version: str
    executor_type: str
    description: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    category: str | None = None
    parameters: list[dict[str, Any]] | None = None
    returns: dict[str, Any] | None = None
    error_strategy: dict[str, Any] | None = None
    nested: dict[str, Any] | None = None
    dynamic_code: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None


class NodeYamlValidator:
    """节点 YAML 校验器

    职责：
    - 加载和解析 YAML 文件
    - 校验必填字段
    - 校验字段类型和约束
    - 校验嵌套深度
    - 校验动态代码语法
    """

    # 有效的 kind 值
    VALID_KINDS = {"node", "workflow", "template"}

    # 有效的执行器类型
    VALID_EXECUTOR_TYPES = {
        "python",
        "llm",
        "http",
        "database",
        "container",
        "condition",
        "loop",
        "parallel",
        "api",
        "code",  # code 是 python 的别名
    }

    # 有效的参数类型
    VALID_PARAM_TYPES = {"string", "number", "integer", "boolean", "array", "object"}

    # 有效的失败处理动作
    VALID_ON_FAILURE_ACTIONS = {"retry", "skip", "abort", "replan", "fallback"}

    # 版本号正则
    VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$")

    # 标签正则
    TAG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")

    # 名称正则
    NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

    def __init__(self, schema_path: Path | None = None):
        """初始化校验器

        参数：
            schema_path: JSON Schema 文件路径（可选）
        """
        self._schema_path = schema_path or SCHEMA_PATH
        self._schema: dict[str, Any] | None = None

    def _load_schema(self) -> dict[str, Any]:
        """加载 JSON Schema"""
        if self._schema is None:
            if self._schema_path.exists():
                with open(self._schema_path, encoding="utf-8") as f:
                    self._schema = json.load(f)
            else:
                self._schema = {}
        return self._schema

    def validate_yaml_string(self, yaml_content: str) -> ValidationResult:
        """校验 YAML 字符串

        参数：
            yaml_content: YAML 内容字符串

        返回：
            ValidationResult 校验结果
        """
        result = ValidationResult()

        # 解析 YAML
        try:
            data = yaml.safe_load(yaml_content)
            if data is None:
                result.add_error(
                    ValidationError(
                        field="root", message="YAML 内容为空", severity=ErrorSeverity.ERROR
                    )
                )
                return result
        except yaml.YAMLError as e:
            result.add_error(
                ValidationError(
                    field="root", message=f"YAML 解析错误: {e}", severity=ErrorSeverity.ERROR
                )
            )
            return result

        # 校验数据
        return self._validate_data(data)

    def validate_yaml_file(self, file_path: Path | str) -> ValidationResult:
        """校验 YAML 文件

        参数：
            file_path: YAML 文件路径

        返回：
            ValidationResult 校验结果
        """
        file_path = Path(file_path)
        result = ValidationResult()

        if not file_path.exists():
            result.add_error(
                ValidationError(
                    field="file",
                    message=f"File not found: {file_path}",
                    severity=ErrorSeverity.ERROR,
                )
            )
            return result

        try:
            # 尝试多种编码
            yaml_content = None
            for encoding in ["utf-8", "utf-8-sig", "gbk", "latin-1"]:
                try:
                    with open(file_path, encoding=encoding) as f:
                        yaml_content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if yaml_content is None:
                result.add_error(
                    ValidationError(
                        field="file",
                        message=f"Failed to decode file: {file_path}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
                return result

            return self.validate_yaml_string(yaml_content)
        except Exception as e:
            result.add_error(
                ValidationError(
                    field="file", message=f"Failed to read file: {e}", severity=ErrorSeverity.ERROR
                )
            )
            return result

    def validate_directory(self, dir_path: Path | str) -> dict[str, ValidationResult]:
        """校验目录下所有 YAML 文件

        参数：
            dir_path: 目录路径

        返回：
            文件名到校验结果的映射
        """
        dir_path = Path(dir_path)
        results = {}

        for yaml_file in dir_path.glob("*.yaml"):
            results[yaml_file.name] = self.validate_yaml_file(yaml_file)

        for yml_file in dir_path.glob("*.yml"):
            results[yml_file.name] = self.validate_yaml_file(yml_file)

        return results

    def _validate_data(self, data: dict[str, Any]) -> ValidationResult:
        """校验数据结构

        参数：
            data: 解析后的 YAML 数据

        返回：
            ValidationResult 校验结果
        """
        result = ValidationResult()

        # 校验必填字段
        self._validate_required_fields(data, result)

        if not result.is_valid:
            return result

        result.node_name = data.get("name")

        # 校验 name
        self._validate_name(data.get("name"), result)

        # 校验 kind
        self._validate_kind(data.get("kind"), result)

        # 校验 version
        self._validate_version(data.get("version"), result)

        # 校验 executor_type
        self._validate_executor_type(data.get("executor_type"), result)

        # 校验 parameters
        if "parameters" in data:
            self._validate_parameters(data["parameters"], result)

        # 校验 error_strategy
        if "error_strategy" in data:
            self._validate_error_strategy(data["error_strategy"], result)

        # 校验 nested
        if "nested" in data:
            self._validate_nested(data["nested"], result, depth=1)

        # 校验 dynamic_code
        if "dynamic_code" in data:
            self._validate_dynamic_code(data["dynamic_code"], result)

        # 校验 tags
        if "tags" in data:
            self._validate_tags(data["tags"], result)

        # 校验 execution
        if "execution" in data:
            self._validate_execution(data["execution"], result)

        return result

    def _validate_required_fields(self, data: dict[str, Any], result: ValidationResult) -> None:
        """校验必填字段"""
        required_fields = ["name", "kind", "version", "executor_type"]

        for field_name in required_fields:
            if field_name not in data:
                result.add_error(
                    ValidationError(
                        field=field_name,
                        message=f"Missing required field: {field_name}",
                        severity=ErrorSeverity.ERROR,
                        suggestion=f"Add '{field_name}' field to the YAML",
                    )
                )

    def _validate_name(self, name: str | None, result: ValidationResult) -> None:
        """校验节点名称"""
        if name is None:
            return

        if not isinstance(name, str):
            result.add_error(
                ValidationError(
                    field="name", message="name must be a string", severity=ErrorSeverity.ERROR
                )
            )
            return

        if not name.strip():
            result.add_error(
                ValidationError(
                    field="name", message="name cannot be empty", severity=ErrorSeverity.ERROR
                )
            )
            return

        # 名称格式校验（警告级别，兼容旧格式）
        if not self.NAME_PATTERN.match(name):
            result.add_error(
                ValidationError(
                    field="name",
                    message=f"name '{name}' should match pattern ^[a-z][a-z0-9_]*$",
                    severity=ErrorSeverity.WARNING,
                    suggestion="Use lowercase letters, numbers, and underscores only",
                )
            )

    def _validate_kind(self, kind: str | None, result: ValidationResult) -> None:
        """校验 kind 字段"""
        if kind is None:
            return

        if kind not in self.VALID_KINDS:
            result.add_error(
                ValidationError(
                    field="kind",
                    message=f"Invalid kind: '{kind}'. Must be one of: {self.VALID_KINDS}",
                    severity=ErrorSeverity.ERROR,
                    suggestion=f"Use one of: {', '.join(self.VALID_KINDS)}",
                )
            )

    def _validate_version(self, version: str | None, result: ValidationResult) -> None:
        """校验版本号"""
        if version is None:
            return

        if not isinstance(version, str):
            result.add_error(
                ValidationError(
                    field="version",
                    message="version must be a string",
                    severity=ErrorSeverity.ERROR,
                )
            )
            return

        if not self.VERSION_PATTERN.match(version):
            result.add_error(
                ValidationError(
                    field="version",
                    message=f"Invalid version format: '{version}'",
                    severity=ErrorSeverity.ERROR,
                    suggestion="Use semantic versioning: X.Y.Z (e.g., 1.0.0)",
                )
            )

    def _validate_executor_type(self, executor_type: str | None, result: ValidationResult) -> None:
        """校验执行器类型"""
        if executor_type is None:
            return

        if executor_type not in self.VALID_EXECUTOR_TYPES:
            result.add_error(
                ValidationError(
                    field="executor_type",
                    message=f"Invalid executor_type: '{executor_type}'",
                    severity=ErrorSeverity.ERROR,
                    suggestion=f"Use one of: {', '.join(self.VALID_EXECUTOR_TYPES)}",
                )
            )

    def _validate_parameters(
        self, parameters: list[dict[str, Any]], result: ValidationResult
    ) -> None:
        """校验参数列表"""
        if not isinstance(parameters, list):
            result.add_error(
                ValidationError(
                    field="parameters",
                    message="parameters must be a list",
                    severity=ErrorSeverity.ERROR,
                )
            )
            return

        for i, param in enumerate(parameters):
            if not isinstance(param, dict):
                result.add_error(
                    ValidationError(
                        field=f"parameters[{i}]",
                        message="Each parameter must be an object",
                        severity=ErrorSeverity.ERROR,
                    )
                )
                continue

            # 校验必填字段
            if "name" not in param:
                result.add_error(
                    ValidationError(
                        field=f"parameters[{i}]",
                        message="Parameter missing 'name' field",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            if "type" not in param:
                result.add_error(
                    ValidationError(
                        field=f"parameters[{i}]",
                        message="Parameter missing 'type' field",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            elif param.get("type") not in self.VALID_PARAM_TYPES:
                result.add_error(
                    ValidationError(
                        field=f"parameters[{i}].type",
                        message=f"Invalid parameter type: '{param.get('type')}'",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            # 校验约束
            if "constraints" in param and "default" in param:
                self._validate_default_against_constraints(
                    param["default"], param["constraints"], f"parameters[{i}]", result
                )

    def _validate_default_against_constraints(
        self, default: Any, constraints: dict[str, Any], field_path: str, result: ValidationResult
    ) -> None:
        """校验默认值是否满足约束"""
        if not isinstance(constraints, dict):
            return

        if "min" in constraints and isinstance(default, int | float):
            if default < constraints["min"]:
                result.add_error(
                    ValidationError(
                        field=field_path,
                        message=f"Default value {default} violates constraints (min: {constraints['min']})",
                        severity=ErrorSeverity.ERROR,
                    )
                )

        if "max" in constraints and isinstance(default, int | float):
            if default > constraints["max"]:
                result.add_error(
                    ValidationError(
                        field=field_path,
                        message=f"Default value {default} violates constraints (max: {constraints['max']})",
                        severity=ErrorSeverity.ERROR,
                    )
                )

    def _validate_error_strategy(
        self, error_strategy: dict[str, Any], result: ValidationResult
    ) -> None:
        """校验错误策略"""
        if not isinstance(error_strategy, dict):
            result.add_error(
                ValidationError(
                    field="error_strategy",
                    message="error_strategy must be an object",
                    severity=ErrorSeverity.ERROR,
                )
            )
            return

        # 校验 on_failure
        if "on_failure" in error_strategy:
            action = error_strategy["on_failure"]
            if action not in self.VALID_ON_FAILURE_ACTIONS:
                result.add_error(
                    ValidationError(
                        field="error_strategy.on_failure",
                        message=f"Invalid on_failure action: '{action}'",
                        severity=ErrorSeverity.ERROR,
                        suggestion=f"Use one of: {', '.join(self.VALID_ON_FAILURE_ACTIONS)}",
                    )
                )

        # 校验 retry
        if "retry" in error_strategy:
            retry = error_strategy["retry"]
            if isinstance(retry, dict):
                if "max_attempts" in retry:
                    max_attempts = retry["max_attempts"]
                    if not isinstance(max_attempts, int) or max_attempts < 0:
                        result.add_error(
                            ValidationError(
                                field="error_strategy.retry.max_attempts",
                                message="max_attempts must be a non-negative integer",
                                severity=ErrorSeverity.ERROR,
                            )
                        )

    def _validate_nested(
        self, nested: dict[str, Any], result: ValidationResult, depth: int = 1
    ) -> None:
        """校验嵌套节点"""
        if not isinstance(nested, dict):
            result.add_error(
                ValidationError(
                    field="nested", message="nested must be an object", severity=ErrorSeverity.ERROR
                )
            )
            return

        # 检查深度 - 当 depth >= MAX_NESTED_DEPTH 时，不允许再添加子节点
        if depth >= MAX_NESTED_DEPTH:
            if "children" in nested and nested["children"]:
                result.add_error(
                    ValidationError(
                        field="nested",
                        message=f"Nested depth exceeds maximum allowed ({MAX_NESTED_DEPTH})",
                        severity=ErrorSeverity.ERROR,
                        suggestion=f"Reduce nesting to at most {MAX_NESTED_DEPTH} levels",
                    )
                )
                return

        # 校验 children
        if "children" in nested:
            children = nested["children"]
            if not isinstance(children, list):
                result.add_error(
                    ValidationError(
                        field="nested.children",
                        message="children must be a list",
                        severity=ErrorSeverity.ERROR,
                    )
                )
                return

            for i, child in enumerate(children):
                if not isinstance(child, dict):
                    result.add_error(
                        ValidationError(
                            field=f"nested.children[{i}]",
                            message="Each child must be an object",
                            severity=ErrorSeverity.ERROR,
                        )
                    )
                    continue

                # 校验子节点必填字段
                if "name" not in child:
                    result.add_error(
                        ValidationError(
                            field=f"nested.children[{i}]",
                            message="Child node missing 'name' field",
                            severity=ErrorSeverity.ERROR,
                        )
                    )

                if "executor_type" not in child:
                    result.add_error(
                        ValidationError(
                            field=f"nested.children[{i}]",
                            message="Child node missing 'executor_type' field",
                            severity=ErrorSeverity.ERROR,
                        )
                    )
                elif child.get("executor_type") not in self.VALID_EXECUTOR_TYPES:
                    result.add_error(
                        ValidationError(
                            field=f"nested.children[{i}].executor_type",
                            message=f"Invalid executor_type: '{child.get('executor_type')}'",
                            severity=ErrorSeverity.ERROR,
                        )
                    )

                # 递归校验嵌套
                if "nested" in child:
                    self._validate_nested(child["nested"], result, depth + 1)

    def _validate_dynamic_code(
        self, dynamic_code: dict[str, Any], result: ValidationResult
    ) -> None:
        """校验动态代码"""
        if not isinstance(dynamic_code, dict):
            result.add_error(
                ValidationError(
                    field="dynamic_code",
                    message="dynamic_code must be an object",
                    severity=ErrorSeverity.ERROR,
                )
            )
            return

        # 校验各代码段的语法
        for code_field in ["pre_execute", "post_execute", "transform"]:
            if code_field in dynamic_code:
                code = dynamic_code[code_field]
                if isinstance(code, str) and code.strip():
                    self._validate_python_syntax(code, f"dynamic_code.{code_field}", result)

    def _validate_python_syntax(self, code: str, field_path: str, result: ValidationResult) -> None:
        """校验 Python 代码语法"""
        try:
            ast.parse(code)
        except SyntaxError as e:
            result.add_error(
                ValidationError(
                    field=field_path,
                    message=f"Python syntax error: {e.msg} at line {e.lineno}",
                    severity=ErrorSeverity.ERROR,
                    suggestion="Fix the Python syntax error",
                )
            )

    def _validate_tags(self, tags: list[str], result: ValidationResult) -> None:
        """校验标签"""
        if not isinstance(tags, list):
            result.add_error(
                ValidationError(
                    field="tags", message="tags must be a list", severity=ErrorSeverity.ERROR
                )
            )
            return

        for i, tag in enumerate(tags):
            if not isinstance(tag, str):
                result.add_error(
                    ValidationError(
                        field=f"tags[{i}]",
                        message="Each tag must be a string",
                        severity=ErrorSeverity.ERROR,
                    )
                )
                continue

            if not self.TAG_PATTERN.match(tag):
                result.add_error(
                    ValidationError(
                        field=f"tags[{i}]",
                        message=f"Invalid tag format: '{tag}'",
                        severity=ErrorSeverity.ERROR,
                        suggestion="Tags should be lowercase with hyphens only",
                    )
                )

    def _validate_execution(self, execution: dict[str, Any], result: ValidationResult) -> None:
        """校验执行配置"""
        if not isinstance(execution, dict):
            result.add_error(
                ValidationError(
                    field="execution",
                    message="execution must be an object",
                    severity=ErrorSeverity.ERROR,
                )
            )
            return

        # 校验 timeout_seconds
        if "timeout_seconds" in execution:
            timeout = execution["timeout_seconds"]
            if not isinstance(timeout, int | float) or timeout <= 0:
                result.add_error(
                    ValidationError(
                        field="execution.timeout_seconds",
                        message="timeout_seconds must be a positive number",
                        severity=ErrorSeverity.ERROR,
                    )
                )


# 导出
__all__ = [
    "ErrorSeverity",
    "ValidationError",
    "ValidationResult",
    "NodeYamlSchema",
    "NodeYamlValidator",
]
