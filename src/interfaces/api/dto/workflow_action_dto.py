"""WorkflowAction DTO（Data Transfer Objects）

用于 API/Interface 层的数据验证与序列化，并提供 DTO ↔ VO 映射。
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.value_objects.workflow_action import ActionType, WorkflowAction


class WorkflowActionDTO(BaseModel):
    """WorkflowAction DTO

    字段与 Domain VO 基本一致，但使用 Pydantic 做输入验证。
    """

    type: ActionType = Field(description="动作类型")
    node_id: str | None = Field(
        default=None,
        description="节点 ID（EXECUTE_NODE 和 ERROR_RECOVERY 时需要）",
    )
    reasoning: str | None = Field(default=None, description="推理过程或动作说明")
    params: dict[str, Any] = Field(default_factory=dict, description="执行参数")
    retry_count: int = Field(default=0, ge=0, description="重试次数")

    @field_validator("node_id", mode="after")
    @classmethod
    def validate_node_id_for_execute_node(cls, v: str | None, info) -> str | None:
        action_type = info.data.get("type")
        if action_type == ActionType.EXECUTE_NODE and not v:
            raise ValueError("EXECUTE_NODE 类型必须提供 node_id")
        if action_type == ActionType.ERROR_RECOVERY and not v:
            raise ValueError("ERROR_RECOVERY 类型必须提供 node_id")
        return v

    def to_vo(self) -> WorkflowAction:
        return WorkflowAction(
            type=self.type,
            node_id=self.node_id,
            reasoning=self.reasoning,
            params=self.params,
            retry_count=self.retry_count,
        )

    @classmethod
    def from_vo(cls, vo: WorkflowAction) -> "WorkflowActionDTO":
        return cls(
            type=vo.type,
            node_id=vo.node_id,
            reasoning=vo.reasoning,
            params=dict(vo.params),
            retry_count=vo.retry_count,
        )

    model_config = ConfigDict(from_attributes=True)
