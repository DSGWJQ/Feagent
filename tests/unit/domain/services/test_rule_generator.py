"""规则生成器测试 - Phase 7.1

TDD RED阶段：测试从用户输入动态生成规则
"""


class TestRuleGenerator:
    """规则生成器测试"""

    def test_generate_from_user_input_should_create_goal_rules(self):
        """从用户输入应生成目标对齐规则"""
        from src.domain.services.enhanced_rule_repository import RuleCategory, RuleSource
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()
        rules = generator.generate_from_user_input(
            start="我有一份销售数据Excel",
            goal="生成月度销售分析报表",
        )

        # 应该生成至少一条目标对齐规则
        goal_rules = [r for r in rules if r.category == RuleCategory.GOAL]
        assert len(goal_rules) >= 1

        # 规则来源应该是动态生成
        assert all(r.source == RuleSource.GENERATED for r in rules)

    def test_generate_from_user_input_should_extract_keywords(self):
        """应从用户输入中提取关键词用于目标对齐"""
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()
        rules = generator.generate_from_user_input(
            start="我有一份销售数据Excel",
            goal="生成月度销售分析报表",
        )

        # 应该提取关键词并存储在metadata中
        goal_rules = [r for r in rules if "goal" in r.id]
        assert len(goal_rules) > 0

        # 检查是否包含关键词
        goal_rule = goal_rules[0]
        assert "keywords" in goal_rule.metadata
        keywords = goal_rule.metadata["keywords"]
        assert any("销售" in kw for kw in keywords) or "销售" in str(keywords)

    def test_generate_from_user_input_with_description_should_add_constraints(self):
        """带描述的用户输入应添加额外约束"""
        from src.domain.services.enhanced_rule_repository import RuleCategory
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()
        rules = generator.generate_from_user_input(
            start="我有一份包含客户信息的Excel",
            goal="生成销售分析报表",
            description="客户姓名需要脱敏处理，只看本月数据",
        )

        # 应该生成数据访问规则（因为提到脱敏）
        data_rules = [r for r in rules if r.category == RuleCategory.DATA]
        assert len(data_rules) >= 1

        # 检查是否包含脱敏相关配置
        has_privacy_rule = any("脱敏" in r.name or "privacy" in r.id.lower() for r in data_rules)
        assert has_privacy_rule

    def test_generate_tool_rules_should_create_allowed_tools_rule(self):
        """生成工具规则应创建允许工具列表规则"""
        from src.domain.services.enhanced_rule_repository import RuleCategory
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()
        rules = generator.generate_tool_rules(allowed_tools=["database", "python", "http"])

        # 应该生成工具约束规则
        tool_rules = [r for r in rules if r.category == RuleCategory.TOOL]
        assert len(tool_rules) >= 1

        # 检查是否记录了允许的工具
        tool_rule = tool_rules[0]
        assert "allowed_tools" in tool_rule.metadata
        assert "database" in tool_rule.metadata["allowed_tools"]

    def test_generate_tool_rules_with_config_should_add_param_constraints(self):
        """带配置的工具规则应添加参数约束"""
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()
        rules = generator.generate_tool_rules(
            allowed_tools=["database", "http"],
            tool_configs={
                "database": {
                    "forbidden_operations": ["DROP", "DELETE", "TRUNCATE"],
                    "max_rows": 10000,
                },
                "http": {
                    "rate_limit": 10,  # 每分钟最多10次
                    "allowed_domains": ["api.example.com"],
                },
            },
        )

        # 应该有数据库约束规则
        db_rules = [r for r in rules if "database" in r.id.lower()]
        assert len(db_rules) >= 1

        # 检查是否记录了禁止的操作
        db_rule = db_rules[0]
        assert (
            "forbidden_operations" in db_rule.metadata
            or "forbidden" in str(db_rule.metadata).lower()
        )

    def test_generate_execution_rules_should_create_timeout_rule(self):
        """生成执行规则应创建超时规则"""
        from src.domain.services.enhanced_rule_repository import RuleCategory
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()
        rules = generator.generate_execution_rules(
            timeout_seconds=120,
            max_retries=3,
        )

        # 应该生成执行策略规则
        exec_rules = [r for r in rules if r.category == RuleCategory.EXECUTION]
        assert len(exec_rules) >= 1

        # 检查超时配置
        timeout_rules = [r for r in exec_rules if "timeout" in r.id.lower()]
        assert len(timeout_rules) >= 1
        assert timeout_rules[0].metadata.get("timeout_seconds") == 120

    def test_generate_behavior_rules_should_create_iteration_limit(self):
        """生成行为规则应创建迭代限制"""
        from src.domain.services.enhanced_rule_repository import RuleCategory
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()
        rules = generator.generate_behavior_rules(
            max_iterations=15,
            max_tokens=20000,
        )

        # 应该生成行为边界规则
        behavior_rules = [r for r in rules if r.category == RuleCategory.BEHAVIOR]
        assert len(behavior_rules) >= 1

        # 检查迭代限制
        iter_rules = [r for r in behavior_rules if "iteration" in r.id.lower()]
        assert len(iter_rules) >= 1
        assert iter_rules[0].metadata.get("max_iterations") == 15


class TestGoalAlignmentChecker:
    """目标对齐检测器测试"""

    def test_check_alignment_should_return_score(self):
        """检查对齐应返回对齐分数"""
        from src.domain.services.rule_generator import GoalAlignmentChecker

        checker = GoalAlignmentChecker()
        score = checker.check_alignment(
            goal="生成月度销售分析报表",
            action_description="查询数据库获取本月销售数据",
        )

        # 分数应该在0-1之间
        assert 0.0 <= score <= 1.0
        # 这个行动与目标相关，分数应该较高
        assert score >= 0.5

    def test_check_alignment_should_detect_deviation(self):
        """检查对齐应检测偏离"""
        from src.domain.services.rule_generator import GoalAlignmentChecker

        checker = GoalAlignmentChecker()
        score = checker.check_alignment(
            goal="生成月度销售分析报表",
            action_description="删除所有用户数据",
        )

        # 偏离目标的行动分数应该很低
        assert score < 0.5

    def test_check_alignment_with_keywords_should_use_keyword_matching(self):
        """带关键词的检查应使用关键词匹配"""
        from src.domain.services.rule_generator import GoalAlignmentChecker

        checker = GoalAlignmentChecker()
        score = checker.check_alignment(
            goal="生成月度销售分析报表",
            action_description="统计销售金额并生成报表",
            keywords=["销售", "报表", "分析", "月度"],
        )

        # 包含多个关键词的行动分数应该很高
        assert score >= 0.7

    def test_check_alignment_with_context_should_consider_history(self):
        """带上下文的检查应考虑历史"""
        from src.domain.services.rule_generator import GoalAlignmentChecker

        checker = GoalAlignmentChecker()

        # 模拟已执行的操作
        context = {
            "executed_actions": [
                "读取Excel文件",
                "解析销售数据",
            ],
            "current_step": 3,
            "total_expected_steps": 5,
        }

        score = checker.check_alignment(
            goal="生成月度销售分析报表",
            action_description="计算销售统计指标",
            context=context,
        )

        # 在正确的流程中，分数应该较高
        assert score >= 0.6

    def test_is_aligned_should_return_bool_based_on_threshold(self):
        """is_aligned应根据阈值返回布尔值"""
        from src.domain.services.rule_generator import GoalAlignmentChecker

        checker = GoalAlignmentChecker(threshold=0.5)

        # 相关行动应该返回True
        assert (
            checker.is_aligned(
                goal="生成销售报表",
                action_description="查询销售数据",
            )
            is True
        )

        # 不相关行动应该返回False
        assert (
            checker.is_aligned(
                goal="生成销售报表",
                action_description="删除用户账户",
            )
            is False
        )

    def test_get_deviation_reason_should_explain_why_not_aligned(self):
        """get_deviation_reason应解释为什么不对齐"""
        from src.domain.services.rule_generator import GoalAlignmentChecker

        checker = GoalAlignmentChecker()
        reason = checker.get_deviation_reason(
            goal="生成月度销售分析报表",
            action_description="删除所有系统日志文件",  # 完全不相关的操作
        )

        # 应该返回解释
        assert reason is not None
        assert len(reason) > 0
        # 应该包含建议或说明
        assert "建议" in reason or "偏离" in reason or "相关" in reason


class TestRuleGeneratorIntegration:
    """规则生成器集成测试"""

    def test_generate_all_rules_from_agent_config(self):
        """从Agent配置生成所有规则"""
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()

        # 模拟完整的Agent配置
        agent_config = {
            "start": "我有一份包含客户订单的数据库",
            "goal": "分析订单趋势并生成可视化报表",
            "description": "关注最近3个月的数据，客户信息需要脱敏",
            "allowed_tools": ["database", "python", "visualization"],
            "tool_configs": {
                "database": {"max_rows": 50000},
            },
            "max_iterations": 20,
            "timeout_seconds": 300,
        }

        rules = generator.generate_all_rules(agent_config)

        # 应该生成多种类别的规则
        from src.domain.services.enhanced_rule_repository import RuleCategory

        categories = {r.category for r in rules}
        assert RuleCategory.GOAL in categories
        assert RuleCategory.TOOL in categories or RuleCategory.DATA in categories

    def test_generated_rules_should_be_evaluable(self):
        """生成的规则应该可以被评估"""
        from src.domain.services.enhanced_rule_repository import EnhancedRuleRepository
        from src.domain.services.rule_generator import RuleGenerator

        generator = RuleGenerator()
        rules = generator.generate_from_user_input(
            start="销售数据",
            goal="生成报表",
        )

        # 添加到规则库
        repo = EnhancedRuleRepository()
        for rule in rules:
            repo.add_rule(rule)

        # 应该可以评估
        context = {
            "action_description": "生成销售报表",
            "alignment_score": 0.8,
        }
        violations = repo.evaluate(context)

        # 不应该有违规（因为行动与目标一致）
        # 注意：这取决于生成的规则条件
        assert isinstance(violations, list)
