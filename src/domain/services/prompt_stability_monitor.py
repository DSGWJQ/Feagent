"""提示词稳定性监控与审计模块

提供以下功能：
1. 提示词使用日志记录
2. 版本/模块/场景/输出格式漂移检测
3. 输出格式验证
4. 审计协调与警报
5. 稳定性监控与报表生成
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# ============================================================================
# 枚举类型定义
# ============================================================================


class DriftType(str, Enum):
    """漂移类型"""

    VERSION = "version"
    MODULE = "module"
    SCENARIO = "scenario"
    OUTPUT_FORMAT = "output_format"


class ValidationErrorType(str, Enum):
    """验证错误类型"""

    JSON_PARSE_ERROR = "json_parse_error"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    STRUCTURE_TOO_DEEP = "structure_too_deep"
    OUTPUT_TOO_LARGE = "output_too_large"
    MISSING_EXPECTED_KEY = "missing_expected_key"
    TYPE_MISMATCH = "type_mismatch"


class AlertType(str, Enum):
    """警报类型"""

    DRIFT_DETECTED = "drift_detected"
    FORMAT_VIOLATION = "format_violation"
    STABILITY_ISSUE = "stability_issue"
    THRESHOLD_EXCEEDED = "threshold_exceeded"


class AlertLevel(str, Enum):
    """警报级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class StabilityStatus(str, Enum):
    """稳定性状态"""

    STABLE = "stable"
    DEGRADED = "degraded"
    UNSTABLE = "unstable"
    UNKNOWN = "unknown"


# ============================================================================
# 数据类定义
# ============================================================================


@dataclass
class PromptUsageLog:
    """提示词使用日志"""

    session_id: str
    prompt_version: str
    module_combination: list[str]
    scenario: str
    task_prompt: str
    expected_output_format: str
    log_id: str = field(default_factory=lambda: f"log_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.now)
    actual_output: str | None = None
    output_valid: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "log_id": self.log_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "prompt_version": self.prompt_version,
            "module_combination": self.module_combination,
            "scenario": self.scenario,
            "task_prompt": self.task_prompt,
            "expected_output_format": self.expected_output_format,
            "actual_output": self.actual_output,
            "output_valid": self.output_valid,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptUsageLog:
        """从字典创建"""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            log_id=data.get("log_id", f"log_{uuid.uuid4().hex[:12]}"),
            session_id=data["session_id"],
            timestamp=timestamp,
            prompt_version=data["prompt_version"],
            module_combination=data["module_combination"],
            scenario=data["scenario"],
            task_prompt=data["task_prompt"],
            expected_output_format=data["expected_output_format"],
            actual_output=data.get("actual_output"),
            output_valid=data.get("output_valid"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ValidationError:
    """验证错误"""

    error_type: ValidationErrorType
    message: str
    location: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutputValidationResult:
    """输出验证结果"""

    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


@dataclass
class DriftDetectionResult:
    """漂移检测结果"""

    drift_detected: bool
    drift_type: DriftType | None
    details: dict[str, Any] = field(default_factory=dict)
    affected_logs: list[str] = field(default_factory=list)


@dataclass
class AuditAlert:
    """审计警报"""

    alert_type: AlertType
    alert_level: AlertLevel
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    alert_id: str = field(default_factory=lambda: f"alert_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "alert_level": self.alert_level.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StabilityMetrics:
    """稳定性指标"""

    status: StabilityStatus
    total_logs: int
    version_consistency: float
    module_consistency: float
    output_validity_rate: float
    scenario_compliance: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "total_logs": self.total_logs,
            "version_consistency": self.version_consistency,
            "module_consistency": self.module_consistency,
            "output_validity_rate": self.output_validity_rate,
            "scenario_compliance": self.scenario_compliance,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AuditResult:
    """审计结果"""

    logs_analyzed: int
    drifts_detected: int
    format_violations: int
    alerts: list[AuditAlert]
    stability_metrics: StabilityMetrics
    audit_id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=datetime.now)

    def get_summary(self) -> dict[str, Any]:
        """获取摘要"""
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp.isoformat(),
            "logs_analyzed": self.logs_analyzed,
            "drifts_detected": self.drifts_detected,
            "format_violations": self.format_violations,
            "alert_count": len(self.alerts),
            "stability_status": self.stability_metrics.status.value,
        }


# ============================================================================
# 提示词使用日志记录器
# ============================================================================


class PromptUsageLogger:
    """提示词使用日志记录器"""

    def __init__(self) -> None:
        self._logs: dict[str, PromptUsageLog] = {}
        self._session_index: dict[str, list[str]] = defaultdict(list)
        self._version_index: dict[str, list[str]] = defaultdict(list)

    def log_prompt_usage(
        self,
        session_id: str,
        prompt_version: str,
        module_combination: list[str],
        scenario: str,
        task_prompt: str,
        expected_output_format: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """记录提示词使用"""
        log = PromptUsageLog(
            session_id=session_id,
            prompt_version=prompt_version,
            module_combination=module_combination,
            scenario=scenario,
            task_prompt=task_prompt,
            expected_output_format=expected_output_format,
            metadata=metadata or {},
        )

        self._logs[log.log_id] = log
        self._session_index[session_id].append(log.log_id)
        self._version_index[prompt_version].append(log.log_id)

        return log.log_id

    def get_usage_history(self) -> list[PromptUsageLog]:
        """获取使用历史"""
        return list(self._logs.values())

    def get_usage_by_session(self, session_id: str) -> list[PromptUsageLog]:
        """按会话获取使用记录"""
        log_ids = self._session_index.get(session_id, [])
        return [self._logs[log_id] for log_id in log_ids if log_id in self._logs]

    def get_usage_by_version(self, version: str) -> list[PromptUsageLog]:
        """按版本获取使用记录"""
        log_ids = self._version_index.get(version, [])
        return [self._logs[log_id] for log_id in log_ids if log_id in self._logs]

    def get_log_by_id(self, log_id: str) -> PromptUsageLog | None:
        """按 ID 获取日志"""
        return self._logs.get(log_id)

    def update_actual_output(
        self,
        log_id: str,
        actual_output: str,
        output_valid: bool,
    ) -> None:
        """更新实际输出"""
        if log_id in self._logs:
            self._logs[log_id].actual_output = actual_output
            self._logs[log_id].output_valid = output_valid

    def get_usage_statistics(self) -> dict[str, Any]:
        """获取使用统计"""
        logs = list(self._logs.values())

        by_version: dict[str, int] = defaultdict(int)
        by_scenario: dict[str, int] = defaultdict(int)
        sessions = set()

        for log in logs:
            by_version[log.prompt_version] += 1
            by_scenario[log.scenario] += 1
            sessions.add(log.session_id)

        return {
            "total_logs": len(logs),
            "unique_sessions": len(sessions),
            "by_version": dict(by_version),
            "by_scenario": dict(by_scenario),
        }


# ============================================================================
# 提示漂移检测器
# ============================================================================


class PromptDriftDetector:
    """提示漂移检测器"""

    def detect_version_drift(
        self,
        logs: list[PromptUsageLog],
    ) -> DriftDetectionResult:
        """检测版本漂移"""
        if not logs:
            return DriftDetectionResult(
                drift_detected=False,
                drift_type=None,
                details={},
                affected_logs=[],
            )

        versions = {log.prompt_version for log in logs}

        if len(versions) > 1:
            return DriftDetectionResult(
                drift_detected=True,
                drift_type=DriftType.VERSION,
                details={
                    "versions": list(versions),
                    "version_count": len(versions),
                },
                affected_logs=[log.log_id for log in logs],
            )

        return DriftDetectionResult(
            drift_detected=False,
            drift_type=None,
            details={"versions": list(versions)},
            affected_logs=[],
        )

    def detect_module_drift(
        self,
        logs: list[PromptUsageLog],
        expected_modules: list[str] | None = None,
    ) -> DriftDetectionResult:
        """检测模块组合漂移"""
        if not logs:
            return DriftDetectionResult(
                drift_detected=False,
                drift_type=None,
                details={},
                affected_logs=[],
            )

        affected_logs = []
        module_variations = set()

        for log in logs:
            module_key = tuple(sorted(log.module_combination))
            module_variations.add(module_key)

            if expected_modules:
                expected_set = set(expected_modules)
                actual_set = set(log.module_combination)
                if expected_set != actual_set:
                    affected_logs.append(log.log_id)

        if affected_logs or len(module_variations) > 1:
            return DriftDetectionResult(
                drift_detected=True,
                drift_type=DriftType.MODULE,
                details={
                    "module_variations": [list(m) for m in module_variations],
                    "expected_modules": expected_modules,
                },
                affected_logs=affected_logs,
            )

        return DriftDetectionResult(
            drift_detected=False,
            drift_type=None,
            details={},
            affected_logs=[],
        )

    def detect_output_format_drift(
        self,
        logs: list[PromptUsageLog],
    ) -> DriftDetectionResult:
        """检测输出格式漂移"""
        if not logs:
            return DriftDetectionResult(
                drift_detected=False,
                drift_type=None,
                details={},
                affected_logs=[],
            )

        invalid_logs = []
        for log in logs:
            if log.output_valid is False:
                invalid_logs.append(log.log_id)

        if invalid_logs:
            return DriftDetectionResult(
                drift_detected=True,
                drift_type=DriftType.OUTPUT_FORMAT,
                details={
                    "invalid_count": len(invalid_logs),
                    "total_count": len(logs),
                    "invalid_rate": len(invalid_logs) / len(logs),
                },
                affected_logs=invalid_logs,
            )

        return DriftDetectionResult(
            drift_detected=False,
            drift_type=None,
            details={},
            affected_logs=[],
        )

    def detect_scenario_drift(
        self,
        logs: list[PromptUsageLog],
        allowed_scenarios: list[str] | None = None,
    ) -> DriftDetectionResult:
        """检测场景漂移"""
        if not logs or not allowed_scenarios:
            return DriftDetectionResult(
                drift_detected=False,
                drift_type=None,
                details={},
                affected_logs=[],
            )

        allowed_set = set(allowed_scenarios)
        affected_logs = []
        unknown_scenarios = set()

        for log in logs:
            if log.scenario not in allowed_set:
                affected_logs.append(log.log_id)
                unknown_scenarios.add(log.scenario)

        if affected_logs:
            return DriftDetectionResult(
                drift_detected=True,
                drift_type=DriftType.SCENARIO,
                details={
                    "unknown_scenarios": list(unknown_scenarios),
                    "allowed_scenarios": allowed_scenarios,
                },
                affected_logs=affected_logs,
            )

        return DriftDetectionResult(
            drift_detected=False,
            drift_type=None,
            details={},
            affected_logs=[],
        )

    def detect_all_drifts(
        self,
        logs: list[PromptUsageLog],
        expected_modules: list[str] | None = None,
        allowed_scenarios: list[str] | None = None,
    ) -> list[DriftDetectionResult]:
        """检测所有类型的漂移"""
        results = []

        # 版本漂移
        version_result = self.detect_version_drift(logs)
        if version_result.drift_detected:
            results.append(version_result)

        # 模块漂移
        module_result = self.detect_module_drift(logs, expected_modules)
        if module_result.drift_detected:
            results.append(module_result)

        # 输出格式漂移
        output_result = self.detect_output_format_drift(logs)
        if output_result.drift_detected:
            results.append(output_result)

        # 场景漂移
        scenario_result = self.detect_scenario_drift(logs, allowed_scenarios)
        if scenario_result.drift_detected:
            results.append(scenario_result)

        return results


# ============================================================================
# 输出格式验证器
# ============================================================================


class OutputFormatValidator:
    """输出格式验证器"""

    def __init__(
        self,
        max_depth: int = 10,
        max_output_size: int = 1000000,  # 1MB
    ) -> None:
        self.max_depth = max_depth
        self.max_output_size = max_output_size

    def validate_json_format(self, output: str) -> OutputValidationResult:
        """验证 JSON 格式"""
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []

        # 检查大小
        if len(output) > self.max_output_size:
            errors.append(
                ValidationError(
                    error_type=ValidationErrorType.OUTPUT_TOO_LARGE,
                    message=f"输出大小 {len(output)} 超过限制 {self.max_output_size}",
                    location="root",
                )
            )
            return OutputValidationResult(is_valid=False, errors=errors)

        # 尝试解析 JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            errors.append(
                ValidationError(
                    error_type=ValidationErrorType.JSON_PARSE_ERROR,
                    message=f"JSON 解析错误: {str(e)}",
                    location="root",
                )
            )
            return OutputValidationResult(is_valid=False, errors=errors)

        # 检查深度
        depth = self._get_depth(data)
        if depth > self.max_depth:
            errors.append(
                ValidationError(
                    error_type=ValidationErrorType.STRUCTURE_TOO_DEEP,
                    message=f"结构深度 {depth} 超过限制 {self.max_depth}",
                    location="root",
                )
            )
            return OutputValidationResult(is_valid=False, errors=errors)

        return OutputValidationResult(
            is_valid=True,
            errors=errors,
            warnings=warnings,
        )

    def _get_depth(self, obj: Any, current_depth: int = 1) -> int:
        """获取对象深度"""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._get_depth(v, current_depth + 1) for v in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._get_depth(item, current_depth + 1) for item in obj)
        return current_depth

    def validate_against_template(
        self,
        output: str,
        template: dict[str, Any],
    ) -> OutputValidationResult:
        """对比模板验证"""
        errors: list[ValidationError] = []

        # 先验证 JSON 格式
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            errors.append(
                ValidationError(
                    error_type=ValidationErrorType.JSON_PARSE_ERROR,
                    message=f"JSON 解析错误: {str(e)}",
                    location="root",
                )
            )
            return OutputValidationResult(is_valid=False, errors=errors)

        # 检查必需字段
        required_fields = template.get("required", [])
        for field_name in required_fields:
            if field_name not in data:
                errors.append(
                    ValidationError(
                        error_type=ValidationErrorType.MISSING_REQUIRED_FIELD,
                        message=f"缺少必需字段: {field_name}",
                        location=field_name,
                    )
                )

        # 检查属性类型
        properties = template.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if prop_name in data:
                expected_type = prop_schema.get("type")
                actual_value = data[prop_name]
                if not self._check_type(actual_value, expected_type):
                    errors.append(
                        ValidationError(
                            error_type=ValidationErrorType.TYPE_MISMATCH,
                            message=f"字段 {prop_name} 类型不匹配，期望 {expected_type}",
                            location=prop_name,
                        )
                    )

        return OutputValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def _check_type(self, value: Any, expected_type: str | None) -> bool:
        """检查类型"""
        if expected_type is None:
            return True

        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type is None:
            return True

        return isinstance(value, expected_python_type)

    def validate_expected_keys(
        self,
        output: str,
        expected_keys: list[str],
    ) -> OutputValidationResult:
        """验证期望的键"""
        errors: list[ValidationError] = []

        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            errors.append(
                ValidationError(
                    error_type=ValidationErrorType.JSON_PARSE_ERROR,
                    message=f"JSON 解析错误: {str(e)}",
                    location="root",
                )
            )
            return OutputValidationResult(is_valid=False, errors=errors)

        if not isinstance(data, dict):
            errors.append(
                ValidationError(
                    error_type=ValidationErrorType.TYPE_MISMATCH,
                    message="期望对象类型",
                    location="root",
                )
            )
            return OutputValidationResult(is_valid=False, errors=errors)

        for key in expected_keys:
            if key not in data:
                errors.append(
                    ValidationError(
                        error_type=ValidationErrorType.MISSING_EXPECTED_KEY,
                        message=f"缺少期望的键: {key}",
                        location=key,
                    )
                )

        return OutputValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )


# ============================================================================
# 提示词审计协调者
# ============================================================================


class PromptAuditCoordinator:
    """提示词审计协调者"""

    def __init__(
        self,
        logger: PromptUsageLogger,
        expected_modules: list[str] | None = None,
        allowed_scenarios: list[str] | None = None,
    ) -> None:
        self._logger = logger
        self._expected_modules = expected_modules
        self._allowed_scenarios = allowed_scenarios
        self._drift_detector = PromptDriftDetector()
        self._validator = OutputFormatValidator()
        self._alerts: list[AuditAlert] = []
        self._alert_callbacks: list[Callable[[AuditAlert], None]] = []

    def run_audit(self) -> AuditResult:
        """运行审计"""
        logs = self._logger.get_usage_history()
        alerts: list[AuditAlert] = []
        drifts_detected = 0
        format_violations = 0

        # 检测漂移
        drift_results = self._drift_detector.detect_all_drifts(
            logs,
            expected_modules=self._expected_modules,
            allowed_scenarios=self._allowed_scenarios,
        )

        for drift_result in drift_results:
            if drift_result.drift_detected:
                drifts_detected += 1
                drift_type_value = (
                    drift_result.drift_type.value if drift_result.drift_type else "unknown"
                )
                alert = self.trigger_alert(
                    alert_type=AlertType.DRIFT_DETECTED,
                    alert_level=AlertLevel.WARNING,
                    message=f"检测到{drift_type_value}漂移",
                    details=drift_result.details,
                )
                alerts.append(alert)

        # 统计格式违规
        for log in logs:
            if log.output_valid is False:
                format_violations += 1

        if format_violations > 0:
            alert = self.trigger_alert(
                alert_type=AlertType.FORMAT_VIOLATION,
                alert_level=AlertLevel.ERROR,
                message=f"检测到 {format_violations} 次格式违规",
                details={"violation_count": format_violations},
            )
            alerts.append(alert)

        # 计算稳定性指标
        stability_metrics = self._calculate_stability_metrics(logs)

        return AuditResult(
            logs_analyzed=len(logs),
            drifts_detected=drifts_detected,
            format_violations=format_violations,
            alerts=alerts,
            stability_metrics=stability_metrics,
        )

    def _calculate_stability_metrics(
        self,
        logs: list[PromptUsageLog],
    ) -> StabilityMetrics:
        """计算稳定性指标"""
        if not logs:
            return StabilityMetrics(
                status=StabilityStatus.UNKNOWN,
                total_logs=0,
                version_consistency=0.0,
                module_consistency=0.0,
                output_validity_rate=0.0,
                scenario_compliance=0.0,
            )

        # 版本一致性
        versions = [log.prompt_version for log in logs]
        most_common_version = max(set(versions), key=versions.count)
        version_consistency = versions.count(most_common_version) / len(versions)

        # 模块一致性
        module_sets = [tuple(sorted(log.module_combination)) for log in logs]
        most_common_modules = max(set(module_sets), key=module_sets.count)
        module_consistency = module_sets.count(most_common_modules) / len(module_sets)

        # 输出有效率
        logs_with_output = [log for log in logs if log.output_valid is not None]
        if logs_with_output:
            valid_count = sum(1 for log in logs_with_output if log.output_valid)
            output_validity_rate = valid_count / len(logs_with_output)
        else:
            output_validity_rate = 1.0

        # 场景合规率
        if self._allowed_scenarios:
            compliant = sum(1 for log in logs if log.scenario in self._allowed_scenarios)
            scenario_compliance = compliant / len(logs)
        else:
            scenario_compliance = 1.0

        # 确定状态
        avg_score = (
            version_consistency + module_consistency + output_validity_rate + scenario_compliance
        ) / 4

        if avg_score >= 0.9:
            status = StabilityStatus.STABLE
        elif avg_score >= 0.7:
            status = StabilityStatus.DEGRADED
        else:
            status = StabilityStatus.UNSTABLE

        return StabilityMetrics(
            status=status,
            total_logs=len(logs),
            version_consistency=version_consistency,
            module_consistency=module_consistency,
            output_validity_rate=output_validity_rate,
            scenario_compliance=scenario_compliance,
        )

    def generate_report(self) -> dict[str, Any]:
        """生成报表"""
        stats = self._logger.get_usage_statistics()

        # 运行审计
        audit_result = self.run_audit()

        return {
            "total_logs": stats["total_logs"],
            "unique_sessions": stats["unique_sessions"],
            "version_distribution": stats["by_version"],
            "scenario_distribution": stats["by_scenario"],
            "audit_summary": audit_result.get_summary(),
            "stability_metrics": audit_result.stability_metrics.to_dict(),
            "alert_count": len(audit_result.alerts),
            "generated_at": datetime.now().isoformat(),
        }

    def trigger_alert(
        self,
        alert_type: AlertType,
        alert_level: AlertLevel,
        message: str,
        details: dict[str, Any],
    ) -> AuditAlert:
        """触发警报"""
        alert = AuditAlert(
            alert_type=alert_type,
            alert_level=alert_level,
            message=message,
            details=details,
        )

        self._alerts.append(alert)

        # 调用回调
        for callback in self._alert_callbacks:
            callback(alert)

        return alert

    def register_alert_callback(
        self,
        callback: Callable[[AuditAlert], None],
    ) -> None:
        """注册警报回调"""
        self._alert_callbacks.append(callback)

    def get_alert_history(self) -> list[AuditAlert]:
        """获取警报历史"""
        return list(self._alerts)

    def get_alerts_by_level(self, level: AlertLevel) -> list[AuditAlert]:
        """按级别获取警报"""
        return [alert for alert in self._alerts if alert.alert_level == level]


# ============================================================================
# 提示词稳定性监控器
# ============================================================================


class PromptStabilityMonitor:
    """提示词稳定性监控器"""

    def __init__(
        self,
        logger: PromptUsageLogger,
        expected_modules: list[str] | None = None,
        allowed_scenarios: list[str] | None = None,
    ) -> None:
        self._logger = logger
        self._coordinator = PromptAuditCoordinator(
            logger=logger,
            expected_modules=expected_modules,
            allowed_scenarios=allowed_scenarios,
        )
        self._metrics_history: list[StabilityMetrics] = []

    def check_stability(self) -> StabilityMetrics:
        """检查稳定性"""
        audit_result = self._coordinator.run_audit()
        metrics = audit_result.stability_metrics
        self._metrics_history.append(metrics)
        return metrics

    def get_stability_metrics(self) -> StabilityMetrics:
        """获取稳定性指标"""
        if self._metrics_history:
            return self._metrics_history[-1]
        return self.check_stability()

    def analyze_stability_trend(
        self,
        window_size: int = 10,
    ) -> dict[str, Any]:
        """分析稳定性趋势"""
        # 如果历史数据不足，先收集
        if len(self._metrics_history) < 2:
            self.check_stability()

        recent_metrics = self._metrics_history[-window_size:]

        if not recent_metrics:
            return {
                "trend": "unknown",
                "data_points": [],
            }

        # 计算趋势
        scores = []
        for m in recent_metrics:
            avg_score = (
                m.version_consistency
                + m.module_consistency
                + m.output_validity_rate
                + m.scenario_compliance
            ) / 4
            scores.append(avg_score)

        if len(scores) >= 2:
            if scores[-1] > scores[0]:
                trend = "improving"
            elif scores[-1] < scores[0]:
                trend = "degrading"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "trend": trend,
            "data_points": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "status": m.status.value,
                    "score": (
                        m.version_consistency
                        + m.module_consistency
                        + m.output_validity_rate
                        + m.scenario_compliance
                    )
                    / 4,
                }
                for m in recent_metrics
            ],
        }
