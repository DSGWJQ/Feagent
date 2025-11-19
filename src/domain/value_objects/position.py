"""Position 值对象 - 节点在画布上的位置

业务定义：
- Position 表示节点在工作流画布上的坐标
- 用于前端拖拽编辑器的节点定位

设计原则：
- 值对象：不可变，通过值比较相等性
- 纯 Python 实现，不依赖任何框架
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """Position 值对象

    属性说明：
    - x: 横坐标（像素）
    - y: 纵坐标（像素）

    为什么使用 frozen=True？
    - 值对象应该是不可变的（Immutable）
    - 防止意外修改
    - 可以作为字典的 key

    示例：
    >>> pos1 = Position(x=100, y=200)
    >>> pos2 = Position(x=100, y=200)
    >>> pos1 == pos2
    True
    """

    x: float
    y: float

    def __post_init__(self) -> None:
        """验证坐标值

        业务规则：
        - x 和 y 可以是任意数值（包括负数，因为画布可以有负坐标）
        """
        # 移除非负数限制，允许负坐标
        pass
