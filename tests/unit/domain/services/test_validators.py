"""测试：验证器系统

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- GoalAlignmentChecker: 检查决策是否与当前目标对齐
- ResourceMonitor: 监控资源使用（token、时间、迭代次数）
- DecisionValidator: 综合验证决策的合法性

真实场景：
1. 对话Agent做出决策
2. 验证器检查决策是否偏离目标
3. 监控资源使用情况
4. 返回验证结果和建议

核心能力：
- 目标对齐检测：判断决策是否服务于当前目标
- 资源监控：跟踪token、时间、迭代次数
- 综合验证：整合多个验证维度
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestGoalAlignmentChecker:
    """测试目标对齐检查器

    业务背景：
    - 对话Agent的决策应该服务于当前目标
    - 检查决策是否偏离目标方向
    - 提供对齐程度评分和建议
    """

    @pytest.mark.asyncio
    async def test_check_aligned_decision(self):
        """测试：检查对齐的决策

        业务场景：
        - 目标：创建数据分析工作流
        - 决策：创建LLM节点用于分析
        - 应该判定为对齐

        验收标准：
        - 返回高对齐分数 (>0.7)
        - is_aligned为True
        """
        # Arrange
        from src.domain.services.validators import Goal, GoalAlignmentChecker

        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            content="""{
            "score": 0.9,
            "is_aligned": true,
            "analysis": "决策直接服务于数据分析目标",
            "suggestion": null
        }"""
        )

        checker = GoalAlignmentChecker(llm=mock_llm)

        goal = Goal(id="goal_1", description="创建一个数据分析工作流，分析销售数据")

        decision = {
            "type": "create_node",
            "node_type": "LLM",
            "reasoning": "创建LLM节点来分析销售数据",
        }

        # Act
        result = await checker.check_alignment(goal, decision)

        # Assert
        assert result.score >= 0.7
        assert result.is_aligned is True

    @pytest.mark.asyncio
    async def test_check_misaligned_decision(self):
        """测试：检查偏离的决策

        业务场景：
        - 目标：创建数据分析工作流
        - 决策：创建发送邮件节点
        - 应该判定为偏离

        验收标准：
        - 返回低对齐分数 (<0.5)
        - is_aligned为False
        - 提供修正建议
        """
        # Arrange
        from src.domain.services.validators import Goal, GoalAlignmentChecker

        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            content="""{
            "score": 0.3,
            "is_aligned": false,
            "analysis": "发送邮件与数据分析目标无直接关联",
            "suggestion": "建议先完成数据分析相关节点"
        }"""
        )

        checker = GoalAlignmentChecker(llm=mock_llm)

        goal = Goal(id="goal_1", description="创建一个数据分析工作流，分析销售数据")

        decision = {
            "type": "create_node",
            "node_type": "NOTIFICATION",
            "reasoning": "创建邮件通知节点",
        }

        # Act
        result = await checker.check_alignment(goal, decision)

        # Assert
        assert result.score < 0.5
        assert result.is_aligned is False
        assert result.suggestion is not None

    @pytest.mark.asyncio
    async def test_check_with_history_context(self):
        """测试：带历史上下文的检查

        业务场景：
        - 有之前的决策历史
        - 新决策应该考虑历史上下文

        验收标准：
        - 历史记录被考虑
        - 结果反映上下文感知
        """
        # Arrange
        from src.domain.services.validators import Goal, GoalAlignmentChecker

        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            content="""{
            "score": 0.85,
            "is_aligned": true,
            "analysis": "基于已创建的API节点，创建LLM分析节点是合理的下一步",
            "suggestion": null
        }"""
        )

        checker = GoalAlignmentChecker(llm=mock_llm)

        goal = Goal(id="goal_1", description="创建数据分析工作流")

        decision = {"type": "create_node", "node_type": "LLM", "reasoning": "分析API获取的数据"}

        history = [
            {"action": "create_node", "node_type": "START"},
            {
                "action": "create_node",
                "node_type": "API",
                "config": {"url": "https://api.example.com"},
            },
        ]

        # Act
        result = await checker.check_alignment(goal, decision, history=history)

        # Assert
        assert result.is_aligned is True


class TestResourceMonitor:
    """测试资源监控器

    业务背景：
    - 监控对话Agent的资源使用
    - 防止资源过度消耗
    - 提供预警和限制
    """

    def test_track_token_usage(self):
        """测试：跟踪Token使用

        业务场景：
        - 每次LLM调用消耗token
        - 需要跟踪总使用量

        验收标准：
        - 正确累加token
        - 可查询当前使用量
        """
        # Arrange
        from src.domain.services.validators import ResourceMonitor

        monitor = ResourceMonitor(token_limit=10000)

        # Act
        monitor.record_token_usage(500)
        monitor.record_token_usage(300)

        # Assert
        assert monitor.tokens_used == 800
        assert monitor.get_usage_ratio("tokens") == 0.08

    def test_track_iteration_count(self):
        """测试：跟踪迭代次数

        业务场景：
        - ReAct循环每次迭代
        - 需要限制最大迭代次数

        验收标准：
        - 正确计数
        - 超限时触发警告
        """
        # Arrange
        from src.domain.services.validators import ResourceMonitor

        monitor = ResourceMonitor(max_iterations=10)

        # Act
        for _ in range(5):
            monitor.record_iteration()

        # Assert
        assert monitor.iteration_count == 5
        assert monitor.is_within_limits() is True

    def test_detect_limit_exceeded(self):
        """测试：检测超限

        业务场景：
        - 资源使用超过限制
        - 应该触发告警

        验收标准：
        - 超限时返回False
        - 返回超限详情
        """
        # Arrange
        from src.domain.services.validators import ResourceMonitor

        monitor = ResourceMonitor(token_limit=1000, max_iterations=5)

        # Act - 超过迭代限制
        for _ in range(6):
            monitor.record_iteration()

        # Assert
        assert monitor.is_within_limits() is False
        violations = monitor.get_violations()
        assert "iterations" in violations

    def test_track_time_usage(self):
        """测试：跟踪时间使用

        业务场景：
        - 任务执行时间需要限制
        - 防止无限执行

        验收标准：
        - 可以启动/停止计时
        - 超时时触发警告
        """
        # Arrange
        import time

        from src.domain.services.validators import ResourceMonitor

        monitor = ResourceMonitor(time_limit_seconds=60)

        # Act
        monitor.start_timer()
        time.sleep(0.1)  # 模拟短暂执行
        elapsed = monitor.get_elapsed_time()

        # Assert
        assert elapsed >= 0.1
        assert monitor.is_within_limits() is True

    def test_get_resource_status(self):
        """测试：获取资源状态

        业务场景：
        - 需要获取综合资源状态
        - 用于监控和决策

        验收标准：
        - 返回所有资源维度
        - 包含使用量和限制
        """
        # Arrange
        from src.domain.services.validators import ResourceMonitor

        monitor = ResourceMonitor(token_limit=10000, max_iterations=10, time_limit_seconds=60)

        monitor.record_token_usage(2000)
        monitor.record_iteration()
        monitor.record_iteration()

        # Act
        status = monitor.get_status()

        # Assert
        assert status["tokens"]["used"] == 2000
        assert status["tokens"]["limit"] == 10000
        assert status["iterations"]["count"] == 2
        assert status["iterations"]["limit"] == 10


class TestDecisionValidator:
    """测试综合决策验证器

    业务背景：
    - 整合目标对齐和资源监控
    - 提供综合验证结果
    - 支持多维度验证
    """

    @pytest.mark.asyncio
    async def test_validate_valid_decision(self):
        """测试：验证有效决策

        业务场景：
        - 决策对齐目标
        - 资源在限制内
        - 应该通过验证

        验收标准：
        - is_valid为True
        - 没有违规项
        """
        # Arrange
        from src.domain.services.validators import (
            DecisionValidator,
            Goal,
            GoalAlignmentChecker,
            ResourceMonitor,
        )

        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            content="""{
            "score": 0.9,
            "is_aligned": true,
            "analysis": "完全对齐",
            "suggestion": null
        }"""
        )

        alignment_checker = GoalAlignmentChecker(llm=mock_llm)
        resource_monitor = ResourceMonitor(token_limit=10000, max_iterations=10)

        validator = DecisionValidator(
            alignment_checker=alignment_checker, resource_monitor=resource_monitor
        )

        goal = Goal(id="goal_1", description="创建工作流")
        decision = {"type": "create_node", "node_type": "LLM"}

        # Act
        result = await validator.validate(decision, goal)

        # Assert
        assert result.is_valid is True
        assert len(result.violations) == 0

    @pytest.mark.asyncio
    async def test_validate_with_resource_violation(self):
        """测试：资源违规时验证失败

        业务场景：
        - 决策对齐目标
        - 但资源已超限
        - 应该验证失败

        验收标准：
        - is_valid为False
        - 包含资源违规信息
        """
        # Arrange
        from src.domain.services.validators import (
            DecisionValidator,
            Goal,
            GoalAlignmentChecker,
            ResourceMonitor,
        )

        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            content="""{
            "score": 0.9,
            "is_aligned": true,
            "analysis": "完全对齐",
            "suggestion": null
        }"""
        )

        alignment_checker = GoalAlignmentChecker(llm=mock_llm)
        resource_monitor = ResourceMonitor(max_iterations=5)

        # 超过迭代限制
        for _ in range(6):
            resource_monitor.record_iteration()

        validator = DecisionValidator(
            alignment_checker=alignment_checker, resource_monitor=resource_monitor
        )

        goal = Goal(id="goal_1", description="创建工作流")
        decision = {"type": "create_node", "node_type": "LLM"}

        # Act
        result = await validator.validate(decision, goal)

        # Assert
        assert result.is_valid is False
        assert any("resource" in v.lower() or "iteration" in v.lower() for v in result.violations)

    @pytest.mark.asyncio
    async def test_validate_with_alignment_violation(self):
        """测试：目标偏离时验证失败

        业务场景：
        - 决策偏离目标
        - 资源在限制内
        - 应该验证失败

        验收标准：
        - is_valid为False
        - 包含对齐违规信息
        - 包含建议
        """
        # Arrange
        from src.domain.services.validators import (
            DecisionValidator,
            Goal,
            GoalAlignmentChecker,
            ResourceMonitor,
        )

        mock_llm = AsyncMock()
        mock_llm.invoke.return_value = MagicMock(
            content="""{
            "score": 0.2,
            "is_aligned": false,
            "analysis": "决策与目标无关",
            "suggestion": "建议重新评估决策方向"
        }"""
        )

        alignment_checker = GoalAlignmentChecker(llm=mock_llm)
        resource_monitor = ResourceMonitor(token_limit=10000)

        validator = DecisionValidator(
            alignment_checker=alignment_checker, resource_monitor=resource_monitor
        )

        goal = Goal(id="goal_1", description="创建数据分析工作流")
        decision = {"type": "create_node", "node_type": "NOTIFICATION"}

        # Act
        result = await validator.validate(decision, goal)

        # Assert
        assert result.is_valid is False
        assert result.suggestion is not None


class TestGoal:
    """测试Goal实体"""

    def test_create_goal(self):
        """测试：创建目标"""
        from src.domain.services.validators import Goal

        goal = Goal(
            id="goal_1",
            description="创建数据分析工作流",
            success_criteria=["有API节点", "有LLM节点", "有END节点"],
        )

        assert goal.id == "goal_1"
        assert goal.status == "pending"
        assert len(goal.success_criteria) == 3

    def test_goal_with_parent(self):
        """测试：带父目标的子目标"""
        from src.domain.services.validators import Goal

        parent = Goal(id="parent_1", description="构建完整应用")

        child = Goal(id="child_1", description="创建后端API", parent_id=parent.id)

        assert child.parent_id == "parent_1"

    def test_goal_status_transition(self):
        """测试：目标状态转换"""
        from src.domain.services.validators import Goal

        goal = Goal(id="goal_1", description="测试目标")

        assert goal.status == "pending"

        goal.status = "in_progress"
        assert goal.status == "in_progress"

        goal.status = "completed"
        assert goal.status == "completed"


class TestRealWorldScenario:
    """测试真实业务场景"""

    @pytest.mark.asyncio
    async def test_continuous_validation_during_react_loop(self):
        """测试：ReAct循环中的持续验证

        业务场景：
        1. 对话Agent在ReAct循环中
        2. 每个决策都需要验证
        3. 验证器持续监控资源和对齐

        验收标准：
        - 正常决策通过
        - 资源超限时阻止
        - 偏离时提供建议
        """
        # Arrange
        from src.domain.services.validators import (
            DecisionValidator,
            Goal,
            GoalAlignmentChecker,
            ResourceMonitor,
        )

        call_count = 0

        async def mock_invoke(messages):
            nonlocal call_count
            call_count += 1
            # 模拟LLM响应
            return MagicMock(
                content="""{
                "score": 0.85,
                "is_aligned": true,
                "analysis": "决策与目标对齐",
                "suggestion": null
            }"""
            )

        mock_llm = AsyncMock()
        mock_llm.invoke.side_effect = mock_invoke

        alignment_checker = GoalAlignmentChecker(llm=mock_llm)
        resource_monitor = ResourceMonitor(
            token_limit=10000, max_iterations=5, time_limit_seconds=60
        )

        validator = DecisionValidator(
            alignment_checker=alignment_checker, resource_monitor=resource_monitor
        )

        goal = Goal(id="goal_1", description="创建一个数据分析工作流")

        # Act - 模拟多次决策验证
        decisions = [
            {"type": "create_node", "node_type": "START"},
            {"type": "create_node", "node_type": "API"},
            {"type": "create_node", "node_type": "LLM"},
            {"type": "create_node", "node_type": "END"},
        ]

        results = []
        for decision in decisions:
            # 记录迭代
            resource_monitor.record_iteration()
            resource_monitor.record_token_usage(500)

            result = await validator.validate(decision, goal)
            results.append(result)

        # Assert
        # 前4个应该都通过
        assert all(r.is_valid for r in results)

        # 再验证一个应该超限（第5次迭代）
        resource_monitor.record_iteration()
        extra_decision = {"type": "create_node", "node_type": "CODE"}
        result_5 = await validator.validate(extra_decision, goal)

        # 第5次迭代正好达到限制，还不超限
        assert result_5.is_valid is True

        # 第6次迭代才真正超限
        resource_monitor.record_iteration()
        final_decision = {"type": "create_node", "node_type": "TEMPLATE"}
        final_result = await validator.validate(final_decision, goal)

        # 第6次迭代超限
        assert final_result.is_valid is False
