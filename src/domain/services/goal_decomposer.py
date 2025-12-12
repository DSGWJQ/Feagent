"""目标分解器（GoalDecomposer）

智能目标分解功能，将全局目标分解为可执行的子目标。

组件：
- GoalStatus: 目标状态枚举
- Goal: 目标实体
- GoalDecomposer: 目标分解器（使用LLM）
- GoalToNodeConverter: 目标到节点转换器
- GoalProgress: 目标进度跟踪器

功能：
- 目标创建与管理
- LLM智能分解
- 依赖关系建立
- 执行顺序计算
- 进度跟踪

设计原则：
- 单一职责：每个类专注于一个功能
- 依赖注入：LLM客户端通过构造函数注入
- 领域纯净：不依赖任何框架

"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

logger = logging.getLogger(__name__)


class GoalStatus(Enum):
    """目标状态"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class DecompositionError(Exception):
    """分解错误"""

    pass


class CircularDependencyError(Exception):
    """循环依赖错误"""

    pass


@dataclass
class Goal:
    """目标实体

    表示一个可分解的目标，可以有子目标和依赖关系。

    属性：
        id: 目标唯一标识
        description: 目标描述
        status: 目标状态
        parent_id: 父目标ID（可选）
        dependencies: 依赖的目标ID列表
        success_criteria: 完成标准列表
    """

    id: str
    description: str
    status: GoalStatus = field(default=GoalStatus.PENDING)
    parent_id: str | None = None
    dependencies: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)

    def __post_init__(self):
        """初始化后处理"""
        # 确保status是GoalStatus枚举
        if isinstance(self.status, str):
            self.status = GoalStatus(self.status)

    def start(self) -> None:
        """开始执行目标"""
        if self.status == GoalStatus.PENDING:
            self.status = GoalStatus.IN_PROGRESS

    def complete(self) -> None:
        """完成目标"""
        if self.status == GoalStatus.IN_PROGRESS:
            self.status = GoalStatus.COMPLETED

    def fail(self) -> None:
        """标记目标失败"""
        if self.status == GoalStatus.IN_PROGRESS:
            self.status = GoalStatus.FAILED


class LLMClientProtocol(Protocol):
    """LLM客户端协议"""

    async def generate(self, prompt: str) -> str:
        """生成响应"""
        ...


class GoalDecomposer:
    """目标分解器

    使用LLM将全局目标分解为可执行的子目标。

    使用示例：
        decomposer = GoalDecomposer(llm_client=my_llm)
        goal = Goal(id="goal_1", description="创建用户注册流程")
        sub_goals = await decomposer.decompose(goal)
    """

    def __init__(self, llm_client: LLMClientProtocol):
        """初始化

        参数：
            llm_client: LLM客户端，用于智能分解
        """
        self.llm = llm_client

    async def decompose(self, global_goal: Goal) -> list[Goal]:
        """将全局目标分解为子目标

        参数：
            global_goal: 要分解的全局目标

        返回：
            子目标列表

        异常：
            DecompositionError: 分解失败时抛出
        """
        prompt = self._build_prompt(global_goal)

        try:
            response = await self.llm.generate(prompt)
            sub_goals_data = json.loads(response)
        except json.JSONDecodeError as e:
            raise DecompositionError(f"LLM返回的JSON格式无效: {e}") from e

        sub_goals_list = sub_goals_data.get("sub_goals", [])

        if not sub_goals_list:
            raise DecompositionError("分解结果为空，无法生成子目标")

        # 创建子目标实体
        sub_goals = []
        for i, data in enumerate(sub_goals_list):
            sub_goal = Goal(
                id=f"{global_goal.id}_sub_{i}",
                description=data["description"],
                status=GoalStatus.PENDING,
                parent_id=global_goal.id,
                success_criteria=data.get("success_criteria", []),
            )
            sub_goals.append(sub_goal)

        # 建立依赖关系（转换索引为ID）
        for i, data in enumerate(sub_goals_list):
            for dep_idx in data.get("dependencies", []):
                if isinstance(dep_idx, int) and 0 <= dep_idx < len(sub_goals):
                    sub_goals[i].dependencies.append(sub_goals[dep_idx].id)

        return sub_goals

    def _build_prompt(self, goal: Goal) -> str:
        """构建分解提示词

        参数：
            goal: 要分解的目标

        返回：
            提示词字符串
        """
        return f"""
请将以下目标分解为可执行的子目标：

目标: {goal.description}

要求:
1. 每个子目标应该是独立可执行的
2. 明确子目标之间的依赖关系
3. 子目标数量控制在3-7个

输出格式 (JSON):
{{
    "sub_goals": [
        {{
            "description": "子目标描述",
            "dependencies": [依赖的子目标索引],
            "success_criteria": ["完成标准1", "完成标准2"]
        }}
    ]
}}
"""

    def get_execution_order(self, goals: list[Goal]) -> list[str]:
        """获取执行顺序

        基于依赖关系计算拓扑排序，返回执行顺序。

        参数：
            goals: 目标列表

        返回：
            按执行顺序排列的目标ID列表

        异常：
            CircularDependencyError: 存在循环依赖时抛出
        """
        # 构建图
        goal_map = {g.id: g for g in goals}
        in_degree = {g.id: 0 for g in goals}
        adj_list: dict[str, list[str]] = {g.id: [] for g in goals}

        for goal in goals:
            for dep_id in goal.dependencies:
                if dep_id in goal_map:
                    adj_list[dep_id].append(goal.id)
                    in_degree[goal.id] += 1

        # Kahn's算法进行拓扑排序
        queue = [gid for gid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in adj_list[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查循环依赖
        if len(result) != len(goals):
            raise CircularDependencyError("检测到循环依赖，无法确定执行顺序")

        return result


class GoalToNodeConverter:
    """目标到节点转换器

    将目标列表转换为工作流节点和边。
    """

    def convert(self, goals: list[Goal]) -> tuple:
        """转换目标为节点和边

        参数：
            goals: 目标列表

        返回：
            (nodes, edges) 元组
        """
        nodes = []
        edges = []

        for i, goal in enumerate(goals):
            # 创建节点
            node = {
                "id": goal.id,
                "type": "goal",
                "position": {"x": 100 + i * 200, "y": 100},
                "data": {
                    "label": goal.description[:20] + "..."
                    if len(goal.description) > 20
                    else goal.description,
                    "description": goal.description,
                    "success_criteria": goal.success_criteria,
                },
            }
            nodes.append(node)

            # 创建边（基于依赖关系）
            for dep_id in goal.dependencies:
                edge = {"id": f"edge_{dep_id}_{goal.id}", "source": dep_id, "target": goal.id}
                edges.append(edge)

        return nodes, edges


class GoalProgress:
    """目标进度跟踪器

    跟踪目标及其子目标的完成进度。
    """

    def __init__(self):
        """初始化"""
        self._goals: dict[str, Goal] = {}
        self._children: dict[str, list[str]] = {}  # parent_id -> [child_ids]

    def add_goal(self, goal: Goal) -> None:
        """添加目标

        参数：
            goal: 要添加的目标
        """
        self._goals[goal.id] = goal

        # 建立父子关系
        if goal.parent_id:
            if goal.parent_id not in self._children:
                self._children[goal.parent_id] = []
            self._children[goal.parent_id].append(goal.id)

    def update_goal(self, goal: Goal) -> None:
        """更新目标状态

        参数：
            goal: 更新后的目标
        """
        self._goals[goal.id] = goal

        # 检查父目标是否应该完成
        if goal.parent_id and goal.parent_id in self._goals:
            self._check_parent_completion(goal.parent_id)

    def _check_parent_completion(self, parent_id: str) -> None:
        """检查父目标是否应该完成

        参数：
            parent_id: 父目标ID
        """
        if parent_id not in self._children:
            return

        child_ids = self._children[parent_id]
        all_completed = all(
            self._goals[cid].status == GoalStatus.COMPLETED
            for cid in child_ids
            if cid in self._goals
        )

        if all_completed and parent_id in self._goals:
            parent = self._goals[parent_id]
            if parent.status != GoalStatus.COMPLETED:
                parent.status = GoalStatus.COMPLETED

    def get_progress(self, goal_id: str) -> float:
        """获取目标进度

        参数：
            goal_id: 目标ID

        返回：
            完成进度 (0.0 - 1.0)
        """
        if goal_id not in self._children:
            # 无子目标，返回自身状态
            goal = self._goals.get(goal_id)
            if goal and goal.status == GoalStatus.COMPLETED:
                return 1.0
            return 0.0

        child_ids = self._children[goal_id]
        if not child_ids:
            return 0.0

        completed_count = sum(
            1
            for cid in child_ids
            if cid in self._goals and self._goals[cid].status == GoalStatus.COMPLETED
        )

        return completed_count / len(child_ids)


# 导出
__all__ = [
    "GoalStatus",
    "Goal",
    "GoalDecomposer",
    "GoalToNodeConverter",
    "GoalProgress",
    "DecompositionError",
    "CircularDependencyError",
    "LLMClientProtocol",
]
