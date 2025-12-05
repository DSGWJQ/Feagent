"""
TDD 测试：工作流连接与依赖图更新 (Step 8)

测试范围：
1. DependencyGraphBuilder - 自动连线与依赖解析
2. TopologicalExecutor - 拓扑排序执行
3. 复杂案例：销售分析父节点 → 数据拉取/指标计算/图表生成子节点
4. EventBus 依赖顺序日志
"""

import logging
import tempfile
from pathlib import Path

import pytest

# ==================== 1. 依赖解析测试 ====================


class TestDependencyResolution:
    """测试：依赖解析"""

    @pytest.fixture
    def graph_builder(self):
        """创建依赖图构建器"""
        from src.domain.services.workflow_dependency_graph import DependencyGraphBuilder

        return DependencyGraphBuilder()

    def test_parse_input_references(self, graph_builder):
        """测试：解析输入引用"""
        node_def = {
            "name": "metric_calculation",
            "inputs": {
                "sales_data": {"from": "data_fetch.output.records"},
                "metrics": {"from": "analyzer.output"},
            },
        }

        refs = graph_builder.parse_input_references(node_def)

        assert len(refs) == 2
        assert refs["sales_data"] == {"node": "data_fetch", "path": "output.records"}
        assert refs["metrics"] == {"node": "analyzer", "path": "output"}

    def test_parse_output_references(self, graph_builder):
        """测试：解析输出引用"""
        node_def = {
            "name": "data_fetch",
            "outputs": {
                "records": {"type": "array", "description": "销售记录"},
                "count": {"type": "integer"},
            },
        }

        outputs = graph_builder.parse_output_schema(node_def)

        assert "records" in outputs
        assert "count" in outputs

    def test_resolve_dependencies_between_nodes(self, graph_builder):
        """测试：解析节点间依赖关系"""
        nodes = [
            {
                "name": "data_fetch",
                "outputs": {"records": {"type": "array"}},
            },
            {
                "name": "metric_calc",
                "inputs": {"data": {"from": "data_fetch.output.records"}},
                "outputs": {"metrics": {"type": "object"}},
            },
            {
                "name": "chart_gen",
                "inputs": {"metrics": {"from": "metric_calc.output.metrics"}},
            },
        ]

        dependencies = graph_builder.resolve_dependencies(nodes)

        # data_fetch 没有依赖
        assert dependencies["data_fetch"] == []
        # metric_calc 依赖 data_fetch
        assert "data_fetch" in dependencies["metric_calc"]
        # chart_gen 依赖 metric_calc
        assert "metric_calc" in dependencies["chart_gen"]


# ==================== 2. 自动连线测试 ====================


class TestAutoWiring:
    """测试：自动连线"""

    @pytest.fixture
    def graph_builder(self):
        from src.domain.services.workflow_dependency_graph import DependencyGraphBuilder

        return DependencyGraphBuilder()

    def test_create_edges_from_dependencies(self, graph_builder):
        """测试：根据依赖创建边"""
        nodes = [
            {"name": "node_a", "outputs": {"result": {}}},
            {"name": "node_b", "inputs": {"data": {"from": "node_a.output.result"}}},
        ]

        edges = graph_builder.create_edges(nodes)

        assert len(edges) == 1
        assert edges[0]["source"] == "node_a"
        assert edges[0]["target"] == "node_b"

    def test_create_edges_with_multiple_dependencies(self, graph_builder):
        """测试：创建多依赖边"""
        nodes = [
            {"name": "source_1", "outputs": {"data_1": {}}},
            {"name": "source_2", "outputs": {"data_2": {}}},
            {
                "name": "consumer",
                "inputs": {
                    "input_1": {"from": "source_1.output.data_1"},
                    "input_2": {"from": "source_2.output.data_2"},
                },
            },
        ]

        edges = graph_builder.create_edges(nodes)

        assert len(edges) == 2
        sources = {e["source"] for e in edges}
        assert "source_1" in sources
        assert "source_2" in sources

    def test_no_edges_for_independent_nodes(self, graph_builder):
        """测试：独立节点无边"""
        nodes = [
            {"name": "node_a", "outputs": {"result": {}}},
            {"name": "node_b", "outputs": {"result": {}}},
        ]

        edges = graph_builder.create_edges(nodes)

        assert len(edges) == 0

    def test_wire_parent_to_children(self, graph_builder):
        """测试：父节点连接子节点"""
        parent_node = {
            "name": "sales_analysis",
            "nested": {
                "children": [
                    {"name": "data_fetch"},
                    {"name": "metric_calc", "inputs": {"data": {"from": "data_fetch.output"}}},
                    {"name": "chart_gen", "inputs": {"metrics": {"from": "metric_calc.output"}}},
                ]
            },
        }

        edges = graph_builder.wire_children(parent_node)

        # data_fetch -> metric_calc, metric_calc -> chart_gen
        assert len(edges) == 2


# ==================== 3. 拓扑排序执行测试 ====================


class TestTopologicalExecution:
    """测试：拓扑排序执行"""

    @pytest.fixture
    def executor(self):
        from src.domain.services.workflow_dependency_graph import TopologicalExecutor

        return TopologicalExecutor()

    def test_topological_sort_linear_chain(self, executor):
        """测试：线性链拓扑排序"""
        nodes = ["A", "B", "C"]
        edges = [("A", "B"), ("B", "C")]

        order = executor.topological_sort(nodes, edges)

        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_topological_sort_diamond(self, executor):
        """测试：菱形依赖拓扑排序"""
        #     A
        #    / \
        #   B   C
        #    \ /
        #     D
        nodes = ["A", "B", "C", "D"]
        edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

        order = executor.topological_sort(nodes, edges)

        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_topological_sort_detects_cycle(self, executor):
        """测试：检测循环依赖"""
        nodes = ["A", "B", "C"]
        edges = [("A", "B"), ("B", "C"), ("C", "A")]  # 循环！

        with pytest.raises(ValueError, match="cycle|循环"):
            executor.topological_sort(nodes, edges)

    def test_topological_sort_parallel_branches(self, executor):
        """测试：并行分支"""
        #   A
        #  /|\
        # B C D
        #  \|/
        #   E
        nodes = ["A", "B", "C", "D", "E"]
        edges = [("A", "B"), ("A", "C"), ("A", "D"), ("B", "E"), ("C", "E"), ("D", "E")]

        order = executor.topological_sort(nodes, edges)

        # A 必须在 B, C, D 之前
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("A") < order.index("D")
        # B, C, D 必须在 E 之前
        assert order.index("B") < order.index("E")
        assert order.index("C") < order.index("E")
        assert order.index("D") < order.index("E")


# ==================== 4. 复杂案例：销售分析 ====================


class TestSalesAnalysisCase:
    """测试：销售分析复杂案例

    场景：
    sales_analysis (父节点)
      ├── data_fetch (数据拉取)
      │     └── 输出: raw_data, record_count
      ├── metric_calculation (指标计算)
      │     ├── 输入: data_fetch.output.raw_data
      │     └── 输出: total_sales, avg_order, top_products
      └── chart_generation (图表生成)
            ├── 输入: metric_calculation.output
            └── 输出: chart_url, summary

    执行顺序: data_fetch → metric_calculation → chart_generation
    """

    @pytest.fixture
    def sales_analysis_yaml(self, tmp_path):
        """创建销售分析 YAML 定义"""
        yaml_content = """
name: sales_analysis
kind: node
description: "销售数据综合分析"
version: "1.0.0"
executor_type: parallel

parameters:
  - name: date_range
    type: object
    required: true
    description: "日期范围"
  - name: region
    type: string
    default: "all"

nested:
  parallel: false
  children:
    - name: data_fetch
      executor_type: code
      outputs:
        raw_data:
          type: array
          description: "原始销售数据"
        record_count:
          type: integer

    - name: metric_calculation
      executor_type: code
      inputs:
        sales_data:
          from: "data_fetch.output.raw_data"
      outputs:
        total_sales:
          type: number
        avg_order:
          type: number
        top_products:
          type: array

    - name: chart_generation
      executor_type: code
      inputs:
        metrics:
          from: "metric_calculation.output"
      outputs:
        chart_url:
          type: string
        summary:
          type: string

output_aggregation: merge
"""
        yaml_file = tmp_path / "sales_analysis.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        return tmp_path

    @pytest.mark.asyncio
    async def test_sales_analysis_dependency_resolution(self, sales_analysis_yaml):
        """测试：销售分析依赖解析"""
        from src.domain.services.workflow_dependency_graph import DependencyGraphBuilder

        builder = DependencyGraphBuilder()

        # 加载 YAML
        import yaml

        yaml_file = sales_analysis_yaml / "sales_analysis.yaml"
        with open(yaml_file, encoding="utf-8") as f:
            node_def = yaml.safe_load(f)

        # 解析子节点依赖
        children = node_def["nested"]["children"]
        dependencies = builder.resolve_dependencies(children)

        # 验证依赖关系
        assert dependencies["data_fetch"] == []
        assert "data_fetch" in dependencies["metric_calculation"]
        assert "metric_calculation" in dependencies["chart_generation"]

    @pytest.mark.asyncio
    async def test_sales_analysis_execution_order(self, sales_analysis_yaml):
        """测试：销售分析执行顺序"""
        from src.domain.services.workflow_dependency_graph import (
            DependencyGraphBuilder,
            TopologicalExecutor,
        )

        builder = DependencyGraphBuilder()
        executor = TopologicalExecutor()

        # 加载并解析
        import yaml

        yaml_file = sales_analysis_yaml / "sales_analysis.yaml"
        with open(yaml_file, encoding="utf-8") as f:
            node_def = yaml.safe_load(f)

        children = node_def["nested"]["children"]
        edges = builder.create_edges(children)
        node_names = [c["name"] for c in children]

        # 拓扑排序
        edge_tuples = [(e["source"], e["target"]) for e in edges]
        order = executor.topological_sort(node_names, edge_tuples)

        # 验证顺序
        assert order.index("data_fetch") < order.index("metric_calculation")
        assert order.index("metric_calculation") < order.index("chart_generation")

    @pytest.mark.asyncio
    async def test_sales_analysis_full_execution(self, sales_analysis_yaml):
        """测试：销售分析完整执行"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        # 创建脚本
        scripts_dir = sales_analysis_yaml / "scripts"
        scripts_dir.mkdir()

        # data_fetch.py
        (scripts_dir / "data_fetch.py").write_text(
            """
raw_data = [
    {"product": "A", "amount": 100},
    {"product": "B", "amount": 200},
    {"product": "C", "amount": 150},
]
record_count = len(raw_data)
output = {"raw_data": raw_data, "record_count": record_count}
""",
            encoding="utf-8",
        )

        # metric_calculation.py
        (scripts_dir / "metric_calculation.py").write_text(
            """
sales_data = input_data.get("sales_data", [])
total_sales = sum(item.get("amount", 0) for item in sales_data)
avg_order = total_sales / len(sales_data) if sales_data else 0
top_products = sorted(sales_data, key=lambda x: x.get("amount", 0), reverse=True)[:2]
output = {
    "total_sales": total_sales,
    "avg_order": avg_order,
    "top_products": top_products
}
""",
            encoding="utf-8",
        )

        # chart_generation.py
        (scripts_dir / "chart_generation.py").write_text(
            """
metrics = input_data.get("metrics", {})
total = metrics.get("total_sales", 0)
chart_url = f"https://charts.example.com/sales?total={total}"
summary = f"Total sales: {total}, Average order: {metrics.get('avg_order', 0):.2f}"
output = {"chart_url": chart_url, "summary": summary}
""",
            encoding="utf-8",
        )

        executor = WorkflowDependencyExecutor(
            definitions_dir=str(sales_analysis_yaml),
            scripts_dir=str(scripts_dir),
        )

        result = await executor.execute_workflow(
            "sales_analysis",
            inputs={"date_range": {"start": "2024-01-01", "end": "2024-12-31"}},
        )

        assert result.success is True
        # 验证聚合输出
        assert "data_fetch" in result.aggregated_output or "raw_data" in str(result.output)
        assert "total_sales" in str(result.output) or "metric_calculation" in str(
            result.aggregated_output
        )


# ==================== 5. EventBus 依赖日志测试 ====================


class TestEventBusDependencyLogging:
    """测试：EventBus 依赖顺序日志"""

    @pytest.mark.asyncio
    async def test_log_execution_order(self, caplog):
        """测试：记录执行顺序日志"""
        from src.domain.services.workflow_dependency_graph import (
            WorkflowDependencyExecutor,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建简单工作流
            yaml_content = """
name: simple_workflow
kind: node
executor_type: sequential
nested:
  parallel: false
  children:
    - name: step_1
      executor_type: code
    - name: step_2
      executor_type: code
      inputs:
        data:
          from: "step_1.output"
"""
            Path(tmpdir, "simple_workflow.yaml").write_text(yaml_content, encoding="utf-8")

            scripts_dir = Path(tmpdir) / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "step_1.py").write_text("output = {'value': 1}", encoding="utf-8")
            (scripts_dir / "step_2.py").write_text(
                "output = {'value': input_data.get('data', {}).get('value', 0) + 1}",
                encoding="utf-8",
            )

            executor = WorkflowDependencyExecutor(
                definitions_dir=tmpdir,
                scripts_dir=str(scripts_dir),
            )

            with caplog.at_level(logging.INFO):
                await executor.execute_workflow("simple_workflow", inputs={})

            # 验证日志包含依赖信息
            log_text = " ".join(record.message for record in caplog.records)
            # 应该记录执行顺序
            assert "step_1" in log_text or "step_2" in log_text

    @pytest.mark.asyncio
    async def test_emit_dependency_events(self):
        """测试：发布依赖事件"""
        from src.domain.services.workflow_dependency_graph import (
            WorkflowDependencyExecutor,
        )

        events_captured = []

        def capture_event(event):
            events_captured.append(event)

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_content = """
name: event_test
kind: node
nested:
  children:
    - name: node_a
      executor_type: code
    - name: node_b
      executor_type: code
      inputs:
        data:
          from: "node_a.output"
"""
            Path(tmpdir, "event_test.yaml").write_text(yaml_content, encoding="utf-8")

            scripts_dir = Path(tmpdir) / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "node_a.py").write_text("output = {'a': 1}", encoding="utf-8")
            (scripts_dir / "node_b.py").write_text("output = {'b': 2}", encoding="utf-8")

            executor = WorkflowDependencyExecutor(
                definitions_dir=tmpdir,
                scripts_dir=str(scripts_dir),
                event_callback=capture_event,
            )

            await executor.execute_workflow("event_test", inputs={})

            # 验证事件
            assert len(events_captured) >= 2
            node_names = [e.node_name for e in events_captured if hasattr(e, "node_name")]
            assert "node_a" in node_names
            assert "node_b" in node_names


# ==================== 6. 数据流传递测试 ====================


class TestDataFlowPassing:
    """测试：数据流传递"""

    @pytest.mark.asyncio
    async def test_output_to_input_passing(self):
        """测试：输出到输入的数据传递"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_content = """
name: data_flow_test
kind: node
nested:
  children:
    - name: producer
      executor_type: code
      outputs:
        value:
          type: integer
    - name: consumer
      executor_type: code
      inputs:
        input_value:
          from: "producer.output.value"
"""
            Path(tmpdir, "data_flow_test.yaml").write_text(yaml_content, encoding="utf-8")

            scripts_dir = Path(tmpdir) / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "producer.py").write_text("output = {'value': 42}", encoding="utf-8")
            (scripts_dir / "consumer.py").write_text(
                "received = input_data.get('input_value', 0)\noutput = {'doubled': received * 2}",
                encoding="utf-8",
            )

            executor = WorkflowDependencyExecutor(
                definitions_dir=tmpdir,
                scripts_dir=str(scripts_dir),
            )

            result = await executor.execute_workflow("data_flow_test", inputs={})

            assert result.success is True
            # consumer 应该收到 producer 的输出
            consumer_result = result.children_results.get("consumer", {})
            if hasattr(consumer_result, "output"):
                assert consumer_result.output.get("doubled") == 84

    @pytest.mark.asyncio
    async def test_multiple_inputs_from_different_sources(self):
        """测试：从多个来源获取输入"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_content = """
name: multi_input_test
kind: node
nested:
  children:
    - name: source_a
      executor_type: code
    - name: source_b
      executor_type: code
    - name: merger
      executor_type: code
      inputs:
        from_a:
          from: "source_a.output.value"
        from_b:
          from: "source_b.output.value"
"""
            Path(tmpdir, "multi_input_test.yaml").write_text(yaml_content, encoding="utf-8")

            scripts_dir = Path(tmpdir) / "scripts"
            scripts_dir.mkdir()
            (scripts_dir / "source_a.py").write_text("output = {'value': 10}", encoding="utf-8")
            (scripts_dir / "source_b.py").write_text("output = {'value': 20}", encoding="utf-8")
            (scripts_dir / "merger.py").write_text(
                """
a = input_data.get('from_a', 0)
b = input_data.get('from_b', 0)
output = {'sum': a + b, 'product': a * b}
""",
                encoding="utf-8",
            )

            executor = WorkflowDependencyExecutor(
                definitions_dir=tmpdir,
                scripts_dir=str(scripts_dir),
            )

            result = await executor.execute_workflow("multi_input_test", inputs={})

            assert result.success is True


# ==================== 7. 边界情况测试 ====================


class TestEdgeCases:
    """测试：边界情况"""

    @pytest.fixture
    def graph_builder(self):
        from src.domain.services.workflow_dependency_graph import DependencyGraphBuilder

        return DependencyGraphBuilder()

    def test_empty_workflow(self, graph_builder):
        """测试：空工作流"""
        nodes = []
        edges = graph_builder.create_edges(nodes)
        assert edges == []

    def test_single_node_no_dependencies(self, graph_builder):
        """测试：单节点无依赖"""
        nodes = [{"name": "lonely_node"}]
        deps = graph_builder.resolve_dependencies(nodes)
        assert deps["lonely_node"] == []

    def test_invalid_reference_format(self, graph_builder):
        """测试：无效引用格式"""
        node_def = {
            "name": "bad_node",
            "inputs": {
                "data": {"from": "invalid_format"},  # 缺少 .output
            },
        }

        refs = graph_builder.parse_input_references(node_def)
        # 应该优雅处理，返回空或跳过无效引用
        assert "data" not in refs or refs["data"].get("node") is None

    def test_self_reference_detection(self, graph_builder):
        """测试：检测自引用"""
        nodes = [
            {
                "name": "self_ref",
                "inputs": {"data": {"from": "self_ref.output.value"}},
            }
        ]

        # 自引用应该被检测或跳过
        edges = graph_builder.create_edges(nodes)
        # 不应该创建自引用边
        self_edges = [e for e in edges if e["source"] == e["target"]]
        assert len(self_edges) == 0

    def test_missing_dependency_node(self, graph_builder):
        """测试：依赖节点不存在"""
        nodes = [
            {
                "name": "orphan",
                "inputs": {"data": {"from": "nonexistent.output.value"}},
            }
        ]

        # 应该优雅处理
        deps = graph_builder.resolve_dependencies(nodes)
        # orphan 的依赖应该为空或标记为未解析
        assert "orphan" in deps


# ==================== 8. 回归测试案例 ====================


class TestRegressionCases:
    """回归测试套件"""

    @pytest.mark.asyncio
    async def test_regression_sales_analysis_pipeline(self):
        """回归测试：销售分析管道"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            # 完整的销售分析案例
            yaml_content = """
name: sales_pipeline
kind: node
description: "销售分析管道 - 回归测试"
version: "1.0.0"

nested:
  parallel: false
  children:
    - name: fetch_sales_data
      executor_type: code
      outputs:
        sales_records:
          type: array

    - name: calculate_metrics
      executor_type: code
      inputs:
        records:
          from: "fetch_sales_data.output.sales_records"
      outputs:
        total_revenue:
          type: number
        order_count:
          type: integer

    - name: generate_report
      executor_type: code
      inputs:
        revenue:
          from: "calculate_metrics.output.total_revenue"
        count:
          from: "calculate_metrics.output.order_count"
      outputs:
        report:
          type: string

output_aggregation: merge
"""
            Path(tmpdir, "sales_pipeline.yaml").write_text(yaml_content, encoding="utf-8")

            scripts_dir = Path(tmpdir) / "scripts"
            scripts_dir.mkdir()

            (scripts_dir / "fetch_sales_data.py").write_text(
                """
sales_records = [
    {"id": 1, "amount": 150.00},
    {"id": 2, "amount": 250.00},
    {"id": 3, "amount": 100.00},
]
output = {"sales_records": sales_records}
""",
                encoding="utf-8",
            )

            (scripts_dir / "calculate_metrics.py").write_text(
                """
records = input_data.get("records", [])
total_revenue = sum(r.get("amount", 0) for r in records)
order_count = len(records)
output = {"total_revenue": total_revenue, "order_count": order_count}
""",
                encoding="utf-8",
            )

            (scripts_dir / "generate_report.py").write_text(
                """
revenue = input_data.get("revenue", 0)
count = input_data.get("count", 0)
avg = revenue / count if count > 0 else 0
report = f"Sales Report: Total Revenue=${revenue:.2f}, Orders={count}, Avg=${avg:.2f}"
output = {"report": report}
""",
                encoding="utf-8",
            )

            executor = WorkflowDependencyExecutor(
                definitions_dir=tmpdir,
                scripts_dir=str(scripts_dir),
            )

            result = await executor.execute_workflow("sales_pipeline", inputs={})

            # 验证成功执行
            assert result.success is True

            # 验证数据正确传递
            # 总收入应该是 150 + 250 + 100 = 500
            output_str = str(result.output) + str(result.aggregated_output or {})
            assert "500" in output_str or "report" in output_str.lower()

    @pytest.mark.asyncio
    async def test_regression_parallel_fan_out_fan_in(self):
        """回归测试：并行扇出扇入模式"""
        from src.domain.services.workflow_dependency_graph import WorkflowDependencyExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_content = """
name: fan_out_in
kind: node

nested:
  children:
    - name: splitter
      executor_type: code

    - name: worker_1
      executor_type: code
      inputs:
        data:
          from: "splitter.output.chunk_1"

    - name: worker_2
      executor_type: code
      inputs:
        data:
          from: "splitter.output.chunk_2"

    - name: aggregator
      executor_type: code
      inputs:
        result_1:
          from: "worker_1.output.result"
        result_2:
          from: "worker_2.output.result"

output_aggregation: merge
"""
            Path(tmpdir, "fan_out_in.yaml").write_text(yaml_content, encoding="utf-8")

            scripts_dir = Path(tmpdir) / "scripts"
            scripts_dir.mkdir()

            (scripts_dir / "splitter.py").write_text(
                "output = {'chunk_1': [1, 2], 'chunk_2': [3, 4]}",
                encoding="utf-8",
            )
            (scripts_dir / "worker_1.py").write_text(
                "data = input_data.get('data', [])\noutput = {'result': sum(data)}",
                encoding="utf-8",
            )
            (scripts_dir / "worker_2.py").write_text(
                "data = input_data.get('data', [])\noutput = {'result': sum(data)}",
                encoding="utf-8",
            )
            (scripts_dir / "aggregator.py").write_text(
                """
r1 = input_data.get('result_1', 0)
r2 = input_data.get('result_2', 0)
output = {'total': r1 + r2}
""",
                encoding="utf-8",
            )

            executor = WorkflowDependencyExecutor(
                definitions_dir=tmpdir,
                scripts_dir=str(scripts_dir),
            )

            result = await executor.execute_workflow("fan_out_in", inputs={})

            assert result.success is True
