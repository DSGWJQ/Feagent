"""协调者状态 DTO

定义协调者状态查询的请求和响应模型。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowStateResponse(BaseModel):
    """工作流状态响应"""

    workflow_id: str = Field(..., description="工作流ID")
    status: str = Field(..., description="工作流状态: running/completed/failed")
    node_count: int = Field(default=0, description="节点总数")
    executed_nodes: list[str] = Field(default_factory=list, description="已执行节点列表")
    running_nodes: list[str] = Field(default_factory=list, description="正在运行节点列表")
    failed_nodes: list[str] = Field(default_factory=list, description="失败节点列表")
    node_inputs: dict[str, Any] = Field(default_factory=dict, description="节点输入数据")
    node_outputs: dict[str, Any] = Field(default_factory=dict, description="节点输出数据")
    node_errors: dict[str, str] = Field(default_factory=dict, description="节点错误信息")
    started_at: datetime | None = Field(default=None, description="开始时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")
    result: dict[str, Any] | None = Field(default=None, description="执行结果")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


class SystemStatusResponse(BaseModel):
    """系统状态响应"""

    total_workflows: int = Field(default=0, description="工作流总数")
    running_workflows: int = Field(default=0, description="运行中工作流数")
    completed_workflows: int = Field(default=0, description="已完成工作流数")
    failed_workflows: int = Field(default=0, description="失败工作流数")
    active_nodes: int = Field(default=0, description="活跃节点数")
    decision_statistics: dict[str, Any] = Field(default_factory=dict, description="决策统计")


class WorkflowListResponse(BaseModel):
    """工作流列表响应"""

    workflows: list[WorkflowStateResponse] = Field(
        default_factory=list, description="工作流状态列表"
    )
    total: int = Field(default=0, description="总数")


class SSEEvent(BaseModel):
    """SSE 事件"""

    type: str = Field(..., description="事件类型")
    workflow_id: str | None = Field(default=None, description="工作流ID")
    data: dict[str, Any] = Field(default_factory=dict, description="事件数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


# 导出
__all__ = [
    "WorkflowStateResponse",
    "SystemStatusResponse",
    "WorkflowListResponse",
    "SSEEvent",
]
