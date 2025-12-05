"""
自描述节点验证器与结果语义化解析器

职责：
1. SelfDescribingNodeValidator - 验证自描述节点定义
   - 必需字段验证
   - 输入输出对齐验证
   - 沙箱许可验证
2. ResultSemanticParser - 解析 WorkflowAgent 返回结果
3. register_self_describing_rules - 注册 Coordinator 验证规则
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.agents.coordinator_agent import CoordinatorAgent

logger = logging.getLogger(__name__)


# ==================== 验证结果数据类 ====================


@dataclass
class NodeValidationResult:
    """节点验证结果"""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: NodeValidationResult) -> NodeValidationResult:
        """合并两个验证结果"""
        return NodeValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )


# ==================== 语义化结果数据类 ====================


@dataclass
class SemanticResult:
    """语义化执行结果

    将 WorkflowAgent 的原始返回结果转换为标准化的语义结构，
    便于系统其他模块理解和消费。
    """

    status: str  # success, failure, partial, timeout
    data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    execution_time_ms: float | None = None
    children_status: dict[str, str] = field(default_factory=dict)
    aggregated_data: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = {
            "status": self.status,
            "data": self.data,
        }
        if self.error_message:
            result["error_message"] = self.error_message
        if self.execution_time_ms is not None:
            result["execution_time_ms"] = self.execution_time_ms
        if self.children_status:
            result["children_status"] = self.children_status
        if self.aggregated_data:
            result["aggregated_data"] = self.aggregated_data
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    def get_summary(self) -> str:
        """生成人类可读摘要"""
        parts = []

        # 状态描述
        status_map = {
            "success": "执行成功",
            "failure": "执行失败",
            "partial": "部分成功",
            "timeout": "执行超时",
        }
        parts.append(status_map.get(self.status, f"状态: {self.status}"))

        # 执行时间
        if self.execution_time_ms is not None:
            if self.execution_time_ms < 1000:
                parts.append(f"耗时 {self.execution_time_ms:.1f}ms")
            else:
                parts.append(f"耗时 {self.execution_time_ms / 1000:.2f}s")

        # 子节点状态
        if self.children_status:
            success_count = sum(1 for s in self.children_status.values() if s == "success")
            total_count = len(self.children_status)
            parts.append(f"子节点 {success_count}/{total_count} 成功")

        # 错误信息
        if self.error_message:
            parts.append(f"错误: {self.error_message[:50]}")

        return " | ".join(parts)


# ==================== 验证器常量 ====================


# 有效的执行器类型
VALID_EXECUTOR_TYPES = {
    "code",
    "llm",
    "http",
    "database",
    "parallel",
    "sequential",
    "transform",
}

# 不需要沙箱的执行器类型
NON_SANDBOX_EXECUTOR_TYPES = {"llm", "http", "database"}

# 危险的导入模块
DANGEROUS_IMPORTS = {
    "os",
    "subprocess",
    "sys",
    "shutil",
    "socket",
    "requests",
    "urllib",
    "ftplib",
    "telnetlib",
    "pickle",
    "marshal",
    "builtins",
    "__builtins__",
}

# 安全的导入模块
SAFE_IMPORTS = {
    "json",
    "math",
    "datetime",
    "re",
    "collections",
    "itertools",
    "functools",
    "operator",
    "typing",
    "dataclasses",
    "enum",
    "decimal",
    "fractions",
    "random",
    "statistics",
    "copy",
    "pprint",
    "textwrap",
    "string",
    "base64",
    "hashlib",
    "hmac",
    "uuid",
}

# Python 类型映射
TYPE_VALIDATORS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "any": lambda v: True,
}


# ==================== 自描述节点验证器 ====================


class SelfDescribingNodeValidator:
    """自描述节点验证器

    提供三类验证：
    1. 必需字段验证 - 确保节点定义包含所有必需字段
    2. 输入输出对齐验证 - 确保输入符合参数定义，输出符合模式
    3. 沙箱许可验证 - 确保代码节点在安全沙箱中执行
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ==================== 必需字段验证 ====================

    def validate_required_fields(self, node_def: dict[str, Any] | None) -> NodeValidationResult:
        """验证必需字段

        必需字段：
        - name: 节点名称
        - executor_type: 执行器类型（必须是有效类型）

        参数：
            node_def: 节点定义字典

        返回：
            验证结果
        """
        errors: list[str] = []

        # 处理 None 或空定义
        if node_def is None:
            return NodeValidationResult(is_valid=False, errors=["节点定义不能为 None"])

        if not isinstance(node_def, dict):
            return NodeValidationResult(is_valid=False, errors=["节点定义必须是字典类型"])

        if not node_def:
            return NodeValidationResult(is_valid=False, errors=["节点定义不能为空"])

        # 验证 name 字段
        if "name" not in node_def:
            errors.append("缺少必需字段: name")
        elif not isinstance(node_def["name"], str) or not node_def["name"].strip():
            errors.append("name 字段必须是非空字符串")

        # 验证 executor_type 字段
        if "executor_type" not in node_def:
            errors.append("缺少必需字段: executor_type")
        else:
            executor_type = node_def["executor_type"]
            if executor_type not in VALID_EXECUTOR_TYPES:
                errors.append(
                    f"无效的 executor_type: {executor_type}, "
                    f"有效值: {', '.join(sorted(VALID_EXECUTOR_TYPES))}"
                )

        # 验证 parameters 字段格式
        if "parameters" in node_def:
            params = node_def["parameters"]
            if not isinstance(params, list):
                errors.append("parameters 字段必须是列表类型")
            else:
                for i, param in enumerate(params):
                    if not isinstance(param, dict):
                        errors.append(f"parameters[{i}] 必须是字典类型")
                    elif "name" not in param:
                        errors.append(f"parameters[{i}] 缺少 name 字段")

        # 验证嵌套子节点
        if "nested" in node_def:
            nested = node_def["nested"]
            if isinstance(nested, dict) and "children" in nested:
                children = nested["children"]
                if isinstance(children, list):
                    for i, child in enumerate(children):
                        if isinstance(child, dict) and "name" not in child:
                            errors.append(f"nested.children[{i}] 缺少 name 字段")

        return NodeValidationResult(is_valid=len(errors) == 0, errors=errors)

    # ==================== 输入输出对齐验证 ====================

    def validate_input_alignment(
        self,
        node_def: dict[str, Any],
        inputs: dict[str, Any],
    ) -> NodeValidationResult:
        """验证输入与参数定义对齐

        检查：
        1. 必需参数是否提供
        2. 参数类型是否匹配

        参数：
            node_def: 节点定义
            inputs: 实际输入

        返回：
            验证结果
        """
        errors: list[str] = []
        warnings: list[str] = []

        parameters = node_def.get("parameters", [])
        if not isinstance(parameters, list):
            return NodeValidationResult(is_valid=True)  # 无参数定义，跳过验证

        for param in parameters:
            if not isinstance(param, dict):
                continue

            param_name = param.get("name")
            if not param_name:
                continue

            param_type = param.get("type", "any")
            is_required = param.get("required", False)
            default_value = param.get("default")

            # 检查必需参数
            if is_required and param_name not in inputs:
                if default_value is None:
                    errors.append(f"缺少必需参数: {param_name}")
                continue

            # 检查类型
            if param_name in inputs:
                value = inputs[param_name]
                validator = TYPE_VALIDATORS.get(param_type)

                if validator and not validator(value):
                    errors.append(
                        f"参数 {param_name} 类型错误: 期望 {param_type}, "
                        f"实际 {type(value).__name__}"
                    )

        return NodeValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    def validate_output_alignment(
        self,
        node_def: dict[str, Any],
        output: dict[str, Any],
    ) -> NodeValidationResult:
        """验证输出与模式定义对齐

        参数：
            node_def: 节点定义
            output: 实际输出

        返回：
            验证结果
        """
        errors: list[str] = []

        output_schema = node_def.get("output_schema")
        if not output_schema:
            return NodeValidationResult(is_valid=True)  # 无输出模式，跳过验证

        # 检查必需字段
        required_fields = output_schema.get("required", [])
        for field_name in required_fields:
            if field_name not in output:
                errors.append(f"输出缺少必需字段: {field_name}")

        return NodeValidationResult(is_valid=len(errors) == 0, errors=errors)

    # ==================== 沙箱许可验证 ====================

    def validate_sandbox_permission(
        self,
        node_def: dict[str, Any],
        require_sandbox: bool = False,
    ) -> NodeValidationResult:
        """验证沙箱许可

        检查：
        1. 代码节点是否启用沙箱（如果 require_sandbox=True）
        2. 是否包含危险导入

        参数：
            node_def: 节点定义
            require_sandbox: 是否强制要求沙箱

        返回：
            验证结果
        """
        errors: list[str] = []
        warnings: list[str] = []

        executor_type = node_def.get("executor_type", "")

        # 非代码节点不需要沙箱验证
        if executor_type in NON_SANDBOX_EXECUTOR_TYPES:
            return NodeValidationResult(is_valid=True)

        execution = node_def.get("execution", {})
        sandbox_enabled = execution.get("sandbox", False)

        # 检查沙箱是否启用
        if require_sandbox and not sandbox_enabled:
            errors.append(
                f"代码节点 '{node_def.get('name', 'unknown')}' "
                "必须启用沙箱执行 (execution.sandbox: true)"
            )

        # 检查危险导入
        allowed_imports = execution.get("allowed_imports", [])
        if isinstance(allowed_imports, list):
            dangerous_found = set(allowed_imports) & DANGEROUS_IMPORTS
            if dangerous_found:
                errors.append(
                    f"包含危险导入模块: {', '.join(sorted(dangerous_found))}. "
                    "这些模块可能导致安全风险。"
                )

        return NodeValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # ==================== 完整验证与日志 ====================

    def validate_all(
        self,
        node_def: dict[str, Any] | None,
        inputs: dict[str, Any] | None = None,
        require_sandbox: bool = False,
    ) -> NodeValidationResult:
        """执行完整验证

        依次执行：
        1. 必需字段验证
        2. 输入对齐验证（如果提供了 inputs）
        3. 沙箱许可验证

        参数：
            node_def: 节点定义
            inputs: 实际输入（可选）
            require_sandbox: 是否强制要求沙箱

        返回：
            合并的验证结果
        """
        # 必需字段验证
        result = self.validate_required_fields(node_def)

        # 如果基本验证失败，直接返回
        if not result.is_valid or node_def is None:
            return result

        # 输入对齐验证
        if inputs is not None:
            input_result = self.validate_input_alignment(node_def, inputs)
            result = result.merge(input_result)

        # 沙箱许可验证
        sandbox_result = self.validate_sandbox_permission(node_def, require_sandbox)
        result = result.merge(sandbox_result)

        return result

    def validate_with_logging(
        self,
        node_def: dict[str, Any] | None,
        inputs: dict[str, Any] | None = None,
        require_sandbox: bool = False,
    ) -> NodeValidationResult:
        """执行验证并记录审批日志

        参数：
            node_def: 节点定义
            inputs: 实际输入（可选）
            require_sandbox: 是否强制要求沙箱

        返回：
            验证结果
        """
        node_name = node_def.get("name", "unknown") if isinstance(node_def, dict) else "unknown"

        self._logger.info(f"开始验证节点: {node_name}")

        result = self.validate_all(node_def, inputs, require_sandbox)

        if result.is_valid:
            self._logger.info(
                f"节点 '{node_name}' 验证通过 (approved) | " f"warnings: {len(result.warnings)}"
            )
        else:
            self._logger.warning(
                f"节点 '{node_name}' 验证拒绝 (rejected) | " f"errors: {result.errors}"
            )

        # 记录详细信息
        for warning in result.warnings:
            self._logger.warning(f"  警告: {warning}")

        for error in result.errors:
            self._logger.error(f"  错误: {error}")

        return result


# ==================== 结果语义化解析器 ====================


class ResultSemanticParser:
    """结果语义化解析器

    将 WorkflowAgent 的原始返回结果转换为标准化的语义结构。
    """

    def parse(self, raw_result: dict[str, Any]) -> SemanticResult:
        """解析原始结果为语义化结果

        参数：
            raw_result: WorkflowAgent 返回的原始结果

        返回：
            语义化结果
        """
        # 确定状态
        status = self._determine_status(raw_result)

        # 提取数据
        data = raw_result.get("output", {})
        if not isinstance(data, dict):
            data = {"value": data}

        # 提取错误信息
        error_message = raw_result.get("error")

        # 提取执行时间
        execution_time_ms = raw_result.get("execution_time_ms")

        # 处理子节点结果
        children_status = {}
        children_results = raw_result.get("children_results", {})
        if isinstance(children_results, dict):
            for child_name, child_result in children_results.items():
                if isinstance(child_result, dict):
                    if child_result.get("success", False):
                        children_status[child_name] = "success"
                    else:
                        children_status[child_name] = "failure"

        # 提取聚合数据
        aggregated_data = raw_result.get("aggregated_output")

        return SemanticResult(
            status=status,
            data=data,
            error_message=error_message,
            execution_time_ms=execution_time_ms,
            children_status=children_status,
            aggregated_data=aggregated_data,
        )

    def _determine_status(self, raw_result: dict[str, Any]) -> str:
        """确定执行状态"""
        success = raw_result.get("success", False)
        children_results = raw_result.get("children_results", {})

        # 检查是否超时
        if raw_result.get("timed_out", False):
            return "timeout"

        # 检查子节点部分成功
        if children_results:
            child_successes = [
                r.get("success", False) for r in children_results.values() if isinstance(r, dict)
            ]
            if child_successes:
                if all(child_successes):
                    return "success"
                elif any(child_successes):
                    return "partial"
                else:
                    return "failure"

        # 简单成功/失败
        return "success" if success else "failure"


# ==================== Coordinator 规则注册 ====================


def register_self_describing_rules(coordinator: CoordinatorAgent) -> None:
    """注册自描述节点验证规则到 Coordinator

    注册的规则：
    1. self_describing_required_fields - 必需字段验证
    2. self_describing_sandbox_permission - 沙箱许可验证

    参数：
        coordinator: CoordinatorAgent 实例
    """
    from src.domain.agents.coordinator_agent import Rule

    validator = SelfDescribingNodeValidator()

    # 规则 1: 必需字段验证
    def check_required_fields(decision: dict[str, Any]) -> bool:
        """检查自描述节点必需字段"""
        if decision.get("action") != "execute_self_describing_node":
            return True  # 不是自描述节点决策，跳过

        node_def = decision.get("node_definition")
        if not node_def:
            return False

        result = validator.validate_required_fields(node_def)
        return result.is_valid

    def get_required_fields_error(decision: dict[str, Any]) -> str:
        """获取必需字段验证错误信息"""
        node_def = decision.get("node_definition", {})
        result = validator.validate_required_fields(node_def)
        return "; ".join(result.errors) if result.errors else "节点定义验证失败"

    coordinator.add_rule(
        Rule(
            id="self_describing_required_fields",
            name="自描述节点必需字段验证",
            description="验证自描述节点定义包含所有必需字段",
            condition=check_required_fields,
            priority=5,
            error_message=get_required_fields_error,
        )
    )

    # 规则 2: 沙箱许可验证
    def check_sandbox_permission(decision: dict[str, Any]) -> bool:
        """检查自描述节点沙箱许可"""
        if decision.get("action") != "execute_self_describing_node":
            return True

        node_def = decision.get("node_definition")
        if not node_def:
            return True  # 由 required_fields 规则处理

        # 代码节点需要验证沙箱
        executor_type = node_def.get("executor_type", "")
        if executor_type in NON_SANDBOX_EXECUTOR_TYPES:
            return True

        result = validator.validate_sandbox_permission(node_def)
        return result.is_valid

    def get_sandbox_error(decision: dict[str, Any]) -> str:
        """获取沙箱验证错误信息"""
        node_def = decision.get("node_definition", {})
        result = validator.validate_sandbox_permission(node_def)
        return "; ".join(result.errors) if result.errors else "沙箱许可验证失败"

    coordinator.add_rule(
        Rule(
            id="self_describing_sandbox_permission",
            name="自描述节点沙箱许可验证",
            description="验证代码节点不包含危险导入",
            condition=check_sandbox_permission,
            priority=6,
            error_message=get_sandbox_error,
        )
    )

    logger.info("已注册自描述节点验证规则: required_fields, sandbox_permission")
