"""CoordinatorBootstrap 单元测试

基于 Codex 分析的 TDD 测试套件（Phase 34.11）：
- 构造路径（带/不带 EventBus） (2 tests)
- 共享实例验证 (2 tests)
- 默认配置 (2 tests)
- Alias 保留 (2 tests)
- 可选依赖健壮性 (2 tests)
- Flag/Placeholder 行为 (2 tests)

P1-1 Step 2 测试套件（新Config系统兼容性）：
- CoordinatorAgentConfig 基础接受 (2 tests)
- Config 映射验证 (5 tests)
- 知识检索开关控制 (1 test)
- 向后兼容性保持 (1 test)

总计: 21 tests (12 原有 + 9 新增)
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_event_bus():
    """Mock EventBus"""
    bus = MagicMock()
    bus.subscribe = MagicMock()
    bus.unsubscribe = MagicMock()
    bus.publish = MagicMock()
    return bus


@pytest.fixture
def minimal_config(mock_event_bus):
    """最小配置（仅必需参数）"""
    return {
        "event_bus": mock_event_bus,
        "rejection_rate_threshold": 0.5,
        "circuit_breaker_config": None,
        "context_bridge": None,
        "failure_strategy_config": None,
        "context_compressor": None,
        "snapshot_manager": None,
        "knowledge_retriever": None,
    }


@pytest.fixture
def full_config(mock_event_bus):
    """完整配置（所有参数）"""
    return {
        "event_bus": mock_event_bus,
        "rejection_rate_threshold": 0.3,
        "circuit_breaker_config": {"failure_threshold": 5, "timeout": 60},
        "context_bridge": MagicMock(),
        "failure_strategy_config": {"default_strategy": "retry", "max_retries": 5},
        "context_compressor": MagicMock(),
        "snapshot_manager": MagicMock(),
        "knowledge_retriever": MagicMock(),
    }


# =====================================================================
# Test: 构造路径（带/不带 EventBus） (2 tests)
# =====================================================================


def test_bootstrap_with_event_bus(minimal_config):
    """测试带 EventBus 的 Bootstrap"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    bootstrap = CoordinatorBootstrap(config=minimal_config)
    wiring = bootstrap.assemble()

    # 验证核心组件存在
    assert wiring.log_collector is not None
    assert wiring.orchestrators is not None
    assert wiring.aliases is not None

    # 验证 SaveRequestOrchestrator 已创建（需要 event_bus）
    assert "save_request_orchestrator" in wiring.orchestrators
    assert wiring.orchestrators["save_request_orchestrator"] is not None

    # 验证相关 alias 不为 None
    assert wiring.aliases.get("_save_request_queue") is not None
    assert wiring.aliases.get("save_receipt_system") is not None


def test_bootstrap_without_event_bus():
    """测试无 EventBus 的 Bootstrap"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    config = {
        "event_bus": None,  # 关键：无 EventBus
        "rejection_rate_threshold": 0.5,
        "circuit_breaker_config": None,
        "context_bridge": None,
        "failure_strategy_config": None,
        "context_compressor": None,
        "snapshot_manager": None,
        "knowledge_retriever": None,
    }

    bootstrap = CoordinatorBootstrap(config=config)
    wiring = bootstrap.assemble()

    # 验证核心组件仍然存在
    assert wiring.log_collector is not None

    # 验证 SaveRequestOrchestrator 未创建（需要 event_bus）
    assert wiring.orchestrators.get("save_request_orchestrator") is None

    # 验证相关 alias 为 None
    assert wiring.aliases.get("_save_request_queue") is None
    assert wiring.aliases.get("save_receipt_system") is None


# =====================================================================
# Test: 共享实例验证 (2 tests)
# =====================================================================


def test_shared_log_collector_instance(minimal_config):
    """测试 log_collector 共享实例"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    bootstrap = CoordinatorBootstrap(config=minimal_config)
    wiring = bootstrap.assemble()

    # 验证 log_collector 是单例
    log_collector = wiring.log_collector

    # SubAgentOrchestrator 使用的 log_collector
    subagent_orch = wiring.orchestrators.get("subagent_orchestrator")
    assert subagent_orch is not None
    assert subagent_orch.log_collector is log_collector

    # PromptVersionFacade 使用的 log_collector
    prompt_facade = wiring.orchestrators.get("prompt_facade")
    assert prompt_facade is not None
    assert prompt_facade.log_collector is log_collector

    # ExperimentOrchestrator 使用的 log_collector
    experiment_orch = wiring.orchestrators.get("experiment_orchestrator")
    assert experiment_orch is not None
    assert experiment_orch.log_collector is log_collector


def test_shared_event_bus_instance(minimal_config):
    """测试 event_bus 共享实例"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    bootstrap = CoordinatorBootstrap(config=minimal_config)
    wiring = bootstrap.assemble()

    event_bus = minimal_config["event_bus"]

    # WorkflowFailureOrchestrator 使用的 event_bus
    failure_orch = wiring.orchestrators.get("failure_orchestrator")
    assert failure_orch is not None
    assert failure_orch.event_bus is event_bus

    # ContainerExecutionMonitor 使用的 event_bus
    container_monitor = wiring.orchestrators.get("container_monitor")
    assert container_monitor is not None
    assert container_monitor.event_bus is event_bus

    # ExecutionSummaryManager 使用的 event_bus
    summary_manager = wiring.orchestrators.get("summary_manager")
    assert summary_manager is not None
    assert summary_manager.event_bus is event_bus


# =====================================================================
# Test: 默认配置 (2 tests)
# =====================================================================


def test_default_failure_strategy_config(mock_event_bus):
    """测试默认 failure_strategy_config"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    config = {
        "event_bus": mock_event_bus,
        "rejection_rate_threshold": 0.5,
        "circuit_breaker_config": None,
        "context_bridge": None,
        "failure_strategy_config": None,  # 使用默认值
        "context_compressor": None,
        "snapshot_manager": None,
        "knowledge_retriever": None,
    }

    bootstrap = CoordinatorBootstrap(config=config)
    wiring = bootstrap.assemble()

    # 验证默认配置
    failure_orch = wiring.orchestrators.get("failure_orchestrator")
    assert failure_orch is not None
    # 验证默认策略 (应该在 orchestrator 的 config 中)
    assert hasattr(failure_orch, "config")
    assert failure_orch.config["default_strategy"] is not None
    assert failure_orch.config["max_retries"] == 3
    assert failure_orch.config["retry_delay"] == 1.0


def test_circuit_breaker_only_when_config_provided(minimal_config):
    """测试 CircuitBreaker 仅在提供 config 时创建"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    # 1. 无 circuit_breaker_config
    minimal_config["circuit_breaker_config"] = None
    bootstrap1 = CoordinatorBootstrap(config=minimal_config)
    wiring1 = bootstrap1.assemble()

    assert wiring1.aliases.get("circuit_breaker") is None

    # 2. 有 circuit_breaker_config
    minimal_config["circuit_breaker_config"] = {"failure_threshold": 5, "timeout": 60}
    bootstrap2 = CoordinatorBootstrap(config=minimal_config)
    wiring2 = bootstrap2.assemble()

    assert wiring2.aliases.get("circuit_breaker") is not None


# =====================================================================
# Test: Alias 保留 (2 tests)
# =====================================================================


def test_supervision_aliases_preserved(minimal_config):
    """测试 Supervision 相关别名保留"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    bootstrap = CoordinatorBootstrap(config=minimal_config)
    wiring = bootstrap.assemble()

    # 验证 SupervisionCoordinator 暴露的别名
    assert "conversation_supervision" in wiring.aliases
    assert "efficiency_monitor" in wiring.aliases
    assert "strategy_repository" in wiring.aliases

    # 验证别名与底层对象同一引用
    supervision_coordinator = wiring.orchestrators.get("supervision_coordinator")
    assert supervision_coordinator is not None
    assert wiring.aliases["conversation_supervision"] is supervision_coordinator.conversation_supervision
    assert wiring.aliases["efficiency_monitor"] is supervision_coordinator.efficiency_monitor
    assert wiring.aliases["strategy_repository"] is supervision_coordinator.strategy_repository


def test_save_request_aliases_preserved(minimal_config):
    """测试 SaveRequest 相关别名保留"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    bootstrap = CoordinatorBootstrap(config=minimal_config)
    wiring = bootstrap.assemble()

    # 验证 SaveRequest 别名
    assert "_save_request_queue" in wiring.aliases
    assert "save_receipt_system" in wiring.aliases
    assert "_save_receipt_logger" in wiring.aliases

    # 验证别名与 orchestrator 内部队列同一对象
    save_orch = wiring.orchestrators.get("save_request_orchestrator")
    assert save_orch is not None
    assert wiring.aliases["_save_request_queue"] is save_orch._save_request_queue
    assert wiring.aliases["save_receipt_system"] is save_orch.save_receipt_system
    assert wiring.aliases["_save_receipt_logger"] is save_orch.save_receipt_system.receipt_logger


# =====================================================================
# Test: 可选依赖健壮性 (2 tests)
# =====================================================================


def test_optional_knowledge_retriever_none(mock_event_bus):
    """测试 knowledge_retriever 为 None 时的健壮性"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    config = {
        "event_bus": mock_event_bus,
        "rejection_rate_threshold": 0.5,
        "circuit_breaker_config": None,
        "context_bridge": None,
        "failure_strategy_config": None,
        "context_compressor": None,
        "snapshot_manager": None,
        "knowledge_retriever": None,  # 关键：为 None
    }

    bootstrap = CoordinatorBootstrap(config=config)
    wiring = bootstrap.assemble()

    # 验证 KnowledgeRetrievalOrchestrator 仍然创建
    knowledge_orch = wiring.orchestrators.get("knowledge_retrieval_orchestrator")
    assert knowledge_orch is not None
    # knowledge_retriever 为 None 时，orchestrator 应该处理优雅
    assert knowledge_orch.knowledge_retriever is None


def test_optional_context_compressor_none(mock_event_bus):
    """测试 context_compressor 为 None 时的健壮性"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    config = {
        "event_bus": mock_event_bus,
        "rejection_rate_threshold": 0.5,
        "circuit_breaker_config": None,
        "context_bridge": None,
        "failure_strategy_config": None,
        "context_compressor": None,  # 关键：为 None
        "snapshot_manager": None,
        "knowledge_retriever": None,
    }

    bootstrap = CoordinatorBootstrap(config=config)
    wiring = bootstrap.assemble()

    # 验证 context_compressor 别名为 None
    assert wiring.aliases.get("context_compressor") is None
    assert wiring.aliases.get("snapshot_manager") is None


# =====================================================================
# Test: Flag/Placeholder 行为 (2 tests)
# =====================================================================


def test_initial_flags_all_false(minimal_config):
    """测试初始布尔标记均为 False"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    bootstrap = CoordinatorBootstrap(config=minimal_config)
    wiring = bootstrap.assemble()

    # 验证所有初始 flag 为 False
    assert wiring.aliases["_is_monitoring"] is False
    assert wiring.aliases["_is_listening_simple_messages"] is False
    assert wiring.aliases["_is_listening_reflections"] is False
    assert wiring.aliases["_is_compressing_context"] is False
    assert wiring.aliases["_auto_repair_enabled"] is False
    assert wiring.aliases["_auto_knowledge_retrieval_enabled"] is False
    assert wiring.aliases["_save_request_handler_enabled"] is False
    assert wiring.aliases["_is_listening_save_requests"] is False


def test_placeholders_remain_none(minimal_config):
    """测试 placeholder 保持 None"""
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    bootstrap = CoordinatorBootstrap(config=minimal_config)
    wiring = bootstrap.assemble()

    # 验证 placeholder 为 None
    assert wiring.aliases.get("_tool_repository") is None
    assert wiring.aliases.get("_code_repair_service") is None


# =====================================================================
# P1-1 Step 2: CoordinatorAgentConfig 兼容性测试
# =====================================================================


# =====================================================================
# Test: CoordinatorAgentConfig 基础接受 (2 tests)
# =====================================================================


def test_bootstrap_accepts_coordinator_agent_config_minimal(mock_event_bus):
    """测试 Bootstrap 接受最小 CoordinatorAgentConfig"""
    from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    # 创建最小 CoordinatorAgentConfig
    agent_config = CoordinatorAgentConfig(event_bus=mock_event_bus)

    # Bootstrap 应该能接受新Config
    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()

    # 验证核心组件存在
    assert wiring.log_collector is not None
    assert wiring.orchestrators is not None
    assert wiring.aliases is not None

    # 验证 SaveRequestOrchestrator 已创建（需要 event_bus）
    assert "save_request_orchestrator" in wiring.orchestrators
    assert wiring.orchestrators["save_request_orchestrator"] is not None


def test_bootstrap_accepts_coordinator_agent_config_full(mock_event_bus):
    """测试 Bootstrap 接受完整 CoordinatorAgentConfig"""
    from src.domain.agents.coordinator_agent_config import (
        ContextConfig,
        CoordinatorAgentConfig,
        FailureHandlingConfig,
        KnowledgeConfig,
        RuleEngineConfig,
    )
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    # 创建完整 CoordinatorAgentConfig
    agent_config = CoordinatorAgentConfig(
        event_bus=mock_event_bus,
        rules=RuleEngineConfig(
            rejection_rate_threshold=0.3,
            circuit_breaker_config={"failure_threshold": 5, "timeout": 60},
        ),
        context=ContextConfig(
            context_bridge=MagicMock(),
            context_compressor=MagicMock(),
            snapshot_manager=MagicMock(),
            max_context_length=8000,
        ),
        failure=FailureHandlingConfig(
            max_retry_attempts=5,
            retry_delay_seconds=2.0,
            enable_auto_recovery=True,
        ),
        knowledge=KnowledgeConfig(
            knowledge_retrieval_orchestrator=MagicMock(),
            enable_knowledge_retrieval=True,
        ),
    )

    # Bootstrap 应该能接受新Config
    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()

    # 验证核心组件存在
    assert wiring.log_collector is not None
    assert wiring.orchestrators is not None
    assert wiring.aliases is not None


# =====================================================================
# Test: Config 映射验证 (5 tests)
# =====================================================================


def test_rules_group_mapping(mock_event_bus):
    """测试 rules 组映射到 rejection_rate_threshold 和 circuit_breaker_config"""
    from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig, RuleEngineConfig
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    agent_config = CoordinatorAgentConfig(
        event_bus=mock_event_bus,
        rules=RuleEngineConfig(
            rejection_rate_threshold=0.3,
            circuit_breaker_config={"failure_threshold": 5, "timeout": 60},
        ),
    )

    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()

    # 验证 rejection_rate_threshold 正确传递
    # (通过检查 wiring 中使用该配置的组件)
    failure_orch = wiring.orchestrators.get("failure_orchestrator")
    assert failure_orch is not None

    # 验证 circuit_breaker 已创建
    assert wiring.aliases.get("circuit_breaker") is not None


def test_context_group_mapping(mock_event_bus):
    """测试 context 组映射到 context_bridge, context_compressor, snapshot_manager"""
    from src.domain.agents.coordinator_agent_config import ContextConfig, CoordinatorAgentConfig
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    mock_context_bridge = MagicMock()
    mock_context_compressor = MagicMock()
    mock_snapshot_manager = MagicMock()

    agent_config = CoordinatorAgentConfig(
        event_bus=mock_event_bus,
        context=ContextConfig(
            context_bridge=mock_context_bridge,
            context_compressor=mock_context_compressor,
            snapshot_manager=mock_snapshot_manager,
        ),
    )

    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()

    # 验证 context 组件正确传递到 aliases
    assert wiring.aliases.get("context_compressor") is mock_context_compressor
    assert wiring.aliases.get("snapshot_manager") is mock_snapshot_manager


def test_failure_group_mapping_to_dict_schema(mock_event_bus):
    """测试 failure 组转换为旧 dict schema"""
    from src.domain.agents.coordinator_agent_config import (
        CoordinatorAgentConfig,
        FailureHandlingConfig,
    )
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    agent_config = CoordinatorAgentConfig(
        event_bus=mock_event_bus,
        failure=FailureHandlingConfig(
            max_retry_attempts=5,
            retry_delay_seconds=2.0,
            enable_auto_recovery=True,
        ),
    )

    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()

    # 验证 failure_orchestrator 使用正确的配置
    failure_orch = wiring.orchestrators.get("failure_orchestrator")
    assert failure_orch is not None
    assert hasattr(failure_orch, "config")
    # 验证旧 schema: max_retries (不是 max_retry_attempts)
    assert failure_orch.config["max_retries"] == 5
    # 验证旧 schema: retry_delay (不是 retry_delay_seconds)
    assert failure_orch.config["retry_delay"] == 2.0


def test_failure_group_default_values_map_to_none(mock_event_bus):
    """测试 failure 组默认值映射为 None（让 Bootstrap 使用默认配置）"""
    from src.domain.agents.coordinator_agent_config import (
        CoordinatorAgentConfig,
        FailureHandlingConfig,
    )
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    # 使用默认值（max_retry_attempts=3, retry_delay_seconds=1.0, enable_auto_recovery=True）
    agent_config = CoordinatorAgentConfig(
        event_bus=mock_event_bus,
        failure=FailureHandlingConfig(),  # 全部默认值
    )

    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()

    # 验证 failure_orchestrator 使用 Bootstrap 默认配置
    failure_orch = wiring.orchestrators.get("failure_orchestrator")
    assert failure_orch is not None
    assert hasattr(failure_orch, "config")
    # Bootstrap 默认: max_retries=3, retry_delay=1.0
    assert failure_orch.config["max_retries"] == 3
    assert failure_orch.config["retry_delay"] == 1.0


def test_knowledge_group_mapping(mock_event_bus):
    """测试 knowledge 组映射到 knowledge_retriever"""
    from src.domain.agents.coordinator_agent_config import (
        CoordinatorAgentConfig,
        KnowledgeConfig,
    )
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    mock_knowledge_retriever = MagicMock()

    agent_config = CoordinatorAgentConfig(
        event_bus=mock_event_bus,
        knowledge=KnowledgeConfig(
            knowledge_retrieval_orchestrator=mock_knowledge_retriever,
            enable_knowledge_retrieval=True,
        ),
    )

    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()

    # 验证 knowledge_retrieval_orchestrator 正确传递
    knowledge_orch = wiring.orchestrators.get("knowledge_retrieval_orchestrator")
    assert knowledge_orch is not None
    assert knowledge_orch.knowledge_retriever is mock_knowledge_retriever


# =====================================================================
# Test: 知识检索开关控制 (1 test)
# =====================================================================


def test_enable_knowledge_retrieval_false_forces_none(mock_event_bus):
    """测试 enable_knowledge_retrieval=False 强制 knowledge_retriever=None"""
    from src.domain.agents.coordinator_agent_config import (
        CoordinatorAgentConfig,
        KnowledgeConfig,
    )
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    mock_knowledge_retriever = MagicMock()

    agent_config = CoordinatorAgentConfig(
        event_bus=mock_event_bus,
        knowledge=KnowledgeConfig(
            knowledge_retrieval_orchestrator=mock_knowledge_retriever,
            enable_knowledge_retrieval=False,  # 关键：禁用知识检索
        ),
    )

    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()

    # 验证即使提供了 knowledge_retrieval_orchestrator，也被强制为 None
    knowledge_orch = wiring.orchestrators.get("knowledge_retrieval_orchestrator")
    assert knowledge_orch is not None
    assert knowledge_orch.knowledge_retriever is None


# =====================================================================
# Test: 向后兼容性保持 (1 test)
# =====================================================================


def test_backward_compatibility_all_old_configs_still_work(mock_event_bus):
    """测试向后兼容：旧 CoordinatorConfig 和 dict 仍然工作"""
    from src.domain.services.coordinator_bootstrap import (
        CoordinatorBootstrap,
        CoordinatorConfig,
    )

    # 1. 测试旧 CoordinatorConfig
    old_config_obj = CoordinatorConfig(
        event_bus=mock_event_bus,
        rejection_rate_threshold=0.5,
        circuit_breaker_config=None,
        context_bridge=None,
        failure_strategy_config=None,
        context_compressor=None,
        snapshot_manager=None,
        knowledge_retriever=None,
    )
    bootstrap1 = CoordinatorBootstrap(config=old_config_obj)
    wiring1 = bootstrap1.assemble()
    assert wiring1.log_collector is not None

    # 2. 测试旧 dict
    old_config_dict = {
        "event_bus": mock_event_bus,
        "rejection_rate_threshold": 0.5,
        "circuit_breaker_config": None,
        "context_bridge": None,
        "failure_strategy_config": None,
        "context_compressor": None,
        "snapshot_manager": None,
        "knowledge_retriever": None,
    }
    bootstrap2 = CoordinatorBootstrap(config=old_config_dict)
    wiring2 = bootstrap2.assemble()
    assert wiring2.log_collector is not None


# =====================================================================
# P1-1 Step 2 Critical Fixes 测试（Codex 建议补充）
# =====================================================================


def test_magicmock_not_misdetected_as_agent_config():
    """P1-1 Critical Fix #1: 避免 duck typing 误判 - MagicMock 不应被当作 CoordinatorAgentConfig"""
    from unittest.mock import MagicMock

    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    fake = MagicMock()
    fake.rules = MagicMock()
    fake.context = MagicMock()
    fake.failure = MagicMock()
    fake.knowledge = MagicMock()

    with pytest.raises(TypeError, match="Unsupported config type"):
        CoordinatorBootstrap(config=fake)


def test_agent_config_validate_relaxed_allows_event_bus_none():
    """P1-1 Critical Fix #3: Bootstrap 调用 validate，但对 event_bus=None 采用宽松模式"""
    from src.domain.agents.coordinator_agent_config import CoordinatorAgentConfig
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    agent_config = CoordinatorAgentConfig(event_bus=None)
    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()

    # 应该能正常装配
    assert wiring.log_collector is not None
    # SaveRequestOrchestrator 不应创建（需要 event_bus）
    assert wiring.orchestrators.get("save_request_orchestrator") is None


def test_failure_mapping_does_not_include_unconsumed_fields(mock_event_bus):
    """P1-1 Critical Fix #2 & #4: failure 映射应只包含 orchestrator 消费字段，避免假生效配置"""
    from src.domain.agents.coordinator_agent_config import (
        CoordinatorAgentConfig,
        FailureHandlingConfig,
    )
    from src.domain.services.coordinator_bootstrap import CoordinatorBootstrap

    agent_config = CoordinatorAgentConfig(
        event_bus=mock_event_bus,
        failure=FailureHandlingConfig(max_retry_attempts=5, retry_delay_seconds=2.0),
    )
    bootstrap = CoordinatorBootstrap(config=agent_config)
    wiring = bootstrap.assemble()
    failure_orch = wiring.orchestrators["failure_orchestrator"]

    # 验证只包含实际消费的字段
    assert "max_retries" in failure_orch.config
    assert "retry_delay" in failure_orch.config
    assert "default_strategy" in failure_orch.config

    # P1-1 Critical Fix #4: enable_auto_recovery 不应包含（未被消费）
    assert "enable_auto_recovery" not in failure_orch.config
