"""结果包与记忆更新集成测试

测试覆盖：
1. 结果包 Schema 验证
2. ResultUnpacker 解包器
3. MemoryUpdater 中期/长期记忆更新
4. KnowledgeWriter 知识库写入
5. CoordinatorResultMonitor 协调者监控与追踪
6. 完整的解包→更新→写入流程
"""

import json
from unittest.mock import MagicMock


class TestResultPackageSchemaValidation:
    """结果包 Schema 验证测试"""

    def test_schema_has_required_fields(self) -> None:
        """测试 Schema 包含必需字段"""
        from src.domain.services.result_memory_integration import RESULT_PACKAGE_SCHEMA

        required_fields = ["result_id", "context_package_id", "agent_id", "status", "output"]
        for field_name in required_fields:
            assert field_name in RESULT_PACKAGE_SCHEMA["properties"]

    def test_schema_has_optional_fields(self) -> None:
        """测试 Schema 包含可选字段"""
        from src.domain.services.result_memory_integration import RESULT_PACKAGE_SCHEMA

        optional_fields = ["logs", "new_knowledge", "errors"]
        for field_name in optional_fields:
            assert field_name in RESULT_PACKAGE_SCHEMA["properties"]

    def test_validate_valid_result(self) -> None:
        """测试验证有效结果包"""
        from src.domain.services.result_memory_integration import validate_result_schema

        valid_result = {
            "result_id": "res_001",
            "context_package_id": "ctx_001",
            "agent_id": "worker",
            "status": "completed",
            "output": {"data": "result"},
            "logs": [{"msg": "log"}],
            "new_knowledge": {"fact": "value"},
            "errors": [],
        }

        is_valid, errors = validate_result_schema(valid_result)
        assert is_valid
        assert len(errors) == 0

    def test_validate_missing_required_field(self) -> None:
        """测试验证缺少必需字段"""
        from src.domain.services.result_memory_integration import validate_result_schema

        invalid_result = {
            "result_id": "res_001",
            # 缺少 context_package_id
            "agent_id": "worker",
            "status": "completed",
            "output": {},
        }

        is_valid, errors = validate_result_schema(invalid_result)
        assert not is_valid
        assert any("context_package_id" in err for err in errors)

    def test_validate_invalid_status(self) -> None:
        """测试验证无效状态"""
        from src.domain.services.result_memory_integration import validate_result_schema

        invalid_result = {
            "result_id": "res_001",
            "context_package_id": "ctx_001",
            "agent_id": "worker",
            "status": "invalid_status",
            "output": {},
        }

        is_valid, errors = validate_result_schema(invalid_result)
        assert not is_valid
        assert any("status" in err for err in errors)


class TestResultUnpacker:
    """结果解包器测试"""

    def test_unpack_result_package(self) -> None:
        """测试解包结果包"""
        from src.domain.services.result_memory_integration import ResultUnpacker
        from src.domain.services.subagent_context_bridge import ResultPackage

        result_pkg = ResultPackage(
            result_id="res_unpack_001",
            context_package_id="ctx_unpack_001",
            agent_id="analyzer",
            status="completed",
            output_data={"analysis": "完成", "score": 95},
            execution_logs=[{"msg": "执行中"}, {"msg": "完成"}],
            knowledge_updates={"new_fact": "发现重要信息"},
        )

        unpacker = ResultUnpacker()
        unpacked = unpacker.unpack(result_pkg)

        assert unpacked.result_id == "res_unpack_001"
        assert unpacked.context_package_id == "ctx_unpack_001"
        assert unpacked.status == "completed"
        assert unpacked.output["analysis"] == "完成"
        assert len(unpacked.logs) == 2
        assert unpacked.new_knowledge["new_fact"] == "发现重要信息"

    def test_unpack_failed_result(self) -> None:
        """测试解包失败结果"""
        from src.domain.services.result_memory_integration import ResultUnpacker
        from src.domain.services.subagent_context_bridge import ResultPackage

        result_pkg = ResultPackage(
            result_id="res_fail_001",
            context_package_id="ctx_fail_001",
            agent_id="worker",
            status="failed",
            output_data={},
            error_message="任务执行超时",
            error_code="TIMEOUT",
        )

        unpacker = ResultUnpacker()
        unpacked = unpacker.unpack(result_pkg)

        assert unpacked.status == "failed"
        assert len(unpacked.errors) > 0
        assert "TIMEOUT" in str(unpacked.errors)

    def test_unpack_extracts_for_memory(self) -> None:
        """测试解包提取用于记忆的数据"""
        from src.domain.services.result_memory_integration import ResultUnpacker
        from src.domain.services.subagent_context_bridge import ResultPackage

        result_pkg = ResultPackage(
            result_id="res_mem_001",
            context_package_id="ctx_mem_001",
            agent_id="worker",
            status="completed",
            output_data={"summary": "任务完成摘要"},
            knowledge_updates={"learned": "新学到的知识"},
        )

        unpacker = ResultUnpacker()
        memory_data = unpacker.extract_for_memory(result_pkg)

        assert "summary" in memory_data
        assert "knowledge" in memory_data
        assert memory_data["knowledge"]["learned"] == "新学到的知识"

    def test_unpack_from_json(self) -> None:
        """测试从 JSON 解包"""
        from src.domain.services.result_memory_integration import ResultUnpacker

        json_str = json.dumps(
            {
                "result_id": "res_json_001",
                "context_package_id": "ctx_json_001",
                "agent_id": "worker",
                "status": "completed",
                "output_data": {"key": "value"},
                "execution_logs": [],
                "knowledge_updates": {},
            }
        )

        unpacker = ResultUnpacker()
        unpacked = unpacker.unpack_from_json(json_str)

        assert unpacked.result_id == "res_json_001"


class TestMemoryUpdater:
    """记忆更新器测试"""

    def test_update_mid_term_memory(self) -> None:
        """测试更新中期记忆"""
        from src.domain.services.result_memory_integration import (
            MemoryUpdater,
            UnpackedResult,
        )

        unpacked = UnpackedResult(
            result_id="res_mid_001",
            context_package_id="ctx_mid_001",
            agent_id="worker",
            status="completed",
            output={"task_result": "分析完成"},
            logs=[],
            new_knowledge={},
            errors=[],
        )

        updater = MemoryUpdater()
        mid_term_update = updater.prepare_mid_term_update(unpacked)

        assert mid_term_update["source_result_id"] == "res_mid_001"
        assert "task_result" in mid_term_update["content"]
        assert mid_term_update["update_type"] == "task_completion"

    def test_update_long_term_memory(self) -> None:
        """测试更新长期记忆"""
        from src.domain.services.result_memory_integration import (
            MemoryUpdater,
            UnpackedResult,
        )

        unpacked = UnpackedResult(
            result_id="res_long_001",
            context_package_id="ctx_long_001",
            agent_id="learner",
            status="completed",
            output={"conclusion": "重要结论"},
            logs=[],
            new_knowledge={
                "facts": ["事实1", "事实2"],
                "insights": "新洞察",
            },
            errors=[],
        )

        updater = MemoryUpdater()
        long_term_updates = updater.prepare_long_term_updates(unpacked)

        assert len(long_term_updates) > 0
        assert any("事实1" in str(u) for u in long_term_updates)

    def test_no_update_for_failed_result(self) -> None:
        """测试失败结果不更新长期记忆"""
        from src.domain.services.result_memory_integration import (
            MemoryUpdater,
            UnpackedResult,
        )

        unpacked = UnpackedResult(
            result_id="res_fail_002",
            context_package_id="ctx_fail_002",
            agent_id="worker",
            status="failed",
            output={},
            logs=[],
            new_knowledge={},
            errors=[{"code": "ERROR", "message": "失败"}],
        )

        updater = MemoryUpdater()
        long_term_updates = updater.prepare_long_term_updates(unpacked)

        # 失败结果不产生长期记忆更新
        assert len(long_term_updates) == 0

    def test_apply_updates_to_session(self) -> None:
        """测试将更新应用到会话"""
        from src.domain.services.result_memory_integration import (
            MemoryUpdater,
            UnpackedResult,
        )

        unpacked = UnpackedResult(
            result_id="res_session_001",
            context_package_id="ctx_session_001",
            agent_id="worker",
            status="completed",
            output={"result": "success"},
            logs=[],
            new_knowledge={"fact": "value"},
            errors=[],
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.mid_term_context = {}

        updater = MemoryUpdater()
        updater.apply_to_session(unpacked, mock_session)

        # 验证 mid_term_context 被更新
        assert mock_session.update_mid_term.called or "res_session_001" in str(
            mock_session.mid_term_context
        )


class TestKnowledgeWriter:
    """知识库写入器测试"""

    def test_write_new_knowledge(self) -> None:
        """测试写入新知识"""
        from src.domain.services.knowledge_manager import KnowledgeManager
        from src.domain.services.result_memory_integration import (
            KnowledgeWriter,
            UnpackedResult,
        )

        knowledge_manager = KnowledgeManager()
        writer = KnowledgeWriter(knowledge_manager)

        unpacked = UnpackedResult(
            result_id="res_knowledge_001",
            context_package_id="ctx_knowledge_001",
            agent_id="analyzer",
            status="completed",
            output={"analysis": "数据分析结果"},
            logs=[],
            new_knowledge={
                "insights": ["洞察1", "洞察2"],
                "conclusions": "最终结论",
            },
            errors=[],
        )

        entry_ids = writer.write_from_result(unpacked)

        assert len(entry_ids) > 0
        # 验证知识已写入
        for entry_id in entry_ids:
            entry = knowledge_manager.get(entry_id)
            assert entry is not None

    def test_write_with_tags(self) -> None:
        """测试带标签写入"""
        from src.domain.services.knowledge_manager import KnowledgeManager
        from src.domain.services.result_memory_integration import (
            KnowledgeWriter,
            UnpackedResult,
        )

        knowledge_manager = KnowledgeManager()
        writer = KnowledgeWriter(knowledge_manager)

        unpacked = UnpackedResult(
            result_id="res_tag_001",
            context_package_id="ctx_tag_001",
            agent_id="worker",
            status="completed",
            output={},
            logs=[],
            new_knowledge={"fact": "重要事实"},
            errors=[],
        )

        entry_ids = writer.write_from_result(
            unpacked,
            tags=["task_result", "auto_generated"],
        )

        assert len(entry_ids) > 0
        entry = knowledge_manager.get(entry_ids[0])
        assert "task_result" in entry["tags"]

    def test_no_write_for_empty_knowledge(self) -> None:
        """测试空知识不写入"""
        from src.domain.services.knowledge_manager import KnowledgeManager
        from src.domain.services.result_memory_integration import (
            KnowledgeWriter,
            UnpackedResult,
        )

        knowledge_manager = KnowledgeManager()
        writer = KnowledgeWriter(knowledge_manager)

        unpacked = UnpackedResult(
            result_id="res_empty_001",
            context_package_id="ctx_empty_001",
            agent_id="worker",
            status="completed",
            output={},
            logs=[],
            new_knowledge={},  # 空知识
            errors=[],
        )

        entry_ids = writer.write_from_result(unpacked)

        assert len(entry_ids) == 0

    def test_write_includes_source_tracking(self) -> None:
        """测试写入包含来源追踪"""
        from src.domain.services.knowledge_manager import KnowledgeManager
        from src.domain.services.result_memory_integration import (
            KnowledgeWriter,
            UnpackedResult,
        )

        knowledge_manager = KnowledgeManager()
        writer = KnowledgeWriter(knowledge_manager)

        unpacked = UnpackedResult(
            result_id="res_track_001",
            context_package_id="ctx_track_001",
            agent_id="analyzer",
            status="completed",
            output={},
            logs=[],
            new_knowledge={"discovery": "新发现"},
            errors=[],
        )

        entry_ids = writer.write_from_result(unpacked)

        entry = knowledge_manager.get(entry_ids[0])
        # 验证元数据包含来源信息
        assert entry["metadata"]["source_result_id"] == "res_track_001"
        assert entry["metadata"]["source_context_id"] == "ctx_track_001"


class TestCoordinatorResultMonitor:
    """协调者结果监控测试"""

    def test_monitor_creation(self) -> None:
        """测试监控器创建"""
        from src.domain.services.result_memory_integration import (
            CoordinatorResultMonitor,
        )

        monitor = CoordinatorResultMonitor(coordinator_id="coord_001")

        assert monitor.coordinator_id == "coord_001"

    def test_generate_tracking_id(self) -> None:
        """测试生成追踪 ID"""
        from src.domain.services.result_memory_integration import (
            CoordinatorResultMonitor,
        )

        monitor = CoordinatorResultMonitor(coordinator_id="coord_001")
        tracking_id = monitor.generate_tracking_id("res_001")

        assert tracking_id.startswith("track_")
        assert "res_001" in tracking_id or len(tracking_id) > 10

    def test_log_result_received(self) -> None:
        """测试记录结果接收日志"""
        from src.domain.services.result_memory_integration import (
            CoordinatorResultMonitor,
        )
        from src.domain.services.subagent_context_bridge import ResultPackage

        monitor = CoordinatorResultMonitor(coordinator_id="coord_001")

        result_pkg = ResultPackage(
            result_id="res_recv_001",
            context_package_id="ctx_recv_001",
            agent_id="worker",
            status="completed",
            output_data={},
        )

        log_entry = monitor.log_result_received(result_pkg)

        assert log_entry["event"] == "result_received"
        assert log_entry["result_id"] == "res_recv_001"
        assert log_entry["coordinator_id"] == "coord_001"
        assert "tracking_id" in log_entry

    def test_log_memory_updated(self) -> None:
        """测试记录记忆更新日志"""
        from src.domain.services.result_memory_integration import (
            CoordinatorResultMonitor,
        )

        monitor = CoordinatorResultMonitor(coordinator_id="coord_001")

        log_entry = monitor.log_memory_updated(
            result_id="res_mem_001",
            tracking_id="track_001",
            update_type="mid_term",
        )

        assert log_entry["event"] == "memory_updated"
        assert log_entry["update_type"] == "mid_term"
        assert log_entry["tracking_id"] == "track_001"

    def test_log_knowledge_written(self) -> None:
        """测试记录知识写入日志"""
        from src.domain.services.result_memory_integration import (
            CoordinatorResultMonitor,
        )

        monitor = CoordinatorResultMonitor(coordinator_id="coord_001")

        log_entry = monitor.log_knowledge_written(
            result_id="res_know_001",
            tracking_id="track_001",
            entry_ids=["entry_001", "entry_002"],
        )

        assert log_entry["event"] == "knowledge_written"
        assert len(log_entry["entry_ids"]) == 2
        assert log_entry["tracking_id"] == "track_001"

    def test_get_processing_trace(self) -> None:
        """测试获取处理追踪"""
        from src.domain.services.result_memory_integration import (
            CoordinatorResultMonitor,
        )
        from src.domain.services.subagent_context_bridge import ResultPackage

        monitor = CoordinatorResultMonitor(coordinator_id="coord_001")

        result_pkg = ResultPackage(
            result_id="res_trace_001",
            context_package_id="ctx_trace_001",
            agent_id="worker",
            status="completed",
            output_data={},
        )

        # 模拟完整处理流程
        monitor.log_result_received(result_pkg)
        tracking_id = monitor.get_tracking_id("res_trace_001")
        monitor.log_memory_updated("res_trace_001", tracking_id, "mid_term")
        monitor.log_knowledge_written("res_trace_001", tracking_id, ["entry_001"])

        trace = monitor.get_processing_trace("res_trace_001")

        assert len(trace) == 3
        assert trace[0]["event"] == "result_received"
        assert trace[1]["event"] == "memory_updated"
        assert trace[2]["event"] == "knowledge_written"


class TestResultProcessingPipeline:
    """结果处理流水线测试"""

    def test_full_processing_pipeline(self) -> None:
        """测试完整处理流水线"""
        from src.domain.services.knowledge_manager import KnowledgeManager
        from src.domain.services.result_memory_integration import (
            ResultProcessingPipeline,
        )
        from src.domain.services.subagent_context_bridge import ResultPackage

        knowledge_manager = KnowledgeManager()
        pipeline = ResultProcessingPipeline(
            coordinator_id="coord_pipeline",
            knowledge_manager=knowledge_manager,
        )

        result_pkg = ResultPackage(
            result_id="res_pipeline_001",
            context_package_id="ctx_pipeline_001",
            agent_id="analyzer",
            status="completed",
            output_data={"analysis": "分析结果"},
            execution_logs=[{"msg": "执行完成"}],
            knowledge_updates={
                "insights": "重要洞察",
                "facts": ["事实1"],
            },
        )

        # 执行流水线
        processing_result = pipeline.process(result_pkg)

        assert processing_result.success
        assert processing_result.tracking_id is not None
        assert processing_result.mid_term_updated
        assert len(processing_result.knowledge_entry_ids) > 0

    def test_pipeline_with_failed_result(self) -> None:
        """测试流水线处理失败结果"""
        from src.domain.services.knowledge_manager import KnowledgeManager
        from src.domain.services.result_memory_integration import (
            ResultProcessingPipeline,
        )
        from src.domain.services.subagent_context_bridge import ResultPackage

        knowledge_manager = KnowledgeManager()
        pipeline = ResultProcessingPipeline(
            coordinator_id="coord_fail",
            knowledge_manager=knowledge_manager,
        )

        result_pkg = ResultPackage(
            result_id="res_fail_pipeline",
            context_package_id="ctx_fail_pipeline",
            agent_id="worker",
            status="failed",
            output_data={},
            error_message="执行失败",
            error_code="EXEC_ERROR",
        )

        processing_result = pipeline.process(result_pkg)

        # 失败结果也应该被处理（记录错误）
        assert processing_result.tracking_id is not None
        # 但不应该写入知识库
        assert len(processing_result.knowledge_entry_ids) == 0

    def test_pipeline_generates_audit_log(self) -> None:
        """测试流水线生成审计日志"""
        from src.domain.services.knowledge_manager import KnowledgeManager
        from src.domain.services.result_memory_integration import (
            ResultProcessingPipeline,
        )
        from src.domain.services.subagent_context_bridge import ResultPackage

        knowledge_manager = KnowledgeManager()
        pipeline = ResultProcessingPipeline(
            coordinator_id="coord_audit",
            knowledge_manager=knowledge_manager,
        )

        result_pkg = ResultPackage(
            result_id="res_audit_001",
            context_package_id="ctx_audit_001",
            agent_id="worker",
            status="completed",
            output_data={"data": "value"},
            knowledge_updates={"fact": "info"},
        )

        pipeline.process(result_pkg)

        # 获取审计日志
        audit_log = pipeline.get_audit_log("res_audit_001")

        assert len(audit_log) > 0
        assert all("timestamp" in entry for entry in audit_log)
        assert all("tracking_id" in entry for entry in audit_log)


class TestMemoryUpdateStrategies:
    """记忆更新策略测试"""

    def test_incremental_update_strategy(self) -> None:
        """测试增量更新策略"""
        from src.domain.services.result_memory_integration import (
            MemoryUpdater,
            UnpackedResult,
            UpdateStrategy,
        )

        updater = MemoryUpdater(strategy=UpdateStrategy.INCREMENTAL)

        unpacked = UnpackedResult(
            result_id="res_inc_001",
            context_package_id="ctx_inc_001",
            agent_id="worker",
            status="completed",
            output={"delta": "增量数据"},
            logs=[],
            new_knowledge={"new": "知识"},
            errors=[],
        )

        update = updater.prepare_mid_term_update(unpacked)

        assert update["strategy"] == "incremental"

    def test_replace_update_strategy(self) -> None:
        """测试替换更新策略"""
        from src.domain.services.result_memory_integration import (
            MemoryUpdater,
            UnpackedResult,
            UpdateStrategy,
        )

        updater = MemoryUpdater(strategy=UpdateStrategy.REPLACE)

        unpacked = UnpackedResult(
            result_id="res_rep_001",
            context_package_id="ctx_rep_001",
            agent_id="worker",
            status="completed",
            output={"full": "完整数据"},
            logs=[],
            new_knowledge={},
            errors=[],
        )

        update = updater.prepare_mid_term_update(unpacked)

        assert update["strategy"] == "replace"


class TestUnpackedResultDataClass:
    """UnpackedResult 数据类测试"""

    def test_unpacked_result_creation(self) -> None:
        """测试 UnpackedResult 创建"""
        from src.domain.services.result_memory_integration import UnpackedResult

        unpacked = UnpackedResult(
            result_id="res_001",
            context_package_id="ctx_001",
            agent_id="worker",
            status="completed",
            output={"key": "value"},
            logs=[{"msg": "log"}],
            new_knowledge={"fact": "info"},
            errors=[],
        )

        assert unpacked.result_id == "res_001"
        assert unpacked.is_success()
        assert not unpacked.has_errors()

    def test_unpacked_result_failed_status(self) -> None:
        """测试失败状态的 UnpackedResult"""
        from src.domain.services.result_memory_integration import UnpackedResult

        unpacked = UnpackedResult(
            result_id="res_fail",
            context_package_id="ctx_fail",
            agent_id="worker",
            status="failed",
            output={},
            logs=[],
            new_knowledge={},
            errors=[{"code": "ERR", "message": "错误"}],
        )

        assert not unpacked.is_success()
        assert unpacked.has_errors()

    def test_unpacked_result_to_dict(self) -> None:
        """测试 UnpackedResult 转字典"""
        from src.domain.services.result_memory_integration import UnpackedResult

        unpacked = UnpackedResult(
            result_id="res_dict",
            context_package_id="ctx_dict",
            agent_id="worker",
            status="completed",
            output={"data": 123},
            logs=[],
            new_knowledge={},
            errors=[],
        )

        data = unpacked.to_dict()

        assert data["result_id"] == "res_dict"
        assert data["output"]["data"] == 123


class TestProcessingResult:
    """处理结果数据类测试"""

    def test_processing_result_success(self) -> None:
        """测试成功的处理结果"""
        from src.domain.services.result_memory_integration import ProcessingResult

        result = ProcessingResult(
            success=True,
            tracking_id="track_001",
            result_id="res_001",
            mid_term_updated=True,
            long_term_updated=True,
            knowledge_entry_ids=["entry_001", "entry_002"],
            errors=[],
        )

        assert result.success
        assert result.tracking_id == "track_001"
        assert len(result.knowledge_entry_ids) == 2

    def test_processing_result_failure(self) -> None:
        """测试失败的处理结果"""
        from src.domain.services.result_memory_integration import ProcessingResult

        result = ProcessingResult(
            success=False,
            tracking_id="track_fail",
            result_id="res_fail",
            mid_term_updated=False,
            long_term_updated=False,
            knowledge_entry_ids=[],
            errors=["处理失败"],
        )

        assert not result.success
        assert len(result.errors) > 0
