"""规则引擎 Facade（Rule Engine Facade）

统一的规则引擎入口，整合决策规则、安全校验、审计、熔断和告警等功能。

组件：
- DecisionStats: 决策统计
- RuleEngineFacade: 规则引擎 Facade

功能：
- 决策规则管理与验证
- 规则构建辅助（Payload/DAG）
- SafetyGuard 安全校验代理
- SaveRequest 审计
- 横切关注点（熔断、告警、拒绝率）

设计原则：
- 组合优先：组合现有组件，不重复实现
- 统一接口：提供一致的规则验证入口
- 依赖注入：支持可选依赖组件

实现日期：2025-12-12（P1-1）
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from src.domain.services.circuit_breaker import CircuitBreaker
from src.domain.services.dynamic_alert_rule_manager import DynamicAlertRuleManager
from src.domain.services.safety_guard import (
    DagRuleBuilder,
    PayloadRuleBuilder,
    SafetyGuard,
    ValidationResult,
)
from src.domain.services.safety_guard import (
    Rule as DecisionRule,
)
from src.domain.services.save_request_audit import AuditResult, AuditRule, SaveRequestAuditor

logger = logging.getLogger(__name__)


# =============================================================================
# 决策统计
# =============================================================================


@dataclass
class DecisionStats:
    """决策统计

    属性：
        total: 总决策数
        passed: 通过数
        rejected: 拒绝数
    """

    total: int = 0
    passed: int = 0
    rejected: int = 0

    @property
    def rejection_rate(self) -> float:
        """拒绝率"""
        return self.rejected / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total": self.total,
            "passed": self.passed,
            "rejected": self.rejected,
            "rejection_rate": self.rejection_rate,
        }


# =============================================================================
# 规则引擎 Facade
# =============================================================================


class RuleEngineFacade:
    """规则引擎 Facade

    统一的规则引擎入口，整合决策规则、安全校验、审计等功能。

    线程安全：
    - 使用 threading.RLock() 保护可变状态（_rules, _statistics）
    - 所有公共方法都是线程安全的
    - 支持并发调用 validate_decision()

    使用示例：
        facade = RuleEngineFacade(
            safety_guard=safety_guard,
            rejection_rate_threshold=0.5
        )
        result = facade.validate_decision(decision)
    """

    def __init__(
        self,
        *,
        safety_guard: SafetyGuard,
        payload_rule_builder: PayloadRuleBuilder | None = None,
        dag_rule_builder: DagRuleBuilder | None = None,
        save_request_auditor: SaveRequestAuditor | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        alert_rule_manager: DynamicAlertRuleManager | None = None,
        rejection_rate_threshold: float = 0.5,
        rules_ref: list[DecisionRule] | None = None,
        statistics_ref: dict[str, int] | None = None,
        log_collector: Any | None = None,
    ) -> None:
        """初始化

        参数：
            safety_guard: SafetyGuard 实例（必选）
            payload_rule_builder: Payload 规则构建器（可选）
            dag_rule_builder: DAG 规则构建器（可选）
            save_request_auditor: SaveRequest 审计器（可选）
            circuit_breaker: 熔断器（可选）
            alert_rule_manager: 告警规则管理器（可选）
            rejection_rate_threshold: 拒绝率阈值（默认0.5）
            rules_ref: 规则列表引用（可选，用于共享状态）
            statistics_ref: 统计字典引用（可选，用于共享状态）
            log_collector: 日志收集器（可选）

        注意（P1-1 Step 3）：
            - rules_ref/statistics_ref 用于与 CoordinatorAgent 渐进集成
            - 提供时，Facade 将操作共享容器而非创建新实例
            - 确保状态一致性，避免重复装配
        """
        self._safety_guard = safety_guard
        self._payload_rule_builder = payload_rule_builder
        self._dag_rule_builder = dag_rule_builder
        self._save_request_auditor = save_request_auditor
        self._circuit_breaker = circuit_breaker
        self._alert_rule_manager = alert_rule_manager
        self._rejection_rate_threshold = rejection_rate_threshold
        self._log_collector = log_collector

        # 共享状态容器（P1-1 Step 3：用于与 CoordinatorAgent 渐进集成）
        self._rules: list[DecisionRule] = rules_ref if rules_ref is not None else []
        self._statistics_ref = statistics_ref

        # 决策统计（如果提供了 statistics_ref，从中初始化）
        if statistics_ref is not None:
            total = statistics_ref.get("total", 0)
            passed = statistics_ref.get("passed", 0)
            rejected = statistics_ref.get("rejected", 0)
            self._statistics = DecisionStats(total=total, passed=passed, rejected=rejected)
        else:
            self._statistics = DecisionStats()

        # 线程安全锁（保护 _rules 和 _statistics）
        self._lock = threading.RLock()

        logger.info(
            "RuleEngineFacade initialized with rejection_rate_threshold=%.2f, "
            "rules_ref=%s, statistics_ref=%s",
            rejection_rate_threshold,
            "provided" if rules_ref is not None else "new",
            "provided" if statistics_ref is not None else "new",
        )

    # =========================================================================
    # 决策规则管理
    # =========================================================================

    def list_decision_rules(self) -> list[DecisionRule]:
        """列出所有决策规则

        返回：
            决策规则列表（按优先级排序，低数字=高优先级）

        注意：
            线程安全 - 使用锁保护
            优先级约定：数字越小优先级越高 (1 > 2 > 3...)
        """
        with self._lock:
            return sorted(self._rules, key=lambda r: r.priority)

    def add_decision_rule(self, rule: DecisionRule) -> None:
        """添加决策规则

        参数：
            rule: 决策规则

        注意：
            线程安全 - 使用锁保护
        """
        with self._lock:
            self._rules.append(rule)
            logger.debug(f"Added decision rule: {rule.id} (priority={rule.priority})")

    def remove_decision_rule(self, rule_id: str) -> bool:
        """移除决策规则

        参数：
            rule_id: 规则ID

        返回：
            是否成功移除

        注意：
            线程安全 - 使用锁保护
            P1-1 Step 3 Critical Fix #1: 原地删除，保持 rules_ref 引用不变
        """
        with self._lock:
            # 原地删除，避免重新绑定破坏共享引用
            for i, rule in enumerate(self._rules):
                if rule.id == rule_id:
                    self._rules.pop(i)
                    logger.debug(f"Removed decision rule: {rule_id}")
                    return True

            logger.warning(f"Decision rule not found: {rule_id}")
            return False

    def validate_decision(
        self, decision: dict[str, Any], *, session_id: str | None = None
    ) -> ValidationResult:
        """验证决策

        按优先级遍历规则，累积错误和修正建议。

        异常处理策略（fail-closed）：
        - 规则执行异常视为验证失败
        - 异常信息记录到 errors 和日志
        - 统计保持一致性

        参数：
            decision: 决策字典
            session_id: 会话ID（可选，用于日志）

        返回：
            ValidationResult 验证结果

        注意：
            线程安全 - 使用锁保护
        """
        with self._lock:
            # 更新统计（P1-1 Step 3：同步更新 statistics_ref）
            self._statistics.total += 1
            if self._statistics_ref is not None:
                self._statistics_ref["total"] = self._statistics_ref.get("total", 0) + 1

            errors = []
            corrections = []

            # 获取规则列表的副本（在锁内）
            # 优先级约定：数字越小优先级越高 (1 > 2 > 3...)
            rules = sorted(self._rules, key=lambda r: r.priority)

        # 在锁外执行规则（避免持锁时间过长）
        for rule in rules:
            try:
                # 检查规则条件是否通过
                condition_result = rule.condition(decision)
                if condition_result:
                    continue

                # 验证失败 - 获取错误消息
                error_msg = rule.error_message
                if callable(error_msg):
                    try:
                        error_msg = error_msg(decision)
                    except Exception as e:
                        error_msg = f"规则 {rule.id} 错误消息生成失败: {e}"
                        logger.error(
                            f"Error generating error message for rule {rule.id}: {e}", exc_info=True
                        )

                errors.append(error_msg)

                # 收集修正建议
                if rule.correction:
                    try:
                        correction = rule.correction(decision)
                        if correction and correction not in corrections:
                            corrections.append(correction)
                    except Exception as e:
                        logger.error(
                            f"Error generating correction for rule {rule.id}: {e}", exc_info=True
                        )
                        # 修正建议失败不影响验证结果，仅记录日志

            except Exception as e:
                # 规则执行异常 - fail-closed 策略（视为验证失败）
                error_msg = f"规则 {rule.id} 执行异常: {e}"
                errors.append(error_msg)
                logger.error(
                    f"Rule {rule.id} execution failed for session {session_id}: {e}",
                    exc_info=True,
                    extra={"rule_id": rule.id, "session_id": session_id, "decision": decision},
                )

        # 更新统计（重新获取锁，P1-1 Step 3：同步更新 statistics_ref）
        is_valid = len(errors) == 0
        with self._lock:
            if is_valid:
                self._statistics.passed += 1
                if self._statistics_ref is not None:
                    self._statistics_ref["passed"] = self._statistics_ref.get("passed", 0) + 1
            else:
                self._statistics.rejected += 1
                if self._statistics_ref is not None:
                    self._statistics_ref["rejected"] = self._statistics_ref.get("rejected", 0) + 1

        # 记录日志（异常不影响验证结果 - fail-closed 完整性保护）
        # P1-1 Step 3 Critical Fix #3: 日志收集器接口兼容（能力探测）
        if self._log_collector and not is_valid:
            log_data = {
                "type": "decision_validation",
                "session_id": session_id,
                "decision": decision,
                "errors": errors,
                "corrections": corrections,
            }
            try:
                # 优先使用 record() 方法（如果存在）
                if hasattr(self._log_collector, "record") and callable(self._log_collector.record):
                    self._log_collector.record(log_data)
                # Fallback: 使用 warning() 方法（UnifiedLogCollector 支持）
                elif hasattr(self._log_collector, "warning") and callable(
                    self._log_collector.warning
                ):
                    self._log_collector.warning(
                        f"Decision validation failed: session={session_id}, "
                        f"errors={len(errors)}, decision_type={decision.get('type', 'unknown')}"
                    )
                # Fallback: 使用 log() 方法
                elif hasattr(self._log_collector, "log") and callable(self._log_collector.log):
                    self._log_collector.log(
                        "warning",
                        f"Decision validation failed: session={session_id}, errors={len(errors)}",
                    )
            except Exception as e:
                # 日志收集失败不应影响验证结果
                logger.debug(
                    f"Log collector failed for session {session_id}: {e}",
                    exc_info=False,  # 降级为 debug，避免噪声
                )

        # 合并所有修正建议为单个字典（如果有）
        merged_correction = None
        if corrections:
            merged_correction = {}
            for corr in corrections:
                if isinstance(corr, dict):
                    merged_correction.update(corr)

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            correction=merged_correction,
        )

    def get_decision_statistics(self) -> dict[str, Any]:
        """获取决策统计

        返回：
            统计字典

        注意：
            线程安全 - 使用锁保护
            P1-1 Step 3: 优先从 statistics_ref 读取（如果提供）
        """
        with self._lock:
            if self._statistics_ref is not None:
                # 从共享容器读取
                total = self._statistics_ref.get("total", 0)
                passed = self._statistics_ref.get("passed", 0)
                rejected = self._statistics_ref.get("rejected", 0)
                rejection_rate = rejected / total if total else 0.0
                return {
                    "total": total,
                    "passed": passed,
                    "rejected": rejected,
                    "rejection_rate": rejection_rate,
                }
            else:
                # 从内部 DecisionStats 读取
                return self._statistics.to_dict()

    def is_rejection_rate_high(self) -> bool:
        """判断拒绝率是否过高

        返回：
            是否超过阈值

        注意：
            线程安全 - 使用锁保护
            P1-1 Step 3: 使用 get_decision_statistics() 确保一致性
        """
        stats = self.get_decision_statistics()
        return stats["rejection_rate"] > self._rejection_rate_threshold

    # =========================================================================
    # 规则构建辅助
    # =========================================================================

    def add_payload_required_fields_rule(
        self, decision_type: str, required_fields: list[str], *, rule_id: str | None = None
    ) -> str:
        """添加 Payload 必填字段规则

        参数：
            decision_type: 决策类型
            required_fields: 必填字段列表
            rule_id: 规则ID（可选）

        返回：
            规则ID
        """
        if not self._payload_rule_builder:
            raise RuntimeError("PayloadRuleBuilder not configured")

        rule = self._payload_rule_builder.build_required_fields_rule(decision_type, required_fields)
        self.add_decision_rule(rule)
        return rule.id

    def add_payload_type_rule(
        self,
        decision_type: str,
        field_types: dict[str, Any],
        nested_field_types: dict[str, Any] | None = None,
    ) -> str:
        """添加 Payload 类型验证规则

        参数：
            decision_type: 决策类型
            field_types: 字段类型字典
            nested_field_types: 嵌套字段类型字典（可选）

        返回：
            规则ID
        """
        if not self._payload_rule_builder:
            raise RuntimeError("PayloadRuleBuilder not configured")

        rule = self._payload_rule_builder.build_type_validation_rule(
            decision_type, field_types, nested_field_types=nested_field_types
        )
        self.add_decision_rule(rule)
        return rule.id

    def add_payload_range_rule(
        self, decision_type: str, field_ranges: dict[str, dict[str, int | float]]
    ) -> str:
        """添加 Payload 范围验证规则

        参数：
            decision_type: 决策类型
            field_ranges: 字段范围字典

        返回：
            规则ID
        """
        if not self._payload_rule_builder:
            raise RuntimeError("PayloadRuleBuilder not configured")

        rule = self._payload_rule_builder.build_range_validation_rule(decision_type, field_ranges)
        self.add_decision_rule(rule)
        return rule.id

    def add_payload_enum_rule(self, decision_type: str, field_enums: dict[str, list[str]]) -> str:
        """添加 Payload 枚举验证规则

        参数：
            decision_type: 决策类型
            field_enums: 字段枚举字典

        返回：
            规则ID
        """
        if not self._payload_rule_builder:
            raise RuntimeError("PayloadRuleBuilder not configured")

        rule = self._payload_rule_builder.build_enum_validation_rule(decision_type, field_enums)
        self.add_decision_rule(rule)
        return rule.id

    def add_dag_validation_rule(self) -> str:
        """添加 DAG 验证规则

        返回：
            规则ID
        """
        if not self._dag_rule_builder:
            raise RuntimeError("DagRuleBuilder not configured")

        rule = self._dag_rule_builder.build_dag_validation_rule()
        self.add_decision_rule(rule)
        return rule.id

    # =========================================================================
    # SafetyGuard 代理
    # =========================================================================

    def configure_file_security(
        self,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        max_content_bytes: int | None = None,
        allowed_operations: set[str] | None = None,
    ) -> None:
        """配置文件安全

        参数：
            whitelist: 白名单路径列表
            blacklist: 黑名单路径列表
            max_content_bytes: 最大内容字节数
            allowed_operations: 允许的操作集合
        """
        self._safety_guard.configure_file_security(
            whitelist=whitelist,
            blacklist=blacklist,
            max_content_bytes=max_content_bytes,
            allowed_operations=allowed_operations,
        )

    def configure_api_domains(
        self,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        allowed_schemes: set[str] | None = None,
    ) -> None:
        """配置 API 域名

        参数：
            whitelist: 白名单域名列表
            blacklist: 黑名单域名列表
            allowed_schemes: 允许的协议集合
        """
        self._safety_guard.configure_api_domains(
            whitelist=whitelist,
            blacklist=blacklist,
            allowed_schemes=allowed_schemes,
        )

    async def validate_file_operation(
        self,
        node_id: str,
        operation: str | None,
        path: str | None,
        config: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """验证文件操作

        参数：
            node_id: 节点ID
            operation: 操作类型
            path: 文件路径
            config: 配置字典

        返回：
            ValidationResult 验证结果
        """
        return await self._safety_guard.validate_file_operation(node_id, operation, path, config)

    async def validate_api_request(
        self,
        node_id: str,
        url: str | None,
        method: str | None = None,
        headers: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> ValidationResult:
        """验证 API 请求

        参数：
            node_id: 节点ID
            url: 请求URL
            method: 请求方法
            headers: 请求头
            body: 请求体

        返回：
            ValidationResult 验证结果
        """
        return await self._safety_guard.validate_api_request(node_id, url, method, headers, body)

    async def validate_human_interaction(
        self,
        node_id: str,
        prompt: str,
        expected_inputs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """验证人机交互

        参数：
            node_id: 节点ID
            prompt: 提示信息
            expected_inputs: 预期输入列表
            metadata: 元数据

        返回：
            ValidationResult 验证结果
        """
        return await self._safety_guard.validate_human_interaction(
            node_id, prompt, expected_inputs, metadata
        )

    # =========================================================================
    # SaveRequest 审计
    # =========================================================================

    def audit_save_request(self, request: Any) -> AuditResult:
        """审计保存请求

        参数：
            request: 保存请求对象

        返回：
            AuditResult 审计结果
        """
        if not self._save_request_auditor:
            raise RuntimeError("SaveRequestAuditor not configured")

        return self._save_request_auditor.audit(request)

    def add_save_audit_rule(self, rule: AuditRule) -> None:
        """添加保存审计规则

        参数：
            rule: 审计规则
        """
        if not self._save_request_auditor:
            raise RuntimeError("SaveRequestAuditor not configured")

        self._save_request_auditor.add_rule(rule)

    def remove_save_audit_rule(self, rule_id: str) -> bool:
        """移除保存审计规则

        参数：
            rule_id: 规则ID

        返回：
            是否成功移除
        """
        if not self._save_request_auditor:
            raise RuntimeError("SaveRequestAuditor not configured")

        return self._save_request_auditor.remove_rule(rule_id)

    # =========================================================================
    # 横切关注点：熔断、告警
    # =========================================================================

    def check_circuit_breaker(self) -> None:
        """检查熔断器状态

        异常：
            如果熔断器打开，可能抛出异常
        """
        if not self._circuit_breaker:
            return

        if self._circuit_breaker.is_open:
            logger.warning("Circuit breaker is OPEN")
            # 注：是否抛异常由 CircuitBreaker 的设计决定
            # 这里仅记录日志，不强制中断

    def record_success(self) -> None:
        """记录成功"""
        if self._circuit_breaker:
            self._circuit_breaker.record_success()

    def record_failure(self) -> None:
        """记录失败"""
        if self._circuit_breaker:
            self._circuit_breaker.record_failure()

    def evaluate_alerts(self, extra_metrics: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """评估告警规则

        参数：
            extra_metrics: 额外指标字典

        返回：
            触发的告警列表

        注意：
            P1-1 Step 3 Critical Fix #2: 使用 get_decision_statistics() 确保读取 statistics_ref
        """
        if not self._alert_rule_manager:
            return []

        # 合并决策统计与额外指标（Critical Fix #2：统一走 get_decision_statistics）
        metrics = self.get_decision_statistics()
        if extra_metrics:
            metrics.update(extra_metrics)

        # 添加熔断器指标
        if self._circuit_breaker:
            metrics["circuit_breaker_open"] = self._circuit_breaker.is_open
            circuit_metrics = self._circuit_breaker.get_metrics()
            metrics.update(circuit_metrics)

        return self._alert_rule_manager.evaluate(metrics)


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    "DecisionStats",
    "RuleEngineFacade",
]
