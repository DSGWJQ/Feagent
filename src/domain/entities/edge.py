"""Edge 实体 - 工作流中节点之间的连接

业务定义：
- Edge 表示工作流中节点之间的连接
- 定义了数据流向和执行顺序
- 可以包含条件表达式（用于条件分支）

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- 使用 dataclass 简化样板代码
- 通过工厂方法 create() 封装创建逻辑
"""

from dataclasses import dataclass
from uuid import uuid4

from src.domain.exceptions import DomainError


@dataclass
class Edge:
    """Edge 实体

    属性说明：
    - id: 唯一标识符（edge_ 前缀）
    - source_node_id: 源节点 ID
    - target_node_id: 目标节点 ID
    - condition: 条件表达式（可选，用于条件分支）

    为什么使用 dataclass？
    1. 自动生成 __init__、__repr__、__eq__ 等方法
    2. 类型注解清晰，IDE 友好
    3. 符合 Python 3.11+ 最佳实践
    4. 纯 Python，不依赖框架（符合 DDD 要求）
    """

    id: str
    source_node_id: str
    target_node_id: str
    condition: str | None = None

    @classmethod
    def create(
        cls,
        source_node_id: str,
        target_node_id: str,
        condition: str | None = None,
    ) -> "Edge":
        """创建 Edge 的工厂方法

        为什么使用工厂方法？
        1. 封装创建逻辑：自动生成 ID
        2. 验证业务规则：确保节点 ID 不为空，不能连接到自己
        3. 符合 DDD 实体创建模式

        参数：
            source_node_id: 源节点 ID（必需）
            target_node_id: 目标节点 ID（必需）
            condition: 条件表达式（可选）

        返回：
            Edge 实例

        抛出：
            DomainError: 当节点 ID 为空或相同时
        """
        # 验证业务规则
        if not source_node_id or not source_node_id.strip():
            raise DomainError("source_node_id 不能为空")

        if not target_node_id or not target_node_id.strip():
            raise DomainError("target_node_id 不能为空")

        if source_node_id.strip() == target_node_id.strip():
            raise DomainError("不能连接到自己")

        return cls(
            id=f"edge_{uuid4().hex[:8]}",
            source_node_id=source_node_id.strip(),
            target_node_id=target_node_id.strip(),
            condition=condition.strip() if condition and condition.strip() else None,
        )
