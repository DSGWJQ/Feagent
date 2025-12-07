"""子 Agent 上下文传递测试

测试覆盖：
1. ResultPackage 结果包数据结构
2. SubAgentContextBridge 上下文桥接器
3. 父 Agent 创建子 Agent 时上下文注入
4. 子 Agent 加载上下文到工作记忆
5. 子 Agent 打包结果返回父 Agent
6. 日志追踪（上下文 ID 和结果包 ID）
7. 父→子→父完整循环
"""

import json

import pytest


class TestResultPackageDataStructure:
    """结果包数据结构测试"""

    def test_result_package_has_required_fields(self) -> None:
        """测试结果包包含必要字段"""
        from src.domain.services.subagent_context_bridge import ResultPackage

        result_pkg = ResultPackage(
            result_id="res_001",
            context_package_id="ctx_001",
            agent_id="child_agent",
            status="completed",
            output_data={"answer": "分析结果"},
        )

        assert result_pkg.result_id == "res_001"
        assert result_pkg.context_package_id == "ctx_001"
        assert result_pkg.agent_id == "child_agent"
        assert result_pkg.status == "completed"
        assert result_pkg.output_data["answer"] == "分析结果"

    def test_result_package_includes_execution_logs(self) -> None:
        """测试结果包包含执行日志"""
        from src.domain.services.subagent_context_bridge import ResultPackage

        result_pkg = ResultPackage(
            result_id="res_002",
            context_package_id="ctx_002",
            agent_id="worker",
            status="completed",
            output_data={"result": "success"},
            execution_logs=[
                {"timestamp": "2024-01-01T10:00:00", "level": "INFO", "message": "开始执行"},
                {"timestamp": "2024-01-01T10:00:05", "level": "INFO", "message": "执行完成"},
            ],
        )

        assert len(result_pkg.execution_logs) == 2
        assert result_pkg.execution_logs[0]["level"] == "INFO"

    def test_result_package_includes_knowledge_updates(self) -> None:
        """测试结果包包含知识更新"""
        from src.domain.services.subagent_context_bridge import ResultPackage

        result_pkg = ResultPackage(
            result_id="res_003",
            context_package_id="ctx_003",
            agent_id="analyzer",
            status="completed",
            output_data={"analysis": "完成"},
            knowledge_updates={
                "new_facts": ["发现1", "发现2"],
                "updated_entities": {"company": "更新后的公司信息"},
            },
        )

        assert "new_facts" in result_pkg.knowledge_updates
        assert len(result_pkg.knowledge_updates["new_facts"]) == 2

    def test_result_package_to_dict_and_from_dict(self) -> None:
        """测试结果包序列化与反序列化"""
        from src.domain.services.subagent_context_bridge import ResultPackage

        original = ResultPackage(
            result_id="res_004",
            context_package_id="ctx_004",
            agent_id="test_agent",
            status="completed",
            output_data={"key": "value"},
            execution_logs=[{"msg": "log"}],
            knowledge_updates={"fact": "info"},
            execution_time_ms=150,
        )

        data = original.to_dict()
        restored = ResultPackage.from_dict(data)

        assert restored.result_id == original.result_id
        assert restored.context_package_id == original.context_package_id
        assert restored.output_data == original.output_data
        assert restored.execution_time_ms == 150

    def test_result_package_to_json(self) -> None:
        """测试结果包 JSON 序列化"""
        from src.domain.services.subagent_context_bridge import ResultPackage

        result_pkg = ResultPackage(
            result_id="res_005",
            context_package_id="ctx_005",
            agent_id="agent",
            status="completed",
            output_data={"data": 123},
        )

        json_str = result_pkg.to_json()
        parsed = json.loads(json_str)

        assert parsed["result_id"] == "res_005"
        assert parsed["context_package_id"] == "ctx_005"

    def test_result_package_failed_status_includes_error(self) -> None:
        """测试失败状态结果包包含错误信息"""
        from src.domain.services.subagent_context_bridge import ResultPackage

        result_pkg = ResultPackage(
            result_id="res_006",
            context_package_id="ctx_006",
            agent_id="failed_agent",
            status="failed",
            output_data={},
            error_message="任务执行超时",
            error_code="TIMEOUT",
        )

        assert result_pkg.status == "failed"
        assert result_pkg.error_message == "任务执行超时"
        assert result_pkg.error_code == "TIMEOUT"


class TestSubAgentContextBridge:
    """上下文桥接器测试"""

    def test_bridge_creation(self) -> None:
        """测试桥接器创建"""
        from src.domain.services.subagent_context_bridge import SubAgentContextBridge

        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        assert bridge.parent_agent_id == "coordinator"

    def test_bridge_inject_context_to_subagent(self) -> None:
        """测试向子 Agent 注入上下文"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import SubAgentContextBridge

        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        context_pkg = ContextPackage(
            package_id="ctx_inject_001",
            task_description="分析数据",
            constraints=["使用中文"],
            input_data={"data": [1, 2, 3]},
        )

        # 注入上下文到子 Agent 配置
        subagent_config = bridge.inject_context(
            context_package=context_pkg,
            target_agent_id="data_analyzer",
        )

        assert subagent_config["context_package_id"] == "ctx_inject_001"
        assert subagent_config["task_description"] == "分析数据"
        assert "使用中文" in subagent_config["constraints"]
        assert subagent_config["parent_agent_id"] == "coordinator"

    def test_bridge_inject_context_as_system_prompt(self) -> None:
        """测试将上下文注入为系统提示词"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import SubAgentContextBridge

        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        context_pkg = ContextPackage(
            package_id="ctx_prompt_001",
            task_description="生成报告",
            constraints=["专业术语", "简洁明了"],
            relevant_knowledge={"domain": "finance"},
        )

        system_prompt = bridge.build_system_prompt(context_pkg)

        assert "生成报告" in system_prompt
        assert "专业术语" in system_prompt
        assert "finance" in system_prompt

    def test_bridge_load_context_to_working_memory(self) -> None:
        """测试加载上下文到工作记忆"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import SubAgentContextBridge

        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        context_pkg = ContextPackage(
            package_id="ctx_memory_001",
            task_description="处理任务",
            short_term_context=["消息1", "消息2"],
            mid_term_context={"goal": "完成分析"},
        )

        working_memory = bridge.load_to_working_memory(context_pkg)

        assert working_memory["task"] == "处理任务"
        assert len(working_memory["short_term"]) == 2
        assert working_memory["mid_term"]["goal"] == "完成分析"
        assert working_memory["context_id"] == "ctx_memory_001"

    def test_bridge_create_result_package(self) -> None:
        """测试创建结果包"""
        from src.domain.services.subagent_context_bridge import SubAgentContextBridge

        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        result_pkg = bridge.create_result_package(
            context_package_id="ctx_result_001",
            agent_id="worker",
            output_data={"analysis": "完成"},
            execution_logs=[{"msg": "执行成功"}],
            knowledge_updates={"new_fact": "发现"},
            status="completed",
        )

        assert result_pkg.result_id.startswith("res_")
        assert result_pkg.context_package_id == "ctx_result_001"
        assert result_pkg.agent_id == "worker"
        assert result_pkg.status == "completed"

    def test_bridge_create_failed_result_package(self) -> None:
        """测试创建失败结果包"""
        from src.domain.services.subagent_context_bridge import SubAgentContextBridge

        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        result_pkg = bridge.create_result_package(
            context_package_id="ctx_fail_001",
            agent_id="failed_worker",
            output_data={},
            status="failed",
            error_message="执行错误",
            error_code="EXEC_ERROR",
        )

        assert result_pkg.status == "failed"
        assert result_pkg.error_message == "执行错误"
        assert result_pkg.error_code == "EXEC_ERROR"


class TestParentAgentContextInjection:
    """父 Agent 上下文注入测试"""

    def test_parent_creates_context_for_child(self) -> None:
        """测试父 Agent 为子 Agent 创建上下文"""
        from src.domain.services.context_protocol import ContextPacker
        from src.domain.services.subagent_context_bridge import SubAgentContextBridge

        # 父 Agent 创建上下文包
        packer = ContextPacker(agent_id="parent_coordinator")
        context_pkg = packer.pack(
            task_description="分析用户数据",
            constraints=["保护隐私", "数据脱敏"],
            input_data={"user_ids": [1, 2, 3]},
            target_agent_id="data_analyzer",
            priority=5,
        )

        # 通过桥接器注入上下文
        bridge = SubAgentContextBridge(parent_agent_id="parent_coordinator")
        subagent_init = bridge.inject_context(context_pkg, "data_analyzer")

        assert subagent_init["task_description"] == "分析用户数据"
        assert subagent_init["priority"] == 5
        assert subagent_init["parent_agent_id"] == "parent_coordinator"

    def test_parent_passes_memory_context_to_child(self) -> None:
        """测试父 Agent 传递记忆上下文给子 Agent"""
        from src.domain.services.context_protocol import ContextPacker
        from src.domain.services.subagent_context_bridge import SubAgentContextBridge

        packer = ContextPacker(agent_id="parent")

        # 包含记忆上下文
        context_pkg = packer.pack(
            task_description="继续分析",
            short_term_context=["用户问了销售数据", "助手回复正在查询"],
            mid_term_context={"session_goal": "完成季度报告"},
        )

        bridge = SubAgentContextBridge(parent_agent_id="parent")
        working_memory = bridge.load_to_working_memory(context_pkg)

        assert len(working_memory["short_term"]) == 2
        assert working_memory["mid_term"]["session_goal"] == "完成季度报告"


class TestChildAgentContextLoading:
    """子 Agent 上下文加载测试"""

    def test_child_loads_context_on_startup(self) -> None:
        """测试子 Agent 启动时加载上下文"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
        )

        context_pkg = ContextPackage(
            package_id="ctx_child_001",
            task_description="执行数据分析",
            constraints=["高效", "准确"],
            input_data={"dataset": "sales_2024"},
        )

        # 子 Agent 启动时加载上下文
        child_agent = ContextAwareSubAgent(
            agent_id="child_analyzer",
            context_package=context_pkg,
        )

        assert child_agent.context_package_id == "ctx_child_001"
        assert child_agent.task_description == "执行数据分析"
        assert "高效" in child_agent.constraints

    def test_child_working_memory_initialized(self) -> None:
        """测试子 Agent 工作记忆初始化"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
        )

        context_pkg = ContextPackage(
            package_id="ctx_wm_001",
            task_description="任务",
            short_term_context=["msg1", "msg2"],
            mid_term_context={"key": "value"},
        )

        child_agent = ContextAwareSubAgent(
            agent_id="child",
            context_package=context_pkg,
        )

        wm = child_agent.get_working_memory()

        assert wm["context_id"] == "ctx_wm_001"
        assert len(wm["short_term"]) == 2
        assert wm["mid_term"]["key"] == "value"


class TestChildAgentResultPackaging:
    """子 Agent 结果打包测试"""

    @pytest.mark.asyncio
    async def test_child_packages_result_on_completion(self) -> None:
        """测试子 Agent 完成时打包结果"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
        )

        context_pkg = ContextPackage(
            package_id="ctx_complete_001",
            task_description="执行任务",
        )

        child_agent = ContextAwareSubAgent(
            agent_id="worker",
            context_package=context_pkg,
        )

        # 模拟任务执行
        result_pkg = await child_agent.complete_task(
            output_data={"result": "成功完成"},
            knowledge_updates={"learned": "新知识"},
        )

        assert result_pkg.context_package_id == "ctx_complete_001"
        assert result_pkg.agent_id == "worker"
        assert result_pkg.status == "completed"
        assert result_pkg.output_data["result"] == "成功完成"

    @pytest.mark.asyncio
    async def test_child_packages_failure_result(self) -> None:
        """测试子 Agent 失败时打包结果"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
        )

        context_pkg = ContextPackage(
            package_id="ctx_fail_002",
            task_description="可能失败的任务",
        )

        child_agent = ContextAwareSubAgent(
            agent_id="risky_worker",
            context_package=context_pkg,
        )

        result_pkg = await child_agent.fail_task(
            error_message="资源不足",
            error_code="RESOURCE_EXHAUSTED",
        )

        assert result_pkg.status == "failed"
        assert result_pkg.error_message == "资源不足"
        assert result_pkg.context_package_id == "ctx_fail_002"

    @pytest.mark.asyncio
    async def test_child_includes_execution_logs(self) -> None:
        """测试子 Agent 结果包含执行日志"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
        )

        context_pkg = ContextPackage(
            package_id="ctx_log_001",
            task_description="带日志的任务",
        )

        child_agent = ContextAwareSubAgent(
            agent_id="logging_worker",
            context_package=context_pkg,
        )

        # 添加执行日志
        child_agent.log("开始执行任务")
        child_agent.log("处理数据中...")
        child_agent.log("任务完成")

        result_pkg = await child_agent.complete_task(
            output_data={"status": "done"},
        )

        # 3 条用户日志 + 1 条自动的 "执行完成" 日志
        assert len(result_pkg.execution_logs) == 4
        assert "开始执行任务" in result_pkg.execution_logs[0]["message"]
        assert "执行完成" in result_pkg.execution_logs[3]["message"]


class TestLoggingAndTracing:
    """日志追踪测试"""

    def test_context_id_in_logs(self) -> None:
        """测试日志中包含上下文 ID"""
        from src.domain.services.subagent_context_bridge import ContextTracingLogger

        logger = ContextTracingLogger(context_id="ctx_trace_001")

        log_entry = logger.info("执行操作")

        assert log_entry["context_id"] == "ctx_trace_001"
        assert log_entry["level"] == "INFO"
        assert "执行操作" in log_entry["message"]

    def test_result_id_in_logs(self) -> None:
        """测试日志中包含结果 ID"""
        from src.domain.services.subagent_context_bridge import ContextTracingLogger

        logger = ContextTracingLogger(
            context_id="ctx_trace_002",
            result_id="res_trace_001",
        )

        log_entry = logger.info("完成任务")

        assert log_entry["context_id"] == "ctx_trace_002"
        assert log_entry["result_id"] == "res_trace_001"

    def test_logger_captures_all_levels(self) -> None:
        """测试日志记录器捕获所有级别"""
        from src.domain.services.subagent_context_bridge import ContextTracingLogger

        logger = ContextTracingLogger(context_id="ctx_levels")

        debug_log = logger.debug("调试信息")
        info_log = logger.info("普通信息")
        warning_log = logger.warning("警告信息")
        error_log = logger.error("错误信息")

        assert debug_log["level"] == "DEBUG"
        assert info_log["level"] == "INFO"
        assert warning_log["level"] == "WARNING"
        assert error_log["level"] == "ERROR"

    def test_logger_get_all_logs(self) -> None:
        """测试获取所有日志"""
        from src.domain.services.subagent_context_bridge import ContextTracingLogger

        logger = ContextTracingLogger(context_id="ctx_all_logs")

        logger.info("日志1")
        logger.info("日志2")
        logger.warning("日志3")

        all_logs = logger.get_logs()

        assert len(all_logs) == 3


class TestParentChildCommunicationCycle:
    """父子 Agent 通信循环测试"""

    @pytest.mark.asyncio
    async def test_full_parent_child_parent_cycle(self) -> None:
        """测试完整的父→子→父循环"""
        from src.domain.services.context_protocol import ContextPacker
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
            SubAgentContextBridge,
        )

        # 1. 父 Agent 创建上下文包
        parent_packer = ContextPacker(agent_id="coordinator")
        context_pkg = parent_packer.pack(
            task_description="分析销售数据",
            constraints=["使用中文", "数据脱敏"],
            input_data={"sales_data": [100, 200, 300]},
            target_agent_id="analyzer",
        )

        # 2. 通过桥接器注入上下文
        bridge = SubAgentContextBridge(parent_agent_id="coordinator")
        bridge.inject_context(context_pkg, "analyzer")

        # 3. 子 Agent 启动并加载上下文
        child_agent = ContextAwareSubAgent(
            agent_id="analyzer",
            context_package=context_pkg,
        )

        assert child_agent.task_description == "分析销售数据"

        # 4. 子 Agent 执行任务并返回结果
        result_pkg = await child_agent.complete_task(
            output_data={
                "analysis": "销售趋势向上",
                "total": 600,
                "average": 200,
            },
            knowledge_updates={
                "trend": "上升",
                "period": "Q3",
            },
        )

        # 5. 父 Agent 接收结果
        assert result_pkg.context_package_id == context_pkg.package_id
        assert result_pkg.status == "completed"
        assert result_pkg.output_data["total"] == 600

        # 6. 验证可追溯性
        assert result_pkg.context_package_id.startswith("ctx_")
        assert result_pkg.result_id.startswith("res_")

    @pytest.mark.asyncio
    async def test_multi_child_parallel_execution(self) -> None:
        """测试多个子 Agent 并行执行"""
        from src.domain.services.context_protocol import ContextPacker
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
            SubAgentContextBridge,
        )

        parent_packer = ContextPacker(agent_id="coordinator")
        SubAgentContextBridge(parent_agent_id="coordinator")

        # 创建多个子任务上下文
        contexts = []
        for i in range(3):
            ctx = parent_packer.pack(
                task_description=f"子任务{i+1}",
                input_data={"task_num": i + 1},
            )
            contexts.append(ctx)

        # 创建多个子 Agent
        children = []
        for i, ctx in enumerate(contexts):
            child = ContextAwareSubAgent(
                agent_id=f"worker_{i+1}",
                context_package=ctx,
            )
            children.append(child)

        # 并行执行
        import asyncio

        results = await asyncio.gather(
            *[
                child.complete_task(output_data={"result": f"完成任务{i+1}"})
                for i, child in enumerate(children)
            ]
        )

        # 验证结果
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.status == "completed"
            assert result.context_package_id == contexts[i].package_id

    @pytest.mark.asyncio
    async def test_hierarchical_context_passing(self) -> None:
        """测试层级上下文传递"""
        from src.domain.services.context_protocol import ContextPacker
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
            SubAgentContextBridge,
        )

        # 根协调器创建任务
        root_packer = ContextPacker(agent_id="root_coordinator")
        root_context = root_packer.pack(
            task_description="复杂分析任务",
            constraints=["全局约束"],
            relevant_knowledge={"global_config": {"timeout": 30}},
        )

        # Level 1: 子协调器
        sub_coordinator = ContextAwareSubAgent(
            agent_id="sub_coordinator",
            context_package=root_context,
        )

        # 子协调器继承上下文并创建下级任务
        sub_packer = ContextPacker(agent_id="sub_coordinator")
        SubAgentContextBridge(parent_agent_id="sub_coordinator")

        # 继承约束并添加新约束
        inherited_constraints = sub_coordinator.constraints + ["子级约束"]
        sub_context = sub_packer.pack(
            task_description="子分析任务",
            constraints=inherited_constraints,
            relevant_knowledge={
                **root_context.relevant_knowledge,
                "sub_config": {"batch_size": 100},
            },
        )

        # Level 2: 执行器
        executor = ContextAwareSubAgent(
            agent_id="executor",
            context_package=sub_context,
        )

        # 验证约束继承
        assert "全局约束" in executor.constraints
        assert "子级约束" in executor.constraints

        # 验证配置继承
        wm = executor.get_working_memory()
        assert wm["knowledge"]["global_config"]["timeout"] == 30


class TestContextBridgeWithSubAgentScheduler:
    """上下文桥接器与 SubAgent 调度器集成测试"""

    @pytest.mark.asyncio
    async def test_bridge_with_registry(self) -> None:
        """测试桥接器与注册表集成"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.sub_agent_scheduler import (
            SubAgentRegistry,
        )
        from src.domain.services.subagent_context_bridge import (
            SubAgentContextBridge,
        )

        # 创建注册表
        registry = SubAgentRegistry()

        # 创建上下文
        context_pkg = ContextPackage(
            package_id="ctx_registry_001",
            task_description="测试任务",
        )

        # 使用工厂创建上下文感知的子 Agent
        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        # 验证桥接器可以与注册表协作
        assert bridge.parent_agent_id == "coordinator"
        assert registry is not None
        assert context_pkg.package_id == "ctx_registry_001"


class TestContextPackageValidation:
    """上下文包验证测试"""

    def test_validate_context_before_injection(self) -> None:
        """测试注入前验证上下文"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import (
            ContextInjectionError,
            SubAgentContextBridge,
        )

        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        # 创建无效上下文（空任务描述）
        invalid_context = ContextPackage(
            package_id="ctx_invalid",
            task_description="",  # 空描述
        )

        with pytest.raises(ContextInjectionError) as exc_info:
            bridge.inject_context(invalid_context, "target")

        assert "task_description" in str(exc_info.value)

    def test_validate_target_agent_id(self) -> None:
        """测试验证目标 Agent ID"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import (
            ContextInjectionError,
            SubAgentContextBridge,
        )

        bridge = SubAgentContextBridge(parent_agent_id="coordinator")

        context_pkg = ContextPackage(
            package_id="ctx_target",
            task_description="任务",
        )

        with pytest.raises(ContextInjectionError):
            bridge.inject_context(context_pkg, "")  # 空目标 ID


class TestResultPackageValidation:
    """结果包验证测试"""

    def test_validate_result_package_on_creation(self) -> None:
        """测试创建时验证结果包"""
        from src.domain.services.subagent_context_bridge import (
            ResultPackage,
            validate_result_package,
        )

        valid_pkg = ResultPackage(
            result_id="res_valid",
            context_package_id="ctx_valid",
            agent_id="agent",
            status="completed",
            output_data={"data": "value"},
        )

        is_valid, errors = validate_result_package(valid_pkg)
        assert is_valid
        assert len(errors) == 0

    def test_detect_invalid_status(self) -> None:
        """测试检测无效状态"""
        from src.domain.services.subagent_context_bridge import (
            ResultPackage,
            validate_result_package,
        )

        invalid_pkg = ResultPackage(
            result_id="res_invalid",
            context_package_id="ctx_invalid",
            agent_id="agent",
            status="unknown_status",  # 无效状态
            output_data={},
        )

        is_valid, errors = validate_result_package(invalid_pkg)
        assert not is_valid
        assert any("status" in err for err in errors)


class TestExecutionTimeMeasurement:
    """执行时间测量测试"""

    @pytest.mark.asyncio
    async def test_result_includes_execution_time(self) -> None:
        """测试结果包含执行时间"""
        import asyncio

        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
        )

        context_pkg = ContextPackage(
            package_id="ctx_time_001",
            task_description="耗时任务",
        )

        child_agent = ContextAwareSubAgent(
            agent_id="timed_worker",
            context_package=context_pkg,
        )

        # 模拟耗时操作
        child_agent.start_execution()
        await asyncio.sleep(0.1)  # 100ms

        result_pkg = await child_agent.complete_task(
            output_data={"done": True},
        )

        assert result_pkg.execution_time_ms >= 100

    @pytest.mark.asyncio
    async def test_timestamps_in_result(self) -> None:
        """测试结果包含时间戳"""
        from src.domain.services.context_protocol import ContextPackage
        from src.domain.services.subagent_context_bridge import (
            ContextAwareSubAgent,
        )

        context_pkg = ContextPackage(
            package_id="ctx_timestamp_001",
            task_description="任务",
        )

        child_agent = ContextAwareSubAgent(
            agent_id="worker",
            context_package=context_pkg,
        )

        child_agent.start_execution()
        result_pkg = await child_agent.complete_task(output_data={})

        assert result_pkg.started_at is not None
        assert result_pkg.completed_at is not None
        assert result_pkg.completed_at >= result_pkg.started_at
