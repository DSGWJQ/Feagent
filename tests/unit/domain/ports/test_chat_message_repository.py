"""ChatMessageRepository Port 测试

真实场景：
1. Repository 是 Domain Layer 定义的接口（Protocol）
2. Infrastructure Layer 会实现这个接口
3. 测试确保 Port 定义了所有必要的方法签名

注意：这不是测试实现，而是测试接口定义本身
"""

import inspect
from typing import Protocol, get_type_hints

from src.domain.ports.chat_message_repository import ChatMessageRepository


# ─────────────────────────────────────────────────────
# 真实场景 1：验证 Repository 是 Protocol
# ─────────────────────────────────────────────────────
def test_chat_message_repository_is_protocol():
    """场景：确保 Repository 是 Protocol（接口）

    真实原因：
    - Protocol 允许 Duck Typing
    - 符合 DDD 的依赖倒置原则
    - Infrastructure 可以实现任何符合接口的类
    """
    # 验证：ChatMessageRepository 继承自 Protocol
    assert issubclass(ChatMessageRepository, Protocol)


# ─────────────────────────────────────────────────────
# 真实场景 2：验证必要的方法存在
# ─────────────────────────────────────────────────────
def test_repository_has_save_method():
    """场景：保存消息（用户发送消息时）

    真实流程：
    1. 用户在工作流中发送消息
    2. UseCase 调用 repository.save(message)
    3. 消息被持久化到数据库
    """
    # 验证：save 方法存在
    assert hasattr(ChatMessageRepository, "save")

    # 验证：save 方法签名正确
    method = ChatMessageRepository.save
    sig = inspect.signature(method)

    # 应该有 2 个参数：self + message
    params = list(sig.parameters.keys())
    assert len(params) == 2
    assert params[0] == "self"
    assert params[1] == "message"


def test_repository_has_find_by_workflow_id_method():
    """场景：查询工作流的历史记录

    真实流程：
    1. 用户打开工作流的对话历史页面
    2. 前端调用 GET /api/workflows/{id}/chat-history
    3. UseCase 调用 repository.find_by_workflow_id(workflow_id)
    4. 返回该工作流的所有历史消息
    """
    assert hasattr(ChatMessageRepository, "find_by_workflow_id")

    method = ChatMessageRepository.find_by_workflow_id
    sig = inspect.signature(method)

    # 应该有参数：self, workflow_id, limit
    params = list(sig.parameters.keys())
    assert "self" in params
    assert "workflow_id" in params
    assert "limit" in params

    # limit 应该有默认值
    assert sig.parameters["limit"].default is not inspect.Parameter.empty


def test_repository_has_search_method():
    """场景：搜索历史对话

    真实流程：
    1. 用户在历史记录中搜索关键词："HTTP节点"
    2. 前端调用 GET /api/workflows/{id}/chat-search?query=HTTP节点
    3. UseCase 调用 repository.search(workflow_id, query)
    4. 返回包含关键词的消息列表
    """
    assert hasattr(ChatMessageRepository, "search")

    method = ChatMessageRepository.search
    sig = inspect.signature(method)

    params = list(sig.parameters.keys())
    assert "self" in params
    assert "workflow_id" in params
    assert "query" in params


def test_repository_has_delete_by_workflow_id_method():
    """场景：清空工作流的对话历史

    真实流程：
    1. 用户点击"清空历史记录"按钮
    2. 前端调用 DELETE /api/workflows/{id}/chat-history
    3. UseCase 调用 repository.delete_by_workflow_id(workflow_id)
    4. 该工作流的所有消息被删除
    """
    assert hasattr(ChatMessageRepository, "delete_by_workflow_id")

    method = ChatMessageRepository.delete_by_workflow_id
    sig = inspect.signature(method)

    params = list(sig.parameters.keys())
    assert "self" in params
    assert "workflow_id" in params


def test_repository_has_count_by_workflow_id_method():
    """场景：显示消息数量

    真实流程：
    1. 前端显示："共 25 条对话记录"
    2. UseCase 调用 repository.count_by_workflow_id(workflow_id)
    3. 返回消息数量
    """
    assert hasattr(ChatMessageRepository, "count_by_workflow_id")

    method = ChatMessageRepository.count_by_workflow_id
    sig = inspect.signature(method)

    params = list(sig.parameters.keys())
    assert "self" in params
    assert "workflow_id" in params


# ─────────────────────────────────────────────────────
# 真实场景 3：验证方法返回类型
# ─────────────────────────────────────────────────────
def test_save_method_returns_none():
    """场景：save 方法不需要返回值

    真实原因：
    - 保存操作是副作用
    - 不需要返回值
    - 如果失败会抛出异常
    """
    method = ChatMessageRepository.save
    sig = inspect.signature(method)

    # 返回类型应该是 None
    return_annotation = sig.return_annotation
    assert return_annotation is None or return_annotation is type(None)


def test_find_by_workflow_id_returns_list():
    """场景：find_by_workflow_id 返回消息列表

    真实原因：
    - 一个工作流可能有多条消息
    - 返回 list[ChatMessage]
    """
    method = ChatMessageRepository.find_by_workflow_id
    hints = get_type_hints(method)

    # 返回类型应该是 list[ChatMessage]
    assert "return" in hints
    return_type = str(hints["return"])
    assert "list" in return_type.lower()
    assert "ChatMessage" in return_type


def test_search_returns_list_of_tuples():
    """场景：search 返回 (消息, 相关性分数) 的列表

    真实原因：
    - 搜索结果需要按相关性排序
    - 返回 list[tuple[ChatMessage, float]]
    - float 是相关性分数（0-1）
    """
    method = ChatMessageRepository.search
    hints = get_type_hints(method)

    # 返回类型应该是 list[tuple[ChatMessage, float]]
    assert "return" in hints
    return_type = str(hints["return"])
    assert "list" in return_type.lower()
    assert "tuple" in return_type.lower()


def test_count_returns_int():
    """场景：count_by_workflow_id 返回整数

    真实原因：
    - 消息数量是整数
    - 用于显示"共 N 条消息"
    """
    method = ChatMessageRepository.count_by_workflow_id
    hints = get_type_hints(method)

    # 返回类型应该是 int
    assert "return" in hints
    assert hints["return"] is int


# ─────────────────────────────────────────────────────
# 真实场景 4：验证参数类型
# ─────────────────────────────────────────────────────
def test_save_accepts_chat_message():
    """场景：save 方法接受 ChatMessage 实体

    真实原因：
    - Repository 操作 Domain Entity
    - 不是 ORM Model，不是 DTO
    """
    method = ChatMessageRepository.save
    hints = get_type_hints(method)

    # message 参数应该是 ChatMessage 类型
    assert "message" in hints
    param_type = str(hints["message"])
    assert "ChatMessage" in param_type


def test_find_by_workflow_id_accepts_string_and_int():
    """场景：find_by_workflow_id 接受 workflow_id (str) 和 limit (int)

    真实原因：
    - workflow_id 是字符串
    - limit 是整数（限制返回数量）
    """
    method = ChatMessageRepository.find_by_workflow_id
    hints = get_type_hints(method)

    # workflow_id 应该是 str
    assert "workflow_id" in hints
    assert hints["workflow_id"] is str

    # limit 应该是 int
    assert "limit" in hints
    assert hints["limit"] is int


def test_search_accepts_workflow_id_and_query_string():
    """场景：search 接受 workflow_id (str) 和 query (str)

    真实原因：
    - workflow_id 是字符串
    - query 是搜索关键词字符串
    """
    method = ChatMessageRepository.search
    hints = get_type_hints(method)

    assert "workflow_id" in hints
    assert hints["workflow_id"] is str

    assert "query" in hints
    assert hints["query"] is str


# ─────────────────────────────────────────────────────
# 真实场景 5：确保接口完整性
# ─────────────────────────────────────────────────────
def test_repository_has_all_necessary_methods():
    """场景：Repository 包含所有必要的方法

    真实场景对应：
    - save: 保存消息
    - find_by_workflow_id: 获取历史记录
    - search: 搜索消息
    - delete_by_workflow_id: 清空历史
    - count_by_workflow_id: 统计数量

    这 5 个方法支持所有聊天功能
    """
    required_methods = [
        "save",
        "find_by_workflow_id",
        "search",
        "delete_by_workflow_id",
        "count_by_workflow_id",
    ]

    for method_name in required_methods:
        assert hasattr(ChatMessageRepository, method_name), f"缺少方法: {method_name}"
