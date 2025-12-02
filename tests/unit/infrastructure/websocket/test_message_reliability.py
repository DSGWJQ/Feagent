"""消息可靠性测试

TDD 驱动：验证 message_id 和 ACK 机制

测试场景：
1. 消息自动添加 message_id
2. 发送消息后等待 ACK
3. ACK 超时后重试
4. 达到最大重试次数后标记失败
5. 收到 ACK 后确认消息已送达
6. 消息去重（幂等性）
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.websocket.canvas_sync import (
    CanvasSyncService,
    MessageAckHandler,
    ReliableMessage,
)


class TestReliableMessage:
    """ReliableMessage 数据类测试"""

    def test_message_has_unique_id(self):
        """测试：每条消息应有唯一 ID"""
        msg1 = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={"node_id": "node_1"},
        )
        msg2 = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={"node_id": "node_1"},
        )

        assert msg1.message_id is not None
        assert msg2.message_id is not None
        assert msg1.message_id != msg2.message_id

    def test_message_tracks_retry_count(self):
        """测试：消息应跟踪重试次数"""
        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={},
        )

        assert msg.retry_count == 0

        msg.retry_count += 1
        assert msg.retry_count == 1

    def test_message_tracks_creation_time(self):
        """测试：消息应记录创建时间"""
        before = datetime.now()
        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={},
        )
        after = datetime.now()

        assert msg.created_at >= before
        assert msg.created_at <= after

    def test_message_to_dict_includes_message_id(self):
        """测试：消息转 dict 应包含 message_id"""
        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={"node_id": "node_1"},
        )

        result = msg.to_dict()

        assert "message_id" in result
        assert result["message_id"] == msg.message_id
        assert result["type"] == "node_created"
        assert result["workflow_id"] == "wf_123"
        assert result["node_id"] == "node_1"

    def test_message_is_expired(self):
        """测试：检查消息是否过期"""
        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={},
            max_retries=3,
        )

        assert msg.is_expired() is False

        msg.retry_count = 3
        assert msg.is_expired() is True


class TestMessageAckHandler:
    """MessageAckHandler 测试"""

    def setup_method(self):
        """设置测试环境"""
        self.handler = MessageAckHandler(ack_timeout=0.1, max_retries=3)

    def test_register_pending_message(self):
        """测试：注册待确认消息"""
        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={},
        )

        self.handler.register_message(msg)

        assert msg.message_id in self.handler.pending_messages
        assert self.handler.pending_messages[msg.message_id] == msg

    def test_acknowledge_message(self):
        """测试：确认消息后从待确认列表移除"""
        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={},
        )

        self.handler.register_message(msg)
        assert msg.message_id in self.handler.pending_messages

        result = self.handler.acknowledge(msg.message_id)

        assert result is True
        assert msg.message_id not in self.handler.pending_messages

    def test_acknowledge_unknown_message_returns_false(self):
        """测试：确认未知消息返回 False"""
        result = self.handler.acknowledge("unknown_id")

        assert result is False

    def test_get_pending_messages_for_workflow(self):
        """测试：获取指定工作流的待确认消息"""
        msg1 = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={},
        )
        msg2 = ReliableMessage(
            type="node_created",
            workflow_id="wf_456",
            data={},
        )
        msg3 = ReliableMessage(
            type="node_updated",
            workflow_id="wf_123",
            data={},
        )

        self.handler.register_message(msg1)
        self.handler.register_message(msg2)
        self.handler.register_message(msg3)

        wf123_messages = self.handler.get_pending_messages("wf_123")

        assert len(wf123_messages) == 2
        message_ids = [m.message_id for m in wf123_messages]
        assert msg1.message_id in message_ids
        assert msg3.message_id in message_ids

    @pytest.mark.asyncio
    async def test_retry_expired_messages(self):
        """测试：重试超时消息"""
        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={},
        )
        self.handler.register_message(msg)

        # 等待超时
        await asyncio.sleep(0.15)

        retry_callback = AsyncMock()
        await self.handler.check_and_retry(retry_callback)

        assert msg.retry_count == 1
        retry_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_message_after_max_retries(self):
        """测试：达到最大重试次数后移除消息"""
        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={},
            max_retries=2,
        )
        msg.retry_count = 2  # 已达到最大重试
        # 设置过去的创建时间以确保超时检测触发
        msg.created_at = datetime.now() - timedelta(seconds=1)

        self.handler.register_message(msg)

        retry_callback = AsyncMock()
        failure_callback = MagicMock()

        await self.handler.check_and_retry(retry_callback, failure_callback)

        # 不应重试
        retry_callback.assert_not_called()
        # 应调用失败回调
        failure_callback.assert_called_once_with(msg)
        # 应从待确认列表移除
        assert msg.message_id not in self.handler.pending_messages


class TestCanvasSyncServiceReliability:
    """CanvasSyncService 消息可靠性测试"""

    def setup_method(self):
        """设置测试环境"""
        self.service = CanvasSyncService()

    @pytest.mark.asyncio
    async def test_broadcast_includes_message_id(self):
        """测试：广播消息应包含 message_id"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        await self.service.connection_manager.connect(
            mock_websocket, "wf_123", send_initial_state=False
        )

        await self.service.sync_node_created(
            workflow_id="wf_123",
            node_id="node_1",
            node_type="llm",
        )

        # 验证发送的消息包含 message_id
        call_args = mock_websocket.send_json.call_args[0][0]
        assert "message_id" in call_args

    @pytest.mark.asyncio
    async def test_handle_ack_message(self):
        """测试：处理 ACK 消息"""
        # 创建消息并注册
        msg = ReliableMessage(
            type="node_created",
            workflow_id="wf_123",
            data={"node_id": "node_1"},
        )
        self.service.ack_handler.register_message(msg)

        # 处理 ACK
        ack_data = {
            "type": "ack",
            "message_id": msg.message_id,
        }

        result = await self.service.handle_client_message("wf_123", ack_data)

        # 消息应被确认
        assert msg.message_id not in self.service.ack_handler.pending_messages
        assert result is True

    @pytest.mark.asyncio
    async def test_deduplicate_messages(self):
        """测试：消息去重（幂等性）"""
        msg_id = "test_msg_123"

        # 第一次接收
        result1 = self.service.check_and_record_message(msg_id)
        assert result1 is True  # 新消息

        # 第二次接收（重复）
        result2 = self.service.check_and_record_message(msg_id)
        assert result2 is False  # 重复消息

    @pytest.mark.asyncio
    async def test_client_sends_ack_on_receive(self):
        """测试：客户端收到消息后应发送 ACK"""
        # Mock WebSocket
        mock_websocket = AsyncMock()
        await self.service.connection_manager.connect(
            mock_websocket, "wf_123", send_initial_state=False
        )

        # 模拟接收带 message_id 的消息
        incoming_message = {
            "type": "node_created",
            "message_id": "msg_123",
            "workflow_id": "wf_123",
            "node_id": "node_1",
        }

        # 处理消息应触发 ACK
        await self.service.process_incoming_message("wf_123", incoming_message, mock_websocket)

        # 验证发送了 ACK
        ack_calls = [
            call
            for call in mock_websocket.send_json.call_args_list
            if call[0][0].get("type") == "ack"
        ]
        assert len(ack_calls) == 1
        assert ack_calls[0][0][0]["message_id"] == "msg_123"


class TestMessageIdempotency:
    """消息幂等性测试"""

    def setup_method(self):
        """设置测试环境"""
        self.service = CanvasSyncService()

    def test_received_message_ids_are_tracked(self):
        """测试：已接收的消息 ID 被跟踪"""
        msg_id = "msg_test_123"

        self.service.check_and_record_message(msg_id)

        assert msg_id in self.service.received_message_ids

    def test_old_message_ids_are_cleaned_up(self):
        """测试：旧的消息 ID 被清理"""
        # 添加足够多的消息 ID 触发清理
        for i in range(1100):
            self.service.check_and_record_message(f"msg_{i}")

        # 最早的消息 ID 应被清理
        # 默认保留 1000 条
        assert len(self.service.received_message_ids) <= 1000
