"""强力压缩器单元测试 - Phase 6

测试目标：
1. PowerCompressor 八段压缩格式
2. 子任务错误提取
3. 未解决问题提取
4. 后续计划生成
5. 知识来源引用集成
6. 协调者查询接口

运行命令：
    pytest tests/unit/domain/services/test_power_compressor.py -v --tb=short
"""

from datetime import datetime

import pytest

# === 测试：PowerCompressedContext 数据结构 ===


class TestPowerCompressedContextStructure:
    """PowerCompressedContext 数据结构测试"""

    def test_power_compressed_context_has_eight_segments(self):
        """测试：PowerCompressedContext 包含八段结构"""
        from src.domain.services.power_compressor import PowerCompressedContext

        ctx = PowerCompressedContext(
            workflow_id="wf_123",
            session_id="session_1",
        )

        # 验证八段字段
        assert hasattr(ctx, "task_goal")
        assert hasattr(ctx, "execution_status")
        assert hasattr(ctx, "node_summary")
        assert hasattr(ctx, "subtask_errors")
        assert hasattr(ctx, "unresolved_issues")
        assert hasattr(ctx, "decision_history")
        assert hasattr(ctx, "next_plan")
        assert hasattr(ctx, "knowledge_sources")

    def test_subtask_errors_segment(self):
        """测试：子任务错误段"""
        from src.domain.services.power_compressor import (
            PowerCompressedContext,
            SubtaskError,
        )

        errors = [
            SubtaskError(
                subtask_id="sub_1",
                error_type="TIMEOUT",
                error_message="请求超时",
                occurred_at=datetime.now(),
                retryable=True,
                source_document={"doc_id": "doc_1", "title": "超时处理指南"},
            ),
        ]

        ctx = PowerCompressedContext(
            workflow_id="wf_123",
            session_id="session_1",
            subtask_errors=errors,
        )

        assert len(ctx.subtask_errors) == 1
        assert ctx.subtask_errors[0].error_type == "TIMEOUT"
        assert ctx.subtask_errors[0].source_document["doc_id"] == "doc_1"

    def test_unresolved_issues_segment(self):
        """测试：未解决问题段"""
        from src.domain.services.power_compressor import (
            PowerCompressedContext,
            UnresolvedIssue,
        )

        issues = [
            UnresolvedIssue(
                issue_id="issue_1",
                description="数据格式不一致",
                severity="high",
                blocked_nodes=["node_3", "node_4"],
                suggested_actions=["添加数据校验", "统一格式"],
                related_knowledge={"doc_id": "doc_2", "title": "数据格式规范"},
            ),
        ]

        ctx = PowerCompressedContext(
            workflow_id="wf_123",
            session_id="session_1",
            unresolved_issues=issues,
        )

        assert len(ctx.unresolved_issues) == 1
        assert ctx.unresolved_issues[0].severity == "high"
        assert "node_3" in ctx.unresolved_issues[0].blocked_nodes

    def test_next_plan_segment(self):
        """测试：后续计划段"""
        from src.domain.services.power_compressor import (
            NextPlanItem,
            PowerCompressedContext,
        )

        plans = [
            NextPlanItem(
                action="重试失败的节点",
                priority=1,
                rationale="节点超时可重试",
                estimated_effort="low",
                dependencies=[],
                knowledge_ref={"doc_id": "doc_3", "title": "重试策略"},
            ),
            NextPlanItem(
                action="验证最终结果",
                priority=2,
                rationale="确保输出正确",
                estimated_effort="medium",
                dependencies=["重试失败的节点"],
            ),
        ]

        ctx = PowerCompressedContext(
            workflow_id="wf_123",
            session_id="session_1",
            next_plan=plans,
        )

        assert len(ctx.next_plan) == 2
        assert ctx.next_plan[0].priority == 1
        assert ctx.next_plan[1].dependencies == ["重试失败的节点"]

    def test_knowledge_sources_segment(self):
        """测试：知识来源段"""
        from src.domain.services.power_compressor import (
            KnowledgeSource,
            PowerCompressedContext,
        )

        sources = [
            KnowledgeSource(
                source_id="kb_1",
                title="销售数据分析指南",
                source_type="knowledge_base",
                relevance_score=0.95,
                applied_to_segments=["task_goal", "next_plan"],
                content_preview="本文档介绍销售数据分析方法...",
            ),
        ]

        ctx = PowerCompressedContext(
            workflow_id="wf_123",
            session_id="session_1",
            knowledge_sources=sources,
        )

        assert len(ctx.knowledge_sources) == 1
        assert ctx.knowledge_sources[0].relevance_score == 0.95
        assert "task_goal" in ctx.knowledge_sources[0].applied_to_segments

    def test_to_dict_serialization(self):
        """测试：序列化为字典"""
        from src.domain.services.power_compressor import PowerCompressedContext

        ctx = PowerCompressedContext(
            workflow_id="wf_123",
            session_id="session_1",
            task_goal="分析销售数据",
        )

        data = ctx.to_dict()

        assert data["workflow_id"] == "wf_123"
        assert data["task_goal"] == "分析销售数据"
        assert "subtask_errors" in data
        assert "unresolved_issues" in data
        assert "next_plan" in data
        assert "knowledge_sources" in data


# === 测试：PowerCompressor 核心功能 ===


class TestPowerCompressorCore:
    """PowerCompressor 核心功能测试"""

    def test_compress_execution_summary(self):
        """测试：压缩执行总结"""
        from src.domain.agents.execution_summary import ExecutionSummary
        from src.domain.services.power_compressor import PowerCompressor

        compressor = PowerCompressor()

        summary = ExecutionSummary(
            workflow_id="wf_123",
            session_id="session_1",
            success=False,
        )

        result = compressor.compress_summary(summary)

        assert result.workflow_id == "wf_123"
        assert result.session_id == "session_1"

    def test_compress_subtask_results(self):
        """测试：压缩子任务结果"""
        from src.domain.services.power_compressor import PowerCompressor

        compressor = PowerCompressor()

        subtask_results = [
            {
                "subtask_id": "sub_1",
                "success": True,
                "output": {"data": "result1"},
            },
            {
                "subtask_id": "sub_2",
                "success": False,
                "error": "连接超时",
                "error_type": "TIMEOUT",
                "retryable": True,
            },
        ]

        result = compressor.compress_subtask_results(
            workflow_id="wf_123",
            session_id="session_1",
            subtask_results=subtask_results,
        )

        assert len(result.subtask_errors) == 1
        assert result.subtask_errors[0].subtask_id == "sub_2"
        assert result.subtask_errors[0].error_type == "TIMEOUT"

    def test_extract_unresolved_issues(self):
        """测试：提取未解决问题"""
        from src.domain.services.power_compressor import PowerCompressor

        compressor = PowerCompressor()

        execution_data = {
            "workflow_id": "wf_123",
            "session_id": "session_1",
            "failed_nodes": ["node_2"],
            "blocking_issues": [
                {
                    "description": "外部 API 不可用",
                    "severity": "critical",
                    "blocked_nodes": ["node_2", "node_3"],
                },
            ],
            "pending_validations": ["数据完整性检查"],
        }

        result = compressor.extract_unresolved_issues(execution_data)

        assert len(result) >= 1
        assert any(i.severity == "critical" for i in result)

    def test_generate_next_plan(self):
        """测试：生成后续计划"""
        from src.domain.services.power_compressor import PowerCompressor

        compressor = PowerCompressor()

        context = {
            "workflow_id": "wf_123",
            "unresolved_issues": [
                {"description": "数据验证失败", "suggested_actions": ["重新验证"]},
            ],
            "pending_nodes": ["node_4", "node_5"],
            "reflection_recommendations": ["优化缓存策略"],
        }

        plans = compressor.generate_next_plan(context)

        assert len(plans) >= 1
        # 应该包含处理未解决问题的计划
        assert any("验证" in p.action or "node" in p.action for p in plans)

    def test_attach_knowledge_sources(self):
        """测试：附加知识来源"""
        from src.domain.services.power_compressor import (
            PowerCompressedContext,
            PowerCompressor,
        )

        compressor = PowerCompressor()

        ctx = PowerCompressedContext(
            workflow_id="wf_123",
            session_id="session_1",
            task_goal="分析销售数据",
            subtask_errors=[],
        )

        knowledge_context = {
            "knowledge": [
                {
                    "source_id": "kb_1",
                    "title": "销售分析指南",
                    "relevance_score": 0.9,
                },
            ],
            "rules": [
                {"id": "rule_1", "name": "数据验证规则"},
            ],
        }

        result = compressor.attach_knowledge_sources(ctx, knowledge_context)

        assert len(result.knowledge_sources) >= 1
        assert result.knowledge_sources[0].title == "销售分析指南"


# === 测试：协调者集成 ===


class TestCoordinatorIntegration:
    """协调者集成测试"""

    @pytest.mark.asyncio
    async def test_coordinator_calls_compressor_on_summary(self):
        """测试：协调者接收总结时调用压缩器"""
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

        # 协调者应该提供压缩方法
        compressed = await coordinator.compress_and_store(summary)

        assert compressed is not None
        assert compressed.workflow_id == "wf_123"

    @pytest.mark.asyncio
    async def test_coordinator_provides_query_interface(self):
        """测试：协调者提供查询接口"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 存储一些压缩数据
        mock_data = {
            "workflow_id": "wf_123",
            "task_goal": "测试任务",
            "subtask_errors": [],
            "unresolved_issues": [{"description": "问题1"}],
        }
        coordinator.store_compressed_context("wf_123", mock_data)

        # 查询接口
        result = coordinator.query_compressed_context("wf_123")

        assert result is not None
        assert result["workflow_id"] == "wf_123"

    @pytest.mark.asyncio
    async def test_coordinator_query_subtask_errors(self):
        """测试：查询子任务错误"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        mock_data = {
            "workflow_id": "wf_123",
            "subtask_errors": [
                {"subtask_id": "sub_1", "error_type": "TIMEOUT"},
                {"subtask_id": "sub_2", "error_type": "VALIDATION"},
            ],
        }
        coordinator.store_compressed_context("wf_123", mock_data)

        errors = coordinator.query_subtask_errors("wf_123")

        assert len(errors) == 2
        assert errors[0]["error_type"] == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_coordinator_query_unresolved_issues(self):
        """测试：查询未解决问题"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        mock_data = {
            "workflow_id": "wf_123",
            "unresolved_issues": [
                {"issue_id": "i1", "description": "API 不可用", "severity": "high"},
            ],
        }
        coordinator.store_compressed_context("wf_123", mock_data)

        issues = coordinator.query_unresolved_issues("wf_123")

        assert len(issues) == 1
        assert issues[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_coordinator_query_next_plan(self):
        """测试：查询后续计划"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        mock_data = {
            "workflow_id": "wf_123",
            "next_plan": [
                {"action": "重试节点", "priority": 1},
                {"action": "验证结果", "priority": 2},
            ],
        }
        coordinator.store_compressed_context("wf_123", mock_data)

        plans = coordinator.query_next_plan("wf_123")

        assert len(plans) == 2
        assert plans[0]["priority"] == 1


# === 测试：知识库集成 ===


class TestKnowledgeIntegration:
    """知识库集成测试"""

    def test_knowledge_source_links_to_segments(self):
        """测试：知识来源链接到各段"""
        from src.domain.services.power_compressor import (
            PowerCompressedContext,
            PowerCompressor,
        )

        compressor = PowerCompressor()

        ctx = PowerCompressedContext(
            workflow_id="wf_123",
            session_id="session_1",
            task_goal="分析用户行为",
            subtask_errors=[],
            unresolved_issues=[],
            next_plan=[],
        )

        knowledge = [
            {
                "source_id": "kb_behavior",
                "title": "用户行为分析方法论",
                "relevance_score": 0.95,
                "source_type": "knowledge_base",
            },
        ]

        result = compressor.link_knowledge_to_segments(ctx, knowledge)

        assert len(result.knowledge_sources) >= 1
        # 知识应该链接到相关段
        linked = result.knowledge_sources[0]
        assert "task_goal" in linked.applied_to_segments

    def test_error_knowledge_attached_to_subtask_errors(self):
        """测试：错误知识附加到子任务错误"""
        from src.domain.services.power_compressor import (
            PowerCompressor,
            SubtaskError,
        )

        compressor = PowerCompressor()

        error = SubtaskError(
            subtask_id="sub_1",
            error_type="HTTP_TIMEOUT",
            error_message="请求超时",
            occurred_at=datetime.now(),
            retryable=True,
        )

        error_knowledge = [
            {
                "error_type": "HTTP_TIMEOUT",
                "solution_title": "HTTP超时处理指南",
                "solution_preview": "当遇到HTTP超时时...",
                "confidence": 0.9,
            },
        ]

        enriched = compressor.enrich_error_with_knowledge(error, error_knowledge)

        assert enriched.source_document is not None
        assert enriched.source_document["title"] == "HTTP超时处理指南"

    def test_issue_knowledge_attached_to_unresolved_issues(self):
        """测试：问题知识附加到未解决问题"""
        from src.domain.services.power_compressor import (
            PowerCompressor,
            UnresolvedIssue,
        )

        compressor = PowerCompressor()

        issue = UnresolvedIssue(
            issue_id="issue_1",
            description="数据格式不一致",
            severity="high",
            blocked_nodes=["node_3"],
            suggested_actions=["添加格式校验"],
        )

        knowledge = [
            {
                "source_id": "kb_format",
                "title": "数据格式规范",
                "relevance_score": 0.88,
            },
        ]

        enriched = compressor.enrich_issue_with_knowledge(issue, knowledge)

        assert enriched.related_knowledge is not None
        assert enriched.related_knowledge["title"] == "数据格式规范"


# === 测试：摘要生成 ===


class TestSummaryGeneration:
    """摘要生成测试"""

    def test_generate_eight_segment_summary(self):
        """测试：生成八段格式摘要"""
        from src.domain.services.power_compressor import (
            KnowledgeSource,
            NextPlanItem,
            PowerCompressedContext,
            SubtaskError,
            UnresolvedIssue,
        )

        ctx = PowerCompressedContext(
            workflow_id="wf_123",
            session_id="session_1",
            task_goal="分析销售数据并生成报告",
            execution_status={"status": "partial", "progress": 0.6},
            node_summary=[
                {"node_id": "n1", "status": "completed"},
                {"node_id": "n2", "status": "failed"},
            ],
            subtask_errors=[
                SubtaskError(
                    subtask_id="sub_1",
                    error_type="TIMEOUT",
                    error_message="API超时",
                    occurred_at=datetime.now(),
                    retryable=True,
                ),
            ],
            unresolved_issues=[
                UnresolvedIssue(
                    issue_id="i1",
                    description="数据不完整",
                    severity="medium",
                    blocked_nodes=["n3"],
                    suggested_actions=["补充数据"],
                ),
            ],
            decision_history=[
                {"decision": "使用备用API", "reason": "主API不可用"},
            ],
            next_plan=[
                NextPlanItem(
                    action="重试超时请求",
                    priority=1,
                    rationale="可重试错误",
                    estimated_effort="low",
                ),
            ],
            knowledge_sources=[
                KnowledgeSource(
                    source_id="kb_1",
                    title="销售分析指南",
                    source_type="knowledge_base",
                    relevance_score=0.9,
                    applied_to_segments=["task_goal"],
                ),
            ],
        )

        summary = ctx.to_eight_segment_summary()

        # 验证八段都存在
        assert "[1.任务目标]" in summary
        assert "[2.执行状态]" in summary
        assert "[3.节点摘要]" in summary
        assert "[4.子任务错误]" in summary
        assert "[5.未解决问题]" in summary
        assert "[6.决策历史]" in summary
        assert "[7.后续计划]" in summary
        assert "[8.知识来源]" in summary

        # 验证内容
        assert "分析销售数据" in summary
        assert "TIMEOUT" in summary
        assert "数据不完整" in summary

    def test_summary_contains_required_fields(self):
        """测试：摘要包含必要字段"""
        from src.domain.services.power_compressor import (
            NextPlanItem,
            PowerCompressedContext,
            SubtaskError,
            UnresolvedIssue,
        )

        ctx = PowerCompressedContext(
            workflow_id="wf_test",
            session_id="session_test",
            subtask_errors=[
                SubtaskError(
                    subtask_id="s1",
                    error_type="ERR",
                    error_message="错误信息",
                    occurred_at=datetime.now(),
                    retryable=False,
                ),
            ],
            unresolved_issues=[
                UnresolvedIssue(
                    issue_id="i1",
                    description="未解决的问题",
                    severity="high",
                    blocked_nodes=[],
                    suggested_actions=[],
                ),
            ],
            next_plan=[
                NextPlanItem(
                    action="后续计划",
                    priority=1,
                    rationale="原因",
                    estimated_effort="medium",
                ),
            ],
        )

        summary = ctx.to_eight_segment_summary()

        # 必须包含：子任务错误、未解决问题、后续计划
        assert "错误信息" in summary
        assert "未解决的问题" in summary
        assert "后续计划" in summary


# === 测试：对话 Agent 可引用 ===


class TestConversationAgentUsage:
    """对话 Agent 使用测试"""

    @pytest.mark.asyncio
    async def test_conversation_agent_can_reference_compressed_context(self):
        """测试：对话 Agent 可引用压缩上下文"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 存储压缩上下文
        compressed_data = {
            "workflow_id": "wf_123",
            "task_goal": "分析数据",
            "subtask_errors": [
                {"subtask_id": "s1", "error_type": "ERR", "error_message": "出错了"},
            ],
            "unresolved_issues": [
                {"issue_id": "i1", "description": "问题", "severity": "low"},
            ],
            "next_plan": [
                {"action": "下一步", "priority": 1},
            ],
            "knowledge_sources": [
                {"source_id": "k1", "title": "知识文档"},
            ],
        }
        coordinator.store_compressed_context("wf_123", compressed_data)

        # 对话 Agent 获取下一轮输入的上下文
        context_for_next_round = coordinator.get_context_for_conversation(workflow_id="wf_123")

        assert context_for_next_round is not None
        assert "task_goal" in context_for_next_round
        assert "subtask_errors" in context_for_next_round
        assert "next_plan" in context_for_next_round
        assert "knowledge_sources" in context_for_next_round

    @pytest.mark.asyncio
    async def test_context_includes_knowledge_for_reference(self):
        """测试：上下文包含可引用的知识"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        compressed_data = {
            "workflow_id": "wf_123",
            "knowledge_sources": [
                {
                    "source_id": "kb_1",
                    "title": "分析方法论",
                    "content_preview": "本文介绍数据分析方法...",
                    "applied_to_segments": ["task_goal", "next_plan"],
                },
            ],
        }
        coordinator.store_compressed_context("wf_123", compressed_data)

        knowledge = coordinator.get_knowledge_for_conversation("wf_123")

        assert len(knowledge) >= 1
        assert knowledge[0]["title"] == "分析方法论"
        assert "content_preview" in knowledge[0]


# 导出
__all__ = [
    "TestPowerCompressedContextStructure",
    "TestPowerCompressorCore",
    "TestCoordinatorIntegration",
    "TestKnowledgeIntegration",
    "TestSummaryGeneration",
    "TestConversationAgentUsage",
]
