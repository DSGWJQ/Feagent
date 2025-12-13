"""Tests for supervision protocols (P1-8 Phase 1)

测试内容：
1. 协议契约测试
2. 适配器功能测试
3. 向后兼容性测试
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from src.domain.services.supervision.protocols import (
    AnalysisRequest,
    AnalysisResult,
    ExecutionResult,
    InterventionExecutor,
    InterventionManagerExecutorAdapter,
    InterventionRequest,
    PromptScannerAnalyzerAdapter,
    StrategyProvider,
    StrategyRepositoryProviderAdapter,
    SupervisionAnalyzer,
    SupervisionModuleAnalyzerAdapter,
)

# =============================================================================
# 协议契约测试
# =============================================================================


class TestProtocolContracts:
    """测试协议契约满足性"""

    def test_supervision_analyzer_protocol_runtime_checkable(self):
        """测试 SupervisionAnalyzer 可运行时检查"""
        adapter = SupervisionModuleAnalyzerAdapter(MagicMock())
        assert isinstance(adapter, SupervisionAnalyzer)

    def test_intervention_executor_protocol_runtime_checkable(self):
        """测试 InterventionExecutor 可运行时检查"""
        adapter = InterventionManagerExecutorAdapter(MagicMock())
        assert isinstance(adapter, InterventionExecutor)

    def test_strategy_provider_protocol_runtime_checkable(self):
        """测试 StrategyProvider 可运行时检查"""
        adapter = StrategyRepositoryProviderAdapter(MagicMock())
        assert isinstance(adapter, StrategyProvider)


# =============================================================================
# AnalysisResult 测试
# =============================================================================


class TestAnalysisResult:
    """测试统一分析结果"""

    def test_analysis_result_default_values(self):
        """测试默认值"""
        result = AnalysisResult()
        assert result.findings == ()
        assert result.severity == "low"
        assert result.recommendations == ()
        assert result.metadata == {}
        assert result.raw is None

    def test_analysis_result_with_findings(self):
        """测试带发现的结果"""
        findings = [{"issue": "test"}]
        result = AnalysisResult(findings=findings, severity="high")
        assert result.findings == findings
        assert result.severity == "high"

    def test_analysis_result_immutable(self):
        """测试结果不可变"""
        result = AnalysisResult()
        with pytest.raises(AttributeError):
            result.severity = "high"  # type: ignore


# =============================================================================
# ExecutionResult 测试
# =============================================================================


class TestExecutionResult:
    """测试统一执行结果"""

    def test_execution_result_default_values(self):
        """测试默认值"""
        result = ExecutionResult()
        assert result.success is True
        assert result.action_taken == ""
        assert result.message == ""
        assert result.outcome == {}

    def test_execution_result_with_action(self):
        """测试带动作的结果"""
        result = ExecutionResult(
            success=True,
            action_taken="context_injection",
            message="Injected warning",
        )
        assert result.action_taken == "context_injection"
        assert result.message == "Injected warning"


# =============================================================================
# SupervisionModuleAnalyzerAdapter 测试
# =============================================================================


class TestSupervisionModuleAnalyzerAdapter:
    """测试 SupervisionModule 适配器"""

    def test_analyze_context(self):
        """测试分析上下文"""
        # Arrange
        mock_module = MagicMock()
        mock_module.analyze_context.return_value = [{"type": "warning", "message": "test"}]
        adapter = SupervisionModuleAnalyzerAdapter(mock_module)

        # Act
        result = adapter.analyze(AnalysisRequest(kind="context", payload={"key": "value"}))

        # Assert
        mock_module.analyze_context.assert_called_once_with({"key": "value"})
        assert len(result.findings) == 1
        assert result.metadata["kind"] == "context"

    def test_analyze_save_request(self):
        """测试分析保存请求"""
        # Arrange
        mock_module = MagicMock()
        mock_module.analyze_save_request.return_value = []
        adapter = SupervisionModuleAnalyzerAdapter(mock_module)

        # Act
        result = adapter.analyze(AnalysisRequest(kind="save_request", payload={"data": "test"}))

        # Assert
        mock_module.analyze_save_request.assert_called_once()
        assert result.metadata["kind"] == "save_request"

    def test_analyze_decision_chain(self):
        """测试分析决策链"""
        # Arrange
        mock_module = MagicMock()
        mock_module.analyze_decision_chain.return_value = [{"decision": "approved"}]
        adapter = SupervisionModuleAnalyzerAdapter(mock_module)
        payload = {"decisions": [{"id": "1"}], "session_id": "sess-123"}

        # Act
        result = adapter.analyze(AnalysisRequest(kind="decision_chain", payload=payload))

        # Assert
        mock_module.analyze_decision_chain.assert_called_once_with([{"id": "1"}], "sess-123")
        assert result.metadata["kind"] == "decision_chain"

    def test_analyze_unsupported_kind(self):
        """测试不支持的分析类型"""
        adapter = SupervisionModuleAnalyzerAdapter(MagicMock())
        with pytest.raises(ValueError, match="Unsupported analysis kind"):
            adapter.analyze(AnalysisRequest(kind="text", payload={}))  # type: ignore


# =============================================================================
# PromptScannerAnalyzerAdapter 测试
# =============================================================================


class TestPromptScannerAnalyzerAdapter:
    """测试 PromptScanner 适配器"""

    def test_analyze_text(self):
        """测试扫描文本"""

        # Arrange
        @dataclass
        class MockScanResult:
            passed: bool = True
            recommended_action: str = "allow"

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = MockScanResult()
        adapter = PromptScannerAnalyzerAdapter(mock_scanner)

        # Act
        result = adapter.analyze(AnalysisRequest(kind="text", payload={"text": "Hello world"}))

        # Assert
        mock_scanner.scan.assert_called_once_with("Hello world")
        assert result.severity == "low"
        assert result.metadata["kind"] == "text"

    def test_analyze_text_extracts_from_message(self):
        """测试从 message 字段提取文本"""
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = MagicMock(recommended_action="allow")
        adapter = PromptScannerAnalyzerAdapter(mock_scanner)

        adapter.analyze(AnalysisRequest(kind="text", payload={"message": "Test message"}))

        mock_scanner.scan.assert_called_once_with("Test message")

    def test_analyze_text_high_severity_on_block(self):
        """测试 block 动作触发高严重程度"""
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = MagicMock(recommended_action="block")
        adapter = PromptScannerAnalyzerAdapter(mock_scanner)

        result = adapter.analyze(AnalysisRequest(kind="text", payload={"text": "Dangerous"}))

        assert result.severity == "high"

    def test_analyze_non_text_raises_error(self):
        """测试非文本类型抛出错误"""
        adapter = PromptScannerAnalyzerAdapter(MagicMock())
        with pytest.raises(ValueError, match="Unsupported analysis kind for PromptScanner"):
            adapter.analyze(AnalysisRequest(kind="context", payload={}))


# =============================================================================
# InterventionManagerExecutorAdapter 测试
# =============================================================================


class TestInterventionManagerExecutorAdapter:
    """测试 InterventionManager 适配器"""

    def test_execute_context_injection(self):
        """测试上下文注入"""
        # Arrange
        mock_manager = MagicMock()
        mock_manager.inject_context.return_value = {"injected": True}
        adapter = InterventionManagerExecutorAdapter(mock_manager)

        request = InterventionRequest(
            kind="context_injection",
            target_agent="conversation",
            context_type="warning",
            message="Be careful",
            severity="medium",
        )

        # Act
        result = adapter.execute(request)

        # Assert
        mock_manager.inject_context.assert_called_once()
        assert result.success is True
        assert result.action_taken == "context_injection"

    def test_execute_task_termination(self):
        """测试任务终止"""
        mock_manager = MagicMock()
        mock_manager.terminate_task.return_value = MagicMock(success=True, message="Terminated")
        adapter = InterventionManagerExecutorAdapter(mock_manager)

        request = InterventionRequest(
            kind="task_termination",
            task_id="task-123",
            reason="Security violation",
            graceful=True,
        )

        result = adapter.execute(request)

        assert result.action_taken == "task_termination"
        mock_manager.terminate_task.assert_called_once()

    def test_execute_replan_requested(self):
        """测试重新规划请求"""
        mock_manager = MagicMock()
        mock_manager.trigger_replan.return_value = {"replan_id": "rp-1"}
        adapter = InterventionManagerExecutorAdapter(mock_manager)

        request = InterventionRequest(
            kind="replan_requested",
            workflow_id="wf-123",
            reason="Efficiency below threshold",
        )

        result = adapter.execute(request)

        assert result.action_taken == "replan_requested"
        mock_manager.trigger_replan.assert_called_once()

    def test_execute_workflow_termination_not_supported(self):
        """测试工作流终止不支持时抛出错误"""
        mock_manager = MagicMock(spec=[])  # 不包含 terminate_workflow
        adapter = InterventionManagerExecutorAdapter(mock_manager)

        request = InterventionRequest(kind="workflow_termination", workflow_id="wf-123")

        with pytest.raises(ValueError, match="terminate_workflow not supported"):
            adapter.execute(request)

    def test_execute_unsupported_kind(self):
        """测试不支持的干预类型"""
        adapter = InterventionManagerExecutorAdapter(MagicMock())
        request = InterventionRequest(kind="unknown")  # type: ignore

        with pytest.raises(ValueError, match="Unsupported intervention kind"):
            adapter.execute(request)


# =============================================================================
# StrategyRepositoryProviderAdapter 测试
# =============================================================================


class TestStrategyRepositoryProviderAdapter:
    """测试 StrategyRepository 适配器"""

    def test_get_strategy_by_condition(self):
        """测试按条件获取策略"""
        # Arrange
        mock_repo = MagicMock()
        mock_repo.find_by_condition.return_value = [
            {"id": "s1", "name": "Strategy 1", "priority": 10}
        ]
        adapter = StrategyRepositoryProviderAdapter(mock_repo)

        # Act
        result = adapter.get_strategy({"condition": "loop_detected"})

        # Assert
        mock_repo.find_by_condition.assert_called_once_with("loop_detected")
        assert result is not None
        assert result["id"] == "s1"

    def test_get_strategy_by_trigger_condition(self):
        """测试按 trigger_condition 获取策略"""
        mock_repo = MagicMock()
        mock_repo.find_by_condition.return_value = [{"id": "s2"}]
        adapter = StrategyRepositoryProviderAdapter(mock_repo)

        adapter.get_strategy({"trigger_condition": "efficiency_low"})

        mock_repo.find_by_condition.assert_called_once_with("efficiency_low")

    def test_get_strategy_returns_none_when_no_condition(self):
        """测试无条件时返回 None"""
        adapter = StrategyRepositoryProviderAdapter(MagicMock())

        result = adapter.get_strategy({})

        assert result is None

    def test_get_strategy_returns_none_when_no_matches(self):
        """测试无匹配时返回 None"""
        mock_repo = MagicMock()
        mock_repo.find_by_condition.return_value = []
        adapter = StrategyRepositoryProviderAdapter(mock_repo)

        result = adapter.get_strategy({"condition": "unknown"})

        assert result is None

    def test_get_strategy_custom_condition_keys(self):
        """测试自定义条件键"""
        mock_repo = MagicMock()
        mock_repo.find_by_condition.return_value = [{"id": "s3"}]
        adapter = StrategyRepositoryProviderAdapter(
            mock_repo, condition_keys=["custom_key", "condition"]
        )

        adapter.get_strategy({"custom_key": "custom_value"})

        mock_repo.find_by_condition.assert_called_once_with("custom_value")


# =============================================================================
# 集成测试
# =============================================================================


class TestProtocolsIntegration:
    """协议集成测试"""

    def test_full_analysis_flow(self):
        """测试完整分析流程"""
        # 模拟 SupervisionModule
        mock_module = MagicMock()
        mock_module.analyze_context.return_value = [{"type": "info", "message": "Context analyzed"}]

        # 创建适配器
        analyzer: SupervisionAnalyzer[AnalysisRequest, AnalysisResult] = (
            SupervisionModuleAnalyzerAdapter(mock_module)
        )

        # 使用统一接口
        request = AnalysisRequest(kind="context", payload={"user_input": "test"})
        result = analyzer.analyze(request)

        # 验证
        assert isinstance(result, AnalysisResult)
        assert len(result.findings) > 0

    def test_full_intervention_flow(self):
        """测试完整干预流程"""
        # 模拟 InterventionManager
        mock_manager = MagicMock()
        mock_manager.inject_context.return_value = {"injected": True}

        # 创建适配器
        executor: InterventionExecutor[InterventionRequest, ExecutionResult] = (
            InterventionManagerExecutorAdapter(mock_manager)
        )

        # 使用统一接口
        request = InterventionRequest(
            kind="context_injection",
            target_agent="conversation",
            message="Warning injected",
        )
        result = executor.execute(request)

        # 验证
        assert isinstance(result, ExecutionResult)
        assert result.success is True
