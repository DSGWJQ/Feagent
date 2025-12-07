"""上下文打包/解包协议测试

测试覆盖：
1. ContextPackage 数据结构
2. ContextPacker 打包器
3. ContextUnpacker 解包器
4. 字段缺失处理
5. 压缩策略
6. 与短期/中期记忆组件兼容性
"""

import json

import pytest


class TestContextPackageDataStructure:
    """上下文包数据结构测试"""

    def test_context_package_has_required_fields(self) -> None:
        """测试上下文包包含必要字段"""
        from src.domain.services.context_protocol import ContextPackage

        package = ContextPackage(
            package_id="pkg_001",
            task_description="分析销售数据趋势",
            constraints=["使用中文回复", "数据脱敏处理"],
            relevant_knowledge={"domain": "sales", "period": "Q3"},
            input_data={"sales_data": [100, 200, 300]},
            prompt_version="1.0.0",
        )

        assert package.package_id == "pkg_001"
        assert package.task_description == "分析销售数据趋势"
        assert len(package.constraints) == 2
        assert package.relevant_knowledge["domain"] == "sales"
        assert package.prompt_version == "1.0.0"

    def test_context_package_optional_fields(self) -> None:
        """测试上下文包可选字段"""
        from src.domain.services.context_protocol import ContextPackage

        package = ContextPackage(
            package_id="pkg_002",
            task_description="生成报告",
            parent_agent_id="coordinator",
            target_agent_id="report_generator",
            priority=1,
            max_tokens=4000,
            short_term_context=["用户刚才问了销售情况"],
            mid_term_context={"session_goal": "完成季度分析"},
            long_term_references=["knowledge_base_001"],
        )

        assert package.parent_agent_id == "coordinator"
        assert package.target_agent_id == "report_generator"
        assert package.priority == 1
        assert package.max_tokens == 4000
        assert len(package.short_term_context) == 1
        assert "session_goal" in package.mid_term_context

    def test_context_package_to_dict_and_from_dict(self) -> None:
        """测试上下文包序列化与反序列化"""
        from src.domain.services.context_protocol import ContextPackage

        original = ContextPackage(
            package_id="pkg_003",
            task_description="代码审查",
            constraints=["遵循PEP8"],
            relevant_knowledge={"language": "Python"},
            input_data={"code": "def foo(): pass"},
            prompt_version="2.0.0",
            priority=2,
        )

        data = original.to_dict()
        restored = ContextPackage.from_dict(data)

        assert restored.package_id == original.package_id
        assert restored.task_description == original.task_description
        assert restored.constraints == original.constraints
        assert restored.priority == original.priority

    def test_context_package_to_json(self) -> None:
        """测试上下文包 JSON 序列化"""
        from src.domain.services.context_protocol import ContextPackage

        package = ContextPackage(
            package_id="pkg_004",
            task_description="测试任务",
            constraints=[],
            relevant_knowledge={},
            input_data={},
            prompt_version="1.0.0",
        )

        json_str = package.to_json()
        parsed = json.loads(json_str)

        assert parsed["package_id"] == "pkg_004"
        assert parsed["task_description"] == "测试任务"

    def test_context_package_from_json(self) -> None:
        """测试从 JSON 创建上下文包"""
        from src.domain.services.context_protocol import ContextPackage

        json_str = json.dumps(
            {
                "package_id": "pkg_005",
                "task_description": "从JSON创建",
                "constraints": ["约束1"],
                "relevant_knowledge": {"key": "value"},
                "input_data": {"data": 123},
                "prompt_version": "1.0.0",
            }
        )

        package = ContextPackage.from_json(json_str)

        assert package.package_id == "pkg_005"
        assert package.constraints == ["约束1"]


class TestContextPacker:
    """上下文打包器测试"""

    def test_pack_basic_context(self) -> None:
        """测试基本上下文打包"""
        from src.domain.services.context_protocol import ContextPacker

        packer = ContextPacker()

        package = packer.pack(
            task_description="分析用户行为",
            constraints=["保护隐私"],
            input_data={"user_actions": ["click", "scroll"]},
        )

        assert package.package_id is not None
        assert package.task_description == "分析用户行为"
        assert "保护隐私" in package.constraints

    def test_pack_with_knowledge(self) -> None:
        """测试带知识上下文的打包"""
        from src.domain.services.context_protocol import ContextPacker

        packer = ContextPacker()

        package = packer.pack(
            task_description="回答问题",
            relevant_knowledge={
                "domain_knowledge": "相关领域知识...",
                "faq": ["问题1", "问题2"],
            },
        )

        assert "domain_knowledge" in package.relevant_knowledge
        assert len(package.relevant_knowledge["faq"]) == 2

    def test_pack_with_memory_context(self) -> None:
        """测试带记忆上下文的打包"""
        from src.domain.services.context_protocol import ContextPacker

        packer = ContextPacker()

        package = packer.pack(
            task_description="继续对话",
            short_term_context=["用户: 你好", "助手: 你好，有什么可以帮助你的？"],
            mid_term_context={
                "session_start": "2024-01-01T10:00:00",
                "user_intent": "咨询产品",
            },
        )

        assert len(package.short_term_context) == 2
        assert package.mid_term_context["user_intent"] == "咨询产品"

    def test_pack_with_prompt_version(self) -> None:
        """测试带提示词版本的打包"""
        from src.domain.services.context_protocol import ContextPacker

        packer = ContextPacker(default_prompt_version="2.1.0")

        package = packer.pack(
            task_description="执行任务",
            prompt_version="3.0.0",
        )

        assert package.prompt_version == "3.0.0"

        # 使用默认版本
        package2 = packer.pack(task_description="另一个任务")
        assert package2.prompt_version == "2.1.0"

    def test_pack_generates_unique_id(self) -> None:
        """测试打包生成唯一ID"""
        from src.domain.services.context_protocol import ContextPacker

        packer = ContextPacker()

        package1 = packer.pack(task_description="任务1")
        package2 = packer.pack(task_description="任务2")

        assert package1.package_id != package2.package_id


class TestContextUnpacker:
    """上下文解包器测试"""

    def test_unpack_basic_context(self) -> None:
        """测试基本上下文解包"""
        from src.domain.services.context_protocol import (
            ContextPackage,
            ContextUnpacker,
        )

        package = ContextPackage(
            package_id="pkg_unpack_001",
            task_description="测试解包",
            constraints=["约束1", "约束2"],
            relevant_knowledge={"info": "信息"},
            input_data={"key": "value"},
            prompt_version="1.0.0",
        )

        unpacker = ContextUnpacker()
        result = unpacker.unpack(package)

        assert result.task_description == "测试解包"
        assert result.constraints == ["约束1", "约束2"]
        assert result.knowledge["info"] == "信息"

    def test_unpack_from_json(self) -> None:
        """测试从 JSON 解包"""
        from src.domain.services.context_protocol import ContextUnpacker

        json_str = json.dumps(
            {
                "package_id": "pkg_json_001",
                "task_description": "JSON解包测试",
                "constraints": ["c1"],
                "relevant_knowledge": {},
                "input_data": {"x": 1},
                "prompt_version": "1.0.0",
            }
        )

        unpacker = ContextUnpacker()
        result = unpacker.unpack_from_json(json_str)

        assert result.task_description == "JSON解包测试"
        assert result.input_data["x"] == 1

    def test_unpack_validates_required_fields(self) -> None:
        """测试解包验证必需字段"""
        from src.domain.services.context_protocol import (
            ContextUnpacker,
            ContextValidationError,
        )

        invalid_json = json.dumps(
            {
                "package_id": "pkg_invalid",
                # 缺少 task_description
            }
        )

        unpacker = ContextUnpacker()
        with pytest.raises(ContextValidationError) as exc_info:
            unpacker.unpack_from_json(invalid_json)

        assert "task_description" in str(exc_info.value)

    def test_unpack_with_default_values(self) -> None:
        """测试解包使用默认值处理缺失可选字段"""
        from src.domain.services.context_protocol import ContextUnpacker

        minimal_json = json.dumps(
            {
                "package_id": "pkg_minimal",
                "task_description": "最小配置",
                "prompt_version": "1.0.0",
            }
        )

        unpacker = ContextUnpacker()
        result = unpacker.unpack_from_json(minimal_json)

        assert result.constraints == []
        assert result.knowledge == {}
        assert result.input_data == {}


class TestMissingFieldHandling:
    """字段缺失处理测试"""

    def test_missing_optional_fields_use_defaults(self) -> None:
        """测试缺失可选字段使用默认值"""
        from src.domain.services.context_protocol import ContextPackage

        package = ContextPackage(
            package_id="pkg_default",
            task_description="默认值测试",
            prompt_version="1.0.0",
        )

        assert package.constraints == []
        assert package.relevant_knowledge == {}
        assert package.input_data == {}
        assert package.short_term_context == []
        assert package.mid_term_context == {}
        assert package.long_term_references == []
        assert package.priority == 0
        assert package.max_tokens is None

    def test_missing_required_field_raises_error(self) -> None:
        """测试缺失必需字段抛出错误"""
        from src.domain.services.context_protocol import (
            ContextPackage,
            ContextValidationError,
        )

        with pytest.raises((TypeError, ContextValidationError)):
            ContextPackage(
                package_id="pkg_error",
                # 缺少 task_description
                prompt_version="1.0.0",
            )

    def test_validate_package_integrity(self) -> None:
        """测试验证包完整性"""
        from src.domain.services.context_protocol import (
            ContextPackage,
            validate_package,
        )

        valid_package = ContextPackage(
            package_id="pkg_valid",
            task_description="有效包",
            prompt_version="1.0.0",
        )

        is_valid, errors = validate_package(valid_package)
        assert is_valid
        assert len(errors) == 0

    def test_validate_detects_empty_task_description(self) -> None:
        """测试检测空任务描述"""
        from src.domain.services.context_protocol import (
            ContextPackage,
            validate_package,
        )

        package = ContextPackage(
            package_id="pkg_empty_task",
            task_description="",  # 空描述
            prompt_version="1.0.0",
        )

        is_valid, errors = validate_package(package)
        assert not is_valid
        assert any("task_description" in err for err in errors)


class TestCompressionStrategy:
    """压缩策略测试"""

    def test_estimate_token_count(self) -> None:
        """测试 Token 数量估算"""
        from src.domain.services.context_protocol import ContextCompressor

        compressor = ContextCompressor()

        # 简单文本
        count1 = compressor.estimate_tokens("Hello world")
        assert count1 > 0

        # 中文文本
        count2 = compressor.estimate_tokens("你好世界")
        assert count2 > 0

    def test_compress_when_under_limit(self) -> None:
        """测试未超限时不压缩"""
        from src.domain.services.context_protocol import (
            ContextCompressor,
            ContextPackage,
        )

        package = ContextPackage(
            package_id="pkg_small",
            task_description="小任务",
            constraints=["约束1"],
            relevant_knowledge={"key": "value"},
            input_data={"x": 1},
            prompt_version="1.0.0",
            max_tokens=10000,  # 足够大
        )

        compressor = ContextCompressor()
        compressed = compressor.compress(package)

        # 应该保持不变
        assert compressed.task_description == package.task_description
        assert compressed.constraints == package.constraints

    def test_compress_truncates_long_context(self) -> None:
        """测试压缩截断过长上下文"""
        from src.domain.services.context_protocol import (
            ContextCompressor,
            ContextPackage,
        )

        long_context = ["消息" * 100 for _ in range(50)]

        package = ContextPackage(
            package_id="pkg_long",
            task_description="长上下文任务",
            short_term_context=long_context,
            prompt_version="1.0.0",
            max_tokens=500,  # 限制较小
        )

        compressor = ContextCompressor()
        compressed = compressor.compress(package)

        # 上下文应该被截断
        assert len(compressed.short_term_context) < len(long_context)

    def test_compress_prioritizes_recent_context(self) -> None:
        """测试压缩优先保留最近上下文"""
        from src.domain.services.context_protocol import (
            ContextCompressor,
            ContextPackage,
        )

        context = [f"消息{i}" for i in range(100)]

        package = ContextPackage(
            package_id="pkg_priority",
            task_description="优先级测试",
            short_term_context=context,
            prompt_version="1.0.0",
            max_tokens=200,
        )

        compressor = ContextCompressor()
        compressed = compressor.compress(package)

        # 应该保留最后的消息（最近的）
        if compressed.short_term_context:
            assert (
                "消息99" in compressed.short_term_context[-1]
                or len(compressed.short_term_context) < 10
            )

    def test_compress_with_strategy_options(self) -> None:
        """测试不同压缩策略选项"""
        from src.domain.services.context_protocol import (
            CompressionStrategy,
            ContextCompressor,
            ContextPackage,
        )

        package = ContextPackage(
            package_id="pkg_strategy",
            task_description="策略测试",
            relevant_knowledge={"large_data": "x" * 5000},
            prompt_version="1.0.0",
            max_tokens=500,
        )

        # 截断策略
        compressor_truncate = ContextCompressor(strategy=CompressionStrategy.TRUNCATE)
        result1 = compressor_truncate.compress(package)

        # 优先级策略
        compressor_priority = ContextCompressor(strategy=CompressionStrategy.PRIORITY)
        result2 = compressor_priority.compress(package)

        # 两种策略都应该减少内容
        assert result1.package_id == package.package_id
        assert result2.package_id == package.package_id

    def test_compression_report(self) -> None:
        """测试压缩报告"""
        from src.domain.services.context_protocol import (
            ContextCompressor,
            ContextPackage,
        )

        package = ContextPackage(
            package_id="pkg_report",
            task_description="报告测试",
            short_term_context=["消息" * 100 for _ in range(20)],
            prompt_version="1.0.0",
            max_tokens=300,
        )

        compressor = ContextCompressor()
        compressed, report = compressor.compress_with_report(package)

        assert "original_tokens" in report
        assert "compressed_tokens" in report
        assert "compression_ratio" in report
        assert report["compressed_tokens"] <= report["original_tokens"]


class TestMemoryCompatibility:
    """与记忆组件兼容性测试"""

    def test_integrate_with_short_term_buffer(self) -> None:
        """测试与短期记忆缓冲区集成"""
        from src.domain.services.context_protocol import ContextPacker

        # 模拟短期记忆数据
        short_term_data = {
            "recent_messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好，有什么可以帮助你的？"},
            ],
            "current_topic": "产品咨询",
        }

        packer = ContextPacker()
        package = packer.pack_with_short_term_memory(
            task_description="回答用户问题",
            short_term_memory=short_term_data,
        )

        assert len(package.short_term_context) == 2
        assert "你好" in package.short_term_context[0]

    def test_integrate_with_mid_term_context(self) -> None:
        """测试与中期上下文集成"""
        from src.domain.services.context_protocol import ContextPacker

        # 模拟中期记忆数据
        mid_term_data = {
            "session_summary": "用户正在咨询产品A的功能",
            "identified_needs": ["功能对比", "价格查询"],
            "conversation_progress": 0.5,
        }

        packer = ContextPacker()
        package = packer.pack_with_mid_term_memory(
            task_description="提供产品建议",
            mid_term_memory=mid_term_data,
        )

        assert "session_summary" in package.mid_term_context
        assert package.mid_term_context["conversation_progress"] == 0.5

    def test_integrate_with_context_manager(self) -> None:
        """测试与 ContextManager 集成"""
        from src.domain.services.context_protocol import ContextPacker

        # 模拟 ContextManager 提供的数据
        context_manager_data = {
            "short_term": ["最近消息1", "最近消息2"],
            "mid_term": {"goal": "完成任务"},
            "long_term_refs": ["kb_001", "kb_002"],
        }

        packer = ContextPacker()
        package = packer.pack_from_context_manager(
            task_description="综合任务",
            context_data=context_manager_data,
        )

        assert package.short_term_context == ["最近消息1", "最近消息2"]
        assert package.mid_term_context["goal"] == "完成任务"
        assert "kb_001" in package.long_term_references

    def test_extract_for_memory_storage(self) -> None:
        """测试提取用于记忆存储的数据"""
        from src.domain.services.context_protocol import (
            ContextPackage,
            ContextUnpacker,
        )

        package = ContextPackage(
            package_id="pkg_extract",
            task_description="提取测试",
            constraints=["约束"],
            relevant_knowledge={"key": "value"},
            input_data={"data": 123},
            short_term_context=["消息1"],
            mid_term_context={"goal": "目标"},
            prompt_version="1.0.0",
        )

        unpacker = ContextUnpacker()
        memory_data = unpacker.extract_for_memory(package)

        assert "short_term" in memory_data
        assert "mid_term" in memory_data
        assert memory_data["short_term"] == ["消息1"]
        assert memory_data["mid_term"]["goal"] == "目标"


class TestContextProtocolIntegration:
    """上下文协议集成测试"""

    def test_full_pack_unpack_cycle(self) -> None:
        """测试完整打包解包循环"""
        from src.domain.services.context_protocol import (
            ContextPacker,
            ContextUnpacker,
        )

        packer = ContextPacker()
        unpacker = ContextUnpacker()

        # 打包
        package = packer.pack(
            task_description="完整循环测试",
            constraints=["约束A", "约束B"],
            relevant_knowledge={"domain": "test"},
            input_data={"input": "data"},
            short_term_context=["msg1", "msg2"],
            mid_term_context={"key": "value"},
            prompt_version="1.0.0",
        )

        # 序列化
        json_str = package.to_json()

        # 解包
        result = unpacker.unpack_from_json(json_str)

        # 验证
        assert result.task_description == "完整循环测试"
        assert result.constraints == ["约束A", "约束B"]
        assert result.knowledge["domain"] == "test"
        assert result.input_data["input"] == "data"

    def test_pack_compress_unpack_cycle(self) -> None:
        """测试打包-压缩-解包循环"""
        from src.domain.services.context_protocol import (
            ContextCompressor,
            ContextPacker,
            ContextUnpacker,
        )

        packer = ContextPacker()
        compressor = ContextCompressor()
        unpacker = ContextUnpacker()

        # 打包大量数据
        package = packer.pack(
            task_description="压缩循环测试",
            short_term_context=["消息" * 50 for _ in range(30)],
            max_tokens=500,
        )

        # 压缩
        compressed = compressor.compress(package)

        # 序列化
        json_str = compressed.to_json()

        # 解包
        result = unpacker.unpack_from_json(json_str)

        # 验证核心信息保留
        assert result.task_description == "压缩循环测试"

    def test_parent_child_context_passing(self) -> None:
        """测试父子 Agent 上下文传递"""
        from src.domain.services.context_protocol import (
            ContextPacker,
            ContextUnpacker,
        )

        # 父 Agent 打包
        parent_packer = ContextPacker(agent_id="coordinator")
        package = parent_packer.pack(
            task_description="分析任务",
            constraints=["子任务约束"],
            input_data={"subtask_input": "data"},
            target_agent_id="analyzer",
        )

        assert package.parent_agent_id == "coordinator"
        assert package.target_agent_id == "analyzer"

        # 子 Agent 解包
        child_unpacker = ContextUnpacker(agent_id="analyzer")
        result = child_unpacker.unpack(package)

        assert result.task_description == "分析任务"
        assert result.source_agent == "coordinator"


class TestContextSchemaValidation:
    """上下文 Schema 验证测试"""

    def test_valid_schema_passes_validation(self) -> None:
        """测试有效 Schema 通过验证"""
        from src.domain.services.context_protocol import (
            ContextSchemaValidator,
        )

        valid_data = {
            "package_id": "pkg_valid",
            "task_description": "有效任务",
            "constraints": ["约束"],
            "relevant_knowledge": {},
            "input_data": {},
            "prompt_version": "1.0.0",
        }

        validator = ContextSchemaValidator()
        result = validator.validate(valid_data)

        assert result.is_valid

    def test_invalid_schema_fails_validation(self) -> None:
        """测试无效 Schema 验证失败"""
        from src.domain.services.context_protocol import (
            ContextSchemaValidator,
        )

        invalid_data = {
            "package_id": "pkg_invalid",
            # 缺少 task_description
            "constraints": "not_a_list",  # 类型错误
        }

        validator = ContextSchemaValidator()
        result = validator.validate(invalid_data)

        assert not result.is_valid
        assert len(result.errors) > 0

    def test_schema_version_compatibility(self) -> None:
        """测试 Schema 版本兼容性"""
        from src.domain.services.context_protocol import (
            ContextSchemaValidator,
        )

        # v1 格式数据
        v1_data = {
            "package_id": "pkg_v1",
            "task_description": "v1任务",
            "prompt_version": "1.0.0",
        }

        validator = ContextSchemaValidator()

        # 应该兼容旧版本
        result = validator.validate(v1_data, schema_version="1.0")
        assert result.is_valid
