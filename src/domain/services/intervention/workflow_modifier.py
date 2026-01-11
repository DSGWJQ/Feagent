"""工作流修改器

Phase 34.15: 从 intervention_system.py 提取 WorkflowModifier
"""

from __future__ import annotations

from typing import Any

from .logger import InterventionLogger
from .models import ModificationResult, NodeReplacementRequest, ValidationResult


class WorkflowModifier:
    """工作流修改器

    提供修改工作流定义的接口。
    """

    def __init__(self, logger: InterventionLogger | None = None):
        """初始化

        参数：
            logger: 干预日志记录器
        """
        self._logger = logger or InterventionLogger()

    def replace_node(
        self,
        workflow_definition: dict[str, Any],
        request: NodeReplacementRequest,
    ) -> ModificationResult:
        """替换节点

        参数：
            workflow_definition: 工作流定义
            request: 替换请求

        返回：
            修改结果
        """
        nodes = workflow_definition.get("nodes", [])

        # 查找原节点
        original_index = None
        for i, node in enumerate(nodes):
            if node.get("id") == request.original_node_id:
                original_index = i
                break

        if original_index is None:
            return ModificationResult(
                success=False,
                error=f"Node not found: {request.original_node_id}",
            )

        # 创建修改后的工作流
        modified_workflow = workflow_definition.copy()
        modified_nodes = nodes.copy()

        # 创建替换节点
        if request.replacement_node_config is None:
            return self.remove_node(workflow_definition, request)

        replacement_node = request.replacement_node_config.copy()
        if "id" not in replacement_node:
            replacement_node["id"] = request.original_node_id  # 保持原 ID
        replacement_node_id = replacement_node["id"]

        # 替换节点
        modified_nodes[original_index] = replacement_node
        modified_workflow["nodes"] = modified_nodes

        # 如果节点 ID 变化，更新边
        if replacement_node_id != request.original_node_id:
            edges = modified_workflow.get("edges", [])
            modified_edges = []
            for edge in edges:
                new_edge = edge.copy()
                if new_edge.get("from") == request.original_node_id:
                    new_edge["from"] = replacement_node_id
                if new_edge.get("to") == request.original_node_id:
                    new_edge["to"] = replacement_node_id
                modified_edges.append(new_edge)
            modified_workflow["edges"] = modified_edges

        # 记录日志
        self._logger.log_node_replacement(
            workflow_id=request.workflow_id,
            original_node_id=request.original_node_id,
            replacement_node_id=replacement_node_id,
            reason=request.reason,
            session_id=request.session_id,
        )

        return ModificationResult(
            success=True,
            modified_workflow=modified_workflow,
            original_node_id=request.original_node_id,
            replacement_node_id=replacement_node_id,
        )

    def remove_node(
        self,
        workflow_definition: dict[str, Any],
        request: NodeReplacementRequest,
    ) -> ModificationResult:
        """移除节点

        参数：
            workflow_definition: 工作流定义
            request: 移除请求

        返回：
            修改结果
        """
        nodes = workflow_definition.get("nodes", [])

        # 查找原节点
        original_index = None
        for i, node in enumerate(nodes):
            if node.get("id") == request.original_node_id:
                original_index = i
                break

        if original_index is None:
            return ModificationResult(
                success=False,
                error=f"Node not found: {request.original_node_id}",
            )

        # 创建修改后的工作流
        modified_workflow = workflow_definition.copy()
        modified_nodes = [n for n in nodes if n.get("id") != request.original_node_id]
        modified_workflow["nodes"] = modified_nodes

        # 移除相关边
        edges = modified_workflow.get("edges", [])
        modified_edges = [
            e
            for e in edges
            if e.get("from") != request.original_node_id and e.get("to") != request.original_node_id
        ]
        modified_workflow["edges"] = modified_edges

        # 记录日志
        self._logger.log_node_replacement(
            workflow_id=request.workflow_id,
            original_node_id=request.original_node_id,
            replacement_node_id=None,
            reason=request.reason,
            session_id=request.session_id,
        )

        return ModificationResult(
            success=True,
            modified_workflow=modified_workflow,
            original_node_id=request.original_node_id,
            replacement_node_id=None,
        )

    def validate_workflow(self, workflow_definition: dict[str, Any]) -> ValidationResult:
        """验证工作流

        参数：
            workflow_definition: 工作流定义

        返回：
            验证结果
        """
        errors = []

        # 检查节点
        nodes = workflow_definition.get("nodes", [])
        if not nodes:
            errors.append("Workflow has no nodes")

        # 检查节点 ID 唯一性
        node_ids = [n.get("id") for n in nodes]
        if len(node_ids) != len(set(node_ids)):
            errors.append("Duplicate node IDs found")

        # 检查边的有效性
        edges = workflow_definition.get("edges", [])
        for edge in edges:
            from_id = edge.get("from")
            to_id = edge.get("to")
            if from_id not in node_ids:
                errors.append(f"Edge references non-existent node: {from_id}")
            if to_id not in node_ids:
                errors.append(f"Edge references non-existent node: {to_id}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )


__all__ = ["WorkflowModifier"]
