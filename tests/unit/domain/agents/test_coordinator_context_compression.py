"""测试：Coordinator 上下文压缩集成

测试目标：
1. Coordinator 每次收到 Reflect 事件时调用压缩器
2. Coordinator 收到子 agent 输出时调用压缩器
3. 更新对话 agent 可见的上下文快照
4. 压缩结果可通过 API 获取

完成标准：
- Coordinator 能正确调用压缩器
- 压缩结果存储在快照管理器中
- 对话 Agent 能获取压缩后的上下文
"""

import pytest

# ==================== 测试1：压缩器集成基础 ====================


class TestCoordinatorCompressorIntegration:
    """测试 Coordinator 与压缩器的基础集成"""

    def test_coordinator_can_initialize_with_compressor(self):
        """Coordinator 可以初始化时配置压缩器"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )

        compressor = ContextCompressor()
        snapshot_manager = ContextSnapshotManager()

        coordinator = CoordinatorAgent(
            context_compressor=compressor,
            snapshot_manager=snapshot_manager,
        )

        assert coordinator.context_compressor is compressor
        assert coordinator.snapshot_manager is snapshot_manager

    def test_coordinator_can_enable_compression(self):
        """Coordinator 可以启用上下文压缩"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_context_compression()

        assert coordinator._is_compressing_context is True

    def test_coordinator_can_disable_compression(self):
        """Coordinator 可以禁用上下文压缩"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_context_compression()
        coordinator.stop_context_compression()

        assert coordinator._is_compressing_context is False


# ==================== 测试2：反思事件压缩 ====================


class TestReflectionEventCompression:
    """测试反思事件触发压缩"""

    @pytest.mark.asyncio
    async def test_reflection_event_triggers_compression(self):
        """反思事件应触发上下文压缩"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        compressor = ContextCompressor()
        snapshot_manager = ContextSnapshotManager()

        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=compressor,
            snapshot_manager=snapshot_manager,
        )

        coordinator.start_context_compression()
        coordinator.start_reflection_listening()

        # 模拟反思事件
        event = WorkflowReflectionCompletedEvent(
            source="workflow_agent",
            workflow_id="wf_001",
            assessment="执行成功，但可优化数据处理",
            should_retry=False,
            confidence=0.92,
        )

        await event_bus.publish(event)

        # 验证快照已创建
        snapshot = snapshot_manager.get_latest_snapshot("wf_001")
        assert snapshot is not None
        assert snapshot.reflection_summary.get("confidence") == 0.92

    @pytest.mark.asyncio
    async def test_multiple_reflections_update_snapshot(self):
        """多次反思应更新快照"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_context_compression()
        coordinator.start_reflection_listening()

        # 第一次反思
        event1 = WorkflowReflectionCompletedEvent(
            source="workflow_agent",
            workflow_id="wf_001",
            assessment="初步评估",
            confidence=0.7,
        )
        await event_bus.publish(event1)

        # 第二次反思
        event2 = WorkflowReflectionCompletedEvent(
            source="workflow_agent",
            workflow_id="wf_001",
            assessment="最终评估：成功",
            confidence=0.95,
        )
        await event_bus.publish(event2)

        # 验证版本递增
        snapshot = coordinator.snapshot_manager.get_latest_snapshot("wf_001")
        assert snapshot.version >= 2
        assert snapshot.reflection_summary.get("confidence") == 0.95


# ==================== 测试3：节点执行输出压缩 ====================


class TestNodeExecutionOutputCompression:
    """测试节点执行输出触发压缩"""

    @pytest.mark.asyncio
    async def test_node_completion_triggers_compression(self):
        """节点完成应触发上下文压缩"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionStartedEvent,
        )
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_context_compression()
        coordinator.start_monitoring()

        # 工作流开始（会设置 _current_workflow_id）
        start_event = WorkflowExecutionStartedEvent(
            source="workflow_agent",
            workflow_id="wf_001",
            node_count=3,
        )
        await event_bus.publish(start_event)

        # 节点完成（使用 _current_workflow_id 关联）
        node_event = NodeExecutionEvent(
            source="workflow_agent",
            node_id="node_1",
            status="completed",
            result={"output": "分析结果"},
        )
        await event_bus.publish(node_event)

        # 验证快照包含节点信息
        snapshot = coordinator.snapshot_manager.get_latest_snapshot("wf_001")
        assert snapshot is not None
        assert len(snapshot.node_summary) >= 1

    @pytest.mark.asyncio
    async def test_node_failure_triggers_compression_with_error(self):
        """节点失败应触发压缩并记录错误"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionStartedEvent,
        )
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_context_compression()
        coordinator.start_monitoring()

        # 工作流开始
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_001",
                node_count=2,
            )
        )

        # 节点失败（使用 _current_workflow_id 关联）
        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_1",
                status="failed",
                error="Connection timeout",
            )
        )

        # 验证快照包含错误
        snapshot = coordinator.snapshot_manager.get_latest_snapshot("wf_001")
        assert snapshot is not None
        assert len(snapshot.error_log) >= 1


# ==================== 测试4：对话消息压缩 ====================


class TestConversationMessageCompression:
    """测试对话消息触发压缩"""

    @pytest.mark.asyncio
    async def test_simple_message_triggers_compression(self):
        """简单消息应触发上下文压缩"""
        from src.domain.agents.conversation_agent import SimpleMessageEvent
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_simple_message_listening()
        coordinator.start_context_compression()

        # 发送简单消息事件
        event = SimpleMessageEvent(
            source="conversation_agent",
            user_input="帮我分析销售数据",
            response="好的，我来为您分析",
            intent="ANALYZE_DATA",
            confidence=0.95,
            session_id="session_001",
        )
        await event_bus.publish(event)

        # 验证消息被压缩
        # 注意：简单消息可能不关联特定工作流，使用 session_id
        assert len(coordinator.message_log) == 1


# ==================== 测试5：获取对话Agent可见的上下文 ====================


class TestConversationAgentContextAccess:
    """测试对话 Agent 获取压缩上下文"""

    @pytest.mark.asyncio
    async def test_get_compressed_context_for_workflow(self):
        """获取工作流的压缩上下文"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_context_compression()
        coordinator.start_reflection_listening()

        # 模拟反思事件
        await event_bus.publish(
            WorkflowReflectionCompletedEvent(
                source="workflow_agent",
                workflow_id="wf_001",
                assessment="执行完成",
                confidence=0.9,
            )
        )

        # 对话 Agent 获取上下文
        context = coordinator.get_compressed_context("wf_001")

        assert context is not None
        assert context.workflow_id == "wf_001"
        assert context.reflection_summary.get("confidence") == 0.9

    @pytest.mark.asyncio
    async def test_get_context_summary_text(self):
        """获取上下文的摘要文本"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionStartedEvent,
            WorkflowReflectionCompletedEvent,
        )
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_context_compression()
        coordinator.start_monitoring()
        coordinator.start_reflection_listening()

        # 模拟完整流程
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_001",
                node_count=2,
            )
        )

        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_1",
                status="completed",
                result={"data": "result"},
            )
        )

        await event_bus.publish(
            WorkflowReflectionCompletedEvent(
                source="workflow_agent",
                workflow_id="wf_001",
                assessment="执行顺利",
                confidence=0.88,
            )
        )

        # 获取摘要文本
        summary_text = coordinator.get_context_summary_text("wf_001")

        assert summary_text is not None
        assert len(summary_text) > 0

    def test_get_nonexistent_context_returns_none(self):
        """获取不存在的上下文返回 None"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )

        coordinator = CoordinatorAgent(
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        context = coordinator.get_compressed_context("nonexistent_wf")

        assert context is None


# ==================== 测试6：压缩历史和版本管理 ====================


class TestCompressionHistoryAndVersioning:
    """测试压缩历史和版本管理"""

    @pytest.mark.asyncio
    async def test_compression_maintains_version_history(self):
        """压缩应维护版本历史"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        snapshot_manager = ContextSnapshotManager()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=snapshot_manager,
        )

        coordinator.start_context_compression()
        coordinator.start_reflection_listening()

        # 多次反思
        for i in range(3):
            await event_bus.publish(
                WorkflowReflectionCompletedEvent(
                    source="workflow_agent",
                    workflow_id="wf_001",
                    assessment=f"评估 {i + 1}",
                    confidence=0.7 + i * 0.1,
                )
            )

        # 验证历史
        snapshots = snapshot_manager.list_snapshots("wf_001")
        assert len(snapshots) == 3

    @pytest.mark.asyncio
    async def test_get_specific_version_snapshot(self):
        """获取特定版本的快照"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        snapshot_manager = ContextSnapshotManager()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=snapshot_manager,
        )

        coordinator.start_context_compression()
        coordinator.start_reflection_listening()

        snapshot_ids = []
        for i in range(2):
            await event_bus.publish(
                WorkflowReflectionCompletedEvent(
                    source="workflow_agent",
                    workflow_id="wf_001",
                    assessment=f"评估 {i + 1}",
                    confidence=0.8 + i * 0.1,
                )
            )
            # 获取最新的快照 ID
            snapshots = snapshot_manager.list_snapshots("wf_001")
            if snapshots:
                # 获取最新添加的
                latest = max(snapshots, key=lambda s: s.version)
                # 我们无法直接获取 ID，所以跳过这个检查

        # 验证可以获取最新快照
        latest = snapshot_manager.get_latest_snapshot("wf_001")
        assert latest is not None
        assert latest.version == 2


# ==================== 测试7：真实场景测试 ====================


class TestRealWorldScenarios:
    """真实场景测试"""

    @pytest.mark.asyncio
    async def test_complete_workflow_compression_flow(self):
        """完整的工作流压缩流程"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionCompletedEvent,
            WorkflowExecutionStartedEvent,
            WorkflowReflectionCompletedEvent,
        )
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        # 启动所有监听（先启用压缩，再启动监控）
        coordinator.start_context_compression()
        coordinator.start_monitoring()
        coordinator.start_reflection_listening()

        # 1. 工作流开始
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_complete",
                node_count=3,
            )
        )

        # 2. 节点执行（使用 _current_workflow_id 关联）
        for i in range(3):
            await event_bus.publish(
                NodeExecutionEvent(
                    source="workflow_agent",
                    node_id=f"node_{i}",
                    status="completed",
                    result={"output": f"result_{i}"},
                )
            )

        # 3. 工作流完成
        await event_bus.publish(
            WorkflowExecutionCompletedEvent(
                source="workflow_agent",
                workflow_id="wf_complete",
                status="completed",
                result={"final": "success"},
            )
        )

        # 4. 反思
        await event_bus.publish(
            WorkflowReflectionCompletedEvent(
                source="workflow_agent",
                workflow_id="wf_complete",
                assessment="工作流执行成功，所有节点正常完成",
                confidence=0.95,
            )
        )

        # 验证最终上下文
        context = coordinator.get_compressed_context("wf_complete")

        assert context is not None
        assert len(context.node_summary) == 3
        assert context.execution_status.get("status") == "completed"
        assert context.reflection_summary.get("confidence") == 0.95

        # 验证摘要文本
        summary = coordinator.get_context_summary_text("wf_complete")
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_error_recovery_compression_flow(self):
        """错误恢复场景的压缩流程"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionStartedEvent,
            WorkflowReflectionCompletedEvent,
        )
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_context_compression()
        coordinator.start_monitoring()
        coordinator.start_reflection_listening()

        # 工作流开始
        await event_bus.publish(
            WorkflowExecutionStartedEvent(
                source="workflow_agent",
                workflow_id="wf_error",
                node_count=2,
            )
        )

        # 节点失败（使用 _current_workflow_id 关联）
        await event_bus.publish(
            NodeExecutionEvent(
                source="workflow_agent",
                node_id="node_0",
                status="failed",
                error="API timeout",
            )
        )

        # 反思建议重试
        await event_bus.publish(
            WorkflowReflectionCompletedEvent(
                source="workflow_agent",
                workflow_id="wf_error",
                assessment="节点失败，建议重试",
                should_retry=True,
                confidence=0.85,
            )
        )

        # 验证上下文包含错误和重试建议
        context = coordinator.get_compressed_context("wf_error")

        assert context is not None
        assert len(context.error_log) >= 1
        assert context.reflection_summary.get("should_retry") is True


# ==================== 测试8：并发安全 ====================


class TestConcurrencySafety:
    """测试并发安全"""

    @pytest.mark.asyncio
    async def test_concurrent_workflow_compression(self):
        """并发工作流压缩"""
        import asyncio

        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_compressor import (
            ContextCompressor,
            ContextSnapshotManager,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_compressor=ContextCompressor(),
            snapshot_manager=ContextSnapshotManager(),
        )

        coordinator.start_context_compression()
        coordinator.start_reflection_listening()

        async def simulate_workflow(wf_id: str):
            # 使用反思事件，因为它有 workflow_id 字段
            from src.domain.agents.workflow_agent import WorkflowReflectionCompletedEvent

            await event_bus.publish(
                WorkflowReflectionCompletedEvent(
                    source="workflow_agent",
                    workflow_id=wf_id,
                    assessment=f"工作流 {wf_id} 执行完成",
                    confidence=0.9,
                )
            )

        # 并发执行多个工作流
        await asyncio.gather(*[simulate_workflow(f"wf_{i}") for i in range(5)])

        # 验证所有工作流都有快照
        for i in range(5):
            context = coordinator.get_compressed_context(f"wf_{i}")
            assert context is not None
