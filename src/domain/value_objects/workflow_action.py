"""WorkflowAction 值对象 - 工作流动作模型

定义工作流中可能的动作类型和数据结构。

ActionType 枚举：
- REASON：推理分析（不执行任何动作）
- EXECUTE_NODE：执行工作流中的一个节点
- WAIT：等待外部事件或用户输入
- FINISH：工作流执行完成
- ERROR_RECOVERY：错误恢复尝试

这些模型作为 LLM 输出解析的目标，提供强类型保证。
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ActionType(str, Enum):
    """工作流动作类型"""

    REASON = "reason"
    EXECUTE_NODE = "execute_node"
    WAIT = "wait"
    FINISH = "finish"
    ERROR_RECOVERY = "error_recovery"


class WorkflowAction(BaseModel):
    """工作流动作模型

    表示工作流中 LLM 决定采取的单个动作。

    字段：
    - type: 动作类型（必填）
    - node_id: 要执行的节点 ID（EXECUTE_NODE 和 ERROR_RECOVERY 时必填）
    - reasoning: 推理说明（可选，用于 REASON 和其他动作的解释）
    - params: 执行参数字典（可选）
    - retry_count: 重试次数（非负整数，默认 0）
    """

    model_config = ConfigDict(
        frozen=True,
        use_enum_values=True,
        extra="ignore",
    )

    type: ActionType
    node_id: str | None = None
    reasoning: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)

    @field_validator("params", mode="before")
    @classmethod
    def _coerce_params(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        raise TypeError("params 必须是 dict")

    @model_validator(mode="after")
    def _validate_node_id_requirements(self) -> "WorkflowAction":
        if self.type in (ActionType.EXECUTE_NODE, ActionType.ERROR_RECOVERY):
            if self.node_id is None or not str(self.node_id).strip():
                raise ValueError("node_id 是必填字段（execute_node / error_recovery）")
        return self


class LLMResponse(BaseModel):
    """LLM 响应模型

    表示 LLM 的原始响应和解析结果。

    字段：
    - raw_content: LLM 返回的原始字符串
    - action: 解析后的 WorkflowAction（解析失败时为 None）
    - is_valid: 解析和验证是否成功
    - error_message: 如果验证失败，包含错误消息
    - parse_attempt: 当前的解析尝试次数（1-3）
    """

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
    )

    raw_content: str
    action: WorkflowAction | None = None
    is_valid: bool = False
    error_message: str | None = None
    parse_attempt: int = Field(default=1, ge=1, le=3)


class WorkflowExecutionContext(BaseModel):
    """工作流执行上下文

    在工作流执行过程中维护的上下文信息。

    字段：
    - workflow_id: 工作流 ID
    - workflow_name: 工作流名称
    - available_nodes: 可用节点 ID 列表
    - executed_nodes: 已执行节点的结果映射 {node_id: result_dict}
    - current_step: 当前执行步骤（从 0 开始）
    - max_steps: 最大步骤限制（默认 50，防止无限循环）
    """

    model_config = ConfigDict(
        extra="ignore",
    )

    workflow_id: str
    workflow_name: str
    available_nodes: list[str]
    executed_nodes: dict[str, Any] = Field(default_factory=dict)
    current_step: int = Field(default=0, ge=0)
    max_steps: int = Field(default=50, ge=1)

    @field_validator("executed_nodes", mode="before")
    @classmethod
    def _coerce_executed_nodes(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        raise TypeError("executed_nodes 必须是 dict")
