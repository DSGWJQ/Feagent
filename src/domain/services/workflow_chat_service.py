"""WorkflowChatService - 工作流对话服务

业务定义：
- 解析用户的自然语言消息
- 生成工作流修改指令
- 应用修改到工作流实体

设计原则：
- 纯 Python 实现，不依赖框架（DDD 要求）
- 使用 LLM 解析用户意图
- 返回修改后的工作流和AI回复消息
"""

import json
from typing import Any

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.workflow_chat_llm import WorkflowChatLLM
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class WorkflowChatService:
    """工作流对话服务

    职责：
    - 解析用户消息，理解用户意图
    - 生成工作流修改指令（添加/删除/修改节点和边）
    - 应用修改到工作流实体
    - 生成AI回复消息

    为什么是 Domain Service？
    - 涉及多个实体的协调（Workflow、Node、Edge）
    - 包含复杂的业务逻辑（LLM 调用、意图解析）
    - 不属于任何单一实体的职责
    """

    def __init__(self, llm: WorkflowChatLLM):
        """初始化服务

        参数：
            llm: LangChain LLM 实例（用于解析用户意图）
        """
        self.llm = llm

    def process_message(self, workflow: Workflow, user_message: str) -> tuple[Workflow, str]:
        """处理用户消息，修改工作流

        参数：
            workflow: 当前工作流实体
            user_message: 用户消息

        返回：
            (修改后的工作流, AI回复消息)

        抛出：
            DomainError: 当消息为空或LLM调用失败时
        """
        # 验证输入
        if not user_message or not user_message.strip():
            raise DomainError("消息不能为空")

        # 1. 构造提示词
        system_prompt = self._build_system_prompt(workflow)
        user_prompt = self._build_user_prompt(user_message)

        # 2. 调用 LLM 解析用户意图
        try:
            result = self.llm.generate_modifications(system_prompt, user_prompt)
        except Exception as e:
            raise DomainError(f"LLM 调用失败: {str(e)}") from e

        if not isinstance(result, dict):
            raise DomainError("LLM 响应格式无效")

        # 3. 应用修改到工作流
        modified_workflow = self._apply_modifications(workflow, result)

        # 4. 生成 AI 回复消息
        ai_message = result.get("ai_message", "已完成修改")

        return modified_workflow, ai_message

    def _build_system_prompt(self, workflow: Workflow) -> str:
        """构造系统提示词

        参数：
            workflow: 当前工作流

        返回：
            系统提示词
        """
        # 序列化当前工作流状态
        workflow_state = {
            "name": workflow.name,
            "description": workflow.description,
            "nodes": [
                {
                    "id": node.id,
                    "type": node.type.value,
                    "name": node.name,
                    "config": node.config,
                    "position": {"x": node.position.x, "y": node.position.y},
                }
                for node in workflow.nodes
            ],
            "edges": [
                {
                    "id": edge.id,
                    "source": edge.source_node_id,
                    "target": edge.target_node_id,
                    "condition": edge.condition,
                }
                for edge in workflow.edges
            ],
        }

        return f"""你是一个工作流编辑助手。用户会告诉你如何修改工作流，你需要：

1. 理解用户意图
2. 生成工作流修改指令
3. 返回 JSON 格式的修改指令

当前工作流状态：
```json
{json.dumps(workflow_state, ensure_ascii=False, indent=2)}
```

支持的节点类型：
- start: 开始节点
- end: 结束节点
- http: HTTP 请求节点
- transform: 数据转换节点
- database: 数据库操作节点
- llm: LLM 调用节点
- python: Python 代码执行节点

返回格式（JSON）：
{{
  "action": "add_node" | "delete_node" | "add_edge" | "delete_edge" | "modify_node",
  "nodes_to_add": [
    {{
      "type": "http",
      "name": "节点名称",
      "config": {{}},
      "position": {{"x": 100, "y": 100}}
    }}
  ],
  "nodes_to_delete": ["node_id"],
  "edges_to_add": [
    {{
      "source": "node_id_1",
      "target": "node_id_2"
    }}
  ],
  "edges_to_delete": ["edge_id"],
  "ai_message": "我已经添加了一个HTTP节点用于获取天气数据"
}}

注意：
- 新节点的位置应该合理（避免重叠）
- 添加节点时通常需要同时添加边
- 删除节点时需要同时删除相关的边
- ai_message 应该简洁地描述做了什么修改
"""

    def _build_user_prompt(self, user_message: str) -> str:
        """构造用户提示词

        参数：
            user_message: 用户消息

        返回：
            用户提示词
        """
        return f"""用户请求：{user_message}

请生成修改指令（JSON 格式）。"""

    def _apply_modifications(self, workflow: Workflow, modifications: dict[str, Any]) -> Workflow:
        """应用修改到工作流

        参数：
            workflow: 原工作流
            modifications: 修改指令

        返回：
            修改后的工作流（新实例）
        """
        # 复制工作流（避免修改原实体）
        new_nodes = workflow.nodes.copy()
        new_edges = workflow.edges.copy()

        # 1. 删除节点
        nodes_to_delete = modifications.get("nodes_to_delete", [])
        if nodes_to_delete:
            new_nodes = [node for node in new_nodes if node.id not in nodes_to_delete]
            # 同时删除相关的边
            new_edges = [
                edge
                for edge in new_edges
                if edge.source_node_id not in nodes_to_delete
                and edge.target_node_id not in nodes_to_delete
            ]

        # 2. 添加节点
        nodes_to_add = modifications.get("nodes_to_add", [])
        for node_data in nodes_to_add:
            new_node = Node.create(
                type=NodeType(node_data["type"]),
                name=node_data["name"],
                config=node_data.get("config", {}),
                position=Position(x=node_data["position"]["x"], y=node_data["position"]["y"]),
            )
            new_nodes.append(new_node)

        # 3. 删除边
        edges_to_delete = modifications.get("edges_to_delete", [])
        if edges_to_delete:
            new_edges = [edge for edge in new_edges if edge.id not in edges_to_delete]

        # 4. 添加边
        edges_to_add = modifications.get("edges_to_add", [])
        for edge_data in edges_to_add:
            source = edge_data["source"]
            target = edge_data["target"]

            # 验证：跳过无效的边
            if not source or not target:
                continue  # 跳过空节点ID
            if source == target:
                continue  # 跳过自连接

            # 验证：检查节点是否存在
            node_ids = {node.id for node in new_nodes}
            if source not in node_ids or target not in node_ids:
                continue  # 跳过不存在的节点

            # 验证：检查边是否已存在
            existing_edges = {(edge.source_node_id, edge.target_node_id) for edge in new_edges}
            if (source, target) in existing_edges:
                continue  # 跳过重复的边

            try:
                new_edge = Edge.create(
                    source_node_id=source,
                    target_node_id=target,
                    condition=edge_data.get("condition"),
                )
                new_edges.append(new_edge)
            except DomainError:
                # 如果创建边失败，跳过这条边
                continue

        # 5. 创建新的工作流实体
        modified_workflow = Workflow(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            nodes=new_nodes,
            edges=new_edges,
            status=workflow.status,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

        return modified_workflow
