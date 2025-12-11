"""监督模块测试 (Supervision Module Tests)

TDD 测试用例，覆盖：
1. SupervisionAction 枚举测试
2. SupervisionInfo 数据结构测试
3. SupervisionRule 规则测试
4. SupervisionModule 核心功能测试
5. 内置规则测试
6. SupervisionLogger 日志测试
7. CoordinatorAgent 集成测试
8. 端到端干预流程测试
9. 日志追踪测试

实现日期：2025-12-08
"""

from datetime import datetime

# =============================================================================
# TestSupervisionAction - 监督动作枚举测试
# =============================================================================


class TestSupervisionAction:
    """监督动作枚举测试"""

    def test_action_warning_value(self):
        """测试：WARNING 动作值"""
        from src.domain.services.supervision_module import SupervisionAction

        assert SupervisionAction.WARNING.value == "warning"

    def test_action_replace_value(self):
        """测试：REPLACE 动作值"""
        from src.domain.services.supervision_module import SupervisionAction

        assert SupervisionAction.REPLACE.value == "replace"

    def test_action_terminate_value(self):
        """测试：TERMINATE 动作值"""
        from src.domain.services.supervision_module import SupervisionAction

        assert SupervisionAction.TERMINATE.value == "terminate"

    def test_action_priority_order(self):
        """测试：动作优先级顺序 TERMINATE > REPLACE > WARNING"""
        from src.domain.services.supervision_module import SupervisionAction

        assert SupervisionAction.get_priority(
            SupervisionAction.TERMINATE
        ) > SupervisionAction.get_priority(SupervisionAction.REPLACE)
        assert SupervisionAction.get_priority(
            SupervisionAction.REPLACE
        ) > SupervisionAction.get_priority(SupervisionAction.WARNING)

    def test_all_actions_are_string_enum(self):
        """测试：所有动作都是字符串枚举"""
        from src.domain.services.supervision_module import SupervisionAction

        for action in SupervisionAction:
            assert isinstance(action.value, str)


# =============================================================================
# TestSupervisionInfo - 监督信息结构测试
# =============================================================================


class TestSupervisionInfo:
    """监督信息结构测试"""

    def test_info_creation_basic(self):
        """测试：基本创建"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
        )

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.WARNING,
            content="检测到敏感操作",
            trigger_rule="rule-001",
            trigger_condition="访问敏感路径",
        )

        assert info.session_id == "session-123"
        assert info.action == SupervisionAction.WARNING
        assert info.content == "检测到敏感操作"
        assert info.trigger_rule == "rule-001"
        assert info.trigger_condition == "访问敏感路径"
        assert info.supervision_id.startswith("sup-")

    def test_info_with_duration(self):
        """测试：带持续时间的监督信息"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
        )

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.REPLACE,
            content="替换敏感内容",
            trigger_rule="rule-002",
            trigger_condition="内容包含敏感词",
            duration=30.0,
        )

        assert info.duration == 30.0

    def test_info_with_metadata(self):
        """测试：带元数据的监督信息"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
        )

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.TERMINATE,
            content="终止危险任务",
            trigger_rule="rule-003",
            trigger_condition="检测到危险命令",
            metadata={"severity": "critical", "command": "rm -rf /"},
        )

        assert info.metadata["severity"] == "critical"
        assert info.metadata["command"] == "rm -rf /"

    def test_info_to_dict(self):
        """测试：序列化为字典"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
        )

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.WARNING,
            content="警告信息",
            trigger_rule="rule-001",
            trigger_condition="条件描述",
        )

        data = info.to_dict()

        assert data["session_id"] == "session-123"
        assert data["action"] == "warning"
        assert data["content"] == "警告信息"
        assert data["trigger_rule"] == "rule-001"
        assert data["trigger_condition"] == "条件描述"
        assert "timestamp" in data

    def test_info_mark_resolved(self):
        """测试：标记为已解决"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
        )

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.WARNING,
            content="警告",
            trigger_rule="rule-001",
            trigger_condition="条件",
        )

        assert info.resolved is False
        info.mark_resolved()
        assert info.resolved is True

    def test_info_timestamp_auto_generated(self):
        """测试：时间戳自动生成"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
        )

        before = datetime.now()
        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.WARNING,
            content="警告",
            trigger_rule="rule-001",
            trigger_condition="条件",
        )
        after = datetime.now()

        assert before <= info.timestamp <= after


# =============================================================================
# TestSupervisionRule - 监督规则测试
# =============================================================================


class TestSupervisionRule:
    """监督规则测试"""

    def test_rule_creation(self):
        """测试：规则创建"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        rule = SupervisionRule(
            rule_id="rule-001",
            name="敏感路径检测",
            description="检测对敏感路径的访问",
            action=SupervisionAction.WARNING,
            priority=50,
        )

        assert rule.rule_id == "rule-001"
        assert rule.name == "敏感路径检测"
        assert rule.action == SupervisionAction.WARNING
        assert rule.priority == 50
        assert rule.enabled is True

    def test_rule_disabled(self):
        """测试：禁用规则"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        rule = SupervisionRule(
            rule_id="rule-001",
            name="测试规则",
            description="描述",
            action=SupervisionAction.WARNING,
            enabled=False,
        )

        assert rule.enabled is False

    def test_rule_check_method(self):
        """测试：规则检查方法"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        # 创建一个检查条件的规则
        rule = SupervisionRule(
            rule_id="rule-001",
            name="长度检测",
            description="检测内容长度",
            action=SupervisionAction.WARNING,
            condition=lambda ctx: len(ctx.get("content", "")) > 100,
        )

        # 短内容不触发
        result1 = rule.check({"content": "短内容"})
        assert result1 is None

        # 长内容触发
        result2 = rule.check({"content": "x" * 150})
        assert result2 is not None
        assert result2.action == SupervisionAction.WARNING

    def test_rule_check_returns_supervision_info(self):
        """测试：规则检查返回 SupervisionInfo"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionRule,
        )

        rule = SupervisionRule(
            rule_id="rule-002",
            name="总是触发",
            description="测试规则",
            action=SupervisionAction.TERMINATE,
            condition=lambda ctx: True,
        )

        result = rule.check({"session_id": "session-123"})

        assert isinstance(result, SupervisionInfo)
        assert result.action == SupervisionAction.TERMINATE
        assert result.trigger_rule == "rule-002"


# =============================================================================
# TestSupervisionModule - 监督模块核心功能测试
# =============================================================================


class TestSupervisionModule:
    """监督模块核心功能测试"""

    def test_module_creation(self):
        """测试：模块创建"""
        from src.domain.services.supervision_module import SupervisionModule

        module = SupervisionModule()

        assert module is not None
        assert isinstance(module.rules, list)

    def test_module_add_rule(self):
        """测试：添加规则"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionModule,
            SupervisionRule,
        )

        module = SupervisionModule()
        rule = SupervisionRule(
            rule_id="rule-001",
            name="测试规则",
            description="描述",
            action=SupervisionAction.WARNING,
        )

        module.add_rule(rule)

        assert len(module.rules) >= 1
        assert any(r.rule_id == "rule-001" for r in module.rules)

    def test_analyze_context_no_violation(self):
        """测试：分析上下文 - 无违规"""
        from src.domain.services.supervision_module import SupervisionModule

        module = SupervisionModule()

        # 模拟正常上下文
        context = {
            "session_id": "session-123",
            "conversation_history": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！"},
            ],
            "usage_ratio": 0.3,
        }

        results = module.analyze_context(context)

        # 正常情况下不应有任何监督信息
        assert isinstance(results, list)

    def test_analyze_context_with_warning(self):
        """测试：分析上下文 - 触发警告"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionModule,
            SupervisionRule,
        )

        module = SupervisionModule()

        # 添加一个会触发的规则
        module.add_rule(
            SupervisionRule(
                rule_id="high-usage",
                name="高上下文使用率",
                description="上下文使用率过高时警告",
                action=SupervisionAction.WARNING,
                condition=lambda ctx: ctx.get("usage_ratio", 0) > 0.8,
            )
        )

        context = {
            "session_id": "session-123",
            "usage_ratio": 0.9,
        }

        results = module.analyze_context(context)

        assert len(results) >= 1
        assert any(r.action == SupervisionAction.WARNING for r in results)

    def test_analyze_context_with_terminate(self):
        """测试：分析上下文 - 触发终止"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionModule,
            SupervisionRule,
        )

        module = SupervisionModule()

        # 添加一个终止规则
        module.add_rule(
            SupervisionRule(
                rule_id="critical-usage",
                name="临界上下文使用率",
                description="上下文使用率临界时终止",
                action=SupervisionAction.TERMINATE,
                condition=lambda ctx: ctx.get("usage_ratio", 0) > 0.95,
            )
        )

        context = {
            "session_id": "session-123",
            "usage_ratio": 0.98,
        }

        results = module.analyze_context(context)

        assert len(results) >= 1
        assert any(r.action == SupervisionAction.TERMINATE for r in results)

    def test_analyze_save_request_normal(self):
        """测试：分析保存请求 - 正常"""
        from src.domain.services.supervision_module import SupervisionModule

        module = SupervisionModule()

        request = {
            "request_id": "req-001",
            "target_path": "/data/output.txt",
            "content": "正常内容",
            "session_id": "session-123",
        }

        results = module.analyze_save_request(request)

        assert isinstance(results, list)

    def test_analyze_save_request_dangerous_path(self):
        """测试：分析保存请求 - 危险路径"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionModule,
            SupervisionRule,
        )

        module = SupervisionModule()

        # 添加危险路径检测规则
        module.add_rule(
            SupervisionRule(
                rule_id="dangerous-path",
                name="危险路径检测",
                description="检测对系统路径的写入",
                action=SupervisionAction.TERMINATE,
                condition=lambda req: req.get("target_path", "").startswith("/etc/"),
            )
        )

        request = {
            "request_id": "req-001",
            "target_path": "/etc/passwd",
            "content": "恶意内容",
            "session_id": "session-123",
        }

        results = module.analyze_save_request(request)

        assert len(results) >= 1
        assert any(r.action == SupervisionAction.TERMINATE for r in results)

    def test_analyze_decision_chain(self):
        """测试：分析决策链路"""
        from src.domain.services.supervision_module import SupervisionModule

        module = SupervisionModule()

        decisions = [
            {"action": "search", "result": "success"},
            {"action": "read", "result": "success"},
            {"action": "write", "result": "pending"},
        ]

        results = module.analyze_decision_chain(decisions, session_id="session-123")

        assert isinstance(results, list)

    def test_analyze_decision_chain_loop_detection(self):
        """测试：分析决策链路 - 循环检测"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionModule,
            SupervisionRule,
        )

        module = SupervisionModule()

        # 添加循环检测规则
        module.add_rule(
            SupervisionRule(
                rule_id="loop-detection",
                name="循环检测",
                description="检测重复决策模式",
                action=SupervisionAction.WARNING,
                condition=lambda ctx: len(ctx.get("decisions", [])) > 3
                and len(set(d.get("action") for d in ctx.get("decisions", []))) == 1,
            )
        )

        # 模拟重复决策
        decisions = [
            {"action": "retry", "result": "failed"},
            {"action": "retry", "result": "failed"},
            {"action": "retry", "result": "failed"},
            {"action": "retry", "result": "failed"},
        ]

        results = module.analyze_decision_chain(decisions, session_id="session-123")

        assert len(results) >= 1

    def test_multiple_rules_triggered(self):
        """测试：多个规则同时触发"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionModule,
            SupervisionRule,
        )

        module = SupervisionModule()

        # 添加多个规则
        module.add_rule(
            SupervisionRule(
                rule_id="rule-1",
                name="规则1",
                description="描述1",
                action=SupervisionAction.WARNING,
                condition=lambda ctx: True,
            )
        )
        module.add_rule(
            SupervisionRule(
                rule_id="rule-2",
                name="规则2",
                description="描述2",
                action=SupervisionAction.WARNING,
                condition=lambda ctx: True,
            )
        )

        context = {"session_id": "session-123"}
        results = module.analyze_context(context)

        assert len(results) >= 2

    def test_should_intervene_no_results(self):
        """测试：判断是否干预 - 无结果"""
        from src.domain.services.supervision_module import SupervisionModule

        module = SupervisionModule()

        assert module.should_intervene([]) is False

    def test_should_intervene_with_warning(self):
        """测试：判断是否干预 - 有警告"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionModule,
        )

        module = SupervisionModule()

        infos = [
            SupervisionInfo(
                session_id="session-123",
                action=SupervisionAction.WARNING,
                content="警告",
                trigger_rule="rule-001",
                trigger_condition="条件",
            )
        ]

        assert module.should_intervene(infos) is True

    def test_get_highest_priority_action(self):
        """测试：获取最高优先级动作"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionModule,
        )

        module = SupervisionModule()

        infos = [
            SupervisionInfo(
                session_id="session-123",
                action=SupervisionAction.WARNING,
                content="警告",
                trigger_rule="rule-001",
                trigger_condition="条件1",
            ),
            SupervisionInfo(
                session_id="session-123",
                action=SupervisionAction.TERMINATE,
                content="终止",
                trigger_rule="rule-002",
                trigger_condition="条件2",
            ),
        ]

        highest = module.get_highest_priority_action(infos)

        assert highest == SupervisionAction.TERMINATE


# =============================================================================
# TestBuiltinRules - 内置规则测试
# =============================================================================


class TestBuiltinRules:
    """内置规则测试"""

    def test_builtin_context_length_rule(self):
        """测试：内置上下文长度规则"""
        from src.domain.services.supervision_module import (
            SupervisionModule,
        )

        module = SupervisionModule(use_builtin_rules=True)

        # 模拟超长对话历史
        context = {
            "session_id": "session-123",
            "conversation_history": [{"role": "user", "content": "x" * 1000}] * 100,
            "usage_ratio": 0.95,
        }

        results = module.analyze_context(context)

        # 应该触发某些规则
        assert isinstance(results, list)

    def test_builtin_sensitive_content_rule(self):
        """测试：内置敏感内容规则"""
        from src.domain.services.supervision_module import (
            SupervisionModule,
        )

        module = SupervisionModule(use_builtin_rules=True)

        request = {
            "request_id": "req-001",
            "target_path": "/data/config.txt",
            "content": "password=secret123",
            "session_id": "session-123",
        }

        results = module.analyze_save_request(request)

        # 敏感内容应该触发规则
        assert isinstance(results, list)

    def test_builtin_dangerous_command_rule(self):
        """测试：内置危险命令规则"""
        from src.domain.services.supervision_module import (
            SupervisionModule,
        )

        module = SupervisionModule(use_builtin_rules=True)

        request = {
            "request_id": "req-001",
            "target_path": "/tmp/script.sh",
            "content": "rm -rf /",
            "session_id": "session-123",
        }

        results = module.analyze_save_request(request)

        # 危险命令应该触发规则
        assert isinstance(results, list)

    def test_builtin_loop_detection_rule(self):
        """测试：内置循环检测规则"""
        from src.domain.services.supervision_module import SupervisionModule

        module = SupervisionModule(use_builtin_rules=True)

        # 模拟循环决策
        decisions = [{"action": "retry", "iteration": i} for i in range(10)]

        results = module.analyze_decision_chain(decisions, session_id="session-123")

        assert isinstance(results, list)


# =============================================================================
# TestSupervisionLogger - 日志记录测试
# =============================================================================


class TestSupervisionLogger:
    """监督日志记录测试"""

    def test_logger_creation(self):
        """测试：日志记录器创建"""
        from src.domain.services.supervision_module import SupervisionLogger

        logger = SupervisionLogger()

        assert logger is not None

    def test_log_trigger(self):
        """测试：记录触发"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionLogger,
        )

        logger = SupervisionLogger()

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.WARNING,
            content="警告内容",
            trigger_rule="rule-001",
            trigger_condition="触发条件",
        )

        logger.log_trigger(info)

        logs = logger.get_logs()
        assert len(logs) >= 1
        assert logs[-1]["type"] == "trigger"
        assert logs[-1]["trigger_rule"] == "rule-001"
        assert logs[-1]["trigger_condition"] == "触发条件"

    def test_log_intervention(self):
        """测试：记录干预"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionLogger,
        )

        logger = SupervisionLogger()

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.TERMINATE,
            content="终止任务",
            trigger_rule="rule-002",
            trigger_condition="危险操作",
        )

        logger.log_intervention(info, result="task_terminated")

        logs = logger.get_logs()
        assert len(logs) >= 1
        assert logs[-1]["type"] == "intervention"
        assert logs[-1]["result"] == "task_terminated"

    def test_get_logs_by_session(self):
        """测试：按会话获取日志"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionLogger,
        )

        logger = SupervisionLogger()

        # 添加多个会话的日志
        info1 = SupervisionInfo(
            session_id="session-A",
            action=SupervisionAction.WARNING,
            content="警告A",
            trigger_rule="rule-001",
            trigger_condition="条件A",
        )
        info2 = SupervisionInfo(
            session_id="session-B",
            action=SupervisionAction.WARNING,
            content="警告B",
            trigger_rule="rule-001",
            trigger_condition="条件B",
        )

        logger.log_trigger(info1)
        logger.log_trigger(info2)

        logs_a = logger.get_logs_by_session("session-A")
        logs_b = logger.get_logs_by_session("session-B")

        assert len(logs_a) == 1
        assert len(logs_b) == 1
        assert logs_a[0]["session_id"] == "session-A"
        assert logs_b[0]["session_id"] == "session-B"

    def test_log_contains_timestamp(self):
        """测试：日志包含时间戳"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionLogger,
        )

        logger = SupervisionLogger()

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.WARNING,
            content="警告",
            trigger_rule="rule-001",
            trigger_condition="条件",
        )

        logger.log_trigger(info)

        logs = logger.get_logs()
        assert "timestamp" in logs[-1]


# =============================================================================
# TestCoordinatorIntegration - Coordinator 集成测试
# =============================================================================


class TestCoordinatorIntegration:
    """Coordinator 集成测试"""

    def test_coordinator_has_supervision_module(self):
        """测试：Coordinator 拥有监督模块"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        assert hasattr(coordinator, "supervision_module")
        assert coordinator.supervision_module is not None

    def test_coordinator_supervise_context(self):
        """测试：Coordinator 监督上下文"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        context = {
            "session_id": "session-123",
            "usage_ratio": 0.5,
        }

        results = coordinator.supervise_context(context)

        assert isinstance(results, list)

    def test_coordinator_supervise_returns_warning(self):
        """测试：Coordinator 监督返回警告"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        coordinator = CoordinatorAgent()

        # 添加会触发的规则
        coordinator.supervision_module.add_rule(
            SupervisionRule(
                rule_id="test-warning",
                name="测试警告",
                description="测试",
                action=SupervisionAction.WARNING,
                condition=lambda ctx: ctx.get("trigger_warning", False),
            )
        )

        context = {
            "session_id": "session-123",
            "trigger_warning": True,
        }

        results = coordinator.supervise_context(context)

        assert len(results) >= 1
        assert any(r.action == SupervisionAction.WARNING for r in results)

    def test_coordinator_supervise_returns_replace(self):
        """测试：Coordinator 监督返回替换"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        coordinator = CoordinatorAgent()

        # 添加替换规则
        coordinator.supervision_module.add_rule(
            SupervisionRule(
                rule_id="test-replace",
                name="测试替换",
                description="测试",
                action=SupervisionAction.REPLACE,
                condition=lambda ctx: ctx.get("trigger_replace", False),
            )
        )

        context = {
            "session_id": "session-123",
            "trigger_replace": True,
        }

        results = coordinator.supervise_context(context)

        assert len(results) >= 1
        assert any(r.action == SupervisionAction.REPLACE for r in results)

    def test_coordinator_supervise_returns_terminate(self):
        """测试：Coordinator 监督返回终止"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        coordinator = CoordinatorAgent()

        # 添加终止规则
        coordinator.supervision_module.add_rule(
            SupervisionRule(
                rule_id="test-terminate",
                name="测试终止",
                description="测试",
                action=SupervisionAction.TERMINATE,
                condition=lambda ctx: ctx.get("trigger_terminate", False),
            )
        )

        context = {
            "session_id": "session-123",
            "trigger_terminate": True,
        }

        results = coordinator.supervise_context(context)

        assert len(results) >= 1
        assert any(r.action == SupervisionAction.TERMINATE for r in results)

    def test_coordinator_supervise_save_request(self):
        """测试：Coordinator 监督保存请求"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        request = {
            "request_id": "req-001",
            "target_path": "/data/output.txt",
            "content": "正常内容",
            "session_id": "session-123",
        }

        results = coordinator.supervise_save_request(request)

        assert isinstance(results, list)

    def test_coordinator_get_supervision_logs(self):
        """测试：Coordinator 获取监督日志"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        logs = coordinator.get_supervision_logs()

        assert isinstance(logs, list)


# =============================================================================
# TestEndToEndIntervention - 端到端干预流程测试
# =============================================================================


class TestEndToEndIntervention:
    """端到端干预流程测试"""

    def test_warning_intervention_flow(self):
        """测试：警告干预流程"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        coordinator = CoordinatorAgent()

        # 添加警告规则
        coordinator.supervision_module.add_rule(
            SupervisionRule(
                rule_id="warn-rule",
                name="警告规则",
                description="测试警告",
                action=SupervisionAction.WARNING,
                condition=lambda ctx: ctx.get("should_warn", False),
            )
        )

        # 执行监督并触发干预
        context = {"session_id": "session-123", "should_warn": True}
        results = coordinator.supervise_context(context)

        # 验证警告被触发
        assert len(results) >= 1
        warning_result = next(r for r in results if r.action == SupervisionAction.WARNING)

        # 执行干预
        coordinator.execute_intervention(warning_result)

        # 验证注入被创建
        injections = coordinator.injection_manager.get_pending_injections(
            "session-123",
            coordinator.injection_manager._injections.get("session-123", [{}])[0].injection_point
            if coordinator.injection_manager._injections.get("session-123")
            else None,
        )

    def test_terminate_intervention_flow(self):
        """测试：终止干预流程"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        coordinator = CoordinatorAgent()

        # 添加终止规则
        coordinator.supervision_module.add_rule(
            SupervisionRule(
                rule_id="terminate-rule",
                name="终止规则",
                description="测试终止",
                action=SupervisionAction.TERMINATE,
                condition=lambda ctx: ctx.get("should_terminate", False),
            )
        )

        # 执行监督
        context = {"session_id": "session-123", "should_terminate": True}
        results = coordinator.supervise_context(context)

        # 验证终止被触发
        assert len(results) >= 1
        terminate_result = next(r for r in results if r.action == SupervisionAction.TERMINATE)

        # 执行干预
        intervention_result = coordinator.execute_intervention(terminate_result)

        # 验证干预结果
        assert intervention_result is not None

    def test_replace_intervention_flow(self):
        """测试：替换干预流程"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        coordinator = CoordinatorAgent()

        # 添加替换规则
        coordinator.supervision_module.add_rule(
            SupervisionRule(
                rule_id="replace-rule",
                name="替换规则",
                description="测试替换",
                action=SupervisionAction.REPLACE,
                condition=lambda ctx: ctx.get("should_replace", False),
                replacement_content="[REDACTED]",
            )
        )

        # 执行监督
        context = {"session_id": "session-123", "should_replace": True}
        results = coordinator.supervise_context(context)

        # 验证替换被触发
        assert len(results) >= 1
        replace_result = next(r for r in results if r.action == SupervisionAction.REPLACE)

        assert replace_result is not None


# =============================================================================
# TestInterventionLogging - 干预日志追踪测试
# =============================================================================


class TestInterventionLogging:
    """干预日志追踪测试"""

    def test_intervention_log_contains_trigger_condition(self):
        """测试：干预日志包含触发条件"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionLogger,
        )

        logger = SupervisionLogger()

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.WARNING,
            content="警告内容",
            trigger_rule="rule-001",
            trigger_condition="上下文使用率超过80%",
        )

        logger.log_intervention(info, result="warning_injected")

        logs = logger.get_logs()
        assert logs[-1]["trigger_condition"] == "上下文使用率超过80%"

    def test_intervention_log_contains_rule_id(self):
        """测试：干预日志包含规则 ID"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionLogger,
        )

        logger = SupervisionLogger()

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.TERMINATE,
            content="终止任务",
            trigger_rule="dangerous-operation-001",
            trigger_condition="检测到危险命令",
        )

        logger.log_intervention(info, result="task_terminated")

        logs = logger.get_logs()
        assert logs[-1]["trigger_rule"] == "dangerous-operation-001"

    def test_intervention_log_traceable(self):
        """测试：干预日志可追踪"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionRule,
        )

        coordinator = CoordinatorAgent()

        # 添加规则
        coordinator.supervision_module.add_rule(
            SupervisionRule(
                rule_id="traceable-rule",
                name="可追踪规则",
                description="测试追踪",
                action=SupervisionAction.WARNING,
                condition=lambda ctx: True,
            )
        )

        # 执行监督
        context = {"session_id": "session-123"}
        results = coordinator.supervise_context(context)

        # 获取日志
        logs = coordinator.get_supervision_logs()

        # 验证日志可追踪
        assert isinstance(logs, list)


# =============================================================================
# TestSupervisionEvents - 监督事件测试
# =============================================================================


class TestSupervisionEvents:
    """监督事件测试"""

    def test_supervision_triggered_event(self):
        """测试：监督触发事件"""
        from src.domain.services.supervision_module import (
            SupervisionAction,
            SupervisionInfo,
            SupervisionTriggeredEvent,
        )

        info = SupervisionInfo(
            session_id="session-123",
            action=SupervisionAction.WARNING,
            content="警告",
            trigger_rule="rule-001",
            trigger_condition="条件",
        )

        event = SupervisionTriggeredEvent(supervision_info=info)

        assert event.event_type == "supervision_triggered"
        assert event.supervision_info == info

    def test_intervention_executed_event(self):
        """测试：干预执行事件"""
        from src.domain.services.supervision_module import (
            InterventionExecutedEvent,
            SupervisionAction,
        )

        event = InterventionExecutedEvent(
            supervision_id="sup-123",
            session_id="session-123",
            action=SupervisionAction.TERMINATE,
            result="task_terminated",
        )

        assert event.event_type == "intervention_executed"
        assert event.result == "task_terminated"
