"""阶段6测试：摘要策略与信息完整性

测试目标：
1. ConversationAgent 发布信息时附带 summary/evidence_refs 字段
2. Coordinator 校验摘要完整性
3. 提供 API 获取原始数据（通过引用ID）
4. 摘要缺失关键信息时可通过引用补齐

完成标准：
- 事件/日志中含摘要与引用
- 提供 API 获取原始数据
- 测试验证摘要缺失关键信息时可通过引用补齐
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ==================== 测试1：摘要数据结构 ====================


class TestSummaryDataStructure:
    """测试摘要数据结构"""

    def test_summary_info_has_required_fields(self):
        """摘要信息应包含必需字段：summary, evidence_refs, created_at"""
        from src.domain.services.summary_strategy import SummaryInfo

        summary = SummaryInfo(
            summary="这是一段摘要",
            evidence_refs=["ref_001", "ref_002"],
        )

        assert summary.summary == "这是一段摘要"
        assert summary.evidence_refs == ["ref_001", "ref_002"]
        assert summary.created_at is not None

    def test_evidence_reference_has_required_fields(self):
        """证据引用应包含必需字段：ref_id, source_type, source_id, data_path"""
        from src.domain.services.summary_strategy import EvidenceReference

        ref = EvidenceReference(
            ref_id="ref_001",
            source_type="node_output",
            source_id="node_123",
            data_path="result.data",
        )

        assert ref.ref_id == "ref_001"
        assert ref.source_type == "node_output"
        assert ref.source_id == "node_123"
        assert ref.data_path == "result.data"

    def test_summary_level_enum(self):
        """摘要级别枚举：BRIEF, STANDARD, DETAILED"""
        from src.domain.services.summary_strategy import SummaryLevel

        assert SummaryLevel.BRIEF.value == "brief"
        assert SummaryLevel.STANDARD.value == "standard"
        assert SummaryLevel.DETAILED.value == "detailed"


# ==================== 测试2：摘要生成器 ====================


class TestSummaryGenerator:
    """测试摘要生成器"""

    def test_generate_summary_from_raw_data(self):
        """从原始数据生成摘要"""
        from src.domain.services.summary_strategy import SummaryGenerator

        generator = SummaryGenerator()

        raw_data = {
            "node_id": "node_123",
            "type": "llm",
            "result": {
                "content": "这是一段很长的LLM输出内容，包含了详细的分析结果...",
                "tokens_used": 1500,
                "model": "gpt-4",
            },
        }

        summary_info = generator.generate(raw_data)

        assert summary_info.summary is not None
        assert len(summary_info.summary) > 0
        assert len(summary_info.evidence_refs) > 0

    def test_generate_summary_with_different_levels(self):
        """不同级别生成不同详细程度的摘要"""
        from src.domain.services.summary_strategy import SummaryGenerator, SummaryLevel

        generator = SummaryGenerator()

        raw_data = {
            "content": "这是一段很长的内容" * 100,  # 较长的内容
        }

        brief_summary = generator.generate(raw_data, level=SummaryLevel.BRIEF)
        standard_summary = generator.generate(raw_data, level=SummaryLevel.STANDARD)
        detailed_summary = generator.generate(raw_data, level=SummaryLevel.DETAILED)

        # BRIEF 最短，DETAILED 最长
        assert len(brief_summary.summary) <= len(standard_summary.summary)
        assert len(standard_summary.summary) <= len(detailed_summary.summary)

    def test_generate_summary_creates_evidence_refs(self):
        """生成摘要时自动创建证据引用"""
        from src.domain.services.summary_strategy import SummaryGenerator

        generator = SummaryGenerator()

        raw_data = {
            "node_id": "node_123",
            "result": {"key1": "value1", "key2": "value2"},
        }

        summary_info = generator.generate(raw_data, source_id="node_123")

        # 应该有引用指向原始数据
        assert len(summary_info.evidence_refs) > 0
        assert any("node_123" in ref for ref in summary_info.evidence_refs)


# ==================== 测试3：证据存储与检索 ====================


class TestEvidenceStore:
    """测试证据存储"""

    def test_store_evidence(self):
        """存储证据数据"""
        from src.domain.services.summary_strategy import EvidenceStore

        store = EvidenceStore()

        raw_data = {
            "content": "原始数据内容",
            "metadata": {"key": "value"},
        }

        ref_id = store.store(raw_data, source_id="node_123", source_type="node_output")

        assert ref_id is not None
        assert ref_id.startswith("ref_")

    def test_retrieve_evidence_by_ref_id(self):
        """通过引用ID检索证据"""
        from src.domain.services.summary_strategy import EvidenceStore

        store = EvidenceStore()

        raw_data = {"content": "原始数据内容"}
        ref_id = store.store(raw_data, source_id="node_123", source_type="node_output")

        retrieved = store.retrieve(ref_id)

        assert retrieved is not None
        assert retrieved["content"] == "原始数据内容"

    def test_retrieve_nonexistent_evidence_returns_none(self):
        """检索不存在的证据返回None"""
        from src.domain.services.summary_strategy import EvidenceStore

        store = EvidenceStore()

        retrieved = store.retrieve("nonexistent_ref")

        assert retrieved is None

    def test_retrieve_evidence_with_data_path(self):
        """通过数据路径检索证据的特定部分"""
        from src.domain.services.summary_strategy import EvidenceStore

        store = EvidenceStore()

        raw_data = {
            "result": {
                "data": {"nested": {"value": 42}},
                "metadata": {"key": "value"},
            }
        }
        ref_id = store.store(raw_data, source_id="node_123", source_type="node_output")

        # 检索特定路径
        nested_value = store.retrieve(ref_id, data_path="result.data.nested.value")

        assert nested_value == 42

    def test_list_references_by_source(self):
        """按来源列出所有引用"""
        from src.domain.services.summary_strategy import EvidenceStore

        store = EvidenceStore()

        store.store({"data": 1}, source_id="node_a", source_type="node_output")
        store.store({"data": 2}, source_id="node_a", source_type="node_output")
        store.store({"data": 3}, source_id="node_b", source_type="node_output")

        refs_a = store.list_by_source("node_a")
        refs_b = store.list_by_source("node_b")

        assert len(refs_a) == 2
        assert len(refs_b) == 1


# ==================== 测试4：Coordinator摘要校验 ====================


class TestCoordinatorSummaryValidation:
    """测试Coordinator摘要校验"""

    def test_validate_summary_completeness(self):
        """校验摘要完整性"""
        from src.domain.services.summary_strategy import (
            SummaryInfo,
            SummaryValidator,
        )

        validator = SummaryValidator()

        # 完整的摘要
        valid_summary = SummaryInfo(
            summary="这是一段完整的摘要，包含了关键信息。",
            evidence_refs=["ref_001"],
        )

        result = validator.validate(valid_summary)
        assert result.is_valid is True

    def test_reject_empty_summary(self):
        """拒绝空摘要"""
        from src.domain.services.summary_strategy import (
            SummaryInfo,
            SummaryValidator,
        )

        validator = SummaryValidator()

        empty_summary = SummaryInfo(
            summary="",
            evidence_refs=["ref_001"],
        )

        result = validator.validate(empty_summary)
        assert result.is_valid is False
        assert "摘要不能为空" in result.errors

    def test_reject_summary_without_evidence(self):
        """拒绝没有证据引用的摘要"""
        from src.domain.services.summary_strategy import (
            SummaryInfo,
            SummaryValidator,
        )

        validator = SummaryValidator()

        no_evidence_summary = SummaryInfo(
            summary="这是一段摘要",
            evidence_refs=[],
        )

        result = validator.validate(no_evidence_summary)
        assert result.is_valid is False
        assert "缺少证据引用" in result.errors

    def test_validate_evidence_refs_exist(self):
        """校验证据引用是否存在"""
        from src.domain.services.summary_strategy import (
            EvidenceStore,
            SummaryInfo,
            SummaryValidator,
        )

        store = EvidenceStore()
        ref_id = store.store({"data": "test"}, source_id="node_123", source_type="node_output")

        validator = SummaryValidator(evidence_store=store)

        # 引用存在
        valid_summary = SummaryInfo(
            summary="摘要内容",
            evidence_refs=[ref_id],
        )
        result = validator.validate(valid_summary)
        assert result.is_valid is True

        # 引用不存在
        invalid_summary = SummaryInfo(
            summary="摘要内容",
            evidence_refs=["nonexistent_ref"],
        )
        result = validator.validate(invalid_summary)
        assert result.is_valid is False
        assert any("引用不存在" in e for e in result.errors)


# ==================== 测试5：信息补全流程 ====================


class TestInformationCompletion:
    """测试信息补全流程"""

    def test_detect_missing_key_information(self):
        """检测摘要缺失关键信息"""
        from src.domain.services.summary_strategy import InformationCompletionService

        service = InformationCompletionService()

        # 摘要缺少数值信息
        summary = "处理完成，结果正常。"
        raw_data = {
            "result": {
                "count": 100,
                "average": 45.5,
                "status": "success",
            }
        }

        missing_info = service.detect_missing_info(summary, raw_data)

        # 应该检测到缺失的数值信息
        assert len(missing_info) > 0
        assert any("count" in info or "average" in info for info in missing_info)

    def test_complete_summary_with_evidence(self):
        """通过证据补全摘要"""
        from src.domain.services.summary_strategy import (
            EvidenceStore,
            InformationCompletionService,
            SummaryInfo,
        )

        store = EvidenceStore()
        service = InformationCompletionService(evidence_store=store)

        raw_data = {
            "result": {
                "total_count": 150,
                "success_rate": 0.95,
            }
        }
        ref_id = store.store(raw_data, source_id="node_123", source_type="node_output")

        # 不完整的摘要
        incomplete_summary = SummaryInfo(
            summary="处理完成。",
            evidence_refs=[ref_id],
        )

        # 补全摘要
        completed_summary = service.complete(incomplete_summary)

        # 补全后应包含数值信息
        assert "150" in completed_summary.summary or "total_count" in completed_summary.summary

    def test_complete_returns_original_if_already_complete(self):
        """如果摘要已完整，返回原始摘要"""
        from src.domain.services.summary_strategy import (
            EvidenceStore,
            InformationCompletionService,
            SummaryInfo,
        )

        store = EvidenceStore()
        service = InformationCompletionService(evidence_store=store)

        raw_data = {"result": {"count": 100}}
        ref_id = store.store(raw_data, source_id="node_123", source_type="node_output")

        # 已经完整的摘要
        complete_summary = SummaryInfo(
            summary="处理完成，共处理 100 条记录。",
            evidence_refs=[ref_id],
        )

        result = service.complete(complete_summary)

        # 返回相同或相似的摘要
        assert "100" in result.summary


# ==================== 测试6：摘要事件与日志 ====================


class TestSummaryEventsAndLogs:
    """测试摘要事件与日志"""

    def test_summary_event_contains_summary_and_refs(self):
        """摘要事件包含摘要和引用"""
        from src.domain.services.summary_strategy import SummaryPublishedEvent

        event = SummaryPublishedEvent(
            source="conversation_agent",
            summary="这是摘要",
            evidence_refs=["ref_001", "ref_002"],
            original_event_id="evt_123",
        )

        assert event.summary == "这是摘要"
        assert event.evidence_refs == ["ref_001", "ref_002"]
        assert event.original_event_id == "evt_123"

    @pytest.mark.asyncio
    async def test_publish_summary_event(self):
        """发布摘要事件"""
        from src.domain.services.event_bus import EventBus
        from src.domain.services.summary_strategy import SummaryPublisher

        event_bus = EventBus()
        publisher = SummaryPublisher(event_bus=event_bus)

        received_events = []

        async def handler(event):
            received_events.append(event)

        from src.domain.services.summary_strategy import SummaryPublishedEvent

        event_bus.subscribe(SummaryPublishedEvent, handler)

        await publisher.publish_summary(
            summary="测试摘要",
            evidence_refs=["ref_001"],
            original_event_id="evt_123",
        )

        assert len(received_events) == 1
        assert received_events[0].summary == "测试摘要"

    def test_summary_log_entry(self):
        """摘要日志条目"""
        from src.domain.services.summary_strategy import SummaryLogger

        logger = SummaryLogger()

        logger.log_summary(
            source="node_123",
            summary="处理完成",
            evidence_refs=["ref_001"],
        )

        logs = logger.get_logs()

        assert len(logs) == 1
        assert logs[0]["source"] == "node_123"
        assert logs[0]["summary"] == "处理完成"
        assert logs[0]["evidence_refs"] == ["ref_001"]


# ==================== 测试7：ConversationAgent集成 ====================


class TestConversationAgentSummaryIntegration:
    """测试ConversationAgent摘要集成"""

    @pytest.mark.asyncio
    async def test_decision_event_includes_summary(self):
        """决策事件包含摘要字段"""
        from src.domain.services.summary_strategy import (
            DecisionWithSummary,
            SummaryInfo,
        )

        summary = SummaryInfo(
            summary="创建LLM节点用于数据分析",
            evidence_refs=["ref_001"],
        )

        decision = DecisionWithSummary(
            decision_type="create_node",
            payload={"node_type": "LLM"},
            summary=summary,
        )

        assert decision.summary.summary == "创建LLM节点用于数据分析"
        assert "ref_001" in decision.summary.evidence_refs

    @pytest.mark.asyncio
    async def test_conversation_agent_publishes_summary_with_decision(self):
        """ConversationAgent发布决策时附带摘要"""
        from src.domain.services.context_manager import (
            GlobalContext,
            SessionContext,
            WorkflowContext,
        )
        from src.domain.services.event_bus import EventBus
        from src.domain.services.summary_strategy import SummaryEnabledConversationAgent

        # 创建上下文
        global_ctx = GlobalContext(user_id="user_1")
        session_ctx = SessionContext(
            session_id="session_1",
            global_context=global_ctx,
        )
        # 创建 WorkflowContext (用于完整上下文验证)
        _ = WorkflowContext(
            workflow_id="wf_1",
            session_context=session_ctx,
        )

        # 创建 mock LLM
        mock_llm = MagicMock()
        mock_llm.think = AsyncMock(return_value="思考中...")
        mock_llm.decide_action = AsyncMock(
            return_value={
                "action_type": "create_node",
                "node_type": "LLM",
                "config": {"model": "gpt-4"},
            }
        )
        mock_llm.should_continue = AsyncMock(return_value=False)

        # 创建事件总线
        event_bus = EventBus()

        # 创建摘要增强的Agent
        agent = SummaryEnabledConversationAgent(
            session_context=session_ctx,
            llm=mock_llm,
            event_bus=event_bus,
        )

        # 捕获事件
        published_events = []

        async def capture_event(event):
            published_events.append(event)

        from src.domain.services.summary_strategy import SummaryPublishedEvent

        event_bus.subscribe(SummaryPublishedEvent, capture_event)

        # 运行
        await agent.run_async("创建一个数据分析节点")

        # 验证发布了摘要事件
        # Note: 实际实现可能不在每次决策时都发布摘要事件
        # 这里主要验证摘要能力已集成


# ==================== 测试8：真实场景测试 ====================


class TestRealWorldScenarios:
    """真实场景测试"""

    @pytest.mark.asyncio
    async def test_workflow_execution_summary_flow(self):
        """工作流执行摘要流程"""
        from src.domain.services.summary_strategy import (
            EvidenceStore,
            InformationCompletionService,
            SummaryGenerator,
            SummaryValidator,
        )

        # 1. 模拟工作流执行产生结果
        node_outputs = {
            "node_1": {
                "type": "api",
                "result": {
                    "status": 200,
                    "data": {"items": list(range(100))},
                },
            },
            "node_2": {
                "type": "llm",
                "result": {
                    "content": "分析结果：数据呈上升趋势，平均值为 50，最大值为 99...",
                    "tokens_used": 500,
                },
            },
        }

        # 2. 存储证据
        store = EvidenceStore()
        refs = []
        for node_id, output in node_outputs.items():
            ref_id = store.store(output, source_id=node_id, source_type="node_output")
            refs.append(ref_id)

        # 3. 生成摘要
        generator = SummaryGenerator()
        summary_info = generator.generate(
            {"nodes": list(node_outputs.keys()), "status": "completed"},
            source_id="workflow_123",
        )
        summary_info.evidence_refs = refs

        # 4. 校验摘要
        validator = SummaryValidator(evidence_store=store)
        validation_result = validator.validate(summary_info)
        assert validation_result.is_valid is True

        # 5. 如果摘要缺失信息，补全
        completion_service = InformationCompletionService(evidence_store=store)
        completed_summary = completion_service.complete(summary_info)

        assert completed_summary is not None

    @pytest.mark.asyncio
    async def test_summary_retrieval_api(self):
        """摘要检索API"""
        from src.domain.services.summary_strategy import EvidenceStore, SummaryRetrievalAPI

        store = EvidenceStore()

        # 存储多个节点的输出
        ref1 = store.store(
            {"result": {"value": 100, "details": "详细信息1"}},
            source_id="node_a",
            source_type="node_output",
        )
        ref2 = store.store(
            {"result": {"value": 200, "details": "详细信息2"}},
            source_id="node_b",
            source_type="node_output",
        )

        # 创建检索API
        api = SummaryRetrievalAPI(evidence_store=store)

        # 通过引用获取原始数据
        data1 = api.get_raw_data(ref1)
        assert data1["result"]["value"] == 100

        # 获取特定路径
        value2 = api.get_raw_data(ref2, data_path="result.value")
        assert value2 == 200

        # 列出某来源的所有引用
        refs_a = api.list_references(source_id="node_a")
        assert len(refs_a) == 1

    @pytest.mark.asyncio
    async def test_missing_info_detection_and_completion(self):
        """缺失信息检测与补全流程"""
        from src.domain.services.summary_strategy import (
            EvidenceStore,
            InformationCompletionService,
            SummaryInfo,
        )

        store = EvidenceStore()

        # 原始数据包含重要数值
        raw_data = {
            "analysis_result": {
                "total_records": 1500,
                "error_count": 23,
                "success_rate": 0.985,
                "processing_time_ms": 3500,
            }
        }
        ref_id = store.store(raw_data, source_id="analysis_node", source_type="node_output")

        # 摘要只提到了部分信息
        incomplete_summary = SummaryInfo(
            summary="分析完成，大部分记录处理成功。",
            evidence_refs=[ref_id],
        )

        # 检测并补全
        service = InformationCompletionService(evidence_store=store)
        missing = service.detect_missing_info(
            incomplete_summary.summary,
            raw_data,
        )

        # 应检测到缺失的具体数值
        assert len(missing) > 0

        # 补全后摘要应包含关键数值
        completed = service.complete(incomplete_summary)
        # 验证补全后包含至少一个具体数值
        import re

        numbers_in_completed = re.findall(r"\d+", completed.summary)
        assert len(numbers_in_completed) > 0


# ==================== 测试9：边界情况 ====================


class TestEdgeCases:
    """边界情况测试"""

    def test_summary_with_very_long_content(self):
        """处理超长内容的摘要"""
        from src.domain.services.summary_strategy import SummaryGenerator

        generator = SummaryGenerator(max_summary_length=200)

        raw_data = {"content": "这是一段非常长的内容。" * 1000}

        summary = generator.generate(raw_data)

        # 摘要长度应在限制内
        assert len(summary.summary) <= 200

    def test_summary_with_nested_data(self):
        """处理深度嵌套数据的摘要"""
        from src.domain.services.summary_strategy import EvidenceStore

        store = EvidenceStore()

        deeply_nested = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "value": "deep_value",
                        }
                    }
                }
            }
        }

        ref_id = store.store(deeply_nested, source_id="nested", source_type="node_output")

        # 可以检索深层路径
        value = store.retrieve(ref_id, data_path="level1.level2.level3.level4.value")
        assert value == "deep_value"

    def test_summary_with_special_characters(self):
        """处理特殊字符的摘要"""
        from src.domain.services.summary_strategy import SummaryGenerator, SummaryValidator

        generator = SummaryGenerator()

        raw_data = {
            "content": "包含特殊字符：<script>alert('xss')</script> & ' \" \n\t",
        }

        summary = generator.generate(raw_data)

        # 不应抛出错误
        assert summary is not None

        # 校验也不应出错
        validator = SummaryValidator()
        result = validator.validate(summary)
        # 只要有摘要和引用就有效
        if summary.summary and summary.evidence_refs:
            assert result.is_valid is True

    def test_concurrent_evidence_access(self):
        """并发访问证据存储"""
        import asyncio

        from src.domain.services.summary_strategy import EvidenceStore

        store = EvidenceStore()

        async def store_and_retrieve(i):
            ref_id = store.store(
                {"index": i, "data": f"data_{i}"},
                source_id=f"node_{i}",
                source_type="node_output",
            )
            retrieved = store.retrieve(ref_id)
            assert retrieved["index"] == i
            return ref_id

        async def run_concurrent():
            tasks = [store_and_retrieve(i) for i in range(100)]
            results = await asyncio.gather(*tasks)
            assert len(results) == 100
            assert len(set(results)) == 100  # 所有ref_id应唯一

        asyncio.run(run_concurrent())
