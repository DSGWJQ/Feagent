"""保存请求通道 (Save Request Channel)

提供标准化的保存请求机制，支持：
1. SaveRequest 事件定义
2. 操作类型和优先级枚举
3. 请求验证
4. 队列管理
5. 意图检测

设计原则：
- ConversationAgent 仅生成保存请求，不直接写文件
- Coordinator 负责接收、排队和审核保存请求
- 所有持久化操作需经过审核通道

创建日期：2025-12-07
"""

import heapq
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from src.domain.services.event_bus import Event


# =============================================================================
# 异常定义
# =============================================================================


class SaveRequestValidationError(Exception):
    """保存请求验证错误"""

    pass


class SaveRequestQueueFullError(Exception):
    """保存请求队列已满错误"""

    pass


# =============================================================================
# 枚举定义
# =============================================================================


class SaveRequestType(str, Enum):
    """保存请求操作类型

    定义允许的持久化操作类型。
    """

    FILE_WRITE = "file_write"  # 文件写入（覆盖）
    FILE_APPEND = "file_append"  # 文件追加
    FILE_DELETE = "file_delete"  # 文件删除
    CONFIG_UPDATE = "config_update"  # 配置更新


class SaveRequestPriority(str, Enum):
    """保存请求优先级

    定义请求处理的优先级顺序。
    CRITICAL > HIGH > NORMAL > LOW
    """

    LOW = "low"  # 低优先级
    NORMAL = "normal"  # 普通优先级（默认）
    HIGH = "high"  # 高优先级
    CRITICAL = "critical"  # 关键优先级

    @staticmethod
    def get_priority_order(priority: "SaveRequestPriority") -> int:
        """获取优先级数值（用于排序）

        数值越大优先级越高。

        参数：
            priority: 优先级枚举值

        返回：
            优先级数值
        """
        order_map = {
            SaveRequestPriority.LOW: 0,
            SaveRequestPriority.NORMAL: 1,
            SaveRequestPriority.HIGH: 2,
            SaveRequestPriority.CRITICAL: 3,
        }
        return order_map.get(priority, 1)


class SaveRequestStatus(str, Enum):
    """保存请求状态

    跟踪请求的处理状态。
    """

    PENDING = "pending"  # 待处理
    QUEUED = "queued"  # 已入队
    VALIDATING = "validating"  # 验证中
    APPROVED = "approved"  # 已批准
    REJECTED = "rejected"  # 已拒绝
    EXECUTING = "executing"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败


# =============================================================================
# 数据结构定义
# =============================================================================


@dataclass
class SaveRequest(Event):
    """保存请求事件

    当 Agent 需要进行持久化操作时，发布此事件。
    Coordinator 订阅此事件进行排队和审核。

    属性：
        request_id: 请求唯一标识
        target_path: 目标路径
        content: 保存内容（字符串或字节）
        operation_type: 操作类型
        session_id: 来源会话 ID
        reason: 保存原因说明
        priority: 优先级
        source_agent: 来源 Agent 类型
        is_binary: 是否为二进制内容
        timestamp: 请求时间戳
        has_warning: 是否有警告
        warnings: 警告列表
    """

    target_path: str = ""
    content: str | bytes = ""
    operation_type: SaveRequestType = SaveRequestType.FILE_WRITE
    session_id: str = ""
    reason: str = ""
    priority: SaveRequestPriority = SaveRequestPriority.NORMAL
    source_agent: str = "ConversationAgent"
    is_binary: bool = False
    request_id: str = field(default_factory=lambda: f"save-{uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.now)
    has_warning: bool = False
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        """初始化后验证"""
        # 验证必填字段
        if not self.target_path:
            raise SaveRequestValidationError(
                "target_path is required and cannot be empty"
            )

        if not self.session_id:
            raise SaveRequestValidationError(
                "session_id is required and cannot be empty"
            )

        # 检查写操作的空内容警告
        if (
            self.operation_type in (SaveRequestType.FILE_WRITE, SaveRequestType.FILE_APPEND)
            and not self.content
        ):
            self.has_warning = True
            self.warnings.append("Empty content for write operation")

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "save_request"

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典

        返回：
            字典表示
        """
        content = self.content
        if isinstance(content, bytes):
            content = content.hex()  # 二进制转十六进制字符串

        return {
            "request_id": self.request_id,
            "target_path": self.target_path,
            "content": content,
            "operation_type": self.operation_type.value,
            "session_id": self.session_id,
            "reason": self.reason,
            "priority": self.priority.value,
            "source_agent": self.source_agent,
            "is_binary": self.is_binary,
            "timestamp": self.timestamp.isoformat(),
            "has_warning": self.has_warning,
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SaveRequest":
        """从字典反序列化

        参数：
            data: 字典数据

        返回：
            SaveRequest 实例
        """
        content = data.get("content", "")
        is_binary = data.get("is_binary", False)

        if is_binary and isinstance(content, str):
            content = bytes.fromhex(content)

        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            request_id=data.get("request_id", f"save-{uuid4().hex[:12]}"),
            target_path=data.get("target_path", ""),
            content=content,
            operation_type=SaveRequestType(data.get("operation_type", "file_write")),
            session_id=data.get("session_id", ""),
            reason=data.get("reason", ""),
            priority=SaveRequestPriority(data.get("priority", "normal")),
            source_agent=data.get("source_agent", "ConversationAgent"),
            is_binary=is_binary,
            timestamp=timestamp or datetime.now(),
            has_warning=data.get("has_warning", False),
            warnings=data.get("warnings", []),
        )


@dataclass
class SaveRequestReceivedEvent(Event):
    """保存请求已接收事件

    当 Coordinator 成功接收 SaveRequest 时发布。

    属性：
        request_id: 原请求 ID
        queued_at: 入队时间
        queue_position: 队列位置
    """

    request_id: str = ""
    queued_at: datetime = field(default_factory=datetime.now)
    queue_position: int = 0

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "save_request_received"


@dataclass
class SaveIntentResult:
    """保存意图检测结果

    属性：
        has_save_intent: 是否有保存意图
        suggested_path: 建议的保存路径
        confidence: 置信度
    """

    has_save_intent: bool = False
    suggested_path: str | None = None
    confidence: float = 0.0


# =============================================================================
# 意图检测器
# =============================================================================


class SaveIntentDetector:
    """保存意图检测器

    从用户输入中检测保存意图。
    """

    # 保存相关的关键词模式
    SAVE_PATTERNS = [
        r"保存到\s*(.+)",
        r"写入\s*(.+)",
        r"存储到\s*(.+)",
        r"导出到\s*(.+)",
        r"输出到\s*(.+)",
        r"save\s+to\s+(.+)",
        r"write\s+to\s+(.+)",
        r"export\s+to\s+(.+)",
    ]

    # 简单匹配的关键词
    SAVE_KEYWORDS = [
        "保存到文件",
        "写入文件",
        "存储到",
        "save to",
        "write to file",
        "导出到",
        "输出到文件",
    ]

    def __init__(self):
        """初始化检测器"""
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.SAVE_PATTERNS
        ]

    def detect(self, user_input: str) -> SaveIntentResult:
        """检测用户输入中的保存意图

        参数：
            user_input: 用户输入文本

        返回：
            SaveIntentResult 检测结果
        """
        if not user_input:
            return SaveIntentResult(has_save_intent=False)

        # 先检查关键词
        input_lower = user_input.lower()
        for keyword in self.SAVE_KEYWORDS:
            if keyword.lower() in input_lower:
                # 尝试提取路径
                path = self._extract_path(user_input)
                return SaveIntentResult(
                    has_save_intent=True,
                    suggested_path=path,
                    confidence=0.8 if path else 0.6,
                )

        # 使用正则表达式匹配
        for pattern in self._compiled_patterns:
            match = pattern.search(user_input)
            if match:
                path = match.group(1).strip() if match.groups() else None
                return SaveIntentResult(
                    has_save_intent=True,
                    suggested_path=path,
                    confidence=0.9,
                )

        return SaveIntentResult(has_save_intent=False)

    def _extract_path(self, text: str) -> str | None:
        """从文本中提取文件路径

        参数：
            text: 输入文本

        返回：
            提取的路径或 None
        """
        # 匹配常见路径模式
        path_patterns = [
            r"(/[\w./\-]+)",  # Unix 路径
            r"([A-Za-z]:[\\\/][\w.\\\/\-]+)",  # Windows 路径
            r"([\w./\-]+\.\w+)",  # 相对路径带扩展名
        ]

        for pattern in path_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return None


# =============================================================================
# 队列管理器
# =============================================================================


class SaveRequestQueueManager:
    """保存请求队列管理器

    管理待处理的保存请求，支持优先级排序。
    """

    def __init__(self, max_size: int = 1000):
        """初始化队列管理器

        参数：
            max_size: 队列最大容量
        """
        self._max_size = max_size
        self._queue: list[tuple[int, int, SaveRequest]] = []  # (priority, counter, request)
        self._counter = 0  # 用于保持 FIFO 顺序
        self._lock = threading.RLock()
        self._requests_by_id: dict[str, SaveRequest] = {}
        self._status_by_id: dict[str, SaveRequestStatus] = {}

    def queue_size(self) -> int:
        """获取队列大小

        返回：
            当前队列中的请求数量
        """
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """检查队列是否为空

        返回：
            True 如果队列为空
        """
        with self._lock:
            return len(self._queue) == 0

    def enqueue(self, request: SaveRequest) -> int:
        """将请求入队

        参数：
            request: 保存请求

        返回：
            队列位置

        异常：
            SaveRequestQueueFullError: 队列已满
        """
        with self._lock:
            if len(self._queue) >= self._max_size:
                raise SaveRequestQueueFullError(
                    f"Queue is full (max_size={self._max_size})"
                )

            # 优先级取负数，因为 heapq 是最小堆
            priority = -SaveRequestPriority.get_priority_order(request.priority)
            self._counter += 1

            heapq.heappush(self._queue, (priority, self._counter, request))
            self._requests_by_id[request.request_id] = request
            self._status_by_id[request.request_id] = SaveRequestStatus.QUEUED

            return len(self._queue)

    def dequeue(self) -> SaveRequest | None:
        """从队列中取出最高优先级的请求

        返回：
            SaveRequest 或 None（如果队列为空）
        """
        with self._lock:
            if not self._queue:
                return None

            _, _, request = heapq.heappop(self._queue)
            self._status_by_id[request.request_id] = SaveRequestStatus.VALIDATING
            return request

    def peek(self) -> SaveRequest | None:
        """查看队首请求但不移除

        返回：
            SaveRequest 或 None（如果队列为空）
        """
        with self._lock:
            if not self._queue:
                return None
            return self._queue[0][2]

    def get_by_session(self, session_id: str) -> list[SaveRequest]:
        """获取特定会话的所有请求

        参数：
            session_id: 会话 ID

        返回：
            该会话的请求列表
        """
        with self._lock:
            return [
                item[2] for item in self._queue
                if item[2].session_id == session_id
            ]

    def get_status(self, request_id: str) -> SaveRequestStatus | None:
        """获取请求状态

        参数：
            request_id: 请求 ID

        返回：
            请求状态或 None
        """
        with self._lock:
            return self._status_by_id.get(request_id)

    def update_status(self, request_id: str, status: SaveRequestStatus) -> None:
        """更新请求状态

        参数：
            request_id: 请求 ID
            status: 新状态
        """
        with self._lock:
            if request_id in self._status_by_id:
                self._status_by_id[request_id] = status

    def get_all_sorted(self) -> list[SaveRequest]:
        """获取所有请求（按优先级排序）

        返回：
            排序后的请求列表
        """
        with self._lock:
            # 复制并排序
            sorted_queue = sorted(self._queue, key=lambda x: (x[0], x[1]))
            return [item[2] for item in sorted_queue]

    def remove(self, request_id: str) -> bool:
        """从队列中移除请求

        参数：
            request_id: 请求 ID

        返回：
            True 如果成功移除
        """
        with self._lock:
            for i, (_, _, request) in enumerate(self._queue):
                if request.request_id == request_id:
                    del self._queue[i]
                    heapq.heapify(self._queue)
                    del self._requests_by_id[request_id]
                    del self._status_by_id[request_id]
                    return True
            return False
