"""上下文打包/解包协议集成测试

测试场景：
1. 与场景提示词系统集成
2. 与 ConversationAgent 上下文管理集成
3. 父子 Agent 完整通信流程
4. 压缩策略在真实数据下的表现
5. 与短期/中期记忆组件兼容性
"""

import json

import pytest

from src.domain.services.context_protocol import (
    CompressionStrategy,
    ContextCompressor,
    ContextPackage,
    ContextPacker,
    ContextSchemaValidator,
    ContextUnpacker,
    create_context_package,
    validate_package,
)


class TestContextProtocolWithScenarioPrompt:
    """上下文协议与场景提示词系统集成测试"""

    def test_pack_context_with_scenario_metadata(self) -> None:
        """测试打包上下文时携带场景元数据"""
        packer = ContextPacker(agent_id="coordinator")

        # 模拟场景提示词系统提供的上下文
        scenario_context = {
            "scenario_id": "financial_analysis",
            "domain": "finance",
            "system_prompt": "你是专业的财务分析师",
            "guidelines": ["使用专业术语", "提供数据支撑"],
        }

        package = packer.pack(
            task_description="分析公司Q3财务报表",
            constraints=["保护敏感财务数据", "使用中文回复"],
            relevant_knowledge=scenario_context,
            input_data={"company": "示例公司", "period": "2024Q3"},
            prompt_version="1.0.0",
        )

        assert package.relevant_knowledge["scenario_id"] == "financial_analysis"
        assert package.relevant_knowledge["domain"] == "finance"
        assert len(package.constraints) == 2

    def test_unpack_and_extract_scenario_context(self) -> None:
        """测试解包时提取场景上下文"""
        unpacker = ContextUnpacker(agent_id="analyzer")

        # 模拟接收到的 JSON 数据
        json_data = {
            "package_id": "ctx_scenario_001",
            "task_description": "执行数据分析任务",
            "constraints": ["遵循分析规范"],
            "relevant_knowledge": {
                "scenario_id": "data_analysis",
                "analysis_type": "exploratory",
                "tools_available": ["pandas", "matplotlib"],
            },
            "input_data": {"data_source": "sales_db"},
            "prompt_version": "2.0.0",
        }

        result = unpacker.unpack_from_json(json.dumps(json_data))

        assert result.knowledge["scenario_id"] == "data_analysis"
        assert "pandas" in result.knowledge["tools_available"]
        assert result.prompt_version == "2.0.0"


class TestContextProtocolWithConversationAgent:
    """上下文协议与 ConversationAgent 集成测试"""

    def test_pack_conversation_history(self) -> None:
        """测试打包对话历史"""
        packer = ContextPacker(agent_id="conversation_agent")

        # 模拟 ConversationAgent 的对话历史
        conversation_history = [
            "user: 我想了解公司的销售情况",
            "assistant: 好的，请问您想了解哪个时间段的销售数据？",
            "user: 最近三个月的",
            "assistant: 正在查询最近三个月的销售数据...",
        ]

        session_context = {
            "session_id": "sess_001",
            "user_intent": "销售数据查询",
            "identified_entities": ["时间范围: 3个月", "数据类型: 销售"],
            "conversation_stage": "gathering_requirements",
        }

        package = packer.pack(
            task_description="根据对话历史查询销售数据",
            short_term_context=conversation_history,
            mid_term_context=session_context,
            constraints=["保护用户隐私", "数据脱敏处理"],
        )

        assert len(package.short_term_context) == 4
        assert package.mid_term_context["user_intent"] == "销售数据查询"
        assert package.mid_term_context["conversation_stage"] == "gathering_requirements"

    def test_subtask_context_propagation(self) -> None:
        """测试子任务上下文传播"""
        parent_packer = ContextPacker(agent_id="coordinator")
        child_unpacker = ContextUnpacker(agent_id="data_fetcher")

        # 父 Agent 创建子任务上下文
        parent_package = parent_packer.pack(
            task_description="从数据库获取销售数据",
            constraints=["使用只读连接", "限制查询结果数量"],
            input_data={
                "query_params": {
                    "start_date": "2024-07-01",
                    "end_date": "2024-09-30",
                    "metrics": ["revenue", "units_sold"],
                },
            },
            target_agent_id="data_fetcher",
            priority=5,
        )

        # 子 Agent 解包
        child_context = child_unpacker.unpack(parent_package)

        assert child_context.source_agent == "coordinator"
        assert child_context.priority == 5
        assert child_context.input_data["query_params"]["start_date"] == "2024-07-01"


class TestParentChildAgentCommunication:
    """父子 Agent 完整通信流程测试"""

    def test_full_hierarchical_context_flow(self) -> None:
        """测试完整的层级上下文流转"""
        # 1. Coordinator Agent 打包任务
        coordinator_packer = ContextPacker(agent_id="coordinator")
        task_package = coordinator_packer.pack(
            task_description="完成用户查询任务",
            constraints=["遵循安全规范", "记录操作日志"],
            relevant_knowledge={"task_type": "data_query", "complexity": "medium"},
            short_term_context=["用户请求：查询销售数据"],
            mid_term_context={"session_goal": "完成数据分析"},
            prompt_version="1.2.0",
        )

        # 2. 序列化传输
        json_str = task_package.to_json()

        # 3. Worker Agent 解包
        worker_unpacker = ContextUnpacker(agent_id="data_worker")
        worker_context = worker_unpacker.unpack_from_json(json_str)

        # 4. Worker Agent 处理并创建子任务结果
        worker_packer = ContextPacker(agent_id="data_worker")
        result_package = worker_packer.pack(
            task_description="返回查询结果",
            input_data={
                "result_status": "success",
                "data": {"total_revenue": 1000000, "total_units": 5000},
            },
            target_agent_id="coordinator",
            metadata={"execution_time_ms": 150, "rows_processed": 1000},
        )

        # 5. Coordinator 接收结果
        coordinator_unpacker = ContextUnpacker(agent_id="coordinator")
        result_context = coordinator_unpacker.unpack(result_package)

        # 验证完整流程
        assert worker_context.source_agent == "coordinator"
        assert worker_context.knowledge["task_type"] == "data_query"
        assert result_context.source_agent == "data_worker"
        assert result_context.input_data["result_status"] == "success"

    def test_multi_level_context_inheritance(self) -> None:
        """测试多级上下文继承"""
        # Level 0: 根协调器
        root_packer = ContextPacker(agent_id="root_coordinator")
        root_package = root_packer.pack(
            task_description="复杂分析任务",
            constraints=["全局约束1", "全局约束2"],
            relevant_knowledge={"global_config": {"timeout": 30}},
        )

        # Level 1: 子协调器接收并扩展
        sub_coordinator_unpacker = ContextUnpacker(agent_id="sub_coordinator")
        sub_context = sub_coordinator_unpacker.unpack(root_package)

        sub_packer = ContextPacker(agent_id="sub_coordinator")
        sub_package = sub_packer.pack(
            task_description="子分析任务",
            constraints=sub_context.constraints + ["局部约束"],
            relevant_knowledge={
                **sub_context.knowledge,
                "local_config": {"batch_size": 100},
            },
        )

        # Level 2: 执行器接收
        executor_unpacker = ContextUnpacker(agent_id="executor")
        executor_context = executor_unpacker.unpack(sub_package)

        # 验证约束继承
        assert len(executor_context.constraints) == 3
        assert "全局约束1" in executor_context.constraints
        assert "局部约束" in executor_context.constraints

        # 验证知识继承与扩展
        assert executor_context.knowledge["global_config"]["timeout"] == 30
        assert executor_context.knowledge["local_config"]["batch_size"] == 100


class TestCompressionWithRealData:
    """压缩策略在真实数据下的表现测试"""

    def test_compress_large_conversation_history(self) -> None:
        """测试压缩大量对话历史"""
        # 模拟真实的长对话历史
        conversation = []
        for i in range(100):
            conversation.append(
                f"user: 这是用户的第{i+1}条消息，包含一些详细的问题描述和背景信息。"
            )
            conversation.append(f"assistant: 这是助手的第{i+1}条回复，包含详细的解答和建议。")

        packer = ContextPacker()
        package = packer.pack(
            task_description="继续对话",
            short_term_context=conversation,
            max_tokens=1000,  # 较小的 Token 限制
        )

        compressor = ContextCompressor(strategy=CompressionStrategy.TRUNCATE)
        compressed, report = compressor.compress_with_report(package)

        # 验证压缩效果
        assert report["compressed_tokens"] <= package.max_tokens
        assert len(compressed.short_term_context) < len(conversation)

        # 验证保留最近的对话
        if compressed.short_term_context:
            # 最后的消息应该被保留
            last_msg = compressed.short_term_context[-1]
            assert "assistant" in last_msg or "user" in last_msg

    def test_compress_with_priority_strategy(self) -> None:
        """测试优先级压缩策略"""
        packer = ContextPacker()
        package = packer.pack(
            task_description="优先级压缩测试",
            constraints=[
                "重要约束1",
                "重要约束2",
                "次要约束3",
                "次要约束4",
                "次要约束5",
                "次要约束6",
            ],
            short_term_context=[f"消息{i}" * 50 for i in range(50)],
            max_tokens=500,
        )

        compressor = ContextCompressor(strategy=CompressionStrategy.PRIORITY)
        compressed = compressor.compress(package)

        # 验证约束被保留（最多5个）
        assert len(compressed.constraints) <= 5

    def test_compression_preserves_critical_fields(self) -> None:
        """测试压缩保留关键字段"""
        packer = ContextPacker()
        package = packer.pack(
            task_description="关键任务描述" * 100,  # 很长的描述
            constraints=["约束"] * 10,
            relevant_knowledge={"key": "value" * 1000},
            input_data={"critical_input": "important_value"},
            short_term_context=["消息" * 100 for _ in range(50)],
            max_tokens=300,
        )

        compressor = ContextCompressor()
        compressed = compressor.compress(package)

        # 关键信息应该被保留
        assert compressed.task_description is not None
        assert len(compressed.task_description) > 0
        assert compressed.input_data == package.input_data  # input_data 不应被截断


class TestMemoryComponentCompatibility:
    """与记忆组件兼容性测试"""

    def test_integrate_with_short_term_buffer_format(self) -> None:
        """测试与短期记忆缓冲区格式兼容"""
        # 模拟 ShortTermBuffer 的数据格式
        short_term_buffer_data = {
            "recent_messages": [
                {"role": "user", "content": "你好", "timestamp": "2024-01-01T10:00:00"},
                {
                    "role": "assistant",
                    "content": "你好！有什么可以帮助你的？",
                    "timestamp": "2024-01-01T10:00:05",
                },
                {"role": "user", "content": "我想查询订单", "timestamp": "2024-01-01T10:00:10"},
            ],
            "buffer_size": 3,
            "max_size": 10,
        }

        packer = ContextPacker()
        package = packer.pack_with_short_term_memory(
            task_description="处理订单查询",
            short_term_memory=short_term_buffer_data,
        )

        # 验证格式转换正确
        assert len(package.short_term_context) == 3
        assert "user: 你好" in package.short_term_context[0]
        assert "assistant: 你好" in package.short_term_context[1]

    def test_integrate_with_mid_term_summary_format(self) -> None:
        """测试与中期记忆摘要格式兼容"""
        # 模拟中期记忆摘要数据
        mid_term_summary_data = {
            "conversation_summary": "用户正在咨询产品购买相关问题",
            "key_entities": ["产品A", "价格", "优惠"],
            "user_preferences": {"language": "zh", "detail_level": "high"},
            "conversation_progress": 0.6,
            "identified_intents": ["product_inquiry", "price_check"],
        }

        packer = ContextPacker()
        package = packer.pack_with_mid_term_memory(
            task_description="回答产品问题",
            mid_term_memory=mid_term_summary_data,
        )

        assert package.mid_term_context["conversation_summary"] == "用户正在咨询产品购买相关问题"
        assert "产品A" in package.mid_term_context["key_entities"]
        assert package.mid_term_context["conversation_progress"] == 0.6

    def test_extract_memory_for_storage(self) -> None:
        """测试提取记忆用于存储"""
        package = ContextPackage(
            package_id="ctx_memory_001",
            task_description="记忆存储测试",
            short_term_context=["消息1", "消息2", "消息3"],
            mid_term_context={"summary": "对话摘要", "progress": 0.5},
            long_term_references=["kb_001", "kb_002"],
        )

        unpacker = ContextUnpacker()
        memory_data = unpacker.extract_for_memory(package)

        # 验证提取的数据可以直接用于记忆存储
        assert memory_data["short_term"] == ["消息1", "消息2", "消息3"]
        assert memory_data["mid_term"]["summary"] == "对话摘要"
        assert "kb_001" in memory_data["long_term_refs"]
        assert "task" in memory_data
        assert "timestamp" in memory_data


class TestContextValidationScenarios:
    """上下文验证场景测试"""

    def test_validate_malformed_json_input(self) -> None:
        """测试验证格式错误的 JSON 输入"""
        unpacker = ContextUnpacker()

        with pytest.raises(json.JSONDecodeError):
            unpacker.unpack_from_json("not valid json")

    def test_validate_missing_multiple_required_fields(self) -> None:
        """测试验证缺少多个必需字段"""
        validator = ContextSchemaValidator()

        invalid_data = {
            # 缺少 package_id 和 task_description
            "constraints": ["约束"],
        }

        result = validator.validate(invalid_data)

        assert not result.is_valid
        assert len(result.errors) >= 2

    def test_validate_type_mismatch(self) -> None:
        """测试验证类型不匹配"""
        validator = ContextSchemaValidator()

        invalid_data = {
            "package_id": "pkg_001",
            "task_description": "任务",
            "constraints": "应该是列表但传了字符串",  # 类型错误
            "priority": "应该是整数",  # 类型错误
        }

        result = validator.validate(invalid_data)

        assert not result.is_valid
        assert any("constraints" in err for err in result.errors)

    def test_validate_boundary_values(self) -> None:
        """测试边界值验证"""
        package = ContextPackage(
            package_id="pkg_boundary",
            task_description="边界测试",
            priority=15,  # 超出 0-10 范围
        )

        is_valid, errors = validate_package(package)

        assert not is_valid
        assert any("priority" in err for err in errors)


class TestContextProtocolRealWorldScenarios:
    """真实场景测试"""

    def test_customer_service_scenario(self) -> None:
        """测试客服场景"""
        # 模拟客服场景的完整上下文流转
        packer = ContextPacker(agent_id="customer_service_coordinator")

        # 客户对话历史
        conversation = [
            "customer: 我的订单一直没有发货",
            "agent: 抱歉给您带来不便，请问您的订单号是多少？",
            "customer: ORD-2024-12345",
            "agent: 正在为您查询订单状态...",
        ]

        # 会话上下文
        session_context = {
            "customer_id": "C001",
            "order_id": "ORD-2024-12345",
            "issue_type": "shipping_delay",
            "sentiment": "frustrated",
            "previous_interactions": 2,
        }

        package = packer.pack(
            task_description="查询订单物流状态并提供解决方案",
            constraints=["保持礼貌专业", "不承诺具体时间", "记录客户反馈"],
            short_term_context=conversation,
            mid_term_context=session_context,
            input_data={"order_id": "ORD-2024-12345"},
            priority=8,  # 高优先级
        )

        # 子 Agent 解包
        logistics_unpacker = ContextUnpacker(agent_id="logistics_query_agent")
        logistics_context = logistics_unpacker.unpack(package)

        assert logistics_context.priority == 8
        assert logistics_context.input_data["order_id"] == "ORD-2024-12345"
        assert "frustrated" in str(logistics_context.mid_term)

    def test_data_analysis_pipeline_scenario(self) -> None:
        """测试数据分析流水线场景"""
        # 协调器创建分析任务
        coordinator_packer = ContextPacker(agent_id="analysis_coordinator")

        analysis_config = {
            "data_sources": ["sales_db", "customer_db"],
            "analysis_types": ["trend", "segmentation", "prediction"],
            "output_format": "report",
        }

        pipeline_context = {
            "pipeline_id": "analysis_001",
            "stage": "data_preparation",
            "total_stages": 4,
            "started_at": "2024-01-01T10:00:00",
        }

        package = coordinator_packer.pack(
            task_description="执行销售趋势分析",
            constraints=["使用最近90天数据", "排除测试数据", "结果四舍五入到整数"],
            relevant_knowledge=analysis_config,
            mid_term_context=pipeline_context,
            max_tokens=2000,
        )

        # 数据准备 Agent 接收
        prep_unpacker = ContextUnpacker(agent_id="data_prep_agent")
        prep_context = prep_unpacker.unpack(package)

        assert "sales_db" in prep_context.knowledge["data_sources"]
        assert prep_context.mid_term["stage"] == "data_preparation"

    def test_code_review_scenario(self) -> None:
        """测试代码审查场景"""
        packer = ContextPacker(agent_id="code_review_coordinator")

        code_context = {
            "repository": "my-project",
            "branch": "feature/new-api",
            "language": "Python",
            "framework": "FastAPI",
            "review_focus": ["security", "performance", "style"],
        }

        package = packer.pack(
            task_description="审查 API 端点代码变更",
            constraints=[
                "遵循 PEP8 规范",
                "检查 SQL 注入风险",
                "验证输入参数",
                "检查错误处理",
            ],
            relevant_knowledge=code_context,
            input_data={
                "files_changed": ["src/api/users.py", "src/api/orders.py"],
                "lines_added": 150,
                "lines_removed": 30,
            },
        )

        # 安全审查 Agent
        security_unpacker = ContextUnpacker(agent_id="security_reviewer")
        security_context = security_unpacker.unpack(package)

        assert "security" in security_context.knowledge["review_focus"]
        assert "SQL 注入" in str(security_context.constraints)


class TestFactoryFunctions:
    """工厂函数测试"""

    def test_create_context_package_shorthand(self) -> None:
        """测试快捷创建上下文包"""
        package = create_context_package(
            task_description="快速创建测试",
            prompt_version="1.5.0",
            constraints=["约束1"],
            input_data={"key": "value"},
        )

        assert package.package_id.startswith("ctx_")
        assert package.task_description == "快速创建测试"
        assert package.prompt_version == "1.5.0"
        assert package.constraints == ["约束1"]

    def test_create_context_package_with_defaults(self) -> None:
        """测试使用默认值创建上下文包"""
        package = create_context_package(task_description="最小创建测试")

        assert package.package_id is not None
        assert package.prompt_version == "1.0.0"
        assert package.constraints == []
        assert package.priority == 0
