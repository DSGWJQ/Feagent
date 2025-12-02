"""测试：双向同步协议

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- ConversationAgent和WorkflowAgent需要双向通信
- 决策验证通过后，需要同步到WorkflowAgent执行
- 工作流执行结果需要反馈给ConversationAgent
- 状态变化需要实时同步

真实场景：
1. 对话Agent做出决策 → 协调者验证 → 同步到工作流Agent
2. 工作流Agent执行完成 → 同步执行结果给对话Agent
3. 节点状态变化 → 同步通知所有相关Agent

核心能力：
- 前向同步：决策 → 工作流
- 反向同步：执行结果 → 对话
- 状态同步：节点/工作流状态变化通知

"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestBidirectionalSyncProtocolSetup:
    """测试双向同步协议的基础设置

    业务背景：
    - 同步协议需要连接到EventBus
    - 需要引用ConversationAgent和WorkflowAgent
    - 需要订阅相关事件
    """

    @pytest.mark.asyncio
    async def test_create_sync_protocol(self):
        """测试：创建同步协议

        验收标准：
        - 协议正确初始化
        - 连接到EventBus
        - 可以引用两个Agent
        """
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = MagicMock()
        mock_workflow_agent = MagicMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )

        assert protocol is not None
        assert protocol.event_bus == event_bus
        assert protocol.conversation_agent == mock_conversation_agent
        assert protocol.workflow_agent == mock_workflow_agent

    @pytest.mark.asyncio
    async def test_protocol_subscribes_to_events(self):
        """测试：协议订阅必要事件

        验收标准：
        - 订阅DecisionValidatedEvent
        - 订阅WorkflowExecutionCompletedEvent
        - 订阅NodeExecutionEvent
        """
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionCompletedEvent,
        )
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = MagicMock()
        mock_workflow_agent = MagicMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )

        # 启动协议（订阅事件）
        protocol.start()

        # 检查订阅
        assert DecisionValidatedEvent in event_bus._subscribers
        assert WorkflowExecutionCompletedEvent in event_bus._subscribers
        assert NodeExecutionEvent in event_bus._subscribers


class TestForwardSync:
    """测试前向同步：决策 → 工作流

    业务背景：
    - 决策验证通过后，需要转发给工作流Agent
    - 工作流Agent根据决策类型执行相应操作
    """

    @pytest.mark.asyncio
    async def test_forward_create_node_decision(self):
        """测试：转发创建节点决策

        业务场景：
        1. 协调者验证通过create_node决策
        2. 同步协议捕获事件
        3. 转发给工作流Agent执行

        验收标准：
        - 工作流Agent收到决策
        - handle_decision被调用
        - 节点被创建
        """
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = MagicMock()
        mock_workflow_agent = AsyncMock()
        mock_workflow_agent.handle_decision.return_value = {"node_id": "node_123"}

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # 发布验证通过的决策
        validated_event = DecisionValidatedEvent(
            original_decision_id="decision_001",
            decision_type="create_node",
            payload={"node_type": "LLM", "config": {"user_prompt": "分析数据"}},
        )
        await event_bus.publish(validated_event)

        # 验证工作流Agent被调用
        mock_workflow_agent.handle_decision.assert_called_once()
        call_args = mock_workflow_agent.handle_decision.call_args[0][0]
        assert call_args["decision_type"] == "create_node"
        assert call_args["node_type"] == "LLM"

    @pytest.mark.asyncio
    async def test_forward_connect_nodes_decision(self):
        """测试：转发连接节点决策

        业务场景：
        - 连接两个节点的决策被验证通过
        - 工作流Agent执行连接操作

        验收标准：
        - 连接决策被正确转发
        - 包含source_id和target_id
        """
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = MagicMock()
        mock_workflow_agent = AsyncMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # 发布连接节点决策
        validated_event = DecisionValidatedEvent(
            original_decision_id="decision_002",
            decision_type="connect_nodes",
            payload={"source_id": "node_1", "target_id": "node_2"},
        )
        await event_bus.publish(validated_event)

        # 验证
        mock_workflow_agent.handle_decision.assert_called_once()
        call_args = mock_workflow_agent.handle_decision.call_args[0][0]
        assert call_args["decision_type"] == "connect_nodes"
        assert call_args["source_id"] == "node_1"
        assert call_args["target_id"] == "node_2"

    @pytest.mark.asyncio
    async def test_forward_execute_workflow_decision(self):
        """测试：转发执行工作流决策

        业务场景：
        - 执行工作流的决策被验证通过
        - 工作流Agent开始执行

        验收标准：
        - 执行决策被转发
        - 工作流开始执行
        """
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = MagicMock()
        mock_workflow_agent = AsyncMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # 发布执行工作流决策
        validated_event = DecisionValidatedEvent(
            original_decision_id="decision_003",
            decision_type="execute_workflow",
            payload={"workflow_id": "workflow_xyz"},
        )
        await event_bus.publish(validated_event)

        # 验证
        mock_workflow_agent.handle_decision.assert_called_once()
        call_args = mock_workflow_agent.handle_decision.call_args[0][0]
        assert call_args["decision_type"] == "execute_workflow"


class TestBackwardSync:
    """测试反向同步：执行结果 → 对话

    业务背景：
    - 工作流执行完成后，结果需要反馈给对话Agent
    - 对话Agent可以据此生成回复或做出下一步决策
    """

    @pytest.mark.asyncio
    async def test_backward_sync_execution_completed(self):
        """测试：同步执行完成结果

        业务场景：
        1. 工作流执行完成
        2. 发布完成事件
        3. 同步协议捕获并转发给对话Agent

        验收标准：
        - 对话Agent收到执行结果
        - 包含workflow_id和result
        """
        from src.domain.agents.workflow_agent import WorkflowExecutionCompletedEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = AsyncMock()
        mock_workflow_agent = MagicMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # 发布执行完成事件
        completed_event = WorkflowExecutionCompletedEvent(
            workflow_id="workflow_xyz", status="completed", result={"analysis": "销售数据分析完成"}
        )
        await event_bus.publish(completed_event)

        # 验证对话Agent收到结果
        mock_conversation_agent.receive_execution_result.assert_called_once()
        call_args = mock_conversation_agent.receive_execution_result.call_args[0][0]
        assert call_args["workflow_id"] == "workflow_xyz"
        assert call_args["status"] == "completed"
        assert "analysis" in call_args["result"]

    @pytest.mark.asyncio
    async def test_backward_sync_execution_failed(self):
        """测试：同步执行失败结果

        业务场景：
        - 工作流执行失败
        - 失败信息需要反馈给对话Agent

        验收标准：
        - 对话Agent收到失败信息
        - 包含错误原因
        """
        from src.domain.agents.workflow_agent import WorkflowExecutionCompletedEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = AsyncMock()
        mock_workflow_agent = MagicMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # 发布执行失败事件
        failed_event = WorkflowExecutionCompletedEvent(
            workflow_id="workflow_xyz", status="failed", result={"error": "API调用超时"}
        )
        await event_bus.publish(failed_event)

        # 验证
        mock_conversation_agent.receive_execution_result.assert_called_once()
        call_args = mock_conversation_agent.receive_execution_result.call_args[0][0]
        assert call_args["status"] == "failed"
        assert "error" in call_args["result"]


class TestNodeStatusSync:
    """测试节点状态同步

    业务背景：
    - 节点执行状态变化需要实时通知
    - 对话Agent可以根据节点状态做出响应
    """

    @pytest.mark.asyncio
    async def test_sync_node_execution_started(self):
        """测试：同步节点开始执行

        验收标准：
        - 节点开始执行时发送通知
        - 对话Agent收到节点状态
        """
        from src.domain.agents.workflow_agent import NodeExecutionEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = AsyncMock()
        mock_workflow_agent = MagicMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # 发布节点执行事件
        node_event = NodeExecutionEvent(
            node_id="node_123", node_type="LLM", status="running", result=None
        )
        await event_bus.publish(node_event)

        # 验证
        mock_conversation_agent.receive_node_status.assert_called_once()
        call_args = mock_conversation_agent.receive_node_status.call_args[0][0]
        assert call_args["node_id"] == "node_123"
        assert call_args["status"] == "running"

    @pytest.mark.asyncio
    async def test_sync_node_execution_completed(self):
        """测试：同步节点执行完成

        验收标准：
        - 节点执行完成时发送通知
        - 包含节点输出
        """
        from src.domain.agents.workflow_agent import NodeExecutionEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = AsyncMock()
        mock_workflow_agent = MagicMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # 发布节点完成事件
        node_event = NodeExecutionEvent(
            node_id="node_123",
            node_type="LLM",
            status="completed",
            result={"content": "分析结果：销售额增长20%"},
        )
        await event_bus.publish(node_event)

        # 验证
        mock_conversation_agent.receive_node_status.assert_called_once()
        call_args = mock_conversation_agent.receive_node_status.call_args[0][0]
        assert call_args["status"] == "completed"
        assert call_args["result"]["content"] == "分析结果：销售额增长20%"


class TestSyncBuffer:
    """测试同步缓冲

    业务背景：
    - 高频事件需要缓冲处理
    - 避免对话Agent过载
    """

    @pytest.mark.asyncio
    async def test_buffer_rapid_node_events(self):
        """测试：缓冲快速节点事件

        业务场景：
        - 多个节点快速执行
        - 事件被缓冲后批量发送

        验收标准：
        - 事件被缓冲
        - 批量通知对话Agent
        """
        from src.domain.agents.workflow_agent import NodeExecutionEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = AsyncMock()
        mock_workflow_agent = MagicMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
            buffer_size=3,  # 缓冲3个事件后批量发送
        )
        protocol.start()

        # 快速发布多个事件
        for i in range(3):
            node_event = NodeExecutionEvent(
                node_id=f"node_{i}",
                node_type="LLM",
                status="completed",
                result={"data": f"result_{i}"},
            )
            await event_bus.publish(node_event)

        # 等待缓冲处理
        await asyncio.sleep(0.1)

        # 验证批量通知
        # 可以是单次批量调用或多次单独调用
        assert mock_conversation_agent.receive_node_status.call_count >= 1


class TestSyncState:
    """测试同步状态管理

    业务背景：
    - 需要跟踪同步状态
    - 支持状态查询和统计
    """

    @pytest.mark.asyncio
    async def test_track_sync_statistics(self):
        """测试：跟踪同步统计

        验收标准：
        - 记录转发的决策数
        - 记录同步的结果数
        - 可以查询统计
        """
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.agents.workflow_agent import WorkflowExecutionCompletedEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = AsyncMock()
        mock_workflow_agent = AsyncMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # 发送一些事件
        await event_bus.publish(
            DecisionValidatedEvent(
                original_decision_id="d1",
                decision_type="create_node",
                payload={"node_type": "START"},
            )
        )
        await event_bus.publish(
            DecisionValidatedEvent(
                original_decision_id="d2", decision_type="create_node", payload={"node_type": "END"}
            )
        )
        await event_bus.publish(
            WorkflowExecutionCompletedEvent(workflow_id="w1", status="completed", result={})
        )

        # 获取统计
        stats = protocol.get_statistics()

        assert stats["decisions_forwarded"] == 2
        assert stats["results_synced"] == 1

    @pytest.mark.asyncio
    async def test_get_sync_status(self):
        """测试：获取同步状态

        验收标准：
        - 返回当前同步状态
        - 包含是否运行中
        - 包含缓冲区状态
        """
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = MagicMock()
        mock_workflow_agent = MagicMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )

        # 未启动时
        status_before = protocol.get_status()
        assert status_before["is_running"] is False

        # 启动后
        protocol.start()
        status_after = protocol.get_status()
        assert status_after["is_running"] is True
        assert "buffer_size" in status_after


class TestSyncProtocolLifecycle:
    """测试同步协议生命周期

    业务背景：
    - 协议需要正确启动和停止
    - 停止后不再处理事件
    """

    @pytest.mark.asyncio
    async def test_stop_protocol(self):
        """测试：停止同步协议

        验收标准：
        - 停止后不再处理新事件
        - 状态变为非运行
        """
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = MagicMock()
        mock_workflow_agent = AsyncMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # 停止协议
        protocol.stop()

        # 发布事件
        await event_bus.publish(
            DecisionValidatedEvent(
                original_decision_id="d1", decision_type="create_node", payload={"node_type": "LLM"}
            )
        )

        # 验证没有处理
        mock_workflow_agent.handle_decision.assert_not_called()
        assert protocol.get_status()["is_running"] is False

    @pytest.mark.asyncio
    async def test_restart_protocol(self):
        """测试：重启同步协议

        验收标准：
        - 停止后可以重新启动
        - 重启后正常处理事件
        """
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        mock_conversation_agent = MagicMock()
        mock_workflow_agent = AsyncMock()

        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )

        # 启动 -> 停止 -> 重启
        protocol.start()
        protocol.stop()
        protocol.start()

        # 发布事件
        await event_bus.publish(
            DecisionValidatedEvent(
                original_decision_id="d1", decision_type="create_node", payload={"node_type": "LLM"}
            )
        )

        # 验证正常处理
        mock_workflow_agent.handle_decision.assert_called_once()


class TestRealWorldScenario:
    """测试真实业务场景"""

    @pytest.mark.asyncio
    async def test_complete_sync_flow(self):
        """测试：完整的同步流程

        业务场景：
        1. 对话Agent发布决策
        2. 协调者验证通过
        3. 同步协议转发给工作流Agent
        4. 工作流Agent执行
        5. 执行结果同步回对话Agent

        这是双向同步的核心场景！

        验收标准：
        - 前向同步正确
        - 反向同步正确
        - 状态一致
        """
        from src.domain.agents.coordinator_agent import DecisionValidatedEvent
        from src.domain.agents.workflow_agent import (
            NodeExecutionEvent,
            WorkflowExecutionCompletedEvent,
        )
        from src.domain.services.bidirectional_sync import BidirectionalSyncProtocol
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()

        # 创建Mock Agent（带状态跟踪）
        received_decisions = []
        received_results = []
        received_node_status = []

        mock_conversation_agent = AsyncMock()

        async def capture_result(result):
            received_results.append(result)

        mock_conversation_agent.receive_execution_result.side_effect = capture_result

        async def capture_node_status(status):
            received_node_status.append(status)

        mock_conversation_agent.receive_node_status.side_effect = capture_node_status

        mock_workflow_agent = AsyncMock()

        async def capture_decision(decision):
            received_decisions.append(decision)
            # 模拟工作流Agent执行后发布事件
            if decision["decision_type"] == "execute_workflow":
                # 发布节点执行事件
                await event_bus.publish(
                    NodeExecutionEvent(
                        node_id="node_1", node_type="LLM", status="running", result=None
                    )
                )
                await event_bus.publish(
                    NodeExecutionEvent(
                        node_id="node_1",
                        node_type="LLM",
                        status="completed",
                        result={"analysis": "分析完成"},
                    )
                )
                # 发布完成事件
                await event_bus.publish(
                    WorkflowExecutionCompletedEvent(
                        workflow_id="workflow_xyz",
                        status="completed",
                        result={"final": "工作流执行成功"},
                    )
                )
            return {"status": "success"}

        mock_workflow_agent.handle_decision.side_effect = capture_decision

        # 创建并启动同步协议
        protocol = BidirectionalSyncProtocol(
            event_bus=event_bus,
            conversation_agent=mock_conversation_agent,
            workflow_agent=mock_workflow_agent,
        )
        protocol.start()

        # Act: 发布一系列决策
        # 1. 创建节点
        await event_bus.publish(
            DecisionValidatedEvent(
                original_decision_id="d1",
                decision_type="create_node",
                payload={"node_type": "START", "config": {}},
            )
        )

        await event_bus.publish(
            DecisionValidatedEvent(
                original_decision_id="d2",
                decision_type="create_node",
                payload={"node_type": "LLM", "config": {"user_prompt": "分析"}},
            )
        )

        await event_bus.publish(
            DecisionValidatedEvent(
                original_decision_id="d3",
                decision_type="create_node",
                payload={"node_type": "END", "config": {}},
            )
        )

        # 2. 连接节点
        await event_bus.publish(
            DecisionValidatedEvent(
                original_decision_id="d4",
                decision_type="connect_nodes",
                payload={"source_id": "node_1", "target_id": "node_2"},
            )
        )

        # 3. 执行工作流
        await event_bus.publish(
            DecisionValidatedEvent(
                original_decision_id="d5",
                decision_type="execute_workflow",
                payload={"workflow_id": "workflow_xyz"},
            )
        )

        # Assert
        # 前向同步：所有决策都被转发
        assert len(received_decisions) == 5

        # 反向同步：执行结果被同步
        assert len(received_results) == 1
        assert received_results[0]["status"] == "completed"

        # 节点状态同步
        assert len(received_node_status) == 2  # running + completed

        # 统计
        stats = protocol.get_statistics()
        assert stats["decisions_forwarded"] == 5
        assert stats["results_synced"] == 1


# ==================== 阶段 3：画布→对话同步测试 ====================


class TestCanvasChangeEvent:
    """CanvasChangeEvent 事件测试

    阶段 3 新增：画布变更事件，用于前端到后端的反向同步
    """

    def test_create_canvas_change_event_with_required_fields(self):
        """测试：创建 CanvasChangeEvent 需要必填字段"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_added",
            change_data={
                "node_id": "node_1",
                "node_type": "HTTP",
                "position": {"x": 100, "y": 200},
            },
            client_id="client_1",
        )

        assert event.workflow_id == "wf_123"
        assert event.change_type == "node_added"
        assert event.change_data["node_id"] == "node_1"
        assert event.client_id == "client_1"
        assert event.version == 0  # 默认版本号

    def test_canvas_change_event_supports_all_change_types(self):
        """测试：CanvasChangeEvent 支持所有变更类型"""
        from src.domain.services.bidirectional_sync import CanvasChangeType

        # 验证所有变更类型枚举
        assert CanvasChangeType.NODE_ADDED.value == "node_added"
        assert CanvasChangeType.NODE_UPDATED.value == "node_updated"
        assert CanvasChangeType.NODE_DELETED.value == "node_deleted"
        assert CanvasChangeType.NODE_MOVED.value == "node_moved"
        assert CanvasChangeType.EDGE_ADDED.value == "edge_added"
        assert CanvasChangeType.EDGE_DELETED.value == "edge_deleted"

    def test_canvas_change_event_has_version_for_conflict_detection(self):
        """测试：CanvasChangeEvent 有版本号用于冲突检测"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_updated",
            change_data={"node_id": "node_1", "changes": {"config": {"url": "new"}}},
            client_id="client_1",
            version=5,
        )

        assert event.version == 5


class TestCanvasState:
    """CanvasState 画布状态测试"""

    def test_create_empty_canvas_state(self):
        """测试：创建空画布状态"""
        from src.domain.services.bidirectional_sync import CanvasState

        state = CanvasState(workflow_id="wf_123")

        assert state.workflow_id == "wf_123"
        assert state.nodes == {}
        assert state.edges == {}
        assert state.version == 0

    def test_canvas_state_add_node(self):
        """测试：向画布状态添加节点"""
        from src.domain.services.bidirectional_sync import CanvasState

        state = CanvasState(workflow_id="wf_123")
        state.add_node(
            node_id="node_1",
            node_type="HTTP",
            position={"x": 100, "y": 200},
            config={"url": "https://api.example.com"},
        )

        assert "node_1" in state.nodes
        assert state.nodes["node_1"]["node_type"] == "HTTP"
        assert state.nodes["node_1"]["position"] == {"x": 100, "y": 200}

    def test_canvas_state_update_node(self):
        """测试：更新画布状态中的节点"""
        from src.domain.services.bidirectional_sync import CanvasState

        state = CanvasState(workflow_id="wf_123")
        state.add_node(node_id="node_1", node_type="HTTP", config={"url": "old"})
        state.update_node(node_id="node_1", changes={"config": {"url": "new"}})

        assert state.nodes["node_1"]["config"]["url"] == "new"

    def test_canvas_state_delete_node(self):
        """测试：从画布状态删除节点"""
        from src.domain.services.bidirectional_sync import CanvasState

        state = CanvasState(workflow_id="wf_123")
        state.add_node(node_id="node_1", node_type="HTTP")
        state.delete_node(node_id="node_1")

        assert "node_1" not in state.nodes

    def test_canvas_state_add_edge(self):
        """测试：向画布状态添加边"""
        from src.domain.services.bidirectional_sync import CanvasState

        state = CanvasState(workflow_id="wf_123")
        state.add_edge(edge_id="edge_1", source_id="node_1", target_id="node_2")

        assert "edge_1" in state.edges
        assert state.edges["edge_1"]["source_id"] == "node_1"
        assert state.edges["edge_1"]["target_id"] == "node_2"


class TestCanvasToConversationSync:
    """画布→对话同步测试

    核心测试：验证画布变更能够同步到 ConversationAgent 上下文
    """

    @pytest.fixture
    def event_bus(self):
        """创建 EventBus"""
        from src.domain.services.event_bus import EventBus

        return EventBus()

    @pytest.fixture
    def sync_service(self, event_bus):
        """创建 BidirectionalSyncService"""
        from src.domain.services.bidirectional_sync import BidirectionalSyncService

        return BidirectionalSyncService(event_bus=event_bus)

    def test_sync_service_subscribes_to_canvas_change_event(self, sync_service, event_bus):
        """测试：同步服务订阅 CanvasChangeEvent"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        # 验证已订阅
        assert CanvasChangeEvent in event_bus._subscribers
        assert len(event_bus._subscribers[CanvasChangeEvent]) > 0

    @pytest.mark.asyncio
    async def test_handle_node_added_updates_canvas_state(self, sync_service, event_bus):
        """测试：处理 node_added 更新画布状态"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        # 发布节点添加事件
        event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_added",
            change_data={
                "node_id": "node_1",
                "node_type": "HTTP",
                "position": {"x": 100, "y": 200},
                "config": {"url": "https://api.example.com"},
            },
            client_id="client_1",
        )

        await event_bus.publish(event)

        # 验证画布状态已更新
        state = sync_service.get_canvas_state("wf_123")
        assert "node_1" in state.nodes
        assert state.nodes["node_1"]["node_type"] == "HTTP"

    @pytest.mark.asyncio
    async def test_handle_node_updated_updates_canvas_state(self, sync_service, event_bus):
        """测试：处理 node_updated 更新画布状态"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        # 先添加节点
        add_event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_added",
            change_data={
                "node_id": "node_1",
                "node_type": "HTTP",
                "position": {"x": 100, "y": 200},
                "config": {"url": "https://old.com"},
            },
            client_id="client_1",
        )
        await event_bus.publish(add_event)

        # 更新节点
        update_event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_updated",
            change_data={
                "node_id": "node_1",
                "changes": {"config": {"url": "https://new.com"}},
            },
            client_id="client_1",
            version=1,
        )
        await event_bus.publish(update_event)

        # 验证节点已更新
        state = sync_service.get_canvas_state("wf_123")
        assert state.nodes["node_1"]["config"]["url"] == "https://new.com"

    @pytest.mark.asyncio
    async def test_handle_node_deleted_removes_from_canvas_state(self, sync_service, event_bus):
        """测试：处理 node_deleted 从画布状态移除节点"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        # 先添加节点
        add_event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_added",
            change_data={"node_id": "node_1", "node_type": "HTTP"},
            client_id="client_1",
        )
        await event_bus.publish(add_event)

        # 删除节点
        delete_event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_deleted",
            change_data={"node_id": "node_1"},
            client_id="client_1",
            version=1,
        )
        await event_bus.publish(delete_event)

        # 验证节点已删除
        state = sync_service.get_canvas_state("wf_123")
        assert "node_1" not in state.nodes

    @pytest.mark.asyncio
    async def test_handle_edge_added_updates_canvas_state(self, sync_service, event_bus):
        """测试：处理 edge_added 更新画布状态"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="edge_added",
            change_data={
                "edge_id": "edge_1",
                "source_id": "node_1",
                "target_id": "node_2",
            },
            client_id="client_1",
        )
        await event_bus.publish(event)

        # 验证边已添加
        state = sync_service.get_canvas_state("wf_123")
        assert "edge_1" in state.edges
        assert state.edges["edge_1"]["source_id"] == "node_1"


class TestConversationAgentContextUpdatePhase3:
    """ConversationAgent 上下文更新测试 - 阶段 3

    核心测试：验证画布变更能够更新到 ConversationAgent.SessionContext
    """

    @pytest.fixture
    def event_bus(self):
        from src.domain.services.event_bus import EventBus

        return EventBus()

    @pytest.fixture
    def mock_conversation_agent(self):
        """创建 Mock ConversationAgent"""
        agent = MagicMock()
        agent.session_context = MagicMock()
        agent.session_context.canvas_state = {}
        return agent

    @pytest.fixture
    def sync_service_with_agent(self, event_bus, mock_conversation_agent):
        """创建带 ConversationAgent 的同步服务"""
        from src.domain.services.bidirectional_sync import BidirectionalSyncService

        service = BidirectionalSyncService(event_bus=event_bus)
        service.register_conversation_agent("wf_123", mock_conversation_agent)
        return service, mock_conversation_agent

    @pytest.mark.asyncio
    async def test_canvas_change_updates_conversation_context(
        self, event_bus, sync_service_with_agent
    ):
        """测试：画布变更更新对话上下文

        这是阶段 3 的核心验收测试！
        用户在画布新增节点后，对话 Agent 上下文能获取该节点
        """
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        service, agent = sync_service_with_agent

        # 发布画布变更
        event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_added",
            change_data={
                "node_id": "node_1",
                "node_type": "LLM",
                "position": {"x": 50, "y": 100},
                "config": {"model": "gpt-4"},
            },
            client_id="client_1",
        )
        await event_bus.publish(event)

        # 验证 ConversationAgent 上下文已更新
        assert "nodes" in agent.session_context.canvas_state
        assert "node_1" in agent.session_context.canvas_state["nodes"]

    @pytest.mark.asyncio
    async def test_conversation_agent_can_access_canvas_state_in_reasoning(
        self, event_bus, sync_service_with_agent
    ):
        """测试：ConversationAgent 推理时可以访问画布状态"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        service, agent = sync_service_with_agent

        # 添加多个节点
        for i in range(3):
            event = CanvasChangeEvent(
                source="canvas",
                workflow_id="wf_123",
                change_type="node_added",
                change_data={
                    "node_id": f"node_{i}",
                    "node_type": "HTTP",
                },
                client_id="client_1",
            )
            await event_bus.publish(event)

        # 验证上下文包含所有节点
        canvas_state = agent.session_context.canvas_state
        assert len(canvas_state.get("nodes", {})) == 3


class TestConflictDetectionPhase3:
    """冲突检测测试 - 阶段 3"""

    @pytest.fixture
    def event_bus(self):
        from src.domain.services.event_bus import EventBus

        return EventBus()

    @pytest.fixture
    def sync_service(self, event_bus):
        from src.domain.services.bidirectional_sync import BidirectionalSyncService

        return BidirectionalSyncService(event_bus=event_bus)

    @pytest.mark.asyncio
    async def test_version_conflict_detected(self, sync_service, event_bus):
        """测试：检测版本冲突"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        # 添加节点（版本 0）
        add_event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_added",
            change_data={"node_id": "node_1", "node_type": "HTTP"},
            client_id="client_1",
            version=0,
        )
        await event_bus.publish(add_event)

        # 更新节点（版本 1）
        update_event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_updated",
            change_data={"node_id": "node_1", "changes": {"config": {"url": "a"}}},
            client_id="client_2",
            version=1,
        )
        await event_bus.publish(update_event)

        # 另一个客户端尝试用旧版本更新（版本 0，冲突）
        conflict_event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_updated",
            change_data={"node_id": "node_1", "changes": {"config": {"url": "b"}}},
            client_id="client_3",
            version=0,  # 旧版本
        )

        # 验证冲突
        result = await sync_service.handle_change(conflict_event)
        assert result.conflict is True
        assert result.current_version > 0

    @pytest.mark.asyncio
    async def test_no_conflict_with_correct_version(self, sync_service, event_bus):
        """测试：正确版本号不产生冲突"""
        from src.domain.services.bidirectional_sync import CanvasChangeEvent

        # 添加节点
        add_event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_added",
            change_data={"node_id": "node_1", "node_type": "HTTP"},
            client_id="client_1",
            version=0,
        )
        await event_bus.publish(add_event)

        # 获取当前版本
        state = sync_service.get_canvas_state("wf_123")
        current_version = state.version

        # 用正确版本更新
        update_event = CanvasChangeEvent(
            source="canvas",
            workflow_id="wf_123",
            change_type="node_updated",
            change_data={"node_id": "node_1", "changes": {"config": {"url": "new"}}},
            client_id="client_1",
            version=current_version,
        )

        result = await sync_service.handle_change(update_event)
        assert result.success is True
        assert result.conflict is False


class TestRealWorldCanvasToConversationScenario:
    """真实场景测试：画布→对话同步"""

    @pytest.fixture
    def event_bus(self):
        from src.domain.services.event_bus import EventBus

        return EventBus()

    @pytest.mark.asyncio
    async def test_user_manual_edit_syncs_to_conversation(self, event_bus):
        """测试：用户手动编辑画布同步到对话上下文

        真实场景：
        1. 用户在画布上拖拽创建节点
        2. 前端发送 CanvasChangeEvent
        3. BidirectionalSyncService 处理变更
        4. ConversationAgent.SessionContext 更新
        5. 下次推理时 ConversationAgent 能访问新节点

        这是阶段 3 的完整验收场景！
        """
        from src.domain.services.bidirectional_sync import (
            BidirectionalSyncService,
            CanvasChangeEvent,
        )

        # 1. 创建服务和模拟的 ConversationAgent
        sync_service = BidirectionalSyncService(event_bus=event_bus)

        mock_agent = MagicMock()
        mock_agent.session_context = MagicMock()
        mock_agent.session_context.canvas_state = {}
        sync_service.register_conversation_agent("wf_123", mock_agent)

        # 2. 模拟用户在画布上创建 3 个节点
        nodes_to_create = [
            {"node_id": "start_node", "node_type": "START", "position": {"x": 100, "y": 50}},
            {
                "node_id": "llm_node",
                "node_type": "LLM",
                "position": {"x": 100, "y": 150},
                "config": {"model": "gpt-4", "user_prompt": "分析数据"},
            },
            {"node_id": "end_node", "node_type": "END", "position": {"x": 100, "y": 250}},
        ]

        for node_data in nodes_to_create:
            event = CanvasChangeEvent(
                source="canvas",
                workflow_id="wf_123",
                change_type="node_added",
                change_data=node_data,
                client_id="frontend_client",
            )
            await event_bus.publish(event)

        # 3. 模拟用户连接节点
        edges_to_create = [
            {"edge_id": "edge_1", "source_id": "start_node", "target_id": "llm_node"},
            {"edge_id": "edge_2", "source_id": "llm_node", "target_id": "end_node"},
        ]

        for edge_data in edges_to_create:
            event = CanvasChangeEvent(
                source="canvas",
                workflow_id="wf_123",
                change_type="edge_added",
                change_data=edge_data,
                client_id="frontend_client",
            )
            await event_bus.publish(event)

        # 4. 验证画布状态
        state = sync_service.get_canvas_state("wf_123")
        assert len(state.nodes) == 3
        assert len(state.edges) == 2
        assert "llm_node" in state.nodes
        assert state.nodes["llm_node"]["config"]["model"] == "gpt-4"

        # 5. 验证 ConversationAgent 上下文已更新
        canvas_state = mock_agent.session_context.canvas_state
        assert "nodes" in canvas_state
        assert len(canvas_state["nodes"]) == 3
        assert "edges" in canvas_state
        assert len(canvas_state["edges"]) == 2

        # 6. 模拟 ConversationAgent 推理时访问画布状态
        # （在真实实现中，这会通过 get_context_for_reasoning() 返回）
        reasoning_context = {
            "canvas_state": canvas_state,
            "message": "用户请求执行工作流",
        }

        # ConversationAgent 应该能看到所有节点
        assert "llm_node" in reasoning_context["canvas_state"]["nodes"]
        assert reasoning_context["canvas_state"]["nodes"]["llm_node"]["node_type"] == "LLM"

        print("✅ 验收通过：用户在画布新增节点后，对话 Agent 上下文能获取该节点")
