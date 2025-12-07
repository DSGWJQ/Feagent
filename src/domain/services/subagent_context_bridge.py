"""
子 Agent 上下文桥接器

该模块实现父子 Agent 之间的上下文传递与结果回收：
1. ResultPackage - 结果包数据结构
2. SubAgentContextBridge - 上下文桥接器（注入/回收）
3. ContextAwareSubAgent - 上下文感知子 Agent
4. ContextTracingLogger - 上下文追踪日志器
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.domain.services.context_protocol import ContextPackage

# ============================================================================
# 异常类
# ============================================================================


class ContextInjectionError(Exception):
    """上下文注入错误"""

    def __init__(self, message: str, field_name: str | None = None):
        super().__init__(message)
        self.message = message
        self.field_name = field_name


# ============================================================================
# 结果包数据结构
# ============================================================================


@dataclass
class ResultPackage:
    """
    结果包数据结构

    子 Agent 完成任务后返回给父 Agent 的结果。

    Attributes:
        result_id: 结果包唯一标识符
        context_package_id: 关联的上下文包 ID
        agent_id: 执行任务的 Agent ID
        status: 执行状态 (completed/failed/cancelled)
        output_data: 输出数据
        execution_logs: 执行日志
        knowledge_updates: 知识更新
        error_message: 错误消息（失败时）
        error_code: 错误代码（失败时）
        execution_time_ms: 执行时间（毫秒）
        started_at: 开始时间
        completed_at: 完成时间
    """

    result_id: str
    context_package_id: str
    agent_id: str
    status: str
    output_data: dict[str, Any]
    execution_logs: list[dict[str, Any]] = field(default_factory=list)
    knowledge_updates: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    error_code: str | None = None
    execution_time_ms: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "result_id": self.result_id,
            "context_package_id": self.context_package_id,
            "agent_id": self.agent_id,
            "status": self.status,
            "output_data": self.output_data,
            "execution_logs": self.execution_logs,
            "knowledge_updates": self.knowledge_updates,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "execution_time_ms": self.execution_time_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResultPackage:
        """从字典创建实例"""
        started_at = None
        completed_at = None

        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            completed_at = datetime.fromisoformat(data["completed_at"])

        return cls(
            result_id=data["result_id"],
            context_package_id=data["context_package_id"],
            agent_id=data["agent_id"],
            status=data["status"],
            output_data=data.get("output_data", {}),
            execution_logs=data.get("execution_logs", []),
            knowledge_updates=data.get("knowledge_updates", {}),
            error_message=data.get("error_message"),
            error_code=data.get("error_code"),
            execution_time_ms=data.get("execution_time_ms", 0),
            started_at=started_at,
            completed_at=completed_at,
        )

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> ResultPackage:
        """从 JSON 字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)


# ============================================================================
# 验证函数
# ============================================================================


VALID_STATUSES = {"completed", "failed", "cancelled", "in_progress"}


def validate_result_package(package: ResultPackage) -> tuple[bool, list[str]]:
    """
    验证结果包

    Args:
        package: 待验证的结果包

    Returns:
        (is_valid, errors) 元组
    """
    errors = []

    # 检查必需字段
    if not package.result_id:
        errors.append("result_id 不能为空")
    if not package.context_package_id:
        errors.append("context_package_id 不能为空")
    if not package.agent_id:
        errors.append("agent_id 不能为空")

    # 检查状态
    if package.status not in VALID_STATUSES:
        errors.append(f"无效的 status: {package.status}")

    # 失败状态需要错误信息
    if package.status == "failed" and not package.error_message:
        errors.append("失败状态需要 error_message")

    return len(errors) == 0, errors


# ============================================================================
# 上下文追踪日志器
# ============================================================================


class ContextTracingLogger:
    """
    上下文追踪日志器

    在日志中自动包含上下文 ID 和结果 ID。
    """

    def __init__(
        self,
        context_id: str,
        result_id: str | None = None,
    ):
        """
        初始化日志器

        Args:
            context_id: 上下文包 ID
            result_id: 结果包 ID（可选）
        """
        self.context_id = context_id
        self.result_id = result_id
        self._logs: list[dict[str, Any]] = []

    def _create_entry(self, level: str, message: str) -> dict[str, Any]:
        """创建日志条目"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "context_id": self.context_id,
        }
        if self.result_id:
            entry["result_id"] = self.result_id

        self._logs.append(entry)
        return entry

    def debug(self, message: str) -> dict[str, Any]:
        """调试日志"""
        return self._create_entry("DEBUG", message)

    def info(self, message: str) -> dict[str, Any]:
        """信息日志"""
        return self._create_entry("INFO", message)

    def warning(self, message: str) -> dict[str, Any]:
        """警告日志"""
        return self._create_entry("WARNING", message)

    def error(self, message: str) -> dict[str, Any]:
        """错误日志"""
        return self._create_entry("ERROR", message)

    def get_logs(self) -> list[dict[str, Any]]:
        """获取所有日志"""
        return self._logs.copy()


# ============================================================================
# 上下文桥接器
# ============================================================================


class SubAgentContextBridge:
    """
    子 Agent 上下文桥接器

    负责：
    1. 将上下文包注入到子 Agent 配置
    2. 构建系统提示词
    3. 加载上下文到工作记忆
    4. 创建结果包
    """

    def __init__(self, parent_agent_id: str):
        """
        初始化桥接器

        Args:
            parent_agent_id: 父 Agent ID
        """
        self.parent_agent_id = parent_agent_id

    def _generate_result_id(self) -> str:
        """生成唯一结果包 ID"""
        return f"res_{uuid.uuid4().hex[:12]}"

    def inject_context(
        self,
        context_package: ContextPackage,
        target_agent_id: str,
    ) -> dict[str, Any]:
        """
        将上下文注入到子 Agent 配置

        Args:
            context_package: 上下文包
            target_agent_id: 目标子 Agent ID

        Returns:
            子 Agent 初始化配置

        Raises:
            ContextInjectionError: 验证失败
        """
        # 验证上下文
        if not context_package.task_description:
            raise ContextInjectionError(
                "task_description 不能为空",
                field_name="task_description",
            )

        # 验证目标 Agent ID
        if not target_agent_id:
            raise ContextInjectionError(
                "target_agent_id 不能为空",
                field_name="target_agent_id",
            )

        return {
            "context_package_id": context_package.package_id,
            "task_description": context_package.task_description,
            "constraints": context_package.constraints,
            "input_data": context_package.input_data,
            "relevant_knowledge": context_package.relevant_knowledge,
            "short_term_context": context_package.short_term_context,
            "mid_term_context": context_package.mid_term_context,
            "priority": context_package.priority,
            "parent_agent_id": self.parent_agent_id,
            "target_agent_id": target_agent_id,
        }

    def build_system_prompt(self, context_package: ContextPackage) -> str:
        """
        构建系统提示词

        将上下文包转换为系统提示词格式。

        Args:
            context_package: 上下文包

        Returns:
            系统提示词
        """
        parts = []

        # 任务描述
        parts.append(f"## 任务\n{context_package.task_description}")

        # 约束条件
        if context_package.constraints:
            constraints_text = "\n".join(f"- {c}" for c in context_package.constraints)
            parts.append(f"## 约束条件\n{constraints_text}")

        # 相关知识
        if context_package.relevant_knowledge:
            knowledge_text = json.dumps(
                context_package.relevant_knowledge,
                ensure_ascii=False,
                indent=2,
            )
            parts.append(f"## 相关知识\n{knowledge_text}")

        # 输入数据
        if context_package.input_data:
            input_text = json.dumps(
                context_package.input_data,
                ensure_ascii=False,
                indent=2,
            )
            parts.append(f"## 输入数据\n{input_text}")

        return "\n\n".join(parts)

    def load_to_working_memory(
        self,
        context_package: ContextPackage,
    ) -> dict[str, Any]:
        """
        加载上下文到工作记忆

        Args:
            context_package: 上下文包

        Returns:
            工作记忆字典
        """
        return {
            "context_id": context_package.package_id,
            "task": context_package.task_description,
            "constraints": context_package.constraints,
            "input": context_package.input_data,
            "knowledge": context_package.relevant_knowledge,
            "short_term": context_package.short_term_context,
            "mid_term": context_package.mid_term_context,
            "priority": context_package.priority,
        }

    def create_result_package(
        self,
        context_package_id: str,
        agent_id: str,
        output_data: dict[str, Any],
        status: str = "completed",
        execution_logs: list[dict[str, Any]] | None = None,
        knowledge_updates: dict[str, Any] | None = None,
        error_message: str | None = None,
        error_code: str | None = None,
        execution_time_ms: int = 0,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> ResultPackage:
        """
        创建结果包

        Args:
            context_package_id: 关联的上下文包 ID
            agent_id: Agent ID
            output_data: 输出数据
            status: 状态
            execution_logs: 执行日志
            knowledge_updates: 知识更新
            error_message: 错误消息
            error_code: 错误代码
            execution_time_ms: 执行时间
            started_at: 开始时间
            completed_at: 完成时间

        Returns:
            ResultPackage 实例
        """
        return ResultPackage(
            result_id=self._generate_result_id(),
            context_package_id=context_package_id,
            agent_id=agent_id,
            status=status,
            output_data=output_data,
            execution_logs=execution_logs or [],
            knowledge_updates=knowledge_updates or {},
            error_message=error_message,
            error_code=error_code,
            execution_time_ms=execution_time_ms,
            started_at=started_at,
            completed_at=completed_at,
        )


# ============================================================================
# 上下文感知子 Agent
# ============================================================================


class ContextAwareSubAgent:
    """
    上下文感知子 Agent

    在启动时加载上下文到工作记忆，
    任务完成时打包结果返回父 Agent。
    """

    def __init__(
        self,
        agent_id: str,
        context_package: ContextPackage,
    ):
        """
        初始化子 Agent

        Args:
            agent_id: Agent ID
            context_package: 上下文包
        """
        self.agent_id = agent_id
        self._context_package = context_package
        self._bridge = SubAgentContextBridge(
            parent_agent_id=context_package.parent_agent_id or "unknown"
        )

        # 加载上下文到工作记忆
        self._working_memory = self._bridge.load_to_working_memory(context_package)

        # 日志器
        self._logger = ContextTracingLogger(context_id=context_package.package_id)
        self._execution_logs: list[dict[str, Any]] = []

        # 执行时间
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None

    @property
    def context_package_id(self) -> str:
        """上下文包 ID"""
        return self._context_package.package_id

    @property
    def task_description(self) -> str:
        """任务描述"""
        return self._context_package.task_description

    @property
    def constraints(self) -> list[str]:
        """约束条件"""
        return self._context_package.constraints

    def get_working_memory(self) -> dict[str, Any]:
        """获取工作记忆"""
        return self._working_memory.copy()

    def log(self, message: str, level: str = "INFO") -> None:
        """
        添加执行日志

        Args:
            message: 日志消息
            level: 日志级别
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "context_id": self.context_package_id,
        }
        self._execution_logs.append(entry)

    def start_execution(self) -> None:
        """标记执行开始"""
        self._started_at = datetime.now()
        self.log("执行开始")

    def _calculate_execution_time(self) -> int:
        """计算执行时间（毫秒）"""
        if self._started_at is None:
            return 0
        if self._completed_at is None:
            self._completed_at = datetime.now()

        delta = self._completed_at - self._started_at
        return int(delta.total_seconds() * 1000)

    async def complete_task(
        self,
        output_data: dict[str, Any],
        knowledge_updates: dict[str, Any] | None = None,
    ) -> ResultPackage:
        """
        完成任务并打包结果

        Args:
            output_data: 输出数据
            knowledge_updates: 知识更新

        Returns:
            ResultPackage 实例
        """
        self._completed_at = datetime.now()
        self.log("执行完成")

        return self._bridge.create_result_package(
            context_package_id=self.context_package_id,
            agent_id=self.agent_id,
            output_data=output_data,
            status="completed",
            execution_logs=self._execution_logs,
            knowledge_updates=knowledge_updates or {},
            execution_time_ms=self._calculate_execution_time(),
            started_at=self._started_at,
            completed_at=self._completed_at,
        )

    async def fail_task(
        self,
        error_message: str,
        error_code: str | None = None,
    ) -> ResultPackage:
        """
        任务失败并打包结果

        Args:
            error_message: 错误消息
            error_code: 错误代码

        Returns:
            ResultPackage 实例
        """
        self._completed_at = datetime.now()
        self.log(f"执行失败: {error_message}", level="ERROR")

        return self._bridge.create_result_package(
            context_package_id=self.context_package_id,
            agent_id=self.agent_id,
            output_data={},
            status="failed",
            execution_logs=self._execution_logs,
            error_message=error_message,
            error_code=error_code,
            execution_time_ms=self._calculate_execution_time(),
            started_at=self._started_at,
            completed_at=self._completed_at,
        )


# ============================================================================
# 工厂函数
# ============================================================================


def context_aware_subagent_factory(
    agent_id: str,
    context_package: ContextPackage,
) -> ContextAwareSubAgent:
    """
    创建上下文感知子 Agent 的工厂函数

    Args:
        agent_id: Agent ID
        context_package: 上下文包

    Returns:
        ContextAwareSubAgent 实例
    """
    return ContextAwareSubAgent(
        agent_id=agent_id,
        context_package=context_package,
    )
