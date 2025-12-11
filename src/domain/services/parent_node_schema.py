"""父节点抽象模型 Schema 与验证器

业务定义：
- 父节点是包含子节点的复合节点，支持继承机制
- 继承机制允许从模板或其他节点继承配置
- 支持 inherit_from（继承源）、inherit（继承块）、override（覆盖块）

设计原则：
- 继承优先级：override > 本地定义 > inherit_from（后者覆盖前者）
- 深合并：对象递归合并，数组去重合并（除非显式 override）
- 循环检测：DFS 检测继承链循环
- 冲突检测：严格模式下，多源同键冲突需显式 override

使用示例：
    validator = ParentNodeValidator(registry={"tpl.base": {...}})
    result = validator.validate(schema_dict)
    if result.is_valid:
        resolved = validator.resolve_inheritance("node.id")
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ============================================================================
# 异常类
# ============================================================================


class InheritanceError(Exception):
    """继承相关错误基类"""


class CyclicInheritanceError(InheritanceError):
    """循环继承错误"""


class ConflictingInheritanceError(InheritanceError):
    """继承冲突错误（多源同键且无 override）"""


class InvalidSchemaError(ValueError):
    """Schema 格式错误"""


# ============================================================================
# 验证结果
# ============================================================================


@dataclass
class ValidationError:
    """验证错误"""

    field: str
    message: str
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def add_error(self, field: str, message: str, suggestion: str | None = None) -> None:
        self.errors.append(ValidationError(field, message, suggestion))
        self.is_valid = False

    def add_warning(self, field: str, message: str) -> None:
        self.warnings.append(ValidationError(field, message))


# ============================================================================
# 父节点 Schema 数据类
# ============================================================================


@dataclass
class ParentNodeSchema:
    """父节点 Schema 数据类

    属性：
        name: 节点名称
        kind: 节点类型 (node/workflow/template)
        version: 版本号
        executor_type: 执行器类型
        inherit_from: 继承源（单个或列表）
        inherit: 继承配置块
        override: 覆盖配置块
        children: 子节点列表
        data: 原始数据字典
    """

    name: str
    kind: str
    version: str
    executor_type: str | None = None
    description: str | None = None
    inherit_from: str | list[str] | None = None
    inherit: dict[str, Any] = field(default_factory=dict)
    override: dict[str, Any] = field(default_factory=dict)
    children: list[dict[str, Any]] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParentNodeSchema:
        """从字典创建 Schema"""
        return cls(
            name=data.get("name", ""),
            kind=data.get("kind", ""),
            version=data.get("version", ""),
            executor_type=data.get("executor_type"),
            description=data.get("description"),
            inherit_from=data.get("inherit_from"),
            inherit=data.get("inherit", {}),
            override=data.get("override", {}),
            children=data.get("children", []),
            data=copy.deepcopy(data),
        )

    @classmethod
    def from_yaml(cls, path: Path | str) -> ParentNodeSchema:
        """从 YAML 文件加载 Schema"""
        path = Path(path)
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data is None:
                    data = {}
                if not isinstance(data, dict):
                    raise InvalidSchemaError(f"YAML 文件内容必须是字典: {path}")
                return cls.from_dict(data)
        except yaml.YAMLError as e:
            raise InvalidSchemaError(f"YAML 解析错误: {e}") from e

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result = copy.deepcopy(self.data)
        result["name"] = self.name
        result["kind"] = self.kind
        result["version"] = self.version
        if self.executor_type:
            result["executor_type"] = self.executor_type
        if self.description:
            result["description"] = self.description
        if self.inherit_from:
            result["inherit_from"] = self.inherit_from
        if self.inherit:
            result["inherit"] = self.inherit
        if self.override:
            result["override"] = self.override
        if self.children:
            result["children"] = self.children
        return result

    def to_yaml(self, path: Path | str) -> None:
        """保存为 YAML 文件"""
        path = Path(path)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.to_dict(), f, allow_unicode=True, sort_keys=False)


# ============================================================================
# 继承合并器
# ============================================================================


class InheritanceMerger:
    """继承合并器

    合并策略：
    - 对象：键级深合并
    - 数组：去重合并（除非 force=True 则完全覆盖）
    - 标量：后者覆盖前者

    参数：
        strict_conflict: 严格冲突检测模式
    """

    def __init__(self, strict_conflict: bool = False):
        self.strict_conflict = strict_conflict

    def merge(
        self,
        sources: list[dict[str, Any]],
        child: dict[str, Any],
        override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """合并多源继承

        参数：
            sources: 继承源列表（按顺序，后者覆盖前者）
            child: 子节点本地定义
            override: 显式覆盖配置

        返回：
            合并后的配置字典
        """
        result: dict[str, Any] = {}

        # 收集 override 覆盖的键路径（这些键不检测冲突）
        override_paths = self._collect_paths(override) if override else set()

        # Step 1: 按顺序合并所有继承源
        for source in sources:
            self._deep_merge(
                result,
                source,
                path="",
                check_conflict=self.strict_conflict,
                skip_conflict_paths=override_paths,
            )

        # Step 2: 合并子节点本地定义
        self._deep_merge(result, child, path="", check_conflict=False)

        # Step 3: 应用显式 override（强制覆盖）
        if override:
            self._deep_merge(result, override, path="", force=True, check_conflict=False)

        return result

    def _collect_paths(self, data: dict[str, Any], prefix: str = "") -> set[str]:
        """收集字典中所有键的路径"""
        paths: set[str] = set()
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            paths.add(path)
            if isinstance(value, dict):
                paths.update(self._collect_paths(value, path))
        return paths

    def _deep_merge(
        self,
        base: dict[str, Any],
        incoming: dict[str, Any],
        path: str = "",
        force: bool = False,
        check_conflict: bool = False,
        skip_conflict_paths: set[str] | None = None,
    ) -> None:
        """深合并字典

        参数：
            base: 基础字典（会被修改）
            incoming: 传入字典
            path: 当前路径（用于错误消息）
            force: 强制覆盖模式（数组完全覆盖）
            check_conflict: 是否检测冲突
            skip_conflict_paths: 跳过冲突检测的路径集合
        """
        skip_conflict_paths = skip_conflict_paths or set()

        for key, value in incoming.items():
            current_path = f"{path}.{key}" if path else key

            if key not in base:
                base[key] = copy.deepcopy(value)
                continue

            existing = base[key]

            # 检查是否跳过此路径的冲突检测
            should_check = check_conflict and current_path not in skip_conflict_paths

            # 对象深合并
            if isinstance(existing, dict) and isinstance(value, dict):
                self._deep_merge(
                    existing, value, current_path, force, check_conflict, skip_conflict_paths
                )

            # 数组合并
            elif isinstance(existing, list) and isinstance(value, list):
                if force:
                    # 强制覆盖数组
                    base[key] = copy.deepcopy(value)
                else:
                    # 去重合并
                    merged = list(existing)
                    for item in value:
                        if item not in merged:
                            merged.append(item)
                    base[key] = merged

            # 标量覆盖
            else:
                if should_check and existing != value:
                    raise ConflictingInheritanceError(
                        f"继承冲突 at '{current_path}': {existing!r} vs {value!r}"
                    )
                base[key] = copy.deepcopy(value)


# ============================================================================
# 父节点验证器
# ============================================================================


# 有效的 kind 枚举
VALID_KINDS = {"node", "workflow", "template"}

# 有效的 executor_type 枚举
VALID_EXECUTOR_TYPES = {
    "python",
    "llm",
    "http",
    "database",
    "container",
    "condition",
    "loop",
    "parallel",
    "sequential",
    "api",
}

# 有效的参数类型
VALID_PARAM_TYPES = {"string", "number", "integer", "boolean", "array", "object"}

# 有效的 on_failure 枚举
VALID_ON_FAILURE = {"retry", "skip", "abort", "replan", "fallback"}

# 允许的 inherit/override 块字段
ALLOWED_INHERIT_FIELDS = {
    "parameters",
    "returns",
    "error_strategy",
    "resources",
    "tags",
    "execution",
}

# 资源格式正则
CPU_PATTERN = re.compile(r"^(\d+(\.\d+)?)(m)?$")
MEMORY_PATTERN = re.compile(r"^(\d+(\.\d+)?)(k|m|g|t|p|e|ki|mi|gi|ti|pi|ei)?$", re.IGNORECASE)


class ParentNodeValidator:
    """父节点 Schema 验证器

    职责：
    - 基础字段验证（kind/name/version/executor_type）
    - inherit_from 语法验证
    - inherit/override 块验证
    - 循环继承检测
    - 冲突检测
    - 引用解析

    参数：
        registry: 节点/模板注册表（id -> schema dict）
        max_depth: 最大继承深度
    """

    def __init__(
        self,
        registry: dict[str, dict[str, Any]] | None = None,
        max_depth: int = 10,
    ):
        self.registry = registry or {}
        self.max_depth = max_depth

    def validate(self, schema: dict[str, Any]) -> ValidationResult:
        """验证 Schema

        参数：
            schema: Schema 字典

        返回：
            ValidationResult 验证结果
        """
        result = ValidationResult(is_valid=True)

        # 基础字段验证
        self._validate_required_fields(schema, result)
        self._validate_kind(schema, result)
        self._validate_name(schema, result)
        self._validate_version(schema, result)
        self._validate_executor_type(schema, result)

        # inherit_from 验证
        self._validate_inherit_from(schema, result)

        # inherit 块验证
        self._validate_inherit_block(schema, result)

        # override 块验证
        self._validate_override_block(schema, result)

        # children 验证
        self._validate_children(schema, result)

        # 并行工作流必须有 children
        self._validate_parallel_requires_children(schema, result)

        return result

    def resolve_reference(self, ref: str) -> dict[str, Any]:
        """解析引用

        参数：
            ref: 引用 ID

        返回：
            引用的 Schema 字典

        异常：
            InvalidSchemaError: 引用不存在
        """
        if ref not in self.registry:
            raise InvalidSchemaError(f"引用不存在: {ref}")
        return copy.deepcopy(self.registry[ref])

    def resolve_inheritance(
        self,
        node_id: str,
        visited: set[str] | None = None,
        depth: int = 0,
    ) -> dict[str, Any]:
        """解析继承链

        参数：
            node_id: 节点 ID
            visited: 已访问节点集合（用于循环检测）
            depth: 当前深度

        返回：
            解析后的完整 Schema

        异常：
            CyclicInheritanceError: 检测到循环继承
            InheritanceError: 继承深度超限
        """
        if visited is None:
            visited = set()

        # 循环检测
        if node_id in visited:
            chain = " -> ".join(list(visited) + [node_id])
            raise CyclicInheritanceError(f"检测到循环继承: {chain}")

        # 深度检测
        if depth > self.max_depth:
            raise InheritanceError(f"继承深度超限 (max={self.max_depth}): depth={depth}")

        visited.add(node_id)

        # 获取当前节点 schema
        schema = self.resolve_reference(node_id)
        inherit_from = schema.get("inherit_from")

        if not inherit_from:
            return schema

        # 标准化 inherit_from 为列表
        if isinstance(inherit_from, str):
            inherit_from = [inherit_from]

        # 递归解析所有父节点
        merger = InheritanceMerger(strict_conflict=False)
        parent_schemas: list[dict[str, Any]] = []

        for parent_id in inherit_from:
            parent_schema = self.resolve_inheritance(parent_id, visited.copy(), depth + 1)
            parent_schemas.append(parent_schema)

        # 合并继承
        child_local = {
            k: v for k, v in schema.items() if k not in ("inherit_from", "inherit", "override")
        }
        child_inherit = schema.get("inherit", {})
        child_override = schema.get("override", {})

        # 先合并 inherit 块到 child_local
        if child_inherit:
            merger._deep_merge(child_local, child_inherit, path="inherit", force=False)

        # 合并所有源
        result = merger.merge(parent_schemas, child_local, child_override)

        # 移除继承标记
        result.pop("inherit_from", None)
        result.pop("inherit", None)
        result.pop("override", None)

        return result

    # ========================================================================
    # 私有验证方法
    # ========================================================================

    def _validate_required_fields(self, schema: dict[str, Any], result: ValidationResult) -> None:
        """验证必填字段"""
        if "kind" not in schema:
            result.add_error("kind", "缺少必填字段 'kind'")
        if "name" not in schema:
            result.add_error("name", "缺少必填字段 'name'")
        if "version" not in schema:
            result.add_error("version", "缺少必填字段 'version'")

    def _validate_kind(self, schema: dict[str, Any], result: ValidationResult) -> None:
        """验证 kind 字段"""
        kind = schema.get("kind")
        if kind is not None and kind not in VALID_KINDS:
            result.add_error("kind", f"无效的 kind 值: {kind!r}，允许值: {VALID_KINDS}")

    def _validate_name(self, schema: dict[str, Any], result: ValidationResult) -> None:
        """验证 name 字段"""
        name = schema.get("name")
        if name is not None and (not isinstance(name, str) or not name.strip()):
            result.add_error("name", "name 必须是非空字符串")

    def _validate_version(self, schema: dict[str, Any], result: ValidationResult) -> None:
        """验证 version 字段"""
        version = schema.get("version")
        if version is not None and not isinstance(version, str):
            result.add_error("version", "version 必须是字符串")

    def _validate_executor_type(self, schema: dict[str, Any], result: ValidationResult) -> None:
        """验证 executor_type 字段"""
        executor_type = schema.get("executor_type")
        if executor_type is not None and executor_type not in VALID_EXECUTOR_TYPES:
            result.add_error(
                "executor_type",
                f"无效的 executor_type: {executor_type!r}，允许值: {VALID_EXECUTOR_TYPES}",
            )

    def _validate_inherit_from(self, schema: dict[str, Any], result: ValidationResult) -> None:
        """验证 inherit_from 字段"""
        inherit_from = schema.get("inherit_from")
        if inherit_from is None:
            return

        # 类型检查
        if isinstance(inherit_from, str):
            if not inherit_from.strip():
                result.add_error("inherit_from", "inherit_from 不能为空字符串")
        elif isinstance(inherit_from, list):
            for i, item in enumerate(inherit_from):
                if not isinstance(item, str) or not item.strip():
                    result.add_error(f"inherit_from[{i}]", "inherit_from 列表元素必须是非空字符串")
        else:
            result.add_error(
                "inherit_from",
                f"inherit_from 必须是字符串或字符串列表，收到: {type(inherit_from).__name__}",
            )

    def _validate_inherit_block(self, schema: dict[str, Any], result: ValidationResult) -> None:
        """验证 inherit 块"""
        inherit = schema.get("inherit")
        if inherit is None:
            return

        if not isinstance(inherit, dict):
            result.add_error("inherit", "inherit 必须是对象")
            return

        # 检查未知字段
        for key in inherit:
            if key not in ALLOWED_INHERIT_FIELDS:
                result.add_error(f"inherit.{key}", f"inherit 块包含未知字段: {key!r}")

        # 验证 parameters
        self._validate_parameters(inherit.get("parameters"), "inherit.parameters", result)

        # 验证 error_strategy
        self._validate_error_strategy(
            inherit.get("error_strategy"), "inherit.error_strategy", result
        )

        # 验证 resources
        self._validate_resources(inherit.get("resources"), "inherit.resources", result)

    def _validate_override_block(self, schema: dict[str, Any], result: ValidationResult) -> None:
        """验证 override 块"""
        override = schema.get("override")
        if override is None:
            return

        if not isinstance(override, dict):
            result.add_error("override", "override 必须是对象")
            return

        # 验证 resources
        self._validate_resources(override.get("resources"), "override.resources", result)

    def _validate_parameters(
        self,
        parameters: Any,
        path: str,
        result: ValidationResult,
    ) -> None:
        """验证 parameters 定义"""
        if parameters is None:
            return

        if not isinstance(parameters, dict):
            result.add_error(path, "parameters 必须是对象")
            return

        for param_name, param_def in parameters.items():
            param_path = f"{path}.{param_name}"

            if not isinstance(param_def, dict):
                result.add_error(param_path, "参数定义必须是对象")
                continue

            # 检查 type 必填
            param_type = param_def.get("type")
            if param_type is None:
                result.add_error(f"{param_path}.type", "参数缺少必填字段 'type'")
            elif param_type not in VALID_PARAM_TYPES:
                result.add_error(f"{param_path}.type", f"无效的参数类型: {param_type!r}")

            # 检查 default 类型匹配
            default = param_def.get("default")
            if default is not None and param_type is not None:
                if not self._check_type_match(default, param_type):
                    result.add_error(
                        f"{param_path}.default", f"default 值类型与 type '{param_type}' 不匹配"
                    )

    def _validate_error_strategy(
        self,
        error_strategy: Any,
        path: str,
        result: ValidationResult,
    ) -> None:
        """验证 error_strategy"""
        if error_strategy is None:
            return

        if not isinstance(error_strategy, dict):
            result.add_error(path, "error_strategy 必须是对象")
            return

        # 验证 retry
        retry = error_strategy.get("retry")
        if retry is not None:
            if not isinstance(retry, dict):
                result.add_error(f"{path}.retry", "retry 必须是对象")
            else:
                max_attempts = retry.get("max_attempts")
                if max_attempts is not None:
                    if not isinstance(max_attempts, int) or max_attempts < 0:
                        result.add_error(
                            f"{path}.retry.max_attempts", "max_attempts 必须是非负整数"
                        )

        # 验证 on_failure
        on_failure = error_strategy.get("on_failure")
        if on_failure is not None and on_failure not in VALID_ON_FAILURE:
            result.add_error(f"{path}.on_failure", f"无效的 on_failure 值: {on_failure!r}")

    def _validate_resources(
        self,
        resources: Any,
        path: str,
        result: ValidationResult,
    ) -> None:
        """验证 resources"""
        if resources is None:
            return

        if not isinstance(resources, dict):
            result.add_error(path, "resources 必须是对象")
            return

        # 验证 cpu
        cpu = resources.get("cpu")
        if cpu is not None:
            if not self._is_valid_cpu(cpu):
                result.add_error(f"{path}.cpu", f"无效的 cpu 格式: {cpu!r}")

        # 验证 memory
        memory = resources.get("memory")
        if memory is not None:
            if not self._is_valid_memory(memory):
                result.add_error(f"{path}.memory", f"无效的 memory 格式: {memory!r}")

    def _validate_children(self, schema: dict[str, Any], result: ValidationResult) -> None:
        """验证 children 子节点列表"""
        children = schema.get("children")
        if children is None:
            return

        if not isinstance(children, list):
            result.add_error("children", "children 必须是数组")
            return

        aliases: set[str] = set()
        for i, child in enumerate(children):
            child_path = f"children[{i}]"

            if not isinstance(child, dict):
                result.add_error(child_path, "子节点必须是对象")
                continue

            # ref 必填
            ref = child.get("ref")
            if ref is None:
                result.add_error(f"{child_path}.ref", "子节点缺少必填字段 'ref'")

            # alias 唯一性检查
            alias = child.get("alias")
            if alias is not None:
                if alias in aliases:
                    result.add_error(f"{child_path}.alias", f"子节点 alias 重复: {alias!r}")
                else:
                    aliases.add(alias)

            # 验证子节点 override
            child_override = child.get("override")
            if child_override is not None:
                self._validate_resources(
                    child_override.get("resources"),
                    f"{child_path}.override.resources",
                    result,
                )

    def _validate_parallel_requires_children(
        self,
        schema: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """验证并行工作流必须有 children"""
        nested = schema.get("nested", {})
        if not isinstance(nested, dict):
            return

        is_parallel = nested.get("parallel", False)
        children = schema.get("children")

        if is_parallel and (children is None or len(children) == 0):
            result.add_error("children", "并行工作流 (nested.parallel=true) 必须定义 children")

    def _is_valid_cpu(self, value: Any) -> bool:
        """检查 cpu 格式是否有效"""
        if isinstance(value, (int, float)):
            return value >= 0
        if isinstance(value, str):
            return bool(CPU_PATTERN.match(value.strip()))
        return False

    def _is_valid_memory(self, value: Any) -> bool:
        """检查 memory 格式是否有效"""
        if isinstance(value, (int, float)):
            return value >= 0
        if isinstance(value, str):
            return bool(MEMORY_PATTERN.match(value.strip()))
        return False

    def _check_type_match(self, value: Any, expected_type: str) -> bool:
        """检查值是否与预期类型匹配"""
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict),
        }
        check = type_checks.get(expected_type)
        if check is None:
            return True  # 未知类型不做检查
        return check(value)
