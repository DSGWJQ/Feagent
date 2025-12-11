"""GAP-H01: 嵌套节点模板测试

测试目标：验证系统支持多种场景的嵌套节点模板
- ETL Pipeline（顺序执行）
- ML Training Pipeline（混合执行）
- API Orchestration（并行+聚合）
- Report Generation（层级嵌套）

TDD 阶段：Red（测试先行）
"""

from pathlib import Path

import pytest
import yaml

from src.domain.services.self_describing_node import SelfDescribingNodeDefinition


class TestNestedTemplateETLPipeline:
    """ETL Pipeline 嵌套模板测试 - 顺序执行子节点"""

    def test_etl_pipeline_yaml_exists(self):
        """测试 ETL Pipeline 模板文件存在"""
        yaml_path = Path("definitions/nodes/etl_pipeline.yaml")
        assert yaml_path.exists(), "etl_pipeline.yaml 模板应该存在"

    def test_etl_pipeline_has_sequential_children(self):
        """测试 ETL Pipeline 包含顺序执行的子节点"""
        yaml_path = Path("definitions/nodes/etl_pipeline.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 验证嵌套结构
        assert "nested" in config, "ETL Pipeline 应该有嵌套结构"
        assert config["nested"].get("parallel") is False, "ETL Pipeline 应该顺序执行"

        # 验证必需的子节点
        children = config["nested"].get("children", [])
        child_names = [c["name"] for c in children]
        assert "extract" in child_names, "应该有 extract 子节点"
        assert "transform" in child_names, "应该有 transform 子节点"
        assert "load" in child_names, "应该有 load 子节点"

    def test_etl_pipeline_child_order_matters(self):
        """测试 ETL Pipeline 子节点顺序正确"""
        yaml_path = Path("definitions/nodes/etl_pipeline.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        children = config["nested"]["children"]
        child_names = [c["name"] for c in children]

        # 顺序应该是 extract -> transform -> load
        extract_idx = child_names.index("extract")
        transform_idx = child_names.index("transform")
        load_idx = child_names.index("load")

        assert (
            extract_idx < transform_idx < load_idx
        ), "ETL 子节点顺序应该是 extract -> transform -> load"

    def test_etl_pipeline_has_error_strategy(self):
        """测试 ETL Pipeline 有错误处理策略"""
        yaml_path = Path("definitions/nodes/etl_pipeline.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert "error_strategy" in config, "ETL Pipeline 应该有错误策略"
        assert config["error_strategy"].get("on_failure") in [
            "abort",
            "retry",
            "skip",
        ], "ETL Pipeline 失败策略应该是 abort/retry/skip"


class TestNestedTemplateMLPipeline:
    """ML Training Pipeline 嵌套模板测试 - 混合执行"""

    def test_ml_pipeline_yaml_exists(self):
        """测试 ML Pipeline 模板文件存在"""
        yaml_path = Path("definitions/nodes/ml_training_pipeline.yaml")
        assert yaml_path.exists(), "ml_training_pipeline.yaml 模板应该存在"

    def test_ml_pipeline_has_mixed_execution(self):
        """测试 ML Pipeline 支持混合执行（部分并行部分顺序）"""
        yaml_path = Path("definitions/nodes/ml_training_pipeline.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 验证嵌套结构
        assert "nested" in config, "ML Pipeline 应该有嵌套结构"

        children = config["nested"].get("children", [])
        child_names = [c["name"] for c in children]

        # 验证必需的子节点
        assert "data_preprocessing" in child_names, "应该有数据预处理子节点"
        assert "model_training" in child_names, "应该有模型训练子节点"
        assert "model_evaluation" in child_names, "应该有模型评估子节点"

    def test_ml_pipeline_has_llm_node(self):
        """测试 ML Pipeline 包含 LLM 类型节点（用于分析）"""
        yaml_path = Path("definitions/nodes/ml_training_pipeline.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        children = config["nested"]["children"]
        executor_types = [c.get("executor_type") for c in children]

        assert "llm" in executor_types, "ML Pipeline 应该包含 LLM 类型节点"


class TestNestedTemplateAPIOrchestration:
    """API Orchestration 嵌套模板测试 - 并行+聚合"""

    def test_api_orchestration_yaml_exists(self):
        """测试 API Orchestration 模板文件存在"""
        yaml_path = Path("definitions/nodes/api_orchestration.yaml")
        assert yaml_path.exists(), "api_orchestration.yaml 模板应该存在"

    def test_api_orchestration_parallel_calls(self):
        """测试 API Orchestration 支持并行调用"""
        yaml_path = Path("definitions/nodes/api_orchestration.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert "nested" in config, "API Orchestration 应该有嵌套结构"
        assert config["nested"].get("parallel") is True, "API Orchestration 应该并行执行"

    def test_api_orchestration_has_aggregation(self):
        """测试 API Orchestration 有输出聚合策略"""
        yaml_path = Path("definitions/nodes/api_orchestration.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 应该有聚合策略
        assert (
            "output_aggregation" in config or config["nested"].get("output_aggregation") is not None
        ), "API Orchestration 应该有输出聚合策略"


class TestNestedTemplateReportGeneration:
    """Report Generation 嵌套模板测试 - 层级嵌套"""

    def test_report_generation_yaml_exists(self):
        """测试 Report Generation 模板文件存在"""
        yaml_path = Path("definitions/nodes/report_generation.yaml")
        assert yaml_path.exists(), "report_generation.yaml 模板应该存在"

    def test_report_generation_multi_level_nesting(self):
        """测试 Report Generation 支持多层嵌套"""
        yaml_path = Path("definitions/nodes/report_generation.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert "nested" in config, "Report Generation 应该有嵌套结构"

        # 检查是否有子节点包含嵌套（二级嵌套）
        children = config["nested"].get("children", [])
        has_nested_child = any(c.get("nested") for c in children)

        assert has_nested_child, "Report Generation 应该支持多层嵌套"


class TestNestedTemplateValidation:
    """嵌套模板通用验证测试"""

    @pytest.fixture
    def all_nested_templates(self):
        """获取所有嵌套模板路径 - 这些模板必须存在"""
        return [
            "definitions/nodes/etl_pipeline.yaml",
            "definitions/nodes/ml_training_pipeline.yaml",
            "definitions/nodes/api_orchestration.yaml",
            "definitions/nodes/report_generation.yaml",
        ]

    def test_all_templates_must_exist(self, all_nested_templates):
        """测试所有嵌套模板文件必须存在（Red阶段关键断言）"""
        for path in all_nested_templates:
            yaml_path = Path(path)
            assert yaml_path.exists(), f"模板文件 {path} 必须存在"

    def test_all_templates_valid_yaml(self, all_nested_templates):
        """测试所有嵌套模板都是有效的 YAML"""
        for path in all_nested_templates:
            yaml_path = Path(path)
            assert yaml_path.exists(), f"模板文件 {path} 必须存在"
            with open(yaml_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            assert config is not None, f"{path} 应该是有效的 YAML"

    def test_all_templates_have_required_fields(self, all_nested_templates):
        """测试所有嵌套模板都有必需字段"""
        required_fields = ["name", "kind", "version", "executor_type"]

        for path in all_nested_templates:
            yaml_path = Path(path)
            assert yaml_path.exists(), f"模板文件 {path} 必须存在"
            with open(yaml_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            for field in required_fields:
                assert field in config, f"{path} 应该有 {field} 字段"

    def test_all_templates_can_be_parsed(self, all_nested_templates):
        """测试所有嵌套模板可以被解析为 SelfDescribingNodeDefinition"""
        for path in all_nested_templates:
            yaml_path = Path(path)
            assert yaml_path.exists(), f"模板文件 {path} 必须存在"
            with open(yaml_path, encoding="utf-8") as f:
                yaml_content = f.read()

            # 应该能成功解析
            node_def = SelfDescribingNodeDefinition.from_yaml(yaml_content)
            assert node_def is not None, f"{path} 应该能被解析"
            assert node_def.has_children, f"{path} 应该有子节点"

    def test_invalid_nested_config_should_fail(self):
        """测试无效的嵌套配置应该报错"""
        invalid_yaml = """
name: invalid_template
kind: node
version: "1.0.0"
executor_type: parallel
nested:
  parallel: true
  children: []  # 空子节点列表应该无效
"""
        with pytest.raises(ValueError):
            SelfDescribingNodeDefinition.from_yaml(invalid_yaml)

    def test_missing_children_in_nested_should_fail(self):
        """测试嵌套配置缺少 children 应该报错"""
        invalid_yaml = """
name: missing_children
kind: node
version: "1.0.0"
executor_type: parallel
nested:
  parallel: true
  # 缺少 children 字段
"""
        with pytest.raises((ValueError, KeyError)):
            node_def = SelfDescribingNodeDefinition.from_yaml(invalid_yaml)
            # 如果解析不报错，验证时应该报错
            if node_def:
                assert not node_def.has_children or len(node_def.children) == 0


class TestNestedTemplateCount:
    """嵌套模板数量测试"""

    def test_minimum_nested_templates_count(self):
        """测试至少有 5 个嵌套节点模板"""
        nodes_dir = Path("definitions/nodes")
        nested_count = 0

        for yaml_file in nodes_dir.glob("*.yaml"):
            with open(yaml_file, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            if config and "nested" in config and config["nested"].get("children"):
                nested_count += 1

        assert nested_count >= 5, f"应该至少有 5 个嵌套模板，当前有 {nested_count} 个"
