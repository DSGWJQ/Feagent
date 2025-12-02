"""节点定义测试 - Phase 8.1

TDD RED阶段：测试 NodeDefinition 数据结构
"""


class TestNodeDefinition:
    """NodeDefinition 基础测试"""

    def test_create_python_node_definition_with_code(self):
        """Python 节点应包含可执行代码"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="数据处理",
            code="result = input_data * 2\nreturn {'output': result}",
        )

        assert node.node_type == NodeType.PYTHON
        assert node.name == "数据处理"
        assert node.code is not None
        assert "result" in node.code

    def test_create_llm_node_definition_with_prompt(self):
        """LLM 节点应包含 Prompt 模板"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.LLM,
            name="文本总结",
            prompt="请总结以下内容：{content}",
            config={"model": "gpt-4", "temperature": 0.7},
        )

        assert node.node_type == NodeType.LLM
        assert node.prompt is not None
        assert "{content}" in node.prompt
        assert node.config["model"] == "gpt-4"

    def test_create_http_node_definition_with_url(self):
        """HTTP 节点应包含 URL 和方法"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.HTTP,
            name="获取天气",
            url="https://api.weather.com/v1/current",
            method="GET",
            config={"headers": {"Authorization": "Bearer xxx"}},
        )

        assert node.node_type == NodeType.HTTP
        assert node.url == "https://api.weather.com/v1/current"
        assert node.method == "GET"

    def test_create_database_node_definition_with_query(self):
        """Database 节点应包含 SQL 查询"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.DATABASE,
            name="查询用户",
            query="SELECT * FROM users WHERE status = 'active'",
            config={"database": "main_db"},
        )

        assert node.node_type == NodeType.DATABASE
        assert node.query is not None
        assert "SELECT" in node.query

    def test_node_definition_has_unique_id(self):
        """节点定义应有唯一ID"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node1 = NodeDefinition(node_type=NodeType.GENERIC, name="Node1")
        node2 = NodeDefinition(node_type=NodeType.GENERIC, name="Node2")

        assert node1.id is not None
        assert node2.id is not None
        assert node1.id != node2.id


class TestNodeDefinitionValidation:
    """NodeDefinition 验证测试"""

    def test_python_node_without_code_should_fail_validation(self):
        """Python 节点缺少 code 应验证失败"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="无代码节点",
            # 没有 code
        )

        errors = node.validate()
        assert len(errors) > 0
        assert any("code" in err.lower() for err in errors)

    def test_llm_node_without_prompt_should_fail_validation(self):
        """LLM 节点缺少 prompt 应验证失败"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.LLM,
            name="无Prompt节点",
            # 没有 prompt
        )

        errors = node.validate()
        assert len(errors) > 0
        assert any("prompt" in err.lower() for err in errors)

    def test_http_node_without_url_should_fail_validation(self):
        """HTTP 节点缺少 url 应验证失败"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.HTTP,
            name="无URL节点",
            # 没有 url
        )

        errors = node.validate()
        assert len(errors) > 0
        assert any("url" in err.lower() for err in errors)

    def test_database_node_without_query_should_fail_validation(self):
        """Database 节点缺少 query 应验证失败"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.DATABASE,
            name="无查询节点",
            # 没有 query
        )

        errors = node.validate()
        assert len(errors) > 0
        assert any("query" in err.lower() for err in errors)

    def test_node_without_name_should_fail_validation(self):
        """节点缺少 name 应验证失败"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="",  # 空名称
            code="print('hello')",
        )

        errors = node.validate()
        assert len(errors) > 0
        assert any("name" in err.lower() for err in errors)

    def test_valid_python_node_should_pass_validation(self):
        """有效的 Python 节点应通过验证"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="有效节点",
            code="return {'result': 42}",
        )

        errors = node.validate()
        assert len(errors) == 0

    def test_generic_node_should_always_pass_validation(self):
        """GENERIC 节点应始终通过验证（无特殊要求）"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="通用节点",
        )

        errors = node.validate()
        assert len(errors) == 0


class TestNodeDefinitionFactory:
    """NodeDefinitionFactory 工厂测试"""

    def test_factory_creates_python_node(self):
        """工厂应创建 Python 节点"""
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_python_node(
            name="计算节点",
            code="return x + y",
            description="执行加法运算",
        )

        assert node.name == "计算节点"
        assert node.code == "return x + y"
        assert node.description == "执行加法运算"

    def test_factory_creates_llm_node(self):
        """工厂应创建 LLM 节点"""
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_llm_node(
            name="文本分析",
            prompt="分析这段文本：{text}",
            model="gpt-4",
            temperature=0.5,
        )

        assert node.name == "文本分析"
        assert "{text}" in node.prompt
        assert node.config.get("model") == "gpt-4"
        assert node.config.get("temperature") == 0.5

    def test_factory_creates_http_node(self):
        """工厂应创建 HTTP 节点"""
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_http_node(
            name="API调用",
            url="https://api.example.com/data",
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        assert node.name == "API调用"
        assert node.url == "https://api.example.com/data"
        assert node.method == "POST"
        assert node.config.get("headers") is not None

    def test_factory_creates_database_node(self):
        """工厂应创建 Database 节点"""
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_database_node(
            name="查询订单",
            query="SELECT * FROM orders WHERE date > :start_date",
            database="sales_db",
        )

        assert node.name == "查询订单"
        assert "orders" in node.query
        assert node.config.get("database") == "sales_db"


class TestNodeDefinitionSchema:
    """NodeDefinition 输入输出 Schema 测试"""

    def test_node_with_input_schema(self):
        """节点应支持输入 Schema 定义"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="处理节点",
            code="return process(data)",
            input_schema={
                "data": "dict",
                "threshold": "float",
            },
        )

        assert "data" in node.input_schema
        assert node.input_schema["data"] == "dict"

    def test_node_with_output_schema(self):
        """节点应支持输出 Schema 定义"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="分析节点",
            code="return {'result': analyze(data)}",
            output_schema={
                "result": "dict",
                "confidence": "float",
            },
        )

        assert "result" in node.output_schema
        assert node.output_schema["result"] == "dict"

    def test_node_to_dict_should_serialize_all_fields(self):
        """to_dict 应序列化所有字段"""
        from src.domain.agents.node_definition import NodeDefinition, NodeType

        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="测试节点",
            description="测试用",
            code="return 42",
            input_schema={"x": "int"},
            output_schema={"result": "int"},
        )

        data = node.to_dict()

        assert data["id"] == node.id
        assert data["node_type"] == "python"
        assert data["name"] == "测试节点"
        assert data["code"] == "return 42"
        assert "input_schema" in data
        assert "output_schema" in data

    def test_node_from_dict_should_deserialize(self):
        """from_dict 应反序列化"""
        from src.domain.agents.node_definition import NodeDefinition

        data = {
            "id": "node_123",
            "node_type": "python",
            "name": "恢复的节点",
            "code": "return 100",
            "input_schema": {"a": "int"},
            "output_schema": {"b": "int"},
        }

        node = NodeDefinition.from_dict(data)

        assert node.id == "node_123"
        assert node.name == "恢复的节点"
        assert node.code == "return 100"
