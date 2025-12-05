"""ToolKnowledgeStore 单元测试 - 阶段 6

测试调用记录与知识库集成功能：
- ToolCallRecord 数据结构
- ToolCallSummary 摘要生成
- ToolKnowledgeStore 存储接口
- 查询接口（按会话/时间/工具名）
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from src.domain.services.tool_knowledge_store import (
    InMemoryToolKnowledgeStore,
    ToolCallRecord,
    ToolCallSummary,
    ToolKnowledgeStore,
)

# =============================================================================
# ToolCallRecord 测试
# =============================================================================


class TestToolCallRecord:
    """ToolCallRecord 数据结构测试"""

    def test_create_record_with_required_fields(self):
        """测试：使用必需字段创建记录"""
        record = ToolCallRecord(
            record_id="rec_001",
            tool_name="echo",
            params={"message": "hello"},
            result={"echoed": "hello"},
            execution_time=0.05,
            is_success=True,
        )

        assert record.record_id == "rec_001"
        assert record.tool_name == "echo"
        assert record.params == {"message": "hello"}
        assert record.result == {"echoed": "hello"}
        assert record.execution_time == 0.05
        assert record.is_success is True
        assert record.error is None

    def test_create_record_with_all_fields(self):
        """测试：使用所有字段创建记录"""
        now = datetime.now(UTC)
        record = ToolCallRecord(
            record_id="rec_002",
            tool_name="http_request",
            params={"url": "https://api.example.com"},
            result={"status": 200},
            execution_time=1.5,
            is_success=True,
            error=None,
            error_type=None,
            caller_id="agent_001",
            caller_type="conversation_agent",
            conversation_id="conv_001",
            workflow_id=None,
            created_at=now,
            metadata={"retry_count": 0},
        )

        assert record.caller_id == "agent_001"
        assert record.caller_type == "conversation_agent"
        assert record.conversation_id == "conv_001"
        assert record.created_at == now
        assert record.metadata == {"retry_count": 0}

    def test_create_failed_record(self):
        """测试：创建失败记录"""
        record = ToolCallRecord(
            record_id="rec_003",
            tool_name="http_request",
            params={"url": "invalid"},
            result={},
            execution_time=0.01,
            is_success=False,
            error="Invalid URL format",
            error_type="validation_error",
        )

        assert record.is_success is False
        assert record.error == "Invalid URL format"
        assert record.error_type == "validation_error"

    def test_record_to_dict(self):
        """测试：记录转换为字典"""
        record = ToolCallRecord(
            record_id="rec_004",
            tool_name="echo",
            params={"message": "test"},
            result={"echoed": "test"},
            execution_time=0.02,
            is_success=True,
        )

        data = record.to_dict()

        assert data["record_id"] == "rec_004"
        assert data["tool_name"] == "echo"
        assert data["is_success"] is True
        assert "created_at" in data

    def test_record_from_dict(self):
        """测试：从字典创建记录"""
        data = {
            "record_id": "rec_005",
            "tool_name": "echo",
            "params": {"message": "hello"},
            "result": {"echoed": "hello"},
            "execution_time": 0.03,
            "is_success": True,
            "created_at": datetime.now(UTC).isoformat(),
        }

        record = ToolCallRecord.from_dict(data)

        assert record.record_id == "rec_005"
        assert record.tool_name == "echo"
        assert record.is_success is True

    def test_record_create_from_execution_result(self):
        """测试：从执行结果创建记录"""
        from src.domain.services.tool_executor import ToolExecutionResult

        exec_result = ToolExecutionResult.success(
            tool_name="echo",
            output={"echoed": "hello"},
            execution_time=0.05,
        )

        record = ToolCallRecord.from_execution_result(
            result=exec_result,
            params={"message": "hello"},
            caller_id="agent_001",
            caller_type="conversation_agent",
            conversation_id="conv_001",
        )

        assert record.tool_name == "echo"
        assert record.is_success is True
        assert record.params == {"message": "hello"}
        assert record.caller_id == "agent_001"
        assert record.conversation_id == "conv_001"


# =============================================================================
# ToolCallSummary 测试
# =============================================================================


class TestToolCallSummary:
    """ToolCallSummary 摘要测试"""

    def test_create_empty_summary(self):
        """测试：创建空摘要"""
        summary = ToolCallSummary(
            conversation_id="conv_001",
            total_calls=0,
            successful_calls=0,
            failed_calls=0,
            total_execution_time=0.0,
            tool_usage={},
            records=[],
        )

        assert summary.total_calls == 0
        assert summary.success_rate == 0.0

    def test_create_summary_with_records(self):
        """测试：使用记录创建摘要"""
        records = [
            ToolCallRecord(
                record_id="rec_001",
                tool_name="echo",
                params={},
                result={},
                execution_time=0.1,
                is_success=True,
            ),
            ToolCallRecord(
                record_id="rec_002",
                tool_name="echo",
                params={},
                result={},
                execution_time=0.2,
                is_success=True,
            ),
            ToolCallRecord(
                record_id="rec_003",
                tool_name="http_request",
                params={},
                result={},
                execution_time=0.5,
                is_success=False,
                error="Timeout",
            ),
        ]

        summary = ToolCallSummary.from_records("conv_001", records)

        assert summary.total_calls == 3
        assert summary.successful_calls == 2
        assert summary.failed_calls == 1
        assert summary.total_execution_time == pytest.approx(0.8, rel=0.01)
        assert summary.tool_usage == {"echo": 2, "http_request": 1}
        assert summary.success_rate == pytest.approx(66.67, rel=0.1)

    def test_summary_to_dict(self):
        """测试：摘要转换为字典"""
        summary = ToolCallSummary(
            conversation_id="conv_001",
            total_calls=5,
            successful_calls=4,
            failed_calls=1,
            total_execution_time=2.5,
            tool_usage={"echo": 3, "http": 2},
            records=[],
        )

        data = summary.to_dict()

        assert data["conversation_id"] == "conv_001"
        assert data["total_calls"] == 5
        assert data["success_rate"] == 80.0
        assert data["avg_execution_time"] == 0.5

    def test_summary_brief_format(self):
        """测试：摘要简要格式（给前端用）"""
        records = [
            ToolCallRecord(
                record_id="rec_001",
                tool_name="echo",
                params={"message": "hello"},
                result={"echoed": "hello"},
                execution_time=0.1,
                is_success=True,
            ),
        ]
        summary = ToolCallSummary.from_records("conv_001", records)

        brief = summary.to_brief()

        assert "total_calls" in brief
        assert "success_rate" in brief
        assert "tool_usage" in brief
        # 简要格式不包含完整记录
        assert "records" not in brief or len(brief.get("records", [])) == 0

    def test_summary_with_error_details(self):
        """测试：摘要包含错误详情"""
        records = [
            ToolCallRecord(
                record_id="rec_001",
                tool_name="http_request",
                params={"url": "invalid"},
                result={},
                execution_time=0.01,
                is_success=False,
                error="Invalid URL",
                error_type="validation_error",
            ),
            ToolCallRecord(
                record_id="rec_002",
                tool_name="http_request",
                params={"url": "https://timeout.com"},
                result={},
                execution_time=30.0,
                is_success=False,
                error="Request timeout",
                error_type="timeout",
            ),
        ]

        summary = ToolCallSummary.from_records("conv_001", records)

        assert summary.failed_calls == 2
        assert len(summary.error_details) == 2
        assert any(e["error_type"] == "validation_error" for e in summary.error_details)
        assert any(e["error_type"] == "timeout" for e in summary.error_details)


# =============================================================================
# InMemoryToolKnowledgeStore 测试
# =============================================================================


class TestInMemoryToolKnowledgeStore:
    """InMemoryToolKnowledgeStore 存储测试"""

    @pytest.fixture
    def store(self) -> InMemoryToolKnowledgeStore:
        """创建存储实例"""
        return InMemoryToolKnowledgeStore()

    @pytest.mark.asyncio
    async def test_save_and_get_record(self, store: InMemoryToolKnowledgeStore):
        """测试：保存和获取记录"""
        record = ToolCallRecord(
            record_id="rec_001",
            tool_name="echo",
            params={"message": "hello"},
            result={"echoed": "hello"},
            execution_time=0.05,
            is_success=True,
        )

        await store.save(record)
        retrieved = await store.get_by_id("rec_001")

        assert retrieved is not None
        assert retrieved.record_id == "rec_001"
        assert retrieved.tool_name == "echo"

    @pytest.mark.asyncio
    async def test_get_nonexistent_record(self, store: InMemoryToolKnowledgeStore):
        """测试：获取不存在的记录"""
        retrieved = await store.get_by_id("nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_query_by_conversation_id(self, store: InMemoryToolKnowledgeStore):
        """测试：按会话 ID 查询"""
        # 保存多条记录
        for i in range(5):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name="echo",
                params={},
                result={},
                execution_time=0.1,
                is_success=True,
                conversation_id="conv_001" if i < 3 else "conv_002",
            )
            await store.save(record)

        # 查询 conv_001
        records = await store.query_by_conversation("conv_001")
        assert len(records) == 3

        # 查询 conv_002
        records = await store.query_by_conversation("conv_002")
        assert len(records) == 2

    @pytest.mark.asyncio
    async def test_query_by_tool_name(self, store: InMemoryToolKnowledgeStore):
        """测试：按工具名查询"""
        tools = ["echo", "echo", "http_request", "echo", "calculator"]
        for i, tool in enumerate(tools):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name=tool,
                params={},
                result={},
                execution_time=0.1,
                is_success=True,
            )
            await store.save(record)

        records = await store.query_by_tool_name("echo")
        assert len(records) == 3

        records = await store.query_by_tool_name("http_request")
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, store: InMemoryToolKnowledgeStore):
        """测试：按时间范围查询"""
        now = datetime.now(UTC)

        # 创建不同时间的记录
        times = [
            now - timedelta(hours=2),
            now - timedelta(hours=1),
            now - timedelta(minutes=30),
            now - timedelta(minutes=10),
            now,
        ]

        for i, t in enumerate(times):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name="echo",
                params={},
                result={},
                execution_time=0.1,
                is_success=True,
                created_at=t,
            )
            await store.save(record)

        # 查询最近 1 小时
        start_time = now - timedelta(hours=1)
        records = await store.query_by_time_range(start_time=start_time)
        assert len(records) == 4  # 最近 1 小时内的 4 条

        # 查询 1-2 小时前（不包含边界）
        end_time = now - timedelta(hours=1, seconds=1)  # 排除正好 1 小时前的记录
        start_time = now - timedelta(hours=2)
        records = await store.query_by_time_range(start_time=start_time, end_time=end_time)
        assert len(records) == 1  # 只有 2 小时前的那条

    @pytest.mark.asyncio
    async def test_query_by_caller(self, store: InMemoryToolKnowledgeStore):
        """测试：按调用者查询"""
        callers = ["agent_001", "agent_001", "agent_002", "workflow_001"]
        caller_types = [
            "conversation_agent",
            "conversation_agent",
            "conversation_agent",
            "workflow_node",
        ]

        for i, (caller, ctype) in enumerate(zip(callers, caller_types, strict=False)):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name="echo",
                params={},
                result={},
                execution_time=0.1,
                is_success=True,
                caller_id=caller,
                caller_type=ctype,
            )
            await store.save(record)

        # 按 caller_id 查询
        records = await store.query_by_caller(caller_id="agent_001")
        assert len(records) == 2

        # 按 caller_type 查询
        records = await store.query_by_caller(caller_type="workflow_node")
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_query_failed_calls(self, store: InMemoryToolKnowledgeStore):
        """测试：查询失败的调用"""
        success_flags = [True, True, False, True, False, False]

        for i, success in enumerate(success_flags):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name="echo",
                params={},
                result={},
                execution_time=0.1,
                is_success=success,
                error=None if success else "Some error",
            )
            await store.save(record)

        records = await store.query_failed()
        assert len(records) == 3

    @pytest.mark.asyncio
    async def test_get_summary_for_conversation(self, store: InMemoryToolKnowledgeStore):
        """测试：获取会话摘要"""
        # 创建混合记录
        records_data = [
            ("echo", True, 0.1),
            ("echo", True, 0.2),
            ("http_request", False, 0.5),
            ("calculator", True, 0.05),
        ]

        for i, (tool, success, time) in enumerate(records_data):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name=tool,
                params={},
                result={},
                execution_time=time,
                is_success=success,
                error=None if success else "Error",
                conversation_id="conv_001",
            )
            await store.save(record)

        summary = await store.get_summary("conv_001")

        assert summary.conversation_id == "conv_001"
        assert summary.total_calls == 4
        assert summary.successful_calls == 3
        assert summary.failed_calls == 1
        assert summary.tool_usage == {"echo": 2, "http_request": 1, "calculator": 1}

    @pytest.mark.asyncio
    async def test_delete_record(self, store: InMemoryToolKnowledgeStore):
        """测试：删除记录"""
        record = ToolCallRecord(
            record_id="rec_001",
            tool_name="echo",
            params={},
            result={},
            execution_time=0.1,
            is_success=True,
        )
        await store.save(record)

        # 确认存在
        assert await store.get_by_id("rec_001") is not None

        # 删除
        deleted = await store.delete("rec_001")
        assert deleted is True

        # 确认已删除
        assert await store.get_by_id("rec_001") is None

    @pytest.mark.asyncio
    async def test_clear_all(self, store: InMemoryToolKnowledgeStore):
        """测试：清空所有记录"""
        for i in range(10):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name="echo",
                params={},
                result={},
                execution_time=0.1,
                is_success=True,
            )
            await store.save(record)

        assert await store.count() == 10

        await store.clear()

        assert await store.count() == 0

    @pytest.mark.asyncio
    async def test_pagination(self, store: InMemoryToolKnowledgeStore):
        """测试：分页查询"""
        for i in range(25):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name="echo",
                params={},
                result={},
                execution_time=0.1,
                is_success=True,
                conversation_id="conv_001",
            )
            await store.save(record)

        # 第一页
        page1 = await store.query_by_conversation("conv_001", limit=10, offset=0)
        assert len(page1) == 10

        # 第二页
        page2 = await store.query_by_conversation("conv_001", limit=10, offset=10)
        assert len(page2) == 10

        # 第三页
        page3 = await store.query_by_conversation("conv_001", limit=10, offset=20)
        assert len(page3) == 5

    @pytest.mark.asyncio
    async def test_concurrent_save(self, store: InMemoryToolKnowledgeStore):
        """测试：并发保存"""

        async def save_record(i: int):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name="echo",
                params={"index": i},
                result={"index": i},
                execution_time=0.1,
                is_success=True,
            )
            await store.save(record)

        # 并发保存 100 条记录
        await asyncio.gather(*[save_record(i) for i in range(100)])

        assert await store.count() == 100


# =============================================================================
# ToolKnowledgeStore 协议测试
# =============================================================================


class TestToolKnowledgeStoreProtocol:
    """ToolKnowledgeStore 协议测试"""

    def test_inmemory_implements_protocol(self):
        """测试：InMemoryToolKnowledgeStore 实现协议"""
        store = InMemoryToolKnowledgeStore()

        # 检查必需方法
        assert hasattr(store, "save")
        assert hasattr(store, "get_by_id")
        assert hasattr(store, "query_by_conversation")
        assert hasattr(store, "query_by_tool_name")
        assert hasattr(store, "query_by_time_range")
        assert hasattr(store, "get_summary")

        # 验证是 ToolKnowledgeStore 的实例
        assert isinstance(store, ToolKnowledgeStore)


# =============================================================================
# 复合查询测试
# =============================================================================


class TestComplexQueries:
    """复合查询测试"""

    @pytest.fixture
    def store(self) -> InMemoryToolKnowledgeStore:
        """创建存储实例"""
        return InMemoryToolKnowledgeStore()

    @pytest.mark.asyncio
    async def test_query_with_multiple_filters(self, store: InMemoryToolKnowledgeStore):
        """测试：多条件组合查询"""
        now = datetime.now(UTC)

        # 创建多样化的记录
        test_data = [
            ("echo", "conv_001", "agent_001", True, now - timedelta(hours=1)),
            ("echo", "conv_001", "agent_001", False, now - timedelta(minutes=30)),
            ("http", "conv_001", "agent_002", True, now - timedelta(minutes=10)),
            ("echo", "conv_002", "agent_001", True, now),
            ("http", "conv_002", "agent_002", False, now),
        ]

        for i, (tool, conv, caller, success, time) in enumerate(test_data):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name=tool,
                params={},
                result={},
                execution_time=0.1,
                is_success=success,
                conversation_id=conv,
                caller_id=caller,
                created_at=time,
            )
            await store.save(record)

        # 组合查询：conv_001 + echo
        records = await store.query(
            conversation_id="conv_001",
            tool_name="echo",
        )
        assert len(records) == 2

        # 组合查询：agent_001 + 成功
        records = await store.query(
            caller_id="agent_001",
            is_success=True,
        )
        assert len(records) == 2

        # 组合查询：最近 20 分钟 + 失败
        records = await store.query(
            start_time=now - timedelta(minutes=20),
            is_success=False,
        )
        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_get_statistics(self, store: InMemoryToolKnowledgeStore):
        """测试：获取统计信息"""
        # 创建测试数据
        tools = ["echo"] * 5 + ["http"] * 3 + ["calculator"] * 2
        success = [True] * 7 + [False] * 3
        times = [0.1, 0.2, 0.15, 0.3, 0.1, 1.0, 1.5, 2.0, 0.05, 0.08]

        for i, (tool, succ, t) in enumerate(zip(tools, success, times, strict=False)):
            record = ToolCallRecord(
                record_id=f"rec_{i:03d}",
                tool_name=tool,
                params={},
                result={},
                execution_time=t,
                is_success=succ,
            )
            await store.save(record)

        stats = await store.get_statistics()

        assert stats["total_records"] == 10
        assert stats["success_count"] == 7
        assert stats["failure_count"] == 3
        assert stats["success_rate"] == 70.0
        assert "avg_execution_time" in stats
        assert "tool_distribution" in stats
        assert stats["tool_distribution"]["echo"] == 5
