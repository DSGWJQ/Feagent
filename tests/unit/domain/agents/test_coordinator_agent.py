"""测试：协调者Agent (CoordinatorAgent)

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- 协调者Agent是多Agent协作系统的"守门人"
- 负责验证对话Agent的决策
- 阻止违规决策，纠正偏差
- 监控系统运行状态

真实场景：
1. 对话Agent发布决策事件
2. 协调者作为中间件拦截事件
3. 验证决策是否合规
4. 通过 → 发布验证事件；拒绝 → 发布拒绝事件
5. 工作流Agent只执行验证通过的决策

核心能力：
- 规则引擎：定义和检查规则
- 决策验证：验证决策合法性
- 纠偏机制：拒绝或修正决策
- 流量监控：监控Agent间的事件流量
"""

import pytest


class TestCoordinatorAgentRuleEngine:
    """测试协调者Agent的规则引擎

    业务背景：
    - 协调者通过规则引擎检查决策
    - 规则可以动态添加和修改
    - 规则有优先级
    """

    def test_add_rule_to_engine(self):
        """测试：添加规则到引擎

        业务场景：
        - 系统管理员定义新规则
        - 规则添加到规则引擎

        验收标准：
        - 规则被正确添加
        - 可以查询已添加的规则
        """
        # Arrange
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        agent = CoordinatorAgent()

        rule = Rule(
            id="rule_1",
            name="禁止创建危险节点",
            description="不允许创建可能执行危险操作的节点",
            condition=lambda decision: decision.get("node_type") not in ["DANGEROUS"],
            priority=1,
        )

        # Act
        agent.add_rule(rule)

        # Assert
        assert len(agent.rules) == 1
        assert agent.rules[0].name == "禁止创建危险节点"

    def test_rules_checked_by_priority(self):
        """测试：规则按优先级检查

        业务场景：
        - 多个规则有不同优先级
        - 高优先级规则先检查

        验收标准：
        - 规则按优先级排序
        - 高优先级规则先执行
        """
        # Arrange
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        agent = CoordinatorAgent()

        check_order = []

        rule_low = Rule(
            id="rule_low",
            name="低优先级规则",
            condition=lambda d: (check_order.append("low"), True)[1],
            priority=10,
        )

        rule_high = Rule(
            id="rule_high",
            name="高优先级规则",
            condition=lambda d: (check_order.append("high"), True)[1],
            priority=1,
        )

        # 故意乱序添加
        agent.add_rule(rule_low)
        agent.add_rule(rule_high)

        # Act
        agent.validate_decision({"type": "test"})

        # Assert - 高优先级应该先执行
        assert check_order[0] == "high"
        assert check_order[1] == "low"

    def test_remove_rule_from_engine(self):
        """测试：从引擎移除规则

        业务场景：
        - 某规则不再需要
        - 从规则引擎移除

        验收标准：
        - 规则被移除
        - 不再影响后续验证
        """
        # Arrange
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        agent = CoordinatorAgent()

        rule = Rule(
            id="rule_1",
            name="临时规则",
            condition=lambda d: False,  # 总是失败
            priority=1,
        )

        agent.add_rule(rule)
        assert len(agent.rules) == 1

        # Act
        agent.remove_rule("rule_1")

        # Assert
        assert len(agent.rules) == 0


class TestCoordinatorAgentDecisionValidation:
    """测试协调者Agent的决策验证

    业务背景：
    - 协调者验证对话Agent的决策
    - 验证结果决定决策是否执行
    """

    def test_validate_valid_decision(self):
        """测试：验证有效决策

        业务场景：
        - 对话Agent决策创建LLM节点
        - 决策符合所有规则
        - 验证通过

        验收标准：
        - 返回验证通过
        - 没有错误信息
        """
        # Arrange
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        agent = CoordinatorAgent()

        # 添加允许LLM节点的规则
        agent.add_rule(
            Rule(
                id="rule_1",
                name="允许LLM节点",
                condition=lambda d: d.get("node_type") in ["LLM", "API", "START", "END"],
                priority=1,
            )
        )

        decision = {"type": "create_node", "node_type": "LLM", "config": {"model": "gpt-4"}}

        # Act
        result = agent.validate_decision(decision)

        # Assert
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_invalid_decision(self):
        """测试：验证无效决策

        业务场景：
        - 对话Agent决策创建危险节点
        - 决策违反安全规则
        - 验证失败

        验收标准：
        - 返回验证失败
        - 包含错误信息
        """
        # Arrange
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        agent = CoordinatorAgent()

        # 添加禁止危险操作的规则
        agent.add_rule(
            Rule(
                id="rule_security",
                name="禁止危险操作",
                condition=lambda d: "rm -rf" not in str(d.get("config", {})),
                error_message="检测到危险命令",
            )
        )

        decision = {
            "type": "create_node",
            "node_type": "CODE",
            "config": {"code": "os.system('rm -rf /')"},
        }

        # Act
        result = agent.validate_decision(decision)

        # Assert
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "危险" in str(result.errors)

    def test_validate_decision_with_multiple_rules(self):
        """测试：多规则验证决策

        业务场景：
        - 决策需要通过所有规则
        - 任何规则失败都会导致验证失败

        验收标准：
        - 所有规则都被检查
        - 收集所有失败的错误
        """
        # Arrange
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        agent = CoordinatorAgent()

        agent.add_rule(
            Rule(
                id="rule_1",
                name="必须有配置",
                condition=lambda d: d.get("config") is not None,
                error_message="决策必须包含配置",
            )
        )

        agent.add_rule(
            Rule(
                id="rule_2",
                name="必须有节点类型",
                condition=lambda d: d.get("node_type") is not None,
                error_message="决策必须指定节点类型",
            )
        )

        # 缺少config和node_type的决策
        decision = {"type": "create_node"}

        # Act
        result = agent.validate_decision(decision)

        # Assert
        assert result.is_valid is False
        assert len(result.errors) == 2


class TestCoordinatorAgentMiddleware:
    """测试协调者Agent作为中间件

    业务背景：
    - 协调者作为EventBus的中间件
    - 拦截对话Agent发布的决策事件
    - 验证后决定是否放行
    """

    @pytest.mark.asyncio
    async def test_middleware_passes_valid_decision(self):
        """测试：中间件放行有效决策

        业务场景：
        - 对话Agent发布决策事件
        - 协调者验证通过
        - 事件继续传播

        验收标准：
        - 有效决策被放行
        - 事件不被阻止
        """
        # Arrange
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        agent = CoordinatorAgent()

        # 允许所有决策的规则
        agent.add_rule(Rule(id="allow_all", name="允许所有", condition=lambda d: True))

        # 注册中间件
        event_bus.add_middleware(agent.as_middleware())

        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe(DecisionMadeEvent, handler)

        # Act
        event = DecisionMadeEvent(decision_type="create_node", payload={"node_type": "LLM"})
        await event_bus.publish(event)

        # Assert
        assert len(received_events) == 1

    @pytest.mark.asyncio
    async def test_middleware_blocks_invalid_decision(self):
        """测试：中间件阻止无效决策

        业务场景：
        - 对话Agent发布违规决策
        - 协调者验证失败
        - 事件被阻止

        验收标准：
        - 无效决策被阻止
        - 事件不传播到订阅者
        """
        # Arrange
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        agent = CoordinatorAgent()

        # 拒绝所有决策的规则
        agent.add_rule(
            Rule(
                id="deny_all",
                name="拒绝所有",
                condition=lambda d: False,
                error_message="所有决策被拒绝",
            )
        )

        event_bus.add_middleware(agent.as_middleware())

        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe(DecisionMadeEvent, handler)

        # Act
        event = DecisionMadeEvent(decision_type="create_node", payload={"node_type": "LLM"})
        await event_bus.publish(event)

        # Assert - 事件应该被阻止
        assert len(received_events) == 0

    @pytest.mark.asyncio
    async def test_middleware_publishes_rejection_event(self):
        """测试：中间件发布拒绝事件

        业务场景：
        - 决策被拒绝时
        - 发布拒绝事件通知对话Agent

        验收标准：
        - 拒绝时发布DecisionRejectedEvent
        - 事件包含拒绝原因
        """
        # Arrange
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionRejectedEvent,
            Rule,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        agent = CoordinatorAgent(event_bus=event_bus)

        agent.add_rule(
            Rule(
                id="deny_dangerous",
                name="拒绝危险操作",
                condition=lambda d: d.get("node_type") != "DANGEROUS",
                error_message="危险操作被拒绝",
            )
        )

        event_bus.add_middleware(agent.as_middleware())

        rejection_events = []

        async def capture_rejection(event):
            rejection_events.append(event)

        event_bus.subscribe(DecisionRejectedEvent, capture_rejection)

        # Act
        event = DecisionMadeEvent(decision_type="create_node", payload={"node_type": "DANGEROUS"})
        await event_bus.publish(event)

        # Assert
        assert len(rejection_events) == 1
        assert "危险" in rejection_events[0].reason


class TestCoordinatorAgentMonitoring:
    """测试协调者Agent的监控能力

    业务背景：
    - 协调者监控系统运行状态
    - 记录决策统计
    - 检测异常模式
    """

    def test_track_decision_statistics(self):
        """测试：跟踪决策统计

        业务场景：
        - 记录通过/拒绝的决策数量
        - 便于分析Agent行为模式

        验收标准：
        - 统计通过的决策数
        - 统计拒绝的决策数
        """
        # Arrange
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        agent = CoordinatorAgent()

        agent.add_rule(
            Rule(id="rule_1", name="只允许LLM", condition=lambda d: d.get("node_type") == "LLM")
        )

        # Act
        agent.validate_decision({"node_type": "LLM"})  # 通过
        agent.validate_decision({"node_type": "LLM"})  # 通过
        agent.validate_decision({"node_type": "API"})  # 拒绝

        # Assert
        stats = agent.get_statistics()
        assert stats["total"] == 3
        assert stats["passed"] == 2
        assert stats["rejected"] == 1

    def test_detect_high_rejection_rate(self):
        """测试：检测高拒绝率

        业务场景：
        - 如果拒绝率过高，可能表示对话Agent行为异常
        - 需要告警

        验收标准：
        - 可以设置拒绝率阈值
        - 超过阈值时触发告警
        """
        # Arrange
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        agent = CoordinatorAgent(rejection_rate_threshold=0.5)

        agent.add_rule(
            Rule(id="rule_1", name="严格规则", condition=lambda d: d.get("valid") is True)
        )

        # Act - 10个决策，8个被拒绝
        for _ in range(2):
            agent.validate_decision({"valid": True})
        for _ in range(8):
            agent.validate_decision({"valid": False})

        # Assert
        assert agent.is_rejection_rate_high() is True
        stats = agent.get_statistics()
        assert stats["rejection_rate"] == 0.8


class TestCoordinatorAgentDecisionCorrection:
    """测试协调者Agent的纠偏能力

    业务背景：
    - 某些决策可以被修正而非直接拒绝
    - 协调者提供修正建议
    """

    def test_suggest_correction_for_invalid_decision(self):
        """测试：为无效决策提供修正建议

        业务场景：
        - 决策略有问题但可以修正
        - 协调者提供修正建议

        验收标准：
        - 返回修正建议
        - 建议可以直接应用
        """
        # Arrange
        from src.domain.agents.coordinator_agent import CoordinatorAgent, Rule

        agent = CoordinatorAgent()

        # 规则：temperature必须在0-1之间
        def check_temperature(d):
            temp = d.get("config", {}).get("temperature", 0.7)
            return 0 <= temp <= 1

        def correct_temperature(d):
            config = d.get("config", {}).copy()
            temp = config.get("temperature", 0.7)
            if temp > 1:
                config["temperature"] = 1.0
            elif temp < 0:
                config["temperature"] = 0.0
            return {**d, "config": config}

        agent.add_rule(
            Rule(
                id="rule_temp",
                name="温度范围",
                condition=check_temperature,
                correction=correct_temperature,
                error_message="temperature必须在0-1之间",
            )
        )

        decision = {
            "type": "create_node",
            "node_type": "LLM",
            "config": {"temperature": 1.5},  # 超出范围
        }

        # Act
        result = agent.validate_decision(decision)

        # Assert
        assert result.is_valid is False
        assert result.correction is not None
        assert result.correction["config"]["temperature"] == 1.0


class TestCoordinatorAgentRealWorldScenario:
    """测试真实业务场景"""

    @pytest.mark.asyncio
    async def test_complete_decision_validation_flow(self):
        """测试：完整的决策验证流程

        业务场景：
        1. 对话Agent发布创建节点决策
        2. 协调者验证决策
        3. 验证通过 → 发布验证事件
        4. 工作流Agent收到验证事件执行

        这是协调者Agent的核心使用场景！

        验收标准：
        - 完整流程正常工作
        - 有效决策被执行
        - 无效决策被拒绝
        """
        # Arrange
        from src.domain.agents.conversation_agent import DecisionMadeEvent
        from src.domain.agents.coordinator_agent import (
            CoordinatorAgent,
            DecisionRejectedEvent,
            DecisionValidatedEvent,
            Rule,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        agent = CoordinatorAgent(event_bus=event_bus)

        # 添加安全规则
        agent.add_rule(
            Rule(
                id="rule_allowed_types",
                name="允许的节点类型",
                condition=lambda d: d.get("node_type")
                in ["START", "END", "LLM", "API", "CONDITION", "LOOP"],
                error_message="不允许的节点类型",
            )
        )

        agent.add_rule(
            Rule(
                id="rule_config_required",
                name="必须有配置",
                condition=lambda d: d.get("config") is not None
                or d.get("node_type") in ["START", "END"],
                error_message="必须提供节点配置",
            )
        )

        event_bus.add_middleware(agent.as_middleware())

        validated_events = []
        rejected_events = []

        async def capture_validated(event):
            validated_events.append(event)

        async def capture_rejected(event):
            rejected_events.append(event)

        event_bus.subscribe(DecisionValidatedEvent, capture_validated)
        event_bus.subscribe(DecisionRejectedEvent, capture_rejected)

        # Act 1 - 有效决策
        valid_decision = DecisionMadeEvent(
            decision_type="create_node",
            payload={"node_type": "LLM", "config": {"model": "gpt-4", "user_prompt": "test"}},
        )
        await event_bus.publish(valid_decision)

        # Act 2 - 无效决策（未知节点类型）
        invalid_decision = DecisionMadeEvent(
            decision_type="create_node", payload={"node_type": "UNKNOWN_TYPE", "config": {}}
        )
        await event_bus.publish(invalid_decision)

        # Assert
        assert len(validated_events) == 1
        assert validated_events[0].original_decision_id is not None

        assert len(rejected_events) == 1
        assert "不允许" in rejected_events[0].reason

        # 验证统计
        stats = agent.get_statistics()
        assert stats["total"] == 2
        assert stats["passed"] == 1
        assert stats["rejected"] == 1
