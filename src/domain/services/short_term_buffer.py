"""短期记忆缓冲区 (ShortTermBuffer) - Step 2: 短期记忆缓冲与饱和事件

业务定义：
- ShortTermBuffer 存储对话轮次信息
- 每个轮次包含 turn_id、role、content、tool_refs、token_usage
- 用于跟踪短期对话历史和 token 使用情况

设计原则：
- 轻量级数据结构，易于序列化
- 支持快速查询和过滤
- 与 SessionContext 集成
- 为上下文压缩提供数据基础

使用场景：
- 记录每轮对话的详细信息
- 计算短期记忆的 token 使用
- 检测上下文饱和
- 为压缩算法提供输入
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TurnRole(str, Enum):
    """对话轮次角色

    枚举值：
    - USER: 用户输入
    - ASSISTANT: 助手回复
    - SYSTEM: 系统消息
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ShortTermBuffer:
    """短期记忆缓冲区

    属性：
    - turn_id: 轮次唯一标识
    - role: 角色（user/assistant/system）
    - content: 内容文本
    - tool_refs: 工具调用引用列表
    - token_usage: token 使用统计
    - timestamp: 创建时间戳

    使用示例：
        buffer = ShortTermBuffer(
            turn_id="turn_001",
            role=TurnRole.USER,
            content="Hello, how are you?",
            tool_refs=[],
            token_usage={"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10}
        )
    """

    turn_id: str
    role: TurnRole
    content: str
    tool_refs: list[str] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def get_total_tokens(self) -> int:
        """获取总 token 数

        返回：
            总 token 数，如果 token_usage 中没有 total_tokens 字段则返回 0
        """
        return self.token_usage.get("total_tokens", 0)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于序列化）

        返回：
            包含所有字段的字典
        """
        return {
            "turn_id": self.turn_id,
            "role": self.role.value,
            "content": self.content,
            "tool_refs": self.tool_refs.copy(),
            "token_usage": self.token_usage.copy(),
            "timestamp": self.timestamp.isoformat(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ShortTermBuffer":
        """从字典重建 ShortTermBuffer（用于反序列化）

        参数：
            data: 包含 ShortTermBuffer 数据的字典

        返回：
            ShortTermBuffer 实例
        """
        # 解析时间戳
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        # 解析角色
        role_str = data.get("role", "user")
        try:
            role = TurnRole(role_str)
        except ValueError:
            role = TurnRole.USER

        return ShortTermBuffer(
            turn_id=data.get("turn_id", ""),
            role=role,
            content=data.get("content", ""),
            tool_refs=data.get("tool_refs", []),
            token_usage=data.get("token_usage", {}),
            timestamp=timestamp,
        )


def calculate_buffer_total_tokens(buffers: list[ShortTermBuffer]) -> int:
    """计算缓冲区列表的总 token 数

    参数：
        buffers: ShortTermBuffer 列表

    返回：
        总 token 数
    """
    return sum(buffer.get_total_tokens() for buffer in buffers)


def filter_buffers_by_role(buffers: list[ShortTermBuffer], role: TurnRole) -> list[ShortTermBuffer]:
    """按角色过滤缓冲区

    参数：
        buffers: ShortTermBuffer 列表
        role: 要过滤的角色

    返回：
        过滤后的 ShortTermBuffer 列表
    """
    return [buffer for buffer in buffers if buffer.role == role]


def get_latest_buffers(buffers: list[ShortTermBuffer], n: int) -> list[ShortTermBuffer]:
    """获取最新的 N 个缓冲区

    参数：
        buffers: ShortTermBuffer 列表
        n: 要获取的数量

    返回：
        最新的 N 个 ShortTermBuffer
    """
    return buffers[-n:] if len(buffers) >= n else buffers
