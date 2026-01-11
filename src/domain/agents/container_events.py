"""容器执行事件 (Container Events) - Phase 4

业务定义：
- 定义容器执行生命周期的事件
- 支持容器执行开始、完成、日志等事件
- 用于 Coordinator 监控和记录容器执行

设计原则：
- 事件驱动：通过事件通知执行状态
- 可追踪：包含完整的执行信息
- 可扩展：支持自定义日志级别和元数据
"""

from dataclasses import dataclass, field
from typing import Any

from src.domain.services.event_bus import Event


@dataclass
class ContainerExecutionStartedEvent(Event):
    """容器执行开始事件

    当容器开始执行代码时发布此事件。

    属性：
        container_id: 容器实例ID
        node_id: 节点ID
        workflow_id: 工作流ID
        image: Docker 镜像名称
        code_preview: 代码预览（前100字符）
    """

    container_id: str = ""
    node_id: str = ""
    workflow_id: str = ""
    image: str = ""
    code_preview: str = ""

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "container_execution_started"


@dataclass
class ContainerExecutionCompletedEvent(Event):
    """容器执行完成事件

    当容器执行完成（成功或失败）时发布此事件。

    属性：
        container_id: 容器实例ID
        node_id: 节点ID
        workflow_id: 工作流ID
        success: 是否执行成功
        exit_code: 退出码
        stdout: 标准输出
        stderr: 标准错误
        execution_time: 执行时间（秒）
        output_data: 输出数据
    """

    container_id: str = ""
    node_id: str = ""
    workflow_id: str = ""
    success: bool = False
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0
    output_data: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "container_execution_completed"


@dataclass
class ContainerLogEvent(Event):
    """容器日志事件

    当容器产生日志时发布此事件。

    属性：
        container_id: 容器实例ID
        node_id: 节点ID
        log_level: 日志级别 (INFO, WARNING, ERROR, DEBUG)
        message: 日志消息
        timestamp: 时间戳
        metadata: 额外元数据
    """

    container_id: str = ""
    node_id: str = ""
    log_level: str = "INFO"
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """事件类型"""
        return "container_log"


# 导出
__all__ = [
    "ContainerExecutionStartedEvent",
    "ContainerExecutionCompletedEvent",
    "ContainerLogEvent",
]
