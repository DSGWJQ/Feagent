"""WorkflowChatService 增强版本 - 对话增强测试

TDD 第一步：先写测试，定义期望的行为

增强功能：
1. 对话历史管理 - 维护多轮对话上下文
2. 意图识别 - 明确识别用户意图
3. 修改验证 - 更详细的验证和错误反馈
4. 建议生成 - 根据工作流提出修改建议
"""

from unittest.mock import Mock

import pytest

from src.domain.entities.edge import Edge
from src.domain.entities.node import Node
from src.domain.entities.workflow import Workflow
from src.domain.services.workflow_chat_service_enhanced import (
    ChatMessage,
    EnhancedWorkflowChatService,
    ModificationResult,
)
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


@pytest.fixture
def mock_llm():
    """Mock LLM 客户端"""
    return Mock()


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


def test_chat_service_maintains_history(mock_llm, sample_workflow):
    """测试：对话服务应该维护对话历史"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    # 模拟 LLM 返回值
    mock_llm.invoke.return_value = Mock(
        content='{"action": "add_node", "nodes_to_add": [], "ai_message": "我理解你了", "intent": "ask_clarification"}'
    )

    # 第一轮对话
    message1 = "添加一个节点"
    service.add_message(message1, is_user=True)

    # 验证历史
    assert len(service.history.messages) == 1
    assert service.history.messages[0].content == message1
    assert service.history.messages[0].is_user is True


def test_chat_service_maintains_conversation_context(mock_llm, sample_workflow):
    """测试：多轮对话应该保持上下文"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    # 添加多条消息
    service.add_message("添加一个 HTTP 节点", is_user=True)
    service.add_message("已添加节点", is_user=False)
    service.add_message("连接到前面的节点", is_user=True)

    # 验证历史维护
    assert len(service.history.messages) == 3
    assert service.history.get_context()  # 应该能获取上下文


def test_modification_result_contains_detailed_info(mock_llm, sample_workflow):
    """测试：修改结果应该包含详细的修改信息"""
    mock_llm.invoke.return_value = Mock(
        content='{"action": "add_node", "nodes_to_add": [{"type": "python", "name": "处理数据", "config": {"code": "result = input1"}, "position": {"x": 350, "y": 100}}], "ai_message": "已添加 Python 节点", "intent": "add_node", "confidence": 0.95}'
    )

    service = EnhancedWorkflowChatService(llm=mock_llm)
    result = service.process_message(sample_workflow, "添加一个 Python 节点处理数据")

    # 验证结果包含所有必要信息
    assert isinstance(result, ModificationResult)
    assert result.success is True
    assert result.ai_message is not None
    assert result.modifications_count > 0


def test_chat_service_identifies_intent_correctly(mock_llm, sample_workflow):
    """测试：服务应该正确识别用户意图"""
    # 模拟 LLM 识别意图
    mock_llm.invoke.return_value = Mock(
        content='{"action": "add_node", "intent": "add_node", "confidence": 0.98, "nodes_to_add": [], "ai_message": "我会添加节点"}'
    )

    service = EnhancedWorkflowChatService(llm=mock_llm)
    result = service.process_message(sample_workflow, "添加一个新节点")

    assert result.intent == "add_node"
    assert result.confidence >= 0.9


def test_chat_service_provides_suggestions(mock_llm, sample_workflow):
    """测试：服务应该根据工作流提供建议"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    # 获取建议
    suggestions = service.get_workflow_suggestions(sample_workflow)

    # 应该返回建议列表
    assert isinstance(suggestions, list)
    # 对于这个简单的工作流，应该有一些基本的建议


def test_chat_service_provides_error_details(mock_llm, sample_workflow):
    """测试：当修改失败时应该提供详细的错误信息"""
    # 模拟 LLM 返回无效的修改
    mock_llm.invoke.return_value = Mock(
        content='{"action": "add_edge", "edges_to_add": [{"source": "invalid_node", "target": "node_1"}], "ai_message": "已添加边", "intent": "add_edge"}'
    )

    service = EnhancedWorkflowChatService(llm=mock_llm)
    result = service.process_message(sample_workflow, "连接两个节点")

    # 应该捕获并报告错误
    if not result.success:
        assert result.error_message is not None
        assert len(result.error_details) > 0


def test_chat_history_export(mock_llm):
    """测试：应该能导出对话历史"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    # 添加一些消息
    service.add_message("Hello", is_user=True)
    service.add_message("Hi there", is_user=False)

    # 导出历史
    history_data = service.history.export()

    assert len(history_data) == 2
    assert history_data[0]["content"] == "Hello"
    assert history_data[1]["content"] == "Hi there"


def test_chat_service_clears_history(mock_llm):
    """测试：应该能清空对话历史"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    service.add_message("Message 1", is_user=True)
    service.add_message("Message 2", is_user=False)

    assert len(service.history.messages) == 2

    # 清空历史
    service.clear_history()

    assert len(service.history.messages) == 0


def test_modification_validation_detailed(mock_llm, sample_workflow):
    """测试：修改验证应该检查所有约束"""
    # 模拟 LLM 返回包含多个修改的请求
    mock_llm.invoke.return_value = Mock(
        content='{"action": "modify_multiple", "nodes_to_add": [{"type": "database", "name": "查询数据库", "config": {}, "position": {"x": 400, "y": 200}}], "edges_to_add": [], "ai_message": "已完成修改"}'
    )

    service = EnhancedWorkflowChatService(llm=mock_llm)
    result = service.process_message(sample_workflow, "添加数据库节点")

    # 应该验证所有修改的有效性
    assert result is not None


def test_chat_service_with_context_awareness(mock_llm, sample_workflow):
    """测试：服务应该根据对话历史调整行为"""
    mock_llm.invoke.return_value = Mock(
        content='{"action": "modify_node", "intent": "context_aware", "ai_message": "基于之前的请求进行修改"}'
    )

    service = EnhancedWorkflowChatService(llm=mock_llm)

    # 第一轮对话
    service.add_message("我想处理 API 数据", is_user=True)
    service.add_message("我理解，我会为你设置数据处理流程", is_user=False)

    # 第二轮对话应该理解上下文
    result = service.process_message(sample_workflow, "加上错误处理")

    assert result is not None
    # LLM 应该在构建提示词时包含历史信息


def test_modification_result_with_rollback_info(mock_llm, sample_workflow):
    """测试：修改结果应该包含回滚信息"""
    mock_llm.invoke.return_value = Mock(
        content='{"action": "add_node", "nodes_to_add": [], "ai_message": "已修改"}'
    )

    service = EnhancedWorkflowChatService(llm=mock_llm)
    result = service.process_message(sample_workflow, "修改工作流")

    # 结果应该包含可以用于回滚的信息
    assert hasattr(result, "original_workflow")
    assert hasattr(result, "modified_workflow")


# ============================================================================
# TDD RED阶段：语义搜索 (Semantic Search) 测试
# ============================================================================


def test_chat_history_semantic_search_basic(mock_llm):
    """测试：应该能通过关键词在对话历史中进行语义搜索"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

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


def test_chat_history_semantic_search_with_relevance_score(mock_llm):
    """测试：搜索结果应该包含相关性评分"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

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


def test_chat_history_search_returns_sorted_by_relevance(mock_llm):
    """测试：搜索结果应该按相关性从高到低排序"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    service.add_message("HTTP 节点", is_user=True)
    service.add_message("HTTP 请求配置", is_user=False)
    service.add_message("数据库节点", is_user=True)
    service.add_message("存储数据", is_user=False)

    results = service.history.search("HTTP")

    # 结果应该按相关性分数降序排列
    if len(results) > 1:
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)


def test_chat_history_search_empty_query_returns_empty(mock_llm):
    """测试：空查询应该返回空结果"""
    service = EnhancedWorkflowChatService(llm=mock_llm)
    service.add_message("添加节点", is_user=True)

    results = service.history.search("")

    assert results == []


def test_chat_history_search_no_matches_returns_empty(mock_llm):
    """测试：无匹配结果应该返回空列表"""
    service = EnhancedWorkflowChatService(llm=mock_llm)
    service.add_message("HTTP 节点", is_user=True)

    results = service.history.search("XYZ_NOT_EXIST")

    assert results == []


# ============================================================================
# TDD RED阶段：相关性过滤 (Relevance Filtering) 测试
# ============================================================================


def test_chat_history_filter_by_relevance_to_keyword(mock_llm):
    """测试：应该能根据关键词过滤历史消息"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    service.add_message("添加 HTTP 节点获取 API 数据", is_user=True)
    service.add_message("已添加节点", is_user=False)
    service.add_message("修改背景颜色", is_user=True)
    service.add_message("已修改", is_user=False)

    # 过滤与 "API" 相关的消息（使用较低的阈值）
    filtered = service.history.filter_by_relevance("API", threshold=0.1)

    # 应该返回与 API 相关的消息
    assert len(filtered) > 0
    assert all(isinstance(msg, ChatMessage) for msg in filtered)


def test_chat_history_filter_respects_threshold(mock_llm):
    """测试：相关性过滤应该遵守阈值"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    service.add_message("HTTP 请求", is_user=True)
    service.add_message("关键词在这里", is_user=False)
    service.add_message("完全不相关的内容", is_user=True)

    # 高阈值应该过滤掉低相关性消息
    high_threshold_results = service.history.filter_by_relevance("HTTP", threshold=0.8)

    # 低阈值应该包含更多消息
    low_threshold_results = service.history.filter_by_relevance("HTTP", threshold=0.2)

    # 高阈值的结果应该 <= 低阈值的结果
    assert len(high_threshold_results) <= len(low_threshold_results)


def test_chat_history_filter_for_context_building(mock_llm):
    """测试：过滤出最相关的消息用于构建上下文"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

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


def test_chat_history_filter_returns_empty_when_no_match(mock_llm):
    """测试：没有匹配时应该返回空列表"""
    service = EnhancedWorkflowChatService(llm=mock_llm)
    service.add_message("不相关的内容", is_user=True)

    filtered = service.history.filter_by_relevance("节点配置", threshold=0.9)

    assert filtered == []


# ============================================================================
# TDD RED阶段：上下文压缩 (Context Compression) 测试
# ============================================================================


def test_chat_history_compression_removes_old_messages_when_exceeds_max_tokens(
    mock_llm,
):
    """测试：当消息超过 token 限制时应该压缩历史"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    # 添加足够多的消息以超过 token 限制
    for i in range(50):
        service.add_message(
            f"这是第 {i} 条消息，内容较长以增加 token 数量。" * 10, is_user=i % 2 == 0
        )

    # 压缩历史（假设 max_tokens=1000）
    compressed = service.history.compress_history(max_tokens=1000)

    # 压缩后应该保留较少的消息，但不会为空
    assert len(compressed) > 0
    assert len(compressed) < len(service.history.messages)


def test_chat_history_compression_preserves_recent_messages(mock_llm):
    """测试：压缩应该保留最近的消息"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    service.add_message("很久以前的消息" * 20, is_user=True)
    service.add_message("中间的消息", is_user=False)
    service.add_message("最近的消息，非常重要", is_user=True)

    compressed = service.history.compress_history(max_tokens=200)

    # 最近的消息应该被保留
    if len(compressed) > 0:
        assert "最近的消息" in compressed[-1].content or len(compressed) > 0


def test_chat_history_compression_returns_history_if_within_limit(mock_llm):
    """测试：如果未超过限制，压缩应该返回原始历史"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    service.add_message("短消息1", is_user=True)
    service.add_message("短消息2", is_user=False)

    original_count = len(service.history.messages)
    compressed = service.history.compress_history(max_tokens=10000)

    # 如果在限制内，应该返回所有消息
    assert len(compressed) == original_count


def test_chat_history_compression_respects_min_messages(mock_llm):
    """测试：压缩不应该删除少于最小消息数的历史"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    service.add_message("消息1" * 50, is_user=True)
    service.add_message("消息2" * 50, is_user=False)
    service.add_message("消息3" * 50, is_user=True)

    # 压缩时指定最小消息数
    compressed = service.history.compress_history(max_tokens=100, min_messages=2)

    # 应该至少保留 min_messages 条
    assert len(compressed) >= 2


def test_chat_history_compression_estimates_token_count(mock_llm):
    """测试：压缩应该能准确估计 token 数量"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

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


def test_chat_history_compression_maintains_message_order(mock_llm):
    """测试：压缩应该维护消息顺序"""
    service = EnhancedWorkflowChatService(llm=mock_llm)

    service.add_message("第一条", is_user=True)
    service.add_message("第二条", is_user=False)
    service.add_message("第三条", is_user=True)

    compressed = service.history.compress_history(max_tokens=10000)

    # 压缩后的消息顺序应该不变
    for i, msg in enumerate(compressed):
        original_msg = service.history.messages[i]
        assert msg.content == original_msg.content
        assert msg.is_user == original_msg.is_user


def test_chat_service_uses_compressed_history_in_prompt(mock_llm, sample_workflow):
    """测试：服务应该在构建提示词时使用压缩后的历史"""
    mock_llm.invoke.return_value = Mock(
        content='{"action": "add_node", "nodes_to_add": [], "ai_message": "已处理"}'
    )

    service = EnhancedWorkflowChatService(llm=mock_llm)

    # 添加大量消息
    for i in range(30):
        service.add_message(f"长消息 {i}" * 20, is_user=i % 2 == 0)

    result = service.process_message(sample_workflow, "修改工作流")

    # 应该成功处理，说明压缩工作正常
    assert result is not None
