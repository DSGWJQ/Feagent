"""强力压缩器端到端集成测试 - Phase 6

测试目标：
1. 真实场景下的压缩器工作流
2. 协调者接收总结时调用压缩器
3. 压缩结果与知识库结合
4. 对话Agent引用压缩上下文
5. 八段格式输出验证
6. 子任务错误、未解决问题、后续计划验证

运行命令：
    pytest tests/integration/test_power_compressor_e2e.py -v --tb=short
"""

from datetime import datetime

import pytest


class TestPowerCompressorE2EWorkflow:
    """强力压缩器端到端工作流测试"""

    @pytest.mark.asyncio
    async def test_full_compression_workflow(self):
        """测试完整的压缩工作流

        场景：工作流执行完成 → 生成总结 → 压缩 → 存储 → 查询
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import ExecutionError, ExecutionSummary
        from src.domain.services.event_bus import EventBus

        # 1. 创建协调者
        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 2. 创建包含错误的执行总结
        summary = ExecutionSummary(
            workflow_id="wf_e2e_001",
            session_id="session_e2e_001",
            success=False,
            errors=[
                ExecutionError(
                    node_id="node_api_call",
                    error_code="HTTP_TIMEOUT",
                    error_message="API请求超时",
                    timestamp=datetime.now(),
                    retryable=True,
                ),
            ],
        )

        # 3. 协调者压缩并存储
        compressed = await coordinator.compress_and_store(summary)

        # 4. 验证压缩结果
        assert compressed is not None
        assert compressed.workflow_id == "wf_e2e_001"
        assert compressed.session_id == "session_e2e_001"

        # 5. 查询压缩上下文
        ctx = coordinator.query_compressed_context("wf_e2e_001")
        assert ctx is not None
        assert ctx["workflow_id"] == "wf_e2e_001"

    @pytest.mark.asyncio
    async def test_subtask_errors_in_real_scenario(self):
        """测试真实场景中的子任务错误提取"""
        from src.domain.services.power_compressor import PowerCompressor

        compressor = PowerCompressor()

        # 模拟真实的子任务执行结果
        subtask_results = [
            {
                "subtask_id": "fetch_data",
                "success": True,
                "output": {"data": [1, 2, 3]},
            },
            {
                "subtask_id": "process_data",
                "success": False,
                "error": "内存不足",
                "error_type": "RESOURCE_EXHAUSTED",
                "retryable": False,
            },
            {
                "subtask_id": "validate_result",
                "success": False,
                "error": "验证超时",
                "error_type": "TIMEOUT",
                "retryable": True,
            },
        ]

        result = compressor.compress_subtask_results(
            workflow_id="wf_real_001",
            session_id="session_real_001",
            subtask_results=subtask_results,
        )

        # 验证错误提取
        assert len(result.subtask_errors) == 2
        error_types = [e.error_type for e in result.subtask_errors]
        assert "RESOURCE_EXHAUSTED" in error_types
        assert "TIMEOUT" in error_types

        # 验证可重试状态
        retryable = [e for e in result.subtask_errors if e.retryable]
        assert len(retryable) == 1
        assert retryable[0].error_type == "TIMEOUT"

    @pytest.mark.asyncio
    async def test_unresolved_issues_extraction(self):
        """测试未解决问题提取"""
        from src.domain.services.power_compressor import PowerCompressor

        compressor = PowerCompressor()

        # 模拟执行数据
        execution_data = {
            "workflow_id": "wf_issues_001",
            "session_id": "session_issues_001",
            "failed_nodes": ["node_3", "node_5"],
            "blocking_issues": [
                {
                    "description": "外部API服务不可用",
                    "severity": "critical",
                    "blocked_nodes": ["node_3", "node_4"],
                    "suggested_actions": ["切换备用API", "延迟重试"],
                },
                {
                    "description": "数据格式不兼容",
                    "severity": "high",
                    "blocked_nodes": ["node_5"],
                    "suggested_actions": ["添加格式转换"],
                },
            ],
            "pending_validations": [
                "结果完整性检查",
                "数据一致性验证",
            ],
        }

        issues = compressor.extract_unresolved_issues(execution_data)

        # 验证问题提取
        assert len(issues) >= 4  # 2个阻塞问题 + 2个待验证

        # 验证严重程度
        critical_issues = [i for i in issues if i.severity == "critical"]
        assert len(critical_issues) >= 1

        # 验证建议操作
        has_suggestions = any(len(i.suggested_actions) > 0 for i in issues)
        assert has_suggestions

    @pytest.mark.asyncio
    async def test_next_plan_generation(self):
        """测试后续计划生成"""
        from src.domain.services.power_compressor import PowerCompressor

        compressor = PowerCompressor()

        # 模拟上下文
        context = {
            "workflow_id": "wf_plan_001",
            "unresolved_issues": [
                {
                    "description": "数据验证失败",
                    "suggested_actions": ["重新验证", "修正数据"],
                },
            ],
            "pending_nodes": ["node_6", "node_7"],
            "reflection_recommendations": [
                "优化缓存策略",
                "增加错误重试",
            ],
        }

        plans = compressor.generate_next_plan(context)

        # 验证计划生成
        assert len(plans) >= 4  # 至少：2个建议操作 + 2个待执行节点

        # 验证优先级
        priorities = [p.priority for p in plans]
        assert priorities == sorted(priorities)  # 优先级应该有序

        # 验证包含不同类型的计划
        actions = [p.action for p in plans]
        assert any("验证" in a for a in actions)
        assert any("node" in a for a in actions)

    @pytest.mark.asyncio
    async def test_knowledge_integration_workflow(self):
        """测试知识库集成工作流"""
        from src.domain.services.power_compressor import (
            PowerCompressedContext,
            PowerCompressor,
            SubtaskError,
        )

        compressor = PowerCompressor()

        # 创建带错误的上下文
        ctx = PowerCompressedContext(
            workflow_id="wf_kb_001",
            session_id="session_kb_001",
            task_goal="分析用户行为数据",
            subtask_errors=[
                SubtaskError(
                    subtask_id="sub_1",
                    error_type="HTTP_TIMEOUT",
                    error_message="请求超时",
                    occurred_at=datetime.now(),
                    retryable=True,
                ),
            ],
        )

        # 模拟知识库数据
        knowledge = [
            {
                "source_id": "kb_timeout",
                "title": "超时处理最佳实践",
                "source_type": "knowledge_base",
                "relevance_score": 0.95,
            },
            {
                "source_id": "kb_behavior",
                "title": "用户行为分析方法",
                "source_type": "knowledge_base",
                "relevance_score": 0.88,
            },
        ]

        # 链接知识到段
        result = compressor.link_knowledge_to_segments(ctx, knowledge)

        # 验证知识链接
        assert len(result.knowledge_sources) == 2

        # 验证知识应用到正确的段
        timeout_kb = next((k for k in result.knowledge_sources if "超时" in k.title), None)
        assert timeout_kb is not None
        assert "subtask_errors" in timeout_kb.applied_to_segments

    @pytest.mark.asyncio
    async def test_coordinator_query_interface_e2e(self):
        """测试协调者查询接口端到端"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 存储完整的压缩上下文
        compressed_data = {
            "workflow_id": "wf_query_001",
            "task_goal": "生成销售报告",
            "execution_status": {"status": "partial", "progress": 0.7},
            "node_summary": [
                {"node_id": "fetch", "status": "completed"},
                {"node_id": "process", "status": "failed"},
                {"node_id": "report", "status": "pending"},
            ],
            "subtask_errors": [
                {
                    "subtask_id": "process",
                    "error_type": "DATA_ERROR",
                    "error_message": "数据格式错误",
                },
            ],
            "unresolved_issues": [
                {
                    "issue_id": "i1",
                    "description": "数据源不稳定",
                    "severity": "high",
                },
            ],
            "decision_history": [
                {"decision": "使用缓存数据", "reason": "主数据源超时"},
            ],
            "next_plan": [
                {"action": "修复数据格式", "priority": 1},
                {"action": "重新处理", "priority": 2},
            ],
            "knowledge_sources": [
                {
                    "source_id": "kb_sales",
                    "title": "销售报告模板",
                    "content_preview": "本文档介绍销售报告的标准格式...",
                },
            ],
        }

        coordinator.store_compressed_context("wf_query_001", compressed_data)

        # 测试各查询接口
        errors = coordinator.query_subtask_errors("wf_query_001")
        assert len(errors) == 1
        assert errors[0]["error_type"] == "DATA_ERROR"

        issues = coordinator.query_unresolved_issues("wf_query_001")
        assert len(issues) == 1
        assert issues[0]["severity"] == "high"

        plans = coordinator.query_next_plan("wf_query_001")
        assert len(plans) == 2
        assert plans[0]["priority"] == 1

        # 测试对话Agent上下文获取
        ctx = coordinator.get_context_for_conversation("wf_query_001")
        assert ctx is not None
        assert ctx["task_goal"] == "生成销售报告"
        assert "subtask_errors" in ctx
        assert "unresolved_issues" in ctx
        assert "next_plan" in ctx
        assert "knowledge_sources" in ctx

        # 测试知识获取
        knowledge = coordinator.get_knowledge_for_conversation("wf_query_001")
        assert len(knowledge) == 1
        assert knowledge[0]["title"] == "销售报告模板"

    @pytest.mark.asyncio
    async def test_eight_segment_summary_output(self):
        """测试八段摘要输出格式"""
        from src.domain.services.power_compressor import (
            KnowledgeSource,
            NextPlanItem,
            PowerCompressedContext,
            SubtaskError,
            UnresolvedIssue,
        )

        # 创建完整的八段上下文
        ctx = PowerCompressedContext(
            workflow_id="wf_summary_001",
            session_id="session_summary_001",
            task_goal="自动化测试数据分析流程",
            execution_status={"status": "partial", "progress": 0.65},
            node_summary=[
                {"node_id": "data_fetch", "status": "completed"},
                {"node_id": "data_clean", "status": "completed"},
                {"node_id": "data_analyze", "status": "failed"},
                {"node_id": "report_gen", "status": "pending"},
            ],
            subtask_errors=[
                SubtaskError(
                    subtask_id="data_analyze",
                    error_type="ANALYSIS_ERROR",
                    error_message="分析算法执行失败",
                    occurred_at=datetime.now(),
                    retryable=True,
                    source_document={"title": "算法错误处理指南"},
                ),
            ],
            unresolved_issues=[
                UnresolvedIssue(
                    issue_id="i1",
                    description="输入数据质量不足",
                    severity="high",
                    blocked_nodes=["data_analyze", "report_gen"],
                    suggested_actions=["增加数据清洗步骤", "添加数据验证"],
                ),
            ],
            decision_history=[
                {"decision": "跳过异常数据", "reason": "异常数据占比小于5%"},
                {"decision": "使用简化算法", "reason": "完整算法超时"},
            ],
            next_plan=[
                NextPlanItem(
                    action="修复分析算法",
                    priority=1,
                    rationale="核心功能必须正常",
                    estimated_effort="medium",
                ),
                NextPlanItem(
                    action="补充数据验证",
                    priority=2,
                    rationale="提高数据质量",
                    estimated_effort="low",
                ),
            ],
            knowledge_sources=[
                KnowledgeSource(
                    source_id="kb_analysis",
                    title="数据分析最佳实践",
                    source_type="knowledge_base",
                    relevance_score=0.92,
                    applied_to_segments=["task_goal", "next_plan"],
                ),
            ],
        )

        # 生成八段摘要
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
        assert "自动化测试数据分析流程" in summary
        assert "65%" in summary  # 进度
        assert "ANALYSIS_ERROR" in summary
        assert "数据质量不足" in summary
        assert "跳过异常数据" in summary
        assert "修复分析算法" in summary
        assert "数据分析最佳实践" in summary

    @pytest.mark.asyncio
    async def test_conversation_agent_context_reference(self):
        """测试对话Agent引用压缩上下文的真实场景"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.agents.execution_summary import ExecutionError, ExecutionSummary
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 模拟第一轮执行：部分失败
        summary_round1 = ExecutionSummary(
            workflow_id="wf_conv_001",
            session_id="session_conv_001",
            success=False,
            errors=[
                ExecutionError(
                    node_id="api_call",
                    error_code="HTTP_ERROR",
                    error_message="API返回500错误",
                    timestamp=datetime.now(),
                    retryable=True,
                ),
            ],
        )

        # 压缩并存储
        await coordinator.compress_and_store(summary_round1)

        # 补充更多上下文信息
        coordinator.store_compressed_context(
            "wf_conv_001",
            {
                "workflow_id": "wf_conv_001",
                "task_goal": "获取用户数据并生成报告",
                "execution_status": {"status": "failed", "progress": 0.5},
                "subtask_errors": [
                    {
                        "subtask_id": "api_call",
                        "error_type": "HTTP_ERROR",
                        "error_message": "API返回500错误",
                    }
                ],
                "unresolved_issues": [
                    {
                        "issue_id": "api_issue",
                        "description": "API服务不稳定",
                        "severity": "high",
                    }
                ],
                "next_plan": [
                    {"action": "重试API调用", "priority": 1},
                    {"action": "启用备用数据源", "priority": 2},
                ],
                "knowledge_sources": [
                    {
                        "source_id": "kb_api",
                        "title": "API错误处理指南",
                        "content_preview": "当API返回5xx错误时...",
                    }
                ],
            },
        )

        # 模拟对话Agent获取下一轮输入的上下文
        context = coordinator.get_context_for_conversation("wf_conv_001")

        # 验证对话Agent可以获取完整上下文
        assert context is not None
        assert context["task_goal"] == "获取用户数据并生成报告"

        # 验证可以获取错误信息用于理解问题
        assert len(context["subtask_errors"]) == 1
        assert context["subtask_errors"][0]["error_type"] == "HTTP_ERROR"

        # 验证可以获取未解决问题用于决策
        assert len(context["unresolved_issues"]) == 1
        assert context["unresolved_issues"][0]["severity"] == "high"

        # 验证可以获取后续计划用于执行
        assert len(context["next_plan"]) == 2
        assert context["next_plan"][0]["action"] == "重试API调用"

        # 验证可以获取知识引用用于辅助决策
        knowledge = coordinator.get_knowledge_for_conversation("wf_conv_001")
        assert len(knowledge) == 1
        assert "API错误处理" in knowledge[0]["title"]


class TestPowerCompressorStatistics:
    """压缩器统计测试"""

    @pytest.mark.asyncio
    async def test_compression_statistics(self):
        """测试压缩统计功能"""
        from src.domain.agents.coordinator_agent import CoordinatorAgent
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        coordinator = CoordinatorAgent(event_bus=event_bus)

        # 存储多个压缩上下文
        coordinator.store_compressed_context(
            "wf_stat_001",
            {
                "workflow_id": "wf_stat_001",
                "subtask_errors": [{"error_type": "E1"}, {"error_type": "E2"}],
                "unresolved_issues": [{"issue_id": "i1"}],
                "next_plan": [{"action": "a1"}],
            },
        )

        coordinator.store_compressed_context(
            "wf_stat_002",
            {
                "workflow_id": "wf_stat_002",
                "subtask_errors": [{"error_type": "E3"}],
                "unresolved_issues": [{"issue_id": "i2"}, {"issue_id": "i3"}],
                "next_plan": [{"action": "a2"}, {"action": "a3"}],
            },
        )

        # 获取统计
        stats = coordinator.get_power_compression_statistics()

        assert stats["total_contexts"] == 2
        assert stats["total_subtask_errors"] == 3
        assert stats["total_unresolved_issues"] == 3
        assert stats["total_next_plan_items"] == 3


# 导出
__all__ = [
    "TestPowerCompressorE2EWorkflow",
    "TestPowerCompressorStatistics",
]
