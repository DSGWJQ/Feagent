"""测试：SessionContext统一定义

TDD第一步：编写测试用例，明确需求和验收标准

业务背景：
- 统一SessionContext定义,消除context_manager和context_bridge的重复定义
- 新建独立实体文件作为唯一来源
- 保持向后兼容,支持两种add_message接口

测试目标：
1. 验证所有23个字段正确定义
2. 验证add_message(dict)方法(context_manager接口)
3. 验证add_message_simple(role, content)方法(context_bridge兼容接口)
4. 验证Goal类型安全性
5. 验证与现有代码的兼容性
"""

import pytest


class TestSessionContextCreation:
    """测试SessionContext创建和基础字段"""

    def test_create_session_context_with_minimal_params(self):
        """测试：最小参数创建SessionContext

        验收标准：
        - 只需要session_id和global_context即可创建
        - 其他字段使用默认值
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test_session", global_context=global_ctx)

        # 验证必需字段
        assert session_ctx.session_id == "test_session"
        assert session_ctx.global_context == global_ctx

        # 验证默认值
        assert session_ctx.conversation_history == []
        assert session_ctx.goal_stack == []
        assert session_ctx.decision_history == []
        assert session_ctx.conversation_summary is None
        assert session_ctx.resource_constraints is None

    def test_session_context_has_all_23_fields(self):
        """测试：SessionContext包含所有23个字段

        字段清单：
        1. session_id
        2. global_context
        3. conversation_history
        4. goal_stack
        5. decision_history
        6. conversation_summary
        7-10. Token统计(total_prompt_tokens, total_completion_tokens, total_tokens, usage_ratio)
        11-13. 模型信息(llm_provider, llm_model, context_limit)
        14-17. 短期记忆(short_term_buffer, is_saturated, saturation_threshold, _event_bus)
        18-19. 冻结备份(_is_frozen, _backup)
        20. 资源约束(resource_constraints)
        21-23. 方法(add_message, add_message_simple, push_goal, pop_goal, current_goal, add_decision, set_model_info, update_token_usage)
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # 验证基础字段
        assert hasattr(session_ctx, "session_id")
        assert hasattr(session_ctx, "global_context")
        assert hasattr(session_ctx, "conversation_history")
        assert hasattr(session_ctx, "goal_stack")
        assert hasattr(session_ctx, "decision_history")
        assert hasattr(session_ctx, "conversation_summary")

        # 验证Token统计字段
        assert hasattr(session_ctx, "total_prompt_tokens")
        assert hasattr(session_ctx, "total_completion_tokens")
        assert hasattr(session_ctx, "total_tokens")
        assert hasattr(session_ctx, "usage_ratio")

        # 验证模型信息字段
        assert hasattr(session_ctx, "llm_provider")
        assert hasattr(session_ctx, "llm_model")
        assert hasattr(session_ctx, "context_limit")

        # 验证短期记忆字段
        assert hasattr(session_ctx, "short_term_buffer")
        assert hasattr(session_ctx, "is_saturated")
        assert hasattr(session_ctx, "saturation_threshold")

        # 验证资源约束字段
        assert hasattr(session_ctx, "resource_constraints")


class TestAddMessageInterface:
    """测试add_message接口(context_manager风格)"""

    def test_add_message_with_dict(self):
        """测试：使用dict添加消息(context_manager接口)

        验收标准：
        - 接受dict参数
        - dict包含role和content
        - 消息添加到conversation_history
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # 添加消息
        session_ctx.add_message({"role": "user", "content": "Hello"})
        session_ctx.add_message({"role": "assistant", "content": "Hi"})

        # 验证
        assert len(session_ctx.conversation_history) == 2
        assert session_ctx.conversation_history[0]["role"] == "user"
        assert session_ctx.conversation_history[0]["content"] == "Hello"
        assert session_ctx.conversation_history[1]["role"] == "assistant"


class TestAddMessageSimpleInterface:
    """测试add_message_simple接口(context_bridge兼容)"""

    def test_add_message_simple_with_role_and_content(self):
        """测试：使用role和content添加消息(context_bridge接口)

        验收标准：
        - 接受role和content两个参数
        - 自动添加timestamp
        - 兼容旧的context_bridge代码
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # 使用简化接口添加消息
        session_ctx.add_message_simple("user", "Hello from bridge")

        # 验证
        assert len(session_ctx.conversation_history) == 1
        message = session_ctx.conversation_history[0]
        assert message["role"] == "user"
        assert message["content"] == "Hello from bridge"
        assert "timestamp" in message  # context_bridge会自动添加timestamp

    def test_add_message_simple_backwards_compatible(self):
        """测试：add_message_simple向后兼容

        验收标准：
        - 旧代码使用add_message_simple仍然工作
        - 与add_message(dict)混用不冲突
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # 混合使用两种接口
        session_ctx.add_message({"role": "user", "content": "Dict style"})
        session_ctx.add_message_simple("assistant", "Simple style")

        # 验证
        assert len(session_ctx.conversation_history) == 2
        assert session_ctx.conversation_history[0]["content"] == "Dict style"
        assert session_ctx.conversation_history[1]["content"] == "Simple style"


class TestGoalStack:
    """测试目标栈(Goal类型安全)"""

    def test_goal_stack_with_goal_type(self):
        """测试：goal_stack使用Goal类型(不是Any)

        验收标准：
        - goal_stack类型为list[Goal]
        - 符合context_manager的严格类型约束
        """
        from src.domain.entities.session_context import GlobalContext, Goal, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # 创建Goal并push
        goal = Goal(id="g1", description="Test goal")
        session_ctx.push_goal(goal)

        # 验证类型
        assert len(session_ctx.goal_stack) == 1
        assert isinstance(session_ctx.goal_stack[0], Goal)
        assert session_ctx.current_goal().id == "g1"


class TestResourceConstraints:
    """测试资源约束字段"""

    def test_resource_constraints_default_none(self):
        """测试：resource_constraints默认为None"""
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        assert session_ctx.resource_constraints is None

    def test_resource_constraints_can_be_set(self):
        """测试：可以设置resource_constraints"""
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(
            session_id="test",
            global_context=global_ctx,
            resource_constraints={"time_limit": 300, "max_parallel": 3},
        )

        assert session_ctx.resource_constraints["time_limit"] == 300
        assert session_ctx.resource_constraints["max_parallel"] == 3


class TestBackwardsCompatibility:
    """测试向后兼容性"""

    def test_import_from_context_manager_still_works(self):
        """测试：从context_manager导入SessionContext仍然有效

        验收标准：
        - 旧的导入路径仍然工作
        - 通过re-export机制
        """
        # 这个测试会在context_manager迁移后生效
        try:
            from src.domain.services.context_manager import GlobalContext, SessionContext

            global_ctx = GlobalContext(user_id="test_user")
            session_ctx = SessionContext(session_id="test", global_context=global_ctx)

            assert session_ctx.session_id == "test"
        except ImportError:
            pytest.skip("context_manager尚未迁移到re-export")

    def test_all_methods_preserved(self):
        """测试：所有方法都保留

        验收标准：
        - add_message
        - add_message_simple (新增)
        - push_goal
        - pop_goal
        - current_goal
        - add_decision
        - set_model_info
        - update_token_usage (如果存在)
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # 验证方法存在
        assert hasattr(session_ctx, "add_message")
        assert hasattr(session_ctx, "add_message_simple")
        assert hasattr(session_ctx, "push_goal")
        assert hasattr(session_ctx, "pop_goal")
        assert hasattr(session_ctx, "current_goal")
        assert hasattr(session_ctx, "add_decision")
        assert hasattr(session_ctx, "set_model_info")


class TestNewFieldsFromCodexReview:
    """测试Codex审查发现的新增字段"""

    def test_canvas_state_field_exists(self):
        """测试：canvas_state字段存在且默认为None

        验收标准：
        - SessionContext包含canvas_state字段
        - 默认值为None
        - 可以设置为dict
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # 验证默认值
        assert hasattr(session_ctx, "canvas_state")
        assert session_ctx.canvas_state is None

        # 验证可以设置
        session_ctx.canvas_state = {"node_positions": {"node1": {"x": 100, "y": 200}}}
        assert session_ctx.canvas_state["node_positions"]["node1"]["x"] == 100

    def test_global_goals_field_in_global_context(self):
        """测试：GlobalContext包含global_goals字段

        验收标准：
        - GlobalContext可以接受global_goals参数
        - 默认值为空列表
        - 返回副本，防止修改
        """
        from src.domain.entities.session_context import GlobalContext

        # 测试默认值
        global_ctx1 = GlobalContext(user_id="test_user")
        assert global_ctx1.global_goals == []

        # 测试设置值
        goals = [{"id": "g1", "desc": "Global goal 1"}]
        global_ctx2 = GlobalContext(user_id="test_user", global_goals=goals)
        assert global_ctx2.global_goals == goals

        # 测试返回副本（修改返回值不影响原始数据）
        returned_goals = global_ctx2.global_goals
        returned_goals.append({"id": "g2", "desc": "Should not affect original"})
        assert len(global_ctx2.global_goals) == 1  # 原始数据未改变

    def test_add_message_dual_signature_dict_style(self):
        """测试：add_message支持dict参数（context_manager风格）

        验收标准：
        - 接受message=dict参数
        - 向后兼容现有代码
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # context_manager风格
        session_ctx.add_message({"role": "user", "content": "Hello dict style"})

        assert len(session_ctx.conversation_history) == 1
        assert session_ctx.conversation_history[0]["role"] == "user"
        assert session_ctx.conversation_history[0]["content"] == "Hello dict style"

    def test_add_message_dual_signature_role_content_style(self):
        """测试：add_message支持role+content参数（context_bridge风格）

        验收标准：
        - 接受role和content参数
        - 自动添加timestamp
        - 与dict风格等效
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # context_bridge风格
        session_ctx.add_message(role="user", content="Hello role+content style")

        assert len(session_ctx.conversation_history) == 1
        message = session_ctx.conversation_history[0]
        assert message["role"] == "user"
        assert message["content"] == "Hello role+content style"
        assert "timestamp" in message  # 自动添加

    def test_add_message_dual_signature_mixed_usage(self):
        """测试：add_message两种风格混合使用

        验收标准：
        - 两种风格可以混合使用
        - 不会相互干扰
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # 混合使用
        session_ctx.add_message({"role": "user", "content": "Dict style"})
        session_ctx.add_message(role="assistant", content="Role+content style")
        session_ctx.add_message({"role": "user", "content": "Dict again"})

        assert len(session_ctx.conversation_history) == 3
        assert session_ctx.conversation_history[0]["content"] == "Dict style"
        assert session_ctx.conversation_history[1]["content"] == "Role+content style"
        assert session_ctx.conversation_history[2]["content"] == "Dict again"

    def test_add_message_dual_signature_invalid_params(self):
        """测试：add_message参数验证

        验收标准：
        - 缺少参数时抛出ValueError
        - 错误消息清晰
        """
        from src.domain.entities.session_context import GlobalContext, SessionContext

        global_ctx = GlobalContext(user_id="test_user")
        session_ctx = SessionContext(session_id="test", global_context=global_ctx)

        # 缺少所有参数
        with pytest.raises(ValueError, match="Must provide either"):
            session_ctx.add_message()

        # 只提供role
        with pytest.raises(ValueError, match="Must provide either"):
            session_ctx.add_message(role="user")

        # 只提供content
        with pytest.raises(ValueError, match="Must provide either"):
            session_ctx.add_message(content="Hello")
