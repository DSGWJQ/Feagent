"""强力压缩器 - Phase 6

业务定义：
- SubtaskError: 子任务错误信息
- UnresolvedIssue: 未解决问题
- NextPlanItem: 后续计划项
- KnowledgeSource: 知识来源
- PowerCompressedContext: 八段压缩上下文
- PowerCompressor: 强力压缩器，实现八段压缩与知识集成

八段压缩格式：
1. 任务目标 (task_goal)
2. 执行状态 (execution_status)
3. 节点摘要 (node_summary)
4. 子任务错误 (subtask_errors)
5. 未解决问题 (unresolved_issues)
6. 决策历史 (decision_history)
7. 后续计划 (next_plan)
8. 知识来源 (knowledge_sources)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ==================== 数据结构 ====================


@dataclass
class SubtaskError:
    """子任务错误

    属性：
        subtask_id: 子任务ID
        error_type: 错误类型（TIMEOUT, VALIDATION, HTTP_ERROR, etc.）
        error_message: 错误消息
        occurred_at: 发生时间
        retryable: 是否可重试
        source_document: 相关知识文档（可选）
    """

    subtask_id: str
    error_type: str
    error_message: str
    occurred_at: datetime
    retryable: bool = False
    source_document: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "subtask_id": self.subtask_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "occurred_at": self.occurred_at.isoformat(),
            "retryable": self.retryable,
            "source_document": self.source_document,
        }


@dataclass
class UnresolvedIssue:
    """未解决问题

    属性：
        issue_id: 问题ID
        description: 问题描述
        severity: 严重程度（low, medium, high, critical）
        blocked_nodes: 被阻塞的节点列表
        suggested_actions: 建议操作
        related_knowledge: 相关知识文档（可选）
    """

    issue_id: str
    description: str
    severity: str
    blocked_nodes: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)
    related_knowledge: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "issue_id": self.issue_id,
            "description": self.description,
            "severity": self.severity,
            "blocked_nodes": self.blocked_nodes,
            "suggested_actions": self.suggested_actions,
            "related_knowledge": self.related_knowledge,
        }


@dataclass
class NextPlanItem:
    """后续计划项

    属性：
        action: 计划操作
        priority: 优先级（1最高）
        rationale: 理由说明
        estimated_effort: 预估工作量（low, medium, high）
        dependencies: 依赖项
        knowledge_ref: 相关知识引用（可选）
    """

    action: str
    priority: int
    rationale: str
    estimated_effort: str = "medium"
    dependencies: list[str] = field(default_factory=list)
    knowledge_ref: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "action": self.action,
            "priority": self.priority,
            "rationale": self.rationale,
            "estimated_effort": self.estimated_effort,
            "dependencies": self.dependencies,
            "knowledge_ref": self.knowledge_ref,
        }


@dataclass
class KnowledgeSource:
    """知识来源

    属性：
        source_id: 来源ID
        title: 标题
        source_type: 来源类型（knowledge_base, rule, document）
        relevance_score: 相关性分数（0-1）
        applied_to_segments: 应用到的段
        content_preview: 内容预览（可选）
    """

    source_id: str
    title: str
    source_type: str
    relevance_score: float = 0.0
    applied_to_segments: list[str] = field(default_factory=list)
    content_preview: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "source_id": self.source_id,
            "title": self.title,
            "source_type": self.source_type,
            "relevance_score": self.relevance_score,
            "applied_to_segments": self.applied_to_segments,
            "content_preview": self.content_preview,
        }


# ==================== 八段压缩上下文 ====================


@dataclass
class PowerCompressedContext:
    """八段压缩上下文

    包含完整的八段压缩格式，用于协调者存储和对话Agent引用。
    """

    workflow_id: str
    session_id: str

    # 八段内容
    task_goal: str = ""
    execution_status: dict[str, Any] = field(default_factory=dict)
    node_summary: list[dict[str, Any]] = field(default_factory=list)
    subtask_errors: list[SubtaskError] = field(default_factory=list)
    unresolved_issues: list[UnresolvedIssue] = field(default_factory=list)
    decision_history: list[dict[str, Any]] = field(default_factory=list)
    next_plan: list[NextPlanItem] = field(default_factory=list)
    knowledge_sources: list[KnowledgeSource] = field(default_factory=list)

    # 元数据
    compressed_at: datetime = field(default_factory=datetime.now)
    context_id: str = field(default_factory=lambda: f"ctx_{uuid4().hex[:12]}")

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_id": self.workflow_id,
            "session_id": self.session_id,
            "context_id": self.context_id,
            "task_goal": self.task_goal,
            "execution_status": self.execution_status,
            "node_summary": self.node_summary,
            "subtask_errors": [e.to_dict() for e in self.subtask_errors],
            "unresolved_issues": [i.to_dict() for i in self.unresolved_issues],
            "decision_history": self.decision_history,
            "next_plan": [p.to_dict() for p in self.next_plan],
            "knowledge_sources": [k.to_dict() for k in self.knowledge_sources],
            "compressed_at": self.compressed_at.isoformat(),
        }

    def to_eight_segment_summary(self) -> str:
        """生成八段格式的文本摘要

        返回格式化的八段摘要，用于日志和调试。
        """
        lines = []

        # 1. 任务目标
        lines.append("[1.任务目标]")
        lines.append(f"  {self.task_goal or '未指定'}")
        lines.append("")

        # 2. 执行状态
        lines.append("[2.执行状态]")
        status = self.execution_status or {}
        lines.append(f"  状态: {status.get('status', '未知')}")
        lines.append(f"  进度: {status.get('progress', 0) * 100:.0f}%")
        lines.append("")

        # 3. 节点摘要
        lines.append("[3.节点摘要]")
        if self.node_summary:
            for node in self.node_summary:
                lines.append(f"  - {node.get('node_id', '?')}: {node.get('status', '?')}")
        else:
            lines.append("  无节点信息")
        lines.append("")

        # 4. 子任务错误
        lines.append("[4.子任务错误]")
        if self.subtask_errors:
            for err in self.subtask_errors:
                retry_flag = "可重试" if err.retryable else "不可重试"
                lines.append(f"  - [{err.error_type}] {err.error_message} ({retry_flag})")
                if err.source_document:
                    lines.append(f"    参考: {err.source_document.get('title', '')}")
        else:
            lines.append("  无错误")
        lines.append("")

        # 5. 未解决问题
        lines.append("[5.未解决问题]")
        if self.unresolved_issues:
            for issue in self.unresolved_issues:
                lines.append(f"  - [{issue.severity}] {issue.description}")
                if issue.blocked_nodes:
                    lines.append(f"    阻塞节点: {', '.join(issue.blocked_nodes)}")
                if issue.suggested_actions:
                    lines.append(f"    建议: {'; '.join(issue.suggested_actions)}")
        else:
            lines.append("  无未解决问题")
        lines.append("")

        # 6. 决策历史
        lines.append("[6.决策历史]")
        if self.decision_history:
            for decision in self.decision_history:
                lines.append(f"  - {decision.get('decision', '?')}")
                lines.append(f"    原因: {decision.get('reason', '?')}")
        else:
            lines.append("  无决策历史")
        lines.append("")

        # 7. 后续计划
        lines.append("[7.后续计划]")
        if self.next_plan:
            for plan in sorted(self.next_plan, key=lambda x: x.priority):
                lines.append(f"  {plan.priority}. {plan.action}")
                lines.append(f"     理由: {plan.rationale}")
                lines.append(f"     工作量: {plan.estimated_effort}")
        else:
            lines.append("  无后续计划")
        lines.append("")

        # 8. 知识来源
        lines.append("[8.知识来源]")
        if self.knowledge_sources:
            for source in self.knowledge_sources:
                lines.append(f"  - {source.title} (相关度: {source.relevance_score:.0%})")
                lines.append(f"    应用到: {', '.join(source.applied_to_segments)}")
        else:
            lines.append("  无知识来源")

        return "\n".join(lines)


# ==================== 强力压缩器 ====================


class PowerCompressor:
    """强力压缩器

    实现八段压缩与知识系统集成。
    """

    def __init__(self):
        """初始化压缩器"""
        pass

    def compress_summary(self, summary: Any) -> PowerCompressedContext:
        """压缩执行总结

        参数：
            summary: ExecutionSummary 实例

        返回：
            PowerCompressedContext
        """
        workflow_id = getattr(summary, "workflow_id", "")
        session_id = getattr(summary, "session_id", "")

        # 提取错误
        errors = []
        if hasattr(summary, "errors") and summary.errors:
            for err in summary.errors:
                # 兼容 error_code 和 error_type
                error_type = getattr(err, "error_code", None) or getattr(
                    err, "error_type", "UNKNOWN"
                )
                # 兼容 error_message 和 message
                error_message = getattr(err, "error_message", None) or getattr(err, "message", "")
                # 兼容 timestamp 和 occurred_at
                occurred_at = getattr(err, "timestamp", None) or getattr(
                    err, "occurred_at", datetime.now()
                )
                errors.append(
                    SubtaskError(
                        subtask_id=getattr(err, "node_id", "") or "unknown",
                        error_type=error_type,
                        error_message=error_message,
                        occurred_at=occurred_at,
                        retryable=getattr(err, "retryable", False),
                    )
                )

        # 生成执行状态
        success = getattr(summary, "success", False)
        execution_status = {
            "status": "completed" if success else "failed",
            "progress": 1.0 if success else 0.5,
        }

        return PowerCompressedContext(
            workflow_id=workflow_id,
            session_id=session_id,
            execution_status=execution_status,
            subtask_errors=errors,
        )

    def compress_subtask_results(
        self,
        workflow_id: str,
        session_id: str,
        subtask_results: list[dict[str, Any]],
    ) -> PowerCompressedContext:
        """压缩子任务结果

        参数：
            workflow_id: 工作流ID
            session_id: 会话ID
            subtask_results: 子任务结果列表

        返回：
            PowerCompressedContext
        """
        errors = []
        node_summary = []

        for result in subtask_results:
            subtask_id = result.get("subtask_id", "unknown")
            success = result.get("success", True)

            # 记录节点状态
            node_summary.append(
                {
                    "node_id": subtask_id,
                    "status": "completed" if success else "failed",
                }
            )

            # 提取错误
            if not success:
                errors.append(
                    SubtaskError(
                        subtask_id=subtask_id,
                        error_type=result.get("error_type", "UNKNOWN"),
                        error_message=result.get("error", ""),
                        occurred_at=datetime.now(),
                        retryable=result.get("retryable", False),
                    )
                )

        return PowerCompressedContext(
            workflow_id=workflow_id,
            session_id=session_id,
            node_summary=node_summary,
            subtask_errors=errors,
        )

    def extract_unresolved_issues(self, execution_data: dict[str, Any]) -> list[UnresolvedIssue]:
        """提取未解决问题

        参数：
            execution_data: 执行数据

        返回：
            UnresolvedIssue 列表
        """
        issues = []

        # 从阻塞问题提取
        blocking_issues = execution_data.get("blocking_issues", [])
        for idx, issue in enumerate(blocking_issues):
            issues.append(
                UnresolvedIssue(
                    issue_id=f"issue_{idx + 1}",
                    description=issue.get("description", ""),
                    severity=issue.get("severity", "medium"),
                    blocked_nodes=issue.get("blocked_nodes", []),
                    suggested_actions=issue.get("suggested_actions", []),
                )
            )

        # 从待验证项提取
        pending_validations = execution_data.get("pending_validations", [])
        for idx, validation in enumerate(pending_validations):
            issues.append(
                UnresolvedIssue(
                    issue_id=f"validation_{idx + 1}",
                    description=validation if isinstance(validation, str) else str(validation),
                    severity="low",
                    blocked_nodes=[],
                    suggested_actions=["执行验证"],
                )
            )

        return issues

    def generate_next_plan(self, context: dict[str, Any]) -> list[NextPlanItem]:
        """生成后续计划

        参数：
            context: 上下文数据

        返回：
            NextPlanItem 列表
        """
        plans = []
        priority = 1

        # 处理未解决问题
        unresolved = context.get("unresolved_issues", [])
        for issue in unresolved:
            actions = issue.get("suggested_actions", [])
            if actions:
                for action in actions:
                    plans.append(
                        NextPlanItem(
                            action=action,
                            priority=priority,
                            rationale=f"解决问题: {issue.get('description', '')}",
                            estimated_effort="medium",
                        )
                    )
                    priority += 1

        # 处理待执行节点
        pending_nodes = context.get("pending_nodes", [])
        for node in pending_nodes:
            plans.append(
                NextPlanItem(
                    action=f"执行节点 {node}",
                    priority=priority,
                    rationale="待执行节点",
                    estimated_effort="medium",
                )
            )
            priority += 1

        # 处理反思建议
        recommendations = context.get("reflection_recommendations", [])
        for rec in recommendations:
            plans.append(
                NextPlanItem(
                    action=rec,
                    priority=priority,
                    rationale="反思建议",
                    estimated_effort="low",
                )
            )
            priority += 1

        return plans

    def attach_knowledge_sources(
        self,
        ctx: PowerCompressedContext,
        knowledge_context: dict[str, Any],
    ) -> PowerCompressedContext:
        """附加知识来源

        参数：
            ctx: 压缩上下文
            knowledge_context: 知识上下文

        返回：
            更新后的 PowerCompressedContext
        """
        sources = []

        # 处理知识库
        knowledge_list = knowledge_context.get("knowledge", [])
        for kb in knowledge_list:
            sources.append(
                KnowledgeSource(
                    source_id=kb.get("source_id", f"kb_{uuid4().hex[:8]}"),
                    title=kb.get("title", "未知"),
                    source_type="knowledge_base",
                    relevance_score=kb.get("relevance_score", 0.0),
                    applied_to_segments=["task_goal"],
                )
            )

        # 处理规则
        rules = knowledge_context.get("rules", [])
        for rule in rules:
            sources.append(
                KnowledgeSource(
                    source_id=rule.get("id", f"rule_{uuid4().hex[:8]}"),
                    title=rule.get("name", "未知规则"),
                    source_type="rule",
                    relevance_score=1.0,
                    applied_to_segments=["decision_history"],
                )
            )

        ctx.knowledge_sources = sources
        return ctx

    def link_knowledge_to_segments(
        self,
        ctx: PowerCompressedContext,
        knowledge: list[dict[str, Any]],
    ) -> PowerCompressedContext:
        """链接知识到各段

        参数：
            ctx: 压缩上下文
            knowledge: 知识列表

        返回：
            更新后的 PowerCompressedContext
        """
        sources = []

        for kb in knowledge:
            # 根据任务目标判断应用到哪些段
            applied_segments = ["task_goal"]

            # 如果有错误，也链接到 subtask_errors
            if ctx.subtask_errors:
                applied_segments.append("subtask_errors")

            # 如果有问题，链接到 unresolved_issues
            if ctx.unresolved_issues:
                applied_segments.append("unresolved_issues")

            # 如果有计划，链接到 next_plan
            if ctx.next_plan:
                applied_segments.append("next_plan")

            sources.append(
                KnowledgeSource(
                    source_id=kb.get("source_id", f"kb_{uuid4().hex[:8]}"),
                    title=kb.get("title", "未知"),
                    source_type=kb.get("source_type", "knowledge_base"),
                    relevance_score=kb.get("relevance_score", 0.0),
                    applied_to_segments=applied_segments,
                    content_preview=kb.get("content_preview"),
                )
            )

        ctx.knowledge_sources = sources
        return ctx

    def enrich_error_with_knowledge(
        self,
        error: SubtaskError,
        error_knowledge: list[dict[str, Any]],
    ) -> SubtaskError:
        """用知识丰富错误信息

        参数：
            error: 子任务错误
            error_knowledge: 错误相关知识

        返回：
            丰富后的 SubtaskError
        """
        # 找到匹配的知识
        for kb in error_knowledge:
            if kb.get("error_type") == error.error_type:
                error.source_document = {
                    "title": kb.get("solution_title", ""),
                    "preview": kb.get("solution_preview", ""),
                    "confidence": kb.get("confidence", 0.0),
                }
                break

        return error

    def enrich_issue_with_knowledge(
        self,
        issue: UnresolvedIssue,
        knowledge: list[dict[str, Any]],
    ) -> UnresolvedIssue:
        """用知识丰富问题信息

        参数：
            issue: 未解决问题
            knowledge: 相关知识

        返回：
            丰富后的 UnresolvedIssue
        """
        # 选择最相关的知识
        if knowledge:
            best = max(knowledge, key=lambda x: x.get("relevance_score", 0))
            issue.related_knowledge = {
                "source_id": best.get("source_id", ""),
                "title": best.get("title", ""),
                "relevance_score": best.get("relevance_score", 0),
            }

        return issue


# 导出
__all__ = [
    "SubtaskError",
    "UnresolvedIssue",
    "NextPlanItem",
    "KnowledgeSource",
    "PowerCompressedContext",
    "PowerCompressor",
]
