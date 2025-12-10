"""ExperimentOrchestrator - A/B实验与灰度发布编排器

从 CoordinatorAgent 提取的实验相关能力，封装 ExperimentManager、
MetricsCollector、GradualRolloutController、CoordinatorExperimentAdapter。

设计要点：
- 方法签名与 CoordinatorAgent 现有接口完全一致（向后兼容）
- 默认内部创建依赖，也支持依赖注入以便测试/替换实现
- 日志格式与 CoordinatorAgent 保持一致
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.domain.services.ab_testing_system import (
        CoordinatorExperimentAdapter,
        ExperimentManager,
        GradualRolloutController,
        MetricsCollector,
        MetricsThresholdChecker,
    )


class ExperimentOrchestrator:
    """A/B 实验与灰度发布编排器"""

    def __init__(
        self,
        log_collector: Any | None = None,
        experiment_manager: Any | None = None,
        metrics_collector: Any | None = None,
        rollout_controller: Any | None = None,
        experiment_adapter: Any | None = None,
    ) -> None:
        """初始化实验编排器

        参数:
            log_collector: 日志收集器（可选）
            experiment_manager: 实验管理器（可选，默认创建新实例）
            metrics_collector: 指标收集器（可选，默认创建新实例）
            rollout_controller: 灰度发布控制器（可选，默认创建新实例）
            experiment_adapter: 实验适配器（可选，默认创建新实例）
        """
        self._log_collector = log_collector

        # 延迟导入以减少上层初始化开销
        from src.domain.services.ab_testing_system import (
            CoordinatorExperimentAdapter,
            ExperimentManager,
            GradualRolloutController,
            MetricsCollector,
        )

        self._experiment_manager = experiment_manager or ExperimentManager()
        self._metrics_collector = metrics_collector or MetricsCollector()
        self._rollout_controller = rollout_controller or GradualRolloutController()
        self._experiment_adapter = experiment_adapter or CoordinatorExperimentAdapter(
            self._experiment_manager,
            self._metrics_collector,
        )

    def _log(self, level: str, source: str, message: str, context: dict[str, Any]) -> None:
        """内部日志记录"""
        if self._log_collector is not None:
            log_method = getattr(self._log_collector, level, None)
            if log_method:
                log_method(source, message, context)

    # ============ A/B 实验基础 ============ #

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        module_name: str,
        control_version: str,
        treatment_version: str,
        traffic_allocation: dict[str, int] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """创建 A/B 测试实验

        参数：
            experiment_id: 实验唯一标识
            name: 实验名称
            module_name: 模块名称（如 "intent_classifier"）
            control_version: 对照组版本号
            treatment_version: 实验组版本号
            traffic_allocation: 流量分配 {"control": 50, "treatment": 50}
            description: 实验描述

        返回：
            实验配置字典
        """
        config = self._experiment_manager.create_experiment(
            experiment_id=experiment_id,
            name=name,
            module_name=module_name,
            control_version=control_version,
            treatment_version=treatment_version,
            traffic_allocation=traffic_allocation or {"control": 50, "treatment": 50},
            description=description,
        )

        self._log(
            "info",
            "ExperimentOrchestrator",
            f"创建A/B实验: {name}",
            {
                "experiment_id": experiment_id,
                "module_name": module_name,
                "control_version": control_version,
                "treatment_version": treatment_version,
            },
        )

        return config.to_dict()

    def create_multi_variant_experiment(
        self,
        experiment_id: str,
        name: str,
        module_name: str,
        variants: dict[str, dict[str, Any]],
        description: str = "",
    ) -> dict[str, Any]:
        """创建多变体实验

        参数：
            experiment_id: 实验唯一标识
            name: 实验名称
            module_name: 模块名称
            variants: 变体配置 {"v1": {"version": "1.0", "allocation": 33}, ...}
            description: 实验描述

        返回：
            实验配置字典
        """
        config = self._experiment_manager.create_multi_variant_experiment(
            experiment_id=experiment_id,
            name=name,
            module_name=module_name,
            variants=variants,
            description=description,
        )

        self._log(
            "info",
            "ExperimentOrchestrator",
            f"创建多变体实验: {name}",
            {
                "experiment_id": experiment_id,
                "module_name": module_name,
                "variant_count": len(variants),
            },
        )

        return config.to_dict()

    def start_experiment(self, experiment_id: str) -> bool:
        """启动实验

        参数：
            experiment_id: 实验ID

        返回：
            是否成功启动
        """
        try:
            self._experiment_manager.start_experiment(experiment_id)
            self._log(
                "info",
                "ExperimentOrchestrator",
                f"启动实验: {experiment_id}",
                {"experiment_id": experiment_id},
            )
            return True
        except Exception as e:
            self._log(
                "error",
                "ExperimentOrchestrator",
                f"启动实验失败: {experiment_id}",
                {"error": str(e)},
            )
            return False

    def pause_experiment(self, experiment_id: str) -> bool:
        """暂停实验

        参数：
            experiment_id: 实验ID

        返回：
            是否成功暂停
        """
        try:
            self._experiment_manager.pause_experiment(experiment_id)
            self._log(
                "info",
                "ExperimentOrchestrator",
                f"暂停实验: {experiment_id}",
                {"experiment_id": experiment_id},
            )
            return True
        except Exception as e:
            self._log(
                "error",
                "ExperimentOrchestrator",
                f"暂停实验失败: {experiment_id}",
                {"error": str(e)},
            )
            return False

    def complete_experiment(self, experiment_id: str) -> bool:
        """完成实验

        参数：
            experiment_id: 实验ID

        返回：
            是否成功完成
        """
        try:
            self._experiment_manager.complete_experiment(experiment_id)
            self._log(
                "info",
                "ExperimentOrchestrator",
                f"完成实验: {experiment_id}",
                {"experiment_id": experiment_id},
            )
            return True
        except Exception as e:
            self._log(
                "error",
                "ExperimentOrchestrator",
                f"完成实验失败: {experiment_id}",
                {"error": str(e)},
            )
            return False

    def get_experiment_variant(self, experiment_id: str, user_id: str) -> str | None:
        """获取用户的实验变体

        根据确定性哈希分配用户到实验变体，确保同一用户
        在同一实验中始终获得相同的变体。

        参数：
            experiment_id: 实验ID
            user_id: 用户ID

        返回：
            变体名称 (如 "control", "treatment") 或 None（实验未运行）
        """
        try:
            return self._experiment_manager.assign_variant(experiment_id, user_id)
        except Exception:
            return None

    # ============ 提示词版本与指标记录 ============ #

    def get_prompt_version_for_experiment(
        self,
        module_name: str,
        user_id: str,
    ) -> str | None:
        """获取用户在模块实验中应使用的提示词版本

        参数：
            module_name: 模块名称
            user_id: 用户ID

        返回：
            提示词版本号，如 "1.0.0"
        """
        return self._experiment_adapter.get_version_for_user(module_name, user_id)

    def record_experiment_metrics(
        self,
        module_name: str,
        user_id: str,
        success: bool,
        duration_ms: int = 0,
        satisfaction: int = 0,
    ) -> None:
        """记录实验指标

        参数：
            module_name: 模块名称
            user_id: 用户ID
            success: 是否成功
            duration_ms: 任务时长（毫秒）
            satisfaction: 满意度评分 (0-5)
        """
        self._experiment_adapter.record_interaction(
            module_name=module_name,
            user_id=user_id,
            success=success,
            duration_ms=duration_ms,
            satisfaction=satisfaction,
        )

    def get_experiment_report(self, experiment_id: str) -> dict[str, Any]:
        """获取实验报告

        包含各变体的指标统计：成功率、平均时长、平均满意度。

        参数：
            experiment_id: 实验ID

        返回：
            实验报告字典
        """
        return self._experiment_adapter.get_experiment_report(experiment_id)

    def get_experiment_metrics_summary(self, experiment_id: str) -> dict[str, Any]:
        """获取实验指标汇总

        参数：
            experiment_id: 实验ID

        返回：
            指标汇总字典，包含各变体的详细指标
        """
        return self._metrics_collector.get_metrics_summary(experiment_id)

    # ============ 灰度发布（Rollout）=========== #

    def create_rollout_plan(
        self,
        experiment_id: str,
        module_name: str,
        new_version: str,
        stages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """创建灰度发布计划

        参数：
            experiment_id: 实验ID（用于跟踪）
            module_name: 模块名称
            new_version: 新版本号
            stages: 发布阶段列表 [{"name": "canary", "percentage": 5}, ...]

        返回：
            发布计划字典
        """
        # 转换为 controller 期望的格式
        rollout_stages = [
            {
                "name": s.get("name", f"stage_{i}"),
                "percentage": s["percentage"],
                "duration_hours": s.get("min_duration_hours", s.get("duration_hours", 24)),
                "metrics_threshold": {"success_rate": s.get("success_threshold", 0.95)},
            }
            for i, s in enumerate(stages)
        ]

        plan = self._rollout_controller.create_rollout_plan(
            experiment_id=experiment_id,
            module_name=module_name,
            new_version=new_version,
            stages=rollout_stages,
        )

        self._log(
            "info",
            "ExperimentOrchestrator",
            f"创建灰度发布计划: {module_name}",
            {
                "experiment_id": experiment_id,
                "new_version": new_version,
                "stage_count": len(stages),
            },
        )

        return {
            "experiment_id": plan.experiment_id,
            "module_name": plan.module_name,
            "new_version": plan.new_version,
            "current_stage": plan.current_stage,
            "stages": plan.stages,
        }

    def advance_rollout_stage(self, experiment_id: str) -> dict[str, Any]:
        """推进灰度发布阶段

        检查当前阶段指标是否达标，如果达标则推进到下一阶段。

        参数：
            experiment_id: 实验ID

        返回：
            推进结果 {"success": bool, "message": str, "current_stage": int}
        """
        result = self._rollout_controller.advance_stage(
            experiment_id=experiment_id,
            collector=self._metrics_collector,
        )

        # 获取当前阶段
        plan = self._rollout_controller.get_plan(experiment_id)
        current_stage = plan.current_stage if plan else 0

        self._log(
            "info",
            "ExperimentOrchestrator",
            f"灰度发布推进: {experiment_id}",
            {"success": result.success, "message": result.message},
        )

        return {
            "success": result.success,
            "message": result.message,
            "current_stage": current_stage,
        }

    def rollback_rollout(self, experiment_id: str) -> dict[str, Any]:
        """回滚灰度发布

        当指标不达标时回滚到上一版本。

        参数：
            experiment_id: 实验ID

        返回：
            回滚结果 {"success": bool, "message": str}
        """
        result = self._rollout_controller.rollback(experiment_id)

        # 获取当前阶段
        plan = self._rollout_controller.get_plan(experiment_id)
        current_stage = plan.current_stage if plan else 0

        self._log(
            "warning",
            "ExperimentOrchestrator",
            f"灰度发布回滚: {experiment_id}",
            {"success": result.success, "message": result.message},
        )

        return {
            "success": result.success,
            "message": result.message,
            "current_stage": current_stage,
        }

    def should_rollback_rollout(self, experiment_id: str) -> bool:
        """检查是否应该回滚

        参数：
            experiment_id: 实验ID

        返回：
            是否应该回滚
        """
        return self._rollout_controller.should_rollback(
            experiment_id=experiment_id,
            collector=self._metrics_collector,
        )

    # ============ 审计与查询 ============ #

    def get_experiment_audit_logs(self, experiment_id: str) -> list[dict[str, Any]]:
        """获取实验审计日志

        参数：
            experiment_id: 实验ID

        返回：
            审计日志列表
        """
        logs = self._experiment_manager.get_audit_logs(experiment_id)
        return [
            {
                "timestamp": log.timestamp.isoformat(),
                "action": log.action,
                "actor": log.actor,
                "details": log.details,
            }
            for log in logs
        ]

    def list_experiments(self, status: str | None = None) -> list[dict[str, Any]]:
        """列出所有实验

        参数：
            status: 可选的状态过滤 ("draft", "running", "paused", "completed")

        返回：
            实验列表
        """
        experiments = self._experiment_manager.list_experiments(status=status)
        return [exp.to_dict() for exp in experiments]

    def get_experiment(self, experiment_id: str) -> dict[str, Any] | None:
        """获取实验详情

        参数：
            experiment_id: 实验ID

        返回：
            实验配置字典或 None
        """
        config = self._experiment_manager.get_experiment(experiment_id)
        return config.to_dict() if config else None

    def check_experiment_metrics_threshold(
        self,
        experiment_id: str,
        variant: str,
        thresholds: dict[str, float],
    ) -> dict[str, Any]:
        """检查实验指标是否达到阈值

        参数：
            experiment_id: 实验ID
            variant: 变体名称
            thresholds: 阈值配置 {"success_rate": 0.95, "avg_duration": 5000}

        返回：
            检查结果 {"passed": bool, "details": {...}}
        """
        from src.domain.services.ab_testing_system import MetricsThresholdChecker

        checker = MetricsThresholdChecker()
        result = checker.check(
            experiment_id=experiment_id,
            variant=variant,
            collector=self._metrics_collector,
            threshold=thresholds,
        )

        return {
            "passed": result.passed,
            "details": result.details,
        }


__all__ = ["ExperimentOrchestrator"]
