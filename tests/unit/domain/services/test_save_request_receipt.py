"""结果回执与记忆更新测试 (Step 8)

测试 SaveRequest 执行后的结果回执和记忆更新功能：
1. SaveRequestResult - 回执数据结构
2. SaveRequestResultEvent - 回执事件
3. SaveResultMemoryHandler - 记忆处理器
4. ViolationKnowledgeWriter - 违规写入长期知识库

TDD: Red → Green → Refactor
创建日期：2025-12-08
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# Test: SaveRequestResult 数据结构
# =============================================================================


class TestSaveRequestResultDataStructure:
    """SaveRequestResult 数据结构测试"""

    def test_create_success_result(self):
        """测试：创建成功的结果回执"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
        )

        result = SaveRequestResult(
            request_id="save-abc123",
            status=SaveResultStatus.SUCCESS,
            message="保存成功",
        )

        assert result.request_id == "save-abc123"
        assert result.status == SaveResultStatus.SUCCESS
        assert result.message == "保存成功"
        assert result.error_code is None
        assert result.error_message is None
        assert result.is_success()

    def test_create_rejected_result(self):
        """测试：创建拒绝的结果回执"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
        )

        result = SaveRequestResult(
            request_id="save-def456",
            status=SaveResultStatus.REJECTED,
            message="保存被拒绝",
            error_code="RULE_VIOLATION",
            error_message="违反敏感路径规则",
        )

        assert result.status == SaveResultStatus.REJECTED
        assert result.error_code == "RULE_VIOLATION"
        assert result.error_message == "违反敏感路径规则"
        assert not result.is_success()

    def test_create_failed_result(self):
        """测试：创建失败的结果回执"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
        )

        result = SaveRequestResult(
            request_id="save-ghi789",
            status=SaveResultStatus.FAILED,
            message="执行失败",
            error_code="IO_ERROR",
            error_message="磁盘空间不足",
            execution_time=0.5,
        )

        assert result.status == SaveResultStatus.FAILED
        assert result.execution_time == 0.5
        assert not result.is_success()
        assert result.is_error()

    def test_result_to_dict(self):
        """测试：序列化为字典"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
        )

        result = SaveRequestResult(
            request_id="save-test",
            status=SaveResultStatus.SUCCESS,
            message="OK",
        )

        data = result.to_dict()

        assert data["request_id"] == "save-test"
        assert data["status"] == "success"
        assert data["message"] == "OK"
        assert "timestamp" in data

    def test_result_severity_levels(self):
        """测试：不同状态的严重级别"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
        )

        success_result = SaveRequestResult(
            request_id="r1",
            status=SaveResultStatus.SUCCESS,
            message="OK",
        )

        rejected_result = SaveRequestResult(
            request_id="r2",
            status=SaveResultStatus.REJECTED,
            message="拒绝",
            violation_severity="high",
        )

        assert success_result.get_severity() == "none"
        assert rejected_result.get_severity() == "high"

    def test_result_with_audit_trail(self):
        """测试：包含审计追踪信息"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
        )

        result = SaveRequestResult(
            request_id="save-audit",
            status=SaveResultStatus.REJECTED,
            message="规则拒绝",
            audit_trail=[
                {"rule": "dangerous_path", "matched": True, "timestamp": "2025-12-08T10:00:00"},
                {"rule": "sensitive_content", "matched": False, "timestamp": "2025-12-08T10:00:01"},
            ],
        )

        assert len(result.audit_trail) == 2
        assert result.audit_trail[0]["rule"] == "dangerous_path"


# =============================================================================
# Test: SaveRequestResultEvent 事件
# =============================================================================


class TestSaveRequestResultEvent:
    """SaveRequestResultEvent 事件测试"""

    def test_create_result_event(self):
        """测试：创建结果回执事件"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveRequestResultEvent,
            SaveResultStatus,
        )

        result = SaveRequestResult(
            request_id="save-evt1",
            status=SaveResultStatus.SUCCESS,
            message="保存成功",
        )

        event = SaveRequestResultEvent(
            result=result,
            session_id="sess-123",
        )

        assert event.event_type == "save_request_result"
        assert event.result.request_id == "save-evt1"
        assert event.session_id == "sess-123"

    def test_event_source_tracking(self):
        """测试：事件来源追踪"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveRequestResultEvent,
            SaveResultStatus,
        )

        result = SaveRequestResult(
            request_id="save-track",
            status=SaveResultStatus.REJECTED,
            message="拒绝",
        )

        event = SaveRequestResultEvent(
            result=result,
            session_id="sess-456",
            source="coordinator_agent",
        )

        assert event.source == "coordinator_agent"


# =============================================================================
# Test: SaveResultMemoryHandler 记忆处理
# =============================================================================


class TestSaveResultMemoryHandler:
    """SaveResultMemoryHandler 记忆处理测试"""

    def test_record_to_short_term_memory(self):
        """测试：记录到短期记忆"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultMemoryHandler,
            SaveResultStatus,
        )

        handler = SaveResultMemoryHandler()

        result = SaveRequestResult(
            request_id="save-st1",
            status=SaveResultStatus.SUCCESS,
            message="保存成功",
        )

        handler.record_to_short_term("sess-1", result)

        # 获取短期记忆
        short_term = handler.get_short_term_memory("sess-1")
        assert len(short_term) == 1
        assert short_term[0]["request_id"] == "save-st1"

    def test_short_term_memory_limit(self):
        """测试：短期记忆容量限制"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultMemoryHandler,
            SaveResultStatus,
        )

        handler = SaveResultMemoryHandler(short_term_limit=5)

        # 添加 10 条记录
        for i in range(10):
            result = SaveRequestResult(
                request_id=f"save-{i}",
                status=SaveResultStatus.SUCCESS,
                message=f"保存 {i}",
            )
            handler.record_to_short_term("sess-limit", result)

        # 应该只保留最近 5 条
        short_term = handler.get_short_term_memory("sess-limit")
        assert len(short_term) == 5
        assert short_term[0]["request_id"] == "save-5"  # 最早的是 save-5

    def test_record_to_medium_term_memory(self):
        """测试：记录到中期记忆"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultMemoryHandler,
            SaveResultStatus,
        )

        handler = SaveResultMemoryHandler()

        result = SaveRequestResult(
            request_id="save-mt1",
            status=SaveResultStatus.REJECTED,
            message="被拒绝",
            error_code="RULE_VIOLATION",
        )

        handler.record_to_medium_term("sess-2", result)

        # 获取中期记忆
        medium_term = handler.get_medium_term_memory("sess-2")
        assert len(medium_term) == 1
        assert medium_term[0]["status"] == "rejected"

    def test_medium_term_aggregation(self):
        """测试：中期记忆聚合统计"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultMemoryHandler,
            SaveResultStatus,
        )

        handler = SaveResultMemoryHandler()

        # 添加混合结果
        for i in range(3):
            handler.record_to_medium_term(
                "sess-agg",
                SaveRequestResult(
                    request_id=f"save-s{i}",
                    status=SaveResultStatus.SUCCESS,
                    message="成功",
                ),
            )

        for i in range(2):
            handler.record_to_medium_term(
                "sess-agg",
                SaveRequestResult(
                    request_id=f"save-r{i}",
                    status=SaveResultStatus.REJECTED,
                    message="拒绝",
                ),
            )

        # 获取聚合统计
        stats = handler.get_session_statistics("sess-agg")
        assert stats["total_requests"] == 5
        assert stats["success_count"] == 3
        assert stats["rejected_count"] == 2
        assert stats["success_rate"] == 0.6

    def test_session_context_for_conversation_agent(self):
        """测试：为 ConversationAgent 生成上下文"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultMemoryHandler,
            SaveResultStatus,
        )

        handler = SaveResultMemoryHandler()

        # 记录一些结果
        handler.record_to_short_term(
            "sess-ctx",
            SaveRequestResult(
                request_id="save-1",
                status=SaveResultStatus.SUCCESS,
                message="成功",
            ),
        )
        handler.record_to_short_term(
            "sess-ctx",
            SaveRequestResult(
                request_id="save-2",
                status=SaveResultStatus.REJECTED,
                message="拒绝",
                error_message="路径不安全",
            ),
        )

        # 生成上下文
        context = handler.generate_context_for_agent("sess-ctx")

        assert "recent_save_results" in context
        assert "save_statistics" in context
        assert len(context["recent_save_results"]) == 2


# =============================================================================
# Test: ViolationKnowledgeWriter 违规知识库
# =============================================================================


class TestViolationKnowledgeWriter:
    """ViolationKnowledgeWriter 违规知识库测试"""

    def test_should_write_to_knowledge_base(self):
        """测试：判断是否应写入知识库"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
            ViolationKnowledgeWriter,
        )

        writer = ViolationKnowledgeWriter()

        # 成功的不需要写入
        success_result = SaveRequestResult(
            request_id="r1",
            status=SaveResultStatus.SUCCESS,
            message="OK",
        )
        assert not writer.should_write_to_knowledge_base(success_result)

        # 高严重级别需要写入
        severe_result = SaveRequestResult(
            request_id="r2",
            status=SaveResultStatus.REJECTED,
            message="拒绝",
            violation_severity="high",
        )
        assert writer.should_write_to_knowledge_base(severe_result)

        # 关键严重级别需要写入
        critical_result = SaveRequestResult(
            request_id="r3",
            status=SaveResultStatus.REJECTED,
            message="拒绝",
            violation_severity="critical",
        )
        assert writer.should_write_to_knowledge_base(critical_result)

    def test_write_violation_record(self):
        """测试：写入违规记录"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
            ViolationKnowledgeWriter,
        )

        mock_knowledge_manager = MagicMock()
        mock_knowledge_manager.create.return_value = "kb-entry-123"

        writer = ViolationKnowledgeWriter(knowledge_manager=mock_knowledge_manager)

        result = SaveRequestResult(
            request_id="save-vio1",
            status=SaveResultStatus.REJECTED,
            message="危险路径违规",
            error_code="DANGEROUS_PATH",
            error_message="尝试写入 /etc/passwd",
            violation_severity="critical",
            audit_trail=[
                {"rule": "dangerous_path", "matched": True},
            ],
        )

        entry_id = writer.write_violation("sess-vio", result)

        assert entry_id == "kb-entry-123"
        mock_knowledge_manager.create.assert_called_once()

        # 检查调用参数
        call_args = mock_knowledge_manager.create.call_args
        assert "violation" in call_args.kwargs.get("category", "").lower() or \
               "violation" in str(call_args)

    def test_batch_write_violations(self):
        """测试：批量写入违规记录"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
            ViolationKnowledgeWriter,
        )

        mock_knowledge_manager = MagicMock()
        mock_knowledge_manager.create.side_effect = ["kb-1", "kb-2"]

        writer = ViolationKnowledgeWriter(knowledge_manager=mock_knowledge_manager)

        results = [
            SaveRequestResult(
                request_id="v1",
                status=SaveResultStatus.REJECTED,
                message="违规1",
                violation_severity="high",
            ),
            SaveRequestResult(
                request_id="v2",
                status=SaveResultStatus.REJECTED,
                message="违规2",
                violation_severity="critical",
            ),
        ]

        entry_ids = writer.batch_write_violations("sess-batch", results)

        assert len(entry_ids) == 2
        assert mock_knowledge_manager.create.call_count == 2


# =============================================================================
# Test: SaveResultReceiptSystem 集成
# =============================================================================


class TestSaveResultReceiptSystem:
    """SaveResultReceiptSystem 集成测试"""

    def test_process_success_result(self):
        """测试：处理成功结果的完整流程"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultReceiptSystem,
            SaveResultStatus,
        )

        system = SaveResultReceiptSystem()

        result = SaveRequestResult(
            request_id="save-int1",
            status=SaveResultStatus.SUCCESS,
            message="保存成功",
        )

        processed = system.process_result("sess-int1", result)

        assert processed["recorded_to_short_term"]
        assert processed["recorded_to_medium_term"]
        assert not processed["written_to_knowledge_base"]

    def test_process_severe_violation_result(self):
        """测试：处理严重违规结果"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultReceiptSystem,
            SaveResultStatus,
        )

        mock_km = MagicMock()
        mock_km.create.return_value = "kb-severe"

        system = SaveResultReceiptSystem(knowledge_manager=mock_km)

        result = SaveRequestResult(
            request_id="save-sev1",
            status=SaveResultStatus.REJECTED,
            message="严重违规",
            violation_severity="critical",
        )

        processed = system.process_result("sess-sev1", result)

        assert processed["recorded_to_short_term"]
        assert processed["recorded_to_medium_term"]
        assert processed["written_to_knowledge_base"]
        assert processed["knowledge_entry_id"] == "kb-severe"

    def test_generate_receipt_log_chain(self):
        """测试：生成 SaveRequest → 审核 → 回执 链路日志"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultReceiptSystem,
            SaveResultStatus,
        )

        system = SaveResultReceiptSystem()

        # 模拟完整流程
        result = SaveRequestResult(
            request_id="save-log1",
            status=SaveResultStatus.SUCCESS,
            message="成功",
            audit_trail=[
                {"step": "received", "timestamp": "2025-12-08T10:00:00"},
                {"step": "validated", "timestamp": "2025-12-08T10:00:01"},
                {"step": "executed", "timestamp": "2025-12-08T10:00:02"},
            ],
        )

        system.process_result("sess-log", result)

        # 获取链路日志
        chain_log = system.get_receipt_chain_log("save-log1")

        assert chain_log is not None
        assert chain_log["request_id"] == "save-log1"
        assert "audit_trail" in chain_log
        assert "receipt_timestamp" in chain_log


# =============================================================================
# Test: ConversationAgent 集成
# =============================================================================


class TestConversationAgentIntegration:
    """ConversationAgent 记忆更新集成测试"""

    def test_conversation_agent_receives_result(self):
        """测试：ConversationAgent 接收保存结果"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveRequestResultEvent,
            SaveResultStatus,
        )
        from src.domain.services.event_bus import EventBus

        event_bus = EventBus()
        received_events = []

        async def handler(event):
            received_events.append(event)

        event_bus.subscribe(SaveRequestResultEvent, handler)

        # 发布结果事件
        result = SaveRequestResult(
            request_id="save-ca1",
            status=SaveResultStatus.SUCCESS,
            message="成功",
        )

        event = SaveRequestResultEvent(
            result=result,
            session_id="sess-ca1",
        )

        import asyncio
        asyncio.get_event_loop().run_until_complete(event_bus.publish(event))

        assert len(received_events) == 1
        assert received_events[0].result.request_id == "save-ca1"

    def test_memory_handler_integration_with_session_context(self):
        """测试：记忆处理器与 SessionContext 集成"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultMemoryHandler,
            SaveResultStatus,
        )

        handler = SaveResultMemoryHandler()

        # 模拟多轮保存操作
        for i in range(3):
            result = SaveRequestResult(
                request_id=f"save-sess{i}",
                status=SaveResultStatus.SUCCESS if i != 1 else SaveResultStatus.REJECTED,
                message=f"结果 {i}",
            )
            handler.record_to_short_term("sess-integrate", result)
            handler.record_to_medium_term("sess-integrate", result)

        # 生成上下文
        context = handler.generate_context_for_agent("sess-integrate")

        assert context["save_statistics"]["total_requests"] == 3
        assert context["save_statistics"]["success_count"] == 2
        assert context["save_statistics"]["rejected_count"] == 1


# =============================================================================
# Test: 日志追踪
# =============================================================================


class TestReceiptLogging:
    """结果回执日志追踪测试"""

    def test_log_chain_format(self):
        """测试：SaveRequest → 审核 → 回执 链路日志格式"""
        from src.domain.services.save_request_receipt import ReceiptLogger

        logger = ReceiptLogger()

        # 记录请求接收
        logger.log_request_received(
            request_id="save-chain1",
            session_id="sess-chain",
            target_path="/tmp/test.txt",
        )

        # 记录审核
        logger.log_audit_completed(
            request_id="save-chain1",
            approved=True,
            rules_checked=["rule1", "rule2"],
        )

        # 记录回执
        logger.log_receipt_sent(
            request_id="save-chain1",
            status="success",
            message="保存成功",
        )

        # 获取完整链路
        chain = logger.get_chain_log("save-chain1")

        assert len(chain) == 3
        assert chain[0]["event"] == "request_received"
        assert chain[1]["event"] == "audit_completed"
        assert chain[2]["event"] == "receipt_sent"

    def test_log_output_format(self):
        """测试：日志输出格式"""
        from src.domain.services.save_request_receipt import ReceiptLogger

        logger = ReceiptLogger()

        logger.log_request_received(
            request_id="save-fmt1",
            session_id="sess-fmt",
            target_path="/data/output.json",
        )

        # 验证日志格式包含关键信息
        logs = logger.get_all_logs()
        assert len(logs) > 0

        log_entry = logs[0]
        assert "request_id" in log_entry
        assert "timestamp" in log_entry
        assert "event" in log_entry


# =============================================================================
# Test: 边界情况
# =============================================================================


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_session_memory(self):
        """测试：空会话的记忆查询"""
        from src.domain.services.save_request_receipt import SaveResultMemoryHandler

        handler = SaveResultMemoryHandler()

        short_term = handler.get_short_term_memory("nonexistent-session")
        medium_term = handler.get_medium_term_memory("nonexistent-session")

        assert short_term == []
        assert medium_term == []

    def test_result_without_error_details(self):
        """测试：没有错误详情的失败结果"""
        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultStatus,
        )

        result = SaveRequestResult(
            request_id="save-noerr",
            status=SaveResultStatus.FAILED,
            message="失败",
            # 没有 error_code 和 error_message
        )

        assert result.is_error()
        assert result.error_code is None
        assert result.error_message is None

    def test_concurrent_session_memory_access(self):
        """测试：并发会话记忆访问"""
        from concurrent.futures import ThreadPoolExecutor

        from src.domain.services.save_request_receipt import (
            SaveRequestResult,
            SaveResultMemoryHandler,
            SaveResultStatus,
        )

        handler = SaveResultMemoryHandler()

        def record_result(session_id, result_id):
            result = SaveRequestResult(
                request_id=result_id,
                status=SaveResultStatus.SUCCESS,
                message="成功",
            )
            handler.record_to_short_term(session_id, result)
            handler.record_to_medium_term(session_id, result)

        # 并发记录
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(100):
                session = f"sess-{i % 5}"
                futures.append(executor.submit(record_result, session, f"save-{i}"))

            for f in futures:
                f.result()

        # 验证数据完整性
        total_records = 0
        for i in range(5):
            session = f"sess-{i}"
            total_records += len(handler.get_medium_term_memory(session))

        assert total_records == 100
