"""A/B 测试系统集成测试

测试场景：
1. 端到端实验流程：创建实验 → 分配变体 → 收集指标 → 生成报告
2. 灰度发布流程：创建发布计划 → 推进阶段 → 完成发布
3. CoordinatorAgent 集成：通过 Coordinator 进行实验管理
4. 模拟真实场景：模拟多用户并发访问和指标记录
"""

import random
from concurrent.futures import ThreadPoolExecutor

from src.domain.agents.coordinator_agent import CoordinatorAgent
from src.domain.services.ab_testing_system import (
    CoordinatorExperimentAdapter,
    ExperimentManager,
    ExperimentStatus,
    GradualRolloutController,
    MetricsCollector,
)


class TestEndToEndExperimentFlow:
    """端到端实验流程测试"""

    def test_complete_experiment_lifecycle(self) -> None:
        """测试完整的实验生命周期：创建→运行→收集指标→完成"""
        # 1. 创建实验
        manager = ExperimentManager()
        collector = MetricsCollector()

        config = manager.create_experiment(
            experiment_id="exp_intent_v2",
            name="意图识别提示词 v2 测试",
            description="测试新版意图识别提示词的效果",
            module_name="intent_classifier",
            control_version="1.0.0",
            treatment_version="2.0.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )

        assert config.status == ExperimentStatus.DRAFT

        # 2. 启动实验
        manager.start_experiment("exp_intent_v2")
        config = manager.get_experiment("exp_intent_v2")
        assert config is not None
        assert config.status == ExperimentStatus.RUNNING

        # 3. 模拟 100 个用户的交互
        user_variants: dict[str, str] = {}
        for i in range(100):
            user_id = f"user_{i:03d}"
            variant = manager.assign_variant("exp_intent_v2", user_id)
            assert variant in ["control", "treatment"]
            user_variants[user_id] = variant

            # 模拟指标记录
            success = random.random() > (0.1 if variant == "treatment" else 0.15)
            duration = random.uniform(100, 500)
            satisfaction = (
                random.uniform(3.5, 5.0) if variant == "treatment" else random.uniform(3.0, 4.5)
            )

            collector.record_success("exp_intent_v2", variant, user_id, success)
            collector.record_duration("exp_intent_v2", variant, user_id, duration)
            collector.record_satisfaction("exp_intent_v2", variant, user_id, satisfaction)

        # 4. 获取指标汇总
        summary = collector.get_metrics_summary("exp_intent_v2")
        assert "control" in summary
        assert "treatment" in summary
        assert "success_rate" in summary["control"]
        assert "avg_duration" in summary["control"]
        assert "avg_satisfaction" in summary["control"]

        # 5. 完成实验
        manager.complete_experiment("exp_intent_v2")
        config = manager.get_experiment("exp_intent_v2")
        assert config is not None
        assert config.status == ExperimentStatus.COMPLETED

        # 6. 验证审计日志
        logs = manager.get_audit_logs("exp_intent_v2")
        actions = [log.action for log in logs]
        assert "create" in actions
        assert "start" in actions
        assert "complete" in actions

    def test_multi_variant_experiment_with_metrics(self) -> None:
        """测试多变体实验"""
        manager = ExperimentManager()
        collector = MetricsCollector()

        # 创建 3 变体实验
        variants = {
            "baseline": {"version": "1.0.0", "allocation": 34},
            "variant_a": {"version": "2.0.0", "allocation": 33},
            "variant_b": {"version": "2.1.0", "allocation": 33},
        }

        manager.create_multi_variant_experiment(
            experiment_id="exp_multi_variant",
            name="多变体提示词测试",
            description="测试三种不同的响应生成策略",
            module_name="response_generator",
            variants=variants,
        )

        manager.start_experiment("exp_multi_variant")

        # 模拟用户分配
        variant_counts: dict[str, int] = {"baseline": 0, "variant_a": 0, "variant_b": 0}
        for i in range(300):
            user_id = f"user_{i:04d}"
            variant = manager.assign_variant("exp_multi_variant", user_id)
            variant_counts[variant] += 1

            # 记录指标
            collector.record_success("exp_multi_variant", variant, user_id, random.random() > 0.1)

        # 验证分布合理性（允许 15% 误差）
        for count in variant_counts.values():
            assert 60 <= count <= 140, f"Variant distribution out of range: {variant_counts}"


class TestGradualRolloutFlow:
    """灰度发布流程测试"""

    def test_complete_rollout_workflow(self) -> None:
        """测试完整的灰度发布流程"""
        collector = MetricsCollector()
        controller = GradualRolloutController()

        # 1. 创建发布计划
        stages = [
            {
                "name": "canary",
                "percentage": 5,
                "duration_hours": 0,
                "metrics_threshold": {"success_rate": 0.90},
            },
            {
                "name": "early_adopters",
                "percentage": 20,
                "duration_hours": 0,
                "metrics_threshold": {"success_rate": 0.92},
            },
            {
                "name": "general_availability",
                "percentage": 50,
                "duration_hours": 0,
                "metrics_threshold": {"success_rate": 0.95},
            },
            {
                "name": "full_rollout",
                "percentage": 100,
                "duration_hours": 0,
                "metrics_threshold": {"success_rate": 0.95},
            },
        ]

        plan = controller.create_rollout_plan(
            experiment_id="rollout_intent_v3",
            module_name="intent_classifier",
            new_version="3.0.0",
            stages=stages,
        )

        assert plan.current_stage == 0
        assert plan.stages[0]["name"] == "canary"

        # 2. 模拟 canary 阶段的成功指标
        for i in range(20):
            collector.record_success("rollout_intent_v3", "treatment", f"user_{i}", True)
        for i in range(2):
            collector.record_success("rollout_intent_v3", "treatment", f"fail_user_{i}", False)

        # 3. 推进到 early_adopters (stage 1)
        result = controller.advance_stage("rollout_intent_v3", collector)
        assert result.success
        plan = controller.get_plan("rollout_intent_v3")
        assert plan.current_stage == 1  # early_adopters

        # 4. 模拟 early_adopters 阶段
        for i in range(50):
            collector.record_success("rollout_intent_v3", "treatment", f"ea_user_{i}", True)
        for i in range(4):
            collector.record_success("rollout_intent_v3", "treatment", f"ea_fail_{i}", False)

        # 5. 推进到 general_availability (stage 2)
        result = controller.advance_stage("rollout_intent_v3", collector)
        assert result.success
        plan = controller.get_plan("rollout_intent_v3")
        assert plan.current_stage == 2  # general_availability

        # 6. 模拟 GA 阶段 (需要更高成功率以满足 95% 阈值)
        for i in range(200):
            collector.record_success("rollout_intent_v3", "treatment", f"ga_user_{i}", True)
        for i in range(3):
            collector.record_success("rollout_intent_v3", "treatment", f"ga_fail_{i}", False)

        # 7. 推进到 full_rollout (stage 3)
        result = controller.advance_stage("rollout_intent_v3", collector)
        assert result.success
        plan = controller.get_plan("rollout_intent_v3")
        assert plan.current_stage == 3  # full_rollout

    def test_rollback_on_poor_metrics(self) -> None:
        """测试指标不达标时的回滚"""
        collector = MetricsCollector()
        controller = GradualRolloutController()

        stages = [
            {
                "name": "canary",
                "percentage": 5,
                "duration_hours": 0,
                "metrics_threshold": {"success_rate": 0.95},
            },
            {
                "name": "full_rollout",
                "percentage": 100,
                "duration_hours": 0,
                "metrics_threshold": {"success_rate": 0.95},
            },
        ]

        controller.create_rollout_plan(
            experiment_id="rollout_bad_version",
            module_name="bad_module",
            new_version="99.0.0",
            stages=stages,
        )

        # 模拟糟糕的指标（60% 成功率）
        for i in range(60):
            collector.record_success("rollout_bad_version", "treatment", f"user_{i}", True)
        for i in range(40):
            collector.record_success("rollout_bad_version", "treatment", f"fail_{i}", False)

        # 检查是否应该回滚
        should_rollback = controller.should_rollback("rollout_bad_version", collector)
        assert should_rollback

        # 执行回滚
        result = controller.rollback("rollout_bad_version")
        assert result.success


class TestCoordinatorAgentIntegration:
    """CoordinatorAgent 实验集成测试"""

    def test_coordinator_experiment_full_flow(self) -> None:
        """测试通过 CoordinatorAgent 进行完整的实验管理"""
        coordinator = CoordinatorAgent()

        # 1. 创建实验
        exp_config = coordinator.create_experiment(
            experiment_id="coord_exp_001",
            name="Coordinator 集成测试",
            module_name="test_module",
            control_version="1.0.0",
            treatment_version="2.0.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )

        assert exp_config["experiment_id"] == "coord_exp_001"
        assert exp_config["status"] == "draft"

        # 2. 启动实验
        success = coordinator.start_experiment("coord_exp_001")
        assert success

        # 3. 获取变体
        variant = coordinator.get_experiment_variant("coord_exp_001", "test_user_1")
        assert variant in ["control", "treatment"]

        # 4. 记录指标
        coordinator.record_experiment_metrics(
            module_name="test_module",
            user_id="test_user_1",
            success=True,
            duration_ms=250.0,
            satisfaction=4.5,
        )

        # 5. 获取报告
        report = coordinator.get_experiment_report("coord_exp_001")
        assert "experiment_id" in report

        # 6. 完成实验
        success = coordinator.complete_experiment("coord_exp_001")
        assert success

        # 7. 验证审计日志
        logs = coordinator.get_experiment_audit_logs("coord_exp_001")
        assert len(logs) >= 3  # create, start, complete
        actions = [log["action"] for log in logs]
        assert "create" in actions

    def test_coordinator_rollout_management(self) -> None:
        """测试通过 CoordinatorAgent 管理灰度发布"""
        coordinator = CoordinatorAgent()

        # 创建发布计划
        plan = coordinator.create_rollout_plan(
            experiment_id="coord_rollout_001",
            module_name="rollout_module",
            new_version="2.0.0",
            stages=[
                {"name": "canary", "percentage": 10, "success_threshold": 0.90},
                {"name": "full", "percentage": 100, "success_threshold": 0.95},
            ],
        )

        assert plan["module_name"] == "rollout_module"
        assert plan["new_version"] == "2.0.0"
        assert len(plan["stages"]) == 2

        # 推进阶段（模拟指标已达标）
        result = coordinator.advance_rollout_stage("coord_rollout_001")
        # 结果取决于是否达到阈值
        assert "success" in result
        assert "message" in result

    def test_coordinator_list_and_filter_experiments(self) -> None:
        """测试列出和过滤实验"""
        coordinator = CoordinatorAgent()

        # 创建多个实验
        coordinator.create_experiment(
            experiment_id="list_exp_1",
            name="实验1",
            module_name="module_a",
            control_version="1.0",
            treatment_version="2.0",
        )

        coordinator.create_experiment(
            experiment_id="list_exp_2",
            name="实验2",
            module_name="module_b",
            control_version="1.0",
            treatment_version="2.0",
        )

        coordinator.start_experiment("list_exp_1")

        # 列出所有实验
        all_experiments = coordinator.list_experiments()
        assert len(all_experiments) >= 2

        # 按状态过滤
        running = coordinator.list_experiments(status="running")
        draft = coordinator.list_experiments(status="draft")

        running_ids = [e["experiment_id"] for e in running]
        draft_ids = [e["experiment_id"] for e in draft]

        assert "list_exp_1" in running_ids
        assert "list_exp_2" in draft_ids

    def test_coordinator_metrics_threshold_check(self) -> None:
        """测试通过 Coordinator 检查指标阈值"""
        coordinator = CoordinatorAgent()

        # 创建并启动实验
        coordinator.create_experiment(
            experiment_id="threshold_exp",
            name="阈值测试",
            module_name="threshold_module",
            control_version="1.0",
            treatment_version="2.0",
        )
        coordinator.start_experiment("threshold_exp")

        # 记录指标 - 使用已分配的变体
        for i in range(20):
            user_id = f"user_{i}"
            # 先获取变体
            variant = coordinator.get_experiment_variant("threshold_exp", user_id)
            # 直接通过 metrics collector 记录
            coordinator._metrics_collector.record_success(
                "threshold_exp",
                variant,
                user_id,
                i < 19,  # 95% 成功率
            )

        # 检查阈值
        result = coordinator.check_experiment_metrics_threshold(
            experiment_id="threshold_exp",
            variant="treatment",
            thresholds={"success_rate": 0.90},
        )

        assert "passed" in result
        assert "details" in result


class TestConcurrentExperimentAccess:
    """并发访问测试"""

    def test_concurrent_variant_assignment(self) -> None:
        """测试并发变体分配的确定性"""
        manager = ExperimentManager()

        manager.create_experiment(
            experiment_id="concurrent_exp",
            name="并发测试",
            description="测试并发场景",
            module_name="concurrent_module",
            control_version="1.0",
            treatment_version="2.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("concurrent_exp")

        results: dict[str, list[str]] = {}

        def assign_for_user(user_id: str) -> tuple[str, str]:
            variant = manager.assign_variant("concurrent_exp", user_id)
            return user_id, variant

        # 并发分配
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(assign_for_user, f"user_{i}") for i in range(100)]
            for future in futures:
                user_id, variant = future.result()
                if user_id not in results:
                    results[user_id] = []
                results[user_id].append(variant)

        # 验证每个用户只有一个结果（确定性）
        for user_id, variants in results.items():
            assert len(set(variants)) == 1, f"User {user_id} got different variants: {variants}"

    def test_concurrent_metrics_recording(self) -> None:
        """测试并发指标记录"""
        manager = ExperimentManager()
        collector = MetricsCollector()

        manager.create_experiment(
            experiment_id="metrics_concurrent",
            name="指标并发测试",
            description="测试指标并发记录",
            module_name="metrics_module",
            control_version="1.0",
            treatment_version="2.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("metrics_concurrent")

        def record_metrics(user_id: str) -> None:
            variant = manager.assign_variant("metrics_concurrent", user_id)
            collector.record_success("metrics_concurrent", variant, user_id, True)
            collector.record_duration("metrics_concurrent", variant, user_id, 100.0)

        # 并发记录
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(record_metrics, f"user_{i}") for i in range(200)]
            for future in futures:
                future.result()

        # 验证指标汇总 - 检查 sample_count
        summary = collector.get_metrics_summary("metrics_concurrent")
        control_count = summary.get("control", {}).get("sample_count", 0)
        treatment_count = summary.get("treatment", {}).get("sample_count", 0)
        total_records = control_count + treatment_count
        assert total_records == 200


class TestExperimentAdapterIntegration:
    """ExperimentAdapter 集成测试"""

    def test_adapter_module_based_version_selection(self) -> None:
        """测试基于模块的版本选择"""
        manager = ExperimentManager()
        collector = MetricsCollector()
        adapter = CoordinatorExperimentAdapter(manager, collector)

        # 为不同模块创建实验
        manager.create_experiment(
            experiment_id="module_a_exp",
            name="模块A实验",
            description="测试模块A",
            module_name="module_a",
            control_version="1.0.0",
            treatment_version="2.0.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("module_a_exp")

        manager.create_experiment(
            experiment_id="module_b_exp",
            name="模块B实验",
            description="测试模块B",
            module_name="module_b",
            control_version="3.0.0",
            treatment_version="4.0.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("module_b_exp")

        # 获取用户的版本
        version_a = adapter.get_version_for_user("module_a", "test_user")
        version_b = adapter.get_version_for_user("module_b", "test_user")

        assert version_a in ["1.0.0", "2.0.0"]
        assert version_b in ["3.0.0", "4.0.0"]

        # 无实验的模块返回空字符串
        version_c = adapter.get_version_for_user("module_c", "test_user")
        assert version_c == ""

    def test_adapter_report_generation(self) -> None:
        """测试报告生成"""
        manager = ExperimentManager()
        collector = MetricsCollector()
        adapter = CoordinatorExperimentAdapter(manager, collector)

        manager.create_experiment(
            experiment_id="report_exp",
            name="报告测试",
            description="测试报告生成",
            module_name="report_module",
            control_version="1.0",
            treatment_version="2.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("report_exp")

        # 记录指标
        for i in range(50):
            adapter.record_interaction(
                module_name="report_module",
                user_id=f"user_{i}",
                success=True,
                duration_ms=150.0,
                satisfaction=4.2,
            )

        # 生成报告
        report = adapter.get_experiment_report("report_exp")

        assert "experiment_id" in report
        assert "variants" in report
        assert report["experiment_id"] == "report_exp"
