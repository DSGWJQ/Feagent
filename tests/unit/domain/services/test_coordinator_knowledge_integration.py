"""Coordinator 与知识维护模块集成示例 (Step 8)

演示 Coordinator 如何复用成功方案：
1. 任务到达时，Coordinator 查询知识库
2. 检查是否有相似的成功解法可复用
3. 检查是否有已知失败案例需要预防
4. 工作流执行后，自动更新知识库

用法：
    pytest tests/unit/domain/services/test_coordinator_knowledge_integration.py -v
"""


class TestCoordinatorKnowledgeIntegration:
    """Coordinator 与知识维护模块集成测试"""

    def test_coordinator_queries_knowledge_before_task(self):
        """测试：Coordinator 在任务执行前查询知识库"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        maintainer.add_memory(
            category=MemoryCategory.FACT,
            content="项目使用 Python 3.11 和 FastAPI 框架",
            source="project_config",
            confidence=1.0,
        )

        maintainer.record_success(
            task_type="api_development",
            task_description="创建用户管理 REST API",
            workflow_id="wf_api_001",
            solution_steps=["定义数据模型", "创建数据库表", "实现 CRUD 端点"],
            success_metrics={"code_coverage": 0.85},
            context={"framework": "fastapi"},
        )

        new_task = {
            "task_type": "api_development",
            "task_description": "创建产品管理 API",
            "context": {"framework": "fastapi"},
        }

        relevant_memories = maintainer.search_memories("FastAPI")
        similar_solutions = retriever.find_similar_solutions(
            task_type=new_task["task_type"],
            task_description=new_task["task_description"],
            context=new_task["context"],
        )

        assert len(relevant_memories) >= 1
        assert len(similar_solutions) >= 1

    def test_coordinator_prevents_known_failure(self):
        """测试：Coordinator 预防已知失败"""
        from src.domain.services.knowledge_maintenance import (
            FailureCategory,
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        maintainer.record_failure(
            task_type="external_api_call",
            task_description="调用第三方支付 API",
            workflow_id="wf_payment_001",
            failure_category=FailureCategory.TIMEOUT,
            error_message="Connection timeout after 30 seconds",
            root_cause="第三方 API 响应慢",
            lesson_learned="调用外部 API 必须设置超时",
            prevention_strategy=["设置 10 秒超时", "实现重试"],
        )

        warning = retriever.check_known_failure(
            task_type="external_api_call",
            task_description="调用物流追踪 API",
            potential_error="timeout",
        )

        assert warning is not None
        assert len(warning.prevention_strategy) >= 1

    def test_coordinator_updates_knowledge_after_workflow(self):
        """测试：Coordinator 在工作流完成后更新知识库"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()

        workflow_success_event = {
            "event_type": "workflow_success",
            "workflow_id": "wf_report_001",
            "task_type": "report_generation",
            "task_description": "生成季度销售分析报告",
            "execution_steps": ["连接数据仓库", "执行聚合查询", "生成图表"],
            "metrics": {"accuracy": 0.98},
        }

        maintainer.on_workflow_event(workflow_success_event)

        assert maintainer.solution_count == 1
        retriever = SolutionRetriever(maintainer)
        solutions = retriever.find_by_task_type("report_generation")
        assert len(solutions) == 1

    def test_full_coordinator_knowledge_workflow(self):
        """测试：完整的 Coordinator 知识工作流"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            MemoryCategory,
            PreferenceType,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        maintainer.add_memory(
            category=MemoryCategory.CONTEXT,
            content="业务规则：订单金额超过 10000 需人工审核",
            source="business_rules",
            confidence=1.0,
        )

        maintainer.add_preference(
            user_id="dev_team",
            preference_type=PreferenceType.CODING_STYLE,
            key="test_framework",
            value="pytest",
        )

        maintainer.on_workflow_event(
            {
                "event_type": "workflow_success",
                "workflow_id": "wf_order_001",
                "task_type": "order_processing",
                "task_description": "处理标准订单",
                "execution_steps": ["验证订单数据", "检查库存", "计算价格"],
                "metrics": {"success_rate": 0.99},
            }
        )

        maintainer.on_workflow_event(
            {
                "event_type": "workflow_failure",
                "workflow_id": "wf_order_002",
                "task_type": "order_processing",
                "task_description": "处理大额订单",
                "error_message": "Order requires manual approval",
                "failure_category": "logic_error",
                "root_cause": "未检查订单金额是否需要人工审核",
            }
        )

        new_task = {
            "task_type": "order_processing",
            "task_description": "处理批量订单",
        }

        business_rules = maintainer.search_memories("订单")
        similar_solutions = retriever.find_similar_solutions(
            task_type=new_task["task_type"],
            task_description=new_task["task_description"],
            context={},
        )
        known_issues = retriever.check_known_failure(
            task_type=new_task["task_type"],
            task_description=new_task["task_description"],
        )

        assert len(business_rules) >= 1
        assert len(similar_solutions) >= 1
        assert known_issues is not None

    def test_continuous_improvement_scenario(self):
        """测试：持续改进场景"""
        from src.domain.services.knowledge_maintenance import (
            KnowledgeMaintainer,
            SolutionRetriever,
        )

        maintainer = KnowledgeMaintainer()
        retriever = SolutionRetriever(maintainer)

        for i, (accuracy, steps) in enumerate(
            [
                (0.7, ["查询数据库 LIKE"]),
                (0.85, ["使用全文索引查询"]),
                (0.98, ["查询 Elasticsearch"]),
            ]
        ):
            maintainer.on_workflow_event(
                {
                    "event_type": "workflow_success",
                    "workflow_id": f"wf_search_v{i+1}",
                    "task_type": "full_text_search",
                    "task_description": "实现全文搜索功能",
                    "execution_steps": steps,
                    "metrics": {"accuracy": accuracy},
                }
            )

        best = retriever.get_best_solution("full_text_search", "accuracy")
        assert best is not None
        assert best.success_metrics["accuracy"] == 0.98
        assert len(retriever.find_by_task_type("full_text_search")) == 3
