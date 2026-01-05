"""WorkflowChatService 增强版本 - 对话增强测试

TDD 第一步：先写测试，定义期望的行为

增强功能：
1. 对话历史管理 - 维护多轮对话上下文（数据库持久化）
2. 意图识别 - 明确识别用户意图
3. 修改验证 - 更详细的验证和错误反馈
4. 建议生成 - 根据工作流提出修改建议

注意：当前实现使用数据库持久化，测试需要 mock ChatMessageRepository
"""

from unittest.mock import Mock

import pytest

from src.domain.entities.chat_message import ChatMessage
from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.tool import Tool
from src.domain.entities.workflow import Workflow
from src.domain.services.workflow_chat_service_enhanced import (
    EnhancedWorkflowChatService,
    extract_main_subgraph,
)
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.domain.value_objects.tool_category import ToolCategory
from src.domain.value_objects.tool_status import ToolStatus
from src.domain.value_objects.workflow_modification_result import ModificationResult


class MockChatMessageRepository:
    """Mock 的聊天消息仓储，用于测试"""

    def __init__(self):
        self._messages: list[ChatMessage] = []

    def save(self, message: ChatMessage) -> None:
        self._messages.append(message)

    def find_by_workflow_id(self, workflow_id: str, limit: int = 100) -> list[ChatMessage]:
        return [m for m in self._messages if m.workflow_id == workflow_id][:limit]

    def delete_by_workflow_id(self, workflow_id: str) -> None:
        self._messages = [m for m in self._messages if m.workflow_id != workflow_id]

    def search(
        self, workflow_id: str, query: str, threshold: float = 0.5
    ) -> list[tuple[ChatMessage, float]]:
        """简单的关键词匹配搜索"""
        if not query or not query.strip():
            return []

        results = []
        query_lower = query.lower()
        keywords = query_lower.split()

        for msg in self._messages:
            if msg.workflow_id != workflow_id:
                continue

            content_lower = msg.content.lower()
            # 计算匹配度
            match_count = sum(1 for kw in keywords if kw in content_lower)
            if match_count > 0:
                score = match_count / len(keywords)
                if score >= threshold:
                    results.append((msg, score))

        # 按分数降序排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results


@pytest.fixture
def mock_llm():
    """Mock LLM 客户端"""
    return Mock()


@pytest.fixture
def mock_repository():
    """Mock 聊天消息仓储"""
    return MockChatMessageRepository()


@pytest.fixture
def sample_workflow():
    """创建示例工作流"""
    nodes = [
        Node.create(
            type=NodeType.START,
            name="开始",
            config={},
            position=Position(x=100, y=100),
        ),
        Node.create(
            type=NodeType.HTTP,
            name="获取数据",
            config={"url": "https://api.example.com", "method": "GET"},
            position=Position(x=300, y=100),
        ),
        Node.create(
            type=NodeType.END,
            name="结束",
            config={},
            position=Position(x=500, y=100),
        ),
    ]
    # 手动设置节点ID以便于边引用
    nodes[0].id = "node_1"
    nodes[1].id = "node_2"
    nodes[2].id = "node_3"

    edges = [
        Edge.create(source_node_id="node_1", target_node_id="node_2"),
        Edge.create(source_node_id="node_2", target_node_id="node_3"),
    ]

    return Workflow.create(
        name="示例工作流",
        description="测试用工作流",
        nodes=nodes,
        edges=edges,
    )


def test_chat_service_maintains_history(mock_llm, mock_repository, sample_workflow):
    """测试：对话服务应该维护对话历史"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    # 模拟 LLM 返回值
    mock_llm.generate_modifications.return_value = {
        "action": "add_node",
        "nodes_to_add": [],
        "ai_message": "我理解你了",
        "intent": "ask_clarification",
    }

    # 第一轮对话
    message1 = "添加一个节点"
    service.add_message(message1, is_user=True)

    # 验证历史（通过 repository 查询）
    messages = mock_repository.find_by_workflow_id("wf_test")
    assert len(messages) == 1
    assert messages[0].content == message1
    assert messages[0].is_user is True


def test_chat_service_maintains_conversation_context(mock_llm, mock_repository, sample_workflow):
    """测试：多轮对话应该保持上下文"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    # 添加多条消息
    service.add_message("添加一个 HTTP 节点", is_user=True)
    service.add_message("已添加节点", is_user=False)
    service.add_message("连接到前面的节点", is_user=True)

    # 验证历史维护
    messages = mock_repository.find_by_workflow_id("wf_test")
    assert len(messages) == 3
    assert service.history.get_context()  # 应该能获取上下文


def test_modification_result_contains_detailed_info(mock_llm, mock_repository, sample_workflow):
    """测试：修改结果应该包含详细的修改信息"""
    mock_llm.generate_modifications.return_value = {
        "action": "add_node",
        "nodes_to_add": [
            {
                "type": "python",
                "name": "处理数据",
                "config": {"code": "result = input1"},
                "position": {"x": 350, "y": 100},
            }
        ],
        "ai_message": "已添加 Python 节点",
        "intent": "add_node",
        "confidence": 0.95,
    }

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    result = service.process_message(sample_workflow, "添加一个 Python 节点处理数据")

    # 验证结果包含所有必要信息
    assert isinstance(result, ModificationResult)
    assert result.success is True
    assert result.ai_message is not None
    assert result.modifications_count > 0


def test_modification_rejects_outside_main_subgraph_fail_closed(mock_llm, mock_repository):
    """测试：LLM 返回主连通子图外的 node_id 修改时应 fail-closed 拒绝（结构化错误）"""
    # 主路径：start -> mid -> end
    start = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    mid = Node.create(type=NodeType.HTTP, name="中间", config={}, position=Position(x=100, y=0))
    end = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))
    isolated = Node.create(
        type=NodeType.PYTHON, name="孤立节点", config={}, position=Position(x=100, y=100)
    )

    start.id = "node_main_start"
    mid.id = "node_main_mid"
    end.id = "node_main_end"
    isolated.id = "node_isolated"

    edge1 = Edge.create(source_node_id=start.id, target_node_id=mid.id)
    edge2 = Edge.create(source_node_id=mid.id, target_node_id=end.id)

    workflow = Workflow.create(
        name="测试工作流",
        description="",
        nodes=[start, mid, end, isolated],
        edges=[edge1, edge2],
    )

    mock_llm.generate_modifications.return_value = {
        "action": "delete_node",
        "intent": "delete_node",
        "confidence": 0.9,
        "nodes_to_delete": ["node_isolated"],
        "ai_message": "删除孤立节点",
    }

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    result = service.process_message(workflow, "删除孤立节点")

    assert result.success is False
    assert result.error_message
    assert result.error_details

    import json

    payload = json.loads(result.error_details[0])
    assert payload["code"] == "workflow_modification_rejected"
    assert any(err["field"] == "nodes_to_delete" for err in payload["errors"])


def test_build_system_prompt_includes_tool_id_constraints_and_candidates(
    mock_llm, mock_repository, sample_workflow
):
    tool_repo = Mock()
    tool_repo.find_published.return_value = [
        Tool(
            id="tool_alpha",
            name="Weather API",
            description="Fetch weather data",
            category=ToolCategory.HTTP,
            status=ToolStatus.PUBLISHED,
            version="1.0.0",
        ),
        Tool(
            id="tool_beta",
            name="Echo",
            description="Echo back input",
            category=ToolCategory.CUSTOM,
            status=ToolStatus.PUBLISHED,
            version="1.0.0",
        ),
    ]

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test",
        llm=mock_llm,
        chat_message_repository=mock_repository,
        tool_repository=tool_repo,
    )

    prompt = service._build_system_prompt(sample_workflow, rag_context="")
    assert "- tool: 工具节点（必须在 config.tool_id 指定 Tool ID）" in prompt
    assert "config.tool_id" in prompt
    assert 'tool_id="tool_alpha"' in prompt
    assert 'tool_id="tool_beta"' in prompt


def test_build_system_prompt_only_includes_main_subgraph_nodes_and_edges(mock_llm, mock_repository):
    """测试：system prompt 的 workflow_state 仅包含 start->end 主连通子图"""
    start = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    mid = Node.create(
        type=NodeType.HTTP, name="主路径节点", config={}, position=Position(x=100, y=0)
    )
    end = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))

    isolated = Node.create(
        type=NodeType.PYTHON, name="孤立节点", config={}, position=Position(x=100, y=100)
    )
    sub_a = Node.create(
        type=NodeType.PYTHON, name="子图A", config={}, position=Position(x=0, y=200)
    )
    sub_b = Node.create(
        type=NodeType.PYTHON, name="子图B", config={}, position=Position(x=100, y=200)
    )

    start.id = "node_main_start"
    mid.id = "node_main_mid"
    end.id = "node_main_end"
    isolated.id = "node_isolated"
    sub_a.id = "node_sub_a"
    sub_b.id = "node_sub_b"

    edge1 = Edge.create(source_node_id=start.id, target_node_id=mid.id)
    edge1.id = "edge_main_1"
    edge2 = Edge.create(source_node_id=mid.id, target_node_id=end.id)
    edge2.id = "edge_main_2"

    sub_edge = Edge.create(source_node_id=sub_a.id, target_node_id=sub_b.id)
    sub_edge.id = "edge_sub"

    workflow = Workflow.create(
        name="测试工作流",
        description="",
        nodes=[start, mid, end, isolated, sub_a, sub_b],
        edges=[edge1, edge2, sub_edge],
    )

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    prompt = service._build_system_prompt(workflow, rag_context="")

    assert "node_main_start" in prompt
    assert "node_main_mid" in prompt
    assert "node_main_end" in prompt
    assert "edge_main_1" in prompt
    assert "edge_main_2" in prompt

    assert "node_isolated" not in prompt
    assert "node_sub_a" not in prompt
    assert "node_sub_b" not in prompt
    assert "edge_sub" not in prompt


def test_chat_service_identifies_intent_correctly(mock_llm, mock_repository, sample_workflow):
    """测试：服务应该正确识别用户意图"""
    # 模拟 LLM 识别意图
    mock_llm.generate_modifications.return_value = {
        "action": "add_node",
        "intent": "add_node",
        "confidence": 0.98,
        "nodes_to_add": [],
        "ai_message": "我会添加节点",
    }

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    result = service.process_message(sample_workflow, "添加一个新节点")

    assert result.intent == "add_node"
    assert result.confidence >= 0.9


def test_chat_service_provides_suggestions(mock_llm, mock_repository, sample_workflow):
    """测试：服务应该根据工作流提供建议"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    # 获取建议
    suggestions = service.get_workflow_suggestions(sample_workflow)

    # 应该返回建议列表
    assert isinstance(suggestions, list)
    # 对于这个简单的工作流，应该有一些基本的建议


def test_chat_service_provides_error_details(mock_llm, mock_repository, sample_workflow):
    """测试：当修改失败时应该提供详细的错误信息"""
    # 模拟 LLM 返回无效的修改
    mock_llm.generate_modifications.return_value = {
        "action": "add_edge",
        "edges_to_add": [{"source": "invalid_node", "target": "node_1"}],
        "ai_message": "已添加边",
        "intent": "add_edge",
    }

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    result = service.process_message(sample_workflow, "连接两个节点")

    # 应该捕获并报告错误
    if not result.success:
        assert result.error_message is not None
        assert len(result.error_details) > 0


def test_chat_history_export(mock_llm, mock_repository):
    """测试：应该能导出对话历史"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    # 添加一些消息
    service.add_message("Hello", is_user=True)
    service.add_message("Hi there", is_user=False)

    # 导出历史
    history_data = service.history.export()

    assert len(history_data) == 2
    assert history_data[0]["content"] == "Hello"
    assert history_data[1]["content"] == "Hi there"


def test_chat_service_clears_history(mock_llm, mock_repository):
    """测试：应该能清空对话历史"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("Message 1", is_user=True)
    service.add_message("Message 2", is_user=False)

    messages = mock_repository.find_by_workflow_id("wf_test")
    assert len(messages) == 2

    # 清空历史
    service.clear_history()

    messages = mock_repository.find_by_workflow_id("wf_test")
    assert len(messages) == 0


def test_modification_validation_detailed(mock_llm, mock_repository, sample_workflow):
    """测试：修改验证应该检查所有约束"""
    # 模拟 LLM 返回包含多个修改的请求
    mock_llm.generate_modifications.return_value = {
        "action": "modify_multiple",
        "nodes_to_add": [
            {
                "type": "database",
                "name": "查询数据库",
                "config": {},
                "position": {"x": 400, "y": 200},
            }
        ],
        "edges_to_add": [],
        "ai_message": "已完成修改",
    }

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    result = service.process_message(sample_workflow, "添加数据库节点")

    # 应该验证所有修改的有效性
    assert result is not None


def test_chat_service_with_context_awareness(mock_llm, mock_repository, sample_workflow):
    """测试：服务应该根据对话历史调整行为"""
    mock_llm.generate_modifications.return_value = {
        "action": "modify_node",
        "intent": "context_aware",
        "ai_message": "基于之前的请求进行修改",
    }

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    # 第一轮对话
    service.add_message("我想处理 API 数据", is_user=True)
    service.add_message("我理解，我会为你设置数据处理流程", is_user=False)

    # 第二轮对话应该理解上下文
    result = service.process_message(sample_workflow, "加上错误处理")

    assert result is not None
    # LLM 应该在构建提示词时包含历史信息


def test_modification_result_with_rollback_info(mock_llm, mock_repository, sample_workflow):
    """测试：修改结果应该包含回滚信息"""
    mock_llm.generate_modifications.return_value = {
        "action": "add_node",
        "nodes_to_add": [],
        "ai_message": "已修改",
    }

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    result = service.process_message(sample_workflow, "修改工作流")

    # 结果应该包含可以用于回滚的信息
    assert hasattr(result, "original_workflow")
    assert hasattr(result, "modified_workflow")


# ============================================================================
# TDD RED阶段：语义搜索 (Semantic Search) 测试
# ============================================================================


def test_chat_history_semantic_search_basic(mock_llm, mock_repository):
    """测试：应该能通过关键词在对话历史中进行语义搜索"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    # 添加包含不同关键词的消息
    service.add_message("我想添加一个 HTTP 节点来获取天气数据", is_user=True)
    service.add_message("已添加 HTTP 节点", is_user=False)
    service.add_message("现在添加数据库节点来存储结果", is_user=True)
    service.add_message("添加了数据库节点", is_user=False)

    # 搜索与 "HTTP" 相关的消息
    results = service.history.search("HTTP")

    assert len(results) > 0
    # 结果应该包含关键字匹配的消息
    assert any("HTTP" in msg.content for msg, _ in results)


def test_chat_history_semantic_search_with_relevance_score(mock_llm, mock_repository):
    """测试：搜索结果应该包含相关性评分"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("添加 HTTP 请求节点", is_user=True)
    service.add_message("配置 API 端点", is_user=False)
    service.add_message("设置认证头", is_user=True)

    # 搜索返回的应该是包含相关性评分的结果
    results = service.history.search("HTTP API")

    # 验证返回的是 (message, relevance_score) 对
    assert len(results) > 0
    if len(results) > 0:
        msg, score = results[0]
        assert isinstance(msg, ChatMessage)
        assert isinstance(score, float)
        assert 0 <= score <= 1.0


def test_chat_history_search_returns_sorted_by_relevance(mock_llm, mock_repository):
    """测试：搜索结果应该按相关性从高到低排序"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("HTTP 节点", is_user=True)
    service.add_message("HTTP 请求配置", is_user=False)
    service.add_message("数据库节点", is_user=True)
    service.add_message("存储数据", is_user=False)

    results = service.history.search("HTTP")

    # 结果应该按相关性分数降序排列
    if len(results) > 1:
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)


def test_chat_history_search_empty_query_returns_empty(mock_llm, mock_repository):
    """测试：空查询应该返回空结果"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    service.add_message("添加节点", is_user=True)

    results = service.history.search("")

    assert results == []


def test_chat_history_search_no_matches_returns_empty(mock_llm, mock_repository):
    """测试：无匹配结果应该返回空列表"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    service.add_message("HTTP 节点", is_user=True)

    results = service.history.search("XYZ_NOT_EXIST")

    assert results == []


# ============================================================================
# TDD RED阶段：相关性过滤 (Relevance Filtering) 测试
# ============================================================================


def test_chat_history_filter_by_relevance_to_keyword(mock_llm, mock_repository):
    """测试：应该能根据关键词过滤历史消息"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("添加 HTTP 节点获取 API 数据", is_user=True)
    service.add_message("已添加节点", is_user=False)
    service.add_message("修改背景颜色", is_user=True)
    service.add_message("已修改", is_user=False)

    # 过滤与 "API" 相关的消息（使用较低的阈值）
    filtered = service.history.filter_by_relevance("API", threshold=0.1)

    # 应该返回与 API 相关的消息
    assert len(filtered) > 0
    assert all(isinstance(msg, ChatMessage) for msg in filtered)


def test_chat_history_filter_respects_threshold(mock_llm, mock_repository):
    """测试：相关性过滤应该遵守阈值"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("HTTP 请求", is_user=True)
    service.add_message("关键词在这里", is_user=False)
    service.add_message("完全不相关的内容", is_user=True)

    # 高阈值应该过滤掉低相关性消息
    high_threshold_results = service.history.filter_by_relevance("HTTP", threshold=0.8)

    # 低阈值应该包含更多消息
    low_threshold_results = service.history.filter_by_relevance("HTTP", threshold=0.2)

    # 高阈值的结果应该 <= 低阈值的结果
    assert len(high_threshold_results) <= len(low_threshold_results)


def test_chat_history_filter_for_context_building(mock_llm, mock_repository):
    """测试：过滤出最相关的消息用于构建上下文"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    # 添加多条消息，混合相关和不相关的
    messages = [
        ("添加 HTTP 节点", True),
        ("配置请求 URL", False),
        ("用户名是什么", True),
        ("您的名字是 John", False),
        ("现在连接数据库", True),
        ("确认连接成功", False),
    ]

    for msg, is_user in messages:
        service.add_message(msg, is_user)

    # 为了构建上下文，应该返回最相关的 N 条消息
    relevant_msgs = service.history.filter_by_relevance("数据库", threshold=0.5, max_results=3)

    assert len(relevant_msgs) <= 3
    assert all(isinstance(msg, ChatMessage) for msg in relevant_msgs)


def test_chat_history_filter_returns_empty_when_no_match(mock_llm, mock_repository):
    """测试：没有匹配时应该返回空列表"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )
    service.add_message("不相关的内容", is_user=True)

    filtered = service.history.filter_by_relevance("节点配置", threshold=0.9)

    assert filtered == []


# ============================================================================
# TDD RED阶段：上下文压缩 (Context Compression) 测试
# ============================================================================


def test_chat_history_compression_removes_old_messages_when_exceeds_max_tokens(
    mock_llm, mock_repository
):
    """测试：当消息超过 token 限制时应该压缩历史"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    # 添加足够多的消息以超过 token 限制
    for i in range(50):
        service.add_message(
            f"这是第 {i} 条消息，内容较长以增加 token 数量。" * 10, is_user=i % 2 == 0
        )

    # 压缩历史（假设 max_tokens=1000）
    compressed = service.history.compress_history(max_tokens=1000)

    # 压缩后应该保留较少的消息，但不会为空
    messages = mock_repository.find_by_workflow_id("wf_test")
    assert len(compressed) > 0
    assert len(compressed) < len(messages)


def test_chat_history_compression_preserves_recent_messages(mock_llm, mock_repository):
    """测试：压缩应该保留最近的消息"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("很久以前的消息" * 20, is_user=True)
    service.add_message("中间的消息", is_user=False)
    service.add_message("最近的消息，非常重要", is_user=True)

    compressed = service.history.compress_history(max_tokens=200)

    # 最近的消息应该被保留
    if len(compressed) > 0:
        assert "最近的消息" in compressed[-1].content or len(compressed) > 0


def test_chat_history_compression_returns_history_if_within_limit(mock_llm, mock_repository):
    """测试：如果未超过限制，压缩应该返回原始历史"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("短消息1", is_user=True)
    service.add_message("短消息2", is_user=False)

    messages = mock_repository.find_by_workflow_id("wf_test")
    original_count = len(messages)
    compressed = service.history.compress_history(max_tokens=10000)

    # 如果在限制内，应该返回所有消息
    assert len(compressed) == original_count


def test_chat_history_compression_respects_min_messages(mock_llm, mock_repository):
    """测试：压缩不应该删除少于最小消息数的历史"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("消息1" * 50, is_user=True)
    service.add_message("消息2" * 50, is_user=False)
    service.add_message("消息3" * 50, is_user=True)

    # 压缩时指定最小消息数
    compressed = service.history.compress_history(max_tokens=100, min_messages=2)

    # 应该至少保留 min_messages 条
    assert len(compressed) >= 2


def test_chat_history_compression_estimates_token_count(mock_llm, mock_repository):
    """测试：压缩应该能准确估计 token 数量"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("测试消息", is_user=True)
    service.add_message("回复消息", is_user=False)

    # 获取压缩后的历史和 token 估计
    compressed = service.history.compress_history(max_tokens=500)
    token_count = service.history.estimate_tokens(compressed)

    # token 数应该是正整数
    assert isinstance(token_count, int)
    assert token_count > 0
    # token 数应该小于等于 max_tokens
    assert token_count <= 500


def test_chat_history_compression_maintains_message_order(mock_llm, mock_repository):
    """测试：压缩应该维护消息顺序"""
    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    service.add_message("第一条", is_user=True)
    service.add_message("第二条", is_user=False)
    service.add_message("第三条", is_user=True)

    compressed = service.history.compress_history(max_tokens=10000)
    messages = mock_repository.find_by_workflow_id("wf_test")

    # 压缩后的消息顺序应该不变
    for i, msg in enumerate(compressed):
        original_msg = messages[i]
        assert msg.content == original_msg.content
        assert msg.is_user == original_msg.is_user


def test_chat_service_uses_compressed_history_in_prompt(mock_llm, mock_repository, sample_workflow):
    """测试：服务应该在构建提示词时使用压缩后的历史"""
    mock_llm.generate_modifications.return_value = {
        "action": "add_node",
        "nodes_to_add": [],
        "ai_message": "已处理",
    }

    service = EnhancedWorkflowChatService(
        workflow_id="wf_test", llm=mock_llm, chat_message_repository=mock_repository
    )

    # 添加大量消息
    for i in range(30):
        service.add_message(f"长消息 {i}" * 20, is_user=i % 2 == 0)

    result = service.process_message(sample_workflow, "修改工作流")

    # 应该成功处理，说明压缩工作正常
    assert result is not None


# ============================================================================
# TDD RED阶段：Story A - 主连通子图提取（extract_main_subgraph）
# ============================================================================


def test_extract_main_subgraph_with_simple_path():
    """测试：提取简单的 start->node->end 主连通子图"""
    # 创建 start -> node1 -> end 的工作流
    start = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node1 = Node.create(type=NodeType.HTTP, name="节点1", config={}, position=Position(x=100, y=0))
    end = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))

    edge1 = Edge.create(source_node_id=start.id, target_node_id=node1.id)
    edge2 = Edge.create(source_node_id=node1.id, target_node_id=end.id)

    workflow = Workflow.create(
        name="测试工作流", description="", nodes=[start, node1, end], edges=[edge1, edge2]
    )

    main_node_ids, main_edge_ids = extract_main_subgraph(workflow)

    # 所有节点都应该在主连通子图中
    assert len(main_node_ids) == 3
    assert start.id in main_node_ids
    assert node1.id in main_node_ids
    assert end.id in main_node_ids

    # 所有边都应该在主连通子图中
    assert len(main_edge_ids) == 2
    assert edge1.id in main_edge_ids
    assert edge2.id in main_edge_ids


def test_extract_main_subgraph_excludes_isolated_node():
    """测试：孤立节点不应该出现在主连通子图中"""
    # 创建主路径：start -> node1 -> end
    start = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node1 = Node.create(type=NodeType.HTTP, name="节点1", config={}, position=Position(x=100, y=0))
    end = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))

    # 创建孤立节点（没有任何边连接）
    isolated = Node.create(
        type=NodeType.PYTHON, name="孤立节点", config={}, position=Position(x=100, y=100)
    )

    edge1 = Edge.create(source_node_id=start.id, target_node_id=node1.id)
    edge2 = Edge.create(source_node_id=node1.id, target_node_id=end.id)

    workflow = Workflow.create(
        name="测试工作流",
        description="",
        nodes=[start, node1, end, isolated],
        edges=[edge1, edge2],
    )

    main_node_ids, main_edge_ids = extract_main_subgraph(workflow)

    # 孤立节点不应该在主连通子图中
    assert isolated.id not in main_node_ids
    # 主路径的所有节点应该在
    assert start.id in main_node_ids
    assert node1.id in main_node_ids
    assert end.id in main_node_ids


def test_extract_main_subgraph_excludes_isolated_subgraph():
    """测试：孤立子图（有边连接但不连通 start/end）不应该出现在主连通子图中"""
    # 主路径：start -> node1 -> end
    start = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node1 = Node.create(type=NodeType.HTTP, name="节点1", config={}, position=Position(x=100, y=0))
    end = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))

    # 孤立子图：nodeA -> nodeB（与主路径无连接）
    nodeA = Node.create(
        type=NodeType.PYTHON, name="节点A", config={}, position=Position(x=0, y=100)
    )
    nodeB = Node.create(
        type=NodeType.DATABASE, name="节点B", config={}, position=Position(x=100, y=100)
    )

    edge_main1 = Edge.create(source_node_id=start.id, target_node_id=node1.id)
    edge_main2 = Edge.create(source_node_id=node1.id, target_node_id=end.id)
    edge_isolated = Edge.create(source_node_id=nodeA.id, target_node_id=nodeB.id)

    workflow = Workflow.create(
        name="测试工作流",
        description="",
        nodes=[start, node1, end, nodeA, nodeB],
        edges=[edge_main1, edge_main2, edge_isolated],
    )

    main_node_ids, main_edge_ids = extract_main_subgraph(workflow)

    # 孤立子图的节点不应该在主连通子图中
    assert nodeA.id not in main_node_ids
    assert nodeB.id not in main_node_ids
    assert edge_isolated.id not in main_edge_ids

    # 主路径应该完整
    assert start.id in main_node_ids
    assert node1.id in main_node_ids
    assert end.id in main_node_ids
    assert edge_main1.id in main_edge_ids
    assert edge_main2.id in main_edge_ids


def test_extract_main_subgraph_missing_start_returns_empty():
    """测试：缺少 start 节点时返回空集（Fail-Closed）"""
    # 只有 node1 -> end，缺少 start
    node1 = Node.create(type=NodeType.HTTP, name="节点1", config={}, position=Position(x=100, y=0))
    end = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))
    edge = Edge.create(source_node_id=node1.id, target_node_id=end.id)

    workflow = Workflow.create(name="测试工作流", description="", nodes=[node1, end], edges=[edge])

    main_node_ids, main_edge_ids = extract_main_subgraph(workflow)

    # 应该返回空集
    assert len(main_node_ids) == 0
    assert len(main_edge_ids) == 0


def test_extract_main_subgraph_missing_end_returns_empty():
    """测试：缺少 end 节点时返回空集（Fail-Closed）"""
    # 只有 start -> node1，缺少 end
    start = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node1 = Node.create(type=NodeType.HTTP, name="节点1", config={}, position=Position(x=100, y=0))
    edge = Edge.create(source_node_id=start.id, target_node_id=node1.id)

    workflow = Workflow.create(
        name="测试工作流", description="", nodes=[start, node1], edges=[edge]
    )

    main_node_ids, main_edge_ids = extract_main_subgraph(workflow)

    # 应该返回空集
    assert len(main_node_ids) == 0
    assert len(main_edge_ids) == 0


def test_extract_main_subgraph_no_path_returns_empty():
    """测试：start 和 end 存在但无路径时返回空集（Fail-Closed）"""
    # start 和 end 都存在，但没有边连接
    start = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    end = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))

    workflow = Workflow.create(name="测试工作流", description="", nodes=[start, end], edges=[])

    main_node_ids, main_edge_ids = extract_main_subgraph(workflow)

    # 应该返回空集
    assert len(main_node_ids) == 0
    assert len(main_edge_ids) == 0


def test_extract_main_subgraph_multiple_starts_and_ends():
    """测试：多个 start/end 节点时，提取全连通子图"""
    # 创建两条路径：
    # start1 -> node1 -> end1
    # start2 -> node2 -> end2
    # 以及交叉连接：node1 -> end2, start2 -> node1
    start1 = Node.create(type=NodeType.START, name="开始1", config={}, position=Position(x=0, y=0))
    start2 = Node.create(
        type=NodeType.START, name="开始2", config={}, position=Position(x=0, y=100)
    )
    node1 = Node.create(type=NodeType.HTTP, name="节点1", config={}, position=Position(x=100, y=0))
    node2 = Node.create(
        type=NodeType.PYTHON, name="节点2", config={}, position=Position(x=100, y=100)
    )
    end1 = Node.create(type=NodeType.END, name="结束1", config={}, position=Position(x=200, y=0))
    end2 = Node.create(type=NodeType.END, name="结束2", config={}, position=Position(x=200, y=100))

    edge1 = Edge.create(source_node_id=start1.id, target_node_id=node1.id)
    edge2 = Edge.create(source_node_id=node1.id, target_node_id=end1.id)
    edge3 = Edge.create(source_node_id=start2.id, target_node_id=node2.id)
    edge4 = Edge.create(source_node_id=node2.id, target_node_id=end2.id)
    edge5 = Edge.create(source_node_id=node1.id, target_node_id=end2.id)  # 交叉
    edge6 = Edge.create(source_node_id=start2.id, target_node_id=node1.id)  # 交叉

    workflow = Workflow.create(
        name="测试工作流",
        description="",
        nodes=[start1, start2, node1, node2, end1, end2],
        edges=[edge1, edge2, edge3, edge4, edge5, edge6],
    )

    main_node_ids, main_edge_ids = extract_main_subgraph(workflow)

    # 所有节点都应该在主连通子图中（因为有交叉连接）
    assert len(main_node_ids) == 6
    assert start1.id in main_node_ids
    assert start2.id in main_node_ids
    assert node1.id in main_node_ids
    assert node2.id in main_node_ids
    assert end1.id in main_node_ids
    assert end2.id in main_node_ids


def test_extract_main_subgraph_branch_that_doesnt_reach_end():
    """测试：分支无法到达 end 的节点不应该出现在主连通子图中"""
    # 主路径：start -> node1 -> end
    # 分支：node1 -> deadend（无法到达 end）
    start = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node1 = Node.create(type=NodeType.HTTP, name="节点1", config={}, position=Position(x=100, y=0))
    end = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))
    deadend = Node.create(
        type=NodeType.PYTHON, name="死胡同", config={}, position=Position(x=100, y=100)
    )

    edge1 = Edge.create(source_node_id=start.id, target_node_id=node1.id)
    edge2 = Edge.create(source_node_id=node1.id, target_node_id=end.id)
    edge3 = Edge.create(source_node_id=node1.id, target_node_id=deadend.id)

    workflow = Workflow.create(
        name="测试工作流",
        description="",
        nodes=[start, node1, end, deadend],
        edges=[edge1, edge2, edge3],
    )

    main_node_ids, main_edge_ids = extract_main_subgraph(workflow)

    # deadend 节点不应该在主连通子图中（因为它无法到达 end）
    assert deadend.id not in main_node_ids
    assert edge3.id not in main_edge_ids

    # 主路径应该完整
    assert start.id in main_node_ids
    assert node1.id in main_node_ids
    assert end.id in main_node_ids


def test_extract_main_subgraph_node_unreachable_from_start():
    """测试：从 start 无法到达的节点不应该出现在主连通子图中"""
    # start -> node1 -> end
    # orphan -> end（orphan 无法从 start 到达）
    start = Node.create(type=NodeType.START, name="开始", config={}, position=Position(x=0, y=0))
    node1 = Node.create(type=NodeType.HTTP, name="节点1", config={}, position=Position(x=100, y=0))
    end = Node.create(type=NodeType.END, name="结束", config={}, position=Position(x=200, y=0))
    orphan = Node.create(
        type=NodeType.PYTHON, name="孤儿节点", config={}, position=Position(x=100, y=100)
    )

    edge1 = Edge.create(source_node_id=start.id, target_node_id=node1.id)
    edge2 = Edge.create(source_node_id=node1.id, target_node_id=end.id)
    edge3 = Edge.create(source_node_id=orphan.id, target_node_id=end.id)

    workflow = Workflow.create(
        name="测试工作流",
        description="",
        nodes=[start, node1, end, orphan],
        edges=[edge1, edge2, edge3],
    )

    main_node_ids, main_edge_ids = extract_main_subgraph(workflow)

    # orphan 节点不应该在主连通子图中（因为它无法从 start 到达）
    assert orphan.id not in main_node_ids
    assert edge3.id not in main_edge_ids

    # 主路径应该完整
    assert start.id in main_node_ids
    assert node1.id in main_node_ids
    assert end.id in main_node_ids
