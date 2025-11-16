"""Agent 实体 - 系统的核心聚合根

业务定义：
- Agent 是用户通过"起点 + 目的"创建的智能代理
- 是整个系统的核心业务概念
- 负责维护自身的业务规则和不变式

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- 使用 dataclass 简化样板代码
- 通过工厂方法 create() 封装创建逻辑
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from src.domain.exceptions import DomainError


@dataclass
class Agent:
    """Agent 实体

    属性说明：
    - id: 唯一标识符（UUID）
    - start: 任务起点描述（业务必需）
    - goal: 任务目的描述（业务必需）
    - status: Agent 状态（active/archived）
    - name: Agent 名称（用户可见）
    - created_at: 创建时间（审计需要）

    为什么使用 dataclass？
    1. 自动生成 __init__、__repr__、__eq__ 等方法
    2. 类型注解清晰，IDE 友好
    3. 符合 Python 3.11+ 最佳实践
    4. 纯 Python，不依赖框架（符合 DDD 要求）
    """

    id: str
    start: str
    goal: str
    status: str
    name: str
    created_at: datetime

    @classmethod
    def create(cls, start: str, goal: str, name: str | None = None) -> "Agent":
        """创建 Agent 的工厂方法

        为什么使用工厂方法而不是直接 __init__？
        1. 封装创建逻辑：自动生成 id、status、created_at
        2. 提供默认值：name 可以自动生成
        3. 符合 DDD 聚合根创建模式
        4. 验证业务规则：确保 start 和 goal 不为空

        参数：
            start: 任务起点描述（例如："我有一个 CSV 文件"）
            goal: 任务目的描述（例如："分析销售数据并生成报告"）
            name: Agent 名称（可选，不提供则自动生成）

        返回：
            Agent 实例

        抛出：
            DomainError: 当 start 或 goal 为空时

        实现说明：
        - 验证：先验证业务规则，再创建实例（Fail Fast 原则）
        - id: 使用 UUID 保证全局唯一性
        - status: 默认为 "active"（新创建的 Agent 都是激活状态）
        - name: 如果未提供，自动生成格式为 "Agent-YYYYMMDD-HHMMSS"
        - created_at: 记录创建时间（用于审计和排序）
        """
        # 验证业务规则（不变式）
        # 为什么先验证？Fail Fast 原则：尽早发现错误，避免创建无效对象

        # 验证 start 不能为空
        # 为什么用 strip()？防止用户输入纯空格绕过验证
        if not start or not start.strip():
            raise DomainError("start 不能为空")

        # 验证 goal 不能为空
        if not goal or not goal.strip():
            raise DomainError("goal 不能为空")

        # 验证通过，创建实例
        return cls(
            id=str(uuid4()),  # UUID 转字符串，方便序列化
            start=start.strip(),  # 去除首尾空格，规范化数据
            goal=goal.strip(),  # 去除首尾空格，规范化数据
            status="active",  # 新创建的 Agent 默认激活
            name=name or f"Agent-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            created_at=datetime.now(),
        )
