"""CoordinatorAgentConfig TDD 测试

验证 CoordinatorAgent 配置系统的正确性。

测试覆盖：
- 配置组 __post_init__ 验证
- CoordinatorAgentConfig.validate() 方法
- 配置不可变性（frozen dataclass）
- with_overrides() 覆盖机制
- to_dict() 序列化
- ConfigBuilder 流式 API
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestRuleEngineConfig:
    """测试 RuleEngineConfig 验证"""

    def test_default_config(self) -> None:
        """默认配置"""
        from src.domain.agents.coordinator_agent_config import RuleEngineConfig

        config = RuleEngineConfig()

        assert config.rejection_rate_threshold == 0.5
        assert config.circuit_breaker_config is None
        assert config.enable_decision_rules_middleware is True
        assert config.alert_rule_manager_enabled is True

    def test_valid_rejection_rate_threshold(self) -> None:
        """有效的拒绝率阈值"""
        from src.domain.agents.coordinator_agent_config import RuleEngineConfig

        config = RuleEngineConfig(rejection_rate_threshold=0.8)
        assert config.rejection_rate_threshold == 0.8

    def test_rejection_rate_threshold_too_high(self) -> None:
        """拒绝率阈值超过 1.0 抛出异常"""
        from src.domain.agents.coordinator_agent_config import RuleEngineConfig

        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            RuleEngineConfig(rejection_rate_threshold=1.5)

    def test_rejection_rate_threshold_negative(self) -> None:
        """拒绝率阈值为负数抛出异常"""
        from src.domain.agents.coordinator_agent_config import RuleEngineConfig

        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            RuleEngineConfig(rejection_rate_threshold=-0.1)

    def test_rejection_rate_threshold_boundary_values(self) -> None:
        """边界值测试：0.0 和 1.0"""
        from src.domain.agents.coordinator_agent_config import RuleEngineConfig

        config_zero = RuleEngineConfig(rejection_rate_threshold=0.0)
        assert config_zero.rejection_rate_threshold == 0.0

        config_one = RuleEngineConfig(rejection_rate_threshold=1.0)
        assert config_one.rejection_rate_threshold == 1.0


class TestContextConfig:
    """测试 ContextConfig 验证"""

    def test_default_config(self) -> None:
        """默认配置"""
        from src.domain.agents.coordinator_agent_config import ContextConfig

        config = ContextConfig()

        assert config.max_context_length == 4000
        assert config.enable_context_compression is True
        assert config.context_bridge is None

    def test_valid_max_context_length(self) -> None:
        """有效的最大上下文长度"""
        from src.domain.agents.coordinator_agent_config import ContextConfig

        config = ContextConfig(max_context_length=8000)
        assert config.max_context_length == 8000

    def test_max_context_length_zero(self) -> None:
        """最大上下文长度为 0 抛出异常"""
        from src.domain.agents.coordinator_agent_config import ContextConfig

        with pytest.raises(ValueError, match="must be positive"):
            ContextConfig(max_context_length=0)

    def test_max_context_length_negative(self) -> None:
        """最大上下文长度为负数抛出异常"""
        from src.domain.agents.coordinator_agent_config import ContextConfig

        with pytest.raises(ValueError, match="must be positive"):
            ContextConfig(max_context_length=-100)


class TestFailureHandlingConfig:
    """测试 FailureHandlingConfig 验证"""

    def test_default_config(self) -> None:
        """默认配置"""
        from src.domain.agents.coordinator_agent_config import FailureHandlingConfig

        config = FailureHandlingConfig()

        assert config.max_retry_attempts == 3
        assert config.retry_delay_seconds == 1.0
        assert config.enable_auto_recovery is True

    def test_valid_max_retry_attempts(self) -> None:
        """有效的最大重试次数"""
        from src.domain.agents.coordinator_agent_config import FailureHandlingConfig

        config = FailureHandlingConfig(max_retry_attempts=5)
        assert config.max_retry_attempts == 5

    def test_max_retry_attempts_zero(self) -> None:
        """最大重试次数为 0（有效）"""
        from src.domain.agents.coordinator_agent_config import FailureHandlingConfig

        config = FailureHandlingConfig(max_retry_attempts=0)
        assert config.max_retry_attempts == 0

    def test_max_retry_attempts_negative(self) -> None:
        """最大重试次数为负数抛出异常"""
        from src.domain.agents.coordinator_agent_config import FailureHandlingConfig

        with pytest.raises(ValueError, match="must be non-negative"):
            FailureHandlingConfig(max_retry_attempts=-1)

    def test_retry_delay_seconds_negative(self) -> None:
        """重试延迟为负数抛出异常"""
        from src.domain.agents.coordinator_agent_config import FailureHandlingConfig

        with pytest.raises(ValueError, match="must be non-negative"):
            FailureHandlingConfig(retry_delay_seconds=-0.5)


class TestKnowledgeConfig:
    """测试 KnowledgeConfig 验证"""

    def test_default_config(self) -> None:
        """默认配置"""
        from src.domain.agents.coordinator_agent_config import KnowledgeConfig

        config = KnowledgeConfig()

        assert config.enable_knowledge_retrieval is True
        assert config.retrieval_timeout_seconds == 5.0
        assert config.max_retrieval_results == 10

    def test_retrieval_timeout_zero(self) -> None:
        """检索超时为 0 抛出异常"""
        from src.domain.agents.coordinator_agent_config import KnowledgeConfig

        with pytest.raises(ValueError, match="must be positive"):
            KnowledgeConfig(retrieval_timeout_seconds=0.0)

    def test_retrieval_timeout_negative(self) -> None:
        """检索超时为负数抛出异常"""
        from src.domain.agents.coordinator_agent_config import KnowledgeConfig

        with pytest.raises(ValueError, match="must be positive"):
            KnowledgeConfig(retrieval_timeout_seconds=-1.0)

    def test_max_retrieval_results_zero(self) -> None:
        """最大检索结果为 0 抛出异常"""
        from src.domain.agents.coordinator_agent_config import KnowledgeConfig

        with pytest.raises(ValueError, match="must be positive"):
            KnowledgeConfig(max_retrieval_results=0)


class TestRuntimeConfig:
    """测试 RuntimeConfig（无验证逻辑）"""

    def test_default_config(self) -> None:
        """默认配置"""
        from src.domain.agents.coordinator_agent_config import RuntimeConfig

        config = RuntimeConfig()

        assert config.enable_performance_monitoring is True
        assert config.enable_debug_logging is False
        assert config.experiment_orchestrator is None


class TestCoordinatorAgentConfigValidate:
    """测试 CoordinatorAgentConfig.validate()"""

    def test_validate_success_with_event_bus(self) -> None:
        """提供 event_bus 验证成功"""
        from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig

        mock_event_bus = MagicMock()
        config = CoordinatorAgentConfig(event_bus=mock_event_bus)

        config.validate()  # 不应抛出异常

    def test_validate_fails_without_event_bus(self) -> None:
        """未提供 event_bus 验证失败"""
        from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig

        config = CoordinatorAgentConfig()

        with pytest.raises(ValueError, match="event_bus is required"):
            config.validate()

    def test_validate_warns_compression_enabled_without_compressor(self, caplog) -> None:
        """启用压缩但未提供压缩器时警告"""
        from src.domain.agents.coordinator_agent_config import (
            ContextConfig,
            CoordinatorAgentConfig,
        )

        mock_event_bus = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            context=ContextConfig(enable_context_compression=True, context_compressor=None),
        )

        with caplog.at_level("WARNING"):
            config.validate()

        assert "context_compression enabled" in caplog.text

    def test_validate_warns_auto_recovery_without_orchestrator(self, caplog) -> None:
        """启用自动恢复但未提供编排器时警告"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            FailureHandlingConfig,
        )

        mock_event_bus = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            failure=FailureHandlingConfig(
                enable_auto_recovery=True, workflow_failure_orchestrator=None
            ),
        )

        with caplog.at_level("WARNING"):
            config.validate()

        assert "auto_recovery enabled" in caplog.text

    def test_validate_warns_knowledge_retrieval_without_orchestrator(self, caplog) -> None:
        """启用知识检索但未提供编排器时警告"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            KnowledgeConfig,
        )

        mock_event_bus = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            knowledge=KnowledgeConfig(
                enable_knowledge_retrieval=True, knowledge_retrieval_orchestrator=None
            ),
        )

        with caplog.at_level("WARNING"):
            config.validate()

        assert "knowledge_retrieval enabled" in caplog.text


class TestConfigImmutability:
    """测试配置不可变性（frozen dataclass）"""

    def test_rule_engine_config_immutable(self) -> None:
        """RuleEngineConfig 不可变"""
        from src.domain.agents.coordinator_agent_config import RuleEngineConfig

        config = RuleEngineConfig()

        with pytest.raises((AttributeError, TypeError)):  # FrozenInstanceError
            config.rejection_rate_threshold = 0.9  # type: ignore

    def test_coordinator_agent_config_immutable(self) -> None:
        """CoordinatorAgentConfig 不可变"""
        from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig

        config = CoordinatorAgentConfig()

        with pytest.raises((AttributeError, TypeError)):  # FrozenInstanceError
            config.event_bus = MagicMock()  # type: ignore


class TestWithOverrides:
    """测试 with_overrides() 方法"""

    def test_override_event_bus(self) -> None:
        """覆盖 event_bus"""
        from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig

        mock_bus1 = MagicMock()
        mock_bus2 = MagicMock()

        config1 = CoordinatorAgentConfig(event_bus=mock_bus1)
        config2 = config1.with_overrides(event_bus=mock_bus2)

        assert config1.event_bus is mock_bus1
        assert config2.event_bus is mock_bus2
        assert config1 is not config2  # 新对象

    def test_override_rules_config(self) -> None:
        """覆盖 rules 配置组"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            RuleEngineConfig,
        )

        mock_event_bus = MagicMock()
        config1 = CoordinatorAgentConfig(event_bus=mock_event_bus)

        new_rules = RuleEngineConfig(rejection_rate_threshold=0.3)
        config2 = config1.with_overrides(rules=new_rules)

        assert config1.rules.rejection_rate_threshold == 0.5
        assert config2.rules.rejection_rate_threshold == 0.3

    def test_override_context_config(self) -> None:
        """覆盖 context 配置组"""
        from src.domain.agents.coordinator_agent_config import (
            ContextConfig,
            CoordinatorAgentConfig,
        )

        mock_event_bus = MagicMock()
        config1 = CoordinatorAgentConfig(event_bus=mock_event_bus)

        new_context = ContextConfig(max_context_length=8000)
        config2 = config1.with_overrides(context=new_context)

        assert config1.context.max_context_length == 4000
        assert config2.context.max_context_length == 8000

    def test_override_multiple_fields(self) -> None:
        """覆盖多个字段"""
        from src.domain.agents.coordinator_agent_config import (
            ContextConfig,
            CoordinatorAgentConfig,
            RuleEngineConfig,
        )

        mock_bus1 = MagicMock()
        mock_bus2 = MagicMock()

        config1 = CoordinatorAgentConfig(event_bus=mock_bus1)
        config2 = config1.with_overrides(
            event_bus=mock_bus2,
            rules=RuleEngineConfig(rejection_rate_threshold=0.3),
            context=ContextConfig(max_context_length=8000),
        )

        assert config2.event_bus is mock_bus2
        assert config2.rules.rejection_rate_threshold == 0.3
        assert config2.context.max_context_length == 8000

    def test_override_invalid_field_raises(self) -> None:
        """覆盖不存在的字段抛出异常"""
        from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig

        config = CoordinatorAgentConfig()

        with pytest.raises(TypeError):
            config.with_overrides(invalid_field="value")  # type: ignore


class TestToDictSerialization:
    """测试 to_dict() 序列化"""

    def test_to_dict_basic(self) -> None:
        """基础序列化"""
        from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig

        mock_event_bus = MagicMock()
        config = CoordinatorAgentConfig(event_bus=mock_event_bus)

        result = config.to_dict()

        assert result["event_bus_configured"] is True
        assert "rules" in result
        assert "context" in result
        assert "failure" in result
        assert "knowledge" in result
        assert "runtime" in result

    def test_to_dict_rules_section(self) -> None:
        """rules 部分序列化"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            RuleEngineConfig,
        )

        mock_event_bus = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            rules=RuleEngineConfig(
                rejection_rate_threshold=0.7,
                enable_decision_rules_middleware=False,
            ),
        )

        result = config.to_dict()

        assert result["rules"]["rejection_rate_threshold"] == 0.7
        assert result["rules"]["enable_decision_rules_middleware"] is False
        assert result["rules"]["circuit_breaker_configured"] is False

    def test_to_dict_context_section(self) -> None:
        """context 部分序列化"""
        from src.domain.agents.coordinator_agent_config import (
            ContextConfig,
            CoordinatorAgentConfig,
        )

        mock_event_bus = MagicMock()
        mock_compressor = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            context=ContextConfig(
                max_context_length=8000,
                enable_context_compression=False,
                context_compressor=mock_compressor,
            ),
        )

        result = config.to_dict()

        assert result["context"]["max_context_length"] == 8000
        assert result["context"]["enable_context_compression"] is False
        assert result["context"]["context_compressor_configured"] is True

    def test_to_dict_failure_section(self) -> None:
        """failure 部分序列化"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            FailureHandlingConfig,
        )

        mock_event_bus = MagicMock()
        mock_orchestrator = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            failure=FailureHandlingConfig(
                max_retry_attempts=5,
                retry_delay_seconds=2.0,
                workflow_failure_orchestrator=mock_orchestrator,
            ),
        )

        result = config.to_dict()

        assert result["failure"]["max_retry_attempts"] == 5
        assert result["failure"]["retry_delay_seconds"] == 2.0
        assert result["failure"]["workflow_failure_orchestrator_configured"] is True

    def test_to_dict_knowledge_section(self) -> None:
        """knowledge 部分序列化"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            KnowledgeConfig,
        )

        mock_event_bus = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            knowledge=KnowledgeConfig(
                enable_knowledge_retrieval=False,
                retrieval_timeout_seconds=10.0,
                max_retrieval_results=20,
            ),
        )

        result = config.to_dict()

        assert result["knowledge"]["enable_knowledge_retrieval"] is False
        assert result["knowledge"]["retrieval_timeout_seconds"] == 10.0
        assert result["knowledge"]["max_retrieval_results"] == 20

    def test_to_dict_runtime_section(self) -> None:
        """runtime 部分序列化"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            RuntimeConfig,
        )

        mock_event_bus = MagicMock()
        mock_orchestrator = MagicMock()
        mock_facade = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            runtime=RuntimeConfig(
                enable_performance_monitoring=False,
                enable_debug_logging=True,
                experiment_orchestrator=mock_orchestrator,
                supervision_facade=mock_facade,
            ),
        )

        result = config.to_dict()

        assert result["runtime"]["enable_performance_monitoring"] is False
        assert result["runtime"]["enable_debug_logging"] is True
        assert result["runtime"]["experiment_orchestrator_configured"] is True
        assert result["runtime"]["supervision_facade_configured"] is True


class TestCoordinatorAgentConfigBuilder:
    """测试 CoordinatorAgentConfigBuilder"""

    def test_builder_basic_flow(self) -> None:
        """基础流式 API"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfigBuilder,
        )

        mock_event_bus = MagicMock()
        config = (
            CoordinatorAgentConfigBuilder()
            .with_event_bus(mock_event_bus)
            .with_rejection_rate_threshold(0.7)
            .with_max_context_length(8000)
            .build()
        )

        assert config.event_bus is mock_event_bus
        assert config.rules.rejection_rate_threshold == 0.7
        assert config.context.max_context_length == 8000

    def test_builder_with_max_retry_attempts(self) -> None:
        """设置最大重试次数"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfigBuilder,
        )

        config = (
            CoordinatorAgentConfigBuilder()
            .with_event_bus(MagicMock())
            .with_max_retry_attempts(5)
            .build()
        )

        assert config.failure.max_retry_attempts == 5

    def test_builder_with_rules_config(self) -> None:
        """设置整个 rules 配置组"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfigBuilder,
            RuleEngineConfig,
        )

        rules_config = RuleEngineConfig(
            rejection_rate_threshold=0.4, enable_decision_rules_middleware=False
        )

        config = (
            CoordinatorAgentConfigBuilder()
            .with_event_bus(MagicMock())
            .with_rules_config(rules_config)
            .build()
        )

        assert config.rules.rejection_rate_threshold == 0.4
        assert config.rules.enable_decision_rules_middleware is False

    def test_builder_with_context_config(self) -> None:
        """设置整个 context 配置组"""
        from src.domain.agents.coordinator_agent_config import (
            ContextConfig,
            CoordinatorAgentConfigBuilder,
        )

        context_config = ContextConfig(max_context_length=10000, enable_context_compression=False)

        config = (
            CoordinatorAgentConfigBuilder()
            .with_event_bus(MagicMock())
            .with_context_config(context_config)
            .build()
        )

        assert config.context.max_context_length == 10000
        assert config.context.enable_context_compression is False

    def test_builder_with_failure_config(self) -> None:
        """设置整个 failure 配置组"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfigBuilder,
            FailureHandlingConfig,
        )

        failure_config = FailureHandlingConfig(max_retry_attempts=10, enable_auto_recovery=False)

        config = (
            CoordinatorAgentConfigBuilder()
            .with_event_bus(MagicMock())
            .with_failure_config(failure_config)
            .build()
        )

        assert config.failure.max_retry_attempts == 10
        assert config.failure.enable_auto_recovery is False

    def test_builder_with_knowledge_config(self) -> None:
        """设置整个 knowledge 配置组"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfigBuilder,
            KnowledgeConfig,
        )

        knowledge_config = KnowledgeConfig(
            enable_knowledge_retrieval=False, max_retrieval_results=20
        )

        config = (
            CoordinatorAgentConfigBuilder()
            .with_event_bus(MagicMock())
            .with_knowledge_config(knowledge_config)
            .build()
        )

        assert config.knowledge.enable_knowledge_retrieval is False
        assert config.knowledge.max_retrieval_results == 20

    def test_builder_with_runtime_config(self) -> None:
        """设置整个 runtime 配置组"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfigBuilder,
            RuntimeConfig,
        )

        runtime_config = RuntimeConfig(
            enable_performance_monitoring=False, enable_debug_logging=True
        )

        config = (
            CoordinatorAgentConfigBuilder()
            .with_event_bus(MagicMock())
            .with_runtime_config(runtime_config)
            .build()
        )

        assert config.runtime.enable_performance_monitoring is False
        assert config.runtime.enable_debug_logging is True

    def test_builder_returns_self_for_chaining(self) -> None:
        """验证方法返回 self 以支持链式调用"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfigBuilder,
        )

        builder = CoordinatorAgentConfigBuilder()

        assert builder.with_event_bus(MagicMock()) is builder
        assert builder.with_rejection_rate_threshold(0.5) is builder
        assert builder.with_max_context_length(5000) is builder

    def test_builder_build_validates_config(self) -> None:
        """build() 调用 validate()"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfigBuilder,
        )

        builder = CoordinatorAgentConfigBuilder()
        # 未设置 event_bus

        with pytest.raises(ValueError, match="event_bus is required"):
            builder.build()

    def test_builder_build_with_valid_config(self) -> None:
        """build() 验证通过返回配置"""
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfigBuilder,
        )

        config = CoordinatorAgentConfigBuilder().with_event_bus(MagicMock()).build()

        assert config.event_bus is not None
