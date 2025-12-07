"""A/B 测试与灰度发布系统单元测试 (TDD)

测试内容：
1. 实验配置 Schema
2. 实验分配逻辑
3. 指标采集
4. 灰度发布控制
5. Coordinator 集成

测试日期：2025-12-07
"""

from datetime import datetime, timedelta

# =============================================================================
# 第一部分：实验配置 Schema 测试
# =============================================================================


class TestExperimentConfig:
    """测试实验配置数据结构"""

    def test_experiment_config_has_required_fields(self) -> None:
        """测试：实验配置应该包含必需字段"""
        from src.domain.services.ab_testing_system import ExperimentConfig

        config = ExperimentConfig(
            experiment_id="exp_001",
            name="提示词优化实验",
            description="测试新版角色定义提示词效果",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )

        assert config.experiment_id == "exp_001"
        assert config.name == "提示词优化实验"
        assert config.module_name == "role_definition"
        assert config.control_version == "1.0.0"
        assert config.treatment_version == "1.1.0"
        assert config.traffic_allocation["control"] == 50

    def test_experiment_config_validates_traffic_allocation(self) -> None:
        """测试：流量分配百分比应该合计100"""
        from src.domain.services.ab_testing_system import (
            ExperimentConfig,
        )

        # 有效配置
        valid_config = ExperimentConfig(
            experiment_id="exp_001",
            name="测试",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        assert valid_config.validate_allocation() is True

        # 无效配置（不等于100）
        invalid_config = ExperimentConfig(
            experiment_id="exp_002",
            name="测试",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 30, "treatment": 50},
        )
        assert invalid_config.validate_allocation() is False

    def test_experiment_status_transitions(self) -> None:
        """测试：实验状态流转"""
        from src.domain.services.ab_testing_system import (
            ExperimentConfig,
            ExperimentStatus,
        )

        config = ExperimentConfig(
            experiment_id="exp_001",
            name="测试",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )

        # 初始状态是 draft
        assert config.status == ExperimentStatus.DRAFT

        # draft -> running
        config.start()
        assert config.status == ExperimentStatus.RUNNING

        # running -> paused
        config.pause()
        assert config.status == ExperimentStatus.PAUSED

        # paused -> running
        config.resume()
        assert config.status == ExperimentStatus.RUNNING

        # running -> completed
        config.complete()
        assert config.status == ExperimentStatus.COMPLETED


class TestExperimentVariant:
    """测试实验变体"""

    def test_variant_has_required_fields(self) -> None:
        """测试：变体应该包含必需字段"""
        from src.domain.services.ab_testing_system import ExperimentVariant

        variant = ExperimentVariant(
            variant_id="var_001",
            name="control",
            prompt_version="1.0.0",
            allocation_percentage=50,
        )

        assert variant.variant_id == "var_001"
        assert variant.name == "control"
        assert variant.prompt_version == "1.0.0"
        assert variant.allocation_percentage == 50


# =============================================================================
# 第二部分：实验分配测试
# =============================================================================


class TestExperimentAssignment:
    """测试实验分配逻辑"""

    def test_assign_user_to_variant_deterministic(self) -> None:
        """测试：用户分配应该是确定性的（同一用户总是分到同一组）"""
        from src.domain.services.ab_testing_system import ExperimentManager

        manager = ExperimentManager()

        # 创建实验
        manager.create_experiment(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )

        # 启动实验
        manager.start_experiment("exp_001")

        # 同一用户多次分配应该得到相同结果
        user_id = "user_123"
        variant1 = manager.assign_variant("exp_001", user_id)
        variant2 = manager.assign_variant("exp_001", user_id)
        variant3 = manager.assign_variant("exp_001", user_id)

        assert variant1 == variant2 == variant3

    def test_assign_user_distributes_according_to_allocation(self) -> None:
        """测试：用户分配应该符合流量分配比例"""
        from src.domain.services.ab_testing_system import ExperimentManager

        manager = ExperimentManager()

        manager.create_experiment(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("exp_001")

        # 分配大量用户，统计分布
        control_count = 0
        treatment_count = 0
        total_users = 1000

        for i in range(total_users):
            variant = manager.assign_variant("exp_001", f"user_{i}")
            if variant == "control":
                control_count += 1
            else:
                treatment_count += 1

        # 分布应该接近 50/50（允许 10% 误差）
        control_ratio = control_count / total_users
        assert 0.40 <= control_ratio <= 0.60

    def test_get_prompt_version_for_variant(self) -> None:
        """测试：根据变体获取对应的提示词版本"""
        from src.domain.services.ab_testing_system import ExperimentManager

        manager = ExperimentManager()

        manager.create_experiment(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("exp_001")

        # 获取对照组版本
        control_version = manager.get_version_for_variant("exp_001", "control")
        assert control_version == "1.0.0"

        # 获取实验组版本
        treatment_version = manager.get_version_for_variant("exp_001", "treatment")
        assert treatment_version == "1.1.0"


# =============================================================================
# 第三部分：指标采集测试
# =============================================================================


class TestMetricsCollection:
    """测试指标采集系统"""

    def test_record_success_metric(self) -> None:
        """测试：记录成功率指标"""
        from src.domain.services.ab_testing_system import MetricsCollector

        collector = MetricsCollector()

        # 记录成功事件
        collector.record_success(
            experiment_id="exp_001",
            variant="control",
            user_id="user_123",
            success=True,
        )
        collector.record_success(
            experiment_id="exp_001",
            variant="control",
            user_id="user_124",
            success=True,
        )
        collector.record_success(
            experiment_id="exp_001",
            variant="control",
            user_id="user_125",
            success=False,
        )

        # 计算成功率
        success_rate = collector.get_success_rate("exp_001", "control")
        assert abs(success_rate - 0.6667) < 0.01  # 2/3 ≈ 0.6667

    def test_record_task_duration(self) -> None:
        """测试：记录任务时长"""
        from src.domain.services.ab_testing_system import MetricsCollector

        collector = MetricsCollector()

        # 记录任务时长
        collector.record_duration(
            experiment_id="exp_001",
            variant="treatment",
            user_id="user_123",
            duration_ms=1000,
        )
        collector.record_duration(
            experiment_id="exp_001",
            variant="treatment",
            user_id="user_124",
            duration_ms=2000,
        )
        collector.record_duration(
            experiment_id="exp_001",
            variant="treatment",
            user_id="user_125",
            duration_ms=3000,
        )

        # 获取平均时长
        avg_duration = collector.get_average_duration("exp_001", "treatment")
        assert avg_duration == 2000

    def test_record_satisfaction_score(self) -> None:
        """测试：记录用户满意度"""
        from src.domain.services.ab_testing_system import MetricsCollector

        collector = MetricsCollector()

        # 记录满意度评分（1-5）
        collector.record_satisfaction(
            experiment_id="exp_001",
            variant="control",
            user_id="user_123",
            score=5,
        )
        collector.record_satisfaction(
            experiment_id="exp_001",
            variant="control",
            user_id="user_124",
            score=4,
        )
        collector.record_satisfaction(
            experiment_id="exp_001",
            variant="control",
            user_id="user_125",
            score=3,
        )

        # 获取平均满意度
        avg_satisfaction = collector.get_average_satisfaction("exp_001", "control")
        assert avg_satisfaction == 4.0

    def test_get_experiment_metrics_summary(self) -> None:
        """测试：获取实验指标汇总"""
        from src.domain.services.ab_testing_system import MetricsCollector

        collector = MetricsCollector()

        # 记录对照组数据
        for i in range(10):
            collector.record_success("exp_001", "control", f"user_{i}", i % 2 == 0)
            collector.record_duration("exp_001", "control", f"user_{i}", 1000 + i * 100)
            collector.record_satisfaction("exp_001", "control", f"user_{i}", 3 + (i % 3))

        # 记录实验组数据
        for i in range(10):
            collector.record_success("exp_001", "treatment", f"user_{i+10}", i % 3 != 0)
            collector.record_duration("exp_001", "treatment", f"user_{i+10}", 800 + i * 80)
            collector.record_satisfaction("exp_001", "treatment", f"user_{i+10}", 4 + (i % 2))

        # 获取汇总
        summary = collector.get_metrics_summary("exp_001")

        assert "control" in summary
        assert "treatment" in summary
        assert "success_rate" in summary["control"]
        assert "avg_duration" in summary["control"]
        assert "avg_satisfaction" in summary["control"]


# =============================================================================
# 第四部分：灰度发布测试
# =============================================================================


class TestGradualRollout:
    """测试灰度发布控制"""

    def test_create_rollout_plan(self) -> None:
        """测试：创建灰度发布计划"""
        from src.domain.services.ab_testing_system import GradualRolloutController

        controller = GradualRolloutController()

        # 创建灰度计划
        plan = controller.create_rollout_plan(
            experiment_id="exp_001",
            module_name="role_definition",
            new_version="1.1.0",
            stages=[
                {"percentage": 5, "duration_hours": 24, "metrics_threshold": {"success_rate": 0.9}},
                {
                    "percentage": 20,
                    "duration_hours": 48,
                    "metrics_threshold": {"success_rate": 0.9},
                },
                {
                    "percentage": 50,
                    "duration_hours": 72,
                    "metrics_threshold": {"success_rate": 0.9},
                },
                {"percentage": 100, "duration_hours": 0, "metrics_threshold": {}},
            ],
        )

        assert plan.experiment_id == "exp_001"
        assert len(plan.stages) == 4
        assert plan.current_stage == 0
        assert plan.current_percentage == 5

    def test_advance_rollout_stage(self) -> None:
        """测试：推进灰度阶段"""
        from src.domain.services.ab_testing_system import (
            GradualRolloutController,
            MetricsCollector,
        )

        controller = GradualRolloutController()
        collector = MetricsCollector()

        # 创建灰度计划
        plan = controller.create_rollout_plan(
            experiment_id="exp_001",
            module_name="role_definition",
            new_version="1.1.0",
            stages=[
                {
                    "percentage": 10,
                    "duration_hours": 24,
                    "metrics_threshold": {"success_rate": 0.8},
                },
                {
                    "percentage": 50,
                    "duration_hours": 48,
                    "metrics_threshold": {"success_rate": 0.8},
                },
                {"percentage": 100, "duration_hours": 0, "metrics_threshold": {}},
            ],
        )

        # 模拟指标达标
        for i in range(10):
            collector.record_success("exp_001", "treatment", f"user_{i}", True)

        # 推进到下一阶段
        result = controller.advance_stage("exp_001", collector)

        assert result.success is True
        assert plan.current_stage == 1
        assert plan.current_percentage == 50

    def test_rollback_on_metrics_failure(self) -> None:
        """测试：指标不达标时回滚"""
        from src.domain.services.ab_testing_system import (
            GradualRolloutController,
            MetricsCollector,
        )

        controller = GradualRolloutController()
        collector = MetricsCollector()

        # 创建灰度计划
        plan = controller.create_rollout_plan(
            experiment_id="exp_001",
            module_name="role_definition",
            new_version="1.1.0",
            stages=[
                {
                    "percentage": 10,
                    "duration_hours": 24,
                    "metrics_threshold": {"success_rate": 0.9},
                },
                {"percentage": 100, "duration_hours": 0, "metrics_threshold": {}},
            ],
        )

        # 模拟指标不达标（成功率低于 0.9）
        for i in range(10):
            collector.record_success("exp_001", "treatment", f"user_{i}", i < 5)  # 50% 成功率

        # 检查是否需要回滚
        should_rollback = controller.should_rollback("exp_001", collector)
        assert should_rollback is True

        # 执行回滚
        rollback_result = controller.rollback("exp_001")
        assert rollback_result.success is True
        assert plan.status == "rolled_back"

    def test_complete_rollout(self) -> None:
        """测试：完成灰度发布"""
        from src.domain.services.ab_testing_system import (
            GradualRolloutController,
            MetricsCollector,
        )

        controller = GradualRolloutController()
        collector = MetricsCollector()

        # 创建灰度计划
        plan = controller.create_rollout_plan(
            experiment_id="exp_001",
            module_name="role_definition",
            new_version="1.1.0",
            stages=[
                {
                    "percentage": 50,
                    "duration_hours": 24,
                    "metrics_threshold": {"success_rate": 0.8},
                },
                {"percentage": 100, "duration_hours": 0, "metrics_threshold": {}},
            ],
        )

        # 模拟指标达标
        for i in range(20):
            collector.record_success("exp_001", "treatment", f"user_{i}", True)

        # 推进所有阶段
        controller.advance_stage("exp_001", collector)
        controller.advance_stage("exp_001", collector)

        assert plan.current_stage == 2  # 超出最后一个阶段
        assert plan.status == "completed"
        assert plan.current_percentage == 100


# =============================================================================
# 第五部分：Coordinator 集成测试
# =============================================================================


class TestCoordinatorExperimentIntegration:
    """测试 Coordinator 与实验系统的集成"""

    def test_coordinator_assigns_experiment_variant(self) -> None:
        """测试：Coordinator 分配实验变体"""
        from src.domain.services.ab_testing_system import (
            CoordinatorExperimentAdapter,
            ExperimentManager,
        )

        manager = ExperimentManager()

        manager.create_experiment(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("exp_001")

        adapter = CoordinatorExperimentAdapter(manager)

        # 为用户分配变体并获取版本
        version = adapter.get_version_for_user(
            module_name="role_definition",
            user_id="user_123",
        )

        assert version in ["1.0.0", "1.1.0"]

    def test_coordinator_records_experiment_metrics(self) -> None:
        """测试：Coordinator 记录实验指标"""
        from src.domain.services.ab_testing_system import (
            CoordinatorExperimentAdapter,
            ExperimentManager,
            MetricsCollector,
        )

        manager = ExperimentManager()
        collector = MetricsCollector()

        manager.create_experiment(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("exp_001")

        adapter = CoordinatorExperimentAdapter(manager, collector)

        # 记录用户交互指标
        adapter.record_interaction(
            module_name="role_definition",
            user_id="user_123",
            success=True,
            duration_ms=1500,
            satisfaction=4,
        )

        # 验证指标已记录
        # 根据用户分配的变体检查
        variant = manager.assign_variant("exp_001", "user_123")
        success_rate = collector.get_success_rate("exp_001", variant)
        assert success_rate == 1.0

    def test_coordinator_gets_experiment_report(self) -> None:
        """测试：Coordinator 获取实验报告"""
        from src.domain.services.ab_testing_system import (
            CoordinatorExperimentAdapter,
            ExperimentManager,
            MetricsCollector,
        )

        manager = ExperimentManager()
        collector = MetricsCollector()

        manager.create_experiment(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("exp_001")

        adapter = CoordinatorExperimentAdapter(manager, collector)

        # 模拟一些交互数据
        for i in range(20):
            adapter.record_interaction(
                module_name="role_definition",
                user_id=f"user_{i}",
                success=i % 3 != 0,
                duration_ms=1000 + i * 100,
                satisfaction=3 + (i % 3),
            )

        # 获取报告
        report = adapter.get_experiment_report("exp_001")

        assert "experiment_id" in report
        assert "control" in report["variants"]
        assert "treatment" in report["variants"]
        assert "winner" in report or "inconclusive" in report


# =============================================================================
# 第六部分：多变体实验测试
# =============================================================================


class TestMultiVariantExperiment:
    """测试多变体实验"""

    def test_create_multi_variant_experiment(self) -> None:
        """测试：创建多变体实验"""
        from src.domain.services.ab_testing_system import ExperimentManager

        manager = ExperimentManager()

        manager.create_multi_variant_experiment(
            experiment_id="exp_002",
            name="多变体实验",
            description="测试三个版本",
            module_name="behavior_guidelines",
            variants={
                "control": {"version": "1.0.0", "allocation": 34},
                "treatment_a": {"version": "1.1.0", "allocation": 33},
                "treatment_b": {"version": "1.2.0", "allocation": 33},
            },
        )

        experiment = manager.get_experiment("exp_002")
        assert len(experiment.variants) == 3
        assert experiment.variants["control"]["version"] == "1.0.0"

    def test_assign_user_to_multi_variants(self) -> None:
        """测试：多变体实验分配"""
        from src.domain.services.ab_testing_system import ExperimentManager

        manager = ExperimentManager()

        manager.create_multi_variant_experiment(
            experiment_id="exp_002",
            name="多变体实验",
            description="测试三个版本",
            module_name="behavior_guidelines",
            variants={
                "control": {"version": "1.0.0", "allocation": 34},
                "treatment_a": {"version": "1.1.0", "allocation": 33},
                "treatment_b": {"version": "1.2.0", "allocation": 33},
            },
        )
        manager.start_experiment("exp_002")

        # 分配用户
        variant = manager.assign_variant("exp_002", "user_123")
        assert variant in ["control", "treatment_a", "treatment_b"]


# =============================================================================
# 第七部分：实验配置持久化测试
# =============================================================================


class TestExperimentPersistence:
    """测试实验配置持久化"""

    def test_export_experiment_config_to_dict(self) -> None:
        """测试：导出实验配置为字典"""
        from src.domain.services.ab_testing_system import ExperimentConfig

        config = ExperimentConfig(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )

        data = config.to_dict()

        assert data["experiment_id"] == "exp_001"
        assert data["name"] == "测试实验"
        assert data["control_version"] == "1.0.0"

    def test_import_experiment_config_from_dict(self) -> None:
        """测试：从字典导入实验配置"""
        from src.domain.services.ab_testing_system import ExperimentConfig

        data = {
            "experiment_id": "exp_001",
            "name": "测试实验",
            "description": "测试",
            "module_name": "role_definition",
            "control_version": "1.0.0",
            "treatment_version": "1.1.0",
            "traffic_allocation": {"control": 50, "treatment": 50},
        }

        config = ExperimentConfig.from_dict(data)

        assert config.experiment_id == "exp_001"
        assert config.control_version == "1.0.0"


# =============================================================================
# 第八部分：指标门槛测试
# =============================================================================


class TestMetricsThreshold:
    """测试指标门槛"""

    def test_check_metrics_against_threshold(self) -> None:
        """测试：检查指标是否达标"""
        from src.domain.services.ab_testing_system import (
            MetricsCollector,
            MetricsThresholdChecker,
        )

        collector = MetricsCollector()

        # 记录达标的指标
        for i in range(10):
            collector.record_success("exp_001", "treatment", f"user_{i}", True)
            collector.record_duration("exp_001", "treatment", f"user_{i}", 1000)
            collector.record_satisfaction("exp_001", "treatment", f"user_{i}", 4)

        checker = MetricsThresholdChecker()

        # 定义门槛
        threshold = {
            "success_rate": 0.9,
            "avg_duration": 2000,  # 最大时长
            "avg_satisfaction": 3.5,  # 最小满意度
        }

        result = checker.check("exp_001", "treatment", collector, threshold)
        assert result.passed is True

    def test_check_metrics_below_threshold(self) -> None:
        """测试：指标未达标"""
        from src.domain.services.ab_testing_system import (
            MetricsCollector,
            MetricsThresholdChecker,
        )

        collector = MetricsCollector()

        # 记录不达标的指标（成功率低）
        for i in range(10):
            collector.record_success("exp_001", "treatment", f"user_{i}", i < 3)  # 30% 成功率

        checker = MetricsThresholdChecker()

        threshold = {"success_rate": 0.9}

        result = checker.check("exp_001", "treatment", collector, threshold)
        assert result.passed is False
        assert "success_rate" in result.failed_metrics


# =============================================================================
# 第九部分：实验生命周期测试
# =============================================================================


class TestExperimentLifecycle:
    """测试实验生命周期管理"""

    def test_experiment_has_start_and_end_time(self) -> None:
        """测试：实验应该有开始和结束时间"""
        from src.domain.services.ab_testing_system import ExperimentConfig

        config = ExperimentConfig(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(days=7),
        )

        assert config.start_time is not None
        assert config.end_time is not None
        assert config.end_time > config.start_time

    def test_experiment_auto_complete_after_end_time(self) -> None:
        """测试：实验结束后自动完成"""
        from src.domain.services.ab_testing_system import ExperimentManager

        manager = ExperimentManager()

        # 创建已过期的实验
        past_end_time = datetime.now() - timedelta(hours=1)
        past_start_time = datetime.now() - timedelta(days=1)

        manager.create_experiment(
            experiment_id="exp_001",
            name="过期实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
            start_time=past_start_time,
            end_time=past_end_time,
        )

        manager.start_experiment("exp_001")

        # 检查实验状态
        manager.check_experiment_expiry("exp_001")
        experiment = manager.get_experiment("exp_001")

        assert experiment.status.value == "completed"


# =============================================================================
# 第十部分：审计日志测试
# =============================================================================


class TestExperimentAuditLog:
    """测试实验审计日志"""

    def test_log_experiment_creation(self) -> None:
        """测试：记录实验创建日志"""
        from src.domain.services.ab_testing_system import ExperimentManager

        manager = ExperimentManager()

        manager.create_experiment(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )

        logs = manager.get_audit_logs("exp_001")
        assert len(logs) >= 1
        assert logs[0].action == "create"

    def test_log_experiment_status_change(self) -> None:
        """测试：记录实验状态变更日志"""
        from src.domain.services.ab_testing_system import ExperimentManager

        manager = ExperimentManager()

        manager.create_experiment(
            experiment_id="exp_001",
            name="测试实验",
            description="测试",
            module_name="role_definition",
            control_version="1.0.0",
            treatment_version="1.1.0",
            traffic_allocation={"control": 50, "treatment": 50},
        )
        manager.start_experiment("exp_001")
        manager.pause_experiment("exp_001")

        logs = manager.get_audit_logs("exp_001")
        actions = [log.action for log in logs]

        assert "create" in actions
        assert "start" in actions
        assert "pause" in actions
