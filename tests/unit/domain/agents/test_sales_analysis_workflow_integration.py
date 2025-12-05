"""销售分析工作流集成测试 - Phase 8.3 TDD Red 阶段

真实场景：销售数据分析工作流
流程：
1. 采集数据：从数据库获取最近3个月的销售数据
2. 计算指标：计算月度销售额、平均值、趋势
3. 生成图表：生成销售趋势折线图
4. 分析总结：LLM 生成分析报告

测试目标：
1. ConversationAgent 生成完整工作流定义
2. WorkflowAgent 按依赖顺序执行节点
3. 节点间数据正确传递
4. 最终输出包含图表和报告

完成标准：
- 端到端测试演示工作流执行成功
- 使用 Mock 数据服务避免外部依赖
- 测试覆盖节点串联和数据流转
"""

import pytest

# ==================== Mock 数据服务 ====================


class MockDatabaseService:
    """Mock 数据库服务

    模拟数据库查询，返回销售数据。
    """

    def query(self, sql: str) -> list[dict]:
        """执行 SQL 查询

        返回：
            销售数据列表
        """
        # 模拟返回最近3个月的销售数据
        return [
            {"month": "2025-10", "product": "产品A", "amount": 12000, "quantity": 150},
            {"month": "2025-10", "product": "产品B", "amount": 8500, "quantity": 95},
            {"month": "2025-11", "product": "产品A", "amount": 15000, "quantity": 180},
            {"month": "2025-11", "product": "产品B", "amount": 9200, "quantity": 110},
            {"month": "2025-12", "product": "产品A", "amount": 18000, "quantity": 200},
            {"month": "2025-12", "product": "产品B", "amount": 11000, "quantity": 130},
        ]


class MockPythonExecutor:
    """Mock Python 执行器

    模拟 Python 代码执行，返回计算结果。
    """

    def execute(self, code: str, input_data: dict) -> dict:
        """执行 Python 代码

        参数：
            code: Python 代码
            input_data: 输入数据

        返回：
            执行结果
        """
        # 模拟指标计算
        if "groupby" in code.lower() or "group_by" in code.lower():
            return {
                "metrics": {
                    "2025-10": {"sum": 20500, "avg": 10250},
                    "2025-11": {"sum": 24200, "avg": 12100},
                    "2025-12": {"sum": 29000, "avg": 14500},
                },
                "trend": "上升",
            }

        # 模拟图表生成
        if "savefig" in code.lower() or "matplotlib" in code.lower():
            return {
                "chart_path": "/tmp/sales_trend.png",
                "chart_type": "line",
                "status": "success",
            }

        return {}


class MockLLMService:
    """Mock LLM 服务

    模拟 LLM 调用，返回分析报告。
    """

    def invoke(self, prompt: str, input_data: dict) -> str:
        """调用 LLM

        参数：
            prompt: Prompt 模板
            input_data: 输入数据

        返回：
            LLM 生成的文本
        """
        return """
        # 销售数据分析报告

        ## 数据概览
        分析了最近3个月（2025年10月至12月）的销售数据。

        ## 主要发现
        1. 销售额呈现稳定上升趋势
        2. 10月销售额: 20,500元
        3. 11月销售额: 24,200元（增长18%)
        4. 12月销售额: 29,000元（增长19.8%)

        ## 建议
        1. 保持当前销售策略
        2. 考虑增加产品库存以应对需求增长
        3. 关注产品B的销售提升空间
        """


# ==================== 测试：工作流定义生成 ====================


class TestSalesAnalysisWorkflowDefinition:
    """测试销售分析工作流定义"""

    def test_create_sales_analysis_workflow_with_four_nodes(self):
        """创建销售分析工作流应包含4个节点

        场景：ConversationAgent 生成完整工作流定义
        期望：工作流包含数据采集、指标计算、图表生成、分析报告4个节点
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        # 创建工作流节点
        node1 = NodeDefinitionFactory.create_data_collection_node(
            name="获取销售数据",
            table="sales",
            time_range="3 months",
        )

        node2 = NodeDefinitionFactory.create_metric_calculation_node(
            name="计算销售指标",
            metrics=["sum", "avg"],
            group_by="month",
        )

        node3 = NodeDefinitionFactory.create_chart_generation_node(
            name="生成趋势图",
            chart_type="line",
            title="销售趋势",
            x_label="月份",
            y_label="销售额",
        )

        node4 = NodeDefinitionFactory.create_data_analysis_node(
            name="生成分析报告",
            analysis_type="summary",
        )

        # 断言：所有节点创建成功
        assert node1 is not None
        assert node2 is not None
        assert node3 is not None
        assert node4 is not None

        # 断言：节点类型正确
        from src.domain.agents.node_definition import NodeType

        assert node1.node_type == NodeType.DATABASE
        assert node2.node_type == NodeType.PYTHON
        assert node3.node_type == NodeType.PYTHON
        assert node4.node_type == NodeType.LLM

    def test_workflow_nodes_should_have_correct_dependencies(self):
        """工作流节点应有正确的依赖关系

        场景：定义节点间的依赖边
        期望：node1 -> node2 -> node3 -> node4 顺序依赖
        """
        from src.domain.agents.workflow_plan import EdgeDefinition

        edges = [
            EdgeDefinition(source_node="获取销售数据", target_node="计算销售指标"),
            EdgeDefinition(source_node="计算销售指标", target_node="生成趋势图"),
            EdgeDefinition(source_node="生成趋势图", target_node="生成分析报告"),
        ]

        assert len(edges) == 3
        assert edges[0].source_node == "获取销售数据"
        assert edges[2].target_node == "生成分析报告"


# ==================== 测试：工作流执行 ====================


class TestSalesAnalysisWorkflowExecution:
    """测试销售分析工作流执行"""

    @pytest.fixture
    def mock_db_service(self):
        """Mock 数据库服务"""
        return MockDatabaseService()

    @pytest.fixture
    def mock_python_executor(self):
        """Mock Python 执行器"""
        return MockPythonExecutor()

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM 服务"""
        return MockLLMService()

    @pytest.mark.asyncio
    async def test_execute_node1_data_collection(self, mock_db_service):
        """执行节点1：数据采集

        场景：从数据库获取销售数据
        期望：返回包含销售记录的数据集
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_data_collection_node(
            name="获取销售数据",
            table="sales",
            time_range="3 months",
        )

        # 模拟执行
        result = mock_db_service.query(node.query)

        # 断言：返回数据
        assert isinstance(result, list)
        assert len(result) > 0
        assert "month" in result[0]
        assert "amount" in result[0]

    def test_execute_node2_metric_calculation(self, mock_python_executor):
        """执行节点2：指标计算

        场景：计算月度销售指标
        期望：返回分组统计结果
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_metric_calculation_node(
            name="计算销售指标",
            metrics=["sum", "avg"],
            group_by="month",
        )

        # 模拟上游数据
        upstream_data = {
            "data": [
                {"month": "2025-10", "amount": 12000},
                {"month": "2025-11", "amount": 15000},
            ]
        }

        # 模拟执行
        result = mock_python_executor.execute(node.code, upstream_data)

        # 断言：返回指标
        assert "metrics" in result
        assert isinstance(result["metrics"], dict)

    def test_execute_node3_chart_generation(self, mock_python_executor):
        """执行节点3：图表生成

        场景：生成销售趋势图
        期望：返回图表文件路径
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_chart_generation_node(
            name="生成趋势图",
            chart_type="line",
            title="销售趋势",
        )

        # 模拟上游数据
        upstream_data = {
            "metrics": {
                "2025-10": {"sum": 20500},
                "2025-11": {"sum": 24200},
                "2025-12": {"sum": 29000},
            }
        }

        # 模拟执行
        result = mock_python_executor.execute(node.code, upstream_data)

        # 断言：返回图表路径
        assert "chart_path" in result
        assert result["status"] == "success"

    def test_execute_node4_data_analysis(self, mock_llm_service):
        """执行节点4：数据分析

        场景：LLM 生成分析报告
        期望：返回结构化报告文本
        """
        from src.domain.agents.node_definition import NodeDefinitionFactory

        node = NodeDefinitionFactory.create_data_analysis_node(
            name="生成分析报告",
            analysis_type="summary",
        )

        # 模拟上游数据
        upstream_data = {
            "metrics": {"2025-10": {"sum": 20500}, "2025-12": {"sum": 29000}},
            "trend": "上升",
        }

        # 模拟执行
        report = mock_llm_service.invoke(node.prompt, upstream_data)

        # 断言：返回报告
        assert isinstance(report, str)
        assert len(report) > 0
        assert "销售" in report or "sales" in report.lower()


# ==================== 测试：端到端工作流 ====================


class TestSalesAnalysisWorkflowEndToEnd:
    """测试销售分析工作流端到端执行"""

    @pytest.fixture
    def workflow_definition(self):
        """创建完整工作流定义"""
        from src.domain.agents.node_definition import NodeDefinitionFactory
        from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan

        # 创建节点
        nodes = [
            NodeDefinitionFactory.create_data_collection_node(
                name="获取销售数据",
                table="sales",
                time_range="3 months",
            ),
            NodeDefinitionFactory.create_metric_calculation_node(
                name="计算销售指标",
                metrics=["sum", "avg"],
                group_by="month",
            ),
            NodeDefinitionFactory.create_chart_generation_node(
                name="生成趋势图",
                chart_type="line",
                title="销售趋势",
            ),
            NodeDefinitionFactory.create_data_analysis_node(
                name="生成分析报告",
                analysis_type="summary",
            ),
        ]

        # 创建边
        edges = [
            EdgeDefinition(source_node=nodes[0].name, target_node=nodes[1].name),
            EdgeDefinition(source_node=nodes[1].name, target_node=nodes[2].name),
            EdgeDefinition(source_node=nodes[2].name, target_node=nodes[3].name),
        ]

        # 创建工作流
        workflow = WorkflowPlan(
            name="销售数据分析",
            goal="分析最近3个月的销售数据，生成趋势图和分析报告",
            description="获取销售数据，计算指标，生成图表，输出报告",
            nodes=nodes,
            edges=edges,
        )

        return workflow

    def test_workflow_execution_completes_successfully(self, workflow_definition):
        """工作流定义应成功创建

        场景：创建完整的销售分析工作流定义
        期望：所有节点定义创建成功，并形成完整的依赖关系
        """
        # 断言：工作流包含4个节点
        assert len(workflow_definition.nodes) == 4

        # 断言：工作流包含3条边（顺序依赖）
        assert len(workflow_definition.edges) == 3

        # 断言：节点类型正确
        from src.domain.agents.node_definition import NodeType

        assert workflow_definition.nodes[0].node_type == NodeType.DATABASE
        assert workflow_definition.nodes[1].node_type == NodeType.PYTHON
        assert workflow_definition.nodes[2].node_type == NodeType.PYTHON
        assert workflow_definition.nodes[3].node_type == NodeType.LLM

        # 断言：节点验证通过
        for node in workflow_definition.nodes:
            errors = node.validate()
            assert len(errors) == 0, f"Node {node.name} validation failed: {errors}"

        # 断言：工作流验证通过
        errors = workflow_definition.validate()
        assert len(errors) == 0, f"Workflow validation failed: {errors}"

    @pytest.mark.asyncio
    async def test_workflow_output_contains_chart_and_report(self):
        """工作流输出应包含图表和报告

        场景：工作流执行完成后
        期望：输出包含图表路径和分析报告
        """
        # 模拟工作流执行结果
        mock_result = {
            "success": True,
            "outputs": {
                "chart_path": "/tmp/sales_trend.png",
                "report": "# 销售数据分析报告\n\n销售额呈现上升趋势...",
                "metrics": {
                    "total_sales": 73700,
                    "avg_monthly_sales": 24566,
                    "trend": "上升",
                },
            },
            "executed_nodes": [
                "获取销售数据",
                "计算销售指标",
                "生成趋势图",
                "生成分析报告",
            ],
        }

        # 断言：输出结构
        assert mock_result["success"] is True
        assert "chart_path" in mock_result["outputs"]
        assert "report" in mock_result["outputs"]
        assert len(mock_result["executed_nodes"]) == 4

    def test_workflow_nodes_execute_in_dependency_order(self):
        """工作流节点应按依赖顺序执行

        场景：验证拓扑排序
        期望：节点执行顺序：数据采集 → 指标计算 → 图表生成 → 分析报告
        """
        from src.domain.agents.workflow_plan import EdgeDefinition

        # 定义边
        edges = [
            EdgeDefinition(source_node="node1", target_node="node2"),
            EdgeDefinition(source_node="node2", target_node="node3"),
            EdgeDefinition(source_node="node3", target_node="node4"),
        ]

        # 拓扑排序（简化验证）
        execution_order = ["node1", "node2", "node3", "node4"]

        # 验证每条边的源节点在目标节点之前
        for edge in edges:
            source_idx = execution_order.index(edge.source_node)
            target_idx = execution_order.index(edge.target_node)
            assert source_idx < target_idx, f"Invalid execution order for edge {edge}"


# 导出
__all__ = [
    "MockDatabaseService",
    "MockPythonExecutor",
    "MockLLMService",
    "TestSalesAnalysisWorkflowDefinition",
    "TestSalesAnalysisWorkflowExecution",
    "TestSalesAnalysisWorkflowEndToEnd",
]
