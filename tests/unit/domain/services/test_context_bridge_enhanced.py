"""上下文桥接器增强测试 - 阶段 5

TDD 驱动：先写测试定义期望行为，再实现功能

测试场景：
1. 每个 workflow 独立上下文 + 显式桥接流程
2. API 让协作者请求前序 workflow 的输出
3. 无桥接时无法访问
4. 日志/接口中可见传递记录

完成标准：
- 多 workflow 场景下，A 的结果需经过桥接才能在 B 中使用
- 日志/接口中可见传递记录
- 无桥接时无法访问
"""

from datetime import datetime

import pytest


class TestWorkflowContextIsolation:
    """测试工作流上下文隔离"""

    def test_workflow_contexts_are_isolated(self):
        """测试：不同工作流的上下文相互隔离

        场景：workflow_A 的数据不能直接被 workflow_B 访问
        """
        from src.domain.services.context_bridge import (
            ContextManager,
        )

        manager = ContextManager()

        # 创建上下文层级
        global_ctx = manager.create_global_context(user_id="user_1")
        session_ctx = manager.create_session_context("session_1", global_ctx)

        # 创建两个工作流上下文
        wf_a_ctx = manager.create_workflow_context("workflow_a", session_ctx)
        wf_b_ctx = manager.create_workflow_context("workflow_b", session_ctx)

        # 在 workflow_A 中设置数据
        wf_a_ctx.set_node_output("node_1", {"result": "A的结果"})
        wf_a_ctx.set_variable("key", "value_from_a")

        # workflow_B 不能直接访问 A 的数据
        assert wf_b_ctx.get_node_output("node_1") == {}
        assert wf_b_ctx.get_variable("key") is None

    def test_cannot_access_other_workflow_without_bridge(self):
        """测试：无桥接时无法访问其他工作流的数据

        验收标准：尝试直接访问应该抛出异常或返回空
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.context_bridge_enhanced import (
            AccessDeniedError,
            SecureContextBridge,
        )

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        wf_a = WorkflowContext(workflow_id="wf_a", session_context=session_ctx)
        wf_b = WorkflowContext(workflow_id="wf_b", session_context=session_ctx)

        # 在 A 中设置数据
        wf_a.set_node_output("node_1", {"secret": "敏感数据"})

        # B 尝试直接访问（无桥接）
        bridge = SecureContextBridge()
        # 注册工作流（但不桥接）
        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)

        # 因为没有执行桥接，所以访问会被拒绝
        with pytest.raises(AccessDeniedError, match="未授权访问"):
            bridge.get_from_workflow(
                source_workflow_id="wf_a",
                target_workflow_id="wf_b",
                key="node_1",
            )


class TestExplicitBridging:
    """测试显式桥接流程"""

    @pytest.mark.asyncio
    async def test_explicit_bridge_request(self):
        """测试：显式请求桥接前序 workflow 的输出

        场景：
        1. workflow_A 执行完成，产生输出
        2. workflow_B 显式请求 A 的输出
        3. 通过 ContextBridge 传递数据
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.context_bridge_enhanced import (
            BridgeRequest,
            SecureContextBridge,
        )

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        wf_a = WorkflowContext(workflow_id="wf_a", session_context=session_ctx)
        wf_b = WorkflowContext(workflow_id="wf_b", session_context=session_ctx)

        # A 产生输出
        wf_a.set_node_output("analysis_node", {"report": "分析报告内容"})
        wf_a.set_variable("status", "completed")

        # 创建桥接器并注册工作流
        bridge = SecureContextBridge()
        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)

        # B 显式请求桥接
        request = BridgeRequest(
            source_workflow_id="wf_a",
            target_workflow_id="wf_b",
            requested_keys=["analysis_node", "status"],
            requester="workflow_b_coordinator",
        )

        # 执行桥接
        result = await bridge.transfer_with_request(request)

        # 验证传递成功
        assert result.success is True
        assert result.transferred_data["analysis_node"]["report"] == "分析报告内容"
        assert result.transferred_data["status"] == "completed"

        # B 现在可以访问
        assert wf_b.get_variable("__bridge_wf_a__") is not None

    @pytest.mark.asyncio
    async def test_bridge_requires_authorization(self):
        """测试：桥接需要授权

        场景：未经授权的桥接请求应被拒绝
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.context_bridge_enhanced import (
            AuthorizationDeniedError,
            BridgeRequest,
            SecureContextBridge,
        )

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        wf_a = WorkflowContext(workflow_id="wf_a", session_context=session_ctx)
        wf_b = WorkflowContext(workflow_id="wf_b", session_context=session_ctx)

        bridge = SecureContextBridge()
        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)

        # 设置 A 的输出为受限
        bridge.set_access_policy(
            workflow_id="wf_a",
            allowed_requesters=["workflow_c"],  # 只允许 C 访问
        )

        # B 请求访问（未授权）
        request = BridgeRequest(
            source_workflow_id="wf_a",
            target_workflow_id="wf_b",
            requested_keys=["any_key"],
            requester="workflow_b",
        )

        with pytest.raises(AuthorizationDeniedError, match="授权被拒绝"):
            await bridge.transfer_with_request(request)

    @pytest.mark.asyncio
    async def test_selective_data_bridging(self):
        """测试：选择性数据桥接

        场景：只传递请求的特定数据，不是全部
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.context_bridge_enhanced import (
            BridgeRequest,
            SecureContextBridge,
        )

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        wf_a = WorkflowContext(workflow_id="wf_a", session_context=session_ctx)
        wf_b = WorkflowContext(workflow_id="wf_b", session_context=session_ctx)

        # A 有多个输出
        wf_a.set_node_output("node_1", {"data": "data_1"})
        wf_a.set_node_output("node_2", {"data": "data_2"})
        wf_a.set_node_output("secret_node", {"password": "secret123"})

        bridge = SecureContextBridge()
        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)

        # B 只请求 node_1
        request = BridgeRequest(
            source_workflow_id="wf_a",
            target_workflow_id="wf_b",
            requested_keys=["node_1"],
            requester="workflow_b",
        )

        result = await bridge.transfer_with_request(request)

        # 只传递了 node_1
        assert "node_1" in result.transferred_data
        assert "node_2" not in result.transferred_data
        assert "secret_node" not in result.transferred_data


class TestBridgeTransferLog:
    """测试桥接传递记录"""

    @pytest.mark.asyncio
    async def test_bridge_transfer_is_logged(self):
        """测试：桥接传递记录可见

        验收标准：日志/接口中可见传递记录
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.context_bridge_enhanced import (
            BridgeRequest,
            SecureContextBridge,
        )

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        wf_a = WorkflowContext(workflow_id="wf_a", session_context=session_ctx)
        wf_b = WorkflowContext(workflow_id="wf_b", session_context=session_ctx)

        wf_a.set_variable("data", "test_data")

        bridge = SecureContextBridge()
        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)

        # 执行桥接
        request = BridgeRequest(
            source_workflow_id="wf_a",
            target_workflow_id="wf_b",
            requested_keys=["data"],
            requester="workflow_b",
        )

        await bridge.transfer_with_request(request)

        # 获取传递记录
        logs = bridge.get_transfer_logs()

        assert len(logs) == 1
        assert logs[0]["source"] == "wf_a"
        assert logs[0]["target"] == "wf_b"
        assert logs[0]["keys"] == ["data"]
        assert "timestamp" in logs[0]

    @pytest.mark.asyncio
    async def test_get_transfer_history_for_workflow(self):
        """测试：获取特定工作流的传递历史"""
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.context_bridge_enhanced import (
            BridgeRequest,
            SecureContextBridge,
        )

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        wf_a = WorkflowContext(workflow_id="wf_a", session_context=session_ctx)
        wf_b = WorkflowContext(workflow_id="wf_b", session_context=session_ctx)
        wf_c = WorkflowContext(workflow_id="wf_c", session_context=session_ctx)

        wf_a.set_variable("data_a", "value_a")
        wf_b.set_variable("data_b", "value_b")

        bridge = SecureContextBridge()
        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)
        bridge.register_workflow(wf_c)

        # A -> B
        await bridge.transfer_with_request(
            BridgeRequest(
                source_workflow_id="wf_a",
                target_workflow_id="wf_b",
                requested_keys=["data_a"],
                requester="wf_b",
            )
        )

        # A -> C
        await bridge.transfer_with_request(
            BridgeRequest(
                source_workflow_id="wf_a",
                target_workflow_id="wf_c",
                requested_keys=["data_a"],
                requester="wf_c",
            )
        )

        # 获取 A 的传出历史
        outgoing = bridge.get_transfer_history(workflow_id="wf_a", direction="outgoing")
        assert len(outgoing) == 2

        # 获取 B 的传入历史
        incoming = bridge.get_transfer_history(workflow_id="wf_b", direction="incoming")
        assert len(incoming) == 1


class TestCoordinatorContextBridgeIntegration:
    """测试协调者与上下文桥接的集成"""

    @pytest.mark.asyncio
    async def test_coordinator_can_request_bridge(self):
        """测试：协调者可以请求上下文桥接

        场景：协调者代表 workflow_B 请求 workflow_A 的输出
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.context_bridge_enhanced import SecureContextBridge
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        bridge = SecureContextBridge()

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        wf_a = WorkflowContext(workflow_id="wf_a", session_context=session_ctx)
        wf_b = WorkflowContext(workflow_id="wf_b", session_context=session_ctx)

        wf_a.set_node_output("result_node", {"value": 42})

        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)

        # 创建协调者并关联桥接器
        coordinator = CoordinatorAgent(
            event_bus=event_bus,
            context_bridge=bridge,
        )

        # 协调者请求桥接
        result = await coordinator.request_context_bridge(
            source_workflow_id="wf_a",
            target_workflow_id="wf_b",
            keys=["result_node"],
        )

        assert result["value"] == 42


class TestRealWorldScenario:
    """真实场景测试"""

    @pytest.mark.asyncio
    async def test_complete_multi_workflow_bridging_scenario(self):
        """测试：完整的多工作流桥接场景

        场景：
        1. workflow_A 执行数据收集任务
        2. workflow_B 需要 A 的结果进行分析
        3. B 通过桥接请求 A 的输出
        4. 验证桥接成功，日志可见
        5. 验证无桥接时 C 无法访问

        这是阶段 5 的完整验收场景！
        """
        from src.domain.services.context_bridge import (
            ContextManager,
        )
        from src.domain.services.context_bridge_enhanced import (
            AccessDeniedError,
            BridgeRequest,
            SecureContextBridge,
        )

        # === 初始化 ===
        manager = ContextManager()
        bridge = SecureContextBridge()

        global_ctx = manager.create_global_context(user_id="user_1")
        session_ctx = manager.create_session_context("session_1", global_ctx)

        # 创建三个工作流
        wf_a = manager.create_workflow_context("wf_data_collection", session_ctx)
        wf_b = manager.create_workflow_context("wf_analysis", session_ctx)
        wf_c = manager.create_workflow_context("wf_unauthorized", session_ctx)

        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)
        bridge.register_workflow(wf_c)

        # === 步骤 1：workflow_A 执行数据收集 ===
        wf_a.set_node_output(
            "data_collector",
            {
                "collected_data": [1, 2, 3, 4, 5],
                "source": "external_api",
                "timestamp": datetime.now().isoformat(),
            },
        )
        wf_a.set_variable("collection_status", "completed")

        # === 步骤 2 & 3：workflow_B 请求桥接 ===
        request = BridgeRequest(
            source_workflow_id="wf_data_collection",
            target_workflow_id="wf_analysis",
            requested_keys=["data_collector", "collection_status"],
            requester="wf_analysis_coordinator",
        )

        result = await bridge.transfer_with_request(request)

        # === 步骤 4：验证桥接成功 ===
        assert result.success is True
        assert result.transferred_data["data_collector"]["collected_data"] == [1, 2, 3, 4, 5]
        assert result.transferred_data["collection_status"] == "completed"

        # 验证日志可见
        logs = bridge.get_transfer_logs()
        assert len(logs) == 1
        assert logs[0]["source"] == "wf_data_collection"
        assert logs[0]["target"] == "wf_analysis"

        # B 可以使用数据
        bridged_data = wf_b.get_variable("__bridge_wf_data_collection__")
        assert bridged_data is not None

        # === 步骤 5：验证无桥接时 C 无法访问 ===
        # C 尝试直接访问 A 的数据（无桥接）
        with pytest.raises(AccessDeniedError):
            bridge.get_from_workflow(
                source_workflow_id="wf_data_collection",
                target_workflow_id="wf_unauthorized",
                key="data_collector",
            )

        print("✅ 验收通过：完整多工作流桥接场景测试成功！")
        print("   - 工作流 A 数据收集完成: ✓")
        print("   - 工作流 B 成功请求桥接: ✓")
        print(f"   - 传递记录可见 ({len(logs)} 条): ✓")
        print("   - 未授权访问被拒绝: ✓")

    @pytest.mark.asyncio
    async def test_chained_workflow_bridging(self):
        """测试：链式工作流桥接

        场景：A -> B -> C 的数据传递链
        """
        from src.domain.services.context_bridge import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.context_bridge_enhanced import (
            BridgeRequest,
            SecureContextBridge,
        )

        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(session_id="session_1", global_context=global_ctx)

        wf_a = WorkflowContext(workflow_id="wf_a", session_context=session_ctx)
        wf_b = WorkflowContext(workflow_id="wf_b", session_context=session_ctx)
        wf_c = WorkflowContext(workflow_id="wf_c", session_context=session_ctx)

        bridge = SecureContextBridge()
        bridge.register_workflow(wf_a)
        bridge.register_workflow(wf_b)
        bridge.register_workflow(wf_c)

        # A 产生数据
        wf_a.set_variable("stage_1_result", {"value": 100})

        # A -> B
        await bridge.transfer_with_request(
            BridgeRequest(
                source_workflow_id="wf_a",
                target_workflow_id="wf_b",
                requested_keys=["stage_1_result"],
                requester="wf_b",
            )
        )

        # B 处理并产生新数据
        bridged = wf_b.get_variable("__bridge_wf_a__")
        wf_b.set_variable("stage_2_result", {"value": bridged["stage_1_result"]["value"] * 2})

        # B -> C
        await bridge.transfer_with_request(
            BridgeRequest(
                source_workflow_id="wf_b",
                target_workflow_id="wf_c",
                requested_keys=["stage_2_result"],
                requester="wf_c",
            )
        )

        # 验证链式传递
        c_bridged = wf_c.get_variable("__bridge_wf_b__")
        assert c_bridged["stage_2_result"]["value"] == 200

        # 验证完整传递历史
        logs = bridge.get_transfer_logs()
        assert len(logs) == 2

        print("✅ 链式桥接测试通过！A(100) -> B(200) -> C")
