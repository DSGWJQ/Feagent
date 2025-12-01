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
