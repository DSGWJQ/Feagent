"""WorkflowChatServiceWithRAG - 集成RAG的工作流对话服务

在原有WorkflowChatService基础上集成RAG（检索增强生成）能力
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


class WorkflowChatServiceWithRAG:
    """集成RAG的工作流对话服务

    职责：
    - 解析用户消息，理解用户意图
    - 从知识库检索相关信息
    - 基于检索结果生成工作流修改指令
    - 应用修改到工作流实体
    - 生成AI回复消息（包含引用来源）
    """

    def __init__(
        self,
        llm: WorkflowChatLLM,
        rag_service=None,  # 避免循环导入
    ):
        """初始化服务

        参数：
            llm: LangChain LLM 实例
            rag_service: RAG服务实例（可选）
        """
        self.llm = llm
        self.rag_service = rag_service

    def set_rag_service(self, rag_service) -> None:
        """设置RAG服务（延迟设置避免循环导入）

        参数：
            rag_service: RAG服务实例
        """
        self.rag_service = rag_service

    async def process_message_async(
        self,
        workflow: Workflow,
        user_message: str,
        use_rag: bool = True,
    ) -> tuple[Workflow, str]:
        """异步处理用户消息（推荐使用）

        参数：
            workflow: 当前工作流实体
            user_message: 用户消息
            use_rag: 是否使用RAG功能

        返回：
            (修改后的工作流, AI回复消息)

        抛出：
            DomainError: 当消息为空或LLM调用失败时
        """
        # 验证输入
        if not user_message or not user_message.strip():
            raise DomainError("消息不能为空")

        # 1. 获取RAG上下文（如果启用）
        rag_context = ""
        rag_sources = []
        if use_rag and self.rag_service:
            try:
                # 使用RAG服务检索上下文
                from src.application.services.rag_service import QueryContext

                query_context = QueryContext(
                    query=user_message,
                    workflow_id=workflow.id,
                    max_context_length=2000,  # 控制上下文长度
                    top_k=3,  # 取最相关的3个片段
                )

                # 检索上下文
                retrieved_context = await self.rag_service.retrieve_context(query_context)
                rag_context = retrieved_context.formatted_context
                rag_sources = retrieved_context.sources

            except Exception as e:
                # RAG检索失败时记录日志但不中断流程
                print(f"RAG检索失败，继续使用原有逻辑: {str(e)}")
                rag_context = ""

        # 2. 构造提示词
        system_prompt = self._build_system_prompt(workflow, rag_context)
        user_prompt = self._build_user_prompt(user_message, rag_context)

        # 3. 调用 LLM 解析用户意图
        try:
            # 尝试使用异步方法
            if hasattr(self.llm, "generate_modifications_async"):
                result = await self.llm.generate_modifications_async(system_prompt, user_prompt)
            else:
                # 降级到同步调用
                result = self.llm.generate_modifications(system_prompt, user_prompt)
        except Exception as e:
            raise DomainError(f"LLM 调用失败: {str(e)}") from e

        if not isinstance(result, dict):
            raise DomainError("LLM 响应格式无效")

        # 4. 应用修改到工作流
        modified_workflow = self._apply_modifications(workflow, result)

        # 5. 生成 AI 回复消息
        ai_message = result.get("ai_message", "已完成修改")

        # 6. 如果有RAG源，添加引用信息
        if rag_sources:
            ai_message = self._add_rag_citations(ai_message, rag_sources)

        return modified_workflow, ai_message

    def process_message(
        self,
        workflow: Workflow,
        user_message: str,
        use_rag: bool = True,
    ) -> tuple[Workflow, str]:
        """同步处理用户消息

        注意：为了更好的性能，建议使用 process_message_async
        """
        import asyncio

        # 创建新的事件循环运行异步方法
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.process_message_async(workflow, user_message, use_rag)
            )
        finally:
            loop.close()

    def _build_system_prompt(self, workflow: Workflow, rag_context: str = "") -> str:
        """构造系统提示词

        参数：
            workflow: 当前工作流
            rag_context: RAG检索到的上下文

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

        base_prompt = f"""你是一个工作流编辑助手。用户会告诉你如何修改工作流，你需要：

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
- ai_message 应该简洁地描述做了什么修改"""

        # 如果有RAG上下文，添加到提示词中
        if rag_context:
            rag_prompt = f"""

相关知识库内容：
{rag_context}

请结合以上知识库内容来回答用户的问题。如果知识库中有相关的工作流模板或最佳实践，请参考它们进行修改。"""

            base_prompt += rag_prompt

        return base_prompt

    def _build_user_prompt(self, user_message: str, rag_context: str = "") -> str:
        """构造用户提示词

        参数：
            user_message: 用户消息
            rag_context: RAG检索到的上下文

        返回：
            用户提示词
        """
        prompt = f"""用户请求：{user_message}

请生成修改指令（JSON 格式）。"""

        if rag_context:
            prompt += "\n\n请参考提供的知识库内容来生成最合适的修改方案。"

        return prompt

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

    def _add_rag_citations(self, ai_message: str, rag_sources: list) -> str:
        """添加RAG引用信息到AI回复

        参数：
            ai_message: 原始AI回复
            rag_sources: RAG来源列表

        返回：
            包含引用信息的AI回复
        """
        if not rag_sources:
            return ai_message

        # 添加引用部分
        citation_text = "\n\n参考来源："
        for i, source in enumerate(rag_sources[:3], 1):  # 最多显示3个来源
            title = source.get("title", "未知文档")
            relevance = source.get("relevance_score", 0)
            citation_text += f"\n{i}. {title} (相关度: {relevance:.2%})"

        return ai_message + citation_text

    async def retrieve_context_only(
        self,
        workflow_id: str,
        query: str,
        max_context_length: int = 4000,
        top_k: int = 5,
    ) -> tuple[str, list]:
        """仅检索上下文，不修改工作流

        参数：
            workflow_id: 工作流ID
            query: 查询文本
            max_context_length: 最大上下文长度
            top_k: 返回的相关文档块数量

        返回：
            (格式化后的上下文, 来源列表)
        """
        if not self.rag_service:
            return "", []

        try:
            from src.application.services.rag_service import QueryContext

            query_context = QueryContext(
                query=query,
                workflow_id=workflow_id,
                max_context_length=max_context_length,
                top_k=top_k,
            )

            retrieved_context = await self.rag_service.retrieve_context(query_context)
            return retrieved_context.formatted_context, retrieved_context.sources

        except Exception as e:
            print(f"检索上下文失败: {str(e)}")
            return "", []
