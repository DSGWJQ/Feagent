"""测试：干预策略系统

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- 当检测到违规时，需要决定干预级别和动作
- 干预级别：NONE -> LOW -> MEDIUM -> HIGH -> CRITICAL
- 干预动作：PASS -> WARN -> SUGGEST -> REJECT -> TERMINATE

真实场景：
1. 协调者检测到决策问题
2. 干预策略评估问题严重程度
3. 决定采取的干预动作
4. 返回干预指令

核心能力：
- 严重程度计算：综合多个维度评估
- 干预决策：根据严重程度选择动作
- 干预执行：返回具体的干预指令
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSeverityLevel:
    """测试严重程度级别（Phase 35.0: 重命名 SeverityLevel → SeverityLevel）"""

    def test_severity_level_ordering(self):
        """测试：严重程度级别排序

        验收标准：
        - NONE < LOW < MEDIUM < HIGH < CRITICAL
        """
        from src.domain.services.intervention_strategy import SeverityLevel

        assert SeverityLevel.NONE.value < SeverityLevel.LOW.value
        assert SeverityLevel.LOW.value < SeverityLevel.MEDIUM.value
        assert SeverityLevel.MEDIUM.value < SeverityLevel.HIGH.value
        assert SeverityLevel.HIGH.value < SeverityLevel.CRITICAL.value


class TestInterventionAction:
    """测试干预动作"""

    def test_intervention_action_types(self):
        """测试：干预动作类型

        验收标准：
        - 包含所有预定义动作
        """
        from src.domain.services.intervention_strategy import InterventionAction

        actions = [a.value for a in InterventionAction]
        assert "pass" in actions
        assert "warn" in actions
        assert "suggest" in actions
        assert "reject" in actions
        assert "terminate" in actions


class TestSeverityCalculator:
    """测试严重程度计算器

    业务背景：
    - 综合多个维度计算严重程度
    - 严重程度决定干预级别
    """

    def test_calculate_severity_no_violations(self):
        """测试：无违规时的严重程度

        验收标准：
        - 严重程度为0
        """
        from src.domain.services.intervention_strategy import SeverityCalculator

        calculator = SeverityCalculator()

        severity = calculator.calculate(
            rule_violations=[], alignment_score=0.9, resource_usage_ratio=0.3
        )

        assert severity == 0.0

    def test_calculate_severity_with_rule_violations(self):
        """测试：有规则违规时的严重程度

        验收标准：
        - 严重程度 > 0
        - 更多违规 = 更高严重程度
        """
        from src.domain.services.intervention_strategy import SeverityCalculator

        calculator = SeverityCalculator()

        # 一个违规
        severity_1 = calculator.calculate(
            rule_violations=["违规1"], alignment_score=0.9, resource_usage_ratio=0.3
        )

        # 两个违规
        severity_2 = calculator.calculate(
            rule_violations=["违规1", "违规2"], alignment_score=0.9, resource_usage_ratio=0.3
        )

        assert severity_1 > 0
        assert severity_2 > severity_1

    def test_calculate_severity_with_low_alignment(self):
        """测试：低对齐分数时的严重程度

        验收标准：
        - 对齐分数越低，严重程度越高
        """
        from src.domain.services.intervention_strategy import SeverityCalculator

        calculator = SeverityCalculator()

        # 高对齐
        severity_high = calculator.calculate(
            rule_violations=[], alignment_score=0.9, resource_usage_ratio=0.3
        )

        # 低对齐
        severity_low = calculator.calculate(
            rule_violations=[], alignment_score=0.3, resource_usage_ratio=0.3
        )

        assert severity_low > severity_high

    def test_calculate_severity_with_high_resource_usage(self):
        """测试：高资源使用时的严重程度

        验收标准：
        - 资源使用越高，严重程度越高
        """
        from src.domain.services.intervention_strategy import SeverityCalculator

        calculator = SeverityCalculator()

        # 低资源使用
        severity_low = calculator.calculate(
            rule_violations=[], alignment_score=0.9, resource_usage_ratio=0.3
        )

        # 高资源使用
        severity_high = calculator.calculate(
            rule_violations=[], alignment_score=0.9, resource_usage_ratio=0.9
        )

        assert severity_high > severity_low


class TestInterventionStrategy:
    """测试干预策略

    业务背景：
    - 根据严重程度决定干预动作
    - 提供干预建议
    """

    def test_decide_pass_for_no_issues(self):
        """测试：无问题时放行

        验收标准：
        - 返回PASS动作
        - 级别为NONE
        """
        from src.domain.services.intervention_strategy import (
            InterventionAction,
            InterventionStrategy,
            SeverityLevel,
        )

        strategy = InterventionStrategy()

        intervention = strategy.decide(
            rule_violations=[], alignment_score=0.9, resource_usage_ratio=0.2
        )

        assert intervention.level == SeverityLevel.NONE
        assert intervention.action == InterventionAction.PASS

    def test_decide_warn_for_minor_issues(self):
        """测试：轻微问题时警告

        验收标准：
        - 返回WARN动作
        - 级别为LOW
        """
        from src.domain.services.intervention_strategy import (
            InterventionAction,
            InterventionStrategy,
            SeverityLevel,
        )

        strategy = InterventionStrategy()

        intervention = strategy.decide(
            rule_violations=[],
            alignment_score=0.65,  # 轻微偏离 (penalty=0.35, > 0.3 threshold)
            resource_usage_ratio=0.4,  # 正常范围
        )

        assert intervention.level == SeverityLevel.LOW
        assert intervention.action == InterventionAction.WARN

    def test_decide_suggest_for_moderate_issues(self):
        """测试：中度问题时建议修正

        验收标准：
        - 返回SUGGEST动作
        - 级别为MEDIUM
        - 包含建议
        """
        from src.domain.services.intervention_strategy import (
            InterventionAction,
            InterventionStrategy,
            SeverityLevel,
        )

        strategy = InterventionStrategy()

        intervention = strategy.decide(
            rule_violations=[],  # 无违规
            alignment_score=0.6,  # 中等偏离 (penalty=0.4)
            resource_usage_ratio=0.55,  # 略高资源使用
            suggestion="建议补充配置",
        )

        assert intervention.level == SeverityLevel.MEDIUM
        assert intervention.action == InterventionAction.SUGGEST
        assert intervention.suggestion is not None

    def test_decide_reject_for_serious_issues(self):
        """测试：严重问题时拒绝

        验收标准：
        - 返回REJECT动作
        - 级别为HIGH
        """
        from src.domain.services.intervention_strategy import (
            InterventionAction,
            InterventionStrategy,
            SeverityLevel,
        )

        strategy = InterventionStrategy()

        intervention = strategy.decide(
            rule_violations=["违反安全规则", "超出权限"],
            alignment_score=0.3,
            resource_usage_ratio=0.7,
        )

        assert intervention.level == SeverityLevel.HIGH
        assert intervention.action == InterventionAction.REJECT

    def test_decide_terminate_for_critical_issues(self):
        """测试：危急问题时终止

        验收标准：
        - 返回TERMINATE动作
        - 级别为CRITICAL
        """
        from src.domain.services.intervention_strategy import (
            InterventionAction,
            InterventionStrategy,
            SeverityLevel,
        )

        strategy = InterventionStrategy()

        intervention = strategy.decide(
            rule_violations=["严重安全违规", "资源耗尽", "目标完全偏离"],
            alignment_score=0.1,
            resource_usage_ratio=0.95,
        )

        assert intervention.level == SeverityLevel.CRITICAL
        assert intervention.action == InterventionAction.TERMINATE


class TestIntervention:
    """测试干预结果"""

    def test_intervention_has_required_fields(self):
        """测试：干预结果包含必要字段"""
        from src.domain.services.intervention_strategy import (
            Intervention,
            InterventionAction,
            SeverityLevel,
        )

        intervention = Intervention(
            level=SeverityLevel.MEDIUM,
            action=InterventionAction.SUGGEST,
            reason="检测到轻微偏离",
            suggestion="建议调整方向",
        )

        assert intervention.level == SeverityLevel.MEDIUM
        assert intervention.action == InterventionAction.SUGGEST
        assert intervention.reason == "检测到轻微偏离"
        assert intervention.suggestion == "建议调整方向"


class TestInterventionStrategyWithCoordinator:
    """测试干预策略与协调者集成

    业务背景：
    - 干预策略与协调者Agent配合使用
    - 协调者调用干预策略获取干预决策
    """

    @pytest.mark.asyncio
    async def test_coordinator_uses_intervention_strategy(self):
        """测试：协调者使用干预策略

        业务场景：
        1. 协调者检测到决策问题
        2. 调用干预策略评估
        3. 根据干预结果采取行动

        验收标准：
        - 干预策略被正确调用
        - 返回合适的干预动作
        """
        from src.domain.services.intervention_strategy import (
            InterventionAction,
            InterventionStrategy,
            SeverityLevel,
        )
        from src.domain.services.validators import (
            DecisionValidator,
            Goal,
            GoalAlignmentChecker,
            ResourceMonitor,
        )

        # 设置验证器
        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            content="""{
            "score": 0.4,
            "is_aligned": false,
            "analysis": "决策偏离目标",
            "suggestion": "建议重新评估"
        }"""
        )

        alignment_checker = GoalAlignmentChecker(llm=mock_llm)
        resource_monitor = ResourceMonitor(token_limit=10000)
        resource_monitor.record_token_usage(5000)  # 50%使用

        validator = DecisionValidator(
            alignment_checker=alignment_checker, resource_monitor=resource_monitor
        )

        # 设置干预策略
        strategy = InterventionStrategy()

        # 验证决策
        goal = Goal(id="goal_1", description="创建分析工作流")
        decision = {"type": "create_node", "node_type": "NOTIFICATION"}

        validation_result = await validator.validate(decision, goal)

        # 获取干预决策
        intervention = strategy.decide(
            rule_violations=validation_result.violations,
            alignment_score=validation_result.alignment_score or 0.5,
            resource_usage_ratio=resource_monitor.get_usage_ratio("tokens"),
            suggestion=validation_result.suggestion,
        )

        # Assert
        assert intervention.action != InterventionAction.PASS
        assert intervention.level.value >= SeverityLevel.LOW.value


class TestRealWorldScenario:
    """测试真实业务场景"""

    @pytest.mark.asyncio
    async def test_intervention_escalation(self):
        """测试：干预升级场景

        业务场景：
        1. 首次轻微偏离 -> 警告
        2. 持续偏离 -> 建议
        3. 严重偏离 -> 拒绝
        4. 极端情况 -> 终止

        验收标准：
        - 干预级别随问题严重程度升级
        """
        from src.domain.services.intervention_strategy import (
            InterventionStrategy,
            SeverityLevel,
        )

        strategy = InterventionStrategy()

        # 场景1: 轻微问题
        intervention_1 = strategy.decide(
            rule_violations=[], alignment_score=0.65, resource_usage_ratio=0.4
        )

        # 场景2: 中度问题
        intervention_2 = strategy.decide(
            rule_violations=["配置不完整"], alignment_score=0.5, resource_usage_ratio=0.6
        )

        # 场景3: 严重问题
        intervention_3 = strategy.decide(
            rule_violations=["违反规则1", "违反规则2"],
            alignment_score=0.3,
            resource_usage_ratio=0.8,
        )

        # 场景4: 危急问题
        intervention_4 = strategy.decide(
            rule_violations=["严重违规1", "严重违规2", "严重违规3"],
            alignment_score=0.1,
            resource_usage_ratio=0.95,
        )

        # Assert - 级别应该逐步升级
        levels = [
            intervention_1.level.value,
            intervention_2.level.value,
            intervention_3.level.value,
            intervention_4.level.value,
        ]

        # 验证级别递增（或至少不降低）
        for i in range(1, len(levels)):
            assert levels[i] >= levels[i - 1], f"Level should not decrease: {levels}"

        # 最严重的应该是CRITICAL
        assert intervention_4.level == SeverityLevel.CRITICAL
