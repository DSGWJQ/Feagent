"""SafetyGuard - 规则数据类

Phase 35.2: 从 CoordinatorAgent 迁移 Rule 数据类，避免循环依赖。
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Rule:
    """验证规则

    属性：
    - id: 规则唯一标识
    - name: 规则名称
    - description: 规则描述
    - condition: 条件函数，接收决策返回bool
    - priority: 优先级（数字越小优先级越高）
    - error_message: 验证失败时的错误信息
    - correction: 可选的修正函数
    """

    id: str
    name: str
    description: str = ""
    condition: Callable[[dict[str, Any]], bool] = field(default=lambda d: True)
    priority: int = 10
    error_message: str | Callable[[dict[str, Any]], str] = "验证失败"
    correction: Callable[[dict[str, Any]], dict[str, Any]] | None = None


__all__ = ["Rule"]
