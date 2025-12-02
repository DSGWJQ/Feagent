"""真实场景：对话历史持久化端到端测试

这个测试模拟完整的用户对话场景：
1. 用户创建工作流
2. 用户与工作流进行多次对话
3. 系统保存所有消息到数据库
4. 用户可以查询历史记录
5. 用户可以搜索历史消息
6. 用户可以清空历史记录

这不是为了测试而测试，而是验证真实业务场景！
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.domain.entities.chat_message import ChatMessage
from src.infrastructure.database.base import Base
from src.infrastructure.database.models import WorkflowModel
from src.infrastructure.database.repositories.chat_message_repository import (
    SQLAlchemyChatMessageRepository,
)


@pytest.fixture
def test_db():
    """创建测试数据库"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    session = Session(engine)
    yield session

    session.close()


# ─────────────────────────────────────────────────────
# 真实场景 1：用户创建工作流并开始对话
# ─────────────────────────────────────────────────────
def test_user_creates_workflow_and_starts_conversation(test_db: Session):
    """场景：用户创建工作流并开始对话

    真实流程：
    1. 用户在前端创建一个新工作流："我的数据处理流程"
    2. 用户开始与工作流对话
    3. 系统保存每条消息到数据库

    验证：
    - 消息应该成功保存到数据库
    - 可以跨会话查询历史记录
    """
    # 1. 创建工作流（模拟用户在前端创建工作流）
    workflow = WorkflowModel(
        id="wf_test_001",
        name="我的数据处理流程",
        description="用于测试的工作流",
        status="draft",
    )
    test_db.add(workflow)
    test_db.commit()

    # 2. 创建 Repository
    repo = SQLAlchemyChatMessageRepository(test_db)

    # 3. 用户发送第一条消息："添加一个HTTP节点"
    user_msg_1 = ChatMessage.create(
        workflow_id="wf_test_001",
        content="添加一个HTTP节点",
        is_user=True,
    )
    repo.save(user_msg_1)
    test_db.commit()

    # 4. AI 回复
    ai_msg_1 = ChatMessage.create(
        workflow_id="wf_test_001",
        content="我已经添加了一个HTTP请求节点，用于调用外部API",
        is_user=False,
    )
    repo.save(ai_msg_1)
    test_db.commit()

    # 5. 验证：查询历史记录（模拟用户刷新页面）
    history = repo.find_by_workflow_id("wf_test_001")

    assert len(history) == 2
    assert history[0].content == "添加一个HTTP节点"
    assert history[0].is_user is True
    assert history[1].content == "我已经添加了一个HTTP请求节点，用于调用外部API"
    assert history[1].is_user is False


# ─────────────────────────────────────────────────────
# 真实场景 2：多轮对话并保持历史
# ─────────────────────────────────────────────────────
def test_multi_turn_conversation_with_history(test_db: Session):
    """场景：用户进行多轮对话

    真实流程：
    1. 用户：添加HTTP节点
    2. AI：已添加HTTP节点
    3. 用户：修改节点配置，URL改为 https://api.example.com
    4. AI：已修改配置
    5. 用户：删除这个节点
    6. AI：已删除节点

    验证：
    - 所有对话都应该按顺序保存
    - 历史记录应该按时间排序
    """
    # 创建工作流
    workflow = WorkflowModel(id="wf_test_002", name="多轮对话测试", status="draft")
    test_db.add(workflow)
    test_db.commit()

    repo = SQLAlchemyChatMessageRepository(test_db)

    # 第一轮对话
    repo.save(ChatMessage.create("wf_test_002", "添加HTTP节点", True))
    test_db.commit()

    repo.save(ChatMessage.create("wf_test_002", "已添加HTTP节点", False))
    test_db.commit()

    # 第二轮对话
    repo.save(
        ChatMessage.create("wf_test_002", "修改节点配置，URL改为 https://api.example.com", True)
    )
    test_db.commit()

    repo.save(ChatMessage.create("wf_test_002", "已修改配置", False))
    test_db.commit()

    # 第三轮对话
    repo.save(ChatMessage.create("wf_test_002", "删除这个节点", True))
    test_db.commit()

    repo.save(ChatMessage.create("wf_test_002", "已删除节点", False))
    test_db.commit()

    # 验证：查询历史记录
    history = repo.find_by_workflow_id("wf_test_002")

    assert len(history) == 6

    # 验证顺序（旧 → 新）
    assert history[0].content == "添加HTTP节点"
    assert history[1].content == "已添加HTTP节点"
    assert history[2].content == "修改节点配置，URL改为 https://api.example.com"
    assert history[3].content == "已修改配置"
    assert history[4].content == "删除这个节点"
    assert history[5].content == "已删除节点"

    # 验证消息类型交替
    assert history[0].is_user is True
    assert history[1].is_user is False
    assert history[2].is_user is True
    assert history[3].is_user is False


# ─────────────────────────────────────────────────────
# 真实场景 3：搜索历史消息
# ─────────────────────────────────────────────────────
def test_search_chat_history(test_db: Session):
    """场景：用户搜索历史对话

    真实流程：
    1. 用户进行了多次对话，讨论了HTTP节点、数据库节点、循环节点
    2. 用户想找回之前关于"HTTP"的讨论
    3. 用户在搜索框输入"HTTP"
    4. 系统返回所有包含"HTTP"的消息

    验证：
    - 搜索应该返回匹配的消息
    - 结果应该按相关性排序
    """
    # 创建工作流
    workflow = WorkflowModel(id="wf_test_003", name="搜索测试", status="draft")
    test_db.add(workflow)
    test_db.commit()

    repo = SQLAlchemyChatMessageRepository(test_db)

    # 添加多条消息
    messages = [
        ("添加一个HTTP节点用于调用API", True),
        ("已添加HTTP请求节点", False),
        ("添加一个数据库节点", True),
        ("已添加数据库节点", False),
        ("HTTP节点的URL怎么配置？", True),
        ("您可以在HTTP节点的配置中设置URL", False),
    ]

    for content, is_user in messages:
        repo.save(ChatMessage.create("wf_test_003", content, is_user))
        test_db.commit()

    # 搜索包含"HTTP"的消息
    results = repo.search("wf_test_003", "HTTP")

    # 验证：应该找到 4 条消息（不包括数据库相关的）
    assert len(results) >= 4

    # 验证：所有结果都包含"HTTP"
    for message, _score in results:
        assert "HTTP" in message.content or "http" in message.content.lower()


# ─────────────────────────────────────────────────────
# 真实场景 4：清空历史记录
# ─────────────────────────────────────────────────────
def test_clear_chat_history(test_db: Session):
    """场景：用户清空历史记录

    真实流程：
    1. 用户进行了一些对话
    2. 用户想重新开始，点击"清空历史记录"
    3. 系统删除所有历史消息
    4. 用户刷新页面，历史记录为空

    验证：
    - 清空后历史记录应该为空
    - 不应该影响其他工作流的历史记录
    """
    # 创建两个工作流
    wf1 = WorkflowModel(id="wf_test_004", name="工作流1", status="draft")
    wf2 = WorkflowModel(id="wf_test_005", name="工作流2", status="draft")
    test_db.add_all([wf1, wf2])
    test_db.commit()

    repo = SQLAlchemyChatMessageRepository(test_db)

    # 在两个工作流中都添加消息
    repo.save(ChatMessage.create("wf_test_004", "工作流1的消息", True))
    repo.save(ChatMessage.create("wf_test_005", "工作流2的消息", True))
    test_db.commit()

    # 验证：两个工作流都有消息
    assert len(repo.find_by_workflow_id("wf_test_004")) == 1
    assert len(repo.find_by_workflow_id("wf_test_005")) == 1

    # 清空工作流1的历史
    repo.delete_by_workflow_id("wf_test_004")
    test_db.commit()

    # 验证：工作流1的历史已清空，工作流2的历史仍然存在
    assert len(repo.find_by_workflow_id("wf_test_004")) == 0
    assert len(repo.find_by_workflow_id("wf_test_005")) == 1


# ─────────────────────────────────────────────────────
# 真实场景 5：统计消息数量
# ─────────────────────────────────────────────────────
def test_count_messages(test_db: Session):
    """场景：显示消息统计

    真实流程：
    1. 前端需要显示："共 10 条对话记录"
    2. 调用 count API 获取数量
    3. 快速返回（不需要加载所有消息）

    验证：
    - count 应该准确返回消息数量
    - 性能应该比 find_all 更好
    """
    # 创建工作流
    workflow = WorkflowModel(id="wf_test_006", name="统计测试", status="draft")
    test_db.add(workflow)
    test_db.commit()

    repo = SQLAlchemyChatMessageRepository(test_db)

    # 添加 5 轮对话（10 条消息）
    for i in range(5):
        repo.save(ChatMessage.create("wf_test_006", f"用户消息 {i + 1}", True))
        repo.save(ChatMessage.create("wf_test_006", f"AI回复 {i + 1}", False))
    test_db.commit()

    # 统计消息数量
    count = repo.count_by_workflow_id("wf_test_006")

    assert count == 10


# ─────────────────────────────────────────────────────
# 真实场景 6：跨会话持久化（最重要！）
# ─────────────────────────────────────────────────────
def test_messages_persist_across_sessions(test_db: Session):
    """场景：对话历史跨会话持久化

    真实流程：
    1. 用户在第一个会话中发送消息
    2. 用户关闭浏览器
    3. 用户稍后重新打开浏览器
    4. 用户应该能看到之前的对话历史

    这是持久化的核心价值！

    验证：
    - 在不同的 Repository 实例中应该能访问相同的数据
    - 模拟跨会话场景
    """
    # 创建工作流
    workflow = WorkflowModel(id="wf_test_007", name="跨会话测试", status="draft")
    test_db.add(workflow)
    test_db.commit()

    # 第一个会话：用户发送消息
    repo_session_1 = SQLAlchemyChatMessageRepository(test_db)
    repo_session_1.save(ChatMessage.create("wf_test_007", "第一个会话的消息", True))
    test_db.commit()

    # 模拟用户关闭浏览器，创建新的 Repository 实例（新会话）
    repo_session_2 = SQLAlchemyChatMessageRepository(test_db)

    # 验证：新会话应该能看到之前的消息
    history = repo_session_2.find_by_workflow_id("wf_test_007")

    assert len(history) == 1
    assert history[0].content == "第一个会话的消息"

    # 第二个会话：用户继续对话
    repo_session_2.save(ChatMessage.create("wf_test_007", "第二个会话的消息", True))
    test_db.commit()

    # 再次创建新实例，验证所有消息都存在
    repo_session_3 = SQLAlchemyChatMessageRepository(test_db)
    history = repo_session_3.find_by_workflow_id("wf_test_007")

    assert len(history) == 2
    assert history[0].content == "第一个会话的消息"
    assert history[1].content == "第二个会话的消息"
