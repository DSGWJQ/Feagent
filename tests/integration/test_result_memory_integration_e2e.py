"""结果包与记忆更新集成测试

测试完整的端到端流程：
1. 子 Agent 完成任务并创建结果包
2. 父 Agent 解包结果
3. 更新中期/长期记忆
4. 写入知识库
5. 追踪 ID 贯穿全流程
"""

import pytest

from src.domain.services.context_protocol import ContextPacker
from src.domain.services.knowledge_manager import KnowledgeManager
from src.domain.services.result_memory_integration import (
    CoordinatorResultMonitor,
    KnowledgeWriter,
    MemoryUpdater,
    ResultProcessingPipeline,
    UnpackedResult,
    UpdateStrategy,
    validate_result_schema,
)
from src.domain.services.subagent_context_bridge import (
    ContextAwareSubAgent,
    ResultPackage,
)


class TestEndToEndResultProcessing:
    """端到端结果处理测试"""

    @pytest.mark.asyncio
    async def test_complete_subagent_to_parent_flow(self) -> None:
        """
        测试完整的子 Agent 到父 Agent 结果流程

        场景：
        1. 父 Agent 创建任务并分配给子 Agent
        2. 子 Agent 执行任务并返回结果
        3. 父 Agent 解包结果并更新记忆
        4. 知识写入知识库
        5. 全流程可追踪
        """
        # ==== 步骤 1: 父 Agent 创建上下文 ====
        packer = ContextPacker(agent_id="coordinator")
        context_pkg = packer.pack(
            task_description="分析销售趋势",
            constraints=["使用中文", "数据脱敏"],
            input_data={"sales": [100, 200, 300]},
        )

        # ==== 步骤 2: 子 Agent 执行任务 ====
        child = ContextAwareSubAgent(
            agent_id="sales_analyzer",
            context_package=context_pkg,
        )
        child.start_execution()
        child.log("开始分析销售数据")
        child.log("计算增长趋势")

        result_pkg = await child.complete_task(
            output_data={
                "trend": "上升",
                "growth_rate": "50%",
                "summary": "销售数据呈上升趋势，环比增长 50%",
            },
            knowledge_updates={
                "facts": ["Q3 销售增长显著", "主要来自新客户"],
                "insights": "新客户开发策略有效",
                "conclusions": "继续执行当前营销策略",
            },
        )

        # ==== 步骤 3: 父 Agent 处理结果 ====
        knowledge_manager = KnowledgeManager()
        pipeline = ResultProcessingPipeline(
            coordinator_id="coordinator",
            knowledge_manager=knowledge_manager,
        )

        processing_result = pipeline.process(result_pkg)

        # ==== 验证处理结果 ====
        assert processing_result.success
        assert processing_result.tracking_id is not None
        assert processing_result.mid_term_updated
        assert len(processing_result.knowledge_entry_ids) > 0

        # 验证知识已写入
        for entry_id in processing_result.knowledge_entry_ids:
            entry = knowledge_manager.get(entry_id)
            assert entry is not None
            assert entry["metadata"]["source_result_id"] == result_pkg.result_id

        # 验证审计日志
        audit_log = pipeline.get_audit_log(result_pkg.result_id)
        assert len(audit_log) >= 2  # 至少有接收和更新事件
        assert audit_log[0]["event"] == "result_received"

    @pytest.mark.asyncio
    async def test_multi_subagent_result_aggregation(self) -> None:
        """
        测试多子 Agent 结果聚合

        场景：多个子 Agent 并行执行，结果汇总到父 Agent
        """
        import asyncio

        packer = ContextPacker(agent_id="coordinator")
        knowledge_manager = KnowledgeManager()

        # 创建多个子任务
        tasks = [
            ("data_fetcher", "获取数据", {"source": "database"}),
            ("data_cleaner", "清洗数据", {"rules": ["remove_nulls"]}),
            ("analyzer", "分析数据", {"method": "statistical"}),
        ]

        # 并行执行子任务
        async def execute_subtask(agent_id: str, desc: str, data: dict) -> ResultPackage:
            ctx = packer.pack(task_description=desc, input_data=data)
            child = ContextAwareSubAgent(agent_id=agent_id, context_package=ctx)
            child.start_execution()
            return await child.complete_task(
                output_data={"result": f"{agent_id}_done"},
                knowledge_updates={"task": agent_id, "status": "completed"},
            )

        results = await asyncio.gather(
            *[execute_subtask(agent_id, desc, data) for agent_id, desc, data in tasks]
        )

        # 处理所有结果
        pipeline = ResultProcessingPipeline(
            coordinator_id="main_coordinator",
            knowledge_manager=knowledge_manager,
        )

        all_tracking_ids = []
        all_knowledge_ids = []

        for result_pkg in results:
            processing_result = pipeline.process(result_pkg)
            assert processing_result.success
            all_tracking_ids.append(processing_result.tracking_id)
            all_knowledge_ids.extend(processing_result.knowledge_entry_ids)

        # 验证所有结果都有独立追踪 ID
        assert len(set(all_tracking_ids)) == 3  # 每个都是唯一的

        # 验证知识都已写入
        assert len(all_knowledge_ids) > 0
        for entry_id in all_knowledge_ids:
            assert knowledge_manager.get(entry_id) is not None

    @pytest.mark.asyncio
    async def test_failed_result_handling(self) -> None:
        """
        测试失败结果处理

        场景：子 Agent 执行失败，结果包标记为 failed
        """
        packer = ContextPacker(agent_id="coordinator")
        context_pkg = packer.pack(
            task_description="可能失败的任务",
            input_data={"risky": True},
        )

        child = ContextAwareSubAgent(
            agent_id="risky_worker",
            context_package=context_pkg,
        )
        child.start_execution()
        child.log("尝试执行风险操作")

        # 任务失败
        result_pkg = await child.fail_task(
            error_message="资源配额不足",
            error_code="QUOTA_EXCEEDED",
        )

        # 处理失败结果
        knowledge_manager = KnowledgeManager()
        pipeline = ResultProcessingPipeline(
            coordinator_id="coordinator",
            knowledge_manager=knowledge_manager,
        )

        processing_result = pipeline.process(result_pkg)

        # 失败结果也应该被处理
        assert processing_result.tracking_id is not None
        # 但不应该写入知识库
        assert len(processing_result.knowledge_entry_ids) == 0

        # 验证审计日志记录了失败
        audit_log = pipeline.get_audit_log(result_pkg.result_id)
        assert any(log["event"] == "result_received" for log in audit_log)


class TestKnowledgeIntegration:
    """知识库集成测试"""

    def test_knowledge_searchable_after_write(self) -> None:
        """测试写入的知识可搜索"""
        knowledge_manager = KnowledgeManager()
        writer = KnowledgeWriter(knowledge_manager)

        unpacked = UnpackedResult(
            result_id="res_search_001",
            context_package_id="ctx_search_001",
            agent_id="analyzer",
            status="completed",
            output={},
            logs=[],
            new_knowledge={
                "insights": "Python 异步编程提高了性能",
                "facts": ["asyncio 是标准库", "await 用于等待协程"],
            },
            errors=[],
        )

        writer.write_from_result(unpacked)

        # 搜索关键词
        search_results = knowledge_manager.search("asyncio")

        assert len(search_results) > 0
        assert any("asyncio" in r["content"] for r in search_results)

    def test_knowledge_tagged_correctly(self) -> None:
        """测试知识正确标记"""
        knowledge_manager = KnowledgeManager()
        writer = KnowledgeWriter(knowledge_manager)

        unpacked = UnpackedResult(
            result_id="res_tag_001",
            context_package_id="ctx_tag_001",
            agent_id="worker",
            status="completed",
            output={},
            logs=[],
            new_knowledge={"discovery": "新发现"},
            errors=[],
        )

        entry_ids = writer.write_from_result(
            unpacked,
            tags=["important", "verified"],
        )

        entry = knowledge_manager.get(entry_ids[0])

        assert "important" in entry["tags"]
        assert "verified" in entry["tags"]
        assert "worker" in entry["tags"]  # agent_id 也应该作为标签


class TestTracingAcrossWorkflow:
    """工作流追踪测试"""

    @pytest.mark.asyncio
    async def test_tracking_id_consistency(self) -> None:
        """测试追踪 ID 一致性"""
        packer = ContextPacker(agent_id="coordinator")
        context_pkg = packer.pack(
            task_description="带追踪的任务",
        )

        child = ContextAwareSubAgent(
            agent_id="tracked_worker",
            context_package=context_pkg,
        )
        child.start_execution()

        result_pkg = await child.complete_task(
            output_data={"done": True},
            knowledge_updates={"fact": "追踪测试"},
        )

        knowledge_manager = KnowledgeManager()
        pipeline = ResultProcessingPipeline(
            coordinator_id="coordinator",
            knowledge_manager=knowledge_manager,
        )

        processing_result = pipeline.process(result_pkg)
        tracking_id = processing_result.tracking_id

        # 验证审计日志中所有事件都有相同的 tracking_id
        audit_log = pipeline.get_audit_log(result_pkg.result_id)

        for entry in audit_log:
            assert entry["tracking_id"] == tracking_id

    def test_monitor_tracks_multiple_results(self) -> None:
        """测试监控器追踪多个结果"""
        monitor = CoordinatorResultMonitor(coordinator_id="coord_multi")

        results = [
            ResultPackage(
                result_id=f"res_multi_{i}",
                context_package_id=f"ctx_multi_{i}",
                agent_id="worker",
                status="completed",
                output_data={},
            )
            for i in range(5)
        ]

        tracking_ids = []
        for result in results:
            monitor.log_result_received(result)
            tracking_ids.append(monitor.get_tracking_id(result.result_id))

        # 验证每个结果都有唯一的追踪 ID
        assert len(set(tracking_ids)) == 5

        # 验证可以获取每个结果的处理追踪
        for result in results:
            trace = monitor.get_processing_trace(result.result_id)
            assert len(trace) == 1  # 只有 result_received 事件


class TestMemoryUpdateStrategies:
    """记忆更新策略测试"""

    def test_incremental_vs_replace_strategy(self) -> None:
        """测试增量与替换策略差异"""
        unpacked = UnpackedResult(
            result_id="res_strategy",
            context_package_id="ctx_strategy",
            agent_id="worker",
            status="completed",
            output={"data": "value"},
            logs=[],
            new_knowledge={},
            errors=[],
        )

        # 增量策略
        inc_updater = MemoryUpdater(strategy=UpdateStrategy.INCREMENTAL)
        inc_update = inc_updater.prepare_mid_term_update(unpacked)
        assert inc_update["strategy"] == "incremental"

        # 替换策略
        rep_updater = MemoryUpdater(strategy=UpdateStrategy.REPLACE)
        rep_update = rep_updater.prepare_mid_term_update(unpacked)
        assert rep_update["strategy"] == "replace"


class TestSchemaValidation:
    """Schema 验证测试"""

    def test_validate_complete_result(self) -> None:
        """测试验证完整结果"""
        valid_result = {
            "result_id": "res_001",
            "context_package_id": "ctx_001",
            "agent_id": "worker",
            "status": "completed",
            "output": {"key": "value"},
            "logs": [{"msg": "log"}],
            "new_knowledge": {"fact": "info"},
            "errors": [],
        }

        is_valid, errors = validate_result_schema(valid_result)
        assert is_valid
        assert len(errors) == 0

    def test_validate_minimal_result(self) -> None:
        """测试验证最小结果"""
        minimal_result = {
            "result_id": "res_min",
            "context_package_id": "ctx_min",
            "agent_id": "worker",
            "status": "completed",
            "output": {},
        }

        is_valid, errors = validate_result_schema(minimal_result)
        assert is_valid

    def test_validate_detects_missing_fields(self) -> None:
        """测试验证检测缺失字段"""
        incomplete = {
            "result_id": "res_inc",
            # 缺少其他必需字段
        }

        is_valid, errors = validate_result_schema(incomplete)
        assert not is_valid
        assert len(errors) > 0


class TestResultPackageIntegrationWithContextProtocol:
    """结果包与上下文协议集成测试"""

    @pytest.mark.asyncio
    async def test_context_to_result_id_chain(self) -> None:
        """测试上下文到结果的 ID 链追踪"""
        # 创建上下文
        packer = ContextPacker(agent_id="parent")
        context_pkg = packer.pack(
            task_description="ID 链测试",
        )
        context_id = context_pkg.package_id

        # 执行任务
        child = ContextAwareSubAgent(
            agent_id="child",
            context_package=context_pkg,
        )
        child.start_execution()

        result_pkg = await child.complete_task(
            output_data={"traced": True},
            knowledge_updates={"trace_test": "success"},
        )
        result_id = result_pkg.result_id

        # 处理结果
        knowledge_manager = KnowledgeManager()
        pipeline = ResultProcessingPipeline(
            coordinator_id="parent",
            knowledge_manager=knowledge_manager,
        )

        processing_result = pipeline.process(result_pkg)

        # 验证 ID 链
        # context_id -> result_id -> tracking_id -> knowledge_entry_ids
        assert result_pkg.context_package_id == context_id
        assert processing_result.result_id == result_id

        # 知识条目应该记录来源
        for entry_id in processing_result.knowledge_entry_ids:
            entry = knowledge_manager.get(entry_id)
            assert entry["metadata"]["source_result_id"] == result_id
            assert entry["metadata"]["source_context_id"] == context_id
