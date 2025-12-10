"""控制流中间表示 (Control Flow IR)

业务定义：
- 从自然语言中提取的控制流结构化表示
- 独立于具体实现，便于验证和转换
- 支持决策点、循环、任务依赖等语义

设计原则：
- 纯数据类，不依赖外部框架（DDD要求）
- 支持序列化/反序列化，便于LLM交互
- 包含置信度等元信息，支持降级策略

使用示例：
    # 创建决策点
    decision = DecisionPoint(
        id="dec1",
        description="quality_check",
        expression="quality_score > 0.8",
        branches=[
            DecisionBranch(label="high", target_task_id="analyze"),
            DecisionBranch(label="low", target_task_id="clean")
        ]
    )

    # 创建循环
    loop = LoopSpec(
        id="loop1",
        description="process_datasets",
        collection="datasets",
        loop_variable="dataset",
        body_task_ids=["validate", "transform"]
    )

    # 组合成 IR
    ir = ControlFlowIR(decisions=[decision], loops=[loop])
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ControlFlowTask:
    """控制流任务

    表示工作流中的一个基础任务单元。
    """

    id: str
    name: str
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionBranch:
    """决策分支

    表示条件判断的一个分支路径。

    属性：
        label: 分支标签（如 "high_quality", "low_quality"）
        target_task_id: 分支目标任务ID
        expression: 分支条件表达式（可选，用于边条件）
    """

    label: str
    target_task_id: str | None = None
    expression: str | None = None


@dataclass
class DecisionPoint:
    """决策点

    表示工作流中的条件判断节点。

    属性：
        id: 决策点唯一标识
        description: 描述信息
        expression: 条件表达式（用于 CONDITION 节点配置）
        branches: 决策分支列表
        confidence: 识别置信度（0.0-1.0）
        source_text: 原始文本片段（用于调试）
    """

    id: str
    description: str
    expression: str
    branches: list[DecisionBranch] = field(default_factory=list)
    confidence: float = 1.0
    source_text: str = ""


@dataclass
class LoopSpec:
    """循环规格

    表示工作流中的循环节点配置。

    属性：
        id: 循环唯一标识
        description: 描述信息
        collection: 集合字段名（用于 LOOP 节点 collection_field）
        loop_variable: 迭代变量名（用于 LOOP 节点 item_variable）
        loop_type: 循环类型（for_each | map | filter | while）
        body_task_ids: 循环体任务ID列表
        condition: 循环条件（仅 while 类型使用）
        confidence: 识别置信度（0.0-1.0）
        source_text: 原始文本片段（用于调试）
    """

    id: str
    description: str
    collection: str
    loop_variable: str = "item"
    loop_type: str = "for_each"
    body_task_ids: list[str] = field(default_factory=list)
    condition: str | None = None
    confidence: float = 1.0
    source_text: str = ""


@dataclass
class ControlFlowIR:
    """控制流中间表示

    聚合决策点、循环、任务等控制流元素的顶层容器。

    属性：
        tasks: 任务列表
        decisions: 决策点列表
        loops: 循环规格列表

    方法：
        is_empty: 判断 IR 是否为空
        from_dict: 从字典反序列化（便于 LLM 输出）
    """

    tasks: list[ControlFlowTask] = field(default_factory=list)
    decisions: list[DecisionPoint] = field(default_factory=list)
    loops: list[LoopSpec] = field(default_factory=list)

    def is_empty(self) -> bool:
        """判断 IR 是否为空

        返回：
            如果不包含任何任务、决策或循环，返回 True
        """
        return not (self.tasks or self.decisions or self.loops)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ControlFlowIR":
        """从字典反序列化

        便于将 LLM 输出的结构化数据转换为 IR 对象。

        参数：
            data: 包含 tasks/decisions/loops 的字典

        返回：
            ControlFlowIR 实例

        示例：
            data = {
                "decisions": [
                    {"id": "d1", "description": "check", "expression": "x > 0", "branches": []}
                ],
                "loops": [
                    {"id": "l1", "description": "iterate", "collection": "items"}
                ]
            }
            ir = ControlFlowIR.from_dict(data)
        """
        decisions = [
            DecisionPoint(
                id=d.get("id", ""),
                description=d.get("description", ""),
                expression=d.get("expression", ""),
                branches=[
                    DecisionBranch(
                        label=b.get("label", ""),
                        target_task_id=b.get("target_task_id"),
                        expression=b.get("expression"),
                    )
                    for b in d.get("branches", [])
                ],
                confidence=d.get("confidence", 1.0),
                source_text=d.get("source_text", ""),
            )
            for d in data.get("decisions", [])
        ]

        loops = [
            LoopSpec(
                id=loop_data.get("id", ""),
                description=loop_data.get("description", ""),
                collection=loop_data.get("collection", "items"),
                loop_variable=loop_data.get("loop_variable", "item"),
                loop_type=loop_data.get("loop_type", "for_each"),
                body_task_ids=loop_data.get("body_task_ids", []),
                condition=loop_data.get("condition"),
                confidence=loop_data.get("confidence", 1.0),
                source_text=loop_data.get("source_text", ""),
            )
            for loop_data in data.get("loops", [])
        ]

        tasks = [
            ControlFlowTask(
                id=t.get("id", ""),
                name=t.get("name", ""),
                description=t.get("description", ""),
                dependencies=t.get("dependencies", []),
                metadata=t.get("metadata", {}),
            )
            for t in data.get("tasks", [])
        ]

        return cls(tasks=tasks, decisions=decisions, loops=loops)


# 导出
__all__ = [
    "ControlFlowTask",
    "DecisionBranch",
    "DecisionPoint",
    "LoopSpec",
    "ControlFlowIR",
]
