"""执行总结单元测试 - Phase 5

测试目标：
1. ExecutionSummary 数据结构
2. ConversationAgent 生成总结
3. Coordinator 记录总结
4. WorkflowAgent 推送最终状态到前端

运行命令：
    pytest tests/unit/domain/agents/test_execution_summary.py -v --tb=short
"""

from datetime import datetime

import pytest

# === 测试：ExecutionSummary 数据结构 ===


class TestExecutionSummaryStructure:
    """ExecutionSummary 数据结构测试"""

    def test_execution_summary_has_required_fields(self):
        """测试：ExecutionSummary 包含必需字段"""
        from src.domain.agents.execution_summary import ExecutionSummary

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=True,
        )

        # 必需字段
        assert summary.workflow_id == "wf_123"
        assert summary.session_id == "session_1"
        assert summary.success is True
        assert summary.summary_id is not None

        # 默认值字段
        assert isinstance(summary.execution_logs, list)
        assert isinstance(summary.errors, list)
        assert isinstance(summary.rules_applied, list)
        assert isinstance(summary.knowledge_references, list)
        assert isinstance(summary.tools_used, list)
        assert isinstance(summary.node_results, dict)
        assert summary.started_at is not None
        assert summary.completed_at is None

    def test_execution_summary_with_execution_logs(self):
        """测试：ExecutionSummary 包含执行日志"""
        from src.domain.agents.execution_summary import ExecutionLogEntry, ExecutionSummary

        logs = [
            ExecutionLogEntry(
                node_id="node_1",
                action="execute",
                timestamp=datetime.now(),
                message="开始执行",
            ),
            ExecutionLogEntry(
                node_id="node_1",
                action="completed",
                timestamp=datetime.now(),
                message="执行完成",
                duration=0.5,
            ),
        ]

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=True,
            execution_logs=logs,
        )

        assert len(summary.execution_logs) == 2
        assert summary.execution_logs[0].node_id == "node_1"
        assert summary.execution_logs[1].duration == 0.5

    def test_execution_summary_with_errors(self):
        """测试：ExecutionSummary 包含错误信息"""
        from src.domain.agents.execution_summary import ExecutionError, ExecutionSummary

        errors = [
            ExecutionError(
                node_id="node_2",
                error_code="HTTP_TIMEOUT",
                error_message="请求超时",
                retryable=True,
            ),
        ]

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=False,
            errors=errors,
        )

        assert len(summary.errors) == 1
        assert summary.errors[0].error_code == "HTTP_TIMEOUT"
        assert summary.errors[0].retryable is True

    def test_execution_summary_with_rules_applied(self):
        """测试：ExecutionSummary 包含应用的规则"""
        from src.domain.agents.execution_summary import ExecutionSummary, RuleApplication

        rules = [
            RuleApplication(
                rule_id="rule_1",
                rule_name="安全检查",
                applied=True,
                result="通过",
            ),
            RuleApplication(
                rule_id="rule_2",
                rule_name="数据验证",
                applied=True,
                result="通过",
            ),
        ]

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=True,
            rules_applied=rules,
        )

        assert len(summary.rules_applied) == 2
        assert summary.rules_applied[0].rule_name == "安全检查"

    def test_execution_summary_with_knowledge_references(self):
        """测试：ExecutionSummary 包含知识引用"""
        from src.domain.agents.execution_summary import ExecutionSummary, KnowledgeRef

        refs = [
            KnowledgeRef(
                source_id="kb_1",
                title="销售数据分析指南",
                relevance_score=0.95,
            ),
        ]

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=True,
            knowledge_references=refs,
        )

        assert len(summary.knowledge_references) == 1
        assert summary.knowledge_references[0].title == "销售数据分析指南"

    def test_execution_summary_with_tools_used(self):
        """测试：ExecutionSummary 包含工具使用记录"""
        from src.domain.agents.execution_summary import ExecutionSummary, ToolUsage

        tools = [
            ToolUsage(
                tool_id="tool_http",
                tool_name="HTTP 请求",
                invocations=3,
                total_time=1.5,
            ),
            ToolUsage(
                tool_id="tool_llm",
                tool_name="LLM 分析",
                invocations=1,
                total_time=2.0,
            ),
        ]

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=True,
            tools_used=tools,
        )

        assert len(summary.tools_used) == 2
        assert summary.tools_used[0].invocations == 3

    def test_execution_summary_to_dict(self):
        """测试：ExecutionSummary 可序列化为字典"""
        from src.domain.agents.execution_summary import ExecutionSummary

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=True,
        )

        data = summary.to_dict()

        assert data["workflow_id"] == "wf_123"
        assert data["session_id"] == "session_1"
        assert data["success"] is True
        assert "summary_id" in data
        assert "execution_logs" in data
        assert "errors" in data
        assert "rules_applied" in data
        assert "knowledge_references" in data
        assert "tools_used" in data

    def test_execution_summary_human_readable(self):
        """测试：ExecutionSummary 可生成人类可读摘要"""
        from src.domain.agents.execution_summary import (
            ExecutionLogEntry,
            ExecutionSummary,
            ToolUsage,
        )

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=True,
            execution_logs=[
                ExecutionLogEntry(
                    node_id="node_1",
                    action="completed",
                    timestamp=datetime.now(),
                    message="完成",
                ),
            ],
            tools_used=[
                ToolUsage(tool_id="t1", tool_name="HTTP", invocations=2, total_time=1.0),
            ],
        )

        text = summary.to_human_readable()

        assert "wf_123" in text
        assert "成功" in text or "success" in text.lower()


# === 测试：ConversationAgent 生成总结 ===


class TestConversationAgentSummaryGeneration:
    """ConversationAgent 总结生成测试"""

    @pytest.mark.asyncio
    async def test_generate_summary_from_workflow_result(self):
        """测试：从工作流结果生成总结"""
        from src.domain.agents.execution_summary import (
            ExecutionSummary,
            SummaryGenerator,
        )

        # 模拟工作流执行结果
        workflow_result = {
            "workflow_id": "wf_123",
            "success": True,
            "node_results": {
                "node_1": {"success": True, "output": {"data": "result1"}},
                "node_2": {"success": True, "output": {"data": "result2"}},
            },
            "execution_time": 2.5,
        }

        generator = SummaryGenerator()
        summary = await generator.generate(
            workflow_result=workflow_result,
            session_id="session_1",
        )

        assert isinstance(summary, ExecutionSummary)
        assert summary.workflow_id == "wf_123"
        assert summary.success is True
        assert len(summary.node_results) == 2

    @pytest.mark.asyncio
    async def test_generate_summary_with_failure(self):
        """测试：从失败的工作流结果生成总结"""
        from src.domain.agents.execution_summary import (
            SummaryGenerator,
        )

        workflow_result = {
            "workflow_id": "wf_456",
            "success": False,
            "failed_node_id": "node_3",
            "error_message": "API 调用失败",
            "node_results": {
                "node_1": {"success": True, "output": {}},
                "node_2": {"success": True, "output": {}},
                "node_3": {"success": False, "error": "API 调用失败"},
            },
        }

        generator = SummaryGenerator()
        summary = await generator.generate(
            workflow_result=workflow_result,
            session_id="session_1",
        )

        assert summary.success is False
        assert len(summary.errors) >= 1
        assert "API" in summary.errors[0].error_message

    @pytest.mark.asyncio
    async def test_generate_summary_includes_rules_from_coordinator(self):
        """测试：总结包含协调者提供的规则"""
        from src.domain.agents.execution_summary import (
            SummaryGenerator,
        )

        workflow_result = {
            "workflow_id": "wf_123",
            "success": True,
            "node_results": {},
        }

        coordinator_context = {
            "rules": [
                {"id": "rule_1", "name": "安全规则", "description": "检查安全性"},
                {"id": "rule_2", "name": "数据验证", "description": "验证数据"},
            ],
        }

        generator = SummaryGenerator()
        summary = await generator.generate(
            workflow_result=workflow_result,
            session_id="session_1",
            coordinator_context=coordinator_context,
        )

        assert len(summary.rules_applied) == 2
        assert summary.rules_applied[0].rule_name == "安全规则"

    @pytest.mark.asyncio
    async def test_generate_summary_includes_knowledge_refs(self):
        """测试：总结包含知识库引用"""
        from src.domain.agents.execution_summary import (
            SummaryGenerator,
        )

        workflow_result = {
            "workflow_id": "wf_123",
            "success": True,
            "node_results": {},
        }

        coordinator_context = {
            "knowledge": [
                {
                    "source_id": "kb_1",
                    "title": "数据分析教程",
                    "relevance_score": 0.9,
                },
            ],
        }

        generator = SummaryGenerator()
        summary = await generator.generate(
            workflow_result=workflow_result,
            session_id="session_1",
            coordinator_context=coordinator_context,
        )

        assert len(summary.knowledge_references) == 1
        assert summary.knowledge_references[0].title == "数据分析教程"

    @pytest.mark.asyncio
    async def test_generate_summary_includes_tools_used(self):
        """测试：总结包含工具使用记录"""
        from src.domain.agents.execution_summary import (
            SummaryGenerator,
        )

        workflow_result = {
            "workflow_id": "wf_123",
            "success": True,
            "node_results": {
                "node_http": {"success": True, "tool_id": "http_tool", "duration": 0.5},
                "node_llm": {"success": True, "tool_id": "llm_tool", "duration": 1.0},
            },
        }

        coordinator_context = {
            "tools": [
                {"id": "http_tool", "name": "HTTP 请求工具"},
                {"id": "llm_tool", "name": "LLM 分析工具"},
            ],
        }

        generator = SummaryGenerator()
        summary = await generator.generate(
            workflow_result=workflow_result,
            session_id="session_1",
            coordinator_context=coordinator_context,
        )

        assert len(summary.tools_used) >= 1


# === 测试：Coordinator 记录总结 ===


class TestCoordinatorSummaryRecording:
    """Coordinator 总结记录测试"""

    @pytest.mark.asyncio
    async def test_coordinator_receives_summary(self):
        """测试：协调者接收执行总结"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import ExecutionSummary
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=True,
        )

        # 协调者应该能记录总结
        coordinator.record_execution_summary(summary)

        # 验证记录
        recorded = coordinator.get_execution_summary("wf_123")
        assert recorded is not None
        assert recorded.workflow_id == "wf_123"

    @pytest.mark.asyncio
    async def test_coordinator_stores_multiple_summaries(self):
        """测试：协调者存储多个工作流的总结"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import ExecutionSummary

        coordinator = CoordinatorAgent()

        summary1 = ExecutionSummary(
            workflow_id="wf_1",
            session_id="session_1",
            success=True,
        )
        summary2 = ExecutionSummary(
            workflow_id="wf_2",
            session_id="session_1",
            success=False,
        )

        coordinator.record_execution_summary(summary1)
        coordinator.record_execution_summary(summary2)

        assert coordinator.get_execution_summary("wf_1") is not None
        assert coordinator.get_execution_summary("wf_2") is not None

    @pytest.mark.asyncio
    async def test_coordinator_publishes_summary_recorded_event(self):
        """测试：协调者发布总结记录事件"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import ExecutionSummary
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        received_events = []

        async def handler(event):
            received_events.append(event)

        from src.domain.agents.execution_summary import ExecutionSummaryRecordedEvent

        event_bus.subscribe(ExecutionSummaryRecordedEvent, handler)

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=True,
        )

        await coordinator.record_execution_summary_async(summary)

        assert len(received_events) == 1
        assert received_events[0].workflow_id == "wf_123"

    @pytest.mark.asyncio
    async def test_coordinator_get_summary_statistics(self):
        """测试：协调者获取总结统计"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import ExecutionSummary

        coordinator = CoordinatorAgent()

        # 记录多个总结
        for i in range(5):
            summary = ExecutionSummary(
                workflow_id=f"wf_{i}",
                session_id="session_1",
                success=(i % 2 == 0),  # 交替成功/失败
            )
            coordinator.record_execution_summary(summary)

        stats = coordinator.get_summary_statistics()

        assert stats["total"] == 5
        assert stats["successful"] == 3  # 0, 2, 4
        assert stats["failed"] == 2  # 1, 3


# === 测试：端到端流程 ===


class TestEndToEndSummaryFlow:
    """端到端总结流程测试"""

    @pytest.mark.asyncio
    async def test_summary_contains_all_required_fields(self):
        """测试：总结包含所有必要字段（规则、知识引用、工具使用）"""
        from src.domain.agents.execution_summary import SummaryGenerator

        generator = SummaryGenerator()

        workflow_result = {
            "workflow_id": "wf_fields",
            "success": True,
            "node_results": {
                "n1": {"success": True, "tool_id": "tool_1", "duration": 0.5},
            },
        }

        coordinator_context = {
            "rules": [
                {"id": "r1", "name": "验证规则", "description": "验证输入"},
            ],
            "knowledge": [
                {"source_id": "k1", "title": "知识文档", "relevance_score": 0.85},
            ],
            "tools": [
                {"id": "tool_1", "name": "HTTP工具"},
            ],
        }

        summary = await generator.generate(
            workflow_result=workflow_result,
            session_id="session_1",
            coordinator_context=coordinator_context,
        )

        # 验证必要字段
        assert len(summary.rules_applied) >= 1
        assert len(summary.knowledge_references) >= 1
        assert len(summary.tools_used) >= 1

        # 验证可读摘要包含关键信息
        readable = summary.to_human_readable()
        assert "wf_fields" in readable


# 导出
__all__ = [
    "TestExecutionSummaryStructure",
    "TestConversationAgentSummaryGeneration",
    "TestCoordinatorSummaryRecording",
    "TestEndToEndSummaryFlow",
]
