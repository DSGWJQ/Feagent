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


# ==================== 压缩上下文 DTO（阶段2新增） ====================


class NodeSummaryItem(BaseModel):
    """节点摘要项"""

    node_id: str = Field(..., description="节点ID")
    type: str | None = Field(default=None, description="节点类型")
    status: str | None = Field(default=None, description="节点状态")
    output_summary: str | None = Field(default=None, description="输出摘要")
    retry_count: int | None = Field(default=None, description="重试次数")


class DecisionHistoryItem(BaseModel):
    """决策历史项"""

    decision_type: str | None = Field(default=None, description="决策类型")
    choice: str | None = Field(default=None, description="选择")
    reason: str | None = Field(default=None, description="原因")
    timestamp: str | None = Field(default=None, description="时间戳")


class ErrorLogItem(BaseModel):
    """错误日志项"""

    node_id: str | None = Field(default=None, description="节点ID")
    error: str | None = Field(default=None, description="错误信息")
    retryable: bool = Field(default=False, description="是否可重试")


class CompressedContextResponse(BaseModel):
    """压缩上下文响应

    包含八段压缩结构和元数据。
    """

    # 元数据
    workflow_id: str = Field(..., description="工作流ID")
    version: int = Field(default=1, description="版本号")
    created_at: str = Field(..., description="创建时间（ISO格式）")

    # 八段内容
    task_goal: str = Field(default="", description="第1段：任务目标")
    execution_status: dict[str, Any] = Field(default_factory=dict, description="第2段：执行状态")
    node_summary: list[dict[str, Any]] = Field(default_factory=list, description="第3段：节点摘要")
    decision_history: list[dict[str, Any]] = Field(
        default_factory=list, description="第4段：决策历史"
    )
    reflection_summary: dict[str, Any] = Field(default_factory=dict, description="第5段：反思摘要")
    conversation_summary: str = Field(default="", description="第6段：对话摘要")
    error_log: list[dict[str, Any]] = Field(default_factory=list, description="第7段：错误日志")
    next_actions: list[str] = Field(default_factory=list, description="第8段：下一步行动")

    # 附加信息
    summary_text: str = Field(default="", description="人类可读的摘要文本")
    evidence_refs: list[str] = Field(default_factory=list, description="证据引用")


class ContextSnapshotItem(BaseModel):
    """上下文快照项"""

    snapshot_id: str = Field(..., description="快照ID")
    workflow_id: str = Field(..., description="工作流ID")
    version: int = Field(default=1, description="版本号")
    created_at: str = Field(..., description="创建时间")
    task_goal: str = Field(default="", description="任务目标")


class ContextHistoryResponse(BaseModel):
    """上下文历史响应"""

    workflow_id: str = Field(..., description="工作流ID")
    snapshots: list[ContextSnapshotItem] = Field(default_factory=list, description="快照列表")
    total: int = Field(default=0, description="总数")


# 导出
__all__ = [
    "WorkflowStateResponse",
    "SystemStatusResponse",
    "WorkflowListResponse",
    "SSEEvent",
    # 压缩上下文 DTO
    "NodeSummaryItem",
    "DecisionHistoryItem",
    "ErrorLogItem",
    "CompressedContextResponse",
    "ContextSnapshotItem",
    "ContextHistoryResponse",
]
