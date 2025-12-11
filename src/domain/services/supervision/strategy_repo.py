"""Phase 34.14: StrategyRepository extracted from supervision_modules."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any


class StrategyRepository:
    """策略库

    管理监督策略的注册、查询和执行。
    """

    def __init__(self) -> None:
        """初始化策略库"""
        self.strategies: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        trigger_conditions: list[str],
        action: str,
        priority: int = 10,
        action_params: dict[str, Any] | None = None,
    ) -> str:
        """注册策略

        参数：
            name: 策略名称
            trigger_conditions: 触发条件列表
            action: 动作 (warn/block/terminate/log)
            priority: 优先级（数字越小优先级越高）
            action_params: 动作参数

        返回：
            策略ID
        """
        strategy_id = f"strategy_{uuid.uuid4().hex[:12]}"

        self.strategies[strategy_id] = {
            "id": strategy_id,
            "name": name,
            "trigger_conditions": trigger_conditions,
            "action": action,
            "priority": priority,
            "action_params": action_params or {},
            "enabled": True,
            "created_at": datetime.now().isoformat(),
        }

        return strategy_id

    def get(self, strategy_id: str) -> dict[str, Any] | None:
        """获取策略

        参数：
            strategy_id: 策略ID

        返回：
            策略字典
        """
        return self.strategies.get(strategy_id)

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有策略

        返回：
            策略列表
        """
        return list(self.strategies.values())

    def find_by_condition(self, condition: str) -> list[dict[str, Any]]:
        """按条件查找策略

        参数：
            condition: 触发条件

        返回：
            匹配的策略列表（按优先级排序）
        """
        matches = []

        for strategy in self.strategies.values():
            if not strategy["enabled"]:
                continue
            if condition in strategy["trigger_conditions"]:
                matches.append(strategy)

        # 按优先级排序
        matches.sort(key=lambda s: s["priority"])

        return matches

    def delete(self, strategy_id: str) -> bool:
        """删除策略

        参数：
            strategy_id: 策略ID

        返回：
            是否成功
        """
        if strategy_id not in self.strategies:
            return False
        del self.strategies[strategy_id]
        return True


__all__ = ["StrategyRepository"]
