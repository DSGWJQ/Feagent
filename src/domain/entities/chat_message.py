"""ChatMessage 实体 - 工作流对话消息

业务定义：
- ChatMessage 记录用户与工作流的对话历史
- 每条消息关联到特定的工作流
- 消息区分用户消息和 AI 回复
- 消息按时间顺序保存，用于展示对话历史

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- 使用 dataclass 简化样板代码
- 通过工厂方法 create() 封装创建逻辑
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from src.domain.exceptions import DomainError


@dataclass
class ChatMessage:
    """ChatMessage 实体

    属性说明：
    - id: 唯一标识符（msg_ 前缀）
    - workflow_id: 关联的工作流 ID
    - content: 消息内容
    - is_user: 是否为用户消息（True: 用户消息，False: AI 回复）
    - timestamp: 消息时间戳（UTC）

    使用场景：
    1. 用户在工作流编辑页面发送消息
    2. AI 回复并修改工作流
    3. 用户查看历史对话记录
    4. 用户搜索历史对话

    为什么使用 dataclass？
    1. 自动生成 __init__、__repr__、__eq__ 等方法
    2. 类型注解清晰，IDE 友好
    3. 符合 Python 3.11+ 最佳实践
    4. 纯 Python，不依赖框架（符合 DDD 要求）
    """

    id: str
    workflow_id: str
    content: str
    is_user: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        workflow_id: str,
        content: str,
        is_user: bool,
    ) -> "ChatMessage":
        """创建 ChatMessage（工厂方法）

        参数：
            workflow_id: 工作流 ID
            content: 消息内容
            is_user: 是否为用户消息

        返回：
            ChatMessage 实例

        抛出：
            DomainError: 当输入参数不合法时

        业务规则：
        1. workflow_id 不能为空（必须关联到工作流）
        2. content 不能为空（空消息没有意义）
        3. 自动生成唯一 ID（msg_ 前缀）
        4. 自动记录时间戳（UTC）
        """
        # 验证：workflow_id 不能为空
        if not workflow_id or (isinstance(workflow_id, str) and not workflow_id.strip()):
            raise DomainError("workflow_id不能为空")

        # 验证：content 不能为空
        if not content or (isinstance(content, str) and not content.strip()):
            raise DomainError("content不能为空")

        # 生成唯一 ID
        message_id = f"msg_{uuid4().hex[:16]}"

        return cls(
            id=message_id,
            workflow_id=workflow_id,
            content=content,
            is_user=is_user,
            timestamp=datetime.now(UTC),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于 API 响应和数据库存储）

        返回：
            包含所有字段的字典

        示例：
            {
                "id": "msg_abc123",
                "workflow_id": "wf_12345",
                "content": "添加HTTP节点",
                "is_user": True,
                "timestamp": "2025-01-29T10:00:00Z"
            }
        """
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "content": self.content,
            "is_user": self.is_user,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatMessage":
        """从字典恢复 ChatMessage（用于从数据库读取）

        参数：
            data: 包含消息数据的字典

        返回：
            ChatMessage 实例

        示例：
            data = {
                "id": "msg_abc123",
                "workflow_id": "wf_12345",
                "content": "添加HTTP节点",
                "is_user": True,
                "timestamp": "2025-01-29T10:00:00Z"
            }
            message = ChatMessage.from_dict(data)
        """
        # 解析时间戳
        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            # ISO 8601 格式字符串 → datetime
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        return cls(
            id=data["id"],
            workflow_id=data["workflow_id"],
            content=data["content"],
            is_user=data["is_user"],
            timestamp=timestamp,
        )
