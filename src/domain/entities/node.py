"""Node 实体 - 工作流中的执行单元

业务定义：
- Node 是工作流中的单个执行步骤
- 每个 Node 有类型、名称、配置、位置等属性
- Node 可以是 HTTP 请求、数据转换、数据库操作等

设计原则：
- 纯 Python 实现，不依赖任何框架（DDD 要求）
- 使用 dataclass 简化样板代码
- 通过工厂方法 create() 封装创建逻辑
"""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.domain.exceptions import DomainError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


@dataclass
class Node:
    """Node 实体

    属性说明：
    - id: 唯一标识符（node_ 前缀）
    - type: 节点类型（HTTP、Transform、Database 等）
    - name: 节点名称（用户可见）
    - config: 节点配置（JSON 格式，不同类型的节点配置不同）
    - position: 节点在画布上的位置

    为什么使用 dataclass？
    1. 自动生成 __init__、__repr__、__eq__ 等方法
    2. 类型注解清晰，IDE 友好
    3. 符合 Python 3.11+ 最佳实践
    4. 纯 Python，不依赖框架（符合 DDD 要求）
    """

    id: str
    type: NodeType
    name: str
    config: dict[str, Any]
    position: Position

    @classmethod
    def create(
        cls,
        type: NodeType,
        name: str,
        config: dict[str, Any],
        position: Position,
    ) -> "Node":
        """创建 Node 的工厂方法

        为什么使用工厂方法？
        1. 封装创建逻辑：自动生成 ID
        2. 验证业务规则：确保 name 不为空
        3. 符合 DDD 实体创建模式

        参数：
            type: 节点类型
            name: 节点名称（必需）
            config: 节点配置
            position: 节点位置

        返回：
            Node 实例

        抛出：
            DomainError: 当 name 为空时
        """
        # 验证业务规则
        if not name or not name.strip():
            raise DomainError("name 不能为空")

        return cls(
            id=f"node_{uuid4().hex[:8]}",
            type=type,
            name=name.strip(),
            config=config,
            position=position,
        )

    def update_position(self, position: Position) -> None:
        """更新节点位置

        用于拖拽调整工作流时更新节点位置

        参数：
            position: 新的位置
        """
        self.position = position

    def update_config(self, config: dict[str, Any]) -> None:
        """更新节点配置

        用于编辑节点属性时更新配置

        参数：
            config: 新的配置
        """
        self.config = config
