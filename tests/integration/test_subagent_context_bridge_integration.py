"""
子 Agent 上下文桥接器集成测试

测试完整的父→子→父循环，包含真实场景：
1. 协调器创建子任务并注入上下文
2. 子 Agent 执行任务并返回结果
3. 协调器接收结果并继续处理
4. 日志追踪贯穿全流程
"""

import asyncio
import json
from datetime import datetime

import pytest

from src.domain.services.context_protocol import (
    ContextPackage,
    ContextPacker,
    ContextUnpacker,
)
from src.domain.services.subagent_context_bridge import (
    ContextAwareSubAgent,
    ContextInjectionError,
    ContextTracingLogger,
    ResultPackage,
    SubAgentContextBridge,
    validate_result_package,
)


class TestEndToEndParentChildCycle:
    """端到端父子循环集成测试"""

    @pytest.mark.asyncio
    async def test_complete_data_analysis_workflow(self) -> None:
        """
        测试完整的数据分析工作流

        场景：
        1. 协调器接收用户请求"分析销售数据"
        2. 协调器创建上下文包分配给数据分析子 Agent
        3. 数据分析子 Agent 执行分析
        4. 子 Agent 返回结果给协调器
        5. 协调器汇总结果返回给用户
        """
        # ==== 步骤 1: 协调器创建上下文包 ====
        coordinator_packer = ContextPacker(agent_id="coordinator_001")

        context_pkg = coordinator_packer.pack(
            task_description="分析 2024 年 Q3 销售数据，计算环比增长率",
            constraints=[
                "使用中文输出",
                "保留两位小数",
                "标注数据来源",
            ],
            input_data={
                "sales_data": {
                    "q2": {"revenue": 1000000, "orders": 500},
                    "q3": {"revenue": 1200000, "orders": 600},
                },
                "period": "Q3 2024",
            },
            relevant_knowledge={
                "calculation_method": "环比增长率 = (本期 - 上期) / 上期 * 100%",
            },
            target_agent_id="data_analyzer",
            priority=5,
        )

        # 验证上下文包已创建
        assert context_pkg.package_id.startswith("ctx_")
        assert context_pkg.parent_agent_id == "coordinator_001"
        assert context_pkg.target_agent_id == "data_analyzer"

        # ==== 步骤 2: 桥接器注入上下文 ====
        bridge = SubAgentContextBridge(parent_agent_id="coordinator_001")
        subagent_config = bridge.inject_context(context_pkg, "data_analyzer")

        assert subagent_config["context_package_id"] == context_pkg.package_id
        assert subagent_config["priority"] == 5

        # ==== 步骤 3: 子 Agent 启动并加载上下文 ====
        analyzer = ContextAwareSubAgent(
            agent_id="data_analyzer",
            context_package=context_pkg,
        )

        # 验证上下文已加载到工作记忆
        working_memory = analyzer.get_working_memory()
        assert working_memory["context_id"] == context_pkg.package_id
        assert "销售数据" in working_memory["task"]
        assert working_memory["input"]["sales_data"]["q3"]["revenue"] == 1200000

        # ==== 步骤 4: 子 Agent 执行分析任务 ====
        analyzer.start_execution()
        analyzer.log("开始分析销售数据")

        # 模拟分析逻辑
        q2_revenue = working_memory["input"]["sales_data"]["q2"]["revenue"]
        q3_revenue = working_memory["input"]["sales_data"]["q3"]["revenue"]
        growth_rate = (q3_revenue - q2_revenue) / q2_revenue * 100

        analyzer.log(f"计算环比增长率: {growth_rate:.2f}%")
        analyzer.log("分析完成")

        # ==== 步骤 5: 子 Agent 返回结果 ====
        result_pkg = await analyzer.complete_task(
            output_data={
                "analysis_result": {
                    "revenue_growth_rate": f"{growth_rate:.2f}%",
                    "revenue_change": q3_revenue - q2_revenue,
                    "orders_growth_rate": "20.00%",
                    "conclusion": "Q3 销售表现良好，收入环比增长 20%",
                },
                "data_source": "internal_sales_db",
            },
            knowledge_updates={
                "q3_performance": "positive",
                "growth_trend": "upward",
            },
        )

        # ==== 步骤 6: 验证结果 ====
        assert result_pkg.context_package_id == context_pkg.package_id
        assert result_pkg.status == "completed"
        assert result_pkg.result_id.startswith("res_")
        assert "20.00%" in result_pkg.output_data["analysis_result"]["revenue_growth_rate"]
        assert result_pkg.knowledge_updates["growth_trend"] == "upward"

        # 验证执行时间已记录
        assert result_pkg.execution_time_ms >= 0
        assert result_pkg.started_at is not None
        assert result_pkg.completed_at is not None

        # 验证日志追踪
        assert len(result_pkg.execution_logs) >= 3  # 至少 3 条用户日志 + 自动日志
        assert any("开始分析" in log["message"] for log in result_pkg.execution_logs)

    @pytest.mark.asyncio
    async def test_multi_step_workflow_with_multiple_subagents(self) -> None:
        """
        测试多子 Agent 协作工作流

        场景：协调器分配多个子任务给不同的子 Agent
        """
        coordinator_packer = ContextPacker(agent_id="main_coordinator")
        SubAgentContextBridge(parent_agent_id="main_coordinator")

        # 定义子任务
        subtasks = [
            {
                "agent_id": "data_fetcher",
                "description": "从数据库获取原始数据",
                "input": {"query": "SELECT * FROM sales WHERE year=2024"},
            },
            {
                "agent_id": "data_cleaner",
                "description": "清洗数据，处理缺失值",
                "input": {"rules": ["remove_nulls", "trim_whitespace"]},
            },
            {
                "agent_id": "report_generator",
                "description": "生成分析报告",
                "input": {"format": "markdown", "sections": ["summary", "charts"]},
            },
        ]

        # 并行创建上下文和子 Agent
        contexts = []
        children = []

        for task in subtasks:
            ctx = coordinator_packer.pack(
                task_description=task["description"],
                input_data=task["input"],
                target_agent_id=task["agent_id"],
            )
            contexts.append(ctx)

            child = ContextAwareSubAgent(
                agent_id=task["agent_id"],
                context_package=ctx,
            )
            children.append(child)

        # 并行执行所有子任务
        async def execute_task(child: ContextAwareSubAgent, task_num: int):
            child.start_execution()
            child.log(f"执行任务 {task_num}")
            await asyncio.sleep(0.05)  # 模拟处理时间
            return await child.complete_task(
                output_data={"task_num": task_num, "status": "success"}
            )

        results = await asyncio.gather(
            *[execute_task(child, i + 1) for i, child in enumerate(children)]
        )

        # 验证所有结果
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.status == "completed"
            assert result.context_package_id == contexts[i].package_id
            assert result.output_data["status"] == "success"

    @pytest.mark.asyncio
    async def test_hierarchical_delegation_three_levels(self) -> None:
        """
        测试三层级层次委托

        场景：
        根协调器 → 子协调器 → 执行器
        """
        # ==== Level 0: 根协调器 ====
        root_packer = ContextPacker(agent_id="root_coordinator")
        root_context = root_packer.pack(
            task_description="完成复杂分析任务",
            constraints=["全局超时 30 秒", "优先保证数据准确性"],
            relevant_knowledge={"global_config": {"timeout": 30, "retry": 3}},
        )

        # ==== Level 1: 子协调器 ====
        sub_coordinator = ContextAwareSubAgent(
            agent_id="sub_coordinator",
            context_package=root_context,
        )
        sub_coordinator.start_execution()

        # 子协调器创建新的上下文给执行器
        sub_packer = ContextPacker(agent_id="sub_coordinator")

        # 继承约束并添加新约束
        inherited_constraints = sub_coordinator.constraints + ["子任务超时 10 秒"]

        # 继承全局知识
        inherited_knowledge = {
            **root_context.relevant_knowledge,
            "sub_config": {"batch_size": 100},
        }

        executor_context = sub_packer.pack(
            task_description="执行数据处理子任务",
            constraints=inherited_constraints,
            relevant_knowledge=inherited_knowledge,
        )

        # ==== Level 2: 执行器 ====
        executor = ContextAwareSubAgent(
            agent_id="executor",
            context_package=executor_context,
        )

        # 验证约束继承
        assert "全局超时 30 秒" in executor.constraints
        assert "子任务超时 10 秒" in executor.constraints

        # 验证知识继承
        wm = executor.get_working_memory()
        assert wm["knowledge"]["global_config"]["timeout"] == 30
        assert wm["knowledge"]["sub_config"]["batch_size"] == 100

        # 执行器完成任务
        executor.start_execution()
        executor_result = await executor.complete_task(output_data={"processed_count": 100})

        # 子协调器收到结果后完成任务
        sub_result = await sub_coordinator.complete_task(
            output_data={
                "sub_task_result": executor_result.to_dict(),
                "aggregated_count": 100,
            },
            knowledge_updates={"processing_complete": True},
        )

        # 验证结果链
        assert executor_result.status == "completed"
        assert sub_result.status == "completed"
        assert sub_result.knowledge_updates["processing_complete"] is True


class TestErrorHandlingScenarios:
    """错误处理场景测试"""

    @pytest.mark.asyncio
    async def test_subagent_failure_propagation(self) -> None:
        """测试子 Agent 失败结果传播"""
        packer = ContextPacker(agent_id="coordinator")
        context_pkg = packer.pack(
            task_description="可能失败的任务",
            input_data={"risky_operation": True},
        )

        child = ContextAwareSubAgent(
            agent_id="risky_worker",
            context_package=context_pkg,
        )
        child.start_execution()
        child.log("开始执行风险操作")
        child.log("检测到资源不足", level="WARNING")

        # 任务失败
        result = await child.fail_task(
            error_message="资源配额不足，无法完成操作",
            error_code="RESOURCE_QUOTA_EXCEEDED",
        )

        # 验证失败结果
        assert result.status == "failed"
        assert result.error_message == "资源配额不足，无法完成操作"
        assert result.error_code == "RESOURCE_QUOTA_EXCEEDED"
        assert result.context_package_id == context_pkg.package_id

        # 验证日志包含失败信息
        error_logs = [log for log in result.execution_logs if log["level"] == "ERROR"]
        assert len(error_logs) >= 1

    def test_invalid_context_injection_raises_error(self) -> None:
        """测试无效上下文注入抛出错误"""
        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        # 空任务描述
        invalid_context = ContextPackage(
            package_id="ctx_invalid",
            task_description="",  # 无效
        )

        with pytest.raises(ContextInjectionError) as exc_info:
            bridge.inject_context(invalid_context, "target_agent")

        assert "task_description" in str(exc_info.value)

    def test_empty_target_agent_id_raises_error(self) -> None:
        """测试空目标 Agent ID 抛出错误"""
        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        valid_context = ContextPackage(
            package_id="ctx_valid",
            task_description="有效任务",
        )

        with pytest.raises(ContextInjectionError):
            bridge.inject_context(valid_context, "")  # 空 ID


class TestTracingAndLogging:
    """追踪和日志测试"""

    @pytest.mark.asyncio
    async def test_full_tracing_across_workflow(self) -> None:
        """测试工作流全流程追踪"""
        packer = ContextPacker(agent_id="coordinator")
        context_pkg = packer.pack(
            task_description="带追踪的任务",
        )

        # 创建追踪日志器
        tracer = ContextTracingLogger(context_id=context_pkg.package_id)

        # 协调器日志
        tracer.info("协调器分配任务")

        # 子 Agent 执行
        child = ContextAwareSubAgent(
            agent_id="worker",
            context_package=context_pkg,
        )
        child.start_execution()
        child.log("工作器执行中")

        result = await child.complete_task(output_data={"done": True})

        # 设置结果 ID 后的追踪
        tracer.result_id = result.result_id
        final_log = tracer.info("任务完成，结果已接收")

        # 验证追踪信息
        assert final_log["context_id"] == context_pkg.package_id
        assert final_log["result_id"] == result.result_id

        # 验证所有日志都包含 context_id
        all_logs = tracer.get_logs()
        for log in all_logs:
            assert "context_id" in log
            assert log["context_id"] == context_pkg.package_id

    def test_log_levels_captured_correctly(self) -> None:
        """测试日志级别正确捕获"""
        tracer = ContextTracingLogger(context_id="ctx_levels_test")

        debug_log = tracer.debug("调试信息")
        info_log = tracer.info("普通信息")
        warning_log = tracer.warning("警告信息")
        error_log = tracer.error("错误信息")

        assert debug_log["level"] == "DEBUG"
        assert info_log["level"] == "INFO"
        assert warning_log["level"] == "WARNING"
        assert error_log["level"] == "ERROR"

        all_logs = tracer.get_logs()
        assert len(all_logs) == 4


class TestResultPackageSerialization:
    """结果包序列化测试"""

    def test_result_package_roundtrip_json(self) -> None:
        """测试结果包 JSON 往返序列化"""
        original = ResultPackage(
            result_id="res_test_001",
            context_package_id="ctx_test_001",
            agent_id="test_agent",
            status="completed",
            output_data={"key": "value", "nested": {"a": 1}},
            execution_logs=[
                {"timestamp": "2024-01-01T00:00:00", "message": "log1"},
                {"timestamp": "2024-01-01T00:00:01", "message": "log2"},
            ],
            knowledge_updates={"fact": "新知识"},
            execution_time_ms=1500,
            started_at=datetime(2024, 1, 1, 0, 0, 0),
            completed_at=datetime(2024, 1, 1, 0, 0, 1),
        )

        # 序列化
        json_str = original.to_json()
        json.loads(json_str)  # Validate JSON is parseable

        # 反序列化
        restored = ResultPackage.from_json(json_str)

        # 验证
        assert restored.result_id == original.result_id
        assert restored.context_package_id == original.context_package_id
        assert restored.output_data == original.output_data
        assert len(restored.execution_logs) == 2
        assert restored.execution_time_ms == 1500

    def test_validate_completed_result_package(self) -> None:
        """测试验证完成状态的结果包"""
        valid_pkg = ResultPackage(
            result_id="res_valid",
            context_package_id="ctx_valid",
            agent_id="agent",
            status="completed",
            output_data={"result": "success"},
        )

        is_valid, errors = validate_result_package(valid_pkg)
        assert is_valid
        assert len(errors) == 0

    def test_validate_invalid_status(self) -> None:
        """测试验证无效状态"""
        invalid_pkg = ResultPackage(
            result_id="res_invalid",
            context_package_id="ctx_invalid",
            agent_id="agent",
            status="unknown_status",
            output_data={},
        )

        is_valid, errors = validate_result_package(invalid_pkg)
        assert not is_valid
        assert any("status" in err for err in errors)


class TestContextProtocolIntegration:
    """与 ContextProtocol 集成测试"""

    def test_packer_unpacker_bridge_integration(self) -> None:
        """测试打包器、解包器与桥接器集成"""
        # 打包
        packer = ContextPacker(agent_id="sender")
        pkg = packer.pack(
            task_description="集成测试任务",
            constraints=["约束1", "约束2"],
            input_data={"param": "value"},
        )

        # 桥接
        bridge = SubAgentContextBridge(parent_agent_id="sender")
        config = bridge.inject_context(pkg, "receiver")

        # 解包
        unpacker = ContextUnpacker(agent_id="receiver")
        unpacked = unpacker.unpack(pkg)

        # 验证数据一致性
        assert unpacked.task_description == "集成测试任务"
        assert config["task_description"] == unpacked.task_description
        assert len(unpacked.constraints) == 2

    def test_bridge_system_prompt_generation(self) -> None:
        """测试桥接器系统提示词生成"""
        packer = ContextPacker(agent_id="coordinator")
        pkg = packer.pack(
            task_description="生成报告任务",
            constraints=["简洁明了", "使用中文"],
            relevant_knowledge={"template": "quarterly_report"},
            input_data={"quarter": "Q3", "year": 2024},
        )

        bridge = SubAgentContextBridge(parent_agent_id="coordinator")
        system_prompt = bridge.build_system_prompt(pkg)

        # 验证系统提示词包含所有必要信息
        assert "生成报告任务" in system_prompt
        assert "简洁明了" in system_prompt
        assert "使用中文" in system_prompt
        assert "quarterly_report" in system_prompt
        assert "Q3" in system_prompt
