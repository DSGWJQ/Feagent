"""Run DTO (Data Transfer Objects)

定义 Run / RunEvent 相关的请求和响应模型

设计原则:
    - 使用 Pydantic BaseModel 进行验证和序列化
    - from_entity() 工厂方法封装实体到 DTO 的转换
    - 支持 from_attributes=True 以便直接从 ORM 对象转换
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.domain.entities.run import Run
from src.domain.entities.run_event import RunEvent


class CreateRunRequest(BaseModel):
    """创建 Run 请求 DTO

    说明:
        - project_id / workflow_id 通常由路径参数提供
        - 这里保留字段以支持从 body 传入 (或用于一致性校验)
    """

    project_id: str | None = Field(
        default=None,
        description="项目 ID (可选，与路径参数保持一致)",
    )
    workflow_id: str | None = Field(
        default=None,
        description="工作流 ID (可选，与路径参数保持一致)",
    )


class RunResponse(BaseModel):
    """Run 响应 DTO"""

    id: str = Field(..., description="Run ID (run_ 前缀)")
    project_id: str = Field(..., description="Project ID")
    workflow_id: str = Field(..., description="Workflow ID")
    status: str = Field(
        ...,
        description="Run status (created/running/completed/failed)",
    )
    created_at: datetime = Field(..., description="创建时间 (UTC)")
    finished_at: datetime | None = Field(
        default=None,
        description="结束时间 (仅终态有值)",
    )
    duration_seconds: float | None = Field(
        default=None,
        description="执行时长 (秒，仅终态有值)",
    )

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_entity(cls, run: Run) -> "RunResponse":
        """从 Run 实体创建 DTO

        Args:
            run: Run 领域实体

        Returns:
            RunResponse DTO
        """
        return cls(
            id=run.id,
            project_id=run.project_id,
            workflow_id=run.workflow_id,
            status=run.status.value,
            created_at=run.created_at,
            finished_at=run.finished_at,
            duration_seconds=run.duration_seconds,
        )

    @classmethod
    def from_entities(cls, runs: list[Run]) -> list["RunResponse"]:
        """从 Run 实体列表创建 DTO 列表

        Args:
            runs: Run 领域实体列表

        Returns:
            RunResponse DTO 列表
        """
        return [cls.from_entity(run) for run in runs]


class RunEventResponse(BaseModel):
    """RunEvent 响应 DTO"""

    id: int | str = Field(
        ...,
        description="事件 ID (自增 int 或 evt_ 前缀)",
    )
    run_id: str = Field(..., description="Run ID")
    type: str = Field(..., description="事件类型 (node_start/workflow_complete 等)")
    channel: str = Field(..., description="事件通道 (execution/planning 等)")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="事件负载 (JSON)",
    )
    created_at: datetime = Field(..., description="创建时间 (UTC)")
    sequence: int | None = Field(
        default=None,
        description="可选序号 (外部事件序列)",
    )

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_entity(cls, event: RunEvent) -> "RunEventResponse":
        """从 RunEvent 实体创建 DTO

        Args:
            event: RunEvent 领域实体

        Returns:
            RunEventResponse DTO
        """
        return cls(
            id=event.id,
            run_id=event.run_id,
            type=event.type,
            channel=event.channel,
            payload=event.payload,
            created_at=event.created_at,
            sequence=event.sequence,
        )

    @classmethod
    def from_entities(cls, events: list[RunEvent]) -> list["RunEventResponse"]:
        """从 RunEvent 实体列表创建 DTO 列表

        Args:
            events: RunEvent 领域实体列表

        Returns:
            RunEventResponse DTO 列表
        """
        return [cls.from_entity(event) for event in events]


class RunReplayEvent(BaseModel):
    """Run replay event in SSE shape (frontend-facing).

    Contract:
    - Must contain `type` and `run_id` like SSE payloads.
    - Allows additional event fields (node_id/result/error/...) via `extra="allow"`.
    """

    type: str = Field(..., description="事件类型 (node_start/workflow_complete 等)")
    run_id: str = Field(..., description="Run ID")

    model_config = ConfigDict(extra="allow")


class RunReplayEventsPageResponse(BaseModel):
    """Paginated run replay response (cursor-based)."""

    run_id: str = Field(..., description="Run ID")
    events: list[RunReplayEvent] = Field(default_factory=list, description="事件列表（按稳定顺序）")
    next_cursor: int | None = Field(
        default=None,
        description="下一页 cursor（使用最后一个事件的自增 id；无更多则为 null）",
    )
    has_more: bool = Field(default=False, description="是否还有更多事件")


class RunListResponse(BaseModel):
    """Run 列表响应 DTO"""

    runs: list[RunResponse] = Field(default_factory=list, description="Run 列表")
    total: int = Field(..., description="总数")

    @classmethod
    def from_entities(cls, runs: list[Run], total: int | None = None) -> "RunListResponse":
        """从 Run 实体列表创建 DTO

        Args:
            runs: Run 领域实体列表
            total: 总数 (可选，默认为列表长度)

        Returns:
            RunListResponse DTO
        """
        return cls(
            runs=RunResponse.from_entities(runs),
            total=total if total is not None else len(runs),
        )
