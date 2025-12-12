"""CoordinatorAgent 配置兼容性测试

测试 P1-1 步骤1：新旧配置参数的兼容性。

测试场景：
1. 旧用法最小：无参数创建
2. 旧用法单参数：传入单个旧参数
3. 新用法纯config：仅传入config参数
4. 混合一致：旧参数与config值一致，不抛出错误
5. 混合冲突：旧参数与config值冲突，抛出ValueError
6. 默认值处理：默认值不导致误判冲突
7. 复杂字段转换：failure_strategy_config dict → FailureHandlingConfig
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestLegacyUsageMinimal:
    """测试场景1：旧用法最小（无参数）"""

    @patch("src.domain.services.coordinator_bootstrap.CoordinatorBootstrap")
    def test_no_arguments_creates_with_defaults(self, mock_bootstrap):
        """无参数创建使用默认配置"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        # Mock Bootstrap to avoid actual initialization
        mock_wiring = MagicMock()
        mock_wiring.base_state = {
            "_rules": [],
            "_statistics": {"total": 0, "passed": 0, "rejected": 0},
            "workflow_states": {},
            "_is_monitoring": False,
            "_node_failure_strategies": {},
            "_workflow_agents": {},
            "message_log": [],
            "reflection_contexts": {},
            "_compressed_contexts": {},
            "_knowledge_cache": {},
            "_is_listening_simple_messages": False,
            "_is_listening_reflections": False,
            "_is_compressing_context": False,
        }
        mock_wiring.log_collector = None
        mock_wiring.aliases = {}
        mock_wiring.orchestrators = {
            "failure_orchestrator": MagicMock(),
            "container_monitor": MagicMock(),
            "log_integration": MagicMock(),
            "knowledge_manager": MagicMock(),
            "knowledge_retrieval_orchestrator": MagicMock(),
            "summary_manager": MagicMock(),
            "power_compressor_facade": MagicMock(),
            "subagent_orchestrator": MagicMock(),
            "supervision_coordinator": MagicMock(
                conversation_supervision=MagicMock(),
                efficiency_monitor=MagicMock(),
                strategy_repository=MagicMock(),
            ),
            "prompt_facade": MagicMock(),
            "experiment_orchestrator": MagicMock(),
            "save_request_orchestrator": MagicMock(),
            "context_injection_manager": MagicMock(),
            "supervision_module": MagicMock(),
            "supervision_facade": MagicMock(),
            "intervention_coordinator": MagicMock(),
            "workflow_modifier": MagicMock(),
            "task_terminator": MagicMock(),
            "safety_guard": MagicMock(),
            "injection_logger": MagicMock(),
            "supervision_logger": MagicMock(),
            "intervention_logger": MagicMock(),
        }
        mock_bootstrap.return_value.assemble.return_value = mock_wiring

        # Create agent without arguments
        _ = CoordinatorAgent()

        # Verify Bootstrap was called with default values
        assert mock_bootstrap.called
        call_config = mock_bootstrap.call_args[1]["config"]
        assert call_config.event_bus is None
        # P1-1 Step 2: 配置已分组，需访问 rules.rejection_rate_threshold
        assert call_config.rules.rejection_rate_threshold == 0.5  # DEFAULT_REJECTION_RATE_THRESHOLD


class TestLegacyUsageSingleParam:
    """测试场景2：旧用法单参数"""

    @patch("src.domain.services.coordinator_bootstrap.CoordinatorBootstrap")
    def test_single_event_bus_parameter(self, mock_bootstrap):
        """传入单个event_bus参数"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        mock_event_bus = MagicMock()

        # Mock Bootstrap
        mock_wiring = MagicMock()
        mock_wiring.base_state = {
            "_rules": [],
            "_statistics": {"total": 0, "passed": 0, "rejected": 0},
            "workflow_states": {},
            "_is_monitoring": False,
            "_node_failure_strategies": {},
            "_workflow_agents": {},
            "message_log": [],
            "reflection_contexts": {},
            "_compressed_contexts": {},
            "_knowledge_cache": {},
            "_is_listening_simple_messages": False,
            "_is_listening_reflections": False,
            "_is_compressing_context": False,
        }
        mock_wiring.log_collector = None
        mock_wiring.aliases = {}
        mock_wiring.orchestrators = {
            "failure_orchestrator": MagicMock(),
            "container_monitor": MagicMock(),
            "log_integration": MagicMock(),
            "knowledge_manager": MagicMock(),
            "knowledge_retrieval_orchestrator": MagicMock(),
            "summary_manager": MagicMock(),
            "power_compressor_facade": MagicMock(),
            "subagent_orchestrator": MagicMock(),
            "supervision_coordinator": MagicMock(
                conversation_supervision=MagicMock(),
                efficiency_monitor=MagicMock(),
                strategy_repository=MagicMock(),
            ),
            "prompt_facade": MagicMock(),
            "experiment_orchestrator": MagicMock(),
            "save_request_orchestrator": MagicMock(),
            "context_injection_manager": MagicMock(),
            "supervision_module": MagicMock(),
            "supervision_facade": MagicMock(),
            "intervention_coordinator": MagicMock(),
            "workflow_modifier": MagicMock(),
            "task_terminator": MagicMock(),
            "safety_guard": MagicMock(),
            "injection_logger": MagicMock(),
            "supervision_logger": MagicMock(),
            "intervention_logger": MagicMock(),
        }
        mock_bootstrap.return_value.assemble.return_value = mock_wiring

        # Create agent with event_bus
        _ = CoordinatorAgent(event_bus=mock_event_bus)

        # Verify event_bus was passed to Bootstrap
        call_config = mock_bootstrap.call_args[1]["config"]
        assert call_config.event_bus is mock_event_bus


class TestNewUsagePureConfig:
    """测试场景3：新用法纯config"""

    @patch("src.domain.services.coordinator_bootstrap.CoordinatorBootstrap")
    def test_pure_config_usage(self, mock_bootstrap):
        """仅传入config参数"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            RuleEngineConfig,
        )

        mock_event_bus = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            rules=RuleEngineConfig(rejection_rate_threshold=0.7),
        )

        # Mock Bootstrap
        mock_wiring = MagicMock()
        mock_wiring.base_state = {
            "_rules": [],
            "_statistics": {"total": 0, "passed": 0, "rejected": 0},
            "workflow_states": {},
            "_is_monitoring": False,
            "_node_failure_strategies": {},
            "_workflow_agents": {},
            "message_log": [],
            "reflection_contexts": {},
            "_compressed_contexts": {},
            "_knowledge_cache": {},
            "_is_listening_simple_messages": False,
            "_is_listening_reflections": False,
            "_is_compressing_context": False,
        }
        mock_wiring.log_collector = None
        mock_wiring.aliases = {}
        mock_wiring.orchestrators = {
            "failure_orchestrator": MagicMock(),
            "container_monitor": MagicMock(),
            "log_integration": MagicMock(),
            "knowledge_manager": MagicMock(),
            "knowledge_retrieval_orchestrator": MagicMock(),
            "summary_manager": MagicMock(),
            "power_compressor_facade": MagicMock(),
            "subagent_orchestrator": MagicMock(),
            "supervision_coordinator": MagicMock(
                conversation_supervision=MagicMock(),
                efficiency_monitor=MagicMock(),
                strategy_repository=MagicMock(),
            ),
            "prompt_facade": MagicMock(),
            "experiment_orchestrator": MagicMock(),
            "save_request_orchestrator": MagicMock(),
            "context_injection_manager": MagicMock(),
            "supervision_module": MagicMock(),
            "supervision_facade": MagicMock(),
            "intervention_coordinator": MagicMock(),
            "workflow_modifier": MagicMock(),
            "task_terminator": MagicMock(),
            "safety_guard": MagicMock(),
            "injection_logger": MagicMock(),
            "supervision_logger": MagicMock(),
            "intervention_logger": MagicMock(),
        }
        mock_bootstrap.return_value.assemble.return_value = mock_wiring

        # Create agent with config only
        _ = CoordinatorAgent(config=config)

        # Verify config values were used
        call_config = mock_bootstrap.call_args[1]["config"]
        assert call_config.event_bus is mock_event_bus
        # P1-1 Step 2: 配置已分组，需访问 rules.rejection_rate_threshold
        assert call_config.rules.rejection_rate_threshold == 0.7


class TestMixedUsageConsistent:
    """测试场景4：混合一致（不冲突）"""

    @patch("src.domain.services.coordinator_bootstrap.CoordinatorBootstrap")
    def test_consistent_mixed_usage(self, mock_bootstrap):
        """旧参数与config值一致，不抛出错误"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            RuleEngineConfig,
        )

        mock_event_bus = MagicMock()
        config = CoordinatorAgentConfig(
            event_bus=mock_event_bus,
            rules=RuleEngineConfig(rejection_rate_threshold=0.7),
        )

        # Mock Bootstrap
        mock_wiring = MagicMock()
        mock_wiring.base_state = {
            "_rules": [],
            "_statistics": {"total": 0, "passed": 0, "rejected": 0},
            "workflow_states": {},
            "_is_monitoring": False,
            "_node_failure_strategies": {},
            "_workflow_agents": {},
            "message_log": [],
            "reflection_contexts": {},
            "_compressed_contexts": {},
            "_knowledge_cache": {},
            "_is_listening_simple_messages": False,
            "_is_listening_reflections": False,
            "_is_compressing_context": False,
        }
        mock_wiring.log_collector = None
        mock_wiring.aliases = {}
        mock_wiring.orchestrators = {
            "failure_orchestrator": MagicMock(),
            "container_monitor": MagicMock(),
            "log_integration": MagicMock(),
            "knowledge_manager": MagicMock(),
            "knowledge_retrieval_orchestrator": MagicMock(),
            "summary_manager": MagicMock(),
            "power_compressor_facade": MagicMock(),
            "subagent_orchestrator": MagicMock(),
            "supervision_coordinator": MagicMock(
                conversation_supervision=MagicMock(),
                efficiency_monitor=MagicMock(),
                strategy_repository=MagicMock(),
            ),
            "prompt_facade": MagicMock(),
            "experiment_orchestrator": MagicMock(),
            "save_request_orchestrator": MagicMock(),
            "context_injection_manager": MagicMock(),
            "supervision_module": MagicMock(),
            "supervision_facade": MagicMock(),
            "intervention_coordinator": MagicMock(),
            "workflow_modifier": MagicMock(),
            "task_terminator": MagicMock(),
            "safety_guard": MagicMock(),
            "injection_logger": MagicMock(),
            "supervision_logger": MagicMock(),
            "intervention_logger": MagicMock(),
        }
        mock_bootstrap.return_value.assemble.return_value = mock_wiring

        # Pass consistent values: event_bus matches config.event_bus
        agent = CoordinatorAgent(event_bus=mock_event_bus, config=config)

        # Should succeed without raising ValueError
        assert agent.event_bus is mock_event_bus


class TestMixedUsageConflict:
    """测试场景5：混合冲突"""

    def test_conflicting_event_bus_raises_error(self):
        """event_bus冲突时抛出ValueError"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig

        mock_bus1 = MagicMock(name="bus1")
        mock_bus2 = MagicMock(name="bus2")

        config = CoordinatorAgentConfig(event_bus=mock_bus1)

        with pytest.raises(ValueError, match="conflicting configuration"):
            CoordinatorAgent(event_bus=mock_bus2, config=config)

    def test_conflicting_rejection_rate_raises_error(self):
        """rejection_rate_threshold冲突时抛出ValueError"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            RuleEngineConfig,
        )

        config = CoordinatorAgentConfig(
            rules=RuleEngineConfig(rejection_rate_threshold=0.3),
        )

        with pytest.raises(ValueError, match="conflicting configuration"):
            CoordinatorAgent(rejection_rate_threshold=0.7, config=config)


class TestDefaultValueHandling:
    """测试场景6：默认值处理"""

    @patch("src.domain.services.coordinator_bootstrap.CoordinatorBootstrap")
    def test_default_values_do_not_conflict(self, mock_bootstrap):
        """未传入的默认值不导致冲突"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.coordinator_agent_config import (
            CoordinatorAgentConfig,
            RuleEngineConfig,
        )

        # Create config with non-default rejection_rate
        config = CoordinatorAgentConfig(
            rules=RuleEngineConfig(rejection_rate_threshold=0.7),
        )

        # Mock Bootstrap
        mock_wiring = MagicMock()
        mock_wiring.base_state = {
            "_rules": [],
            "_statistics": {"total": 0, "passed": 0, "rejected": 0},
            "workflow_states": {},
            "_is_monitoring": False,
            "_node_failure_strategies": {},
            "_workflow_agents": {},
            "message_log": [],
            "reflection_contexts": {},
            "_compressed_contexts": {},
            "_knowledge_cache": {},
            "_is_listening_simple_messages": False,
            "_is_listening_reflections": False,
            "_is_compressing_context": False,
        }
        mock_wiring.log_collector = None
        mock_wiring.aliases = {}
        mock_wiring.orchestrators = {
            "failure_orchestrator": MagicMock(),
            "container_monitor": MagicMock(),
            "log_integration": MagicMock(),
            "knowledge_manager": MagicMock(),
            "knowledge_retrieval_orchestrator": MagicMock(),
            "summary_manager": MagicMock(),
            "power_compressor_facade": MagicMock(),
            "subagent_orchestrator": MagicMock(),
            "supervision_coordinator": MagicMock(
                conversation_supervision=MagicMock(),
                efficiency_monitor=MagicMock(),
                strategy_repository=MagicMock(),
            ),
            "prompt_facade": MagicMock(),
            "experiment_orchestrator": MagicMock(),
            "save_request_orchestrator": MagicMock(),
            "context_injection_manager": MagicMock(),
            "supervision_module": MagicMock(),
            "supervision_facade": MagicMock(),
            "intervention_coordinator": MagicMock(),
            "workflow_modifier": MagicMock(),
            "task_terminator": MagicMock(),
            "safety_guard": MagicMock(),
            "injection_logger": MagicMock(),
            "supervision_logger": MagicMock(),
            "intervention_logger": MagicMock(),
        }
        mock_bootstrap.return_value.assemble.return_value = mock_wiring

        # Do not pass rejection_rate_threshold explicitly - should use sentinel
        # and not conflict with config
        _ = CoordinatorAgent(config=config)

        # Should succeed without ValueError
        call_config = mock_bootstrap.call_args[1]["config"]
        # P1-1 Step 2: 配置已分组，需访问 rules.rejection_rate_threshold
        assert call_config.rules.rejection_rate_threshold == 0.7


class TestComplexFieldConversion:
    """测试场景7：复杂字段转换"""

    @patch("src.domain.services.coordinator_bootstrap.CoordinatorBootstrap")
    def test_failure_strategy_dict_to_config(self, mock_bootstrap):
        """failure_strategy_config dict → Bootstrap schema 映射（Critical Fix-1）"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.workflow_failure_orchestrator import (
            FailureHandlingStrategy,
        )

        failure_dict = {
            "max_retry_attempts": 5,
            "retry_delay_seconds": 2.0,
            "enable_auto_recovery": False,
        }

        # Mock Bootstrap
        mock_wiring = MagicMock()
        mock_wiring.base_state = {
            "_rules": [],
            "_statistics": {"total": 0, "passed": 0, "rejected": 0},
            "workflow_states": {},
            "_is_monitoring": False,
            "_node_failure_strategies": {},
            "_workflow_agents": {},
            "message_log": [],
            "reflection_contexts": {},
            "_compressed_contexts": {},
            "_knowledge_cache": {},
            "_is_listening_simple_messages": False,
            "_is_listening_reflections": False,
            "_is_compressing_context": False,
        }
        mock_wiring.log_collector = None
        mock_wiring.aliases = {}
        mock_wiring.orchestrators = {
            "failure_orchestrator": MagicMock(),
            "container_monitor": MagicMock(),
            "log_integration": MagicMock(),
            "knowledge_manager": MagicMock(),
            "knowledge_retrieval_orchestrator": MagicMock(),
            "summary_manager": MagicMock(),
            "power_compressor_facade": MagicMock(),
            "subagent_orchestrator": MagicMock(),
            "supervision_coordinator": MagicMock(
                conversation_supervision=MagicMock(),
                efficiency_monitor=MagicMock(),
                strategy_repository=MagicMock(),
            ),
            "prompt_facade": MagicMock(),
            "experiment_orchestrator": MagicMock(),
            "save_request_orchestrator": MagicMock(),
            "context_injection_manager": MagicMock(),
            "supervision_module": MagicMock(),
            "supervision_facade": MagicMock(),
            "intervention_coordinator": MagicMock(),
            "workflow_modifier": MagicMock(),
            "task_terminator": MagicMock(),
            "safety_guard": MagicMock(),
            "injection_logger": MagicMock(),
            "supervision_logger": MagicMock(),
            "intervention_logger": MagicMock(),
        }
        mock_bootstrap.return_value.assemble.return_value = mock_wiring

        # Create agent with failure_strategy_config dict
        _ = CoordinatorAgent(failure_strategy_config=failure_dict)

        # P1-1 Step 2: 配置已分组，验证 failure 组的转换
        call_config = mock_bootstrap.call_args[1]["config"]
        # failure_strategy_config dict → FailureHandlingConfig 对象
        assert call_config.failure.max_retry_attempts == 5
        assert call_config.failure.retry_delay_seconds == 2.0
        assert call_config.failure.enable_auto_recovery is False
