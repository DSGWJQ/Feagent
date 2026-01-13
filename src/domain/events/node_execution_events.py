"""节点执行事件 (Node Execution Events)

Domain 层事件定义，用于节点执行生命周期的可观测性和事件驱动通信。

设计原则：
- 继承 Event 基类（符合 EventBus 契约）
- 携带完整的节点执行上下文（node_id, node_type, node_name, run_id）
- 用于 Application 层订阅并记录执行轨迹
- 支持分布式追踪（correlation_id）

继承字段说明（来自 Event 基类）：
- id: 事件唯一标识符（UUID）
- timestamp: 事件创建时间
- source: 事件来源（发布者标识）
- correlation_id: 关联ID，用于追踪事件因果关系
"""

from dataclasses import dataclass, field
from typing import Any

from src.domain.services.event_bus import Event


@dataclass
class NodeExecutionStartedEvent(Event):
    """节点开始执行事件

    在节点开始执行前发布，标记节点进入运行态。

    属性：
        node_id: 节点唯一标识符
        node_type: 节点类型（如 'http', 'database', 'transform' 等）
        node_name: 节点显示名称
        inputs: 节点输入参数字典
        run_id: 关联的工作流运行ID，用于追踪执行链路
    """

    node_id: str = ""
    node_type: str = ""
    node_name: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None


@dataclass
class NodeExecutionCompletedEvent(Event):
    """节点执行完成事件

    在节点成功完成执行后发布，标记节点进入完成态。

    属性：
        node_id: 节点唯一标识符
        node_type: 节点类型
        node_name: 节点显示名称
        output: 节点输出结果（任意类型）
        duration_ms: 执行耗时（毫秒）
        run_id: 关联的工作流运行ID
    """

    node_id: str = ""
    node_type: str = ""
    node_name: str = ""
    output: Any = None
    duration_ms: float = 0.0
    run_id: str | None = None


@dataclass
class NodeExecutionFailedEvent(Event):
    """节点执行失败事件

    在节点执行失败后发布，标记节点进入失败态。

    属性：
        node_id: 节点唯一标识符
        node_type: 节点类型
        node_name: 节点显示名称
        error: 错误信息描述
        error_type: 错误类型（如 'TimeoutError', 'ValidationError' 等）
        run_id: 关联的工作流运行ID
    """

    node_id: str = ""
    node_type: str = ""
    node_name: str = ""
    error: str = ""
    error_type: str = ""
    run_id: str | None = None


__all__ = [
    "NodeExecutionStartedEvent",
    "NodeExecutionCompletedEvent",
    "NodeExecutionFailedEvent",
]
