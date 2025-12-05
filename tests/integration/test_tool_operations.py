"""工具运维测试 - 阶段 7

测试场景：
1. 热更新验证（添加、修改、删除工具）
2. 并发监控验证
3. 事件订阅验证
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.domain.services.tool_concurrency_controller import (
    ConcurrencyConfig,
    ToolConcurrencyController,
)
from src.domain.services.tool_engine import (
    ToolEngine,
    ToolEngineConfig,
    ToolEngineEvent,
    ToolEngineEventType,
)
from src.domain.services.tool_executor import EchoExecutor, ToolExecutionContext


def create_tool_yaml(name: str, version: str = "1.0.0", handler: str = "echo") -> str:
    """创建工具 YAML 配置"""
    return f"""name: {name}
version: "{version}"
description: Test tool {name}
category: custom
parameters:
  - name: message
    type: string
    description: The message to process
    required: true
entry:
  type: builtin
  handler: {handler}
"""


# =============================================================================
# 热更新测试
# =============================================================================


class TestHotReload:
    """热更新测试"""

    @pytest.mark.asyncio
    async def test_hot_reload_add_new_tool(self, tmp_path: Path):
        """测试：热更新添加新工具"""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # 创建初始工具
        (tools_dir / "initial_tool.yaml").write_text(
            create_tool_yaml("initial_tool"), encoding="utf-8"
        )

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        engine.register_executor("echo", EchoExecutor())

        # 初始加载
        await engine.load()
        assert engine.tool_count == 1

        # 添加新工具
        (tools_dir / "new_tool.yaml").write_text(create_tool_yaml("new_tool"), encoding="utf-8")

        # 触发重载
        changes = await engine.reload()

        # 验证
        assert "new_tool" in changes["added"]
        assert engine.tool_count == 2

    @pytest.mark.asyncio
    async def test_hot_reload_modify_tool(self, tmp_path: Path):
        """测试：热更新修改工具"""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # 创建初始工具
        (tools_dir / "my_tool.yaml").write_text(
            create_tool_yaml("my_tool", "1.0.0"), encoding="utf-8"
        )

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        engine.register_executor("echo", EchoExecutor())
        await engine.load()

        assert engine.get("my_tool").version == "1.0.0"

        # 修改工具
        (tools_dir / "my_tool.yaml").write_text(
            create_tool_yaml("my_tool", "2.0.0"), encoding="utf-8"
        )

        changes = await engine.reload()

        assert "my_tool" in changes["modified"]
        assert engine.get("my_tool").version == "2.0.0"

    @pytest.mark.asyncio
    async def test_hot_reload_remove_tool(self, tmp_path: Path):
        """测试：热更新删除工具"""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        tool_file = tools_dir / "temp_tool.yaml"
        tool_file.write_text(create_tool_yaml("temp_tool"), encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        engine.register_executor("echo", EchoExecutor())
        await engine.load()

        assert engine.get("temp_tool") is not None

        # 删除工具
        tool_file.unlink()
        changes = await engine.reload()

        assert "temp_tool" in changes["removed"]
        assert engine.get("temp_tool") is None

    @pytest.mark.asyncio
    async def test_hot_reload_events(self, tmp_path: Path):
        """测试：热更新事件通知"""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        engine.register_executor("echo", EchoExecutor())

        events: list[ToolEngineEvent] = []
        engine.subscribe(lambda e: events.append(e))

        # 初始加载
        await engine.load()

        # 添加工具
        (tools_dir / "event_tool.yaml").write_text(create_tool_yaml("event_tool"), encoding="utf-8")
        await engine.reload()

        # 验证事件
        event_types = [e.event_type for e in events]
        assert ToolEngineEventType.RELOAD_STARTED in event_types
        assert ToolEngineEventType.TOOL_ADDED in event_types
        assert ToolEngineEventType.RELOAD_COMPLETED in event_types


# =============================================================================
# 并发监控测试
# =============================================================================


class TestConcurrencyMonitoring:
    """并发监控测试"""

    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        """测试：指标追踪"""
        config = ConcurrencyConfig(max_concurrent=5, queue_size=10)
        controller = ToolConcurrencyController(config)

        # 初始状态
        metrics = controller.get_metrics()
        assert metrics.current_concurrent == 0

        # 获取槽位
        slot1 = await controller.acquire_slot("tool1", "c1", "conversation_agent")
        slot2 = await controller.acquire_slot("tool2", "c2", "conversation_agent")

        metrics = controller.get_metrics()
        assert metrics.current_concurrent == 2
        assert metrics.total_acquired == 2

        # 释放槽位
        await controller.release_slot(slot1.slot_id)
        await controller.release_slot(slot2.slot_id)

        metrics = controller.get_metrics()
        assert metrics.current_concurrent == 0

    @pytest.mark.asyncio
    async def test_bucket_metrics(self):
        """测试：分桶指标"""
        config = ConcurrencyConfig(max_concurrent=10, bucket_limits={"http": 3, "ai": 2})
        controller = ToolConcurrencyController(config)

        await controller.acquire_slot("http_tool", "c1", "conversation_agent", bucket="http")
        await controller.acquire_slot("http_tool", "c2", "conversation_agent", bucket="http")
        await controller.acquire_slot("ai_tool", "c3", "conversation_agent", bucket="ai")

        bucket_metrics = controller.get_bucket_metrics()
        assert bucket_metrics["http"]["current"] == 2
        assert bucket_metrics["ai"]["current"] == 1

    @pytest.mark.asyncio
    async def test_rejection_tracking(self):
        """测试：拒绝追踪"""
        config = ConcurrencyConfig(max_concurrent=2, strategy="reject")
        controller = ToolConcurrencyController(config)

        await controller.acquire_slot("tool1", "c1", "conversation_agent")
        await controller.acquire_slot("tool2", "c2", "conversation_agent")

        # 尝试获取更多（应被拒绝）
        slot3 = await controller.acquire_slot("tool3", "c3", "conversation_agent")
        assert slot3 is None

        metrics = controller.get_metrics()
        assert metrics.total_rejected == 1

    @pytest.mark.asyncio
    async def test_timeout_detection(self):
        """测试：超时检测"""
        config = ConcurrencyConfig(max_concurrent=5, default_timeout=0.1)
        controller = ToolConcurrencyController(config)

        await controller.acquire_slot("tool1", "c1", "conversation_agent", timeout=0.1)
        await asyncio.sleep(0.15)

        timeout_slots = controller.get_timeout_slots()
        assert len(timeout_slots) == 1

    @pytest.mark.asyncio
    async def test_timeout_cancellation(self):
        """测试：超时取消"""
        config = ConcurrencyConfig(max_concurrent=5, default_timeout=0.1)
        controller = ToolConcurrencyController(config)

        await controller.acquire_slot("tool1", "c1", "conversation_agent", timeout=0.1)
        await controller.acquire_slot("tool2", "c2", "conversation_agent", timeout=0.1)
        await asyncio.sleep(0.15)

        cancelled = await controller.cancel_timeout_slots()
        assert len(cancelled) == 2

        metrics = controller.get_metrics()
        assert metrics.current_concurrent == 0
        assert metrics.total_timeout == 2


# =============================================================================
# 事件订阅测试
# =============================================================================


class TestEventSubscription:
    """事件订阅测试"""

    @pytest.mark.asyncio
    async def test_execution_events(self, tmp_path: Path):
        """测试：执行事件"""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "event_tool.yaml").write_text(create_tool_yaml("event_tool"), encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        engine.register_executor("echo", EchoExecutor())

        events: list[ToolEngineEvent] = []
        engine.subscribe(lambda e: events.append(e))

        await engine.load()
        assert engine.tool_count == 1, f"加载错误: {engine.load_errors}"

        events.clear()

        context = ToolExecutionContext(caller_id="test", caller_type="direct")
        result = await engine.execute("event_tool", {"message": "hello"}, context)

        assert result.is_success, f"执行失败: {result.error}"

        event_types = [e.event_type for e in events]
        assert ToolEngineEventType.EXECUTION_STARTED in event_types
        assert ToolEngineEventType.EXECUTION_COMPLETED in event_types

    @pytest.mark.asyncio
    async def test_validation_error_event(self, tmp_path: Path):
        """测试：验证错误事件"""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "event_tool.yaml").write_text(create_tool_yaml("event_tool"), encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        engine.register_executor("echo", EchoExecutor())

        events: list[ToolEngineEvent] = []
        engine.subscribe(lambda e: events.append(e))

        await engine.load()
        events.clear()

        context = ToolExecutionContext(caller_id="test", caller_type="direct")
        result = await engine.execute("event_tool", {}, context)

        assert not result.is_success
        assert result.error_type == "validation_error"

        validation_events = [
            e for e in events if e.event_type == ToolEngineEventType.VALIDATION_ERROR
        ]
        assert len(validation_events) == 1


# =============================================================================
# 端到端运维场景测试
# =============================================================================


class TestOperationsScenarios:
    """端到端运维场景测试"""

    @pytest.mark.asyncio
    async def test_complete_tool_lifecycle(self, tmp_path: Path):
        """测试：完整的工具生命周期"""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()

        # 创建初始工具
        (tools_dir / "initial.yaml").write_text(create_tool_yaml("initial"), encoding="utf-8")

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        engine.register_executor("echo", EchoExecutor())

        # 1. 初始加载
        await engine.load()
        assert engine.tool_count == 1

        # 2. 添加工具
        (tools_dir / "lifecycle_tool.yaml").write_text(
            create_tool_yaml("lifecycle_tool"), encoding="utf-8"
        )
        changes = await engine.reload()
        assert "lifecycle_tool" in changes["added"]

        # 3. 执行工具
        context = ToolExecutionContext(caller_id="test", caller_type="direct")
        result = await engine.execute("lifecycle_tool", {"message": "test"}, context)
        assert result.is_success

        # 4. 更新工具
        (tools_dir / "lifecycle_tool.yaml").write_text(
            create_tool_yaml("lifecycle_tool", "2.0.0"), encoding="utf-8"
        )
        changes = await engine.reload()
        assert "lifecycle_tool" in changes["modified"]
        assert engine.get("lifecycle_tool").version == "2.0.0"

        # 5. 删除工具
        (tools_dir / "lifecycle_tool.yaml").unlink()
        changes = await engine.reload()
        assert "lifecycle_tool" in changes["removed"]

    @pytest.mark.asyncio
    async def test_concurrent_tool_execution(self, tmp_path: Path):
        """测试：并发工具执行"""
        tools_dir = tmp_path / "tools"
        tools_dir.mkdir()
        (tools_dir / "concurrent_tool.yaml").write_text(
            create_tool_yaml("concurrent_tool"), encoding="utf-8"
        )

        config = ToolEngineConfig(tools_directory=str(tools_dir))
        engine = ToolEngine(config)
        engine.register_executor("echo", EchoExecutor())
        await engine.load()

        async def execute_tool(i: int):
            context = ToolExecutionContext(caller_id=f"test_{i}", caller_type="direct")
            return await engine.execute("concurrent_tool", {"message": f"msg_{i}"}, context)

        # 并发执行 5 个请求
        results = await asyncio.gather(*[execute_tool(i) for i in range(5)])

        # 验证所有请求成功
        for i, r in enumerate(results):
            assert r.is_success, f"请求 {i} 失败: {r.error}"

        stats = engine.get_statistics()
        assert stats["total_tools"] == 1
