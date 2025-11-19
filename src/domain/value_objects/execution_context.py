"""ExecutionContext - 执行上下文

职责：
1. 在 Task 之间传递数据
2. 存储前置任务结果
3. 管理共享变量
4. 提供上下文隔离（复制）

设计原则：
- 值对象：不可变性（通过复制实现隔离）
- 封装性：隐藏内部数据结构
- 类型安全：使用类型提示
- 易用性：提供简洁的 API

为什么需要 ExecutionContext？
- Task 之间需要传递数据（前置任务的结果）
- 需要共享变量（如 API Key、配置等）
- 需要上下文隔离（避免意外修改）
- 需要序列化/反序列化（持久化、传输）

使用场景：
1. ExecutionEngine 在执行 Run 时，维护一个 ExecutionContext
2. 每个 Task 执行完成后，将结果存储到 ExecutionContext
3. 后续 Task 可以从 ExecutionContext 获取前置任务的结果
4. 共享变量可以在所有 Task 之间共享（如 API Key）

示例：
    # 创建上下文
    context = ExecutionContext.create()

    # 存储任务结果
    context.set_task_result("Task 1", {"result": "data"})

    # 获取任务结果
    result = context.get_task_result("Task 1")

    # 设置共享变量
    context.set_variable("api_key", "secret-key")

    # 复制上下文（隔离）
    context2 = context.copy()
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class ExecutionContext:
    """执行上下文

    职责：
    1. 存储任务结果（Task 名称 -> 结果）
    2. 管理共享变量（变量名 -> 值）
    3. 提供上下文隔离（复制）
    4. 序列化/反序列化

    设计：
    - 使用两个字典分别存储任务结果和共享变量
    - 提供工厂方法 create() 创建实例
    - 提供 copy() 方法实现深拷贝
    - 提供 to_dict() / from_dict() 实现序列化
    """

    def __init__(self):
        """初始化执行上下文

        注意：不建议直接调用 __init__，请使用 create() 工厂方法
        """
        self._tasks: dict[str, Any] = {}  # 任务结果：Task 名称 -> 结果
        self._variables: dict[str, Any] = {}  # 共享变量：变量名 -> 值

    @classmethod
    def create(cls) -> ExecutionContext:
        """创建空的执行上下文（工厂方法）

        返回：
            ExecutionContext 实例
        """
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionContext:
        """从字典创建执行上下文

        参数：
            data: 字典数据，格式：
                {
                    "tasks": {"Task 1": {...}, "Task 2": {...}},
                    "variables": {"var1": "value1", "var2": "value2"}
                }

        返回：
            ExecutionContext 实例
        """
        context = cls()
        context._tasks = deepcopy(data.get("tasks", {}))
        context._variables = deepcopy(data.get("variables", {}))
        return context

    def set_task_result(self, task_name: str, result: Any) -> None:
        """存储任务结果

        参数：
            task_name: 任务名称
            result: 任务结果（任意类型）
        """
        self._tasks[task_name] = result

    def get_task_result(self, task_name: str, default: Any = None) -> Any:
        """获取任务结果

        参数：
            task_name: 任务名称
            default: 默认值（如果任务不存在）

        返回：
            任务结果，如果不存在则返回 default
        """
        return self._tasks.get(task_name, default)

    def has_task(self, task_name: str) -> bool:
        """检查任务是否存在

        参数：
            task_name: 任务名称

        返回：
            True 如果任务存在，否则 False
        """
        return task_name in self._tasks

    def remove_task(self, task_name: str) -> None:
        """删除任务结果

        参数：
            task_name: 任务名称
        """
        if task_name in self._tasks:
            del self._tasks[task_name]

    def get_all_task_names(self) -> list[str]:
        """获取所有任务名称

        返回：
            任务名称列表
        """
        return list(self._tasks.keys())

    def set_variable(self, name: str, value: Any) -> None:
        """设置共享变量

        参数：
            name: 变量名
            value: 变量值（任意类型）
        """
        self._variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """获取共享变量

        参数：
            name: 变量名
            default: 默认值（如果变量不存在）

        返回：
            变量值，如果不存在则返回 default
        """
        return self._variables.get(name, default)

    def is_empty(self) -> bool:
        """检查上下文是否为空

        返回：
            True 如果没有任务结果和共享变量，否则 False
        """
        return len(self._tasks) == 0 and len(self._variables) == 0

    def size(self) -> int:
        """获取任务结果数量

        返回：
            任务结果数量
        """
        return len(self._tasks)

    def clear(self) -> None:
        """清空上下文（删除所有任务结果和共享变量）"""
        self._tasks.clear()
        self._variables.clear()

    def copy(self) -> ExecutionContext:
        """复制上下文（深拷贝）

        返回：
            新的 ExecutionContext 实例（独立副本）
        """
        new_context = ExecutionContext()
        new_context._tasks = deepcopy(self._tasks)
        new_context._variables = deepcopy(self._variables)
        return new_context

    def merge(self, other: ExecutionContext) -> None:
        """合并另一个上下文

        将 other 的任务结果和共享变量合并到当前上下文。
        如果有重复的键，other 的值会覆盖当前值。

        参数：
            other: 另一个 ExecutionContext 实例
        """
        self._tasks.update(other._tasks)
        self._variables.update(other._variables)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（序列化）

        返回：
            字典格式的上下文数据：
            {
                "tasks": {"Task 1": {...}, "Task 2": {...}},
                "variables": {"var1": "value1", "var2": "value2"}
            }
        """
        return {
            "tasks": deepcopy(self._tasks),
            "variables": deepcopy(self._variables),
        }

    def __repr__(self) -> str:
        """字符串表示"""
        return f"ExecutionContext(tasks={len(self._tasks)}, variables={len(self._variables)})"

    def __str__(self) -> str:
        """用户友好的字符串表示"""
        return (
            f"ExecutionContext with {len(self._tasks)} tasks and {len(self._variables)} variables"
        )
