"""WorkflowChatService Enhanced - 增强版本（对话增强）

Domain 层：增强的工作流对话服务

功能增强：
1. 对话历史管理 - 维护多轮对话上下文（数据库持久化）
2. 意图识别 - 明确识别用户意图和信心度
3. 修改验证 - 更详细的验证和错误反馈
4. 工作流建议 - 根据工作流结构提供建议
5. 修改回滚 - 记录原始工作流支持回滚
"""

import json
from dataclasses import dataclass
from typing import Any

from src.domain.entities.chat_message import ChatMessage
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.exceptions import DomainError
from src.domain.ports.chat_message_repository import ChatMessageRepository
from src.domain.ports.tool_repository import ToolRepository
from src.domain.ports.workflow_chat_llm import WorkflowChatLLM
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.domain.value_objects.workflow_modification_result import ModificationResult


@dataclass
class ChatHistory:
    """对话历史管理（数据库持久化）

    职责：
    - 使用 ChatMessageRepository 管理对话历史
    - 提供对话上下文的查询和压缩功能
    - 支持跨会话的历史记录持久化
    """

    workflow_id: str
    repository: ChatMessageRepository
    max_messages: int = 1000  # 最多保留1000条消息

    def add_message(self, content: str, is_user: bool) -> None:
        """添加消息并保存到数据库

        参数：
            content: 消息内容
            is_user: 是否来自用户
        """
        message = ChatMessage.create(workflow_id=self.workflow_id, content=content, is_user=is_user)
        self.repository.save(message)

    def get_context(self, last_n: int = 10) -> str:
        """获取最近的对话上下文（从数据库加载）

        参数：
            last_n: 获取最近 n 条消息

        返回：
            格式化的对话上下文字符串
        """
        messages = self.repository.find_by_workflow_id(self.workflow_id, limit=last_n)
        context = []
        for msg in messages:
            role = "用户" if msg.is_user else "助手"
            context.append(f"{role}：{msg.content}")

        return "\n".join(context)

    def clear(self) -> None:
        """清空所有消息（从数据库删除）"""
        self.repository.delete_by_workflow_id(self.workflow_id)

    def export(self) -> list[dict[str, Any]]:
        """导出消息列表（从数据库加载）"""
        messages = self.repository.find_by_workflow_id(self.workflow_id, limit=self.max_messages)
        return [msg.to_dict() for msg in messages]

    def search(self, query: str, threshold: float = 0.5) -> list[tuple[ChatMessage, float]]:
        """在消息历史中进行语义搜索（使用 repository）

        参数：
            query: 搜索查询词
            threshold: 相关性阈值（0-1）

        返回：
            [(ChatMessage, relevance_score), ...] 按相关性降序排列
        """
        if not query or not query.strip():
            return []

        # 直接使用 repository 的搜索功能
        return self.repository.search(self.workflow_id, query, threshold=threshold)

    def filter_by_relevance(
        self, keyword: str, threshold: float = 0.5, max_results: int | None = None
    ) -> list[ChatMessage]:
        """根据关键词过滤相关的消息（使用 repository）

        参数：
            keyword: 关键词
            threshold: 相关性阈值（0-1）
            max_results: 最大返回结果数

        返回：
            符合条件的消息列表
        """
        search_results = self.search(keyword, threshold=threshold)

        # 提取消息（忽略分数）
        filtered = [msg for msg, score in search_results]

        # 应用最大结果数限制
        if max_results is not None:
            filtered = filtered[:max_results]

        return filtered

    def compress_history(self, max_tokens: int, min_messages: int = 2) -> list[ChatMessage]:
        """压缩历史消息以控制 token 数量（从数据库加载）

        参数：
            max_tokens: 最大允许的 token 数
            min_messages: 最小保留消息数

        返回：
            压缩后的消息列表
        """
        # 从数据库加载所有消息
        messages = self.repository.find_by_workflow_id(self.workflow_id, limit=self.max_messages)

        if not messages:
            return []

        # 估计当前 token 数
        current_tokens = self.estimate_tokens(messages)

        # 如果在限制内，返回所有消息
        if current_tokens <= max_tokens:
            return messages.copy()

        # 从后往前（从最新到最旧）构建消息列表，确保保留最近的消息
        compressed = []
        token_count = 0

        for msg in reversed(messages):
            msg_tokens = self._estimate_message_tokens(msg)

            if len(compressed) >= len(messages) - min_messages:
                # 已经删除足够的旧消息，保留最少数量
                if token_count + msg_tokens <= max_tokens or len(compressed) < min_messages:
                    compressed.append(msg)
                    token_count += msg_tokens
            else:
                # 还可以继续删除旧消息
                if token_count + msg_tokens <= max_tokens:
                    compressed.append(msg)
                    token_count += msg_tokens

        # 反转以保持时间顺序
        compressed.reverse()
        return compressed

    def estimate_tokens(self, messages: list[ChatMessage]) -> int:
        """估计消息列表的 token 数量

        参数：
            messages: 消息列表

        返回：
            估计的 token 数
        """
        total = 0
        for msg in messages:
            total += self._estimate_message_tokens(msg)
        return total

    @staticmethod
    def _estimate_message_tokens(msg: ChatMessage) -> int:
        """估计单条消息的 token 数

        使用启发式方法：中文约1-2字符1个token，英文约4字符1个token

        参数：
            msg: 消息

        返回：
            估计的 token 数
        """
        content = msg.content

        # 估计中文字符数（CJK 字符）
        import re

        cjk_count = len(re.findall(r"[\u4e00-\u9fff]", content))

        # 估计其他字符
        other_count = len(content) - cjk_count

        # 中文：平均 1.3 字符 = 1 token
        # 英文：平均 4 字符 = 1 token
        tokens = int(cjk_count / 1.3) + int(other_count / 4)

        # 至少计为 1 token
        return max(1, tokens)


class EnhancedWorkflowChatService:
    """增强版工作流对话服务（数据库持久化）

    职责：
    1. 维护对话历史和上下文（数据库持久化）
    2. 识别用户意图和信心度
    3. 应用修改到工作流
    4. 提供工作流建议
    5. 支持修改回滚

    增强点：
    - 多轮对话上下文支持（跨会话持久化）
    - 更详细的意图识别
    - 更好的错误反馈
    - 工作流优化建议
    """

    def __init__(
        self,
        workflow_id: str,
        llm: WorkflowChatLLM,
        chat_message_repository: ChatMessageRepository,
        tool_repository: ToolRepository | None = None,
        rag_service=None,
        memory_service=None,
        history=None,
    ):
        """初始化服务

        参数：
            workflow_id: 工作流 ID（用于关联对话历史）
            llm: WorkflowChatLLM 实例（Domain Port）
            chat_message_repository: 对话消息仓储
            rag_service: RAG服务实例（可选）
            memory_service: CompositeMemoryService 实例（可选，优先使用）
        """
        self.workflow_id = workflow_id
        self.llm = llm
        self.tool_repository = tool_repository

        # 注意：Domain 层不应依赖 Application/Infrastructure 具体实现。
        # 若需要高性能内存系统，请在外部注入一个兼容 ChatHistory 的 adapter（Ports/Adapters）。
        if history is not None:
            self.history = history
        elif memory_service is not None:
            self.history = memory_service
        else:
            self.history = ChatHistory(workflow_id=workflow_id, repository=chat_message_repository)

        self.rag_service = rag_service

    def _build_tool_candidates_prompt(self) -> str:
        repository = self.tool_repository
        if repository is None:
            return "（不可用：tool repository unavailable）"

        tools = repository.find_published()
        if not tools:
            return "（空：no published tools available）"

        def _sanitize(value: str, *, limit: int) -> str:
            normalized = (value or "").replace("\r", " ").replace("\n", " ").strip()
            if len(normalized) <= limit:
                return normalized
            return f"{normalized[: max(0, limit - 1)]}…"

        ordered = sorted(tools, key=lambda tool: (tool.name.casefold(), tool.id))
        max_items = 50
        lines = []
        for tool in ordered[:max_items]:
            lines.append(
                f'- tool_id="{tool.id}" name="{_sanitize(tool.name, limit=60)}" '
                f'category="{tool.category.value}" description="{_sanitize(tool.description, limit=120)}"'
            )

        if len(ordered) > max_items:
            lines.append(f"- ... ({len(ordered) - max_items} more tools omitted)")

        return "\n".join(lines)

    def add_message(self, content: str, is_user: bool) -> None:
        """添加消息到历史

        参数：
            content: 消息内容
            is_user: 是否来自用户
        """
        self.history.add_message(content, is_user)

    def clear_history(self) -> None:
        """清空对话历史"""
        self.history.clear()

    def process_message(self, workflow: Workflow, user_message: str) -> ModificationResult:
        """处理用户消息，修改工作流

        参数：
            workflow: 当前工作流实体
            user_message: 用户消息

        返回：
            ModificationResult 包含修改结果和详细信息
        """
        # 验证输入
        if not user_message or not user_message.strip():
            return ModificationResult(
                success=False,
                ai_message="",
                error_message="消息不能为空",
                error_details=["用户消息内容为空"],
            )

        # 添加用户消息到历史
        self.add_message(user_message, is_user=True)

        # 0. 检索RAG上下文（如果RAG服务可用）
        rag_context = ""
        rag_sources = []
        if self.rag_service:
            try:
                import asyncio

                # 创建异步任务获取RAG上下文
                from src.domain.value_objects.query_context import QueryContext

                query_context = QueryContext(
                    query=user_message,
                    workflow_id=workflow.id,
                    max_context_length=2000,
                    top_k=3,
                )

                # 运行异步检索
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    retrieved_context = loop.run_until_complete(
                        self.rag_service.retrieve_context(query_context)
                    )
                    rag_context = retrieved_context.formatted_context
                    rag_sources = retrieved_context.sources
                finally:
                    loop.close()

            except Exception as e:
                # RAG检索失败时不中断流程，仅记录
                print(f"RAG检索失败: {str(e)}")

        # 1. 构造提示词（包含历史上下文和RAG上下文）
        system_prompt = self._build_system_prompt(workflow, rag_context)
        user_prompt = self._build_user_prompt_with_context(user_message)

        # 2. 调用 LLM 解析用户意图
        try:
            llm_result = self.llm.generate_modifications(system_prompt, user_prompt)
        except Exception as e:
            error_msg = f"LLM 调用失败: {str(e)}"
            return ModificationResult(
                success=False,
                ai_message="",
                error_message=error_msg,
                error_details=[str(e)],
            )

        # 3. 应用修改到工作流
        try:
            modified_workflow, modifications_count = self._apply_modifications(workflow, llm_result)
        except DomainError as e:
            return ModificationResult(
                success=False,
                ai_message=llm_result.get("ai_message", "修改失败"),
                error_message=str(e),
                error_details=[str(e)],
                original_workflow=workflow,
            )

        # 4. 添加助手消息到历史
        ai_message = llm_result.get("ai_message", "已完成修改")
        self.add_message(ai_message, is_user=False)

        # 5. 返回结果
        return ModificationResult(
            success=True,
            ai_message=ai_message,
            intent=llm_result.get("intent", ""),
            confidence=llm_result.get("confidence", 0.0),
            modifications_count=modifications_count,
            original_workflow=workflow,
            modified_workflow=modified_workflow,
            rag_sources=rag_sources,
            react_steps=llm_result.get("react_steps", []),
        )

    def get_workflow_suggestions(self, workflow: Workflow) -> list[str]:
        """根据工作流结构提供优化建议

        参数：
            workflow: 工作流实体

        返回：
            建议列表
        """
        suggestions = []

        # 检查工作流结构
        if not workflow.nodes:
            suggestions.append("工作流没有任何节点，请添加至少一个节点")
            return suggestions

        # 检查开始和结束节点
        has_start = any(node.type == NodeType.START for node in workflow.nodes)
        has_end = any(node.type == NodeType.END for node in workflow.nodes)

        if not has_start:
            suggestions.append("缺少开始节点（start），建议在工作流开头添加开始节点")
        if not has_end:
            suggestions.append("缺少结束节点（end），建议在工作流末尾添加结束节点")

        # 检查节点连接
        if workflow.edges:
            connected_nodes = set()
            for edge in workflow.edges:
                connected_nodes.add(edge.source_node_id)
                connected_nodes.add(edge.target_node_id)

            for node in workflow.nodes:
                if node.type != NodeType.START and node.id not in connected_nodes:
                    suggestions.append(f"节点 '{node.name}' 未连接到任何边，可能会被跳过")
        else:
            if len(workflow.nodes) > 1:
                suggestions.append("工作流有多个节点但没有边连接，请添加边以连接节点")

        # 检查循环连接
        if not workflow.edges:
            suggestions.append("添加边来连接工作流中的节点，以定义执行顺序")

        # 检查节点配置
        for node in workflow.nodes:
            if node.type not in [NodeType.START, NodeType.END] and not node.config:
                suggestions.append(f"节点 '{node.name}' 没有配置，可能需要添加配置信息")

        return suggestions

    def _build_system_prompt(self, workflow: Workflow, rag_context: str = "") -> str:
        """构造系统提示词（包含历史上下文和RAG上下文）

        参数：
            workflow: 当前工作流
            rag_context: RAG检索到的上下文（可选）

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

        tool_candidates = self._build_tool_candidates_prompt()
        base_prompt = f"""你是一个工作流编辑助手。用户会告诉你如何修改工作流，你需要：

1. 理解用户意图
2. 识别用户的主要意图（add_node, delete_node, add_edge, modify_node等）
3. 生成工作流修改指令
4. 返回 JSON 格式的修改指令

当前工作流状态：
```json
{json.dumps(workflow_state, ensure_ascii=False, indent=2)}
```

支持的节点类型：
- start: 开始节点
- end: 结束节点
- httpRequest: HTTP 请求节点
- transform: 数据转换节点
- database: 数据库操作节点
- conditional: 条件分支节点
- loop: 循环节点
- python: Python 代码执行节点
- textModel: LLM 调用节点（文本）
- prompt: 提示词节点
- file: 文件操作节点
- notification: 消息通知节点
- tool: 工具节点（必须在 config.tool_id 指定 Tool ID）

工具节点约束：
- 工具节点（type=\"tool\"）必须包含 config.tool_id，且 tool_id 必须来自“允许工具列表”
- 严禁把工具 name 当作 tool_id；严禁根据 name 猜测/映射 tool_id
- 如果用户只描述了工具名称/功能但无法确定 tool_id，请返回 intent 为 \"ask_clarification\" 并在 ai_message 中要求用户提供 tool_id

允许工具列表（仅 id/name/category/description，不包含任何实现配置）：
{tool_candidates}

返回格式（JSON）：
{{
  "intent": "add_node|delete_node|add_edge|delete_edge|modify_node|ask_clarification",
  "confidence": 0.95,
  "action": "add_node" | "delete_node" | "add_edge" | "delete_edge" | "modify_node",
  "nodes_to_add": [
    {{
      "type": "httpRequest",
      "name": "节点名称",
      "config": {{}},
      "position": {{"x": 100, "y": 100}}
    }}
  ],
  "nodes_to_delete": ["node_id"],
  "edges_to_add": [
    {{
      "source": "node_id_1",
      "target": "node_id_2",
      "condition": null
    }}
  ],
  "edges_to_delete": ["edge_id"],
  "ai_message": "我已经添加了一个HTTP节点用于获取天气数据",
  "react_steps": [
    {{
      "step": 1,
      "thought": "用户需要添加HTTP节点来处理HTTP请求",
      "action": {{
        "type": "add_node",
        "node": {{
          "type": "httpRequest",
          "name": "节点名称",
          "config": {{}},
          "position": {{"x": 100, "y": 100}}
        }}
      }},
      "observation": "HTTP请求节点已成功添加"
    }}
  ]
}}

要求：
- intent 字段必须包含用户的主要意图
- confidence 字段表示你对这个意图的信心度（0-1）
- 新节点的位置应该合理（避免重叠）
- 添加节点时通常需要同时添加边
- 删除节点时需要同时删除相关的边
- ai_message 应该简洁地描述做了什么修改
- react_steps 字段包含ReAct推理步骤（思考→行动→观察），用于展示AI的推理过程
- 每个react_step应包含：step（步骤号）、thought（思考内容）、action（执行的操作）、observation（执行结果的观察）
- 如果无法理解用户意图，设置 intent 为 "ask_clarification"，react_steps 可以为空
"""

        # 如果有RAG上下文，添加到提示词中
        if rag_context:
            rag_prompt = f"""

相关知识库内容：
{rag_context}

请结合以上知识库内容来回答用户的问题。如果知识库中有相关的工作流模板或最佳实践，请参考它们进行修改。
"""
            base_prompt += rag_prompt

        return base_prompt

    def _build_user_prompt_with_context(self, user_message: str) -> str:
        """构造包含历史上下文的用户提示词

        参数：
            user_message: 用户新消息

        返回：
            用户提示词
        """
        # 压缩历史以避免 token 溢出（限制为 2000 tokens）
        compressed_history = self.history.compress_history(max_tokens=2000, min_messages=2)

        # 构建格式化的上下文
        context_lines = []
        for msg in compressed_history:
            role = "用户" if msg.is_user else "助手"
            context_lines.append(f"{role}：{msg.content}")

        context = "\n".join(context_lines)

        if context:
            return f"""对话历史：
{context}

用户新消息：{user_message}

请根据以上对话历史和用户新消息，生成修改指令（JSON 格式）。"""
        else:
            return f"""用户请求：{user_message}

请生成修改指令（JSON 格式）。"""

    def _apply_modifications(
        self, workflow: Workflow, modifications: dict[str, Any]
    ) -> tuple[Workflow, int]:
        """应用修改到工作流

        参数：
            workflow: 原工作流
            modifications: 修改指令

        返回：
            (修改后的工作流，修改数量)
        """
        modifications_count = 0
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
            modifications_count += len(nodes_to_delete)

        # 2. 添加节点
        nodes_to_add = modifications.get("nodes_to_add", [])
        for node_data in nodes_to_add:
            try:
                new_node = Node.create(
                    type=NodeType(node_data["type"]),
                    name=node_data["name"],
                    config=node_data.get("config", {}),
                    position=Position(x=node_data["position"]["x"], y=node_data["position"]["y"]),
                )
                new_nodes.append(new_node)
                modifications_count += 1
            except ValueError as e:
                raise DomainError(f"无效的节点类型: {node_data.get('type')}") from e

        # 3. 删除边
        edges_to_delete = modifications.get("edges_to_delete", [])
        if edges_to_delete:
            new_edges = [edge for edge in new_edges if edge.id not in edges_to_delete]
            modifications_count += len(edges_to_delete)

        # 4. 添加边
        edges_to_add = modifications.get("edges_to_add", [])
        for edge_data in edges_to_add:
            source = edge_data.get("source", "")
            target = edge_data.get("target", "")

            # 验证：跳过无效的边
            if not source or not target:
                continue
            if source == target:
                continue

            # 验证：检查节点是否存在
            node_ids = {node.id for node in new_nodes}
            if source not in node_ids or target not in node_ids:
                continue

            # 验证：检查边是否已存在
            existing_edges = {(edge.source_node_id, edge.target_node_id) for edge in new_edges}
            if (source, target) in existing_edges:
                continue

            try:
                new_edge = Edge.create(
                    source_node_id=source,
                    target_node_id=target,
                    condition=edge_data.get("condition"),
                )
                new_edges.append(new_edge)
                modifications_count += 1
            except DomainError:
                continue

        # 5. 创建新的工作流实体
        modified_workflow = Workflow(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            nodes=new_nodes,
            edges=new_edges,
            status=workflow.status,
            source=workflow.source,
            source_id=workflow.source_id,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

        return modified_workflow, modifications_count
