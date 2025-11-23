"""Workflow Enhanced Features DTO

包括：
- ScheduleWorkflowRequest/Response
- EnhancedChatWorkflowRequest/Response
- ExecuteConcurrentWorkflowsRequest/Response
"""

from typing import Any

from pydantic import BaseModel, Field


# ========== Schedule Workflow DTOs ==========


class ScheduleWorkflowRequest(BaseModel):
    """为工作流创建定时任务的请求"""

    cron_expression: str = Field(..., description="Cron 表达式", example="0 9 * * MON-FRI")
    max_retries: int = Field(default=3, description="最大重试次数", ge=0)

    class Config:
        json_schema_extra = {
            "example": {
                "cron_expression": "0 9 * * MON-FRI",
                "max_retries": 3,
            }
        }


class ScheduledWorkflowResponse(BaseModel):
    """定时工作流的响应"""

    id: str
    workflow_id: str
    cron_expression: str
    status: str = Field(description="Status: active/disabled/paused")
    next_execution_time: str | None = None
    max_retries: int = 0
    consecutive_failures: int = 0

    @classmethod
    def from_entity(cls, entity: Any) -> "ScheduledWorkflowResponse":
        """从领域实体转换"""
        return cls(
            id=entity.id,
            workflow_id=entity.workflow_id,
            cron_expression=entity.cron_expression,
            status=entity.status,
            next_execution_time=str(entity.next_execution_time)
            if hasattr(entity, "next_execution_time") and entity.next_execution_time
            else None,
            max_retries=entity.max_retries,
            consecutive_failures=entity.consecutive_failures,
        )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "scheduled_123",
                "workflow_id": "wf_123",
                "cron_expression": "0 9 * * MON-FRI",
                "status": "active",
                "next_execution_time": "2025-01-24T09:00:00",
                "max_retries": 3,
                "consecutive_failures": 0,
            }
        }


# ========== Concurrent Workflows DTOs ==========


class ExecuteConcurrentWorkflowsRequest(BaseModel):
    """并发执行多个工作流的请求"""

    workflow_ids: list[str] = Field(..., description="工作流 ID 列表")
    max_concurrent: int = Field(default=5, description="最大并发数", ge=1)

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_ids": ["wf_1", "wf_2", "wf_3"],
                "max_concurrent": 5,
            }
        }


class ExecutionResultResponse(BaseModel):
    """执行结果的响应"""

    workflow_id: str
    run_id: str
    status: str = Field(description="Status: submitted/running/succeeded/failed")

    @classmethod
    def from_entity(cls, entity: Any) -> "ExecutionResultResponse":
        """从执行结果实体转换"""
        return cls(
            workflow_id=entity.workflow_id,
            run_id=entity.run_id,
            status=entity.status,
        )

    class Config:
        json_schema_extra = {
            "example": {
                "workflow_id": "wf_1",
                "run_id": "run_123",
                "status": "submitted",
            }
        }


# ========== Chat Workflows DTOs ==========


class ChatMessageRequest(BaseModel):
    """对话消息请求"""

    message: str = Field(..., description="用户消息", min_length=1)

    class Config:
        json_schema_extra = {
            "example": {
                "message": "添加一个 HTTP 节点",
            }
        }


class ChatMessageResponse(BaseModel):
    """对话消息响应"""

    role: str = Field(description="角色: user/assistant")
    content: str = Field(description="消息内容")

    class Config:
        json_schema_extra = {
            "example": {
                "role": "user",
                "content": "添加一个 HTTP 节点",
            }
        }


class EnhancedChatWorkflowResponse(BaseModel):
    """增强对话工作流的响应"""

    success: bool
    response: str | None = None
    error_message: str | None = None
    modified_workflow: dict | None = None

    @classmethod
    def from_entity(cls, entity: Any) -> "EnhancedChatWorkflowResponse":
        """从使用场景结果转换"""
        return cls(
            success=entity.success,
            response=getattr(entity, "response", None),
            error_message=getattr(entity, "error_message", None),
            modified_workflow=getattr(entity, "modified_workflow", None),
        )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "response": "已添加 HTTP 节点",
                "error_message": None,
                "modified_workflow": {"id": "wf_123", "nodes": []},
            }
        }
