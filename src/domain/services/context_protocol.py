"""
上下文打包/解包协议

该模块实现父子 Agent 之间的上下文传递协议：
1. ContextPackage - 上下文包数据结构
2. ContextPacker - 父 Agent 打包器
3. ContextUnpacker - 子 Agent 解包器
4. ContextCompressor - 压缩策略，避免信息过载
5. ContextSchemaValidator - Schema 验证器
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# ============================================================================
# 异常类
# ============================================================================


class ContextValidationError(Exception):
    """上下文验证错误"""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


# ============================================================================
# 枚举类型
# ============================================================================


class CompressionStrategy(str, Enum):
    """压缩策略"""

    NONE = "none"  # 不压缩
    TRUNCATE = "truncate"  # 截断
    PRIORITY = "priority"  # 优先级筛选
    SUMMARIZE = "summarize"  # 摘要（需要 LLM）


# ============================================================================
# 数据结构
# ============================================================================


@dataclass
class ContextPackage:
    """
    上下文包数据结构

    用于父子 Agent 之间传递任务上下文。

    Attributes:
        package_id: 包唯一标识符
        task_description: 任务描述
        prompt_version: 提示词版本
        constraints: 约束条件列表
        relevant_knowledge: 相关知识
        input_data: 输入数据
        parent_agent_id: 父 Agent ID
        target_agent_id: 目标子 Agent ID
        priority: 优先级 (0-10, 0 最低)
        max_tokens: 最大 Token 数限制
        short_term_context: 短期上下文（最近对话）
        mid_term_context: 中期上下文（会话摘要）
        long_term_references: 长期知识引用
        created_at: 创建时间
        metadata: 其他元数据
    """

    package_id: str
    task_description: str
    prompt_version: str = "1.0.0"
    constraints: list[str] = field(default_factory=list)
    relevant_knowledge: dict[str, Any] = field(default_factory=dict)
    input_data: dict[str, Any] = field(default_factory=dict)
    parent_agent_id: str | None = None
    target_agent_id: str | None = None
    priority: int = 0
    max_tokens: int | None = None
    short_term_context: list[str] = field(default_factory=list)
    mid_term_context: dict[str, Any] = field(default_factory=dict)
    long_term_references: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "package_id": self.package_id,
            "task_description": self.task_description,
            "prompt_version": self.prompt_version,
            "constraints": self.constraints,
            "relevant_knowledge": self.relevant_knowledge,
            "input_data": self.input_data,
            "parent_agent_id": self.parent_agent_id,
            "target_agent_id": self.target_agent_id,
            "priority": self.priority,
            "max_tokens": self.max_tokens,
            "short_term_context": self.short_term_context,
            "mid_term_context": self.mid_term_context,
            "long_term_references": self.long_term_references,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextPackage:
        """从字典创建实例"""
        return cls(
            package_id=data["package_id"],
            task_description=data["task_description"],
            prompt_version=data.get("prompt_version", "1.0.0"),
            constraints=data.get("constraints", []),
            relevant_knowledge=data.get("relevant_knowledge", {}),
            input_data=data.get("input_data", {}),
            parent_agent_id=data.get("parent_agent_id"),
            target_agent_id=data.get("target_agent_id"),
            priority=data.get("priority", 0),
            max_tokens=data.get("max_tokens"),
            short_term_context=data.get("short_term_context", []),
            mid_term_context=data.get("mid_term_context", {}),
            long_term_references=data.get("long_term_references", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> ContextPackage:
        """从 JSON 字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class UnpackedContext:
    """
    解包后的上下文

    提供给子 Agent 使用的简化视图。
    """

    task_description: str
    constraints: list[str]
    knowledge: dict[str, Any]
    input_data: dict[str, Any]
    short_term: list[str]
    mid_term: dict[str, Any]
    source_agent: str | None
    prompt_version: str
    priority: int
    metadata: dict[str, Any]


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class CompressionReport:
    """压缩报告"""

    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    truncated_fields: list[str]
    strategy_used: str


# ============================================================================
# Schema 验证
# ============================================================================

REQUIRED_FIELDS = ["package_id", "task_description"]
OPTIONAL_FIELDS = [
    "prompt_version",
    "constraints",
    "relevant_knowledge",
    "input_data",
    "parent_agent_id",
    "target_agent_id",
    "priority",
    "max_tokens",
    "short_term_context",
    "mid_term_context",
    "long_term_references",
    "created_at",
    "metadata",
]

FIELD_TYPES = {
    "package_id": str,
    "task_description": str,
    "prompt_version": str,
    "constraints": list,
    "relevant_knowledge": dict,
    "input_data": dict,
    "parent_agent_id": (str, type(None)),
    "target_agent_id": (str, type(None)),
    "priority": int,
    "max_tokens": (int, type(None)),
    "short_term_context": list,
    "mid_term_context": dict,
    "long_term_references": list,
    "created_at": str,
    "metadata": dict,
}


def validate_package(package: ContextPackage) -> tuple[bool, list[str]]:
    """
    验证上下文包

    Args:
        package: 待验证的上下文包

    Returns:
        (is_valid, errors) 元组
    """
    errors = []

    # 检查必需字段
    if not package.package_id:
        errors.append("package_id 不能为空")
    if not package.task_description:
        errors.append("task_description 不能为空")

    # 检查优先级范围
    if package.priority < 0 or package.priority > 10:
        errors.append("priority 必须在 0-10 之间")

    # 检查 max_tokens
    if package.max_tokens is not None and package.max_tokens <= 0:
        errors.append("max_tokens 必须大于 0")

    return len(errors) == 0, errors


class ContextSchemaValidator:
    """上下文 Schema 验证器"""

    def __init__(self):
        """初始化验证器"""
        self.required_fields = REQUIRED_FIELDS
        self.field_types = FIELD_TYPES

    def validate(self, data: dict[str, Any], schema_version: str = "1.0") -> ValidationResult:
        """
        验证数据是否符合 Schema

        Args:
            data: 待验证的字典数据
            schema_version: Schema 版本

        Returns:
            ValidationResult 实例
        """
        errors = []

        # 检查必需字段
        for field_name in self.required_fields:
            if field_name not in data:
                errors.append(f"缺少必需字段: {field_name}")
            elif not data[field_name]:
                errors.append(f"字段 {field_name} 不能为空")

        # 检查字段类型
        for field_name, expected_type in self.field_types.items():
            if field_name in data and data[field_name] is not None:
                if not isinstance(data[field_name], expected_type):
                    errors.append(
                        f"字段 {field_name} 类型错误: "
                        f"期望 {expected_type}, 实际 {type(data[field_name])}"
                    )

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)


# ============================================================================
# 打包器
# ============================================================================


class ContextPacker:
    """
    上下文打包器

    父 Agent 用于创建上下文包。
    """

    def __init__(
        self,
        agent_id: str | None = None,
        default_prompt_version: str = "1.0.0",
    ):
        """
        初始化打包器

        Args:
            agent_id: 当前 Agent ID
            default_prompt_version: 默认提示词版本
        """
        self.agent_id = agent_id
        self.default_prompt_version = default_prompt_version

    def _generate_package_id(self) -> str:
        """生成唯一包 ID"""
        return f"ctx_{uuid.uuid4().hex[:12]}"

    def pack(
        self,
        task_description: str,
        constraints: list[str] | None = None,
        relevant_knowledge: dict[str, Any] | None = None,
        input_data: dict[str, Any] | None = None,
        prompt_version: str | None = None,
        target_agent_id: str | None = None,
        priority: int = 0,
        max_tokens: int | None = None,
        short_term_context: list[str] | None = None,
        mid_term_context: dict[str, Any] | None = None,
        long_term_references: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContextPackage:
        """
        打包上下文

        Args:
            task_description: 任务描述
            constraints: 约束条件
            relevant_knowledge: 相关知识
            input_data: 输入数据
            prompt_version: 提示词版本
            target_agent_id: 目标 Agent ID
            priority: 优先级
            max_tokens: Token 限制
            short_term_context: 短期上下文
            mid_term_context: 中期上下文
            long_term_references: 长期知识引用
            metadata: 元数据

        Returns:
            ContextPackage 实例
        """
        return ContextPackage(
            package_id=self._generate_package_id(),
            task_description=task_description,
            prompt_version=prompt_version or self.default_prompt_version,
            constraints=constraints or [],
            relevant_knowledge=relevant_knowledge or {},
            input_data=input_data or {},
            parent_agent_id=self.agent_id,
            target_agent_id=target_agent_id,
            priority=priority,
            max_tokens=max_tokens,
            short_term_context=short_term_context or [],
            mid_term_context=mid_term_context or {},
            long_term_references=long_term_references or [],
            metadata=metadata or {},
        )

    def pack_with_short_term_memory(
        self,
        task_description: str,
        short_term_memory: dict[str, Any],
        **kwargs: Any,
    ) -> ContextPackage:
        """
        使用短期记忆打包

        Args:
            task_description: 任务描述
            short_term_memory: 短期记忆数据
            **kwargs: 其他参数

        Returns:
            ContextPackage 实例
        """
        # 提取消息列表
        messages = short_term_memory.get("recent_messages", [])
        context = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                context.append(f"{role}: {content}")
            else:
                context.append(str(msg))

        return self.pack(
            task_description=task_description,
            short_term_context=context,
            **kwargs,
        )

    def pack_with_mid_term_memory(
        self,
        task_description: str,
        mid_term_memory: dict[str, Any],
        **kwargs: Any,
    ) -> ContextPackage:
        """
        使用中期记忆打包

        Args:
            task_description: 任务描述
            mid_term_memory: 中期记忆数据
            **kwargs: 其他参数

        Returns:
            ContextPackage 实例
        """
        return self.pack(
            task_description=task_description,
            mid_term_context=mid_term_memory,
            **kwargs,
        )

    def pack_from_context_manager(
        self,
        task_description: str,
        context_data: dict[str, Any],
        **kwargs: Any,
    ) -> ContextPackage:
        """
        从 ContextManager 数据打包

        Args:
            task_description: 任务描述
            context_data: ContextManager 提供的数据
            **kwargs: 其他参数

        Returns:
            ContextPackage 实例
        """
        return self.pack(
            task_description=task_description,
            short_term_context=context_data.get("short_term", []),
            mid_term_context=context_data.get("mid_term", {}),
            long_term_references=context_data.get("long_term_refs", []),
            **kwargs,
        )


# ============================================================================
# 解包器
# ============================================================================


class ContextUnpacker:
    """
    上下文解包器

    子 Agent 用于解析上下文包。
    """

    def __init__(self, agent_id: str | None = None):
        """
        初始化解包器

        Args:
            agent_id: 当前 Agent ID
        """
        self.agent_id = agent_id
        self._validator = ContextSchemaValidator()

    def unpack(self, package: ContextPackage) -> UnpackedContext:
        """
        解包上下文

        Args:
            package: 上下文包

        Returns:
            UnpackedContext 实例
        """
        return UnpackedContext(
            task_description=package.task_description,
            constraints=package.constraints,
            knowledge=package.relevant_knowledge,
            input_data=package.input_data,
            short_term=package.short_term_context,
            mid_term=package.mid_term_context,
            source_agent=package.parent_agent_id,
            prompt_version=package.prompt_version,
            priority=package.priority,
            metadata=package.metadata,
        )

    def unpack_from_json(self, json_str: str) -> UnpackedContext:
        """
        从 JSON 解包

        Args:
            json_str: JSON 字符串

        Returns:
            UnpackedContext 实例

        Raises:
            ContextValidationError: 验证失败
        """
        data = json.loads(json_str)

        # 验证
        result = self._validator.validate(data)
        if not result.is_valid:
            # 包含具体的错误字段信息
            error_details = "; ".join(result.errors)
            raise ContextValidationError(
                f"上下文包验证失败: {error_details}",
                result.errors,
            )

        package = ContextPackage.from_dict(data)
        return self.unpack(package)

    def extract_for_memory(self, package: ContextPackage) -> dict[str, Any]:
        """
        提取用于记忆存储的数据

        Args:
            package: 上下文包

        Returns:
            可存储的记忆数据
        """
        return {
            "short_term": package.short_term_context,
            "mid_term": package.mid_term_context,
            "long_term_refs": package.long_term_references,
            "task": package.task_description,
            "timestamp": package.created_at,
        }


# ============================================================================
# 压缩器
# ============================================================================


class ContextCompressor:
    """
    上下文压缩器

    避免信息过载，在 Token 限制内优化上下文。
    """

    # 简单的 Token 估算：中文约 2 字符/token，英文约 4 字符/token
    CHARS_PER_TOKEN_CN = 2
    CHARS_PER_TOKEN_EN = 4

    def __init__(self, strategy: CompressionStrategy = CompressionStrategy.TRUNCATE):
        """
        初始化压缩器

        Args:
            strategy: 压缩策略
        """
        self.strategy = strategy

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本 Token 数

        Args:
            text: 文本

        Returns:
            估算的 Token 数
        """
        if not text:
            return 0

        # 简单估算：检测中文字符比例
        cn_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        en_chars = len(text) - cn_chars

        cn_tokens = cn_chars / self.CHARS_PER_TOKEN_CN
        en_tokens = en_chars / self.CHARS_PER_TOKEN_EN

        return int(cn_tokens + en_tokens)

    def _estimate_package_tokens(self, package: ContextPackage) -> int:
        """估算整个包的 Token 数"""
        total = 0
        total += self.estimate_tokens(package.task_description)
        total += self.estimate_tokens(" ".join(package.constraints))
        total += self.estimate_tokens(json.dumps(package.relevant_knowledge))
        total += self.estimate_tokens(json.dumps(package.input_data))
        total += self.estimate_tokens(" ".join(package.short_term_context))
        total += self.estimate_tokens(json.dumps(package.mid_term_context))
        return total

    def compress(self, package: ContextPackage) -> ContextPackage:
        """
        压缩上下文包

        Args:
            package: 原始上下文包

        Returns:
            压缩后的上下文包
        """
        if package.max_tokens is None:
            return package

        current_tokens = self._estimate_package_tokens(package)
        if current_tokens <= package.max_tokens:
            return package

        # 需要压缩
        if self.strategy == CompressionStrategy.TRUNCATE:
            return self._compress_truncate(package)
        elif self.strategy == CompressionStrategy.PRIORITY:
            return self._compress_priority(package)
        else:
            return self._compress_truncate(package)

    def _compress_truncate(self, package: ContextPackage) -> ContextPackage:
        """截断策略压缩"""
        max_tokens = package.max_tokens or 4000

        # 保留核心字段的 Token 预算
        task_budget = min(200, max_tokens // 4)
        constraints_budget = min(100, max_tokens // 8)
        context_budget = max_tokens - task_budget - constraints_budget

        # 压缩短期上下文（保留最近的）
        compressed_context = []
        context_tokens = 0
        for msg in reversed(package.short_term_context):
            msg_tokens = self.estimate_tokens(msg)
            if context_tokens + msg_tokens <= context_budget:
                compressed_context.insert(0, msg)
                context_tokens += msg_tokens
            else:
                break

        return ContextPackage(
            package_id=package.package_id,
            task_description=package.task_description[: task_budget * 4],
            prompt_version=package.prompt_version,
            constraints=package.constraints[:5],  # 最多 5 个约束
            relevant_knowledge=package.relevant_knowledge,
            input_data=package.input_data,
            parent_agent_id=package.parent_agent_id,
            target_agent_id=package.target_agent_id,
            priority=package.priority,
            max_tokens=package.max_tokens,
            short_term_context=compressed_context,
            mid_term_context=package.mid_term_context,
            long_term_references=package.long_term_references[:3],
            created_at=package.created_at,
            metadata=package.metadata,
        )

    def _compress_priority(self, package: ContextPackage) -> ContextPackage:
        """优先级策略压缩"""
        # 与截断类似，但优先保留高优先级内容
        return self._compress_truncate(package)

    def compress_with_report(
        self, package: ContextPackage
    ) -> tuple[ContextPackage, dict[str, Any]]:
        """
        压缩并返回报告

        Args:
            package: 原始上下文包

        Returns:
            (压缩后的包, 压缩报告)
        """
        original_tokens = self._estimate_package_tokens(package)
        compressed = self.compress(package)
        compressed_tokens = self._estimate_package_tokens(compressed)

        # 检测被截断的字段
        truncated_fields = []
        if len(compressed.short_term_context) < len(package.short_term_context):
            truncated_fields.append("short_term_context")
        if len(compressed.constraints) < len(package.constraints):
            truncated_fields.append("constraints")
        if len(compressed.long_term_references) < len(package.long_term_references):
            truncated_fields.append("long_term_references")

        report = {
            "original_tokens": original_tokens,
            "compressed_tokens": compressed_tokens,
            "compression_ratio": (
                compressed_tokens / original_tokens if original_tokens > 0 else 1.0
            ),
            "truncated_fields": truncated_fields,
            "strategy_used": self.strategy.value,
        }

        return compressed, report


# ============================================================================
# 工厂函数
# ============================================================================


def create_context_package(
    task_description: str,
    prompt_version: str = "1.0.0",
    **kwargs: Any,
) -> ContextPackage:
    """
    创建上下文包的便捷函数

    Args:
        task_description: 任务描述
        prompt_version: 提示词版本
        **kwargs: 其他参数

    Returns:
        ContextPackage 实例
    """
    return ContextPackage(
        package_id=f"ctx_{uuid.uuid4().hex[:12]}",
        task_description=task_description,
        prompt_version=prompt_version,
        constraints=kwargs.get("constraints", []),
        relevant_knowledge=kwargs.get("relevant_knowledge", {}),
        input_data=kwargs.get("input_data", {}),
        parent_agent_id=kwargs.get("parent_agent_id"),
        target_agent_id=kwargs.get("target_agent_id"),
        priority=kwargs.get("priority", 0),
        max_tokens=kwargs.get("max_tokens"),
        short_term_context=kwargs.get("short_term_context", []),
        mid_term_context=kwargs.get("mid_term_context", {}),
        long_term_references=kwargs.get("long_term_references", []),
        metadata=kwargs.get("metadata", {}),
    )
