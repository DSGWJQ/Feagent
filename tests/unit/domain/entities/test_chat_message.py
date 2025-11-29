"""ChatMessage Entity 单元测试

真实场景：
1. 用户和工作流进行对话
2. 每条消息（用户消息 + AI 回复）都需要记录
3. 消息需要关联到特定工作流
4. 消息需要唯一标识以便后续查询
"""

from datetime import UTC, datetime

import pytest

from src.domain.entities.chat_message import ChatMessage
from src.domain.exceptions import DomainError


# ─────────────────────────────────────────────────────
# 真实场景 1：用户发起对话
# ─────────────────────────────────────────────────────
def test_create_user_message_in_workflow_conversation():
    """场景：用户在工作流编辑页面发送消息

    真实流程：
    1. 用户在前端输入："添加一个HTTP节点"
    2. 系统创建 ChatMessage 记录这条用户消息
    3. 消息关联到当前工作流 ID
    """
    workflow_id = "wf_12345"
    user_input = "添加一个HTTP节点"

    message = ChatMessage.create(workflow_id=workflow_id, content=user_input, is_user=True)

    # 验证：消息应该有唯一ID
    assert message.id is not None
    assert len(message.id) > 0

    # 验证：消息关联到正确的工作流
    assert message.workflow_id == workflow_id

    # 验证：消息内容正确
    assert message.content == user_input

    # 验证：标记为用户消息
    assert message.is_user is True

    # 验证：记录时间戳（用于历史记录排序）
    assert message.timestamp is not None
    assert isinstance(message.timestamp, datetime)
    # 时间戳应该在合理范围内（最近1分钟）
    now = datetime.now(UTC)
    time_diff = (now - message.timestamp).total_seconds()
    assert 0 <= time_diff <= 60


def test_create_ai_response_message_in_workflow_conversation():
    """场景：AI 回复用户请求

    真实流程：
    1. 用户发送："添加一个HTTP节点"
    2. AI 处理后回复："我已经添加了一个HTTP请求节点"
    3. 系统创建 ChatMessage 记录 AI 的回复
    """
    workflow_id = "wf_12345"
    ai_response = "我已经添加了一个HTTP请求节点"

    message = ChatMessage.create(workflow_id=workflow_id, content=ai_response, is_user=False)

    assert message.id is not None
    assert message.workflow_id == workflow_id
    assert message.content == ai_response
    assert message.is_user is False
    assert message.timestamp is not None


# ─────────────────────────────────────────────────────
# 真实场景 2：多工作流隔离
# ─────────────────────────────────────────────────────
def test_messages_from_different_workflows_are_isolated():
    """场景：多个用户同时编辑不同的工作流

    真实流程：
    1. 用户 A 在工作流 wf_001 中对话
    2. 用户 B 在工作流 wf_002 中对话
    3. 两个工作流的消息应该有不同的 workflow_id
    """
    # 用户 A 的工作流
    msg_a = ChatMessage.create(workflow_id="wf_001", content="添加数据库节点", is_user=True)

    # 用户 B 的工作流
    msg_b = ChatMessage.create(workflow_id="wf_002", content="添加HTTP节点", is_user=True)

    # 验证：两条消息属于不同的工作流
    assert msg_a.workflow_id != msg_b.workflow_id

    # 验证：每条消息都有唯一 ID
    assert msg_a.id != msg_b.id


# ─────────────────────────────────────────────────────
# 真实场景 3：消息唯一性
# ─────────────────────────────────────────────────────
def test_each_message_has_unique_id():
    """场景：同一个工作流的多条消息

    真实流程：
    1. 用户在工作流中进行多���对话
    2. 每条消息都需要有唯一 ID 以便后续查询、引用
    """
    workflow_id = "wf_12345"

    msg1 = ChatMessage.create(workflow_id=workflow_id, content="添加HTTP节点", is_user=True)
    msg2 = ChatMessage.create(workflow_id=workflow_id, content="已添加HTTP节点", is_user=False)
    msg3 = ChatMessage.create(workflow_id=workflow_id, content="删除这个节点", is_user=True)

    # 验证：每条消息都有不同的 ID
    ids = {msg1.id, msg2.id, msg3.id}
    assert len(ids) == 3  # 三个唯一 ID

    # 验证：所有消息都属于同一个工作流
    assert msg1.workflow_id == msg2.workflow_id == msg3.workflow_id


# ─────────────────────────────────────────────────────
# 真实场景 4：数据验证（防止脏数据）
# ─────────────────────────────────────────────────────
def test_cannot_create_message_without_workflow_id():
    """场景：防止创建无主消息

    真实问题：
    - 如果消息没有关联工作流，后续无法查询历史记录
    - 会导致数据孤岛
    """
    with pytest.raises(DomainError, match="workflow_id不能为空"):
        ChatMessage.create(workflow_id="", content="添加HTTP节点", is_user=True)


def test_cannot_create_message_with_empty_content():
    """场景：防止创建空消息

    真实问题：
    - 用户误点击发送，或者网络请求错误
    - 空消息对对话历史没有意义
    """
    with pytest.raises(DomainError, match="content不能为空"):
        ChatMessage.create(workflow_id="wf_12345", content="", is_user=True)

    # 空白字符串也应该被拒绝
    with pytest.raises(DomainError, match="content不能为空"):
        ChatMessage.create(workflow_id="wf_12345", content="   ", is_user=True)


def test_cannot_create_message_with_none_workflow_id():
    """场景：防止 None 值

    真实问题：
    - 代码 bug 可能传入 None
    - 数据库外键约束会��败
    """
    with pytest.raises(DomainError, match="workflow_id不能为空"):
        ChatMessage.create(
            workflow_id=None,  # type: ignore
            content="添加HTTP节点",
            is_user=True,
        )


# ─────────────────────────────────────────────────────
# 真实场景 5：序列化（用于 API 响应）
# ─────────────────────────────────────────────────────
def test_message_can_be_serialized_to_dict_for_api_response():
    """场景：前端需要获取对话历史

    真实流程：
    1. 前端调用 GET /api/workflows/{id}/chat-history
    2. 后端查询消息列表
    3. 将 ChatMessage 实体序列化为 JSON 返回
    """
    message = ChatMessage.create(workflow_id="wf_12345", content="添加HTTP节点", is_user=True)

    data = message.to_dict()

    # 验证：包含所有必要字段
    assert "id" in data
    assert "workflow_id" in data
    assert "content" in data
    assert "is_user" in data
    assert "timestamp" in data

    # 验证：字段值正确
    assert data["id"] == message.id
    assert data["workflow_id"] == "wf_12345"
    assert data["content"] == "添加HTTP节点"
    assert data["is_user"] is True

    # 验证：时间戳是 ISO 格式字符串（JSON 兼容）
    assert isinstance(data["timestamp"], str)
    assert "T" in data["timestamp"]  # ISO 8601 格式


# ─────────────────────────────────────────────────────
# 真实场景 6：从字典恢复（用于从数据库读取）
# ─────────────────────────────────────────────────────
def test_message_can_be_reconstructed_from_dict():
    """场景：从数据库读取历史记录

    真实流程：
    1. Repository 从数据库查询 chat_messages 表
    2. 将 ORM Model 转换为 Entity
    3. Entity 需要从字典数据重建
    """
    original = ChatMessage.create(workflow_id="wf_12345", content="添加HTTP节点", is_user=True)

    # 模拟：序列化到数据库，再从数据库读取
    data = original.to_dict()
    reconstructed = ChatMessage.from_dict(data)

    # 验证：重建的对象与原对象相同
    assert reconstructed.id == original.id
    assert reconstructed.workflow_id == original.workflow_id
    assert reconstructed.content == original.content
    assert reconstructed.is_user == original.is_user
    assert reconstructed.timestamp == original.timestamp


# ─────────────────────────────────────────────────────
# 真实场景 7：时间戳排序（用于显示历史记录）
# ─────────────────────────────────────────────────────
def test_messages_can_be_sorted_by_timestamp():
    """场景：前端显示对话历史（按时间顺序）

    真实流程：
    1. 用户查看历史记录
    2. 消息应该按时间顺序显示（旧 → 新）
    3. Entity 应该支持按 timestamp 排序
    """
    import time

    workflow_id = "wf_12345"

    msg1 = ChatMessage.create(workflow_id=workflow_id, content="第一条消息", is_user=True)
    time.sleep(0.01)  # 确保时间戳不同

    msg2 = ChatMessage.create(workflow_id=workflow_id, content="第二条消息", is_user=False)
    time.sleep(0.01)

    msg3 = ChatMessage.create(workflow_id=workflow_id, content="第三条消息", is_user=True)

    # 模拟：乱序列表
    messages = [msg3, msg1, msg2]

    # 排序
    sorted_messages = sorted(messages, key=lambda m: m.timestamp)

    # 验证：排序后应该是 msg1, msg2, msg3
    assert sorted_messages[0].content == "第一条消息"
    assert sorted_messages[1].content == "第二条消息"
    assert sorted_messages[2].content == "第三条消息"
