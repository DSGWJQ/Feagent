"""通用节点 YAML 规范校验测试 - TDD Red Phase

测试目标：
- 验证 YAML 节点定义符合通用规范
- 校验必填字段、类型约束、枚举值
- 验证错误策略、嵌套声明、动态代码段

TDD 流程：
1. Red: 先写失败的测试（本文件）
2. Green: 实现 NodeYamlValidator 让测试通过
3. Refactor: 优化代码结构
"""

from pathlib import Path

import pytest

# 这些导入会在 Green 阶段实现后才能通过
from src.domain.services.node_yaml_validator import (
    NodeYamlValidator,
)


class TestNodeYamlSchemaBasicFields:
    """测试基础字段校验"""

    def test_valid_minimal_node_should_pass_validation(self):
        """测试：最小有效节点定义应该通过校验"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
parameters:
  - name: input
    type: string
    required: true
returns:
  type: object
  properties:
    result:
      type: string
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_missing_name_should_fail_validation(self):
        """测试：缺少 name 字段应该校验失败"""
        yaml_content = """
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("name" in e.field for e in result.errors)

    def test_missing_kind_should_fail_validation(self):
        """测试：缺少 kind 字段应该校验失败"""
        yaml_content = """
name: test_node
description: 测试节点
version: "1.0.0"
executor_type: python
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("kind" in e.field for e in result.errors)

    def test_invalid_kind_value_should_fail_validation(self):
        """测试：无效的 kind 值应该校验失败"""
        yaml_content = """
name: test_node
kind: invalid_kind
description: 测试节点
version: "1.0.0"
executor_type: python
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("kind" in e.field for e in result.errors)

    def test_missing_version_should_fail_validation(self):
        """测试：缺少 version 字段应该校验失败"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
executor_type: python
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("version" in e.field for e in result.errors)

    def test_invalid_version_format_should_fail_validation(self):
        """测试：无效的版本格式应该校验失败"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "invalid"
executor_type: python
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("version" in e.field for e in result.errors)


class TestNodeYamlSchemaExecutorType:
    """测试执行类型校验"""

    def test_valid_executor_types_should_pass(self):
        """测试：有效的执行类型应该通过"""
        valid_types = ["python", "llm", "http", "database", "container", "condition", "loop"]
        validator = NodeYamlValidator()

        for exec_type in valid_types:
            yaml_content = f"""
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: {exec_type}
"""
            result = validator.validate_yaml_string(yaml_content)
            assert result.is_valid is True, f"executor_type '{exec_type}' should be valid"

    def test_invalid_executor_type_should_fail(self):
        """测试：无效的执行类型应该失败"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: unknown_type
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("executor_type" in e.field for e in result.errors)


class TestNodeYamlSchemaParameters:
    """测试参数 Schema 校验"""

    def test_parameter_with_valid_type_should_pass(self):
        """测试：参数类型有效应该通过"""
        valid_types = ["string", "number", "integer", "boolean", "array", "object"]
        validator = NodeYamlValidator()

        for param_type in valid_types:
            yaml_content = f"""
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
parameters:
  - name: test_param
    type: {param_type}
    required: true
"""
            result = validator.validate_yaml_string(yaml_content)
            assert result.is_valid is True, f"param type '{param_type}' should be valid"

    def test_parameter_without_name_should_fail(self):
        """测试：参数缺少 name 应该失败"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
parameters:
  - type: string
    required: true
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("parameters" in e.field for e in result.errors)

    def test_parameter_without_type_should_fail(self):
        """测试：参数缺少 type 应该失败"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
parameters:
  - name: test_param
    required: true
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("parameters" in e.field for e in result.errors)

    def test_parameter_with_constraints_should_validate(self):
        """测试：参数约束应该被验证"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
parameters:
  - name: temperature
    type: number
    required: false
    default: 0.7
    constraints:
      min: 0.0
      max: 2.0
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is True

    def test_parameter_default_violates_constraints_should_fail(self):
        """测试：默认值违反约束应该失败"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
parameters:
  - name: temperature
    type: number
    required: false
    default: 5.0
    constraints:
      min: 0.0
      max: 2.0
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("constraints" in e.message.lower() for e in result.errors)


class TestNodeYamlSchemaErrorStrategy:
    """测试错误策略校验"""

    def test_valid_error_strategy_should_pass(self):
        """测试：有效的错误策略应该通过"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
error_strategy:
  retry:
    max_attempts: 3
    delay_seconds: 1.0
    backoff_multiplier: 2.0
  on_failure: skip
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is True

    def test_invalid_on_failure_action_should_fail(self):
        """测试：无效的失败处理动作应该失败"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
error_strategy:
  on_failure: invalid_action
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("on_failure" in e.field for e in result.errors)

    def test_valid_on_failure_actions_should_pass(self):
        """测试：有效的失败处理动作应该通过"""
        valid_actions = ["retry", "skip", "abort", "replan", "fallback"]
        validator = NodeYamlValidator()

        for action in valid_actions:
            yaml_content = f"""
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
error_strategy:
  on_failure: {action}
"""
            result = validator.validate_yaml_string(yaml_content)
            assert result.is_valid is True, f"on_failure '{action}' should be valid"

    def test_negative_retry_attempts_should_fail(self):
        """测试：负数重试次数应该失败"""
        yaml_content = """
name: test_node
kind: node
description: 测试节点
version: "1.0.0"
executor_type: python
error_strategy:
  retry:
    max_attempts: -1
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False


class TestNodeYamlSchemaNestedNodes:
    """测试嵌套节点校验"""

    def test_valid_nested_children_should_pass(self):
        """测试：有效的嵌套子节点应该通过"""
        yaml_content = """
name: parent_node
kind: node
description: 父节点
version: "1.0.0"
executor_type: container
nested:
  children:
    - name: child_1
      executor_type: python
    - name: child_2
      executor_type: llm
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is True

    def test_nested_with_parallel_flag_should_pass(self):
        """测试：并行执行标志应该通过"""
        yaml_content = """
name: parallel_node
kind: node
description: 并行节点
version: "1.0.0"
executor_type: parallel
nested:
  parallel: true
  children:
    - name: task_1
      executor_type: python
    - name: task_2
      executor_type: http
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is True

    def test_nested_exceeds_max_depth_should_fail(self):
        """测试：嵌套深度超过限制应该失败"""
        # 构造深度为 6 的嵌套（假设最大深度为 5）
        yaml_content = """
name: level_0
kind: node
description: 深度测试
version: "1.0.0"
executor_type: container
nested:
  children:
    - name: level_1
      executor_type: container
      nested:
        children:
          - name: level_2
            executor_type: container
            nested:
              children:
                - name: level_3
                  executor_type: container
                  nested:
                    children:
                      - name: level_4
                        executor_type: container
                        nested:
                          children:
                            - name: level_5
                              executor_type: python
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("depth" in e.message.lower() for e in result.errors)


class TestNodeYamlSchemaDynamicCode:
    """测试动态代码段校验"""

    def test_valid_dynamic_code_should_pass(self):
        """测试：有效的动态代码应该通过"""
        yaml_content = """
name: dynamic_node
kind: node
description: 动态代码节点
version: "1.0.0"
executor_type: python
dynamic_code:
  pre_execute: |
    # 预处理代码
    data = prepare_input(input_data)
  post_execute: |
    # 后处理代码
    result = format_output(result)
  transform: |
    # 数据转换
    return transform_data(data)
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is True

    def test_dynamic_code_with_syntax_error_should_fail(self):
        """测试：有语法错误的动态代码应该失败"""
        yaml_content = """
name: bad_code_node
kind: node
description: 错误代码节点
version: "1.0.0"
executor_type: python
dynamic_code:
  pre_execute: |
    def broken(
      # 缺少闭合括号
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("syntax" in e.message.lower() for e in result.errors)


class TestNodeYamlSchemaExtendedMetadata:
    """测试扩展元数据校验"""

    def test_valid_extended_metadata_should_pass(self):
        """测试：有效的扩展元数据应该通过"""
        yaml_content = """
name: full_node
kind: node
description: 完整节点定义
version: "1.0.0"
author: test_author
tags:
  - data-processing
  - analytics
category: data
executor_type: python
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is True

    def test_invalid_tag_format_should_fail(self):
        """测试：无效的标签格式应该失败"""
        yaml_content = """
name: bad_tags_node
kind: node
description: 错误标签节点
version: "1.0.0"
executor_type: python
tags:
  - "tag with spaces!"
  - "invalid@tag#"
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("tags" in e.field for e in result.errors)


class TestNodeYamlSchemaExecution:
    """测试执行配置校验"""

    def test_valid_execution_config_should_pass(self):
        """测试：有效的执行配置应该通过"""
        yaml_content = """
name: exec_node
kind: node
description: 执行配置节点
version: "1.0.0"
executor_type: python
execution:
  timeout_seconds: 30
  sandbox: true
  memory_limit: "256m"
  cpu_limit: "0.5"
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is True

    def test_negative_timeout_should_fail(self):
        """测试：负数超时时间应该失败"""
        yaml_content = """
name: bad_timeout_node
kind: node
description: 错误超时节点
version: "1.0.0"
executor_type: python
execution:
  timeout_seconds: -10
"""
        validator = NodeYamlValidator()
        result = validator.validate_yaml_string(yaml_content)

        assert result.is_valid is False
        assert any("timeout" in e.field.lower() for e in result.errors)


class TestNodeYamlValidatorFileOperations:
    """测试文件操作"""

    def test_validate_yaml_file_should_work(self, tmp_path):
        """测试：验证 YAML 文件应该工作"""
        yaml_file = tmp_path / "test_node.yaml"
        yaml_file.write_text("""
name: file_test_node
kind: node
description: 文件测试节点
version: "1.0.0"
executor_type: python
""")

        validator = NodeYamlValidator()
        result = validator.validate_yaml_file(yaml_file)

        assert result.is_valid is True

    def test_validate_nonexistent_file_should_fail(self, tmp_path):
        """测试：验证不存在的文件应该失败"""
        nonexistent = tmp_path / "nonexistent.yaml"

        validator = NodeYamlValidator()
        result = validator.validate_yaml_file(nonexistent)

        assert result.is_valid is False
        assert any(
            "not found" in e.message.lower() or "exist" in e.message.lower() for e in result.errors
        )

    def test_validate_directory_should_work(self, tmp_path):
        """测试：验证目录下所有 YAML 文件应该工作"""
        # 创建有效文件
        (tmp_path / "valid.yaml").write_text("""
name: valid_node
kind: node
description: 有效节点
version: "1.0.0"
executor_type: python
""")
        # 创建无效文件
        (tmp_path / "invalid.yaml").write_text("""
name: invalid_node
kind: invalid_kind
""")

        validator = NodeYamlValidator()
        results = validator.validate_directory(tmp_path)

        assert len(results) == 2
        assert results["valid.yaml"].is_valid is True
        assert results["invalid.yaml"].is_valid is False


class TestNodeYamlSchemaIntegration:
    """集成测试：验证现有节点定义文件"""

    def test_validate_existing_llm_yaml(self):
        """测试：验证现有 llm.yaml 文件"""
        llm_yaml_path = Path("definitions/nodes/llm.yaml")
        if not llm_yaml_path.exists():
            pytest.skip("llm.yaml not found")

        validator = NodeYamlValidator()
        result = validator.validate_yaml_file(llm_yaml_path)

        # 现有文件可能需要迁移，所以这里允许警告
        assert result.is_valid is True or len(result.warnings) > 0

    def test_validate_existing_code_yaml(self):
        """测试：验证现有 code.yaml 文件"""
        code_yaml_path = Path("definitions/nodes/code.yaml")
        if not code_yaml_path.exists():
            pytest.skip("code.yaml not found")

        validator = NodeYamlValidator()
        result = validator.validate_yaml_file(code_yaml_path)

        assert result.is_valid is True or len(result.warnings) > 0

    def test_validate_existing_api_yaml(self):
        """测试：验证现有 api.yaml 文件"""
        api_yaml_path = Path("definitions/nodes/api.yaml")
        if not api_yaml_path.exists():
            pytest.skip("api.yaml not found")

        validator = NodeYamlValidator()
        result = validator.validate_yaml_file(api_yaml_path)

        assert result.is_valid is True or len(result.warnings) > 0
