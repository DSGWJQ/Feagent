"""执行总结模块 - Phase 5

业务定义：
- ExecutionSummary: 工作流执行总结数据结构
- SummaryGenerator: 总结生成器
- ExecutionSummaryRecordedEvent: 总结记录事件

支持场景：
1. WorkflowAgent 执行完成后，ConversationAgent 生成总结
2. 总结包含执行日志、成功/失败状态、错误信息
3. 总结包含规则应用、知识引用、工具使用记录
4. Coordinator 记录总结并发布事件（由外部订阅者决定是否推送到前端）

使用示例：
    # 生成总结
    generator = SummaryGenerator()
    summary = await generator.generate(
        workflow_result=result,
        session_id="session_1",
        coordinator_context=context,
    )

    # 协调者记录并推送
    await coordinator.record_execution_summary_async(summary)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from src.domain.services.event_bus import Event

# ==================== 执行日志条目 ====================


@dataclass
class ExecutionLogEntry:
    """执行日志条目

    记录工作流执行过程中的单个日志事件。

    属性：
        node_id: 节点ID
        action: 动作类型（execute, completed, failed, skipped）
        timestamp: 时间戳
        message: 日志消息
        duration: 执行时长（秒，可选）
        metadata: 额外元数据
    """

    node_id: str
    action: str
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""
    duration: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "duration": self.duration,
            "metadata": self.metadata,
        }


# ==================== 执行错误 ====================


@dataclass
class ExecutionError:
    """执行错误

    记录执行过程中发生的错误。

    属性：
        node_id: 失败的节点ID
        error_code: 错误代码
        error_message: 错误消息
        retryable: 是否可重试
        timestamp: 发生时间
        stack_trace: 堆栈跟踪（可选）
    """

    node_id: str
    error_code: str
    error_message: str
    retryable: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    stack_trace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "retryable": self.retryable,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace,
        }


# ==================== 规则应用记录 ====================


@dataclass
class RuleApplication:
    """规则应用记录

    记录执行过程中应用的规则。

    属性：
        rule_id: 规则ID
        rule_name: 规则名称
        applied: 是否应用
        result: 应用结果（通过/拒绝/跳过）
        message: 附加消息
    """

    rule_id: str
    rule_name: str
    applied: bool = True
    result: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "applied": self.applied,
            "result": self.result,
            "message": self.message,
        }


# ==================== 知识引用 ====================


@dataclass
class KnowledgeRef:
    """知识引用

    记录执行过程中引用的知识条目。

    属性：
        source_id: 知识源ID
        title: 标题
        relevance_score: 相关性分数（0-1）
        content_preview: 内容预览
        document_id: 文档ID（可选）
    """

    source_id: str
    title: str
    relevance_score: float = 0.0
    content_preview: str = ""
    document_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "source_id": self.source_id,
            "title": self.title,
            "relevance_score": self.relevance_score,
            "content_preview": self.content_preview,
            "document_id": self.document_id,
        }


# ==================== 工具使用记录 ====================


@dataclass
class ToolUsage:
    """工具使用记录

    记录执行过程中工具的使用情况。

    属性：
        tool_id: 工具ID
        tool_name: 工具名称
        invocations: 调用次数
        total_time: 总耗时（秒）
        success_count: 成功次数
        failure_count: 失败次数
    """

    tool_id: str
    tool_name: str
    invocations: int = 0
    total_time: float = 0.0
    success_count: int = 0
    failure_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "invocations": self.invocations,
            "total_time": self.total_time,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }


# ==================== 执行总结 ====================


@dataclass
class ExecutionSummary:
    """执行总结

    工作流执行完成后生成的完整总结，包含：
    - 执行日志
    - 成功/失败状态
    - 错误信息
    - 应用的规则
    - 知识引用
    - 工具使用

    属性：
        workflow_id: 工作流ID
        session_id: 会话ID
        success: 是否成功
        summary_id: 总结ID（自动生成）
        execution_logs: 执行日志列表
        errors: 错误列表
        rules_applied: 应用的规则
        knowledge_references: 知识引用
        tools_used: 工具使用记录
        node_results: 节点执行结果
        started_at: 开始时间
        completed_at: 完成时间
        total_duration: 总耗时（秒）
        metadata: 额外元数据
    """

    workflow_id: str
    session_id: str
    success: bool
    summary_id: str = field(default_factory=lambda: f"summary_{uuid4().hex[:12]}")
    execution_logs: list[ExecutionLogEntry] = field(default_factory=list)
    errors: list[ExecutionError] = field(default_factory=list)
    rules_applied: list[RuleApplication] = field(default_factory=list)
    knowledge_references: list[KnowledgeRef] = field(default_factory=list)
    tools_used: list[ToolUsage] = field(default_factory=list)
    node_results: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    total_duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典

        返回：
            可序列化的字典表示
        """
        return {
            "summary_id": self.summary_id,
            "workflow_id": self.workflow_id,
            "session_id": self.session_id,
            "success": self.success,
            "execution_logs": [log.to_dict() for log in self.execution_logs],
            "errors": [err.to_dict() for err in self.errors],
            "rules_applied": [rule.to_dict() for rule in self.rules_applied],
            "knowledge_references": [ref.to_dict() for ref in self.knowledge_references],
            "tools_used": [tool.to_dict() for tool in self.tools_used],
            "node_results": self.node_results,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration": self.total_duration,
            "metadata": self.metadata,
        }

    def to_human_readable(self) -> str:
        """生成人类可读的摘要文本

        返回：
            格式化的摘要文本
        """
        lines = []

        # 标题
        status = "成功" if self.success else "失败"
        lines.append(f"=== 执行总结 [{self.workflow_id}] ===")
        lines.append(f"状态: {status}")
        lines.append(f"会话: {self.session_id}")

        if self.total_duration > 0:
            lines.append(f"耗时: {self.total_duration:.2f}秒")

        # 节点执行情况
        if self.node_results:
            lines.append(f"\n节点执行: {len(self.node_results)}个")
            success_count = sum(1 for r in self.node_results.values() if r.get("success", False))
            lines.append(f"  成功: {success_count}, 失败: {len(self.node_results) - success_count}")

        # 错误信息
        if self.errors:
            lines.append(f"\n错误 ({len(self.errors)}个):")
            for err in self.errors[:3]:  # 最多显示3个
                lines.append(f"  - [{err.node_id}] {err.error_message}")

        # 规则应用
        if self.rules_applied:
            lines.append(f"\n规则 ({len(self.rules_applied)}条):")
            for rule in self.rules_applied[:3]:
                lines.append(f"  - {rule.rule_name}: {rule.result}")

        # 知识引用
        if self.knowledge_references:
            lines.append(f"\n知识引用 ({len(self.knowledge_references)}条):")
            for ref in self.knowledge_references[:3]:
                score_str = f"{ref.relevance_score:.0%}" if ref.relevance_score else ""
                lines.append(f"  - {ref.title} {score_str}")

        # 工具使用
        if self.tools_used:
            lines.append(f"\n工具使用 ({len(self.tools_used)}个):")
            for tool in self.tools_used[:3]:
                lines.append(f"  - {tool.tool_name}: {tool.invocations}次调用")

        return "\n".join(lines)

    def mark_completed(self) -> None:
        """标记执行完成"""
        self.completed_at = datetime.now()
        if self.started_at:
            self.total_duration = (self.completed_at - self.started_at).total_seconds()


# ==================== 总结生成器 ====================


class SummaryGenerator:
    """总结生成器

    从工作流执行结果生成 ExecutionSummary。
    """

    async def generate(
        self,
        workflow_result: dict[str, Any],
        session_id: str,
        coordinator_context: dict[str, Any] | None = None,
    ) -> ExecutionSummary:
        """生成执行总结

        参数：
            workflow_result: 工作流执行结果
            session_id: 会话ID
            coordinator_context: 协调者上下文（规则、知识、工具）

        返回：
            ExecutionSummary 实例
        """
        coordinator_context = coordinator_context or {}

        # 提取基本信息
        workflow_id = workflow_result.get("workflow_id", "")
        success = workflow_result.get("success", False)
        node_results = workflow_result.get("node_results", {})

        # 创建总结
        summary = ExecutionSummary(
            workflow_id=workflow_id,
            session_id=session_id,
            success=success,
            node_results=node_results,
        )

        # 生成执行日志
        summary.execution_logs = self._generate_logs(node_results)

        # 生成错误信息
        summary.errors = self._generate_errors(workflow_result, node_results)

        # 从协调者上下文提取规则
        summary.rules_applied = self._extract_rules(coordinator_context)

        # 从协调者上下文提取知识引用
        summary.knowledge_references = self._extract_knowledge(coordinator_context)

        # 从节点结果和上下文提取工具使用
        summary.tools_used = self._extract_tools(node_results, coordinator_context)

        # 设置时间信息
        summary.total_duration = workflow_result.get("execution_time", 0.0)
        summary.mark_completed()

        return summary

    def _generate_logs(self, node_results: dict[str, Any]) -> list[ExecutionLogEntry]:
        """从节点结果生成执行日志"""
        logs = []

        for node_id, result in node_results.items():
            success = result.get("success", False)
            action = "completed" if success else "failed"

            log = ExecutionLogEntry(
                node_id=node_id,
                action=action,
                message=result.get("message", ""),
                duration=result.get("duration"),
            )
            logs.append(log)

        return logs

    def _generate_errors(
        self,
        workflow_result: dict[str, Any],
        node_results: dict[str, Any],
    ) -> list[ExecutionError]:
        """生成错误列表"""
        errors = []

        # 从工作流结果获取主错误
        if not workflow_result.get("success", True):
            failed_node = workflow_result.get("failed_node_id", "")
            error_msg = workflow_result.get("error_message", "Unknown error")

            if failed_node:
                error = ExecutionError(
                    node_id=failed_node,
                    error_code="WORKFLOW_FAILED",
                    error_message=error_msg,
                    retryable=True,
                )
                errors.append(error)

        # 从节点结果获取错误
        for node_id, result in node_results.items():
            if not result.get("success", True):
                node_error = result.get("error", "")
                if node_error:
                    error = ExecutionError(
                        node_id=node_id,
                        error_code=result.get("error_code", "NODE_FAILED"),
                        error_message=node_error,
                        retryable=result.get("retryable", True),
                    )
                    errors.append(error)

        return errors

    def _extract_rules(self, coordinator_context: dict[str, Any]) -> list[RuleApplication]:
        """从协调者上下文提取规则"""
        rules = []

        for rule_data in coordinator_context.get("rules", []):
            rule = RuleApplication(
                rule_id=rule_data.get("id", ""),
                rule_name=rule_data.get("name", ""),
                applied=True,
                result="通过",  # 默认通过（如果执行了）
                message=rule_data.get("description", ""),
            )
            rules.append(rule)

        return rules

    def _extract_knowledge(self, coordinator_context: dict[str, Any]) -> list[KnowledgeRef]:
        """从协调者上下文提取知识引用"""
        refs = []

        for kb_data in coordinator_context.get("knowledge", []):
            ref = KnowledgeRef(
                source_id=kb_data.get("source_id", ""),
                title=kb_data.get("title", ""),
                relevance_score=kb_data.get("relevance_score", 0.0),
                content_preview=kb_data.get("content_preview", ""),
                document_id=kb_data.get("document_id"),
            )
            refs.append(ref)

        return refs

    def _extract_tools(
        self,
        node_results: dict[str, Any],
        coordinator_context: dict[str, Any],
    ) -> list[ToolUsage]:
        """从节点结果和上下文提取工具使用"""
        tool_stats: dict[str, dict[str, Any]] = {}

        # 从协调者上下文获取工具信息
        tool_names = {}
        for tool_data in coordinator_context.get("tools", []):
            tool_id = tool_data.get("id", "")
            tool_names[tool_id] = tool_data.get("name", tool_id)

        # 从节点结果统计工具使用
        for _node_id, result in node_results.items():
            tool_id = result.get("tool_id")
            if tool_id:
                if tool_id not in tool_stats:
                    tool_stats[tool_id] = {
                        "name": tool_names.get(tool_id, tool_id),
                        "invocations": 0,
                        "total_time": 0.0,
                        "success_count": 0,
                        "failure_count": 0,
                    }

                stats = tool_stats[tool_id]
                stats["invocations"] += 1
                stats["total_time"] += result.get("duration", 0.0)

                if result.get("success", False):
                    stats["success_count"] += 1
                else:
                    stats["failure_count"] += 1

        # 转换为 ToolUsage 列表
        tools = []
        for tool_id, stats in tool_stats.items():
            tool = ToolUsage(
                tool_id=tool_id,
                tool_name=stats["name"],
                invocations=stats["invocations"],
                total_time=stats["total_time"],
                success_count=stats["success_count"],
                failure_count=stats["failure_count"],
            )
            tools.append(tool)

        return tools


# ==================== 事件定义 ====================


@dataclass
class ExecutionSummaryRecordedEvent(Event):
    """执行总结记录事件

    当协调者记录执行总结时发布此事件。

    属性：
        workflow_id: 工作流ID
        session_id: 会话ID
        success: 是否成功
        summary_id: 总结ID
    """

    workflow_id: str = ""
    session_id: str = ""
    success: bool = True
    summary_id: str = ""

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "execution_summary_recorded"


# 导出
__all__ = [
    "ExecutionLogEntry",
    "ExecutionError",
    "RuleApplication",
    "KnowledgeRef",
    "ToolUsage",
    "ExecutionSummary",
    "SummaryGenerator",
    "ExecutionSummaryRecordedEvent",
]
