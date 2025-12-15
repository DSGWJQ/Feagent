"""Unit tests for src.domain.agents.agent_channel (P3-Task6).

测试范围：
- AgentWebSocketChannel: 会话管理、消息发送、广播
- AgentMessage: 序列化、反序列化、默认值
- AgentChannelBridge: 消息分发逻辑
- AgentMessageHandler: 消息处理器调度

覆盖目标: 0% → 80%+
测试数量: ~23 tests
"""

from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

import src.domain.agents.agent_channel as agent_channel


@pytest.fixture
def fixed_dt() -> datetime:
    """固定时间戳用于确定性测试"""
    return datetime(2024, 1, 2, 3, 4, 5)


@pytest.fixture
def fixed_uuid() -> UUID:
    """固定UUID用于确定性测试"""
    return UUID("12345678-1234-5678-1234-567812345678")


# 移除 patch_datetime_now fixture，采用更实用的测试策略


# ==================== TestAgentMessage ====================


class TestAgentMessage:
    """测试 AgentMessage 消息结构"""

    def test_to_dict_serializes_expected_fields(self, fixed_dt: datetime):
        """to_dict() 应正确序列化所有字段"""
        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.PLAN_PROPOSED,
            session_id="s1",
            payload={"k": "v"},
            message_id="msg_001",
            timestamp=fixed_dt,
        )

        data = msg.to_dict()
        assert data == {
            "type": "plan_proposed",
            "session_id": "s1",
            "payload": {"k": "v"},
            "message_id": "msg_001",
            "timestamp": fixed_dt.isoformat(),
        }

    def test_message_creation_defaults_message_id_and_timestamp(
        self,
        fixed_uuid: UUID,
    ):
        """消息创建时应自动生成 message_id 和 timestamp"""
        before = datetime.now()

        with patch.object(agent_channel, "uuid4", return_value=fixed_uuid):
            msg = agent_channel.AgentMessage(
                type=agent_channel.AgentMessageType.TASK_REQUEST,
                session_id="s1",
            )

        after = datetime.now()

        assert msg.payload == {}
        assert msg.message_id == "msg_123456781234"
        # 验证 timestamp 是合理的当前时间
        assert isinstance(msg.timestamp, datetime)
        assert before <= msg.timestamp <= after

    def test_from_dict_parses_valid_type(self):
        """from_dict() 应正确解析有效的消息类型"""
        before = datetime.now()
        msg = agent_channel.AgentMessage.from_dict(
            {
                "type": "task_request",
                "session_id": "s1",
                "payload": {"q": "hi"},
                "message_id": "msg_abc",
            }
        )
        after = datetime.now()

        assert msg.type == agent_channel.AgentMessageType.TASK_REQUEST
        assert msg.session_id == "s1"
        assert msg.payload == {"q": "hi"}
        assert msg.message_id == "msg_abc"
        # 验证 timestamp 自动生成
        assert isinstance(msg.timestamp, datetime)
        assert before <= msg.timestamp <= after

    def test_from_dict_invalid_type_coerces_to_error(self):
        """from_dict() 对无效消息类型应转换为 ERROR"""
        before = datetime.now()
        msg = agent_channel.AgentMessage.from_dict(
            {"type": "not-a-real-type", "session_id": "s1", "payload": {"x": 1}}
        )
        after = datetime.now()

        assert msg.type == agent_channel.AgentMessageType.ERROR
        assert msg.session_id == "s1"
        assert msg.payload == {"x": 1}
        # 验证 timestamp 自动生成
        assert isinstance(msg.timestamp, datetime)
        assert before <= msg.timestamp <= after


# ==================== TestAgentWebSocketChannel ====================


class TestAgentWebSocketChannel:
    """测试 AgentWebSocketChannel 会话管理"""

    @pytest.mark.asyncio
    async def test_register_session_success_stores_session(self, fixed_dt: datetime):
        """register_session() 应成功存储会话信息"""
        channel = agent_channel.AgentWebSocketChannel()
        ws = AsyncMock()

        with patch.object(agent_channel, "datetime") as dt:
            dt.now.return_value = fixed_dt
            await channel.register_session("s1", ws, "u1")

        assert channel.active_sessions["s1"]["websocket"] is ws
        assert channel.active_sessions["s1"]["user_id"] == "u1"
        assert channel.active_sessions["s1"]["connected_at"] == fixed_dt

    @pytest.mark.asyncio
    async def test_unregister_session_cleans_up_and_is_idempotent(self):
        """unregister_session() 应清理会话并支持幂等调用"""
        channel = agent_channel.AgentWebSocketChannel()
        ws = AsyncMock()

        await channel.register_session("s1", ws, "u1")
        await channel.unregister_session("s1")
        await channel.unregister_session("s1")  # 第二次调用应安全

        assert "s1" not in channel.active_sessions

    @pytest.mark.asyncio
    async def test_send_to_session_success_sends_json(self, fixed_dt: datetime):
        """send_to_session() 成功时应发送 JSON 消息"""
        channel = agent_channel.AgentWebSocketChannel()
        ws = AsyncMock()
        await channel.register_session("s1", ws, "u1")

        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.HEARTBEAT,
            session_id="s1",
            payload={"ok": True},
            message_id="msg_001",
            timestamp=fixed_dt,
        )

        ok = await channel.send_to_session("s1", msg)
        assert ok is True
        ws.send_json.assert_awaited_once_with(msg.to_dict())

    @pytest.mark.asyncio
    async def test_send_to_session_session_not_found_returns_false(self):
        """send_to_session() 会话不存在时应返回 False"""
        channel = agent_channel.AgentWebSocketChannel()
        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.HEARTBEAT,
            session_id="missing",
            message_id="msg_001",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
        )

        ok = await channel.send_to_session("missing", msg)
        assert ok is False

    @pytest.mark.asyncio
    async def test_send_to_session_websocket_send_failure_returns_false(self):
        """send_to_session() WebSocket 发送失败时应返回 False"""
        channel = agent_channel.AgentWebSocketChannel()
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("send failed")
        await channel.register_session("s1", ws, "u1")

        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.HEARTBEAT,
            session_id="s1",
            message_id="msg_001",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
        )

        ok = await channel.send_to_session("s1", msg)
        assert ok is False

    @pytest.mark.asyncio
    async def test_broadcast_empty_sessions_returns_zero(self):
        """broadcast() 无会话时应返回 0"""
        channel = agent_channel.AgentWebSocketChannel()
        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.HEARTBEAT,
            session_id="irrelevant",
            message_id="msg_001",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
        )

        sent = await channel.broadcast(msg)
        assert sent == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_sessions(self, fixed_dt: datetime):
        """broadcast() 应发送消息到所有会话"""
        channel = agent_channel.AgentWebSocketChannel()
        ws1, ws2 = AsyncMock(), AsyncMock()
        await channel.register_session("s1", ws1, "u1")
        await channel.register_session("s2", ws2, "u2")

        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.HEARTBEAT,
            session_id="server",
            message_id="msg_001",
            timestamp=fixed_dt,
        )

        sent = await channel.broadcast(msg)
        assert sent == 2
        ws1.send_json.assert_awaited_once_with(msg.to_dict())
        ws2.send_json.assert_awaited_once_with(msg.to_dict())

    @pytest.mark.asyncio
    async def test_broadcast_continues_on_send_failure_counts_successes(self, fixed_dt: datetime):
        """broadcast() 部分发送失败时应继续并统计成功数"""
        channel = agent_channel.AgentWebSocketChannel()
        ws_bad, ws_ok = AsyncMock(), AsyncMock()
        ws_bad.send_json.side_effect = RuntimeError("boom")
        await channel.register_session("bad", ws_bad, "u1")
        await channel.register_session("ok", ws_ok, "u2")

        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.HEARTBEAT,
            session_id="server",
            message_id="msg_001",
            timestamp=fixed_dt,
        )

        sent = await channel.broadcast(msg)
        assert sent == 1
        ws_ok.send_json.assert_awaited_once_with(msg.to_dict())

    @pytest.mark.asyncio
    async def test_broadcast_excludes_session_does_not_send_and_decrements_count(
        self, fixed_dt: datetime
    ):
        """broadcast(exclude_session=...) 应跳过被排除会话并正确统计"""
        channel = agent_channel.AgentWebSocketChannel()
        ws1, ws2 = AsyncMock(), AsyncMock()
        await channel.register_session("s1", ws1, "u1")
        await channel.register_session("s2", ws2, "u2")

        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.HEARTBEAT,
            session_id="server",
            message_id="msg_001",
            timestamp=fixed_dt,
        )

        sent = await channel.broadcast(msg, exclude_session="s1")
        assert sent == 1
        ws1.send_json.assert_not_called()
        ws2.send_json.assert_awaited_once_with(msg.to_dict())

    def test_get_session_returns_session_or_none(self):
        """get_session() 应返回会话信息或 None"""
        channel = agent_channel.AgentWebSocketChannel()
        channel._sessions["s1"] = {
            "websocket": object(),
            "user_id": "u1",
            "connected_at": "t",
        }

        assert channel.get_session("s1") == channel.active_sessions["s1"]
        assert channel.get_session("missing") is None


# ==================== TestAgentChannelBridge ====================


class TestAgentChannelBridge:
    """测试 AgentChannelBridge 消息分发"""

    @pytest.mark.asyncio
    async def test_dispatch_plan_to_workflow_returns_message_without_sending(self):
        """dispatch_plan_to_workflow() 应返回消息但不发送"""
        channel = AsyncMock(spec=agent_channel.AgentWebSocketChannel)
        bridge = agent_channel.AgentChannelBridge(channel=channel)

        plan = {"nodes": [{"id": "n1"}]}
        msg = await bridge.dispatch_plan_to_workflow("s1", plan)

        assert msg.type == agent_channel.AgentMessageType.WORKFLOW_DISPATCH
        assert msg.session_id == "s1"
        assert msg.payload == plan
        channel.send_to_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_plan_proposed_sends_expected_message(self):
        """notify_plan_proposed() 应发送正确的计划提议消息"""
        channel = AsyncMock(spec=agent_channel.AgentWebSocketChannel)
        channel.send_to_session = AsyncMock(return_value=True)
        bridge = agent_channel.AgentChannelBridge(channel=channel)

        await bridge.notify_plan_proposed("s1", plan_summary="sum", estimated_steps=3)

        channel.send_to_session.assert_awaited_once()
        session_id, msg = channel.send_to_session.call_args.args
        assert session_id == "s1"
        assert msg.type == agent_channel.AgentMessageType.PLAN_PROPOSED
        assert msg.payload == {"summary": "sum", "estimated_steps": 3}

    @pytest.mark.asyncio
    async def test_notify_execution_started_sends_expected_message(self):
        """notify_execution_started() 应发送正确的执行开始消息"""
        channel = AsyncMock(spec=agent_channel.AgentWebSocketChannel)
        channel.send_to_session = AsyncMock(return_value=True)
        bridge = agent_channel.AgentChannelBridge(channel=channel)

        await bridge.notify_execution_started("s1", "wf1")

        session_id, msg = channel.send_to_session.call_args.args
        assert session_id == "s1"
        assert msg.type == agent_channel.AgentMessageType.EXECUTION_STARTED
        assert msg.payload == {"workflow_id": "wf1"}

    @pytest.mark.asyncio
    async def test_report_progress_sends_expected_message(self):
        """report_progress() 应发送正确的进度消息"""
        channel = AsyncMock(spec=agent_channel.AgentWebSocketChannel)
        channel.send_to_session = AsyncMock(return_value=True)
        bridge = agent_channel.AgentChannelBridge(channel=channel)

        await bridge.report_progress(
            session_id="s1",
            workflow_id="wf1",
            current_node="n1",
            progress=0.5,
            message="half",
        )

        session_id, msg = channel.send_to_session.call_args.args
        assert session_id == "s1"
        assert msg.type == agent_channel.AgentMessageType.EXECUTION_PROGRESS
        assert msg.payload["workflow_id"] == "wf1"
        assert msg.payload["current_node"] == "n1"
        assert msg.payload["progress"] == 0.5
        assert msg.payload["message"] == "half"

    @pytest.mark.asyncio
    async def test_report_failed_sends_expected_message(self):
        """report_failed() 应发送正确的失败消息"""
        channel = AsyncMock(spec=agent_channel.AgentWebSocketChannel)
        channel.send_to_session = AsyncMock(return_value=True)
        bridge = agent_channel.AgentChannelBridge(channel=channel)

        await bridge.report_failed("s1", "wf1", error="nope", failed_node="n9")

        session_id, msg = channel.send_to_session.call_args.args
        assert session_id == "s1"
        assert msg.type == agent_channel.AgentMessageType.EXECUTION_FAILED
        assert msg.payload == {
            "workflow_id": "wf1",
            "error": "nope",
            "failed_node": "n9",
        }

    @pytest.mark.asyncio
    async def test_report_completed_sends_expected_message(self):
        """report_completed() 应发送正确的完成消息"""
        channel = AsyncMock(spec=agent_channel.AgentWebSocketChannel)
        channel.send_to_session = AsyncMock(return_value=True)
        bridge = agent_channel.AgentChannelBridge(channel=channel)

        result = {"ok": True}
        await bridge.report_completed("s1", "wf1", result=result)

        session_id, msg = channel.send_to_session.call_args.args
        assert session_id == "s1"
        assert msg.type == agent_channel.AgentMessageType.EXECUTION_COMPLETED
        assert msg.payload == {"workflow_id": "wf1", "result": result}

    @pytest.mark.asyncio
    async def test_push_execution_summary_prefers_to_dict(self):
        """push_execution_summary() 优先使用对象的 to_dict() 方法"""
        channel = AsyncMock(spec=agent_channel.AgentWebSocketChannel)
        channel.send_to_session = AsyncMock(return_value=True)
        bridge = agent_channel.AgentChannelBridge(channel=channel)

        summary = SimpleNamespace(to_dict=lambda: {"workflow_id": "wf1", "success": True})
        await bridge.push_execution_summary("s1", summary)

        _, msg = channel.send_to_session.call_args.args
        assert msg.type == agent_channel.AgentMessageType.EXECUTION_SUMMARY
        assert msg.payload == {"workflow_id": "wf1", "success": True}

    @pytest.mark.asyncio
    async def test_push_execution_summary_falls_back_to_attributes(self):
        """push_execution_summary() 无 to_dict() 时应回退到属性访问"""
        channel = AsyncMock(spec=agent_channel.AgentWebSocketChannel)
        channel.send_to_session = AsyncMock(return_value=True)
        bridge = agent_channel.AgentChannelBridge(channel=channel)

        summary = SimpleNamespace(workflow_id="wf2", session_id="s1", success=False)
        await bridge.push_execution_summary("s1", summary)

        _, msg = channel.send_to_session.call_args.args
        assert msg.type == agent_channel.AgentMessageType.EXECUTION_SUMMARY
        assert msg.payload == {
            "workflow_id": "wf2",
            "session_id": "s1",
            "success": False,
        }


# ==================== TestAgentMessageHandler ====================


class TestAgentMessageHandler:
    """测试 AgentMessageHandler 消息处理器调度"""

    @pytest.mark.asyncio
    async def test_handle_task_request_without_handler_returns_no_handler(self):
        """handle_message() 无处理器时应返回 no_handler"""
        channel = agent_channel.AgentWebSocketChannel()
        handler = agent_channel.AgentMessageHandler(channel=channel)

        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.TASK_REQUEST,
            session_id="s1",
            payload={"q": "hi"},
            message_id="msg_001",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
        )

        result = await handler.handle_message(msg)
        assert result == {"status": "no_handler"}

    @pytest.mark.asyncio
    async def test_handle_cancel_task_and_plan_approved_dispatch_to_callbacks(self):
        """handle_message() 应正确调度 CANCEL_TASK 和 PLAN_APPROVED"""
        channel = agent_channel.AgentWebSocketChannel()
        handler = agent_channel.AgentMessageHandler(channel=channel)

        on_cancel = AsyncMock()
        on_approved = AsyncMock()
        handler.on_cancel_task = on_cancel
        handler.on_plan_approved = on_approved

        cancel_msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.CANCEL_TASK,
            session_id="s1",
            payload={},
            message_id="msg_001",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
        )
        approved_msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.PLAN_APPROVED,
            session_id="s1",
            payload={"plan_id": "p1"},
            message_id="msg_002",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
        )

        assert await handler.handle_message(cancel_msg) is None
        assert await handler.handle_message(approved_msg) is None
        on_cancel.assert_awaited_once_with("s1", "")
        on_approved.assert_awaited_once_with("s1", "p1")

    @pytest.mark.asyncio
    async def test_handle_message_callback_exception_returns_error_dict(self):
        """handle_message() 回调异常时应返回错误字典"""
        channel = agent_channel.AgentWebSocketChannel()
        handler = agent_channel.AgentMessageHandler(channel=channel)

        async def boom(*_args, **_kwargs):
            raise RuntimeError("handler failed")

        handler.on_task_request = boom

        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.TASK_REQUEST,
            session_id="s1",
            payload={"q": "hi"},
            message_id="msg_001",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
        )

        result = await handler.handle_message(msg)
        assert result == {"error": "handler failed"}

    @pytest.mark.asyncio
    async def test_handle_message_unhandled_type_logs_warning_and_returns_none(self, caplog):
        """handle_message() 遇到未处理类型应记录 warning 并返回 None"""
        channel = agent_channel.AgentWebSocketChannel()
        handler = agent_channel.AgentMessageHandler(channel=channel)

        msg = agent_channel.AgentMessage(
            type=agent_channel.AgentMessageType.HEARTBEAT,
            session_id="s1",
            payload={},
            message_id="msg_001",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
        )

        caplog.set_level(logging.WARNING, logger=agent_channel.__name__)
        result = await handler.handle_message(msg)

        assert result is None
        assert any("Unhandled message type" in r.message for r in caplog.records)
