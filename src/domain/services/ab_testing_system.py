"""A/B 测试与灰度发布系统

功能：
1. 实验配置管理
2. 用户分流分配
3. 指标采集与统计
4. 灰度发布控制
5. Coordinator 集成

创建日期：2025-12-07
"""

import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# =============================================================================
# 异常定义
# =============================================================================


class InvalidAllocationError(Exception):
    """无效的流量分配"""

    pass


class ExperimentNotFoundError(Exception):
    """实验未找到"""

    pass


class InvalidStatusTransitionError(Exception):
    """无效的状态转换"""

    pass


# =============================================================================
# 枚举定义
# =============================================================================


class ExperimentStatus(str, Enum):
    """实验状态"""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


# =============================================================================
# 数据结构
# =============================================================================


@dataclass
class ExperimentVariant:
    """实验变体

    Attributes:
        variant_id: 变体ID
        name: 变体名称（如 control, treatment）
        prompt_version: 对应的提示词版本
        allocation_percentage: 流量分配百分比
    """

    variant_id: str
    name: str
    prompt_version: str
    allocation_percentage: int


@dataclass
class ExperimentConfig:
    """实验配置

    Attributes:
        experiment_id: 实验ID
        name: 实验名称
        description: 实验描述
        module_name: 提示词模块名称
        control_version: 对照组版本
        treatment_version: 实验组版本
        traffic_allocation: 流量分配 {variant_name: percentage}
        status: 实验状态
        start_time: 开始时间
        end_time: 结束时间
        variants: 多变体配置（用于多变体实验）
    """

    experiment_id: str
    name: str
    description: str
    module_name: str
    control_version: str
    treatment_version: str
    traffic_allocation: dict[str, int]
    status: ExperimentStatus = ExperimentStatus.DRAFT
    start_time: datetime | None = None
    end_time: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    variants: dict[str, dict[str, Any]] = field(default_factory=dict)

    def validate_allocation(self) -> bool:
        """验证流量分配是否合计100"""
        total = sum(self.traffic_allocation.values())
        return total == 100

    def start(self) -> None:
        """启动实验"""
        if self.status not in [ExperimentStatus.DRAFT, ExperimentStatus.PAUSED]:
            raise InvalidStatusTransitionError(f"Cannot start from {self.status}")
        self.status = ExperimentStatus.RUNNING
        if not self.start_time:
            self.start_time = datetime.now()

    def pause(self) -> None:
        """暂停实验"""
        if self.status != ExperimentStatus.RUNNING:
            raise InvalidStatusTransitionError(f"Cannot pause from {self.status}")
        self.status = ExperimentStatus.PAUSED

    def resume(self) -> None:
        """恢复实验"""
        if self.status != ExperimentStatus.PAUSED:
            raise InvalidStatusTransitionError(f"Cannot resume from {self.status}")
        self.status = ExperimentStatus.RUNNING

    def complete(self) -> None:
        """完成实验"""
        if self.status not in [ExperimentStatus.RUNNING, ExperimentStatus.PAUSED]:
            raise InvalidStatusTransitionError(f"Cannot complete from {self.status}")
        self.status = ExperimentStatus.COMPLETED
        self.end_time = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """导出为字典"""
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "module_name": self.module_name,
            "control_version": self.control_version,
            "treatment_version": self.treatment_version,
            "traffic_allocation": self.traffic_allocation,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "variants": self.variants,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentConfig":
        """从字典导入"""
        config = cls(
            experiment_id=data["experiment_id"],
            name=data["name"],
            description=data["description"],
            module_name=data["module_name"],
            control_version=data["control_version"],
            treatment_version=data["treatment_version"],
            traffic_allocation=data["traffic_allocation"],
        )
        if "status" in data:
            config.status = ExperimentStatus(data["status"])
        if "start_time" in data and data["start_time"]:
            config.start_time = datetime.fromisoformat(data["start_time"])
        if "end_time" in data and data["end_time"]:
            config.end_time = datetime.fromisoformat(data["end_time"])
        if "variants" in data:
            config.variants = data["variants"]
        return config


@dataclass
class ExperimentAuditLog:
    """实验审计日志"""

    action: str
    experiment_id: str
    actor: str = "system"
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RolloutStage:
    """灰度发布阶段"""

    percentage: int
    duration_hours: int
    metrics_threshold: dict[str, float]


@dataclass
class RolloutPlan:
    """灰度发布计划"""

    experiment_id: str
    module_name: str
    new_version: str
    stages: list[dict[str, Any]]
    current_stage: int = 0
    status: str = "active"

    @property
    def current_percentage(self) -> int:
        if self.current_stage >= len(self.stages):
            return 100
        return self.stages[self.current_stage]["percentage"]


@dataclass
class RolloutResult:
    """灰度操作结果"""

    success: bool
    message: str = ""


@dataclass
class ThresholdCheckResult:
    """指标门槛检查结果"""

    passed: bool
    failed_metrics: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 指标采集器
# =============================================================================


class MetricsCollector:
    """指标采集器

    采集实验指标：
    - 成功率
    - 任务时长
    - 用户满意度
    """

    def __init__(self) -> None:
        # 成功记录: experiment_id -> variant -> [(user_id, success)]
        self._success_records: dict[str, dict[str, list[tuple[str, bool]]]] = {}
        # 时长记录: experiment_id -> variant -> [(user_id, duration_ms)]
        self._duration_records: dict[str, dict[str, list[tuple[str, int]]]] = {}
        # 满意度记录: experiment_id -> variant -> [(user_id, score)]
        self._satisfaction_records: dict[str, dict[str, list[tuple[str, int]]]] = {}
        self._lock = threading.RLock()

    def record_success(
        self,
        experiment_id: str,
        variant: str,
        user_id: str,
        success: bool,
    ) -> None:
        """记录成功/失败事件"""
        with self._lock:
            if experiment_id not in self._success_records:
                self._success_records[experiment_id] = {}
            if variant not in self._success_records[experiment_id]:
                self._success_records[experiment_id][variant] = []
            self._success_records[experiment_id][variant].append((user_id, success))

    def record_duration(
        self,
        experiment_id: str,
        variant: str,
        user_id: str,
        duration_ms: int,
    ) -> None:
        """记录任务时长"""
        with self._lock:
            if experiment_id not in self._duration_records:
                self._duration_records[experiment_id] = {}
            if variant not in self._duration_records[experiment_id]:
                self._duration_records[experiment_id][variant] = []
            self._duration_records[experiment_id][variant].append((user_id, duration_ms))

    def record_satisfaction(
        self,
        experiment_id: str,
        variant: str,
        user_id: str,
        score: int,
    ) -> None:
        """记录满意度评分"""
        with self._lock:
            if experiment_id not in self._satisfaction_records:
                self._satisfaction_records[experiment_id] = {}
            if variant not in self._satisfaction_records[experiment_id]:
                self._satisfaction_records[experiment_id][variant] = []
            self._satisfaction_records[experiment_id][variant].append((user_id, score))

    def get_success_rate(self, experiment_id: str, variant: str) -> float:
        """获取成功率"""
        with self._lock:
            records = self._success_records.get(experiment_id, {}).get(variant, [])
            if not records:
                return 0.0
            successes = sum(1 for _, s in records if s)
            return successes / len(records)

    def get_average_duration(self, experiment_id: str, variant: str) -> float:
        """获取平均时长"""
        with self._lock:
            records = self._duration_records.get(experiment_id, {}).get(variant, [])
            if not records:
                return 0.0
            total = sum(d for _, d in records)
            return total / len(records)

    def get_average_satisfaction(self, experiment_id: str, variant: str) -> float:
        """获取平均满意度"""
        with self._lock:
            records = self._satisfaction_records.get(experiment_id, {}).get(variant, [])
            if not records:
                return 0.0
            total = sum(s for _, s in records)
            return total / len(records)

    def get_metrics_summary(self, experiment_id: str) -> dict[str, dict[str, float]]:
        """获取实验指标汇总"""
        with self._lock:
            result: dict[str, dict[str, float]] = {}

            # 获取所有变体
            variants = set()
            if experiment_id in self._success_records:
                variants.update(self._success_records[experiment_id].keys())
            if experiment_id in self._duration_records:
                variants.update(self._duration_records[experiment_id].keys())
            if experiment_id in self._satisfaction_records:
                variants.update(self._satisfaction_records[experiment_id].keys())

            for variant in variants:
                result[variant] = {
                    "success_rate": self.get_success_rate(experiment_id, variant),
                    "avg_duration": self.get_average_duration(experiment_id, variant),
                    "avg_satisfaction": self.get_average_satisfaction(experiment_id, variant),
                    "sample_count": len(
                        self._success_records.get(experiment_id, {}).get(variant, [])
                    ),
                }

            return result


# =============================================================================
# 指标门槛检查器
# =============================================================================


class MetricsThresholdChecker:
    """指标门槛检查器"""

    def check(
        self,
        experiment_id: str,
        variant: str,
        collector: MetricsCollector,
        threshold: dict[str, float],
    ) -> ThresholdCheckResult:
        """检查指标是否达标

        Args:
            experiment_id: 实验ID
            variant: 变体名称
            collector: 指标采集器
            threshold: 门槛配置

        Returns:
            ThresholdCheckResult: 检查结果
        """
        failed_metrics: list[str] = []
        details: dict[str, Any] = {}

        # 检查成功率
        if "success_rate" in threshold:
            success_rate = collector.get_success_rate(experiment_id, variant)
            details["success_rate"] = success_rate
            if success_rate < threshold["success_rate"]:
                failed_metrics.append("success_rate")

        # 检查时长（时长是越低越好，所以检查是否超过阈值）
        if "avg_duration" in threshold:
            avg_duration = collector.get_average_duration(experiment_id, variant)
            details["avg_duration"] = avg_duration
            if avg_duration > threshold["avg_duration"]:
                failed_metrics.append("avg_duration")

        # 检查满意度
        if "avg_satisfaction" in threshold:
            avg_satisfaction = collector.get_average_satisfaction(experiment_id, variant)
            details["avg_satisfaction"] = avg_satisfaction
            if avg_satisfaction < threshold["avg_satisfaction"]:
                failed_metrics.append("avg_satisfaction")

        return ThresholdCheckResult(
            passed=len(failed_metrics) == 0,
            failed_metrics=failed_metrics,
            details=details,
        )


# =============================================================================
# 实验管理器
# =============================================================================


class ExperimentManager:
    """实验管理器

    负责：
    1. 实验配置管理
    2. 用户分流分配
    3. 实验生命周期管理
    """

    def __init__(self) -> None:
        # 实验存储: experiment_id -> ExperimentConfig
        self._experiments: dict[str, ExperimentConfig] = {}
        # 模块实验映射: module_name -> experiment_id
        self._module_experiments: dict[str, str] = {}
        # 用户分配缓存: (experiment_id, user_id) -> variant
        self._assignment_cache: dict[tuple[str, str], str] = {}
        # 审计日志: experiment_id -> [AuditLog]
        self._audit_logs: dict[str, list[ExperimentAuditLog]] = {}
        self._lock = threading.RLock()

    def create_experiment(
        self,
        experiment_id: str,
        name: str,
        description: str,
        module_name: str,
        control_version: str,
        treatment_version: str,
        traffic_allocation: dict[str, int],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> ExperimentConfig:
        """创建实验"""
        with self._lock:
            config = ExperimentConfig(
                experiment_id=experiment_id,
                name=name,
                description=description,
                module_name=module_name,
                control_version=control_version,
                treatment_version=treatment_version,
                traffic_allocation=traffic_allocation,
                start_time=start_time,
                end_time=end_time,
            )

            self._experiments[experiment_id] = config
            self._module_experiments[module_name] = experiment_id
            self._audit_logs[experiment_id] = []

            self._add_audit_log(experiment_id, "create", {"name": name})

            return config

    def create_multi_variant_experiment(
        self,
        experiment_id: str,
        name: str,
        description: str,
        module_name: str,
        variants: dict[str, dict[str, Any]],
    ) -> ExperimentConfig:
        """创建多变体实验

        Args:
            experiment_id: 实验ID
            name: 实验名称
            description: 描述
            module_name: 模块名称
            variants: 变体配置 {variant_name: {"version": "x.x.x", "allocation": int}}
        """
        with self._lock:
            # 构建流量分配
            traffic_allocation = {v: variants[v]["allocation"] for v in variants}

            # 找到 control 和第一个 treatment
            control_version = ""
            treatment_version = ""
            for v_name, v_config in variants.items():
                if v_name == "control":
                    control_version = v_config["version"]
                elif not treatment_version:
                    treatment_version = v_config["version"]

            config = ExperimentConfig(
                experiment_id=experiment_id,
                name=name,
                description=description,
                module_name=module_name,
                control_version=control_version,
                treatment_version=treatment_version,
                traffic_allocation=traffic_allocation,
                variants=variants,
            )

            self._experiments[experiment_id] = config
            self._module_experiments[module_name] = experiment_id
            self._audit_logs[experiment_id] = []

            self._add_audit_log(experiment_id, "create", {"name": name, "multi_variant": True})

            return config

    def get_experiment(self, experiment_id: str) -> ExperimentConfig:
        """获取实验配置"""
        with self._lock:
            if experiment_id not in self._experiments:
                raise ExperimentNotFoundError(f"Experiment {experiment_id} not found")
            return self._experiments[experiment_id]

    def start_experiment(self, experiment_id: str) -> None:
        """启动实验"""
        with self._lock:
            experiment = self.get_experiment(experiment_id)
            experiment.start()
            self._add_audit_log(experiment_id, "start")

    def pause_experiment(self, experiment_id: str) -> None:
        """暂停实验"""
        with self._lock:
            experiment = self.get_experiment(experiment_id)
            experiment.pause()
            self._add_audit_log(experiment_id, "pause")

    def resume_experiment(self, experiment_id: str) -> None:
        """恢复实验"""
        with self._lock:
            experiment = self.get_experiment(experiment_id)
            experiment.resume()
            self._add_audit_log(experiment_id, "resume")

    def complete_experiment(self, experiment_id: str) -> None:
        """完成实验"""
        with self._lock:
            experiment = self.get_experiment(experiment_id)
            experiment.complete()
            self._add_audit_log(experiment_id, "complete")

    def check_experiment_expiry(self, experiment_id: str) -> None:
        """检查实验是否过期"""
        with self._lock:
            experiment = self.get_experiment(experiment_id)
            if experiment.end_time and datetime.now() > experiment.end_time:
                if experiment.status == ExperimentStatus.RUNNING:
                    experiment.complete()
                    self._add_audit_log(experiment_id, "auto_complete", {"reason": "expired"})

    def assign_variant(self, experiment_id: str, user_id: str) -> str:
        """为用户分配变体

        使用确定性哈希算法确保同一用户始终分配到同一变体
        """
        with self._lock:
            # 检查缓存
            cache_key = (experiment_id, user_id)
            if cache_key in self._assignment_cache:
                return self._assignment_cache[cache_key]

            experiment = self.get_experiment(experiment_id)

            # 计算哈希值
            hash_input = f"{experiment_id}:{user_id}".encode()
            hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
            bucket = hash_value % 100  # 0-99

            # 根据流量分配确定变体
            cumulative = 0
            variant = "control"  # 默认

            for variant_name, allocation in experiment.traffic_allocation.items():
                cumulative += allocation
                if bucket < cumulative:
                    variant = variant_name
                    break

            # 缓存结果
            self._assignment_cache[cache_key] = variant

            return variant

    def get_version_for_variant(self, experiment_id: str, variant: str) -> str:
        """获取变体对应的版本"""
        with self._lock:
            experiment = self.get_experiment(experiment_id)

            # 多变体实验
            if experiment.variants and variant in experiment.variants:
                return experiment.variants[variant]["version"]

            # 标准 A/B 实验
            if variant == "control":
                return experiment.control_version
            else:
                return experiment.treatment_version

    def get_experiment_for_module(self, module_name: str) -> ExperimentConfig | None:
        """获取模块当前的活跃实验"""
        with self._lock:
            experiment_id = self._module_experiments.get(module_name)
            if not experiment_id:
                return None
            experiment = self._experiments.get(experiment_id)
            if experiment and experiment.status == ExperimentStatus.RUNNING:
                return experiment
            return None

    def get_audit_logs(self, experiment_id: str) -> list[ExperimentAuditLog]:
        """获取审计日志"""
        with self._lock:
            return list(self._audit_logs.get(experiment_id, []))

    def list_experiments(self, status: str | None = None) -> list[ExperimentConfig]:
        """列出所有实验

        参数：
            status: 可选的状态过滤 ("draft", "running", "paused", "completed")

        返回：
            实验配置列表
        """
        with self._lock:
            experiments = list(self._experiments.values())
            if status:
                experiments = [e for e in experiments if e.status.value == status]
            return experiments

    def _add_audit_log(
        self,
        experiment_id: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """添加审计日志"""
        log = ExperimentAuditLog(
            action=action,
            experiment_id=experiment_id,
            details=details or {},
        )
        if experiment_id not in self._audit_logs:
            self._audit_logs[experiment_id] = []
        self._audit_logs[experiment_id].append(log)


# =============================================================================
# 灰度发布控制器
# =============================================================================


class GradualRolloutController:
    """灰度发布控制器

    负责：
    1. 灰度计划管理
    2. 阶段推进
    3. 回滚控制
    """

    def __init__(self) -> None:
        # 灰度计划: experiment_id -> RolloutPlan
        self._plans: dict[str, RolloutPlan] = {}
        self._lock = threading.RLock()

    def create_rollout_plan(
        self,
        experiment_id: str,
        module_name: str,
        new_version: str,
        stages: list[dict[str, Any]],
    ) -> RolloutPlan:
        """创建灰度发布计划"""
        with self._lock:
            plan = RolloutPlan(
                experiment_id=experiment_id,
                module_name=module_name,
                new_version=new_version,
                stages=stages,
            )
            self._plans[experiment_id] = plan
            return plan

    def get_plan(self, experiment_id: str) -> RolloutPlan | None:
        """获取灰度计划"""
        with self._lock:
            return self._plans.get(experiment_id)

    def advance_stage(
        self,
        experiment_id: str,
        collector: MetricsCollector,
    ) -> RolloutResult:
        """推进灰度阶段"""
        with self._lock:
            plan = self._plans.get(experiment_id)
            if not plan:
                return RolloutResult(success=False, message="Plan not found")

            if plan.status != "active":
                return RolloutResult(success=False, message=f"Plan status is {plan.status}")

            current_stage = (
                plan.stages[plan.current_stage] if plan.current_stage < len(plan.stages) else None
            )

            if current_stage:
                # 检查门槛
                threshold = current_stage.get("metrics_threshold", {})
                if threshold:
                    checker = MetricsThresholdChecker()
                    result = checker.check(experiment_id, "treatment", collector, threshold)
                    if not result.passed:
                        return RolloutResult(
                            success=False,
                            message=f"Metrics not met: {result.failed_metrics}",
                        )

            # 推进阶段
            plan.current_stage += 1

            # 检查是否完成
            if plan.current_stage >= len(plan.stages):
                plan.status = "completed"

            return RolloutResult(success=True, message="Advanced to next stage")

    def should_rollback(
        self,
        experiment_id: str,
        collector: MetricsCollector,
    ) -> bool:
        """检查是否需要回滚"""
        with self._lock:
            plan = self._plans.get(experiment_id)
            if not plan or plan.status != "active":
                return False

            current_stage = (
                plan.stages[plan.current_stage] if plan.current_stage < len(plan.stages) else None
            )

            if not current_stage:
                return False

            threshold = current_stage.get("metrics_threshold", {})
            if not threshold:
                return False

            checker = MetricsThresholdChecker()
            result = checker.check(experiment_id, "treatment", collector, threshold)

            return not result.passed

    def rollback(self, experiment_id: str) -> RolloutResult:
        """执行回滚"""
        with self._lock:
            plan = self._plans.get(experiment_id)
            if not plan:
                return RolloutResult(success=False, message="Plan not found")

            plan.status = "rolled_back"
            plan.current_stage = 0

            return RolloutResult(success=True, message="Rolled back successfully")


# =============================================================================
# Coordinator 适配器
# =============================================================================


class CoordinatorExperimentAdapter:
    """Coordinator 实验适配器

    提供给 CoordinatorAgent 使用的实验接口
    """

    def __init__(
        self,
        manager: ExperimentManager,
        collector: MetricsCollector | None = None,
    ) -> None:
        self._manager = manager
        self._collector = collector or MetricsCollector()

    def get_version_for_user(
        self,
        module_name: str,
        user_id: str,
    ) -> str:
        """为用户获取提示词版本

        如果模块有活跃实验，根据分配返回对应版本；
        否则返回默认版本。
        """
        experiment = self._manager.get_experiment_for_module(module_name)

        if not experiment:
            # 没有活跃实验，返回 None 让调用者使用默认版本
            return ""

        variant = self._manager.assign_variant(experiment.experiment_id, user_id)
        return self._manager.get_version_for_variant(experiment.experiment_id, variant)

    def record_interaction(
        self,
        module_name: str,
        user_id: str,
        success: bool,
        duration_ms: int = 0,
        satisfaction: int = 0,
    ) -> None:
        """记录用户交互指标"""
        experiment = self._manager.get_experiment_for_module(module_name)

        if not experiment:
            return

        variant = self._manager.assign_variant(experiment.experiment_id, user_id)

        if success is not None:
            self._collector.record_success(
                experiment.experiment_id,
                variant,
                user_id,
                success,
            )

        if duration_ms > 0:
            self._collector.record_duration(
                experiment.experiment_id,
                variant,
                user_id,
                duration_ms,
            )

        if satisfaction > 0:
            self._collector.record_satisfaction(
                experiment.experiment_id,
                variant,
                user_id,
                satisfaction,
            )

    def get_experiment_report(self, experiment_id: str) -> dict[str, Any]:
        """获取实验报告"""
        experiment = self._manager.get_experiment(experiment_id)
        metrics = self._collector.get_metrics_summary(experiment_id)

        # 分析胜者
        winner = None
        if "control" in metrics and "treatment" in metrics:
            control_rate = metrics["control"].get("success_rate", 0)
            treatment_rate = metrics["treatment"].get("success_rate", 0)

            if treatment_rate > control_rate * 1.05:  # 5% 显著提升
                winner = "treatment"
            elif control_rate > treatment_rate * 1.05:
                winner = "control"

        report: dict[str, Any] = {
            "experiment_id": experiment_id,
            "name": experiment.name,
            "status": experiment.status.value,
            "variants": metrics,
        }

        if winner:
            report["winner"] = winner
        else:
            report["inconclusive"] = True

        return report
