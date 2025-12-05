"""NodeDefinition 扩展测试 - YAML 解析、嵌套支持、DAG 验证

TDD Red Phase: 先编写失败测试用例，再实现功能

测试覆盖：
1. YAML 解析器测试
2. 元数据 dataclass 测试
3. 嵌套/组合节点测试
4. 父子 DAG 解析测试
5. 输入输出验证测试
6. 错误处理测试
"""

from pathlib import Path

import pytest

# 导入待测试模块（TDD Red 阶段可能不存在）
from src.domain.agents.node_definition import (
    NodeDefinition,
    NodeType,
)

# ============================================================
# 测试 1: YAML 解析器
# ============================================================


class TestNodeDefinitionYamlParser:
    """YAML 解析器测试"""

    def test_parse_yaml_string_should_return_node_definition(self):
        """测试：解析 YAML 字符串应返回 NodeDefinition"""
        yaml_content = """
name: test_node
kind: node
version: "1.0.0"
executor_type: python
description: 测试节点
code: |
    result = input_data.get('value', 0) * 2
    output = {'result': result}
"""
        node = NodeDefinition.from_yaml(yaml_content)

        assert node is not None
        assert node.name == "test_node"
        assert node.node_type == NodeType.PYTHON
        assert node.description == "测试节点"
        assert "result = input_data" in node.code

    def test_parse_yaml_file_should_load_node_definition(self):
        """测试：解析 YAML 文件应加载 NodeDefinition"""
        # 使用已存在的示例文件
        yaml_path = Path("definitions/nodes/llm.yaml")
        if yaml_path.exists():
            node = NodeDefinition.from_yaml_file(yaml_path)
            assert node is not None
            assert node.name is not None
            assert node.node_type is not None

    def test_parse_yaml_with_parameters_should_populate_input_schema(self):
        """测试：解析带参数的 YAML 应填充 input_schema"""
        yaml_content = """
name: param_node
kind: node
version: "1.0.0"
executor_type: python
parameters:
  - name: input_value
    type: number
    required: true
    description: 输入值
  - name: multiplier
    type: number
    default: 2
"""
        node = NodeDefinition.from_yaml(yaml_content)

        assert node.input_schema is not None
        assert "input_value" in node.input_schema
        assert "multiplier" in node.input_schema

    def test_parse_yaml_with_returns_should_populate_output_schema(self):
        """测试：解析带返回值的 YAML 应填充 output_schema"""
        yaml_content = """
name: return_node
kind: node
version: "1.0.0"
executor_type: python
returns:
  type: object
  properties:
    result:
      type: number
      description: 计算结果
    status:
      type: string
"""
        node = NodeDefinition.from_yaml(yaml_content)

        assert node.output_schema is not None
        assert "result" in node.output_schema
        assert "status" in node.output_schema

    def test_parse_invalid_yaml_should_raise_error(self):
        """测试：解析无效 YAML 应抛出错误"""
        invalid_yaml = """
name: [invalid
  - broken yaml
"""
        with pytest.raises(ValueError, match="YAML"):
            NodeDefinition.from_yaml(invalid_yaml)

    def test_parse_yaml_missing_required_fields_should_raise_error(self):
        """测试：缺少必填字段应抛出错误"""
        yaml_content = """
description: 缺少 name 和 executor_type
"""
        with pytest.raises(ValueError, match="required"):
            NodeDefinition.from_yaml(yaml_content)


# ============================================================
# 测试 2: 元数据 Dataclass
# ============================================================


class TestNodeDefinitionMetadata:
    """元数据 dataclass 测试"""

    def test_metadata_from_yaml_should_include_author(self):
        """测试：从 YAML 解析应包含 author"""
        yaml_content = """
name: meta_node
kind: node
version: "1.0.0"
executor_type: python
author: test_author
"""
        node = NodeDefinition.from_yaml(yaml_content)

        # author 存储在 config 中
        assert node.config.get("author") == "test_author"

    def test_metadata_from_yaml_should_include_tags(self):
        """测试：从 YAML 解析应包含 tags"""
        yaml_content = """
name: tagged_node
kind: node
version: "1.0.0"
executor_type: python
tags:
  - data
  - processing
"""
        node = NodeDefinition.from_yaml(yaml_content)

        # 检查 tags 存储位置
        tags = node.config.get("tags", [])
        assert "data" in tags or "processing" in tags

    def test_metadata_from_yaml_should_include_category(self):
        """测试：从 YAML 解析应包含 category"""
        yaml_content = """
name: categorized_node
kind: node
version: "1.0.0"
executor_type: llm
category: analysis
"""
        node = NodeDefinition.from_yaml(yaml_content)

        assert node.config.get("category") == "analysis"

    def test_metadata_version_should_be_preserved(self):
        """测试：版本号应被保留"""
        yaml_content = """
name: versioned_node
kind: node
version: "2.1.0"
executor_type: python
"""
        node = NodeDefinition.from_yaml(yaml_content)

        assert node.config.get("version") == "2.1.0"


# ============================================================
# 测试 3: 嵌套/组合节点
# ============================================================


class TestNodeDefinitionNested:
    """嵌套/组合节点测试"""

    def test_parse_nested_children_should_create_child_nodes(self):
        """测试：解析嵌套子节点应创建子节点"""
        yaml_content = """
name: parent_node
kind: node
version: "1.0.0"
executor_type: parallel
nested:
  parallel: true
  children:
    - name: child_1
      executor_type: python
    - name: child_2
      executor_type: llm
"""
        node = NodeDefinition.from_yaml(yaml_content)

        assert len(node.children) == 2
        assert node.children[0].name == "child_1"
        assert node.children[1].name == "child_2"

    def test_nested_children_should_have_parent_reference(self):
        """测试：嵌套子节点应有父节点引用"""
        yaml_content = """
name: parent_node
kind: node
version: "1.0.0"
executor_type: parallel
nested:
  children:
    - name: child_node
      executor_type: python
"""
        node = NodeDefinition.from_yaml(yaml_content)

        assert len(node.children) == 1
        child = node.children[0]
        assert child.parent_id == node.id

    def test_nested_parallel_flag_should_be_preserved(self):
        """测试：嵌套 parallel 标志应被保留"""
        yaml_content = """
name: parallel_parent
kind: node
version: "1.0.0"
executor_type: parallel
nested:
  parallel: true
  children:
    - name: task_1
      executor_type: python
"""
        node = NodeDefinition.from_yaml(yaml_content)

        # parallel 标志应存储在 config 中
        assert node.config.get("nested_parallel") is True

    def test_deeply_nested_should_respect_max_depth(self):
        """测试：深度嵌套应遵守最大深度限制"""
        # 创建超过最大深度的嵌套结构
        yaml_content = """
name: deep_parent
kind: node
version: "1.0.0"
executor_type: parallel
nested:
  children:
    - name: level_1
      executor_type: parallel
      nested:
        children:
          - name: level_2
            executor_type: parallel
            nested:
              children:
                - name: level_3
                  executor_type: parallel
                  nested:
                    children:
                      - name: level_4
                        executor_type: parallel
                        nested:
                          children:
                            - name: level_5
                              executor_type: parallel
                              nested:
                                children:
                                  - name: level_6_too_deep
                                    executor_type: python
"""
        with pytest.raises(ValueError, match="depth|exceeded"):
            NodeDefinition.from_yaml(yaml_content)


# ============================================================
# 测试 4: 父子 DAG 解析
# ============================================================


class TestNodeDefinitionDAG:
    """父子 DAG 解析测试"""

    def test_get_all_descendants_should_return_all_children(self):
        """测试：get_all_descendants 应返回所有后代"""
        yaml_content = """
name: root
kind: node
version: "1.0.0"
executor_type: parallel
nested:
  children:
    - name: child_1
      executor_type: parallel
      nested:
        children:
          - name: grandchild_1
            executor_type: python
    - name: child_2
      executor_type: python
"""
        node = NodeDefinition.from_yaml(yaml_content)

        descendants = node.get_all_descendants()
        names = [d.name for d in descendants]

        assert "child_1" in names
        assert "child_2" in names
        assert "grandchild_1" in names
        assert len(descendants) == 3

    def test_build_dag_should_create_execution_order(self):
        """测试：构建 DAG 应创建执行顺序"""
        yaml_content = """
name: dag_root
kind: node
version: "1.0.0"
executor_type: parallel
nested:
  children:
    - name: step_1
      executor_type: python
    - name: step_2
      executor_type: python
      depends_on:
        - step_1
"""
        node = NodeDefinition.from_yaml(yaml_content)

        # 获取执行顺序
        execution_order = node.get_execution_order()

        # step_1 应在 step_2 之前
        step_1_idx = next(i for i, n in enumerate(execution_order) if n.name == "step_1")
        step_2_idx = next(i for i, n in enumerate(execution_order) if n.name == "step_2")
        assert step_1_idx < step_2_idx

    def test_find_node_by_name_should_search_descendants(self):
        """测试：按名称查找节点应搜索后代"""
        yaml_content = """
name: search_root
kind: node
version: "1.0.0"
executor_type: parallel
nested:
  children:
    - name: target_node
      executor_type: python
"""
        node = NodeDefinition.from_yaml(yaml_content)

        found = node.find_node_by_name("target_node")
        assert found is not None
        assert found.name == "target_node"

    def test_find_node_by_name_not_found_should_return_none(self):
        """测试：查找不存在的节点应返回 None"""
        yaml_content = """
name: search_root
kind: node
version: "1.0.0"
executor_type: python
"""
        node = NodeDefinition.from_yaml(yaml_content)

        found = node.find_node_by_name("nonexistent")
        assert found is None


# ============================================================
# 测试 5: 输入输出验证
# ============================================================


class TestNodeDefinitionInputOutputValidation:
    """输入输出验证测试"""

    def test_validate_input_with_valid_data_should_pass(self):
        """测试：有效输入数据应通过验证"""
        yaml_content = """
name: validated_node
kind: node
version: "1.0.0"
executor_type: python
parameters:
  - name: count
    type: integer
    required: true
    constraints:
      min: 1
      max: 100
"""
        node = NodeDefinition.from_yaml(yaml_content)

        # 有效输入
        errors = node.validate_input({"count": 50})
        assert len(errors) == 0

    def test_validate_input_missing_required_should_fail(self):
        """测试：缺少必填参数应失败"""
        yaml_content = """
name: required_node
kind: node
version: "1.0.0"
executor_type: python
parameters:
  - name: required_param
    type: string
    required: true
"""
        node = NodeDefinition.from_yaml(yaml_content)

        # 缺少必填参数
        errors = node.validate_input({})
        assert len(errors) > 0
        assert any("required" in e.lower() for e in errors)

    def test_validate_input_type_mismatch_should_fail(self):
        """测试：类型不匹配应失败"""
        yaml_content = """
name: typed_node
kind: node
version: "1.0.0"
executor_type: python
parameters:
  - name: number_param
    type: number
    required: true
"""
        node = NodeDefinition.from_yaml(yaml_content)

        # 类型不匹配
        errors = node.validate_input({"number_param": "not_a_number"})
        assert len(errors) > 0
        assert any("type" in e.lower() for e in errors)

    def test_validate_input_constraint_violation_should_fail(self):
        """测试：违反约束应失败"""
        yaml_content = """
name: constrained_node
kind: node
version: "1.0.0"
executor_type: python
parameters:
  - name: value
    type: number
    constraints:
      min: 0
      max: 10
"""
        node = NodeDefinition.from_yaml(yaml_content)

        # 违反约束
        errors = node.validate_input({"value": 100})
        assert len(errors) > 0
        assert any("constraint" in e.lower() or "max" in e.lower() for e in errors)

    def test_validate_output_with_valid_data_should_pass(self):
        """测试：有效输出数据应通过验证"""
        yaml_content = """
name: output_node
kind: node
version: "1.0.0"
executor_type: python
returns:
  type: object
  properties:
    result:
      type: number
"""
        node = NodeDefinition.from_yaml(yaml_content)

        errors = node.validate_output({"result": 42})
        assert len(errors) == 0


# ============================================================
# 测试 6: 错误处理
# ============================================================


class TestNodeDefinitionErrorHandling:
    """错误处理测试"""

    def test_parse_yaml_with_error_strategy_should_preserve_config(self):
        """测试：解析带错误策略的 YAML 应保留配置"""
        yaml_content = """
name: error_handled_node
kind: node
version: "1.0.0"
executor_type: python
error_strategy:
  retry:
    max_attempts: 3
    delay_seconds: 1
  on_failure: skip
"""
        node = NodeDefinition.from_yaml(yaml_content)

        error_strategy = node.config.get("error_strategy", {})
        assert error_strategy.get("on_failure") == "skip"
        assert error_strategy.get("retry", {}).get("max_attempts") == 3

    def test_parse_yaml_with_dynamic_code_should_preserve_code(self):
        """测试：解析带动态代码的 YAML 应保留代码"""
        yaml_content = """
name: dynamic_node
kind: node
version: "1.0.0"
executor_type: python
dynamic_code:
  pre_execute: |
    data = prepare_data(input_data)
  transform: |
    result = transform_data(data)
  post_execute: |
    cleanup()
"""
        node = NodeDefinition.from_yaml(yaml_content)

        dynamic_code = node.config.get("dynamic_code", {})
        assert "pre_execute" in dynamic_code
        assert "transform" in dynamic_code
        assert "post_execute" in dynamic_code

    def test_to_yaml_should_serialize_correctly(self):
        """测试：to_yaml 应正确序列化"""
        node = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="serialize_test",
            code="output = {'result': 1}",
            description="测试序列化",
        )

        yaml_str = node.to_yaml()

        assert "serialize_test" in yaml_str
        assert "python" in yaml_str.lower()

    def test_round_trip_yaml_should_preserve_data(self):
        """测试：YAML 往返应保留数据"""
        original_yaml = """
name: round_trip_node
kind: node
version: "1.0.0"
executor_type: llm
description: 往返测试
prompt: "请分析数据"
"""
        node = NodeDefinition.from_yaml(original_yaml)
        yaml_str = node.to_yaml()
        node2 = NodeDefinition.from_yaml(yaml_str)

        assert node2.name == node.name
        assert node2.node_type == node.node_type
        assert node2.description == node.description


# ============================================================
# 测试 7: 与现有 YAML 文件集成
# ============================================================


class TestNodeDefinitionIntegration:
    """与现有 YAML 文件集成测试"""

    def test_load_existing_llm_yaml(self):
        """测试：加载现有 llm.yaml"""
        yaml_path = Path("definitions/nodes/llm.yaml")
        if yaml_path.exists():
            node = NodeDefinition.from_yaml_file(yaml_path)
            assert node is not None
            assert node.node_type == NodeType.LLM

    def test_load_existing_data_collection_yaml(self):
        """测试：加载现有 data_collection.yaml"""
        yaml_path = Path("definitions/nodes/data_collection.yaml")
        if yaml_path.exists():
            node = NodeDefinition.from_yaml_file(yaml_path)
            assert node is not None
            assert node.node_type == NodeType.DATABASE

    def test_load_existing_parallel_pipeline_yaml(self):
        """测试：加载现有 parallel_data_pipeline.yaml"""
        yaml_path = Path("definitions/nodes/parallel_data_pipeline.yaml")
        if yaml_path.exists():
            node = NodeDefinition.from_yaml_file(yaml_path)
            assert node is not None
            assert node.node_type == NodeType.PARALLEL
            # 应有子节点
            assert len(node.children) > 0

    def test_load_all_yaml_files_in_directory(self):
        """测试：加载目录下所有 YAML 文件"""
        nodes_dir = Path("definitions/nodes")
        if nodes_dir.exists():
            nodes = NodeDefinition.from_yaml_directory(nodes_dir)
            assert len(nodes) > 0
            # 所有节点都应有名称
            for node in nodes:
                assert node.name is not None


# ============================================================
# 测试 8: 边界条件
# ============================================================


class TestNodeDefinitionEdgeCases:
    """边界条件测试"""

    def test_empty_yaml_should_raise_error(self):
        """测试：空 YAML 应抛出错误"""
        with pytest.raises(ValueError):
            NodeDefinition.from_yaml("")

    def test_yaml_with_only_comments_should_raise_error(self):
        """测试：只有注释的 YAML 应抛出错误"""
        yaml_content = """
# 这是注释
# 没有实际内容
"""
        with pytest.raises(ValueError):
            NodeDefinition.from_yaml(yaml_content)

    def test_yaml_with_unknown_executor_type_should_use_generic(self):
        """测试：未知执行器类型应使用 GENERIC"""
        yaml_content = """
name: unknown_type_node
kind: node
version: "1.0.0"
executor_type: unknown_type
"""
        node = NodeDefinition.from_yaml(yaml_content)
        assert node.node_type == NodeType.GENERIC

    def test_yaml_with_special_characters_in_name_should_handle(self):
        """测试：名称中的特殊字符应处理"""
        yaml_content = """
name: node_with_中文_name
kind: node
version: "1.0.0"
executor_type: python
"""
        # 应该能解析，但可能有警告
        node = NodeDefinition.from_yaml(yaml_content)
        assert node.name == "node_with_中文_name"
