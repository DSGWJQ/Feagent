"""TaskEvent 值对象 - Task 执行事件

业务定义：
- TaskEvent 记录 Task 执行过程中的关键事件
- 用于审计、调试、监控
- 事件是不可变的（创建后不修改）

第一性原理：
1. 什么是值对象？
   - 没有唯一标识（ID）
   - 由属性值决定相等性
   - 不可变（Immutable）
   - 可以被替换（Replaceable）

2. TaskEvent 为什么是值对象？
   - TaskEvent 没有独立的业务意义，必须属于某个 Task
   - TaskEvent 的相等性由 timestamp + message 决定
   - TaskEvent 创建后不应该被修改（审计需求）
   - TaskEvent 可以被复制和替换

3. TaskEvent 与 Task 的关系：
   - 聚合关系：Task 是聚合根，TaskEvent 是聚合内的值对象
   - 生命周期：TaskEvent 的生命周期完全由 Task 管理
   - 访问控制：外部只能通过 Task.add_event() 来创建 TaskEvent

设计原则：
- 使用 @dataclass(frozen=True) 确保不可变性
- 不提供 setter 方法
- 所有属性都是只读的
- 通过工厂方法 create() 封装创建逻辑
"""

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class TaskEvent:
    """TaskEvent 值对象

    属性说明：
    - timestamp: 事件发生时间（UTC）
    - message: 事件消息（描述发生了什么）

    为什么使用 @dataclass(frozen=True)？
    1. frozen=True 使对象不可变（符合值对象定义）
    2. 自动生成 __init__、__repr__、__eq__、__hash__ 方法
    3. 类型注解清晰，IDE 友好
    4. 纯 Python，不依赖框架（符合 DDD 要求）

    为什么不可变？
    1. 审计需求：事件记录不应该被篡改
    2. 线程安全：不可变对象天然线程安全
    3. 可哈希：可以作为字典的 key 或放入 set
    4. 简化推理：不用担心对象状态被意外修改

    示例：
    >>> event = TaskEvent.create("开始下载文件")
    >>> event.timestamp  # datetime(2024, 1, 1, 12, 0, 0)
    >>> event.message    # "开始下载文件"
    >>> event.message = "修改消息"  # ❌ 抛出 FrozenInstanceError
    """

    timestamp: datetime
    message: str

    @classmethod
    def create(cls, message: str) -> "TaskEvent":
        """创建 TaskEvent（工厂方法）

        为什么使用工厂方法而不是直接 __init__？
        1. 封装创建逻辑：自动设置 timestamp
        2. 业务语义清晰：create() 比 __init__() 更符合业务语言
        3. 验证逻辑集中：在一个地方验证所有业务规则
        4. 易于测试：可以 mock 工厂方法

        参数：
            message: 事件消息（必填）

        返回：
            TaskEvent 实例

        异常：
            ValueError: message 为空或纯空格

        示例：
        >>> event = TaskEvent.create("开始下载文件")
        >>> event.message
        '开始下载文件'
        """
        # 验证：message 不能为空
        if not message or not message.strip():
            raise ValueError("事件消息不能为空")

        # 自动设置时间戳（UTC）
        timestamp = datetime.now(UTC)

        # 去除首尾空格
        message = message.strip()

        return cls(timestamp=timestamp, message=message)

    def __str__(self) -> str:
        """字符串表示（用于日志）

        为什么重写 __str__？
        1. 日志友好：方便打印和调试
        2. 可读性：比默认的 repr 更易读

        示例：
        >>> event = TaskEvent.create("开始下载文件")
        >>> str(event)
        '[2024-01-01 12:00:00] 开始下载文件'
        """
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.message}"
