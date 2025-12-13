"""ConversationAgent control flow module.

This module extracts control flow planning logic out of
`src/domain/agents/conversation_agent.py` (P1-6 Phase 5).

Scope:
- Control flow extraction: `_extract_control_flow_by_rules` (~60 lines)
- Control node building: `build_control_nodes` (~77 lines)

Design principles:
- Keep `ConversationAgent` public API and behavior 100% backward compatible
- Use a Mixin to avoid circular imports and keep `conversation_agent.py` as the stable entry point
- Pure functions: no dependency on agent state (only take parameters, return results)
- Pure move (no logic changes): this file is a verbatim relocation of existing implementations

Host contract: No runtime dependencies on host attributes (pure functions only).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.agents.control_flow_ir import ControlFlowIR
    from src.domain.agents.node_definition import NodeDefinition
    from src.domain.agents.workflow_plan import EdgeDefinition


# Import RULE_BASED_EXTRACTION_CONFIDENCE constant from conversation_agent
# This is a module-level constant, safe to import
RULE_BASED_EXTRACTION_CONFIDENCE = 0.6
"""基于规则提取的置信度（较低，因为不如LLM准确）"""


class ConversationAgentControlFlowMixin:
    """Control flow planning mixin for ConversationAgent (P1-6 Phase 5).

    This mixin encapsulates control flow extraction and node building
    that was previously inline in ConversationAgent.

    Both methods are pure functions (no agent state dependencies):
    - _extract_control_flow_by_rules: Parse text for control flow patterns
    - build_control_nodes: Convert ControlFlowIR to NodeDefinition/EdgeDefinition
    """

    # =========================================================================
    # Phase 17: Control Flow Planning (Priority 3)
    # =========================================================================

    def _extract_control_flow_by_rules(self, text: str) -> ControlFlowIR:
        """基于规则从文本中提取控制流

        使用简单的关键词匹配识别决策点和循环，支持中英文输入。
        这是一个快速回退策略，当 LLM 分析失败时使用。

        参数：
            text: 用户输入的目标描述

        返回：
            ControlFlowIR 实例

        规则：
            - 检测中文："如果"、"否则"、"循环"、"遍历"
            - 检测英文："if"、"else"、"for each"、"loop"

        示例：
            "如果数据质量大于0.8则分析" → 生成 DecisionPoint
            "遍历所有数据集" → 生成 LoopSpec
        """
        from uuid import uuid4

        from src.domain.agents.control_flow_ir import (
            ControlFlowIR,
            DecisionPoint,
            LoopSpec,
        )

        ir = ControlFlowIR()
        lowered = text.lower()

        # 检测决策点（中英文）
        if "如果" in text or "if" in lowered:
            ir.decisions.append(
                DecisionPoint(
                    id=str(uuid4()),
                    description="conditional_branch",
                    expression="...",  # 占位符，实际需要 LLM 或更复杂的解析
                    branches=[],
                    confidence=RULE_BASED_EXTRACTION_CONFIDENCE,  # 规则识别置信度较低
                    source_text=text,
                )
            )

        # 检测循环（中英文）
        loop_keywords = ["循环", "遍历", "for each", "foreach", "for every", "迭代"]
        if any(keyword in text or keyword in lowered for keyword in loop_keywords):
            ir.loops.append(
                LoopSpec(
                    id=str(uuid4()),
                    description="loop_over_items",
                    collection="items",  # 默认集合名
                    loop_variable="item",
                    loop_type="for_each",
                    confidence=RULE_BASED_EXTRACTION_CONFIDENCE,
                    source_text=text,
                )
            )

        return ir

    def build_control_nodes(
        self,
        control_ir: ControlFlowIR,
        existing_nodes: list[NodeDefinition],
        existing_edges: list[EdgeDefinition],
    ) -> tuple[list[NodeDefinition], list[EdgeDefinition]]:
        """将 ControlFlowIR 转换为 NodeDefinition + EdgeDefinition

        参数：
            control_ir: 控制流 IR
            existing_nodes: 现有节点列表（用于避免ID冲突）
            existing_edges: 现有边列表

        返回：
            (新节点列表, 新边列表)

        转换规则：
            - DecisionPoint → NodeType.CONDITION 节点
            - LoopSpec → NodeType.LOOP 节点
            - 分支 → EdgeDefinition with condition

        示例：
            DecisionPoint(expression="x > 0", branches=[...])
            → NodeDefinition(node_type=CONDITION, config={"expression": "x > 0"})
        """
        from src.domain.agents.node_definition import NodeDefinition, NodeType
        from src.domain.agents.workflow_plan import EdgeDefinition

        if not control_ir or control_ir.is_empty():
            return [], []

        new_nodes: list[NodeDefinition] = []
        new_edges: list[EdgeDefinition] = []

        # 转换决策点
        for decision in control_ir.decisions:
            node_name = decision.description or f"decision_{decision.id}"
            condition_node = NodeDefinition(
                node_type=NodeType.CONDITION,
                name=node_name,
                config={"expression": decision.expression},
            )
            new_nodes.append(condition_node)

            # 转换分支为边
            for branch in decision.branches:
                target = branch.target_task_id or branch.label
                if not target:
                    continue
                new_edges.append(
                    EdgeDefinition(
                        source_node=node_name,
                        target_node=target,
                        condition=branch.expression or branch.label,
                    )
                )

        # 转换循环
        for loop in control_ir.loops:
            loop_name = loop.description or f"loop_{loop.id}"
            loop_node = NodeDefinition(
                node_type=NodeType.LOOP,
                name=loop_name,
                config={
                    "collection_field": loop.collection,
                    "loop_type": loop.loop_type,
                    "loop_variable": loop.loop_variable,
                    "condition": loop.condition,
                },
            )
            new_nodes.append(loop_node)

            # 循环体任务边
            for task_id in loop.body_task_ids:
                new_edges.append(EdgeDefinition(source_node=loop_name, target_node=task_id))

        return new_nodes, new_edges
