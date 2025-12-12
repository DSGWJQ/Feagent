"""测试：上下文管理器 (Context Manager)

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- 多Agent协作系统需要管理多层上下文
- 全局上下文(只读) → 会话上下文 → 工作流上下文 → 节点上下文
- 各层上下文有不同的生命周期和访问权限
- 这是 Phase 0 基础设施的核心组件

真实场景：
1. 用户开始会话，创建SessionContext继承GlobalContext
2. 对话Agent分解目标，目标栈存储在SessionContext
3. 工作流执行时，创建独立的WorkflowContext
4. 节点执行时，创建临时的NodeContext
5. 工作流间传递数据时，通过上下文桥接并摘要
"""

import pytest


class TestGlobalContext:
    """测试全局上下文

    业务背景：
    - 全局上下文存储系统级配置和用户偏好
    - 整个会话期间只读，不可修改
    - 是所有其他上下文的基础
    """

    def test_create_global_context_with_user_and_config(self):
        """测试：创建全局上下文应包含用户信息和系统配置

        业务场景：
        - 用户登录后创建全局上下文
        - 包含用户ID、偏好设置、系统配置

        验收标准：
        - 可以创建GlobalContext
        - 包含user_id、user_preferences、system_config
        """
        # Arrange & Act
        from src.domain.services.context_manager import GlobalContext

        global_ctx = GlobalContext(
            user_id="user_123",
            user_preferences={"language": "zh-CN", "theme": "dark"},
            system_config={"max_tokens": 10000, "timeout": 60},
        )

        # Assert
        assert global_ctx.user_id == "user_123"
        assert global_ctx.user_preferences["language"] == "zh-CN"
        assert global_ctx.system_config["max_tokens"] == 10000

    def test_global_context_should_be_immutable(self):
        """测试：全局上下文应该是不可变的

        业务场景：
        - 全局配置在会话期间不应被修改
        - 防止Agent意外修改系统配置

        为什么需要这个测试？
        1. 保护系统配置不被意外修改
        2. 确保多Agent共享时的一致性
        3. 符合"全局只读"的设计原则

        验收标准：
        - 尝试修改属性应该抛出异常或被忽略
        """
        # Arrange
        from src.domain.services.context_manager import GlobalContext

        global_ctx = GlobalContext(
            user_id="user_123",
            user_preferences={"language": "zh-CN"},
            system_config={"max_tokens": 10000},
        )

        # Act & Assert - 尝试修改应该失败
        with pytest.raises((AttributeError, TypeError, Exception)):
            global_ctx.user_id = "hacker"


class TestSessionContext:
    """测试会话上下文

    业务背景：
    - 会话上下文管理单次用户会话的状态
    - 继承全局上下文（只读访问）
    - 存储对话历史、目标栈、决策历史
    """

    def test_create_session_context_inherits_global(self):
        """测试：会话上下文应继承全局上下文

        业务场景：
        - 用户开始新会话
        - 会话上下文可以访问全局配置
        - 但不能修改全局配置

        验收标准：
        - SessionContext包含对GlobalContext的引用
        - 可以读取全局配置
        """
        # Arrange
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(
            user_id="user_123",
            user_preferences={"language": "zh-CN"},
            system_config={"max_tokens": 10000},
        )

        # Act
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # Assert
        assert session_ctx.session_id == "session_abc"
        assert session_ctx.global_context.user_id == "user_123"
        assert session_ctx.global_context.system_config["max_tokens"] == 10000

    def test_session_context_manages_conversation_history(self):
        """测试：会话上下文管理对话历史

        业务场景：
        - 对话Agent与用户交互
        - 对话历史需要被记录
        - 用于ReAct循环的上下文

        验收标准：
        - 可以添加消息到对话历史
        - 可以获取完整对话历史
        """
        # Arrange
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # Act
        session_ctx.add_message({"role": "user", "content": "帮我分析数据"})
        session_ctx.add_message({"role": "assistant", "content": "好的，请上传数据文件"})

        # Assert
        assert len(session_ctx.conversation_history) == 2
        assert session_ctx.conversation_history[0]["role"] == "user"
        assert session_ctx.conversation_history[1]["role"] == "assistant"

    def test_session_context_manages_goal_stack(self):
        """测试：会话上下文管理目标栈

        业务场景：
        - 对话Agent分解全局目标为子目标
        - 子目标形成栈结构（LIFO）
        - 完成一个子目标后弹出，处理下一个

        为什么用栈？
        1. 支持嵌套目标（目标可以有子目标）
        2. 自然的完成顺序（先完成最内层）
        3. 便于追踪当前正在处理的目标

        验收标准：
        - 可以push目标
        - 可以pop目标
        - 可以peek当前目标
        """
        # Arrange
        from src.domain.services.context_manager import GlobalContext, Goal, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        goal1 = Goal(id="goal_1", description="分析销售数据")
        goal2 = Goal(id="goal_2", description="生成报告", parent_id="goal_1")

        # Act
        session_ctx.push_goal(goal1)
        session_ctx.push_goal(goal2)

        # Assert
        assert session_ctx.current_goal().id == "goal_2"  # 栈顶是goal2
        assert len(session_ctx.goal_stack) == 2

        # Pop goal2
        popped = session_ctx.pop_goal()
        assert popped.id == "goal_2"
        assert session_ctx.current_goal().id == "goal_1"

    def test_session_context_records_decision_history(self):
        """测试：会话上下文记录决策历史

        业务场景：
        - 对话Agent做出多个决策
        - 决策历史用于审计和回溯
        - 协调者可以分析决策模式

        验收标准：
        - 可以添加决策到历史
        - 可以查询决策历史
        """
        # Arrange
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # Act
        session_ctx.add_decision({"id": "decision_1", "type": "create_node", "confidence": 0.9})
        session_ctx.add_decision(
            {"id": "decision_2", "type": "execute_workflow", "confidence": 0.85}
        )

        # Assert
        assert len(session_ctx.decision_history) == 2
        assert session_ctx.decision_history[0]["type"] == "create_node"

    def test_session_context_with_resource_constraints(self):
        """测试：会话上下文支持资源约束

        业务场景：
        - ConversationAgent需要在决策时考虑资源约束
        - 资源约束包括：时间限制、并发限制等
        - 约束信息存储在SessionContext中

        为什么需要这个测试？
        1. 确保SessionContext有resource_constraints字段
        2. 支持运行时设置和读取资源约束
        3. 修复Pyright类型检查错误(conversation_agent.py:1283, 1307)

        验收标准：
        - SessionContext可以设置resource_constraints
        - 默认值为None（无特殊约束）
        - 可以读取约束信息
        """
        # Arrange
        from src.domain.services.context_manager import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="user_123")

        # Act & Assert - 测试默认为None
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)
        assert session_ctx.resource_constraints is None

        # Act & Assert - 测试设置约束
        constraints = {"time_limit": 300, "max_parallel": 3}
        session_ctx2 = SessionContext(
            session_id="test2", global_context=global_ctx, resource_constraints=constraints
        )
        assert session_ctx2.resource_constraints == constraints
        assert session_ctx2.resource_constraints["time_limit"] == 300
        assert session_ctx2.resource_constraints["max_parallel"] == 3

        # Act & Assert - 测试运行时设置
        session_ctx3 = SessionContext(session_id="test3", global_context=global_ctx)
        assert session_ctx3.resource_constraints is None
        session_ctx3.resource_constraints = {"time_limit": 600}
        assert session_ctx3.resource_constraints["time_limit"] == 600


class TestWorkflowContext:
    """测试工作流上下文

    业务背景：
    - 每个工作流执行有独立的上下文
    - 存储节点数据、执行历史、变量
    - 上下文隔离，工作流间不互相影响
    """

    def test_create_workflow_context_with_session_reference(self):
        """测试：工作流上下文引用会话上下文

        业务场景：
        - 工作流执行时需要访问会话信息
        - 但工作流上下文是隔离的

        验收标准：
        - WorkflowContext包含对SessionContext的引用
        - 可以访问会话上下文（只读）
        """
        # Arrange
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # Act
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        # Assert
        assert workflow_ctx.workflow_id == "workflow_xyz"
        assert workflow_ctx.session_context.session_id == "session_abc"

    def test_workflow_context_stores_node_outputs(self):
        """测试：工作流上下文存储节点输出

        业务场景：
        - 节点执行完成后，输出存储到工作流上下文
        - 下游节点可以获取上游节点的输出
        - 这是节点间数据传递的核心机制

        验收标准：
        - 可以设置节点输出
        - 可以获取节点输出
        - 支持按key获取特定输出
        """
        # Arrange
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        # Act
        workflow_ctx.set_node_output("node_1", {"result": "success", "data": {"count": 100}})

        # Assert
        output = workflow_ctx.get_node_output("node_1")
        assert output["result"] == "success"
        assert output["data"]["count"] == 100

        # 按key获取
        result = workflow_ctx.get_node_output("node_1", "result")
        assert result == "success"

    def test_workflow_context_manages_variables(self):
        """测试：工作流上下文管理变量

        业务场景：
        - 工作流执行过程中需要存储中间变量
        - 变量可以跨节点使用
        - 例如：循环计数器、累加器

        验收标准：
        - 可以设置变量
        - 可以获取变量
        - 变量不存在时返回默认值
        """
        # Arrange
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        # Act
        workflow_ctx.set_variable("counter", 0)
        workflow_ctx.set_variable("total", 100)

        # Assert
        assert workflow_ctx.get_variable("counter") == 0
        assert workflow_ctx.get_variable("total") == 100
        assert workflow_ctx.get_variable("not_exist", default=-1) == -1

    def test_workflow_contexts_are_isolated(self):
        """测试：不同工作流的上下文相互隔离

        业务场景：
        - 同时执行多个工作流
        - 一个工作流的变量不应影响另一个
        - 这是并发执行的基础

        为什么需要这个测试？
        1. 确保工作流间数据隔离
        2. 防止并发执行时的数据污染
        3. 保证工作流的独立性

        验收标准：
        - 两个WorkflowContext互不影响
        - 修改一个不会影响另一个
        """
        # Arrange
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        workflow_ctx_1 = WorkflowContext(workflow_id="workflow_1", session_context=session_ctx)
        workflow_ctx_2 = WorkflowContext(workflow_id="workflow_2", session_context=session_ctx)

        # Act
        workflow_ctx_1.set_variable("x", 100)
        workflow_ctx_2.set_variable("x", 200)

        # Assert - 互不影响
        assert workflow_ctx_1.get_variable("x") == 100
        assert workflow_ctx_2.get_variable("x") == 200


class TestNodeContext:
    """测试节点上下文

    业务背景：
    - 节点执行时的临时上下文
    - 存储输入数据、执行状态、输出数据
    - 生命周期最短，节点执行完就销毁
    """

    def test_create_node_context_with_inputs(self):
        """测试：创建节点上下文并设置输入

        业务场景：
        - 节点开始执行前，准备输入数据
        - 输入可能来自上游节点或用户输入

        验收标准：
        - 可以创建NodeContext
        - 可以设置和获取输入数据
        """
        # Arrange & Act
        from src.domain.services.context_manager import (
            GlobalContext,
            NodeContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        node_ctx = NodeContext(
            node_id="node_llm_1",
            workflow_context=workflow_ctx,
            inputs={"prompt": "分析这段数据", "temperature": 0.7},
        )

        # Assert
        assert node_ctx.node_id == "node_llm_1"
        assert node_ctx.inputs["prompt"] == "分析这段数据"
        assert node_ctx.inputs["temperature"] == 0.7

    def test_node_context_tracks_execution_state(self):
        """测试：节点上下文跟踪执行状态

        业务场景：
        - 节点执行有多个状态：pending, running, completed, failed
        - 用于画布上显示执行进度

        验收标准：
        - 默认状态是pending
        - 可以更新状态
        """
        # Arrange
        from src.domain.services.context_manager import (
            GlobalContext,
            NodeContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        node_ctx = NodeContext(node_id="node_1", workflow_context=workflow_ctx)

        # Assert default state
        assert node_ctx.execution_state == "pending"

        # Act - update state
        node_ctx.set_state("running")
        assert node_ctx.execution_state == "running"

        node_ctx.set_state("completed")
        assert node_ctx.execution_state == "completed"

    def test_node_context_stores_outputs(self):
        """测试：节点上下文存储输出

        业务场景：
        - 节点执行完成后，存储输出
        - 输出会被传递给下游节点

        验收标准：
        - 可以设置输出
        - 输出可以被获取
        """
        # Arrange
        from src.domain.services.context_manager import (
            GlobalContext,
            NodeContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)

        node_ctx = NodeContext(node_id="node_1", workflow_context=workflow_ctx)

        # Act
        node_ctx.set_output("result", "分析完成")
        node_ctx.set_output("data", {"summary": "销售额增长10%"})

        # Assert
        assert node_ctx.outputs["result"] == "分析完成"
        assert node_ctx.outputs["data"]["summary"] == "销售额增长10%"


class TestContextHierarchy:
    """测试上下文层级关系

    业务背景：
    - 上下文形成层级：Global → Session → Workflow → Node
    - 下层可以访问上层数据（只读）
    - 修改只影响当前层
    """

    def test_node_can_access_workflow_variables(self):
        """测试：节点上下文可以访问工作流变量

        业务场景：
        - 节点执行时需要读取工作流级别的变量
        - 例如：读取循环计数器

        验收标准：
        - 通过NodeContext可以获取WorkflowContext的变量
        """
        # Arrange
        from src.domain.services.context_manager import (
            GlobalContext,
            NodeContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)
        workflow_ctx.set_variable("batch_size", 100)

        node_ctx = NodeContext(node_id="node_1", workflow_context=workflow_ctx)

        # Act & Assert
        assert node_ctx.workflow_context.get_variable("batch_size") == 100

    def test_node_can_access_global_config(self):
        """测试：节点上下文可以访问全局配置

        业务场景：
        - 节点可能需要读取系统配置
        - 例如：LLM的max_tokens限制

        验收标准：
        - 通过层级关系可以访问GlobalContext
        """
        # Arrange
        from src.domain.services.context_manager import (
            GlobalContext,
            NodeContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123", system_config={"max_tokens": 8000})
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)
        workflow_ctx = WorkflowContext(workflow_id="workflow_xyz", session_context=session_ctx)
        node_ctx = NodeContext(node_id="node_1", workflow_context=workflow_ctx)

        # Act & Assert - 通过层级访问
        max_tokens = node_ctx.workflow_context.session_context.global_context.system_config[
            "max_tokens"
        ]
        assert max_tokens == 8000


class TestContextBridge:
    """测试上下文桥接

    业务背景：
    - 工作流之间需要传递数据
    - 传递时需要摘要以控制token消耗
    - 这是目标分解后子工作流协作的基础
    """

    def test_transfer_data_between_workflow_contexts(self):
        """测试：在工作流上下文之间传递数据

        业务场景：
        - 工作流A完成后，结果需要传递给工作流B
        - 数据传递时可以选择性传递

        验收标准：
        - 可以将数据从源工作流传递到目标工作流
        - 传递的数据在目标工作流中可访问
        """
        # Arrange
        from src.domain.services.context_manager import (
            ContextBridge,
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        source_workflow = WorkflowContext(workflow_id="workflow_1", session_context=session_ctx)
        target_workflow = WorkflowContext(workflow_id="workflow_2", session_context=session_ctx)

        # 源工作流有一些输出
        source_workflow.set_node_output(
            "node_final",
            {
                "analysis_result": "销售额增长10%",
                "raw_data": [1, 2, 3, 4, 5],  # 大量数据
            },
        )

        # Act - 传递数据
        bridge = ContextBridge()
        bridge.transfer(
            source=source_workflow,
            target=target_workflow,
            keys=["analysis_result"],  # 只传递摘要，不传递原始数据
        )

        # Assert
        transferred = target_workflow.get_variable("__transferred__")
        assert transferred is not None
        assert "analysis_result" in transferred
        assert transferred["analysis_result"] == "销售额增长10%"

    def test_transfer_with_summary(self):
        """测试：传递时进行摘要

        业务场景：
        - 大量数据传递时需要摘要
        - 控制token消耗
        - 保留关键信息

        验收标准：
        - 可以对传递的数据进行摘要
        - 摘要后的数据更精简
        """
        # Arrange
        from src.domain.services.context_manager import (
            ContextBridge,
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )

        global_ctx = GlobalContext(user_id="user_123")
        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        source_workflow = WorkflowContext(workflow_id="workflow_1", session_context=session_ctx)
        target_workflow = WorkflowContext(workflow_id="workflow_2", session_context=session_ctx)

        # 源工作流有大量数据
        source_workflow.set_variable(
            "execution_log",
            [
                {"step": 1, "action": "fetch_data", "result": "success"},
                {"step": 2, "action": "process", "result": "success"},
                {"step": 3, "action": "analyze", "result": "success"},
            ],
        )

        # Act - 传递并摘要
        bridge = ContextBridge()
        bridge.transfer_with_summary(
            source=source_workflow,
            target=target_workflow,
            summary_fn=lambda data: {"steps_count": len(data), "all_success": True},
        )

        # Assert
        transferred = target_workflow.get_variable("__transferred__")
        assert transferred["steps_count"] == 3
        assert transferred["all_success"] is True


class TestRealWorldScenario:
    """测试真实业务场景

    完整的Agent协作流程测试
    """

    def test_complete_agent_collaboration_context_flow(self):
        """测试：完整的Agent协作上下文流程

        业务场景：
        1. 用户开始会话
        2. 对话Agent设置全局目标并分解
        3. 工作流Agent执行子工作流
        4. 节点执行产生输出
        5. 结果传递回对话Agent

        这是多Agent协作的完整上下文管理流程！

        验收标准：
        - 全局上下文在整个流程中保持不变
        - 会话上下文正确记录目标和决策
        - 工作流上下文正确隔离
        - 节点输出正确传递
        """
        # Arrange
        from src.domain.services.context_manager import (
            GlobalContext,
            Goal,
            NodeContext,
            SessionContext,
            WorkflowContext,
        )

        # 1. 用户开始会话
        global_ctx = GlobalContext(
            user_id="user_123",
            user_preferences={"language": "zh-CN"},
            system_config={"max_tokens": 10000},
        )

        session_ctx = SessionContext(session_id="session_abc", global_context=global_ctx)

        # 2. 对话Agent设置目标
        main_goal = Goal(id="goal_main", description="分析销售数据并生成报告")
        sub_goal_1 = Goal(id="goal_sub_1", description="获取数据", parent_id="goal_main")

        session_ctx.push_goal(main_goal)
        session_ctx.push_goal(sub_goal_1)

        # 3. 工作流Agent执行子工作流
        workflow_ctx = WorkflowContext(
            workflow_id="workflow_fetch_data", session_context=session_ctx
        )

        # 4. 节点执行
        node_ctx = NodeContext(
            node_id="node_api_call",
            workflow_context=workflow_ctx,
            inputs={"url": "https://api.example.com/sales"},
        )

        node_ctx.set_state("running")
        # 模拟API调用结果
        node_ctx.set_output("data", {"sales": [100, 200, 300]})
        node_ctx.set_state("completed")

        # 保存到工作流上下文
        workflow_ctx.set_node_output(node_ctx.node_id, node_ctx.outputs)

        # 5. 目标完成，弹出栈
        session_ctx.pop_goal()  # 完成 sub_goal_1

        # 记录决策
        session_ctx.add_decision(
            {"id": "decision_1", "type": "complete_goal", "goal_id": "goal_sub_1"}
        )

        # Assert - 验证整个流程
        # 全局上下文不变
        assert global_ctx.user_id == "user_123"

        # 会话上下文记录正确
        assert session_ctx.current_goal().id == "goal_main"
        assert len(session_ctx.decision_history) == 1

        # 工作流上下文有节点输出
        output = workflow_ctx.get_node_output("node_api_call")
        assert output["data"]["sales"] == [100, 200, 300]

        # 节点状态正确
        assert node_ctx.execution_state == "completed"
