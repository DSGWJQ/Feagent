"""RuleEngineFacade TDD 测试

验证从 CoordinatorAgent 提取的规则引擎 Facade 功能。

测试覆盖：
- 初始化与依赖注入
- 决策规则管理（CRUD + 统计）
- 规则构建辅助（Payload/DAG）
- SafetyGuard 代理
- SaveRequest 审计
- 横切关注点（熔断、告警）
- 异常处理（fail-closed 策略）
- 线程安全
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@dataclass
class _TestDecisionRule:
    """测试用决策规则桩"""

    id: str
    priority: int = 10
    condition: Any = None
    error_message: Any = "测试错误"
    correction: Any = None

    def __post_init__(self):
        if self.condition is None:
            self.condition = lambda d: True


class TestRuleEngineFacadeInit:
    """测试初始化"""

    def test_minimal_init_with_safety_guard_only(self) -> None:
        """最小初始化：仅提供 SafetyGuard"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_safety_guard = MagicMock()
        facade = RuleEngineFacade(safety_guard=mock_safety_guard)

        assert facade._safety_guard is mock_safety_guard
        assert facade._payload_rule_builder is None
        assert facade._dag_rule_builder is None
        assert facade._save_request_auditor is None
        assert facade._circuit_breaker is None
        assert facade._alert_rule_manager is None
        assert facade._rejection_rate_threshold == 0.5

    def test_full_init_with_all_dependencies(self) -> None:
        """完整初始化：注入所有依赖"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_safety_guard = MagicMock()
        mock_payload_builder = MagicMock()
        mock_dag_builder = MagicMock()
        mock_auditor = MagicMock()
        mock_breaker = MagicMock()
        mock_alert_manager = MagicMock()
        mock_log_collector = MagicMock()

        facade = RuleEngineFacade(
            safety_guard=mock_safety_guard,
            payload_rule_builder=mock_payload_builder,
            dag_rule_builder=mock_dag_builder,
            save_request_auditor=mock_auditor,
            circuit_breaker=mock_breaker,
            alert_rule_manager=mock_alert_manager,
            rejection_rate_threshold=0.3,
            log_collector=mock_log_collector,
        )

        assert facade._payload_rule_builder is mock_payload_builder
        assert facade._dag_rule_builder is mock_dag_builder
        assert facade._save_request_auditor is mock_auditor
        assert facade._circuit_breaker is mock_breaker
        assert facade._alert_rule_manager is mock_alert_manager
        assert facade._rejection_rate_threshold == 0.3
        assert facade._log_collector is mock_log_collector

    def test_init_creates_empty_rules_list(self) -> None:
        """初始化创建空规则列表"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        assert facade._rules == []

    def test_init_creates_zero_statistics(self) -> None:
        """初始化创建零统计"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        stats = facade.get_decision_statistics()

        assert stats["total"] == 0
        assert stats["passed"] == 0
        assert stats["rejected"] == 0
        assert stats["rejection_rate"] == 0.0


class TestDecisionRulesManagement:
    """测试决策规则管理"""

    def test_add_decision_rule(self) -> None:
        """添加决策规则"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(id="rule-001", priority=10)

        facade.add_decision_rule(rule)

        rules = facade.list_decision_rules()
        assert len(rules) == 1
        assert rules[0].id == "rule-001"

    def test_list_decision_rules_sorted_by_priority(self) -> None:
        """列出规则按优先级降序排列"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule1 = _TestDecisionRule(id="low", priority=5)
        rule2 = _TestDecisionRule(id="high", priority=20)
        rule3 = _TestDecisionRule(id="mid", priority=10)

        facade.add_decision_rule(rule1)
        facade.add_decision_rule(rule2)
        facade.add_decision_rule(rule3)

        rules = facade.list_decision_rules()
        assert [r.id for r in rules] == ["high", "mid", "low"]

    def test_remove_decision_rule_success(self) -> None:
        """移除规则成功"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(id="rule-001")
        facade.add_decision_rule(rule)

        result = facade.remove_decision_rule("rule-001")

        assert result is True
        assert len(facade.list_decision_rules()) == 0

    def test_remove_decision_rule_not_found(self) -> None:
        """移除不存在的规则返回 False"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())

        result = facade.remove_decision_rule("non-existent")

        assert result is False


class TestDecisionValidationCore:
    """测试决策验证核心功能"""

    def test_validate_decision_all_rules_pass(self) -> None:
        """所有规则通过"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(id="rule-001", condition=lambda d: True)
        facade.add_decision_rule(rule)

        result = facade.validate_decision({"action": "test"})

        assert result.is_valid is True
        assert result.errors == []

    def test_validate_decision_rule_fails(self) -> None:
        """规则验证失败"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(id="rule-001", condition=lambda d: False, error_message="验证失败")
        facade.add_decision_rule(rule)

        result = facade.validate_decision({"action": "test"})

        assert result.is_valid is False
        assert "验证失败" in result.errors

    def test_validate_decision_callable_error_message(self) -> None:
        """动态生成错误消息"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(
            id="rule-001",
            condition=lambda d: False,
            error_message=lambda d: f"字段 {d.get('field')} 无效",
        )
        facade.add_decision_rule(rule)

        result = facade.validate_decision({"field": "username"})

        assert result.is_valid is False
        assert "字段 username 无效" in result.errors

    def test_validate_decision_with_correction(self) -> None:
        """验证失败时返回修正建议"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(
            id="rule-001",
            condition=lambda d: False,
            error_message="字段缺失",
            correction=lambda d: {"suggested_field": "value"},
        )
        facade.add_decision_rule(rule)

        result = facade.validate_decision({"action": "test"})

        assert result.is_valid is False
        assert result.correction == {"suggested_field": "value"}

    def test_validate_decision_updates_statistics(self) -> None:
        """验证更新统计数据"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule_pass = _TestDecisionRule(id="pass", condition=lambda d: True)
        rule_fail = _TestDecisionRule(id="fail", condition=lambda d: False)
        facade.add_decision_rule(rule_pass)

        # 通过的验证
        facade.validate_decision({"action": "test1"})
        facade.validate_decision({"action": "test2"})

        # 失败的验证
        facade.remove_decision_rule("pass")
        facade.add_decision_rule(rule_fail)
        facade.validate_decision({"action": "test3"})

        stats = facade.get_decision_statistics()
        assert stats["total"] == 3
        assert stats["passed"] == 2
        assert stats["rejected"] == 1
        assert stats["rejection_rate"] == pytest.approx(1 / 3)

    def test_is_rejection_rate_high(self) -> None:
        """判断拒绝率是否过高"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock(), rejection_rate_threshold=0.5)
        rule_fail = _TestDecisionRule(id="fail", condition=lambda d: False)
        facade.add_decision_rule(rule_fail)

        # 6次验证，全部失败 -> 拒绝率 100%
        for i in range(6):
            facade.validate_decision({"action": f"test{i}"})

        assert facade.is_rejection_rate_high() is True


class TestDecisionValidationExceptionPaths:
    """测试决策验证异常路径（fail-closed 策略）"""

    def test_rule_condition_raises_exception(self) -> None:
        """规则条件执行异常 - fail-closed"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        def bad_condition(d):
            raise ValueError("条件执行失败")

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(id="bad-rule", condition=bad_condition)
        facade.add_decision_rule(rule)

        result = facade.validate_decision({"action": "test"})

        assert result.is_valid is False
        assert any("执行异常" in err for err in result.errors)
        # 统计应更新为拒绝
        stats = facade.get_decision_statistics()
        assert stats["rejected"] == 1

    def test_error_message_callable_raises_exception(self) -> None:
        """错误消息生成失败 - 降级为固定消息"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        def bad_error_message(d):
            raise RuntimeError("消息生成失败")

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(
            id="rule-001",
            condition=lambda d: False,
            error_message=bad_error_message,
        )
        facade.add_decision_rule(rule)

        result = facade.validate_decision({"action": "test"})

        assert result.is_valid is False
        assert any("错误消息生成失败" in err for err in result.errors)

    def test_correction_callable_raises_exception(self) -> None:
        """修正建议生成失败 - 不影响验证结果"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        def bad_correction(d):
            raise RuntimeError("修正生成失败")

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(
            id="rule-001",
            condition=lambda d: False,
            error_message="验证失败",
            correction=bad_correction,
        )
        facade.add_decision_rule(rule)

        result = facade.validate_decision({"action": "test"})

        # 验证失败，但修正为空（不应崩溃）
        assert result.is_valid is False
        assert result.correction is None or result.correction == {}


class TestThreadSafety:
    """测试线程安全"""

    def test_concurrent_validate_decision(self) -> None:
        """并发调用 validate_decision 保证统计一致性"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        rule = _TestDecisionRule(id="rule-001", condition=lambda d: d.get("pass", False))
        facade.add_decision_rule(rule)

        def validate_worker(pass_flag):
            return facade.validate_decision({"pass": pass_flag})

        # 100次并发验证：50次通过，50次失败
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(validate_worker, i % 2 == 0) for i in range(100)]
            results = [f.result() for f in as_completed(futures)]

        passed_count = sum(1 for r in results if r.is_valid)
        failed_count = sum(1 for r in results if not r.is_valid)

        assert passed_count == 50
        assert failed_count == 50

        stats = facade.get_decision_statistics()
        assert stats["total"] == 100
        assert stats["passed"] == 50
        assert stats["rejected"] == 50

    def test_concurrent_add_remove_rules(self) -> None:
        """并发添加/移除规则不导致数据损坏"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())

        def add_rule(i):
            rule = _TestDecisionRule(id=f"rule-{i}")
            facade.add_decision_rule(rule)

        def remove_rule(i):
            facade.remove_decision_rule(f"rule-{i}")

        with ThreadPoolExecutor(max_workers=5) as executor:
            # 添加 50 个规则
            add_futures = [executor.submit(add_rule, i) for i in range(50)]
            for f in as_completed(add_futures):
                f.result()

            # 移除前 25 个规则
            remove_futures = [executor.submit(remove_rule, i) for i in range(25)]
            for f in as_completed(remove_futures):
                f.result()

        rules = facade.list_decision_rules()
        assert len(rules) == 25

    def test_concurrent_validate_and_modify_rules(self) -> None:
        """并发验证与修改规则（交叉场景）- 验证真实竞态条件"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())

        # 初始规则
        for i in range(10):
            rule = _TestDecisionRule(
                id=f"rule-{i}", priority=i, condition=lambda d, i=i: d.get("value", 0) > i
            )
            facade.add_decision_rule(rule)

        validate_count = 0
        validate_lock = threading.Lock()

        def validate_worker():
            nonlocal validate_count
            import random

            for _ in range(10):
                result = facade.validate_decision({"value": random.randint(0, 15)})
                with validate_lock:
                    validate_count += 1
                # 验证不应抛出异常
                assert result is not None

        def add_worker():
            import random

            for i in range(10, 20):
                rule = _TestDecisionRule(id=f"rule-new-{i}", priority=i)
                facade.add_decision_rule(rule)
                import time

                time.sleep(random.uniform(0.001, 0.005))

        def remove_worker():
            import random

            for i in range(5):
                facade.remove_decision_rule(f"rule-{i}")
                import time

                time.sleep(random.uniform(0.001, 0.005))

        # 并发执行：5个验证线程 + 2个添加线程 + 2个移除线程
        with ThreadPoolExecutor(max_workers=9) as executor:
            futures = []
            futures.extend([executor.submit(validate_worker) for _ in range(5)])
            futures.extend([executor.submit(add_worker) for _ in range(2)])
            futures.extend([executor.submit(remove_worker) for _ in range(2)])

            # 等待所有任务完成（不应抛出异常）
            for f in as_completed(futures):
                f.result()

        # 验证最终状态一致性
        stats = facade.get_decision_statistics()
        assert stats["total"] == validate_count  # 统计应与实际验证次数一致
        assert stats["total"] == stats["passed"] + stats["rejected"]

        # 规则列表应可访问（不损坏）
        final_rules = facade.list_decision_rules()
        assert len(final_rules) > 0


class TestRuleBuilderIntegration:
    """测试规则构建辅助"""

    def test_add_payload_required_fields_rule(self) -> None:
        """添加 Payload 必填字段规则"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_builder = MagicMock()
        mock_rule = _TestDecisionRule(id="payload-required")
        mock_builder.build_required_fields_rule.return_value = mock_rule

        facade = RuleEngineFacade(safety_guard=MagicMock(), payload_rule_builder=mock_builder)

        rule_id = facade.add_payload_required_fields_rule(
            decision_type="workflow_execution", required_fields=["workflow_id", "user_id"]
        )

        assert rule_id == "payload-required"
        mock_builder.build_required_fields_rule.assert_called_once_with(
            "workflow_execution", ["workflow_id", "user_id"]
        )
        assert len(facade.list_decision_rules()) == 1

    def test_add_payload_type_rule(self) -> None:
        """添加 Payload 类型验证规则"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_builder = MagicMock()
        mock_rule = _TestDecisionRule(id="payload-type")
        mock_builder.build_type_validation_rule.return_value = mock_rule

        facade = RuleEngineFacade(safety_guard=MagicMock(), payload_rule_builder=mock_builder)

        rule_id = facade.add_payload_type_rule(
            decision_type="workflow_execution",
            field_types={"workflow_id": str, "timeout": int},
        )

        assert rule_id == "payload-type"
        mock_builder.build_type_validation_rule.assert_called_once()

    def test_add_payload_range_rule(self) -> None:
        """添加 Payload 范围验证规则"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_builder = MagicMock()
        mock_rule = _TestDecisionRule(id="payload-range")
        mock_builder.build_range_validation_rule.return_value = mock_rule

        facade = RuleEngineFacade(safety_guard=MagicMock(), payload_rule_builder=mock_builder)

        rule_id = facade.add_payload_range_rule(
            decision_type="workflow_execution",
            field_ranges={"timeout": {"min": 1, "max": 3600}},
        )

        assert rule_id == "payload-range"

    def test_add_payload_enum_rule(self) -> None:
        """添加 Payload 枚举验证规则"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_builder = MagicMock()
        mock_rule = _TestDecisionRule(id="payload-enum")
        mock_builder.build_enum_validation_rule.return_value = mock_rule

        facade = RuleEngineFacade(safety_guard=MagicMock(), payload_rule_builder=mock_builder)

        rule_id = facade.add_payload_enum_rule(
            decision_type="workflow_execution",
            field_enums={"status": ["pending", "running", "completed"]},
        )

        assert rule_id == "payload-enum"

    def test_add_dag_validation_rule(self) -> None:
        """添加 DAG 验证规则"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_builder = MagicMock()
        mock_rule = _TestDecisionRule(id="dag-validation")
        mock_builder.build_dag_validation_rule.return_value = mock_rule

        facade = RuleEngineFacade(safety_guard=MagicMock(), dag_rule_builder=mock_builder)

        rule_id = facade.add_dag_validation_rule()

        assert rule_id == "dag-validation"

    def test_add_payload_rule_without_builder_raises(self) -> None:
        """未配置 builder 时抛出异常"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())

        with pytest.raises(RuntimeError, match="PayloadRuleBuilder not configured"):
            facade.add_payload_required_fields_rule("test", ["field1"])


class TestSafetyGuardProxy:
    """测试 SafetyGuard 代理"""

    def test_configure_file_security(self) -> None:
        """配置文件安全"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_guard = MagicMock()
        facade = RuleEngineFacade(safety_guard=mock_guard)

        facade.configure_file_security(
            whitelist=["/data"], blacklist=["/system"], max_content_bytes=1024000
        )

        mock_guard.configure_file_security.assert_called_once_with(
            whitelist=["/data"],
            blacklist=["/system"],
            max_content_bytes=1024000,
            allowed_operations=None,
        )

    def test_configure_api_domains(self) -> None:
        """配置 API 域名"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_guard = MagicMock()
        facade = RuleEngineFacade(safety_guard=mock_guard)

        facade.configure_api_domains(whitelist=["api.example.com"], allowed_schemes={"https"})

        mock_guard.configure_api_domains.assert_called_once_with(
            whitelist=["api.example.com"], blacklist=None, allowed_schemes={"https"}
        )

    @pytest.mark.asyncio
    async def test_validate_file_operation(self) -> None:
        """验证文件操作"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_guard = MagicMock()
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_guard.validate_file_operation = AsyncMock(return_value=mock_result)

        facade = RuleEngineFacade(safety_guard=mock_guard)

        result = await facade.validate_file_operation(
            node_id="node-001", operation="read", path="/data/file.txt"
        )

        assert result.is_valid is True
        mock_guard.validate_file_operation.assert_called_once_with(
            "node-001", "read", "/data/file.txt", None
        )

    @pytest.mark.asyncio
    async def test_validate_api_request(self) -> None:
        """验证 API 请求"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_guard = MagicMock()
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_guard.validate_api_request = AsyncMock(return_value=mock_result)

        facade = RuleEngineFacade(safety_guard=mock_guard)

        result = await facade.validate_api_request(
            node_id="node-001", url="https://api.example.com", method="GET"
        )

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_human_interaction(self) -> None:
        """验证人机交互"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_guard = MagicMock()
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_guard.validate_human_interaction = AsyncMock(return_value=mock_result)

        facade = RuleEngineFacade(safety_guard=mock_guard)

        result = await facade.validate_human_interaction(
            node_id="node-001", prompt="请输入用户名", expected_inputs=["username"]
        )

        assert result.is_valid is True


class TestSaveRequestAudit:
    """测试 SaveRequest 审计"""

    def test_audit_save_request(self) -> None:
        """审计保存请求"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_auditor = MagicMock()
        mock_result = MagicMock()
        mock_result.passed = True
        mock_auditor.audit.return_value = mock_result

        facade = RuleEngineFacade(safety_guard=MagicMock(), save_request_auditor=mock_auditor)

        mock_request = {"file_path": "/data/test.json", "content": "{}"}
        result = facade.audit_save_request(mock_request)

        assert result.passed is True
        mock_auditor.audit.assert_called_once_with(mock_request)

    def test_audit_without_auditor_raises(self) -> None:
        """未配置审计器时抛出异常"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())

        with pytest.raises(RuntimeError, match="SaveRequestAuditor not configured"):
            facade.audit_save_request({})

    def test_add_save_audit_rule(self) -> None:
        """添加保存审计规则"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_auditor = MagicMock()
        facade = RuleEngineFacade(safety_guard=MagicMock(), save_request_auditor=mock_auditor)

        mock_rule = MagicMock()
        facade.add_save_audit_rule(mock_rule)

        mock_auditor.add_rule.assert_called_once_with(mock_rule)

    def test_remove_save_audit_rule(self) -> None:
        """移除保存审计规则"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_auditor = MagicMock()
        mock_auditor.remove_rule.return_value = True
        facade = RuleEngineFacade(safety_guard=MagicMock(), save_request_auditor=mock_auditor)

        result = facade.remove_save_audit_rule("rule-001")

        assert result is True
        mock_auditor.remove_rule.assert_called_once_with("rule-001")


class TestCrossCuttingConcerns:
    """测试横切关注点"""

    def test_check_circuit_breaker_open(self) -> None:
        """检查熔断器打开状态"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_breaker = MagicMock()
        mock_breaker.is_open = True
        facade = RuleEngineFacade(safety_guard=MagicMock(), circuit_breaker=mock_breaker)

        # 不应抛出异常（仅记录日志）
        facade.check_circuit_breaker()

    def test_check_circuit_breaker_without_breaker(self) -> None:
        """未配置熔断器时不执行检查"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        facade.check_circuit_breaker()  # 不应崩溃

    def test_record_success(self) -> None:
        """记录成功"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_breaker = MagicMock()
        facade = RuleEngineFacade(safety_guard=MagicMock(), circuit_breaker=mock_breaker)

        facade.record_success()
        mock_breaker.record_success.assert_called_once()

    def test_record_failure(self) -> None:
        """记录失败"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_breaker = MagicMock()
        facade = RuleEngineFacade(safety_guard=MagicMock(), circuit_breaker=mock_breaker)

        facade.record_failure()
        mock_breaker.record_failure.assert_called_once()

    def test_evaluate_alerts_with_decision_stats(self) -> None:
        """评估告警规则（包含决策统计）"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_alert_manager = MagicMock()
        mock_alert_manager.evaluate.return_value = [{"rule_id": "high_rejection_rate"}]

        facade = RuleEngineFacade(safety_guard=MagicMock(), alert_rule_manager=mock_alert_manager)

        # 生成一些统计数据
        rule_fail = _TestDecisionRule(id="fail", condition=lambda d: False)
        facade.add_decision_rule(rule_fail)
        for i in range(10):
            facade.validate_decision({"action": f"test{i}"})

        alerts = facade.evaluate_alerts()

        assert len(alerts) == 1
        # 验证传递了正确的指标
        call_args = mock_alert_manager.evaluate.call_args[0][0]
        assert "total" in call_args
        assert "rejection_rate" in call_args

    def test_evaluate_alerts_with_circuit_breaker_metrics(self) -> None:
        """评估告警包含熔断器指标"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_breaker = MagicMock()
        mock_breaker.is_open = True
        mock_breaker.get_metrics.return_value = {"failure_count": 5}

        mock_alert_manager = MagicMock()
        mock_alert_manager.evaluate.return_value = []

        facade = RuleEngineFacade(
            safety_guard=MagicMock(),
            circuit_breaker=mock_breaker,
            alert_rule_manager=mock_alert_manager,
        )

        facade.evaluate_alerts()

        call_args = mock_alert_manager.evaluate.call_args[0][0]
        assert call_args["circuit_breaker_open"] is True
        assert call_args["failure_count"] == 5

    def test_evaluate_alerts_without_manager(self) -> None:
        """未配置告警管理器返回空列表"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        facade = RuleEngineFacade(safety_guard=MagicMock())
        alerts = facade.evaluate_alerts()

        assert alerts == []


class TestLogCollector:
    """测试日志收集"""

    def test_validate_decision_logs_failure(self) -> None:
        """验证失败时记录日志"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_log_collector = MagicMock()
        facade = RuleEngineFacade(safety_guard=MagicMock(), log_collector=mock_log_collector)

        rule = _TestDecisionRule(id="rule-001", condition=lambda d: False, error_message="验证失败")
        facade.add_decision_rule(rule)

        facade.validate_decision({"action": "test"}, session_id="session-001")

        mock_log_collector.record.assert_called_once()
        call_args = mock_log_collector.record.call_args[0][0]
        assert call_args["type"] == "decision_validation"
        assert call_args["session_id"] == "session-001"
        assert "验证失败" in call_args["errors"]

    def test_validate_decision_does_not_log_success(self) -> None:
        """验证成功时不记录日志"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_log_collector = MagicMock()
        facade = RuleEngineFacade(safety_guard=MagicMock(), log_collector=mock_log_collector)

        rule = _TestDecisionRule(id="rule-001", condition=lambda d: True)
        facade.add_decision_rule(rule)

        facade.validate_decision({"action": "test"})

        mock_log_collector.record.assert_not_called()

    def test_log_collector_exception_does_not_break_validation(self) -> None:
        """日志收集器异常不影响验证结果（fail-closed 完整性）"""
        from src.domain.services.rule_engine_facade import RuleEngineFacade

        mock_log_collector = MagicMock()
        mock_log_collector.record.side_effect = RuntimeError("日志系统故障")

        facade = RuleEngineFacade(safety_guard=MagicMock(), log_collector=mock_log_collector)

        rule = _TestDecisionRule(id="rule-001", condition=lambda d: False, error_message="验证失败")
        facade.add_decision_rule(rule)

        # 日志异常不应传播
        result = facade.validate_decision({"action": "test"}, session_id="session-001")

        # 验证结果应正常返回
        assert result.is_valid is False
        assert "验证失败" in result.errors

        # 统计应正确更新
        stats = facade.get_decision_statistics()
        assert stats["total"] == 1
        assert stats["rejected"] == 1
