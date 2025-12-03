"""Agent WebSocket 端到端集成测试 - Phase 4

测试目标：
1. WebSocket 连接建立和断开
2. 客户端发送任务请求
3. 服务器推送计划提议
4. 工作流执行并反馈进度
5. 完整任务生命周期

运行命令：
    pytest tests/integration/test_agent_websocket_e2e.py -v -s
"""

import asyncio

import pytest

from src.domain.agents.agent_channel import (
    AgentChannelBridge,
    AgentMessage,
    AgentMessageHandler,
    AgentMessageType,
    AgentWebSocketChannel,
)

# === Mock WebSocket ===


class MockWebSocket:
    """模拟 WebSocket 连接"""

    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_messages: list[dict] = []
        self.receive_queue: asyncio.Queue = asyncio.Queue()

    async def accept(self):
        self.accepted = True

    async def close(self):
        self.closed = True

    async def send_json(self, data: dict):
        self.sent_messages.append(data)

    async def receive_json(self) -> dict:
        return await self.receive_queue.get()

    def put_message(self, data: dict):
        """模拟客户端发送消息"""
        self.receive_queue.put_nowait(data)


# === 集成测试 ===


class TestAgentWebSocketE2E:
    """Agent WebSocket 端到端测试"""

    @pytest.mark.asyncio
    async def test_client_connects_and_receives_ack(self):
        """测试：客户端连接并收到确认"""
        channel = AgentWebSocketChannel()
        ws = MockWebSocket()

        await channel.register_session(
            session_id="session_1",
            websocket=ws,
            user_id="user_123",
        )

        assert "session_1" in channel.active_sessions
        assert channel.active_sessions["session_1"]["user_id"] == "user_123"

    @pytest.mark.asyncio
    async def test_task_request_triggers_plan_proposal(self):
        """测试：任务请求触发计划提议"""
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)
        handler = AgentMessageHandler(channel=channel)

        ws = MockWebSocket()
        await channel.register_session("session_1", ws, "user_1")

        # 设置处理器
        async def on_task(session_id, payload):
            await bridge.notify_plan_proposed(
                session_id=session_id,
                plan_summary=f"处理: {payload.get('query')}",
                estimated_steps=3,
            )
            return {"status": "accepted"}

        handler.on_task_request = on_task

        # 发送任务请求
        msg = AgentMessage(
            type=AgentMessageType.TASK_REQUEST,
            session_id="session_1",
            payload={"query": "分析销售数据"},
        )

        await handler.handle_message(msg)

        # 验证收到计划提议
        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "plan_proposed"
        assert "分析销售数据" in ws.sent_messages[0]["payload"]["summary"]

    @pytest.mark.asyncio
    async def test_plan_approval_triggers_execution(self):
        """测试：计划批准触发执行"""
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)
        handler = AgentMessageHandler(channel=channel)

        ws = MockWebSocket()
        await channel.register_session("session_1", ws, "user_1")

        execution_started = []

        async def on_plan_approved(session_id, plan_id):
            execution_started.append(plan_id)
            await bridge.notify_execution_started(session_id, f"wf_{plan_id}")

        handler.on_plan_approved = on_plan_approved

        # 发送计划批准
        msg = AgentMessage(
            type=AgentMessageType.PLAN_APPROVED,
            session_id="session_1",
            payload={"plan_id": "plan_123"},
        )

        await handler.handle_message(msg)

        # 验证执行开始
        assert "plan_123" in execution_started
        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "execution_started"

    @pytest.mark.asyncio
    async def test_workflow_execution_reports_progress(self):
        """测试：工作流执行报告进度"""
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)

        ws = MockWebSocket()
        await channel.register_session("session_1", ws, "user_1")

        # 模拟工作流执行
        workflow_id = "wf_test"

        await bridge.notify_execution_started("session_1", workflow_id)

        for i in range(3):
            await bridge.report_progress(
                session_id="session_1",
                workflow_id=workflow_id,
                current_node=f"node_{i + 1}",
                progress=(i + 1) / 3,
                message=f"步骤 {i + 1}",
            )

        await bridge.report_completed(
            session_id="session_1",
            workflow_id=workflow_id,
            result={"data": "result"},
        )

        # 验证消息序列
        assert len(ws.sent_messages) == 5  # started + 3 progress + completed

        assert ws.sent_messages[0]["type"] == "execution_started"
        assert ws.sent_messages[1]["type"] == "execution_progress"
        assert ws.sent_messages[2]["type"] == "execution_progress"
        assert ws.sent_messages[3]["type"] == "execution_progress"
        assert ws.sent_messages[4]["type"] == "execution_completed"

        # 验证进度值
        assert ws.sent_messages[1]["payload"]["progress"] == pytest.approx(0.333, rel=0.01)
        assert ws.sent_messages[3]["payload"]["progress"] == 1.0

    @pytest.mark.asyncio
    async def test_workflow_failure_reports_error(self):
        """测试：工作流失败报告错误"""
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)

        ws = MockWebSocket()
        await channel.register_session("session_1", ws, "user_1")

        await bridge.notify_execution_started("session_1", "wf_fail")
        await bridge.report_progress("session_1", "wf_fail", "node_1", 0.5, "处理中")
        await bridge.report_failed(
            session_id="session_1",
            workflow_id="wf_fail",
            error="数据库连接超时",
            failed_node="node_2",
        )

        # 验证失败消息
        assert len(ws.sent_messages) == 3
        assert ws.sent_messages[2]["type"] == "execution_failed"
        assert "数据库" in ws.sent_messages[2]["payload"]["error"]
        assert ws.sent_messages[2]["payload"]["failed_node"] == "node_2"


class TestFullTaskLifecycleE2E:
    """完整任务生命周期端到端测试"""

    @pytest.mark.asyncio
    async def test_complete_task_flow(self):
        """测试：完整任务流程（请求 → 计划 → 批准 → 执行 → 完成）"""
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)
        handler = AgentMessageHandler(channel=channel)

        ws = MockWebSocket()
        await channel.register_session("session_1", ws, "user_1")

        # 设置处理器
        async def on_task_request(session_id, payload):
            query = payload.get("query", "")
            await bridge.notify_plan_proposed(session_id, f"计划: {query}", 2)
            return {"status": "accepted", "plan_id": "plan_001"}

        async def on_plan_approved(session_id, plan_id):
            workflow_id = f"wf_{plan_id}"
            await bridge.notify_execution_started(session_id, workflow_id)

            # 模拟执行
            for i in range(2):
                await asyncio.sleep(0.01)
                await bridge.report_progress(
                    session_id, workflow_id, f"node_{i}", (i + 1) / 2, f"步骤 {i + 1}"
                )

            await bridge.report_completed(session_id, workflow_id, {"success": True})

        handler.on_task_request = on_task_request
        handler.on_plan_approved = on_plan_approved

        # 1. 发送任务请求
        await handler.handle_message(
            AgentMessage(
                type=AgentMessageType.TASK_REQUEST,
                session_id="session_1",
                payload={"query": "分析数据"},
            )
        )

        # 验证计划提议
        assert ws.sent_messages[-1]["type"] == "plan_proposed"

        # 2. 批准计划
        await handler.handle_message(
            AgentMessage(
                type=AgentMessageType.PLAN_APPROVED,
                session_id="session_1",
                payload={"plan_id": "plan_001"},
            )
        )

        # 等待异步执行完成
        await asyncio.sleep(0.1)

        # 3. 验证完整消息序列
        message_types = [msg["type"] for msg in ws.sent_messages]

        assert "plan_proposed" in message_types
        assert "execution_started" in message_types
        assert "execution_progress" in message_types
        assert "execution_completed" in message_types

    @pytest.mark.asyncio
    async def test_cancel_task_stops_execution(self):
        """测试：取消任务停止执行"""
        channel = AgentWebSocketChannel()
        handler = AgentMessageHandler(channel=channel)

        cancelled_tasks = []

        async def on_cancel(session_id, task_id):
            cancelled_tasks.append(task_id)

        handler.on_cancel_task = on_cancel

        # 发送取消请求
        await handler.handle_message(
            AgentMessage(
                type=AgentMessageType.CANCEL_TASK,
                session_id="session_1",
                payload={"task_id": "task_abc"},
            )
        )

        assert "task_abc" in cancelled_tasks

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolation(self):
        """测试：多会话隔离"""
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)

        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await channel.register_session("session_1", ws1, "user_1")
        await channel.register_session("session_2", ws2, "user_2")

        # 向 session_1 发送消息
        await bridge.report_progress("session_1", "wf_1", "node_1", 0.5, "进度1")

        # 向 session_2 发送消息
        await bridge.report_progress("session_2", "wf_2", "node_2", 0.7, "进度2")

        # 验证隔离
        assert len(ws1.sent_messages) == 1
        assert ws1.sent_messages[0]["payload"]["message"] == "进度1"

        assert len(ws2.sent_messages) == 1
        assert ws2.sent_messages[0]["payload"]["message"] == "进度2"

    @pytest.mark.asyncio
    async def test_broadcast_to_all_sessions(self):
        """测试：广播到所有会话"""
        channel = AgentWebSocketChannel()

        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        ws3 = MockWebSocket()

        await channel.register_session("s1", ws1, "u1")
        await channel.register_session("s2", ws2, "u2")
        await channel.register_session("s3", ws3, "u3")

        # 广播消息
        msg = AgentMessage(
            type=AgentMessageType.EXECUTION_STARTED,
            session_id="broadcast",
            payload={"workflow_id": "wf_global"},
        )

        count = await channel.broadcast(msg)

        # 验证所有客户端收到
        assert count == 3
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert len(ws3.sent_messages) == 1


class TestConversationWorkflowInteraction:
    """ConversationAgent 与 WorkflowAgent 交互测试"""

    @pytest.mark.asyncio
    async def test_conversation_dispatches_plan_to_workflow(self):
        """测试：ConversationAgent 分发计划到 WorkflowAgent"""
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)

        # 模拟 ConversationAgent 生成计划
        plan = {
            "workflow_id": "wf_sales_analysis",
            "nodes": [
                {"id": "fetch", "type": "http", "config": {"url": "/api/sales"}},
                {"id": "process", "type": "llm", "config": {"prompt": "分析"}},
                {"id": "report", "type": "template", "config": {}},
            ],
            "edges": [
                {"source": "fetch", "target": "process"},
                {"source": "process", "target": "report"},
            ],
        }

        # 分发计划
        msg = await bridge.dispatch_plan_to_workflow("session_1", plan)

        assert msg.type == AgentMessageType.WORKFLOW_DISPATCH
        assert msg.payload["workflow_id"] == "wf_sales_analysis"
        assert len(msg.payload["nodes"]) == 3

    @pytest.mark.asyncio
    async def test_workflow_reports_back_to_conversation(self):
        """测试：WorkflowAgent 报告结果给 ConversationAgent"""
        channel = AgentWebSocketChannel()
        bridge = AgentChannelBridge(channel=channel)

        ws = MockWebSocket()
        await channel.register_session("session_1", ws, "user_1")

        # 模拟 WorkflowAgent 执行完成后报告
        await bridge.report_completed(
            session_id="session_1",
            workflow_id="wf_123",
            result={
                "summary": "销售数据分析完成",
                "insights": ["趋势上升", "Q4表现最佳"],
                "charts": ["bar_chart.png"],
            },
        )

        # 验证结果
        assert len(ws.sent_messages) == 1
        result = ws.sent_messages[0]["payload"]["result"]
        assert result["summary"] == "销售数据分析完成"
        assert len(result["insights"]) == 2


# 导出
__all__ = [
    "TestAgentWebSocketE2E",
    "TestFullTaskLifecycleE2E",
    "TestConversationWorkflowInteraction",
]
