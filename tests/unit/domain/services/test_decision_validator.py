"""决策验证器测试 - Phase 7.2

TDD RED阶段：测试决策验证流程
"""

from datetime import datetime


class TestValidationStatus:
    """验证状态枚举测试"""

    def test_validation_status_should_have_approved(self):
        """验证状态应包含APPROVED"""
        from src.domain.services.decision_validator import ValidationStatus

        assert ValidationStatus.APPROVED.value == "approved"

    def test_validation_status_should_have_modified(self):
        """验证状态应包含MODIFIED"""
        from src.domain.services.decision_validator import ValidationStatus

        assert ValidationStatus.MODIFIED.value == "modified"

    def test_validation_status_should_have_rejected(self):
        """验证状态应包含REJECTED"""
        from src.domain.services.decision_validator import ValidationStatus

        assert ValidationStatus.REJECTED.value == "rejected"

    def test_validation_status_should_have_escalated(self):
        """验证状态应包含ESCALATED"""
        from src.domain.services.decision_validator import ValidationStatus

        assert ValidationStatus.ESCALATED.value == "escalated"


class TestDecisionRequest:
    """决策请求数据类测试"""

    def test_create_decision_request_with_required_fields(self):
        """创建决策请求应包含必需字段"""
        from src.domain.services.decision_validator import DecisionRequest

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={
                "node_type": "database",
                "config": {"sql": "SELECT * FROM users"},
            },
            context={"workflow_id": "wf_123"},
            requester="conversation_agent",
        )

        assert request.decision_id == "dec_123"
        assert request.decision_type == "create_node"
        assert request.payload["node_type"] == "database"
        assert request.requester == "conversation_agent"

    def test_decision_request_should_have_timestamp(self):
        """决策请求应有时间戳"""
        from src.domain.services.decision_validator import DecisionRequest

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={},
            context={},
            requester="test",
        )

        assert request.timestamp is not None
        assert isinstance(request.timestamp, datetime)


class TestValidationResult:
    """验证结果数据类测试"""

    def test_create_validation_result_approved(self):
        """创建批准的验证结果"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            ValidationResult,
            ValidationStatus,
        )

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={},
            context={},
            requester="test",
        )

        result = ValidationResult(
            status=ValidationStatus.APPROVED,
            original_request=request,
            violations=[],
            suggestions=[],
        )

        assert result.status == ValidationStatus.APPROVED
        assert result.modified_payload is None
        assert len(result.violations) == 0

    def test_create_validation_result_modified(self):
        """创建修正后批准的验证结果"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            ValidationResult,
            ValidationStatus,
        )

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={"sql": "SELECT * FROM users"},
            context={},
            requester="test",
        )

        result = ValidationResult(
            status=ValidationStatus.MODIFIED,
            original_request=request,
            modified_payload={"sql": "SELECT id, name FROM users"},
            violations=[],
            suggestions=["已限制查询字段"],
        )

        assert result.status == ValidationStatus.MODIFIED
        assert result.modified_payload is not None
        assert "SELECT id" in result.modified_payload["sql"]

    def test_create_validation_result_rejected(self):
        """创建拒绝的验证结果"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            ValidationResult,
            ValidationStatus,
        )
        from src.domain.services.rule_engine import RuleAction, RuleViolation

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={"tool": "shell"},
            context={},
            requester="test",
        )

        violation = RuleViolation(
            rule_id="tool_whitelist",
            rule_name="工具白名单检查",
            action=RuleAction.REJECT_DECISION,
            context={},
            message="工具 shell 不在允许列表中",
        )

        result = ValidationResult(
            status=ValidationStatus.REJECTED,
            original_request=request,
            violations=[violation],
            suggestions=["请使用允许的工具: database, python, http"],
        )

        assert result.status == ValidationStatus.REJECTED
        assert len(result.violations) == 1
        assert len(result.suggestions) == 1


class TestDecisionValidator:
    """决策验证器测试"""

    def test_validate_should_approve_valid_decision(self):
        """验证应批准有效决策"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            DecisionValidator,
            ValidationStatus,
        )
        from src.domain.services.enhanced_rule_repository import EnhancedRuleRepository

        repo = EnhancedRuleRepository()
        validator = DecisionValidator(rule_repository=repo)

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={
                "node_type": "database",
                "config": {"sql": "SELECT id FROM users"},
            },
            context={"workflow_id": "wf_123"},
            requester="conversation_agent",
        )

        result = validator.validate(request)

        assert result.status == ValidationStatus.APPROVED

    def test_validate_should_reject_tool_not_allowed(self):
        """验证应拒绝未授权的工具"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            DecisionValidator,
            ValidationStatus,
        )
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        # 添加工具白名单规则
        def check_tool(ctx):
            allowed = ["database", "python", "http"]
            tool = ctx.get("requested_tool") or ctx.get("payload", {}).get("node_type")
            return tool and tool not in allowed

        repo.add_rule(
            EnhancedRule(
                id="tool_whitelist",
                name="工具白名单检查",
                category=RuleCategory.TOOL,
                description="只允许特定工具",
                condition=check_tool,
                action=RuleAction.REJECT_DECISION,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )

        validator = DecisionValidator(rule_repository=repo)

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={"node_type": "shell"},  # shell 不在允许列表
            context={},
            requester="conversation_agent",
        )

        result = validator.validate(request)

        assert result.status == ValidationStatus.REJECTED
        assert len(result.violations) >= 1

    def test_validate_should_check_behavior_rules(self):
        """验证应检查行为边界规则"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            DecisionValidator,
            ValidationStatus,
        )
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()
        repo.add_rule(
            EnhancedRule(
                id="max_iterations",
                name="最大迭代次数",
                category=RuleCategory.BEHAVIOR,
                description="限制迭代次数",
                condition="iteration_count > 10",
                action=RuleAction.FORCE_TERMINATE,
                priority=1,
                source=RuleSource.SYSTEM,
            )
        )

        validator = DecisionValidator(rule_repository=repo)

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="continue",
            payload={},
            context={"iteration_count": 15},  # 超过限制
            requester="conversation_agent",
        )

        result = validator.validate(request)

        assert result.status == ValidationStatus.REJECTED

    def test_validate_should_check_goal_alignment(self):
        """验证应检查目标对齐"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            DecisionValidator,
            ValidationStatus,
        )
        from src.domain.services.enhanced_rule_repository import EnhancedRuleRepository
        from src.domain.services.rule_generator import GoalAlignmentChecker

        repo = EnhancedRuleRepository()
        goal_checker = GoalAlignmentChecker(threshold=0.5)

        validator = DecisionValidator(
            rule_repository=repo,
            goal_checker=goal_checker,
        )

        # 设置目标
        validator.set_goal("生成销售分析报表")

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={
                "action_description": "删除所有用户数据",
            },
            context={},
            requester="conversation_agent",
        )

        result = validator.validate(request)

        # 应该因为偏离目标而被拒绝或修正
        assert result.status in [ValidationStatus.REJECTED, ValidationStatus.MODIFIED]

    def test_validate_should_suggest_corrections(self):
        """验证应提供修正建议"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            DecisionValidator,
        )
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()
        repo.add_rule(
            EnhancedRule(
                id="low_confidence",
                name="低置信度警告",
                category=RuleCategory.BEHAVIOR,
                description="决策置信度过低",
                condition="confidence < 0.5",
                action=RuleAction.SUGGEST_CORRECTION,
                priority=3,
                source=RuleSource.SYSTEM,
                metadata={"suggestion": "请提供更多上下文信息以提高置信度"},
            )
        )

        validator = DecisionValidator(rule_repository=repo)

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={},
            context={"confidence": 0.3},  # 低置信度
            requester="conversation_agent",
        )

        result = validator.validate(request)

        # 应该有建议
        assert len(result.suggestions) >= 1


class TestDecisionValidatorAutoCorrection:
    """决策验证器自动修正测试"""

    def test_should_auto_correct_sensitive_query(self):
        """应自动修正敏感数据查询"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            DecisionValidator,
            ValidationStatus,
        )
        from src.domain.services.enhanced_rule_repository import (
            EnhancedRule,
            EnhancedRuleRepository,
            RuleCategory,
            RuleSource,
        )
        from src.domain.services.rule_engine import RuleAction

        repo = EnhancedRuleRepository()

        # 添加敏感字段过滤规则（带修正逻辑）
        def check_sensitive_fields(ctx):
            sql = ctx.get("payload", {}).get("config", {}).get("sql", "")
            return "SELECT *" in sql.upper()

        repo.add_rule(
            EnhancedRule(
                id="sensitive_query",
                name="敏感查询检查",
                category=RuleCategory.DATA,
                description="禁止SELECT *",
                condition=check_sensitive_fields,
                action=RuleAction.SUGGEST_CORRECTION,
                priority=1,
                source=RuleSource.SYSTEM,
                metadata={
                    "correction_type": "field_restriction",
                    "suggestion": "请指定具体字段而不是SELECT *",
                },
            )
        )

        validator = DecisionValidator(rule_repository=repo)

        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={
                "node_type": "database",
                "config": {"sql": "SELECT * FROM users"},
            },
            context={},
            requester="conversation_agent",
        )

        result = validator.validate(request)

        # 应该被标记为需要修正
        assert result.status in [ValidationStatus.MODIFIED, ValidationStatus.REJECTED]
        assert len(result.suggestions) >= 1


class TestDecisionValidatorWithRuleGenerator:
    """决策验证器与规则生成器集成测试"""

    def test_validate_with_generated_rules(self):
        """使用生成的规则进行验证"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            DecisionValidator,
            ValidationStatus,
        )
        from src.domain.services.enhanced_rule_repository import EnhancedRuleRepository
        from src.domain.services.rule_generator import RuleGenerator

        # 生成规则
        generator = RuleGenerator()
        rules = generator.generate_from_user_input(
            start="销售数据Excel",
            goal="生成月度销售分析报表",
            description="客户姓名需要脱敏",
        )

        # 添加到规则库
        repo = EnhancedRuleRepository()
        for rule in rules:
            repo.add_rule(rule)

        validator = DecisionValidator(rule_repository=repo)

        # 测试相关行动
        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={
                "action_description": "查询销售数据并生成报表",
            },
            context={
                "alignment_score": 0.8,
            },
            requester="conversation_agent",
        )

        result = validator.validate(request)

        # 应该通过（行动与目标一致）
        assert result.status in [ValidationStatus.APPROVED, ValidationStatus.MODIFIED]

    def test_validate_with_tool_rules(self):
        """使用工具规则进行验证"""
        from src.domain.services.decision_validator import (
            DecisionRequest,
            DecisionValidator,
            ValidationStatus,
        )
        from src.domain.services.enhanced_rule_repository import EnhancedRuleRepository
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()
        rules = generator.generate_tool_rules(
            allowed_tools=["database", "python"],
            tool_configs={
                "database": {"forbidden_operations": ["DROP", "DELETE"]},
            },
        )

        repo = EnhancedRuleRepository()
        for rule in rules:
            repo.add_rule(rule)

        validator = DecisionValidator(rule_repository=repo)

        # 测试禁止的操作
        request = DecisionRequest(
            decision_id="dec_123",
            decision_type="create_node",
            payload={
                "requested_tool": "database",
                "operation": "DROP TABLE users",
            },
            context={},
            requester="conversation_agent",
        )

        result = validator.validate(request)

        # 应该被拒绝
        assert result.status == ValidationStatus.REJECTED
