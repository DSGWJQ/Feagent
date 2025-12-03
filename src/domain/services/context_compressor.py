"""上下文压缩器 (Context Compressor) - 八段压缩模块

业务定义：
- 实现"八段压缩"策略，将复杂对话/执行日志压缩成结构化摘要
- 支持增量更新和全量重建
- 与现有 SummaryStrategy 系统集成

八段结构：
1. TaskGoal - 任务目标段：当前工作流的目标
2. ExecutionStatus - 执行状态段：当前执行进度
3. NodeSummary - 节点摘要段：已执行节点的关键信息
4. DecisionHistory - 决策历史段：重要决策记录
5. ReflectionSummary - 反思结果段：反思的关键发现
6. ConversationSummary - 对话摘要段：对话的核心内容
7. ErrorLog - 错误记录段：发生的错误和处理情况
8. NextActions - 下一步建议段：推荐的后续行动

设计原则：
- 每段有明确的提取策略
- 支持从不同来源（对话、执行、反思）提取信息
- 保持与 EvidenceStore 的集成，支持原始数据追溯
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

# ==================== 数据结构 ====================


@dataclass
class CompressedContext:
    """压缩上下文 - 九段结构

    属性：
    - workflow_id: 工作流ID
    - task_goal: 任务目标（第1段）
    - execution_status: 执行状态（第2段）
    - node_summary: 节点摘要（第3段）
    - decision_history: 决策历史（第4段）
    - reflection_summary: 反思摘要（第5段）
    - conversation_summary: 对话摘要（第6段）
    - error_log: 错误日志（第7段）
    - next_actions: 下一步行动（第8段）
    - knowledge_references: 知识引用（第9段）- Phase 5 新增
    - created_at: 创建时间
    - version: 版本号
    - evidence_refs: 证据引用
    """

    workflow_id: str

    # 九段内容
    task_goal: str = ""
    execution_status: dict[str, Any] = field(default_factory=dict)
    node_summary: list[dict[str, Any]] = field(default_factory=list)
    decision_history: list[dict[str, Any]] = field(default_factory=list)
    reflection_summary: dict[str, Any] = field(default_factory=dict)
    conversation_summary: str = ""
    error_log: list[dict[str, Any]] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    knowledge_references: list[dict[str, Any]] = field(default_factory=list)  # Phase 5

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典

        返回：
            字典表示
        """
        return {
            "workflow_id": self.workflow_id,
            "task_goal": self.task_goal,
            "execution_status": self.execution_status,
            "node_summary": self.node_summary,
            "decision_history": self.decision_history,
            "reflection_summary": self.reflection_summary,
            "conversation_summary": self.conversation_summary,
            "error_log": self.error_log,
            "next_actions": self.next_actions,
            "knowledge_references": self.knowledge_references,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "evidence_refs": self.evidence_refs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompressedContext":
        """从字典创建

        参数：
            data: 字典数据

        返回：
            CompressedContext 实例
        """
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            workflow_id=data.get("workflow_id", ""),
            task_goal=data.get("task_goal", ""),
            execution_status=data.get("execution_status", {}),
            node_summary=data.get("node_summary", []),
            decision_history=data.get("decision_history", []),
            reflection_summary=data.get("reflection_summary", {}),
            conversation_summary=data.get("conversation_summary", ""),
            error_log=data.get("error_log", []),
            next_actions=data.get("next_actions", []),
            knowledge_references=data.get("knowledge_references", []),
            created_at=created_at,
            version=data.get("version", 1),
            evidence_refs=data.get("evidence_refs", []),
        )

    def to_summary_text(self) -> str:
        """生成摘要文本

        返回：
            人类可读的摘要文本
        """
        parts = []

        if self.task_goal:
            parts.append(f"[目标] {self.task_goal}")

        if self.execution_status:
            status = self.execution_status.get("status", "unknown")
            progress = self.execution_status.get("progress", 0)
            parts.append(f"[状态] {status} ({progress:.0%})")

        if self.node_summary:
            completed = sum(1 for n in self.node_summary if n.get("status") == "completed")
            total = len(self.node_summary)
            parts.append(f"[节点] {completed}/{total} 已完成")

        if self.reflection_summary:
            assessment = self.reflection_summary.get("assessment", "")
            if assessment:
                parts.append(f"[反思] {assessment[:100]}")

        if self.conversation_summary:
            parts.append(f"[对话] {self.conversation_summary[:100]}")

        if self.error_log:
            parts.append(f"[错误] {len(self.error_log)} 个错误")

        if self.next_actions:
            parts.append(f"[下一步] {', '.join(self.next_actions[:3])}")

        # Phase 5: 添加知识引用摘要
        if self.knowledge_references:
            parts.append(f"[知识引用] {len(self.knowledge_references)} 条")

        return " | ".join(parts) if parts else "空上下文"


@dataclass
class CompressionInput:
    """压缩输入

    属性：
    - source_type: 来源类型 (conversation/execution/reflection)
    - workflow_id: 工作流ID
    - raw_data: 原始数据
    - timestamp: 时间戳
    """

    source_type: str  # conversation, execution, reflection
    workflow_id: str
    raw_data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


# ==================== 上下文压缩器 ====================


class ContextCompressor:
    """上下文压缩器

    职责：
    1. 从不同来源提取信息
    2. 压缩成八段结构
    3. 支持增量合并
    4. 与 EvidenceStore 集成

    使用示例：
        compressor = ContextCompressor()
        input_data = CompressionInput(
            source_type="conversation",
            workflow_id="wf_001",
            raw_data={"messages": [...]}
        )
        result = compressor.compress(input_data)
    """

    # 默认最大段落长度
    DEFAULT_MAX_SEGMENT_LENGTH = 500

    def __init__(
        self,
        max_segment_length: int | None = None,
        evidence_store: Any | None = None,
    ):
        """初始化压缩器

        参数：
            max_segment_length: 最大段落长度
            evidence_store: 证据存储（可选）
        """
        self.max_segment_length = max_segment_length or self.DEFAULT_MAX_SEGMENT_LENGTH
        self.evidence_store = evidence_store

    def compress(self, input_data: CompressionInput) -> CompressedContext:
        """压缩输入数据

        参数：
            input_data: 压缩输入

        返回：
            压缩后的上下文
        """
        raw_data = input_data.raw_data
        evidence_refs = []

        # 存储原始数据到证据存储
        if self.evidence_store and raw_data:
            ref_id = self.evidence_store.store(
                raw_data,
                source_id=input_data.workflow_id,
                source_type=input_data.source_type,
            )
            evidence_refs.append(ref_id)

        # 根据来源类型提取不同的信息
        context = CompressedContext(
            workflow_id=input_data.workflow_id,
            evidence_refs=evidence_refs,
        )

        if input_data.source_type == "conversation":
            context.task_goal = self._extract_task_goal(raw_data)
            context.conversation_summary = self._extract_conversation_summary(raw_data)

        elif input_data.source_type == "execution":
            context.execution_status = self._extract_execution_status(raw_data)
            context.node_summary = self._extract_node_summaries(raw_data)
            context.error_log = self._extract_errors(raw_data)
            context.next_actions = self._extract_next_actions(raw_data)

        elif input_data.source_type == "reflection":
            context.reflection_summary = self._extract_reflection_summary(raw_data)
            context.next_actions = self._extract_next_actions(raw_data)

        return context

    def merge(
        self,
        existing: CompressedContext,
        new_input: CompressionInput,
    ) -> CompressedContext:
        """合并新输入到现有上下文

        参数：
            existing: 现有上下文
            new_input: 新输入

        返回：
            合并后的上下文
        """
        # 先压缩新输入
        new_context = self.compress(new_input)

        # 创建合并后的上下文
        merged = CompressedContext(
            workflow_id=existing.workflow_id,
            version=existing.version + 1,
            evidence_refs=existing.evidence_refs + new_context.evidence_refs,
        )

        # 合并各段
        merged.task_goal = new_context.task_goal or existing.task_goal

        # 执行状态：使用新的
        merged.execution_status = (
            new_context.execution_status
            if new_context.execution_status
            else existing.execution_status
        )

        # 节点摘要：合并，更新已有节点
        merged.node_summary = self._merge_node_summaries(
            existing.node_summary, new_context.node_summary
        )

        # 决策历史：追加
        merged.decision_history = existing.decision_history + new_context.decision_history

        # 反思摘要：使用新的（如果有）
        merged.reflection_summary = (
            new_context.reflection_summary
            if new_context.reflection_summary
            else existing.reflection_summary
        )

        # 对话摘要：保留现有的（除非新的更完整）
        merged.conversation_summary = (
            new_context.conversation_summary
            if new_context.conversation_summary
            else existing.conversation_summary
        )

        # 错误日志：追加
        merged.error_log = existing.error_log + new_context.error_log

        # 下一步行动：使用新的
        merged.next_actions = (
            new_context.next_actions if new_context.next_actions else existing.next_actions
        )

        return merged

    def _merge_node_summaries(
        self,
        existing: list[dict[str, Any]],
        new: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """合并节点摘要

        参数：
            existing: 现有节点摘要
            new: 新节点摘要

        返回：
            合并后的节点摘要
        """
        # 创建节点ID到摘要的映射
        merged = {n.get("node_id"): n for n in existing}

        # 更新或添加新节点
        for node in new:
            node_id = node.get("node_id")
            if node_id:
                merged[node_id] = node

        return list(merged.values())

    # ==================== 提取方法 ====================

    def _extract_task_goal(self, raw_data: dict[str, Any]) -> str:
        """提取任务目标

        参数：
            raw_data: 原始数据

        返回：
            任务目标字符串
        """
        # 优先使用显式的 goal 字段
        if "goal" in raw_data:
            return str(raw_data["goal"])

        # 从 entities 中提取
        entities = raw_data.get("entities", {})
        if entities:
            action = entities.get("action", "")
            target = entities.get("target", "")
            if action or target:
                return f"{action}{target}".strip()

        # 从用户消息中提取
        messages = raw_data.get("messages", [])
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if content:
                    # 截取第一句话作为目标
                    return self._truncate(content, 100)

        return ""

    def _extract_execution_status(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """提取执行状态

        参数：
            raw_data: 原始数据

        返回：
            执行状态字典
        """
        status = {}

        if "workflow_status" in raw_data:
            status["status"] = raw_data["workflow_status"]

        if "progress" in raw_data:
            status["progress"] = raw_data["progress"]

        if "nodes_total" in raw_data:
            status["nodes_total"] = raw_data["nodes_total"]

        if "nodes_completed" in raw_data:
            status["nodes_completed"] = raw_data["nodes_completed"]

        # 从 executed_nodes 计算进度
        executed_nodes = raw_data.get("executed_nodes", [])
        if executed_nodes and "nodes_completed" not in status:
            completed = sum(1 for n in executed_nodes if n.get("status") == "completed")
            status["nodes_completed"] = completed

        return status

    def _extract_node_summaries(self, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """提取节点摘要

        参数：
            raw_data: 原始数据

        返回：
            节点摘要列表
        """
        summaries = []
        executed_nodes = raw_data.get("executed_nodes", [])

        for node in executed_nodes:
            summary = {
                "node_id": node.get("node_id"),
                "type": node.get("type"),
                "status": node.get("status"),
            }

            # 压缩输出
            output = node.get("output")
            if output:
                if isinstance(output, dict):
                    content = output.get("content", "")
                    if content:
                        summary["output_summary"] = self._truncate(str(content), 150)
                else:
                    summary["output_summary"] = self._truncate(str(output), 150)

            # 添加重试信息
            if "retry_count" in node:
                summary["retry_count"] = node["retry_count"]

            summaries.append(summary)

        return summaries

    def _extract_errors(self, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """提取错误信息

        参数：
            raw_data: 原始数据

        返回：
            错误列表
        """
        errors = []

        # 从显式错误列表提取
        error_list = raw_data.get("errors", [])
        for err in error_list:
            errors.append(
                {
                    "node_id": err.get("node_id"),
                    "error": err.get("error"),
                    "retryable": err.get("retryable", False),
                }
            )

        # 从失败节点提取
        executed_nodes = raw_data.get("executed_nodes", [])
        for node in executed_nodes:
            if node.get("status") == "failed" and node.get("error"):
                # 避免重复
                node_id = node.get("node_id")
                if not any(e.get("node_id") == node_id for e in errors):
                    errors.append(
                        {
                            "node_id": node_id,
                            "error": node.get("error"),
                            "retryable": node.get("retryable", True),
                        }
                    )

        return errors

    def _extract_reflection_summary(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """提取反思摘要

        参数：
            raw_data: 原始数据

        返回：
            反思摘要字典
        """
        summary = {}

        if "assessment" in raw_data:
            summary["assessment"] = raw_data["assessment"]

        if "confidence" in raw_data:
            summary["confidence"] = raw_data["confidence"]

        if "should_retry" in raw_data:
            summary["should_retry"] = raw_data["should_retry"]

        if "issues" in raw_data:
            summary["issues"] = raw_data["issues"]

        if "recommendations" in raw_data:
            summary["recommendations"] = raw_data["recommendations"]

        return summary

    def _extract_conversation_summary(self, raw_data: dict[str, Any]) -> str:
        """提取对话摘要

        参数：
            raw_data: 原始数据

        返回：
            对话摘要字符串
        """
        messages = raw_data.get("messages", [])
        if not messages:
            return ""

        # 简单策略：提取用户消息的核心内容
        user_messages = [msg.get("content", "") for msg in messages if msg.get("role") == "user"]

        if user_messages:
            # 合并并截断
            combined = " ".join(user_messages)
            return self._truncate(combined, self.max_segment_length)

        return ""

    def _extract_decision_history(self, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """提取决策历史

        参数：
            raw_data: 原始数据

        返回：
            决策历史列表
        """
        decisions = raw_data.get("decisions", [])
        return [
            {
                "decision_type": d.get("decision_type"),
                "choice": d.get("choice"),
                "reason": d.get("reason"),
                "timestamp": d.get("timestamp"),
            }
            for d in decisions
        ]

    def _extract_next_actions(self, raw_data: dict[str, Any]) -> list[str]:
        """提取下一步行动

        参数：
            raw_data: 原始数据

        返回：
            下一步行动列表
        """
        actions = []

        # 从待执行节点
        pending = raw_data.get("pending_nodes", [])
        for node_id in pending[:3]:  # 最多3个
            actions.append(f"执行节点 {node_id}")

        # 从反思建议
        reflection = raw_data.get("reflection", {})
        recommendations = reflection.get("recommendations", [])
        actions.extend(recommendations[:3])  # 最多3个

        # 从显式 recommendations
        if "recommendations" in raw_data:
            actions.extend(raw_data["recommendations"][:3])

        # 去重
        seen = set()
        unique_actions = []
        for action in actions:
            if action not in seen:
                seen.add(action)
                unique_actions.append(action)

        return unique_actions[:5]  # 最多5个

    def _truncate(self, text: str, max_length: int) -> str:
        """截断文本

        参数：
            text: 原始文本
            max_length: 最大长度

        返回：
            截断后的文本
        """
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."


# ==================== 快照管理器 ====================


class ContextSnapshotManager:
    """上下文快照管理器

    职责：
    1. 保存压缩上下文的快照
    2. 按ID或工作流检索快照
    3. 管理快照生命周期

    使用示例：
        manager = ContextSnapshotManager()
        snapshot_id = manager.save_snapshot(context)
        retrieved = manager.get_snapshot(snapshot_id)
    """

    def __init__(self):
        """初始化快照管理器"""
        self._snapshots: dict[str, CompressedContext] = {}
        self._workflow_index: dict[str, list[str]] = {}  # workflow_id -> [snapshot_ids]
        self._lock = threading.Lock()

    def save_snapshot(self, context: CompressedContext) -> str:
        """保存快照

        参数：
            context: 压缩上下文

        返回：
            快照ID
        """
        with self._lock:
            snapshot_id = f"snap_{uuid4().hex[:12]}"

            # 存储快照
            self._snapshots[snapshot_id] = context

            # 更新工作流索引
            workflow_id = context.workflow_id
            if workflow_id not in self._workflow_index:
                self._workflow_index[workflow_id] = []
            self._workflow_index[workflow_id].append(snapshot_id)

            return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> CompressedContext | None:
        """获取快照

        参数：
            snapshot_id: 快照ID

        返回：
            压缩上下文，不存在返回None
        """
        return self._snapshots.get(snapshot_id)

    def list_snapshots(self, workflow_id: str) -> list[CompressedContext]:
        """列出工作流的所有快照

        参数：
            workflow_id: 工作流ID

        返回：
            快照列表
        """
        snapshot_ids = self._workflow_index.get(workflow_id, [])
        return [self._snapshots[sid] for sid in snapshot_ids if sid in self._snapshots]

    def get_latest_snapshot(self, workflow_id: str) -> CompressedContext | None:
        """获取最新快照

        参数：
            workflow_id: 工作流ID

        返回：
            最新的压缩上下文，不存在返回None
        """
        snapshots = self.list_snapshots(workflow_id)
        if not snapshots:
            return None

        # 按版本号排序，返回最新的
        return max(snapshots, key=lambda s: s.version)

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """删除快照

        参数：
            snapshot_id: 快照ID

        返回：
            是否删除成功
        """
        with self._lock:
            if snapshot_id not in self._snapshots:
                return False

            context = self._snapshots.pop(snapshot_id)

            # 更新索引
            workflow_id = context.workflow_id
            if workflow_id in self._workflow_index:
                self._workflow_index[workflow_id] = [
                    sid for sid in self._workflow_index[workflow_id] if sid != snapshot_id
                ]

            return True

    def clear_workflow_snapshots(self, workflow_id: str) -> int:
        """清除工作流的所有快照

        参数：
            workflow_id: 工作流ID

        返回：
            删除的快照数量
        """
        with self._lock:
            snapshot_ids = self._workflow_index.get(workflow_id, [])
            count = 0

            for sid in snapshot_ids:
                if sid in self._snapshots:
                    del self._snapshots[sid]
                    count += 1

            if workflow_id in self._workflow_index:
                del self._workflow_index[workflow_id]

            return count


# 导出
__all__ = [
    "CompressedContext",
    "CompressionInput",
    "ContextCompressor",
    "ContextSnapshotManager",
]
