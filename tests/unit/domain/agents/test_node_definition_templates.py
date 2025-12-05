"""节点定义模板测试 - Phase 8.3 TDD Red 阶段

测试目标：
1. NodeDefinitionFactory 提供场景化模板方法
2. 模板方法生成正确配置的节点
3. 节点配置符合 ConversationAgent LLM 输出格式
4. 节点可以被 WorkflowAgent 正确执行

完成标准：
- 模板方法测试全部失败（Red）
- 然后实现模板方法让测试通过（Green）
- 最后重构优化（Refactor）
"""


class TestDataCollectionNodeTemplate:
    """测试数据采集节点模板"""

    def test_create_data_collection_node_should_return_database_node(self):
        """创建数据采集节点应返回 DATABASE 类型节点

        场景：需要从数据库获取销售数据
        期望：返回配置正确的 DATABASE 节点
        """
        from src.domain.agents.node_definition import (
            NodeDefinitionFactory,
            NodeType,
        )

        # 执行：使用模板方法创建数据采集节点
        node = NodeDefinitionFactory.create_data_collection_node(
            name="获取销售数据",
            table="sales",
            time_range="3 months",
            filters={"status": "completed"},
        )

        # 断言：节点类型和配置
        assert node.node_type == NodeType.DATABASE
        assert node.name == "获取销售数据"
        assert node.query is not None
        assert "sales" in node.query
        assert "3" in node.query or "month" in node.query.lower()

    def test_data_collection_node_should_have_connection_config(self):
        """数据采集节点应包含数据库连接配置

        场景：节点需要连接到特定数据库
        期望：config 包含 database 配置
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_data_collection_node(
            name="获取用户数据",
            table="users",
            database="main_db",
        )

        assert "database" in node.config
        assert node.config["database"] == "main_db"

    def test_data_collection_node_with_custom_query(self):
        """数据采集节点应支持自定义查询

        场景：需要复杂的 SQL 查询
        期望：可以传入自定义 query 参数
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        custom_query = "SELECT product_id, SUM(amount) FROM sales GROUP BY product_id"
        node = NodeDefinitionFactory.create_data_collection_node(
            name="产品销售统计",
            query=custom_query,
        )

        assert node.query == custom_query


class TestMetricCalculationNodeTemplate:
    """测试指标计算节点模板"""

    def test_create_metric_calculation_node_should_return_python_node(self):
        """创建指标计算节点应返回 PYTHON 类型节点

        场景：需要计算销售趋势指标
        期望：返回包含 pandas 计算代码的 PYTHON 节点
        """
        from src.domain.agents.node_definition import (
            NodeDefinitionFactory,
            NodeType,
        )

        node = NodeDefinitionFactory.create_metric_calculation_node(
            name="计算销售趋势",
            metrics=["sum", "avg", "trend"],
            group_by="month",
        )

        assert node.node_type == NodeType.PYTHON
        assert node.name == "计算销售趋势"
        assert node.code is not None
        assert "pandas" in node.code or "pd" in node.code

    def test_metric_calculation_node_should_handle_multiple_metrics(self):
        """指标计算节点应支持多个指标计算

        场景：同时计算总和、平均值、趋势
        期望：代码包含所有指标的计算逻辑
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_metric_calculation_node(
            name="多指标计算",
            metrics=["sum", "avg", "max", "min"],
        )

        code_lower = node.code.lower()
        assert "sum" in code_lower
        assert "avg" in code_lower or "mean" in code_lower
        assert "max" in code_lower
        assert "min" in code_lower

    def test_metric_calculation_node_with_group_by(self):
        """指标计算节点应支持分组聚合

        场景：按月份分组计算销售额
        期望：代码包含 groupby 逻辑
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_metric_calculation_node(
            name="按月统计",
            metrics=["sum"],
            group_by="month",
        )

        assert "group" in node.code.lower()

    def test_metric_calculation_node_should_have_input_schema(self):
        """指标计算节点应定义输入 schema

        场景：节点需要接收上游数据
        期望：input_schema 定义数据格式
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_metric_calculation_node(
            name="计算指标",
            metrics=["sum"],
        )

        assert node.input_schema is not None
        assert "data" in node.input_schema or "input_data" in node.input_schema


class TestChartGenerationNodeTemplate:
    """测试图表生成节点模板"""

    def test_create_chart_generation_node_should_return_python_node(self):
        """创建图表生成节点应返回 PYTHON 类型节点

        场景：需要生成销售趋势图
        期望：返回包含 matplotlib 代码的 PYTHON 节点
        """
        from src.domain.agents.node_definition import (
            NodeDefinitionFactory,
            NodeType,
        )

        node = NodeDefinitionFactory.create_chart_generation_node(
            name="生成趋势图",
            chart_type="line",
            title="销售趋势",
            x_label="月份",
            y_label="销售额",
        )

        assert node.node_type == NodeType.PYTHON
        assert node.name == "生成趋势图"
        assert node.code is not None
        assert "matplotlib" in node.code or "plt" in node.code

    def test_chart_generation_node_should_support_different_chart_types(self):
        """图表生成节点应支持多种图表类型

        场景：需要生成不同类型的图表（折线图、柱状图、饼图）
        期望：根据 chart_type 生成相应代码
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        line_node = NodeDefinitionFactory.create_chart_generation_node(
            name="折线图", chart_type="line", title="趋势"
        )
        bar_node = NodeDefinitionFactory.create_chart_generation_node(
            name="柱状图", chart_type="bar", title="对比"
        )
        pie_node = NodeDefinitionFactory.create_chart_generation_node(
            name="饼图", chart_type="pie", title="占比"
        )

        assert "plot" in line_node.code.lower()
        assert "bar" in bar_node.code.lower()
        assert "pie" in pie_node.code.lower()

    def test_chart_generation_node_should_save_to_file(self):
        """图表生成节点应保存图表到文件

        场景：生成的图表需要保存为图片
        期望：代码包含 savefig 逻辑
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_chart_generation_node(
            name="保存图表", chart_type="line", title="测试"
        )

        assert "savefig" in node.code.lower()

    def test_chart_generation_node_should_have_customizable_style(self):
        """图表生成节点应支持样式自定义

        场景：需要设置图表颜色、大小等样式
        期望：config 包含 style 配置
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_chart_generation_node(
            name="自定义图表",
            chart_type="line",
            title="测试",
            figsize=(12, 6),
            color="blue",
        )

        assert "figsize" in node.config
        assert node.config["figsize"] == (12, 6)


class TestDataAnalysisNodeTemplate:
    """测试数据分析节点模板"""

    def test_create_data_analysis_node_should_return_llm_node(self):
        """创建数据分析节点应返回 LLM 类型节点

        场景：需要 LLM 分析数据并生成报告
        期望：返回配置正确的 LLM 节点
        """
        from src.domain.agents.node_definition import (
            NodeDefinitionFactory,
            NodeType,
        )

        node = NodeDefinitionFactory.create_data_analysis_node(
            name="生成分析报告",
            analysis_type="summary",
        )

        assert node.node_type == NodeType.LLM
        assert node.name == "生成分析报告"
        assert node.prompt is not None

    def test_data_analysis_node_should_have_analysis_type_in_prompt(self):
        """数据分析节点 prompt 应包含分析类型

        场景：不同分析类型需要不同的 prompt
        期望：prompt 包含分析类型相关内容
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        summary_node = NodeDefinitionFactory.create_data_analysis_node(
            name="数据总结", analysis_type="summary"
        )
        insight_node = NodeDefinitionFactory.create_data_analysis_node(
            name="洞察分析", analysis_type="insight"
        )
        recommendation_node = NodeDefinitionFactory.create_data_analysis_node(
            name="建议生成", analysis_type="recommendation"
        )

        assert "summary" in summary_node.prompt.lower() or "总结" in summary_node.prompt
        assert "insight" in insight_node.prompt.lower() or "洞察" in insight_node.prompt
        assert (
            "recommendation" in recommendation_node.prompt.lower()
            or "建议" in recommendation_node.prompt
        )

    def test_data_analysis_node_should_support_custom_model(self):
        """数据分析节点应支持自定义模型

        场景：需要使用特定的 LLM 模型
        期望：config 包含 model 配置
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_data_analysis_node(
            name="高级分析",
            analysis_type="insight",
            model="gpt-4-turbo",
            temperature=0.3,
        )

        assert node.config["model"] == "gpt-4-turbo"
        assert node.config["temperature"] == 0.3

    def test_data_analysis_node_should_reference_input_data(self):
        """数据分析节点 prompt 应引用输入数据

        场景：LLM 需要基于上游数据进行分析
        期望：prompt 包含数据引用占位符
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_data_analysis_node(
            name="分析销售数据", analysis_type="summary"
        )

        # prompt 应该包含数据占位符，如 {data} 或 {input_data}
        assert "{" in node.prompt and "}" in node.prompt


class TestNodeTemplateIntegration:
    """测试节点模板集成"""

    def test_all_template_nodes_should_pass_validation(self):
        """所有模板节点应通过验证

        场景：模板生成的节点应该是完整且有效的
        期望：所有节点 validate() 返回空错误列表
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        nodes = [
            NodeDefinitionFactory.create_data_collection_node(name="采集数据", table="sales"),
            NodeDefinitionFactory.create_metric_calculation_node(name="计算指标", metrics=["sum"]),
            NodeDefinitionFactory.create_chart_generation_node(
                name="生成图表", chart_type="line", title="趋势"
            ),
            NodeDefinitionFactory.create_data_analysis_node(
                name="分析数据", analysis_type="summary"
            ),
        ]

        for node in nodes:
            errors = node.validate()
            assert len(errors) == 0, f"Node {node.name} validation failed: {errors}"

    def test_template_nodes_should_be_serializable(self):
        """模板节点应可序列化

        场景：节点需要通过 EventBus 传输
        期望：所有节点可以 to_dict() 和 from_dict()
        """
        from src.domain.agents.node_definition import (
            NodeDefinition,
            NodeDefinitionFactory,
        )

        node = NodeDefinitionFactory.create_data_collection_node(
            name="测试节点", table="test_table"
        )

        # 序列化
        node_dict = node.to_dict()
        assert isinstance(node_dict, dict)
        assert "node_type" in node_dict
        assert "name" in node_dict

        # 反序列化
        restored_node = NodeDefinition.from_dict(node_dict)
        assert restored_node.name == node.name
        assert restored_node.node_type == node.node_type


# 导出
__all__ = [
    "TestDataCollectionNodeTemplate",
    "TestMetricCalculationNodeTemplate",
    "TestChartGenerationNodeTemplate",
    "TestDataAnalysisNodeTemplate",
    "TestNodeTemplateIntegration",
]
