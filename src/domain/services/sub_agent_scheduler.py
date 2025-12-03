"""子Agent调度器 (Sub-Agent Scheduler) - 阶段3核心模块

业务定义：
- 定义子Agent接口（搜索、MCP、Python执行器等）
- 管理子Agent注册、实例化和生命周期
- 与现有工具体系整合

设计原则：
- 协议驱动：通过 SubAgentProtocol 定义统一接口
- 注册表模式：SubAgentRegistry 管理所有子Agent类型
- 基类模板：BaseSubAgent 提供通用实现

子Agent类型：
- SEARCH: 搜索Agent（网页、文档）
- MCP: MCP协议Agent
- PYTHON_EXECUTOR: Python代码执行Agent
- DATA_PROCESSOR: 数据处理Agent
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4

# ==================== 枚举定义 ====================


class SubAgentType(str, Enum):
    """子Agent类型枚举

    定义系统支持的子Agent类型：
    - SEARCH: 搜索Agent（网页、文档搜索）
    - MCP: MCP协议Agent（与外部MCP服务交互）
    - PYTHON_EXECUTOR: Python代码执行Agent
    - DATA_PROCESSOR: 数据处理Agent
    """

    SEARCH = "search"
    MCP = "mcp"
    PYTHON_EXECUTOR = "python_executor"
    DATA_PROCESSOR = "data_processor"


class SubAgentStatus(str, Enum):
    """子Agent状态枚举

    跟踪子Agent生命周期状态：
    - CREATED: 已创建，等待执行
    - RUNNING: 正在执行
    - COMPLETED: 执行完成
    - FAILED: 执行失败
    - CANCELLED: 被取消
    """

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==================== 数据结构 ====================


@dataclass
class SubAgentResult:
    """子Agent执行结果

    属性：
    - agent_id: Agent实例ID
    - agent_type: Agent类型
    - success: 是否成功
    - output: 输出数据
    - error: 错误信息（失败时）
    - execution_time: 执行时间（秒）
    - started_at: 开始时间
    - completed_at: 完成时间
    """

    agent_id: str
    agent_type: str
    success: bool = True
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time: float = 0.0
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "execution_time": self.execution_time,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class SubAgentTask:
    """子Agent任务定义

    属性：
    - task_id: 任务ID
    - agent_type: 目标Agent类型
    - payload: 任务负载数据
    - priority: 优先级（数字越小优先级越高）
    - timeout: 超时时间（秒）
    - created_at: 创建时间
    - parent_workflow_id: 父工作流ID（可选）
    """

    task_id: str
    agent_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timeout: float = 60.0
    created_at: datetime = field(default_factory=datetime.now)
    parent_workflow_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "payload": self.payload,
            "priority": self.priority,
            "timeout": self.timeout,
            "created_at": self.created_at.isoformat(),
            "parent_workflow_id": self.parent_workflow_id,
        }


# ==================== 协议定义 ====================


class SubAgentProtocol(Protocol):
    """子Agent协议接口

    定义所有子Agent必须实现的方法。

    方法：
    - execute: 执行任务
    - get_capabilities: 获取能力描述
    - get_status: 获取当前状态
    """

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> SubAgentResult:
        """执行任务

        参数：
            task: 任务数据
            context: 执行上下文

        返回：
            SubAgentResult 执行结果
        """
        ...

    def get_capabilities(self) -> dict[str, Any]:
        """获取Agent能力描述

        返回：
            能力描述字典
        """
        ...

    def get_status(self) -> SubAgentStatus:
        """获取当前状态

        返回：
            SubAgentStatus 状态枚举
        """
        ...


# ==================== 基类实现 ====================


class BaseSubAgent(ABC):
    """子Agent基类

    提供通用实现：
    - 自动生成ID
    - 状态跟踪
    - 执行时间计算
    - 错误处理

    子类需要实现：
    - agent_type 属性
    - _execute_internal 方法
    - get_capabilities 方法
    """

    def __init__(self, agent_id: str | None = None, config: dict[str, Any] | None = None):
        """初始化子Agent

        参数：
            agent_id: Agent实例ID（可选，自动生成）
            config: 配置字典（可选）
        """
        self.agent_id = agent_id or f"subagent_{uuid4().hex[:12]}"
        self.config = config or {}
        self._status = SubAgentStatus.CREATED
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None

    @property
    @abstractmethod
    def agent_type(self) -> SubAgentType:
        """获取Agent类型"""
        ...

    @abstractmethod
    async def _execute_internal(
        self, task: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """内部执行逻辑

        子类实现此方法执行具体任务。

        参数：
            task: 任务数据
            context: 执行上下文

        返回：
            输出数据字典

        异常：
            可以抛出异常，由基类处理
        """
        ...

    @abstractmethod
    def get_capabilities(self) -> dict[str, Any]:
        """获取Agent能力描述"""
        ...

    def get_status(self) -> SubAgentStatus:
        """获取当前状态"""
        return self._status

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> SubAgentResult:
        """执行任务

        封装执行逻辑，处理状态更新和错误捕获。

        参数：
            task: 任务数据
            context: 执行上下文

        返回：
            SubAgentResult 执行结果
        """
        self._status = SubAgentStatus.RUNNING
        self._started_at = datetime.now()
        start_time = time.time()

        try:
            output = await self._execute_internal(task, context)

            self._status = SubAgentStatus.COMPLETED
            self._completed_at = datetime.now()
            execution_time = time.time() - start_time

            return SubAgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=True,
                output=output,
                execution_time=execution_time,
                started_at=self._started_at,
                completed_at=self._completed_at,
            )

        except Exception as e:
            self._status = SubAgentStatus.FAILED
            self._completed_at = datetime.now()
            execution_time = time.time() - start_time

            return SubAgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type.value,
                success=False,
                output={},
                error=str(e),
                execution_time=execution_time,
                started_at=self._started_at,
                completed_at=self._completed_at,
            )

    def cancel(self) -> None:
        """取消执行"""
        if self._status == SubAgentStatus.RUNNING:
            self._status = SubAgentStatus.CANCELLED
            self._completed_at = datetime.now()


# ==================== 注册表 ====================


class SubAgentRegistry:
    """子Agent注册表

    管理所有子Agent类型的注册和实例化。

    使用示例：
        registry = SubAgentRegistry()
        registry.register(SubAgentType.SEARCH, SearchSubAgent)
        agent = registry.create_instance(SubAgentType.SEARCH, config={...})
    """

    def __init__(self):
        """初始化注册表"""
        self._registry: dict[SubAgentType, type] = {}

    def register(self, agent_type: SubAgentType, agent_class: type) -> None:
        """注册Agent类

        参数：
            agent_type: Agent类型
            agent_class: Agent类
        """
        self._registry[agent_type] = agent_class

    def unregister(self, agent_type: SubAgentType) -> bool:
        """取消注册Agent类

        参数：
            agent_type: Agent类型

        返回：
            是否成功取消
        """
        if agent_type in self._registry:
            del self._registry[agent_type]
            return True
        return False

    def has(self, agent_type: SubAgentType) -> bool:
        """检查是否已注册

        参数：
            agent_type: Agent类型

        返回：
            是否已注册
        """
        return agent_type in self._registry

    def get(self, agent_type: SubAgentType) -> type | None:
        """获取Agent类

        参数：
            agent_type: Agent类型

        返回：
            Agent类，未注册返回None
        """
        return self._registry.get(agent_type)

    def list_types(self) -> list[SubAgentType]:
        """列出所有已注册类型

        返回：
            已注册的Agent类型列表
        """
        return list(self._registry.keys())

    def create_instance(
        self,
        agent_type: SubAgentType,
        agent_id: str | None = None,
        config: dict[str, Any] | None = None,
        **kwargs,
    ) -> Any | None:
        """创建Agent实例

        参数：
            agent_type: Agent类型
            agent_id: 实例ID（可选）
            config: 配置字典（可选）
            **kwargs: 其他构造参数

        返回：
            Agent实例，未注册返回None
        """
        agent_class = self.get(agent_type)
        if agent_class is None:
            return None

        # 尝试不同的构造方式，按优先级尝试
        # 1. 完整参数（BaseSubAgent子类）
        try:
            return agent_class(agent_id=agent_id, config=config, **kwargs)
        except TypeError:
            pass

        # 2. 仅config参数（简单Agent）
        try:
            return agent_class(config=config, **kwargs)
        except TypeError:
            pass

        # 3. 仅agent_id参数
        try:
            return agent_class(agent_id=agent_id, **kwargs)
        except TypeError:
            pass

        # 4. 仅kwargs
        try:
            return agent_class(**kwargs)
        except TypeError:
            return None


# 导出
__all__ = [
    "SubAgentType",
    "SubAgentStatus",
    "SubAgentResult",
    "SubAgentTask",
    "SubAgentProtocol",
    "BaseSubAgent",
    "SubAgentRegistry",
]
