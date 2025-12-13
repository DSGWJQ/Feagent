"""ConversationAgent workflow module.

This module extracts workflow-planning concerns out of
`src/domain/agents/conversation_agent.py` (P1-6 Phase 3).

Scope:
- Workflow planning: `create_workflow_plan`
- Node decomposition: `decompose_to_nodes`
- Workflow replanning: `replan_workflow`
- Plan creation + decision event publishing: `create_workflow_plan_and_publish`

Design principles:
- Keep `ConversationAgent` public API and behavior 100% backward compatible
- Use a Mixin to avoid circular imports and keep `conversation_agent.py` as the stable entry point
- Depend only on minimal host attributes/methods (documented below)
- Pure move (no logic changes): this file is a verbatim relocation of existing implementations

Host contract (expected on the concrete ConversationAgent):
- llm: ConversationAgentLLM-compatible object with plan_workflow/decompose_to_nodes
- event_bus: EventBus | None
- session_context: SessionContext (provides session_id)
- get_context_for_reasoning(): returns dict[str, Any]
- _stage_decision_record(record: dict): stage decision for batch commit (P0-2 Phase 2)
- _flush_staged_state(): flush staged decisions to session_context (P0-2 Phase 2)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from src.domain.agents.conversation_agent_events import DecisionMadeEvent
from src.domain.agents.conversation_agent_models import DecisionType

if TYPE_CHECKING:
    from src.domain.agents.conversation_agent_protocols import EventBusProtocol, WorkflowHost
    from src.domain.agents.node_definition import NodeDefinition
    from src.domain.agents.workflow_plan import WorkflowPlan
    from src.domain.services.context_manager import SessionContext


class ConversationAgentWorkflowMixin:
    """Workflow planning mixin for ConversationAgent (P1-6 Phase 3).

    This mixin encapsulates workflow planning, node decomposition, and
    replanning logic that was previously inline in ConversationAgent.

    Host expectations (attributes):
    - llm: Must provide async methods plan_workflow/decompose_to_nodes/replan_workflow
    - event_bus: Optional EventBus for publishing DecisionMadeEvent
    - session_context: SessionContext for decision recording

    Host expectations (methods):
    - get_context_for_reasoning(): Returns dict containing conversation history,
      goals, decision history, etc.

    Type contract: Host must satisfy WorkflowHost protocol (implemented).
    """

    # --- Host-provided attributes (runtime expectations) ---
    # Type: WorkflowHost protocol (see conversation_agent_protocols.py)
    llm: Any
    event_bus: EventBusProtocol | None
    session_context: SessionContext

    def get_context_for_reasoning(self) -> dict[str, Any]:  # pragma: no cover
        """Get reasoning context from host.

        Must be provided by concrete ConversationAgent.
        """
        raise NotImplementedError("Host must implement get_context_for_reasoning()")

    def _stage_decision_record(self, record: dict[str, Any]) -> None:  # pragma: no cover
        """Stage decision record for batch commit (P0-2 Phase 2).

        Must be provided by concrete ConversationAgent.
        """
        raise NotImplementedError("Host must implement _stage_decision_record()")

    async def _flush_staged_state(self) -> None:  # pragma: no cover
        """Flush staged state updates (P0-2 Phase 2).

        Must be provided by concrete ConversationAgent.
        """
        raise NotImplementedError("Host must implement _flush_staged_state()")

    # =========================================================================
    # Phase 8: Workflow Planning Capabilities
    # =========================================================================

    async def create_workflow_plan(self: WorkflowHost, goal: str) -> WorkflowPlan:
        """根据目标创建工作流规划（Phase 8 新增）

        使用LLM根据用户目标生成完整的工作流计划，包括节点定义和边定义。
        支持父子节点结构和策略传播。

        参数：
            goal: 用户目标描述

        返回：
            WorkflowPlan 实例，包含节点、边、验证状态等

        抛出：
            ValueError: 如果规划验证失败或存在循环依赖

        示例：
            plan = await agent.create_workflow_plan("分析数据集并生成报告")
        """
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        # 获取上下文
        context = self.get_context_for_reasoning()
        context["goal"] = goal

        # 调用 LLM 规划工作流
        plan_data = await self.llm.plan_workflow(goal, context)

        # 转换节点（支持父节点）
        nodes = []
        for node_data in plan_data.get("nodes", []):
            node_type_str = node_data.get("type", "generic")
            try:
                node_type = NodeType(node_type_str.lower())
            except ValueError:
                node_type = NodeType.GENERIC

            node = NodeDefinition(
                node_type=node_type,
                name=node_data.get("name", ""),
                code=node_data.get("code"),
                prompt=node_data.get("prompt"),
                url=node_data.get("url"),
                method=node_data.get("method", "GET"),
                query=node_data.get("query"),
                config=node_data.get("config", {}),
                # Phase 9: 父节点策略支持
                error_strategy=node_data.get("error_strategy"),
                resource_limits=node_data.get("resource_limits", {}),
            )

            # Phase 9: 如果有子节点，添加并传播策略
            if "children" in node_data and node_data["children"]:
                for child_data in node_data["children"]:
                    child_type_str = child_data.get("type", "python")
                    try:
                        child_type = NodeType(child_type_str.lower())
                    except ValueError:
                        child_type = NodeType.PYTHON

                    child = NodeDefinition(
                        node_type=child_type,
                        name=child_data.get("name", ""),
                        code=child_data.get("code"),
                        prompt=child_data.get("prompt"),
                        url=child_data.get("url"),
                        method=child_data.get("method", "GET"),
                        query=child_data.get("query"),
                        config=child_data.get("config", {}),
                    )
                    node.add_child(child)

                # 传播策略到子节点
                if node.error_strategy or node.resource_limits:
                    node.propagate_strategy_to_children()

            nodes.append(node)

        # 转换边
        edges = []
        for edge_data in plan_data.get("edges", []):
            edge = EdgeDefinition(
                source_node=edge_data.get("source", edge_data.get("source_node", "")),
                target_node=edge_data.get("target", edge_data.get("target_node", "")),
                condition=edge_data.get("condition"),
            )
            edges.append(edge)

        # 创建规划
        plan = WorkflowPlan(
            name=plan_data.get("name", f"Plan for: {goal[:30]}"),
            description=plan_data.get("description", ""),
            goal=goal,
            nodes=nodes,
            edges=edges,
        )

        # 验证规划
        errors = plan.validate()
        if errors:
            raise ValueError(f"工作流规划验证失败: {'; '.join(errors)}")

        # 检测循环依赖
        if plan.has_circular_dependency():
            raise ValueError("工作流存在循环依赖 (Circular dependency detected)")

        return plan

    async def decompose_to_nodes(self: WorkflowHost, goal: str) -> list[NodeDefinition]:
        """将目标分解为节点定义列表（Phase 8 新增）

        调用LLM将用户目标分解为一系列可执行的节点定义。
        支持父子节点结构和策略传播。

        参数：
            goal: 用户目标描述

        返回：
            NodeDefinition 列表，每个节点包含类型、代码、配置等信息

        示例：
            nodes = await agent.decompose_to_nodes("处理CSV数据")
        """
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        # 调用 LLM 分解
        node_dicts = await self.llm.decompose_to_nodes(goal)

        # 转换为 NodeDefinition（支持父节点）
        nodes = []
        for node_data in node_dicts:
            node_type_str = node_data.get("type", "generic")
            try:
                node_type = NodeType(node_type_str.lower())
            except ValueError:
                node_type = NodeType.GENERIC

            node = NodeDefinition(
                node_type=node_type,
                name=node_data.get("name", ""),
                code=node_data.get("code"),
                prompt=node_data.get("prompt"),
                url=node_data.get("url"),
                query=node_data.get("query"),
                config=node_data.get("config", {}),
                # Phase 9: 父节点策略支持
                error_strategy=node_data.get("error_strategy"),
                resource_limits=node_data.get("resource_limits", {}),
            )

            # Phase 9: 如果有子节点，添加并传播策略
            if "children" in node_data and node_data["children"]:
                for child_data in node_data["children"]:
                    child_type_str = child_data.get("type", "python")
                    try:
                        child_type = NodeType(child_type_str.lower())
                    except ValueError:
                        child_type = NodeType.PYTHON

                    child = NodeDefinition(
                        node_type=child_type,
                        name=child_data.get("name", ""),
                        code=child_data.get("code"),
                        prompt=child_data.get("prompt"),
                        url=child_data.get("url"),
                        query=child_data.get("query"),
                        config=child_data.get("config", {}),
                    )
                    node.add_child(child)

                # 传播策略到子节点
                if node.error_strategy or node.resource_limits:
                    node.propagate_strategy_to_children()

            nodes.append(node)

        return nodes

    async def create_workflow_plan_and_publish(self: WorkflowHost, goal: str) -> WorkflowPlan:
        """创建工作流规划并发布决策事件（Phase 8 新增）

        组合create_workflow_plan和事件发布逻辑，便于上层调用。

        参数：
            goal: 用户目标描述

        返回：
            WorkflowPlan 实例

        副作用：
        - 发布DecisionMadeEvent到event_bus（如果存在）
        - 记录决策到session_context.decision_history

        示例：
            plan = await agent.create_workflow_plan_and_publish("数据分析任务")
        """
        plan = await self.create_workflow_plan(goal)

        # 发布决策事件
        if self.event_bus:
            event = DecisionMadeEvent(
                source="conversation_agent",
                decision_type=DecisionType.CREATE_WORKFLOW_PLAN.value,
                decision_id=plan.id,
                payload=plan.to_dict(),
                confidence=1.0,
            )
            await self.event_bus.publish(event)

        # 记录决策 - 使用staged机制，避免绕过批量提交路径
        self._stage_decision_record(
            {
                "id": plan.id,
                "type": DecisionType.CREATE_WORKFLOW_PLAN.value,
                "payload": {"plan_name": plan.name, "node_count": len(plan.nodes)},
                "timestamp": datetime.now().isoformat(),
            }
        )
        await self._flush_staged_state()

        return plan

    async def replan_workflow(
        self: WorkflowHost,
        original_goal: str,
        failed_node_id: str,
        failure_reason: str,
        execution_context: dict[str, Any],
    ) -> dict[str, Any]:
        """根据失败信息重新规划工作流（Phase 13 新增）

        当工作流执行失败时，调用LLM分析失败原因并生成新的执行计划。
        如果LLM不支持replan_workflow方法，则回退到普通的plan_workflow。

        参数：
            original_goal: 原始目标描述
            failed_node_id: 失败的节点ID
            failure_reason: 失败原因描述
            execution_context: 执行上下文（已完成的节点和输出）

        返回：
            重新规划的工作流字典（LLM raw plan dict，非WorkflowPlan对象）

        示例：
            plan_dict = await agent.replan_workflow(
                original_goal="分析数据",
                failed_node_id="node_2",
                failure_reason="数据格式不匹配",
                execution_context={"completed_nodes": ["node_1"]}
            )
        """
        # 构建上下文
        context = self.get_context_for_reasoning()
        context["original_goal"] = original_goal
        context["failed_node_id"] = failed_node_id
        context["failure_reason"] = failure_reason
        context["execution_context"] = execution_context

        # 调用 LLM 重新规划
        if hasattr(self.llm, "replan_workflow"):
            plan = await self.llm.replan_workflow(
                goal=original_goal,
                failed_node_id=failed_node_id,
                failure_reason=failure_reason,
                execution_context=execution_context,
            )
        else:
            # 回退到普通的工作流规划
            plan = await self.llm.plan_workflow(original_goal, context)

        return plan
