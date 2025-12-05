"""ToolKnowledgeStore - 工具调用记录与知识库 - 阶段 6

业务定义：
- ToolCallRecord: 单次工具调用记录
- ToolCallSummary: 调用摘要（给前端/WorkflowAgent）
- ToolKnowledgeStore: 知识库存储协议
- InMemoryToolKnowledgeStore: 内存实现

设计原则：
- 完整记录每次调用（参数、结果、耗时、错误）
- 支持多维度查询（会话、时间、工具名、调用者）
- 提供摘要生成功能
- 线程安全
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.services.tool_executor import ToolExecutionResult


# =============================================================================
# 工具调用记录
# =============================================================================


@dataclass
class ToolCallRecord:
    """工具调用记录

    记录单次工具调用的完整信息：
    - 调用参数和结果
    - 执行时间和状态
    - 调用者信息
    - 错误详情（如有）
    """

    # 基本标识
    record_id: str
    tool_name: str

    # 调用数据
    params: dict[str, Any]
    result: dict[str, Any]

    # 执行信息
    execution_time: float
    is_success: bool

    # 错误信息
    error: str | None = None
    error_type: str | None = None

    # 调用者信息
    caller_id: str | None = None
    caller_type: str = "unknown"
    conversation_id: str | None = None
    workflow_id: str | None = None

    # 时间戳
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # 元数据
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_execution_result(
        cls,
        result: ToolExecutionResult,
        params: dict[str, Any],
        caller_id: str | None = None,
        caller_type: str = "unknown",
        conversation_id: str | None = None,
        workflow_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolCallRecord:
        """从执行结果创建记录

        参数：
            result: ToolExecutionResult 执行结果
            params: 调用参数
            caller_id: 调用者 ID
            caller_type: 调用者类型
            conversation_id: 会话 ID
            workflow_id: 工作流 ID
            metadata: 元数据

        返回：
            ToolCallRecord 实例
        """
        return cls(
            record_id=f"rec_{uuid.uuid4().hex[:12]}",
            tool_name=result.tool_name,
            params=params,
            result=result.output,
            execution_time=result.execution_time,
            is_success=result.is_success,
            error=result.error,
            error_type=result.error_type,
            caller_id=caller_id,
            caller_type=caller_type,
            conversation_id=conversation_id,
            workflow_id=workflow_id,
            created_at=result.executed_at,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "record_id": self.record_id,
            "tool_name": self.tool_name,
            "params": self.params,
            "result": self.result,
            "execution_time": self.execution_time,
            "is_success": self.is_success,
            "error": self.error,
            "error_type": self.error_type,
            "caller_id": self.caller_id,
            "caller_type": self.caller_type,
            "conversation_id": self.conversation_id,
            "workflow_id": self.workflow_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolCallRecord:
        """从字典创建记录"""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(UTC)

        return cls(
            record_id=data["record_id"],
            tool_name=data["tool_name"],
            params=data.get("params", {}),
            result=data.get("result", {}),
            execution_time=data.get("execution_time", 0.0),
            is_success=data.get("is_success", False),
            error=data.get("error"),
            error_type=data.get("error_type"),
            caller_id=data.get("caller_id"),
            caller_type=data.get("caller_type", "unknown"),
            conversation_id=data.get("conversation_id"),
            workflow_id=data.get("workflow_id"),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )


# =============================================================================
# 工具调用摘要
# =============================================================================


@dataclass
class ToolCallSummary:
    """工具调用摘要

    汇总会话中的工具调用信息：
    - 调用统计（总数、成功、失败）
    - 工具使用分布
    - 执行时间统计
    - 错误详情
    """

    conversation_id: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    total_execution_time: float
    tool_usage: dict[str, int]
    records: list[ToolCallRecord]
    error_details: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def success_rate(self) -> float:
        """成功率（百分比）"""
        if self.total_calls == 0:
            return 0.0
        return round(self.successful_calls / self.total_calls * 100, 2)

    @property
    def avg_execution_time(self) -> float:
        """平均执行时间"""
        if self.total_calls == 0:
            return 0.0
        return round(self.total_execution_time / self.total_calls, 4)

    @classmethod
    def from_records(
        cls,
        conversation_id: str,
        records: list[ToolCallRecord],
    ) -> ToolCallSummary:
        """从记录列表创建摘要

        参数：
            conversation_id: 会话 ID
            records: 调用记录列表

        返回：
            ToolCallSummary 实例
        """
        total_calls = len(records)
        successful_calls = sum(1 for r in records if r.is_success)
        failed_calls = total_calls - successful_calls
        total_execution_time = sum(r.execution_time for r in records)

        # 统计工具使用
        tool_usage: dict[str, int] = defaultdict(int)
        for r in records:
            tool_usage[r.tool_name] += 1

        # 收集错误详情
        error_details = [
            {
                "record_id": r.record_id,
                "tool_name": r.tool_name,
                "error": r.error,
                "error_type": r.error_type,
                "execution_time": r.execution_time,
            }
            for r in records
            if not r.is_success
        ]

        return cls(
            conversation_id=conversation_id,
            total_calls=total_calls,
            successful_calls=successful_calls,
            failed_calls=failed_calls,
            total_execution_time=total_execution_time,
            tool_usage=dict(tool_usage),
            records=records,
            error_details=error_details,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（完整格式）"""
        return {
            "conversation_id": self.conversation_id,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.success_rate,
            "total_execution_time": self.total_execution_time,
            "avg_execution_time": self.avg_execution_time,
            "tool_usage": self.tool_usage,
            "error_details": self.error_details,
            "records": [r.to_dict() for r in self.records],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_brief(self) -> dict[str, Any]:
        """转换为简要格式（给前端用）

        不包含完整记录，只有统计信息
        """
        return {
            "conversation_id": self.conversation_id,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.success_rate,
            "avg_execution_time": self.avg_execution_time,
            "tool_usage": self.tool_usage,
            "has_errors": len(self.error_details) > 0,
        }


# =============================================================================
# 知识库存储协议
# =============================================================================


class ToolKnowledgeStore(ABC):
    """工具知识库存储协议

    定义知识库必须实现的方法：
    - 保存和获取记录
    - 多维度查询
    - 摘要生成
    - 统计信息
    """

    @abstractmethod
    async def save(self, record: ToolCallRecord) -> None:
        """保存记录"""
        ...

    @abstractmethod
    async def get_by_id(self, record_id: str) -> ToolCallRecord | None:
        """根据 ID 获取记录"""
        ...

    @abstractmethod
    async def query_by_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """按会话 ID 查询"""
        ...

    @abstractmethod
    async def query_by_tool_name(
        self,
        tool_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """按工具名查询"""
        ...

    @abstractmethod
    async def query_by_time_range(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """按时间范围查询"""
        ...

    @abstractmethod
    async def query_by_caller(
        self,
        caller_id: str | None = None,
        caller_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """按调用者查询"""
        ...

    @abstractmethod
    async def query_failed(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """查询失败的调用"""
        ...

    @abstractmethod
    async def query(
        self,
        conversation_id: str | None = None,
        tool_name: str | None = None,
        caller_id: str | None = None,
        caller_type: str | None = None,
        is_success: bool | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """组合条件查询"""
        ...

    @abstractmethod
    async def get_summary(self, conversation_id: str) -> ToolCallSummary:
        """获取会话摘要"""
        ...

    @abstractmethod
    async def get_statistics(self) -> dict[str, Any]:
        """获取全局统计信息"""
        ...

    @abstractmethod
    async def delete(self, record_id: str) -> bool:
        """删除记录"""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """清空所有记录"""
        ...

    @abstractmethod
    async def count(self) -> int:
        """获取记录总数"""
        ...


# =============================================================================
# 内存实现
# =============================================================================


class InMemoryToolKnowledgeStore(ToolKnowledgeStore):
    """内存知识库实现

    特点：
    - 线程安全（使用 asyncio.Lock）
    - 支持所有查询接口
    - 适合开发和测试
    """

    def __init__(self) -> None:
        """初始化内存存储"""
        self._records: dict[str, ToolCallRecord] = {}
        self._lock = asyncio.Lock()

        # 索引（加速查询）
        self._by_conversation: dict[str, list[str]] = defaultdict(list)
        self._by_tool: dict[str, list[str]] = defaultdict(list)
        self._by_caller: dict[str, list[str]] = defaultdict(list)

    async def save(self, record: ToolCallRecord) -> None:
        """保存记录"""
        async with self._lock:
            self._records[record.record_id] = record

            # 更新索引
            if record.conversation_id:
                self._by_conversation[record.conversation_id].append(record.record_id)
            self._by_tool[record.tool_name].append(record.record_id)
            if record.caller_id:
                self._by_caller[record.caller_id].append(record.record_id)

    async def get_by_id(self, record_id: str) -> ToolCallRecord | None:
        """根据 ID 获取记录"""
        async with self._lock:
            return self._records.get(record_id)

    async def query_by_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """按会话 ID 查询"""
        async with self._lock:
            record_ids = self._by_conversation.get(conversation_id, [])
            records = [self._records[rid] for rid in record_ids if rid in self._records]
            # 按时间排序
            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[offset : offset + limit]

    async def query_by_tool_name(
        self,
        tool_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """按工具名查询"""
        async with self._lock:
            record_ids = self._by_tool.get(tool_name, [])
            records = [self._records[rid] for rid in record_ids if rid in self._records]
            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[offset : offset + limit]

    async def query_by_time_range(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """按时间范围查询"""
        async with self._lock:
            records = list(self._records.values())

            if start_time:
                records = [r for r in records if r.created_at >= start_time]
            if end_time:
                records = [r for r in records if r.created_at <= end_time]

            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[offset : offset + limit]

    async def query_by_caller(
        self,
        caller_id: str | None = None,
        caller_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """按调用者查询"""
        async with self._lock:
            if caller_id:
                record_ids = self._by_caller.get(caller_id, [])
                records = [self._records[rid] for rid in record_ids if rid in self._records]
            else:
                records = list(self._records.values())

            if caller_type:
                records = [r for r in records if r.caller_type == caller_type]

            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[offset : offset + limit]

    async def query_failed(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """查询失败的调用"""
        async with self._lock:
            records = [r for r in self._records.values() if not r.is_success]
            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[offset : offset + limit]

    async def query(
        self,
        conversation_id: str | None = None,
        tool_name: str | None = None,
        caller_id: str | None = None,
        caller_type: str | None = None,
        is_success: bool | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        """组合条件查询"""
        async with self._lock:
            records = list(self._records.values())

            # 应用过滤条件
            if conversation_id:
                records = [r for r in records if r.conversation_id == conversation_id]
            if tool_name:
                records = [r for r in records if r.tool_name == tool_name]
            if caller_id:
                records = [r for r in records if r.caller_id == caller_id]
            if caller_type:
                records = [r for r in records if r.caller_type == caller_type]
            if is_success is not None:
                records = [r for r in records if r.is_success == is_success]
            if start_time:
                records = [r for r in records if r.created_at >= start_time]
            if end_time:
                records = [r for r in records if r.created_at <= end_time]

            records.sort(key=lambda r: r.created_at, reverse=True)
            return records[offset : offset + limit]

    async def get_summary(self, conversation_id: str) -> ToolCallSummary:
        """获取会话摘要"""
        records = await self.query_by_conversation(conversation_id, limit=10000)
        return ToolCallSummary.from_records(conversation_id, records)

    async def get_statistics(self) -> dict[str, Any]:
        """获取全局统计信息"""
        async with self._lock:
            records = list(self._records.values())

            total = len(records)
            success_count = sum(1 for r in records if r.is_success)
            failure_count = total - success_count

            # 工具分布
            tool_dist: dict[str, int] = defaultdict(int)
            for r in records:
                tool_dist[r.tool_name] += 1

            # 平均执行时间
            total_time = sum(r.execution_time for r in records)
            avg_time = total_time / total if total > 0 else 0.0

            return {
                "total_records": total,
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": round(success_count / total * 100, 2) if total > 0 else 0.0,
                "total_execution_time": total_time,
                "avg_execution_time": round(avg_time, 4),
                "tool_distribution": dict(tool_dist),
            }

    async def delete(self, record_id: str) -> bool:
        """删除记录"""
        async with self._lock:
            if record_id not in self._records:
                return False

            record = self._records.pop(record_id)

            # 更新索引
            if record.conversation_id and record_id in self._by_conversation.get(
                record.conversation_id, []
            ):
                self._by_conversation[record.conversation_id].remove(record_id)
            if record_id in self._by_tool.get(record.tool_name, []):
                self._by_tool[record.tool_name].remove(record_id)
            if record.caller_id and record_id in self._by_caller.get(record.caller_id, []):
                self._by_caller[record.caller_id].remove(record_id)

            return True

    async def clear(self) -> None:
        """清空所有记录"""
        async with self._lock:
            self._records.clear()
            self._by_conversation.clear()
            self._by_tool.clear()
            self._by_caller.clear()

    async def count(self) -> int:
        """获取记录总数"""
        async with self._lock:
            return len(self._records)


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "ToolCallRecord",
    "ToolCallSummary",
    "ToolKnowledgeStore",
    "InMemoryToolKnowledgeStore",
]
