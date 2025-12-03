"""Agent WebSocket 通信信道单元测试 - Phase 4

测试目标：
1. Agent 消息协议定义
2. AgentWebSocketChannel 消息处理
3. ConversationAgent → WorkflowAgent 计划推送
4. WorkflowAgent → ConversationAgent 结果反馈
5. 客户端消息订阅

运行命令：
    pytest tests/unit/interfaces/test_agent_websocket_channel.py -v --tb=short
"""

from unittest.mock import AsyncMock

import pytest

# === 测试：Agent 消息类型 ===


class TestAgentMessageType:
    """Agent 消息类型测试"""

    def test_message_type_enum_has_required_types(self):
        """测试：消息类型枚举包含必需的类型"""
        from src.domain.agents.agent_channel import AgentMessageType

        # 客户端 → 服务器
        assert AgentMessageType.TASK_REQUEST  # 任务请求
        assert AgentMessageType.CANCEL_TASK  # 取消任务

        # 服务器 → 客户端
        assert AgentMessageType.PLAN_PROPOSED  # 计划提议
        assert AgentMessageType.PLAN_APPROVED  # 计划批准
        assert AgentMessageType.EXECUTION_STARTED  # 执行开始
        assert AgentMessageType.EXECUTION_PROGRESS  # 执行进度
        assert AgentMessageType.EXECUTION_COMPLETED  # 执行完成
        assert AgentMessageType.EXECUTION_FAILED  # 执行失败

        # Agent 间通信
        assert AgentMessageType.WORKFLOW_DISPATCH  # 工作流分发
        assert AgentMessageType.WORKFLOW_RESULT  # 工作流结果


class TestAgentMessage:
    """Agent 消息结构测试"""

    def test_message_has_required_fields(self):
        """测试：消息有必需字段"""
        from src.domain.agents.agent_channel import AgentMessage, AgentMessageType

        msg = AgentMessage(
            type=AgentMessageType.TASK_REQUEST,
            session_id="session_123",
            payload={"task": "分析数据"},
        )

        assert msg.type == AgentMessageType.TASK_REQUEST
        assert msg.session_id == "session_123"
        assert msg.payload == {"task": "分析数据"}
        assert msg.message_id is not None
        assert msg.timestamp is not None

    def test_message_to_dict(self):
        """测试：消息可序列化为字典"""
        from src.domain.agents.agent_channel import AgentMessage, AgentMessageType

        msg = AgentMessage(
            type=AgentMessageType.PLAN_PROPOSED,
            session_id="session_456",
            payload={"plan": [{"step": 1}]},
        )

        data = msg.to_dict()

        assert data["type"] == "plan_proposed"
        assert data["session_id"] == "session_456"
        assert data["payload"]["plan"] == [{"step": 1}]
        assert "message_id" in data
        assert "timestamp" in data

    def test_message_from_dict(self):
        """测试：可从字典创建消息"""
        from src.domain.agents.agent_channel import AgentMessage, AgentMessageType

        data = {
            "type": "task_request",
            "session_id": "session_789",
            "payload": {"query": "帮我分析"},
            "message_id": "msg_001",
        }

        msg = AgentMessage.from_dict(data)

        assert msg.type == AgentMessageType.TASK_REQUEST
        assert msg.session_id == "session_789"
        assert msg.payload["query"] == "帮我分析"


# === 测试：AgentWebSocketChannel ===


class TestAgentWebSocketChannel:
    """Agent WebSocket 信道测试"""

    def test_channel_creation(self):
        """测试：信道创建"""
        from src.domain.agents.agent_channel import AgentWebSocketChannel

        channel = AgentWebSocketChannel()

        assert channel is not None
        assert channel.active_sessions == {}

    @pytest.mark.asyncio
    async def test_register_session(self):
        """测试：注册会话"""
        from src.domain.agents.agent_channel import AgentWebSocketChannel

        channel = AgentWebSocketChannel()
        mock_ws = AsyncMock()

        await channel.register_session(
            session_id="session_1",
            websocket=mock_ws,
            user_id="user_123",
        )

        assert "session_1" in channel.active_sessions
        assert channel.active_sessions["session_1"]["user_id"] == "user_123"

    @pytest.mark.asyncio
    async def test_unregister_session(self):
        """测试：注销会话"""
        from src.domain.agents.agent_channel import AgentWebSocketChannel

        channel = AgentWebSocketChannel()
        mock_ws = AsyncMock()

        await channel.register_session("session_1", mock_ws, "user_1")
        await channel.unregister_session("session_1")

        assert "session_1" not in channel.active_sessions

    @pytest.mark.asyncio
    async def test_send_to_session(self):
        """测试：向会话发送消息"""
        from src.domain.agents.agent_channel import (
            AgentMessage,
            AgentMessageType,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        mock_ws = AsyncMock()

        await channel.register_session("session_1", mock_ws, "user_1")

        msg = AgentMessage(
            type=AgentMessageType.PLAN_PROPOSED,
            session_id="session_1",
            payload={"plan": "test"},
        )

        await channel.send_to_session("session_1", msg)

        mock_ws.send_json.assert_called_once()
        sent_data = mock_ws.send_json.call_args[0][0]
        assert sent_data["type"] == "plan_proposed"

    @pytest.mark.asyncio
    async def test_broadcast_to_all_sessions(self):
        """测试：广播消息到所有会话"""
        from src.domain.agents.agent_channel import (
            AgentMessage,
            AgentMessageType,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()

        await channel.register_session("session_1", mock_ws1, "user_1")
        await channel.register_session("session_2", mock_ws2, "user_2")

        msg = AgentMessage(
            type=AgentMessageType.EXECUTION_STARTED,
            session_id="broadcast",
            payload={},
        )

        await channel.broadcast(msg)

        assert mock_ws1.send_json.called
        assert mock_ws2.send_json.called


# === 测试：ConversationAgent → WorkflowAgent 推送 ===


class TestPlanDispatch:
    """计划分发测试"""

    @pytest.mark.asyncio
    async def test_dispatch_plan_to_workflow_agent(self):
        """测试：向 WorkflowAgent 分发计划"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentMessageType,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)

        plan = {
            "workflow_id": "wf_123",
            "nodes": [
                {"id": "node_1", "type": "llm", "config": {}},
                {"id": "node_2", "type": "http", "config": {}},
            ],
            "edges": [{"source": "node_1", "target": "node_2"}],
        }

        msg = await bridge.dispatch_plan_to_workflow(
            session_id="session_1",
            plan=plan,
        )

        assert msg.type == AgentMessageType.WORKFLOW_DISPATCH
        assert msg.payload["workflow_id"] == "wf_123"
        assert len(msg.payload["nodes"]) == 2

    @pytest.mark.asyncio
    async def test_notify_client_plan_proposed(self):
        """测试：通知客户端计划已提议"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        mock_ws = AsyncMock()
        await channel.register_session("session_1", mock_ws, "user_1")

        bridge = AgentChannelBridge(channel=channel)

        await bridge.notify_plan_proposed(
            session_id="session_1",
            plan_summary="分析销售数据并生成报告",
            estimated_steps=3,
        )

        mock_ws.send_json.assert_called_once()
        sent_data = mock_ws.send_json.call_args[0][0]
        assert sent_data["type"] == "plan_proposed"
        assert sent_data["payload"]["summary"] == "分析销售数据并生成报告"


# === 测试：WorkflowAgent → ConversationAgent 反馈 ===


class TestWorkflowFeedback:
    """工作流反馈测试"""

    @pytest.mark.asyncio
    async def test_report_execution_progress(self):
        """测试：报告执行进度"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        mock_ws = AsyncMock()
        await channel.register_session("session_1", mock_ws, "user_1")

        bridge = AgentChannelBridge(channel=channel)

        await bridge.report_progress(
            session_id="session_1",
            workflow_id="wf_123",
            current_node="node_2",
            progress=0.5,
            message="正在处理数据...",
        )

        mock_ws.send_json.assert_called()
        sent_data = mock_ws.send_json.call_args[0][0]
        assert sent_data["type"] == "execution_progress"
        assert sent_data["payload"]["progress"] == 0.5

    @pytest.mark.asyncio
    async def test_report_execution_completed(self):
        """测试：报告执行完成"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        mock_ws = AsyncMock()
        await channel.register_session("session_1", mock_ws, "user_1")

        bridge = AgentChannelBridge(channel=channel)

        await bridge.report_completed(
            session_id="session_1",
            workflow_id="wf_123",
            result={"summary": "分析完成", "data": [1, 2, 3]},
        )

        mock_ws.send_json.assert_called()
        sent_data = mock_ws.send_json.call_args[0][0]
        assert sent_data["type"] == "execution_completed"
        assert sent_data["payload"]["result"]["summary"] == "分析完成"

    @pytest.mark.asyncio
    async def test_report_execution_failed(self):
        """测试：报告执行失败"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        mock_ws = AsyncMock()
        await channel.register_session("session_1", mock_ws, "user_1")

        bridge = AgentChannelBridge(channel=channel)

        await bridge.report_failed(
            session_id="session_1",
            workflow_id="wf_123",
            error="连接数据库失败",
            failed_node="node_3",
        )

        mock_ws.send_json.assert_called()
        sent_data = mock_ws.send_json.call_args[0][0]
        assert sent_data["type"] == "execution_failed"
        assert "数据库" in sent_data["payload"]["error"]


# === 测试：端到端消息流 ===


class TestEndToEndMessageFlow:
    """端到端消息流测试"""

    @pytest.mark.asyncio
    async def test_full_task_lifecycle(self):
        """测试：完整任务生命周期"""
        from src.domain.agents.agent_channel import (
            AgentChannelBridge,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        mock_ws = AsyncMock()
        await channel.register_session("session_1", mock_ws, "user_1")

        bridge = AgentChannelBridge(channel=channel)

        received_messages = []

        def capture_message(data):
            received_messages.append(data)

        mock_ws.send_json.side_effect = capture_message

        # 1. 提议计划
        await bridge.notify_plan_proposed(
            session_id="session_1",
            plan_summary="分析数据",
            estimated_steps=2,
        )

        # 2. 开始执行
        await bridge.notify_execution_started(
            session_id="session_1",
            workflow_id="wf_123",
        )

        # 3. 进度更新
        await bridge.report_progress(
            session_id="session_1",
            workflow_id="wf_123",
            current_node="node_1",
            progress=0.5,
            message="处理中",
        )

        # 4. 完成
        await bridge.report_completed(
            session_id="session_1",
            workflow_id="wf_123",
            result={"success": True},
        )

        # 验证消息序列
        assert len(received_messages) == 4
        assert received_messages[0]["type"] == "plan_proposed"
        assert received_messages[1]["type"] == "execution_started"
        assert received_messages[2]["type"] == "execution_progress"
        assert received_messages[3]["type"] == "execution_completed"


# === 测试：消息处理器 ===


class TestMessageHandler:
    """消息处理器测试"""

    @pytest.mark.asyncio
    async def test_handle_task_request(self):
        """测试：处理任务请求"""
        from src.domain.agents.agent_channel import (
            AgentMessage,
            AgentMessageHandler,
            AgentMessageType,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        handler = AgentMessageHandler(channel=channel)

        # 注册任务处理回调
        task_received = []

        async def on_task_request(session_id: str, payload: dict):
            task_received.append((session_id, payload))
            return {"status": "accepted"}

        handler.on_task_request = on_task_request

        # 处理任务请求消息
        msg = AgentMessage(
            type=AgentMessageType.TASK_REQUEST,
            session_id="session_1",
            payload={"query": "帮我分析销售数据"},
        )

        result = await handler.handle_message(msg)

        assert len(task_received) == 1
        assert task_received[0][0] == "session_1"
        assert task_received[0][1]["query"] == "帮我分析销售数据"
        assert result["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_handle_cancel_task(self):
        """测试：处理取消任务"""
        from src.domain.agents.agent_channel import (
            AgentMessage,
            AgentMessageHandler,
            AgentMessageType,
            AgentWebSocketChannel,
        )

        channel = AgentWebSocketChannel()
        handler = AgentMessageHandler(channel=channel)

        cancelled = []

        async def on_cancel(session_id: str, task_id: str):
            cancelled.append(task_id)

        handler.on_cancel_task = on_cancel

        msg = AgentMessage(
            type=AgentMessageType.CANCEL_TASK,
            session_id="session_1",
            payload={"task_id": "task_123"},
        )

        await handler.handle_message(msg)

        assert "task_123" in cancelled


# 导出
__all__ = [
    "TestAgentMessageType",
    "TestAgentMessage",
    "TestAgentWebSocketChannel",
    "TestPlanDispatch",
    "TestWorkflowFeedback",
    "TestEndToEndMessageFlow",
    "TestMessageHandler",
]
