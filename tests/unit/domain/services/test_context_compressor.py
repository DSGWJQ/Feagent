"""阶段2测试：上下文压缩与传递 - 八段压缩模块

测试目标：
1. 实现"八段压缩"模块，将复杂对话/执行日志压缩成结构化摘要
2. 验证八段结构的完整性和数据一致性
3. 测试 Coordinator 调用压缩器更新上下文快照的流程

八段结构定义：
1. TaskGoal - 任务目标段：当前工作流的目标
2. ExecutionStatus - 执行状态段：当前执行进度
3. NodeSummary - 节点摘要段：已执行节点的关键信息
4. DecisionHistory - 决策历史段：重要决策记录
5. ReflectionSummary - 反思结果段：反思的关键发现
6. ConversationSummary - 对话摘要段：对话的核心内容
7. ErrorLog - 错误记录段：发生的错误和处理情况
8. NextActions - 下一步建议段：推荐的后续行动

完成标准：
- 八段结构完整，每段有明确的数据模型
- 压缩器能正确处理各类输入数据
- Coordinator 能正确调用压缩器并更新快照
- 支持增量更新和全量重建
"""

from datetime import datetime

import pytest

# ==================== 测试1：八段压缩数据结构 ====================


class TestEightSegmentDataStructures:
    """测试八段压缩的数据结构"""

    def test_compressed_context_has_eight_segments(self):
        """压缩上下文应包含完整的八个段落"""
        from src.domain.services.context_compressor import CompressedContext

        context = CompressedContext(
            workflow_id="wf_001",
            task_goal="创建数据分析工作流",
            execution_status={"status": "running", "progress": 0.5},
            node_summary=[{"node_id": "n1", "summary": "LLM分析完成"}],
            decision_history=[{"decision": "使用GPT-4", "reason": "更准确"}],
            reflection_summary={"assessment": "执行顺利", "confidence": 0.9},
            conversation_summary="用户要求分析销售数据",
            error_log=[],
            next_actions=["执行下一个节点", "验证结果"],
        )

        # 验证八段都存在
        assert context.task_goal is not None
        assert context.execution_status is not None
        assert context.node_summary is not None
        assert context.decision_history is not None
        assert context.reflection_summary is not None
        assert context.conversation_summary is not None
        assert context.error_log is not None
        assert context.next_actions is not None

    def test_compressed_context_has_metadata(self):
        """压缩上下文应包含元数据：workflow_id, created_at, version"""
        from src.domain.services.context_compressor import CompressedContext

        context = CompressedContext(workflow_id="wf_001")

        assert context.workflow_id == "wf_001"
        assert context.created_at is not None
        assert isinstance(context.created_at, datetime)
        assert context.version >= 1

    def test_segment_types_are_correct(self):
        """各段的数据类型应正确"""
        from src.domain.services.context_compressor import CompressedContext

        context = CompressedContext(
            workflow_id="wf_001",
            task_goal="目标描述",
            execution_status={"status": "running"},
            node_summary=[{"node_id": "n1"}],
            decision_history=[{"decision": "d1"}],
            reflection_summary={"assessment": "良好"},
            conversation_summary="对话摘要",
            error_log=[{"error": "e1"}],
            next_actions=["action1", "action2"],
        )

        # 类型检查
        assert isinstance(context.task_goal, str)
        assert isinstance(context.execution_status, dict)
        assert isinstance(context.node_summary, list)
        assert isinstance(context.decision_history, list)
        assert isinstance(context.reflection_summary, dict)
        assert isinstance(context.conversation_summary, str)
        assert isinstance(context.error_log, list)
        assert isinstance(context.next_actions, list)


# ==================== 测试2：压缩输入数据结构 ====================


class TestCompressionInputStructures:
    """测试压缩输入的数据结构"""

    def test_compression_input_from_conversation_log(self):
        """压缩输入：从对话日志创建"""
        from src.domain.services.context_compressor import CompressionInput

        input_data = CompressionInput(
            source_type="conversation",
            workflow_id="wf_001",
            raw_data={
                "messages": [
                    {"role": "user", "content": "分析销售数据"},
                    {"role": "assistant", "content": "好的，我来分析"},
                ],
                "session_id": "session_123",
            },
        )

        assert input_data.source_type == "conversation"
        assert input_data.workflow_id == "wf_001"
        assert "messages" in input_data.raw_data

    def test_compression_input_from_execution_log(self):
        """压缩输入：从执行日志创建"""
        from src.domain.services.context_compressor import CompressionInput

        input_data = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={
                "nodes_executed": ["n1", "n2"],
                "node_outputs": {
                    "n1": {"result": "success"},
                    "n2": {"result": "pending"},
                },
                "errors": [],
            },
        )

        assert input_data.source_type == "execution"
        assert "nodes_executed" in input_data.raw_data

    def test_compression_input_from_reflection(self):
        """压缩输入：从反思结果创建"""
        from src.domain.services.context_compressor import CompressionInput

        input_data = CompressionInput(
            source_type="reflection",
            workflow_id="wf_001",
            raw_data={
                "assessment": "执行过程中发现数据格式问题",
                "issues": ["数据格式不一致"],
                "recommendations": ["添加数据校验节点"],
                "confidence": 0.85,
                "should_retry": False,
            },
        )

        assert input_data.source_type == "reflection"
        assert input_data.raw_data["confidence"] == 0.85


# ==================== 测试3：上下文压缩器核心功能 ====================


class TestContextCompressorCore:
    """测试上下文压缩器核心功能"""

    def test_compress_empty_input_returns_minimal_context(self):
        """压缩空输入应返回最小上下文"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        input_data = CompressionInput(
            source_type="conversation",
            workflow_id="wf_001",
            raw_data={},
        )

        result = compressor.compress(input_data)

        assert result.workflow_id == "wf_001"
        assert result.task_goal == ""
        assert result.execution_status == {}
        assert result.node_summary == []
        assert result.error_log == []

    def test_compress_conversation_extracts_goal(self):
        """压缩对话日志应提取任务目标"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        input_data = CompressionInput(
            source_type="conversation",
            workflow_id="wf_001",
            raw_data={
                "messages": [
                    {"role": "user", "content": "帮我创建一个分析销售数据的工作流"},
                    {"role": "assistant", "content": "好的，我来为您创建"},
                ],
                "intent": "CREATE_WORKFLOW",
                "goal": "创建分析销售数据的工作流",
            },
        )

        result = compressor.compress(input_data)

        assert "销售数据" in result.task_goal or "创建" in result.task_goal
        assert result.conversation_summary != ""

    def test_compress_execution_log_extracts_node_summary(self):
        """压缩执行日志应提取节点摘要"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        input_data = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={
                "executed_nodes": [
                    {
                        "node_id": "node_1",
                        "type": "LLM",
                        "status": "completed",
                        "output": {"content": "分析结果..."},
                    },
                    {
                        "node_id": "node_2",
                        "type": "HTTP",
                        "status": "running",
                        "output": None,
                    },
                ],
                "workflow_status": "running",
                "progress": 0.5,
            },
        )

        result = compressor.compress(input_data)

        assert len(result.node_summary) == 2
        assert result.execution_status.get("status") == "running"
        assert result.execution_status.get("progress") == 0.5

    def test_compress_execution_log_extracts_errors(self):
        """压缩执行日志应提取错误信息"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        input_data = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={
                "executed_nodes": [
                    {
                        "node_id": "node_1",
                        "type": "HTTP",
                        "status": "failed",
                        "error": "Connection timeout",
                    },
                ],
                "workflow_status": "failed",
                "errors": [{"node_id": "node_1", "error": "Connection timeout", "retryable": True}],
            },
        )

        result = compressor.compress(input_data)

        assert len(result.error_log) >= 1
        assert any("timeout" in str(e).lower() for e in result.error_log)

    def test_compress_reflection_extracts_assessment(self):
        """压缩反思结果应提取评估信息"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        input_data = CompressionInput(
            source_type="reflection",
            workflow_id="wf_001",
            raw_data={
                "assessment": "工作流执行成功，但可优化数据处理流程",
                "issues": ["数据处理耗时较长"],
                "recommendations": ["添加缓存节点", "并行处理"],
                "confidence": 0.92,
                "should_retry": False,
            },
        )

        result = compressor.compress(input_data)

        assert "assessment" in result.reflection_summary
        assert result.reflection_summary["confidence"] == 0.92
        assert len(result.next_actions) >= 1


# ==================== 测试4：增量压缩功能 ====================


class TestIncrementalCompression:
    """测试增量压缩功能"""

    def test_merge_new_input_into_existing_context(self):
        """合并新输入到现有上下文"""
        from src.domain.services.context_compressor import (
            CompressedContext,
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        # 现有上下文
        existing = CompressedContext(
            workflow_id="wf_001",
            task_goal="创建数据分析工作流",
            execution_status={"status": "running", "progress": 0.3},
            node_summary=[{"node_id": "n1", "status": "completed"}],
            decision_history=[],
            reflection_summary={},
            conversation_summary="用户请求分析销售数据",
            error_log=[],
            next_actions=["执行节点2"],
        )

        # 新输入
        new_input = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={
                "executed_nodes": [
                    {"node_id": "n2", "status": "completed", "output": {"result": "ok"}},
                ],
                "workflow_status": "running",
                "progress": 0.6,
            },
        )

        result = compressor.merge(existing, new_input)

        # 验证合并结果
        assert result.workflow_id == "wf_001"
        assert result.execution_status.get("progress") == 0.6  # 更新进度
        assert len(result.node_summary) == 2  # 增加了节点
        assert result.task_goal == "创建数据分析工作流"  # 保持不变

    def test_merge_updates_version(self):
        """合并时应更新版本号"""
        from src.domain.services.context_compressor import (
            CompressedContext,
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        existing = CompressedContext(workflow_id="wf_001", version=1)

        new_input = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={"progress": 0.5},
        )

        result = compressor.merge(existing, new_input)

        assert result.version == 2

    def test_merge_preserves_error_log(self):
        """合并时应保留错误日志"""
        from src.domain.services.context_compressor import (
            CompressedContext,
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        existing = CompressedContext(
            workflow_id="wf_001",
            error_log=[{"node_id": "n1", "error": "Error 1"}],
        )

        new_input = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={
                "errors": [{"node_id": "n2", "error": "Error 2"}],
            },
        )

        result = compressor.merge(existing, new_input)

        assert len(result.error_log) == 2

    def test_merge_updates_reflection_summary(self):
        """合并反思结果应更新反思摘要"""
        from src.domain.services.context_compressor import (
            CompressedContext,
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        existing = CompressedContext(
            workflow_id="wf_001",
            reflection_summary={"assessment": "初步评估", "confidence": 0.7},
        )

        new_input = CompressionInput(
            source_type="reflection",
            workflow_id="wf_001",
            raw_data={
                "assessment": "最终评估：执行成功",
                "confidence": 0.95,
                "recommendations": ["优化缓存"],
            },
        )

        result = compressor.merge(existing, new_input)

        assert result.reflection_summary["confidence"] == 0.95
        assert "最终评估" in result.reflection_summary["assessment"]


# ==================== 测试5：上下文快照管理 ====================


class TestContextSnapshotManagement:
    """测试上下文快照管理"""

    def test_create_snapshot_from_context(self):
        """从上下文创建快照"""
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextSnapshotManager,
        )

        manager = ContextSnapshotManager()

        context = CompressedContext(
            workflow_id="wf_001",
            task_goal="测试目标",
            execution_status={"status": "running"},
        )

        snapshot_id = manager.save_snapshot(context)

        assert snapshot_id is not None
        assert snapshot_id.startswith("snap_")

    def test_retrieve_snapshot_by_id(self):
        """通过ID检索快照"""
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextSnapshotManager,
        )

        manager = ContextSnapshotManager()

        context = CompressedContext(
            workflow_id="wf_001",
            task_goal="测试目标",
        )

        snapshot_id = manager.save_snapshot(context)
        retrieved = manager.get_snapshot(snapshot_id)

        assert retrieved is not None
        assert retrieved.workflow_id == "wf_001"
        assert retrieved.task_goal == "测试目标"

    def test_list_snapshots_by_workflow(self):
        """按工作流列出快照"""
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextSnapshotManager,
        )

        manager = ContextSnapshotManager()

        # 为同一工作流创建多个快照
        for i in range(3):
            context = CompressedContext(
                workflow_id="wf_001",
                task_goal=f"目标_{i}",
                version=i + 1,
            )
            manager.save_snapshot(context)

        # 为另一个工作流创建快照
        other_context = CompressedContext(workflow_id="wf_002")
        manager.save_snapshot(other_context)

        snapshots = manager.list_snapshots(workflow_id="wf_001")

        assert len(snapshots) == 3

    def test_get_latest_snapshot(self):
        """获取最新快照"""
        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextSnapshotManager,
        )

        manager = ContextSnapshotManager()

        # 创建多个版本
        for i in range(3):
            context = CompressedContext(
                workflow_id="wf_001",
                task_goal=f"目标_{i}",
                version=i + 1,
            )
            manager.save_snapshot(context)

        latest = manager.get_latest_snapshot(workflow_id="wf_001")

        assert latest is not None
        assert latest.version == 3
        assert latest.task_goal == "目标_2"


# ==================== 测试6：八段压缩策略 ====================


class TestEightSegmentCompressionStrategies:
    """测试八段压缩的各种策略"""

    def test_task_goal_extraction_from_user_intent(self):
        """从用户意图提取任务目标"""
        from src.domain.services.context_compressor import ContextCompressor

        compressor = ContextCompressor()

        raw_data = {
            "intent": "CREATE_WORKFLOW",
            "confidence": 0.95,
            "entities": {
                "action": "创建",
                "target": "销售分析工作流",
            },
            "messages": [{"role": "user", "content": "帮我创建销售分析工作流"}],
        }

        goal = compressor._extract_task_goal(raw_data)

        assert "销售" in goal or "工作流" in goal

    def test_execution_status_summarization(self):
        """执行状态摘要"""
        from src.domain.services.context_compressor import ContextCompressor

        compressor = ContextCompressor()

        raw_data = {
            "workflow_status": "running",
            "progress": 0.75,
            "started_at": "2024-01-01T10:00:00",
            "estimated_completion": "2024-01-01T10:05:00",
            "nodes_total": 4,
            "nodes_completed": 3,
        }

        status = compressor._extract_execution_status(raw_data)

        assert status["status"] == "running"
        assert status["progress"] == 0.75
        assert "nodes_completed" in status

    def test_node_summary_compression(self):
        """节点摘要压缩"""
        from src.domain.services.context_compressor import ContextCompressor

        compressor = ContextCompressor()

        raw_data = {
            "executed_nodes": [
                {
                    "node_id": "llm_1",
                    "type": "LLM",
                    "status": "completed",
                    "started_at": "2024-01-01T10:00:00",
                    "completed_at": "2024-01-01T10:00:30",
                    "output": {
                        "content": "这是一段很长的LLM输出内容，包含详细分析..." * 10,
                        "tokens_used": 1500,
                    },
                },
            ]
        }

        summaries = compressor._extract_node_summaries(raw_data)

        assert len(summaries) == 1
        assert summaries[0]["node_id"] == "llm_1"
        assert summaries[0]["status"] == "completed"
        # 输出应被压缩，不包含完整内容
        assert len(str(summaries[0].get("output_summary", ""))) < 200

    def test_decision_history_extraction(self):
        """决策历史提取"""
        from src.domain.services.context_compressor import ContextCompressor

        compressor = ContextCompressor()

        raw_data = {
            "decisions": [
                {
                    "decision_type": "node_selection",
                    "choice": "GPT-4",
                    "reason": "需要更高的准确性",
                    "alternatives": ["GPT-3.5", "Claude"],
                    "timestamp": "2024-01-01T10:00:00",
                },
                {
                    "decision_type": "retry_strategy",
                    "choice": "exponential_backoff",
                    "reason": "避免频繁请求",
                },
            ]
        }

        history = compressor._extract_decision_history(raw_data)

        assert len(history) == 2
        assert history[0]["decision_type"] == "node_selection"

    def test_conversation_summary_compression(self):
        """对话摘要压缩"""
        from src.domain.services.context_compressor import ContextCompressor

        compressor = ContextCompressor()

        raw_data = {
            "messages": [
                {"role": "user", "content": "我需要分析上个月的销售数据"},
                {"role": "assistant", "content": "好的，请问您需要分析哪些维度？"},
                {"role": "user", "content": "按产品类别和地区分析"},
                {
                    "role": "assistant",
                    "content": "明白了，我将为您创建一个包含数据获取、分析和可视化的工作流",
                },
            ]
        }

        summary = compressor._extract_conversation_summary(raw_data)

        # 摘要应该简洁但包含关键信息
        assert len(summary) > 0
        assert len(summary) < 500  # 不应过长
        # 应包含关键词
        assert "销售" in summary or "分析" in summary

    def test_next_actions_generation(self):
        """下一步行动建议生成"""
        from src.domain.services.context_compressor import ContextCompressor

        compressor = ContextCompressor()

        raw_data = {
            "workflow_status": "running",
            "current_node": "node_2",
            "pending_nodes": ["node_3", "node_4"],
            "reflection": {
                "recommendations": ["优化数据缓存", "添加错误处理"],
            },
        }

        actions = compressor._extract_next_actions(raw_data)

        assert len(actions) >= 1
        # 应包含待执行节点或建议
        assert any("node" in a.lower() or "执行" in a for a in actions) or any(
            "优化" in a or "添加" in a for a in actions
        )


# ==================== 测试7：与现有摘要系统集成 ====================


class TestIntegrationWithSummarySystem:
    """测试与现有摘要系统的集成"""

    def test_use_evidence_store_for_raw_data(self):
        """使用证据存储保存原始数据"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )
        from src.domain.services.summary_strategy import EvidenceStore

        evidence_store = EvidenceStore()
        compressor = ContextCompressor(evidence_store=evidence_store)

        input_data = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={
                "executed_nodes": [{"node_id": "n1", "output": {"result": "detailed data"}}],
            },
        )

        result = compressor.compress(input_data)

        # 应该有证据引用
        assert len(result.evidence_refs) > 0
        # 可以通过引用检索原始数据
        for ref_id in result.evidence_refs:
            data = evidence_store.retrieve(ref_id)
            assert data is not None

    def test_compressed_context_has_summary_info_compatibility(self):
        """压缩上下文与 SummaryInfo 兼容"""
        from src.domain.services.context_compressor import CompressedContext
        from src.domain.services.summary_strategy import SummaryInfo

        context = CompressedContext(
            workflow_id="wf_001",
            task_goal="测试目标",
            evidence_refs=["ref_001", "ref_002"],
        )

        # 可以转换为 SummaryInfo
        summary_info = SummaryInfo(
            summary=context.to_summary_text(),
            evidence_refs=context.evidence_refs,
            source_id=context.workflow_id,
        )

        assert summary_info.summary is not None
        assert len(summary_info.evidence_refs) == 2


# ==================== 测试8：真实场景测试 ====================


class TestRealWorldScenarios:
    """真实场景测试"""

    def test_full_workflow_compression_flow(self):
        """完整的工作流压缩流程"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
            ContextSnapshotManager,
        )

        compressor = ContextCompressor()
        snapshot_manager = ContextSnapshotManager()

        # 1. 初始对话
        conversation_input = CompressionInput(
            source_type="conversation",
            workflow_id="wf_001",
            raw_data={
                "messages": [
                    {"role": "user", "content": "分析最近的用户行为数据"},
                ],
                "goal": "分析用户行为数据",
            },
        )
        ctx1 = compressor.compress(conversation_input)
        snapshot_manager.save_snapshot(ctx1)

        # 2. 执行进度更新
        execution_input = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={
                "executed_nodes": [
                    {"node_id": "fetch", "status": "completed"},
                    {"node_id": "analyze", "status": "running"},
                ],
                "workflow_status": "running",
                "progress": 0.5,
            },
        )
        ctx2 = compressor.merge(ctx1, execution_input)
        snapshot_manager.save_snapshot(ctx2)

        # 3. 反思结果
        reflection_input = CompressionInput(
            source_type="reflection",
            workflow_id="wf_001",
            raw_data={
                "assessment": "数据分析节点执行时间过长",
                "recommendations": ["增加并行处理", "优化查询"],
                "confidence": 0.85,
            },
        )
        ctx3 = compressor.merge(ctx2, reflection_input)
        snapshot_manager.save_snapshot(ctx3)

        # 验证最终压缩结果
        final = snapshot_manager.get_latest_snapshot("wf_001")

        assert final.task_goal != ""
        assert final.execution_status.get("progress") == 0.5
        assert len(final.node_summary) == 2
        assert final.reflection_summary.get("confidence") == 0.85
        assert len(final.next_actions) >= 1

    def test_error_recovery_compression(self):
        """错误恢复场景的压缩"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        # 初始上下文
        initial = compressor.compress(
            CompressionInput(
                source_type="execution",
                workflow_id="wf_001",
                raw_data={
                    "executed_nodes": [
                        {"node_id": "n1", "status": "completed"},
                        {"node_id": "n2", "status": "failed", "error": "API timeout"},
                    ],
                    "workflow_status": "failed",
                    "errors": [{"node_id": "n2", "error": "API timeout", "retryable": True}],
                },
            )
        )

        # 重试后的更新
        retry_input = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={
                "executed_nodes": [{"node_id": "n2", "status": "completed", "retry_count": 1}],
                "workflow_status": "running",
            },
        )

        recovered = compressor.merge(initial, retry_input)

        # 错误日志应保留历史
        assert len(recovered.error_log) >= 1
        # 节点状态应更新
        node_n2 = next((n for n in recovered.node_summary if n["node_id"] == "n2"), None)
        assert node_n2 is not None
        assert node_n2["status"] == "completed"

    @pytest.mark.asyncio
    async def test_coordinator_integration_simulation(self):
        """模拟 Coordinator 集成场景"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
            ContextSnapshotManager,
        )

        # 模拟 Coordinator 使用压缩器
        class MockCoordinator:
            def __init__(self):
                self.compressor = ContextCompressor()
                self.snapshot_manager = ContextSnapshotManager()
                self.current_context: dict = {}

            def on_reflection_completed(self, workflow_id: str, reflection_data: dict):
                """处理反思完成事件"""
                input_data = CompressionInput(
                    source_type="reflection",
                    workflow_id=workflow_id,
                    raw_data=reflection_data,
                )

                if workflow_id in self.current_context:
                    new_ctx = self.compressor.merge(self.current_context[workflow_id], input_data)
                else:
                    new_ctx = self.compressor.compress(input_data)

                self.current_context[workflow_id] = new_ctx
                self.snapshot_manager.save_snapshot(new_ctx)

                return new_ctx

            def get_context_for_conversation_agent(self, workflow_id: str):
                """获取对话Agent可见的上下文"""
                return self.current_context.get(workflow_id)

        coordinator = MockCoordinator()

        # 模拟反思事件
        reflection_data = {
            "assessment": "工作流执行完成",
            "confidence": 0.95,
            "recommendations": ["可以进行下一步操作"],
        }

        ctx = coordinator.on_reflection_completed("wf_001", reflection_data)

        assert ctx is not None
        assert ctx.reflection_summary["confidence"] == 0.95

        # 对话Agent可以获取上下文
        visible_ctx = coordinator.get_context_for_conversation_agent("wf_001")
        assert visible_ctx is not None


# ==================== 测试9：边界情况 ====================


class TestEdgeCases:
    """边界情况测试"""

    def test_compress_with_missing_fields(self):
        """处理缺失字段的输入"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        # 只有部分字段
        input_data = CompressionInput(
            source_type="execution",
            workflow_id="wf_001",
            raw_data={
                "workflow_status": "running",
                # 缺少 executed_nodes, progress 等
            },
        )

        result = compressor.compress(input_data)

        # 不应抛出异常
        assert result.workflow_id == "wf_001"
        assert result.execution_status.get("status") == "running"

    def test_compress_with_very_long_content(self):
        """处理超长内容"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor(max_segment_length=200)

        long_content = "这是一段非常长的内容。" * 1000

        input_data = CompressionInput(
            source_type="conversation",
            workflow_id="wf_001",
            raw_data={
                "messages": [{"role": "assistant", "content": long_content}],
            },
        )

        result = compressor.compress(input_data)

        # 摘要应被截断
        assert len(result.conversation_summary) <= 200

    def test_compress_with_special_characters(self):
        """处理特殊字符"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        input_data = CompressionInput(
            source_type="conversation",
            workflow_id="wf_001",
            raw_data={
                "messages": [
                    {
                        "role": "user",
                        "content": "包含特殊字符：<script>alert('xss')</script> & ' \" \n\t",
                    }
                ],
            },
        )

        # 不应抛出异常
        result = compressor.compress(input_data)
        assert result is not None

    def test_compress_with_unicode(self):
        """处理 Unicode 字符"""
        from src.domain.services.context_compressor import (
            CompressionInput,
            ContextCompressor,
        )

        compressor = ContextCompressor()

        input_data = CompressionInput(
            source_type="conversation",
            workflow_id="wf_001",
            raw_data={
                "messages": [
                    {"role": "user", "content": "中文消息 🎉 日本語 한국어 العربية"},
                ],
            },
        )

        result = compressor.compress(input_data)
        assert result is not None
        assert "中文" in result.conversation_summary or len(result.conversation_summary) > 0

    def test_concurrent_snapshot_access(self):
        """并发快照访问"""
        import asyncio

        from src.domain.services.context_compressor import (
            CompressedContext,
            ContextSnapshotManager,
        )

        manager = ContextSnapshotManager()

        async def save_and_retrieve(i):
            context = CompressedContext(
                workflow_id=f"wf_{i % 3}",  # 3个不同的工作流
                task_goal=f"目标_{i}",
                version=i,
            )
            snapshot_id = manager.save_snapshot(context)
            retrieved = manager.get_snapshot(snapshot_id)
            assert retrieved.task_goal == f"目标_{i}"
            return snapshot_id

        async def run_concurrent():
            tasks = [save_and_retrieve(i) for i in range(50)]
            results = await asyncio.gather(*tasks)
            assert len(results) == 50
            assert len(set(results)) == 50  # 所有ID唯一

        asyncio.run(run_concurrent())


# ==================== 测试10：转换和序列化 ====================


class TestSerializationAndConversion:
    """测试序列化和转换"""

    def test_compressed_context_to_dict(self):
        """压缩上下文转换为字典"""
        from src.domain.services.context_compressor import CompressedContext

        context = CompressedContext(
            workflow_id="wf_001",
            task_goal="测试目标",
            execution_status={"status": "running"},
            node_summary=[{"node_id": "n1"}],
            decision_history=[],
            reflection_summary={},
            conversation_summary="对话摘要",
            error_log=[],
            next_actions=["action1"],
        )

        result = context.to_dict()

        assert isinstance(result, dict)
        assert result["workflow_id"] == "wf_001"
        assert result["task_goal"] == "测试目标"
        assert "created_at" in result

    def test_compressed_context_from_dict(self):
        """从字典创建压缩上下文"""
        from src.domain.services.context_compressor import CompressedContext

        data = {
            "workflow_id": "wf_001",
            "task_goal": "测试目标",
            "execution_status": {"status": "completed"},
            "node_summary": [],
            "decision_history": [],
            "reflection_summary": {},
            "conversation_summary": "",
            "error_log": [],
            "next_actions": [],
            "version": 3,
        }

        context = CompressedContext.from_dict(data)

        assert context.workflow_id == "wf_001"
        assert context.version == 3

    def test_to_summary_text(self):
        """生成摘要文本"""
        from src.domain.services.context_compressor import CompressedContext

        context = CompressedContext(
            workflow_id="wf_001",
            task_goal="分析销售数据",
            execution_status={"status": "running", "progress": 0.5},
            node_summary=[{"node_id": "n1", "status": "completed"}],
            reflection_summary={"assessment": "进展顺利"},
            conversation_summary="用户请求分析数据",
            next_actions=["执行下一节点"],
        )

        text = context.to_summary_text()

        assert isinstance(text, str)
        assert len(text) > 0
        # 应包含关键信息
        assert "分析销售数据" in text or "销售" in text
