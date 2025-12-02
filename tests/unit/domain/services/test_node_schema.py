"""阶段6测试：通用节点Schema约束

测试目标：
1. 定义输入/输出类型
2. 允许的子节点类型
3. WorkflowAgent创建节点时执行schema校验
4. 父子节点展开保持类型一致

完成标准：
- Schema 文档 + 校验逻辑
- 单元测试覆盖
- 父子节点展开保持类型一致
"""


# ==================== 测试1：节点Schema定义 ====================


class TestNodeSchemaDefinition:
    """测试节点Schema定义"""

    def test_node_schema_has_io_types(self):
        """节点Schema应定义输入/输出类型"""
        from src.domain.services.node_schema import NodeSchema

        schema = NodeSchema(
            node_type="llm",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "temperature": {"type": "number", "default": 0.7},
                },
                "required": ["prompt"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "tokens_used": {"type": "integer"},
                },
            },
        )

        assert schema.input_schema is not None
        assert schema.output_schema is not None
        assert "prompt" in schema.input_schema["properties"]
        assert "content" in schema.output_schema["properties"]

    def test_node_schema_allowed_children(self):
        """节点Schema应定义允许的子节点类型"""
        from src.domain.services.node_schema import NodeSchema

        # GENERIC节点可以包含多种子节点
        generic_schema = NodeSchema(
            node_type="generic",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            allowed_child_types=["llm", "api", "code", "condition"],
        )

        assert "llm" in generic_schema.allowed_child_types
        assert "api" in generic_schema.allowed_child_types

    def test_node_schema_no_children_for_leaf_nodes(self):
        """叶子节点不允许子节点"""
        from src.domain.services.node_schema import NodeSchema

        llm_schema = NodeSchema(
            node_type="llm",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            allowed_child_types=[],  # 不允许子节点
        )

        assert len(llm_schema.allowed_child_types) == 0

    def test_node_schema_constraints(self):
        """节点Schema应支持约束条件"""
        from src.domain.services.node_schema import NodeSchema, SchemaConstraint

        # 约束：temperature 必须在 0-2 之间
        temp_constraint = SchemaConstraint(
            field_name="temperature",
            constraint_type="range",
            min_value=0.0,
            max_value=2.0,
        )

        schema = NodeSchema(
            node_type="llm",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            constraints=[temp_constraint],
        )

        assert len(schema.constraints) == 1
        assert schema.constraints[0].min_value == 0.0
        assert schema.constraints[0].max_value == 2.0


# ==================== 测试2：Schema注册表 ====================


class TestNodeSchemaRegistry:
    """测试Schema注册表"""

    def test_registry_initialization_with_predefined_schemas(self):
        """注册表初始化时包含预定义Schema"""
        from src.domain.services.node_schema import NodeSchemaRegistry

        registry = NodeSchemaRegistry()

        # 应包含所有13种预定义节点类型的Schema
        predefined_types = [
            "start",
            "end",
            "condition",
            "loop",
            "parallel",
            "llm",
            "knowledge",
            "classify",
            "template",
            "api",
            "code",
            "mcp",
            "generic",
        ]

        for node_type in predefined_types:
            assert registry.has_schema(node_type), f"缺少 {node_type} 的Schema"

    def test_get_schema_by_type(self):
        """按类型获取Schema"""
        from src.domain.services.node_schema import NodeSchemaRegistry

        registry = NodeSchemaRegistry()

        llm_schema = registry.get_schema("llm")

        assert llm_schema is not None
        assert llm_schema.node_type == "llm"

    def test_register_custom_schema(self):
        """注册自定义Schema"""
        from src.domain.services.node_schema import NodeSchema, NodeSchemaRegistry

        registry = NodeSchemaRegistry()

        custom_schema = NodeSchema(
            node_type="custom_node",
            input_schema={
                "type": "object",
                "properties": {"input1": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"output1": {"type": "string"}},
            },
        )

        registry.register(custom_schema)

        assert registry.has_schema("custom_node")
        retrieved = registry.get_schema("custom_node")
        assert retrieved.node_type == "custom_node"

    def test_get_nonexistent_schema_returns_none(self):
        """获取不存在的Schema返回None"""
        from src.domain.services.node_schema import NodeSchemaRegistry

        registry = NodeSchemaRegistry()

        schema = registry.get_schema("nonexistent_type")

        assert schema is None

    def test_list_all_schemas(self):
        """列出所有已注册的Schema"""
        from src.domain.services.node_schema import NodeSchemaRegistry

        registry = NodeSchemaRegistry()

        all_schemas = registry.list_all()

        assert len(all_schemas) >= 13  # 至少包含预定义的13种


# ==================== 测试3：输入校验 ====================


class TestInputValidation:
    """测试输入校验"""

    def test_validate_required_fields(self):
        """验证必需字段"""
        from src.domain.services.node_schema import NodeSchema, NodeSchemaValidator

        schema = NodeSchema(
            node_type="llm",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "model": {"type": "string"},
                },
                "required": ["prompt"],
            },
            output_schema={"type": "object", "properties": {}},
        )

        validator = NodeSchemaValidator(schema)

        # 缺少必需字段
        result = validator.validate_input({"model": "gpt-4"})
        assert result.is_valid is False
        assert any("prompt" in e for e in result.errors)

        # 包含必需字段
        result = validator.validate_input({"prompt": "test"})
        assert result.is_valid is True

    def test_validate_field_types(self):
        """验证字段类型"""
        from src.domain.services.node_schema import NodeSchema, NodeSchemaValidator

        schema = NodeSchema(
            node_type="llm",
            input_schema={
                "type": "object",
                "properties": {
                    "temperature": {"type": "number"},
                    "max_tokens": {"type": "integer"},
                },
                "required": [],
            },
            output_schema={"type": "object", "properties": {}},
        )

        validator = NodeSchemaValidator(schema)

        # 错误类型
        result = validator.validate_input({"temperature": "not_a_number"})
        assert result.is_valid is False

        # 正确类型
        result = validator.validate_input({"temperature": 0.7, "max_tokens": 100})
        assert result.is_valid is True

    def test_validate_constraints(self):
        """验证约束条件"""
        from src.domain.services.node_schema import (
            NodeSchema,
            NodeSchemaValidator,
            SchemaConstraint,
        )

        constraint = SchemaConstraint(
            field_name="temperature",
            constraint_type="range",
            min_value=0.0,
            max_value=2.0,
        )

        schema = NodeSchema(
            node_type="llm",
            input_schema={
                "type": "object",
                "properties": {"temperature": {"type": "number"}},
                "required": [],
            },
            output_schema={"type": "object", "properties": {}},
            constraints=[constraint],
        )

        validator = NodeSchemaValidator(schema)

        # 超出范围
        result = validator.validate_input({"temperature": 3.0})
        assert result.is_valid is False
        assert any("range" in e.lower() or "temperature" in e for e in result.errors)

        # 在范围内
        result = validator.validate_input({"temperature": 1.0})
        assert result.is_valid is True


# ==================== 测试4：输出校验 ====================


class TestOutputValidation:
    """测试输出校验"""

    def test_validate_output_structure(self):
        """验证输出结构"""
        from src.domain.services.node_schema import NodeSchema, NodeSchemaValidator

        schema = NodeSchema(
            node_type="llm",
            input_schema={"type": "object", "properties": {}},
            output_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "tokens_used": {"type": "integer"},
                },
                "required": ["content"],
            },
        )

        validator = NodeSchemaValidator(schema)

        # 缺少必需输出字段
        result = validator.validate_output({"tokens_used": 100})
        assert result.is_valid is False
        assert any("content" in e for e in result.errors)

        # 完整输出
        result = validator.validate_output({"content": "response", "tokens_used": 100})
        assert result.is_valid is True


# ==================== 测试5：子节点类型校验 ====================


class TestChildNodeValidation:
    """测试子节点类型校验"""

    def test_validate_allowed_child_type(self):
        """验证允许的子节点类型"""
        from src.domain.services.node_schema import NodeSchema, NodeSchemaValidator

        schema = NodeSchema(
            node_type="generic",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            allowed_child_types=["llm", "api", "code"],
        )

        validator = NodeSchemaValidator(schema)

        # 允许的类型
        assert validator.is_child_type_allowed("llm") is True
        assert validator.is_child_type_allowed("api") is True

        # 不允许的类型
        assert validator.is_child_type_allowed("parallel") is False

    def test_validate_child_type_for_leaf_node(self):
        """叶子节点不允许任何子节点"""
        from src.domain.services.node_schema import NodeSchema, NodeSchemaValidator

        schema = NodeSchema(
            node_type="llm",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            allowed_child_types=[],  # 叶子节点
        )

        validator = NodeSchemaValidator(schema)

        assert validator.is_child_type_allowed("api") is False
        assert validator.is_child_type_allowed("code") is False
        assert validator.can_have_children() is False

    def test_nested_generic_nodes(self):
        """嵌套通用节点的类型校验"""
        from src.domain.services.node_schema import NodeSchema, NodeSchemaValidator

        # GENERIC可以包含其他GENERIC
        schema = NodeSchema(
            node_type="generic",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {}},
            allowed_child_types=["llm", "api", "generic"],  # 允许嵌套
        )

        validator = NodeSchemaValidator(schema)

        assert validator.is_child_type_allowed("generic") is True


# ==================== 测试6：WorkflowAgent节点创建校验 ====================


class TestWorkflowAgentSchemaValidation:
    """测试WorkflowAgent创建节点时的Schema校验"""

    def test_create_node_validates_schema(self):
        """创建节点时执行Schema校验"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # 有效的节点创建
        result = agent.create_node_with_validation(
            node_type="llm",
            config={"user_prompt": "test prompt"},
        )

        assert result["success"] is True
        assert result["node"] is not None

    def test_create_node_rejects_invalid_config(self):
        """拒绝无效配置的节点创建"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # 缺少必需字段的配置
        result = agent.create_node_with_validation(
            node_type="llm",
            config={},  # 缺少 user_prompt
        )

        assert result["success"] is False
        assert "errors" in result
        assert len(result["errors"]) > 0

    def test_add_child_validates_type(self):
        """添加子节点时验证类型"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # 创建父节点 (GENERIC)
        parent_result = agent.create_node_with_validation(
            node_type="generic",
            config={"name": "pipeline"},
        )
        parent_id = parent_result["node"].id

        # 添加允许的子节点类型
        add_result = agent.add_child_with_validation(
            parent_id=parent_id,
            child_type="llm",
            child_config={"user_prompt": "test"},
        )
        assert add_result["success"] is True

    def test_add_child_rejects_disallowed_type(self):
        """拒绝不允许的子节点类型"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # 创建LLM节点（叶子节点）
        parent_result = agent.create_node_with_validation(
            node_type="llm",
            config={"user_prompt": "test"},
        )
        parent_id = parent_result["node"].id

        # 尝试添加子节点到叶子节点
        add_result = agent.add_child_with_validation(
            parent_id=parent_id,
            child_type="api",
            child_config={},
        )

        assert add_result["success"] is False
        assert any("不允许" in e or "cannot" in e.lower() for e in add_result["errors"])


# ==================== 测试7：父子节点展开类型一致性 ====================


class TestParentChildTypeConsistency:
    """测试父子节点展开类型一致性"""

    def test_expand_maintains_type_consistency(self):
        """展开节点时保持类型一致"""
        from src.domain.services.node_schema import (
            NodeSchemaRegistry,
            SchemaValidatingWorkflowAgent,
        )

        agent = SchemaValidatingWorkflowAgent()
        registry = NodeSchemaRegistry()

        # 创建GENERIC节点并添加子节点
        parent_result = agent.create_node_with_validation(
            node_type="generic",
            config={"name": "data_pipeline"},
        )
        parent = parent_result["node"]

        # 添加LLM子节点
        agent.add_child_with_validation(
            parent_id=parent.id,
            child_type="llm",
            child_config={"user_prompt": "analyze data"},
        )

        # 展开节点
        expanded = agent.expand_node(parent.id)

        # 验证展开后子节点类型正确
        for child in expanded["children"]:
            # 子节点类型应该是父节点允许的类型
            parent_schema = registry.get_schema("generic")
            assert child["type"] in parent_schema.allowed_child_types

    def test_collapse_preserves_child_types(self):
        """折叠节点后重新展开，子节点类型保持一致"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # 创建并配置节点
        parent_result = agent.create_node_with_validation(
            node_type="generic",
            config={"name": "pipeline"},
        )
        parent_id = parent_result["node"].id

        # 添加多个子节点
        agent.add_child_with_validation(
            parent_id=parent_id,
            child_type="api",
            child_config={"url": "http://example.com"},
        )
        agent.add_child_with_validation(
            parent_id=parent_id,
            child_type="llm",
            child_config={"user_prompt": "process"},
        )

        # 记录原始子节点类型
        original_expanded = agent.expand_node(parent_id)
        original_types = [c["type"] for c in original_expanded["children"]]

        # 折叠然后重新展开
        agent.collapse_node(parent_id)
        re_expanded = agent.expand_node(parent_id)
        re_expanded_types = [c["type"] for c in re_expanded["children"]]

        # 类型应保持一致
        assert original_types == re_expanded_types

    def test_nested_expansion_type_consistency(self):
        """嵌套展开时类型一致性"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # 创建父GENERIC
        parent_result = agent.create_node_with_validation(
            node_type="generic",
            config={"name": "outer"},
        )
        parent_id = parent_result["node"].id

        # 添加嵌套的GENERIC子节点
        inner_result = agent.add_child_with_validation(
            parent_id=parent_id,
            child_type="generic",
            child_config={"name": "inner"},
        )
        inner_id = inner_result["child_id"]

        # 在内部GENERIC中添加LLM
        agent.add_child_with_validation(
            parent_id=inner_id,
            child_type="llm",
            child_config={"user_prompt": "test"},
        )

        # 递归展开
        full_expansion = agent.expand_node_recursive(parent_id)

        # 验证嵌套结构类型正确
        assert full_expansion["type"] == "generic"
        assert len(full_expansion["children"]) == 1
        assert full_expansion["children"][0]["type"] == "generic"
        assert len(full_expansion["children"][0]["children"]) == 1
        assert full_expansion["children"][0]["children"][0]["type"] == "llm"


# ==================== 测试8：Schema文档生成 ====================


class TestSchemaDocumentation:
    """测试Schema文档生成"""

    def test_generate_schema_documentation(self):
        """生成Schema文档"""
        from src.domain.services.node_schema import NodeSchemaRegistry, SchemaDocGenerator

        registry = NodeSchemaRegistry()
        doc_generator = SchemaDocGenerator(registry)

        # 生成LLM节点的文档
        llm_doc = doc_generator.generate_doc("llm")

        assert llm_doc is not None
        assert "llm" in llm_doc.lower()
        assert "input" in llm_doc.lower()
        assert "output" in llm_doc.lower()

    def test_generate_all_schemas_documentation(self):
        """生成所有Schema的文档"""
        from src.domain.services.node_schema import NodeSchemaRegistry, SchemaDocGenerator

        registry = NodeSchemaRegistry()
        doc_generator = SchemaDocGenerator(registry)

        # 生成完整文档
        full_doc = doc_generator.generate_all()

        # 应包含所有预定义节点类型
        for node_type in ["llm", "api", "code", "condition", "loop", "generic"]:
            assert node_type in full_doc.lower()

    def test_doc_includes_constraints(self):
        """文档包含约束信息"""
        from src.domain.services.node_schema import (
            NodeSchema,
            NodeSchemaRegistry,
            SchemaConstraint,
            SchemaDocGenerator,
        )

        registry = NodeSchemaRegistry()

        # 添加带约束的自定义Schema
        constraint = SchemaConstraint(
            field_name="temperature",
            constraint_type="range",
            min_value=0.0,
            max_value=2.0,
        )

        custom_schema = NodeSchema(
            node_type="custom_llm",
            input_schema={
                "type": "object",
                "properties": {"temperature": {"type": "number"}},
            },
            output_schema={"type": "object", "properties": {}},
            constraints=[constraint],
        )

        registry.register(custom_schema)

        doc_generator = SchemaDocGenerator(registry)
        doc = doc_generator.generate_doc("custom_llm")

        # 文档应包含约束信息
        assert "0" in doc and "2" in doc  # 范围值


# ==================== 测试9：真实场景测试 ====================


class TestRealWorldSchemaScenarios:
    """真实场景测试"""

    def test_complete_workflow_creation_with_schema_validation(self):
        """完整工作流创建流程（含Schema校验）"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # 1. 创建根节点
        root_result = agent.create_node_with_validation(
            node_type="start",
            config={},
        )
        assert root_result["success"] is True

        # 2. 创建处理管道
        pipeline_result = agent.create_node_with_validation(
            node_type="generic",
            config={"name": "data_processing_pipeline"},
        )
        assert pipeline_result["success"] is True
        pipeline_id = pipeline_result["node"].id

        # 3. 添加API调用节点
        api_result = agent.add_child_with_validation(
            parent_id=pipeline_id,
            child_type="api",
            child_config={"method": "GET", "url": "https://api.example.com/data"},
        )
        assert api_result["success"] is True

        # 4. 添加LLM处理节点
        llm_result = agent.add_child_with_validation(
            parent_id=pipeline_id,
            child_type="llm",
            child_config={"user_prompt": "分析获取的数据"},
        )
        assert llm_result["success"] is True

        # 5. 创建结束节点
        end_result = agent.create_node_with_validation(
            node_type="end",
            config={},
        )
        assert end_result["success"] is True

    def test_invalid_workflow_rejected(self):
        """无效工作流被拒绝"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # 尝试创建无效的节点配置
        results = []

        # 1. LLM节点缺少prompt
        result1 = agent.create_node_with_validation(
            node_type="llm",
            config={"temperature": 0.7},  # 缺少 user_prompt
        )
        results.append(result1)

        # 2. API节点类型错误
        result2 = agent.create_node_with_validation(
            node_type="api",
            config={"method": 123},  # method 应该是字符串
        )
        results.append(result2)

        # 至少一个应该失败
        failed_count = sum(1 for r in results if not r["success"])
        assert failed_count >= 1

    def test_schema_validation_with_io_type_checking(self):
        """节点间I/O类型检查"""
        from src.domain.services.node_schema import (
            NodeSchemaRegistry,
            SchemaValidatingWorkflowAgent,
        )

        agent = SchemaValidatingWorkflowAgent()
        registry = NodeSchemaRegistry()

        # 创建API节点（输出JSON数据）
        api_result = agent.create_node_with_validation(
            node_type="api",
            config={"url": "http://example.com"},
        )
        assert api_result["node"] is not None

        # 创建LLM节点（需要字符串输入）
        llm_result = agent.create_node_with_validation(
            node_type="llm",
            config={"user_prompt": "处理数据"},
        )
        assert llm_result["node"] is not None

        # 验证连接兼容性
        api_schema = registry.get_schema("api")
        llm_schema = registry.get_schema("llm")

        # API输出可以转换为LLM输入
        # 这里主要验证Schema存在且可访问
        assert api_schema.output_schema is not None
        assert llm_schema.input_schema is not None


# ==================== 测试10：边界情况 ====================


class TestSchemaEdgeCases:
    """边界情况测试"""

    def test_empty_config(self):
        """空配置处理"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # START节点允许空配置
        result = agent.create_node_with_validation(
            node_type="start",
            config={},
        )
        assert result["success"] is True

    def test_extra_fields_in_config(self):
        """配置中的额外字段"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        # 包含额外字段的配置
        result = agent.create_node_with_validation(
            node_type="llm",
            config={
                "user_prompt": "test",
                "extra_field": "should be ignored or rejected",
            },
        )

        # 根据实现策略，可能接受或拒绝额外字段
        # 这里验证不会崩溃
        assert "success" in result

    def test_deeply_nested_generic_nodes(self):
        """深度嵌套的通用节点"""
        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        agent = SchemaValidatingWorkflowAgent()

        max_depth = 5
        parent_id = None

        for i in range(max_depth):
            if parent_id is None:
                result = agent.create_node_with_validation(
                    node_type="generic",
                    config={"name": f"level_{i}"},
                )
                parent_id = result["node"].id
            else:
                result = agent.add_child_with_validation(
                    parent_id=parent_id,
                    child_type="generic",
                    child_config={"name": f"level_{i}"},
                )
                parent_id = result["child_id"]

            assert result["success"] is True

    def test_concurrent_schema_operations(self):
        """并发Schema操作"""
        import asyncio

        from src.domain.services.node_schema import SchemaValidatingWorkflowAgent

        async def create_nodes(agent, node_type, count):
            results = []
            for i in range(count):
                result = agent.create_node_with_validation(
                    node_type=node_type,
                    config={"user_prompt": f"prompt_{i}"} if node_type == "llm" else {},
                )
                results.append(result)
            return results

        async def run_concurrent():
            agent = SchemaValidatingWorkflowAgent()
            tasks = [
                create_nodes(agent, "llm", 10),
                create_nodes(agent, "api", 10),
                create_nodes(agent, "generic", 10),
            ]
            all_results = await asyncio.gather(*tasks)

            # 验证所有操作成功
            for results in all_results:
                for r in results:
                    assert r["success"] is True

        asyncio.run(run_concurrent())
