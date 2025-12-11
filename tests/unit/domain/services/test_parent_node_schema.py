"""父节点抽象模型 Schema 验证单元测试

测试范围：
- 父节点 schema 验证
- 继承机制（inherit_from, override）
- 输入输出定义继承
- 错误处理策略继承
- 资源限制继承
- 子节点列表验证
- 复用标签合并

TDD红灯阶段：所有测试应先失败
"""

from __future__ import annotations

import pytest

from src.domain.services.parent_node_schema import (
    ParentNodeSchema,
    ParentNodeValidator,
    InheritanceMerger,
    InheritanceError,
    CyclicInheritanceError,
    ConflictingInheritanceError,
    InvalidSchemaError,
)


class TestParentNodeSchemaBasicValidation:
    """基础 Schema 验证测试"""

    def test_valid_parent_node_schema_minimal(self):
        """最小有效父节点 schema"""
        schema = {
            "name": "parent_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "children": [
                {"ref": "node.extract", "alias": "extract"}
            ]
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_valid_parent_node_schema_full(self):
        """完整父节点 schema"""
        schema = {
            "name": "data_pipeline",
            "kind": "workflow",
            "version": "1.0.0",
            "description": "Data processing workflow",
            "executor_type": "parallel",
            "inherit_from": ["tpl.base.io", "tpl.base.resources"],
            "inherit": {
                "parameters": {
                    "input_path": {"type": "string", "required": True}
                },
                "returns": {
                    "output_path": {"type": "string"}
                },
                "error_strategy": {
                    "retry": {"max_attempts": 3, "delay_seconds": 5.0}
                },
                "resources": {
                    "cpu": "2",
                    "memory": "4g"
                },
                "tags": ["team:data", "tier:batch"]
            },
            "override": {
                "resources": {"cpu": "4"},
                "tags": ["owner:alice"]
            },
            "children": [
                {"ref": "node.extract", "alias": "extract"},
                {"ref": "node.transform", "alias": "transform"}
            ]
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_kind_field(self):
        """缺少 kind 字段"""
        schema = {
            "name": "test_workflow",
            "version": "1.0.0",
            "executor_type": "sequential"
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("kind" in str(e).lower() for e in result.errors)

    def test_invalid_kind_enum(self):
        """kind 字段值非法"""
        schema = {
            "name": "test_workflow",
            "kind": "invalid_kind",
            "version": "1.0.0",
            "executor_type": "sequential"
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("kind" in str(e).lower() for e in result.errors)

    def test_missing_name_field(self):
        """缺少 name 字段"""
        schema = {
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential"
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("name" in str(e).lower() for e in result.errors)

    def test_missing_version_field(self):
        """缺少 version 字段"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "executor_type": "sequential"
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("version" in str(e).lower() for e in result.errors)


class TestInheritFromValidation:
    """inherit_from 字段验证测试"""

    def test_inherit_from_single_string(self):
        """inherit_from 单字符串"""
        schema = {
            "name": "child_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit_from": "tpl.base"
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        # 基础语法验证通过
        assert result.is_valid or all(
            "inherit_from" not in str(e).lower() or "reference" in str(e).lower()
            for e in result.errors
        )

    def test_inherit_from_array(self):
        """inherit_from 数组"""
        schema = {
            "name": "child_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit_from": ["tpl.base.io", "tpl.base.resources"]
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        # 基础语法验证通过
        assert result.is_valid or all(
            "inherit_from" not in str(e).lower() or "reference" in str(e).lower()
            for e in result.errors
        )

    def test_inherit_from_empty_string(self):
        """inherit_from 空字符串"""
        schema = {
            "name": "child_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit_from": ""
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("inherit_from" in str(e).lower() or "empty" in str(e).lower()
                   for e in result.errors)

    def test_inherit_from_invalid_type(self):
        """inherit_from 类型非法（数字）"""
        schema = {
            "name": "child_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit_from": 123
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("inherit_from" in str(e).lower() or "type" in str(e).lower()
                   for e in result.errors)


class TestInheritBlockValidation:
    """inherit 块验证测试"""

    def test_inherit_parameters_valid(self):
        """inherit.parameters 有效定义"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "parameters": {
                    "input_path": {"type": "string", "required": True},
                    "batch_size": {"type": "integer", "default": 100}
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert result.is_valid

    def test_inherit_parameters_missing_type(self):
        """inherit.parameters 缺少 type"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "parameters": {
                    "input_path": {"required": True}  # 缺少 type
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("type" in str(e).lower() for e in result.errors)

    def test_inherit_parameters_invalid_type_enum(self):
        """inherit.parameters type 值非法"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "parameters": {
                    "input_path": {"type": "invalid_type", "required": True}
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("type" in str(e).lower() for e in result.errors)

    def test_inherit_parameters_default_type_mismatch(self):
        """inherit.parameters default 类型不匹配"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "parameters": {
                    "batch_size": {"type": "integer", "default": "not_a_number"}
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("default" in str(e).lower() or "mismatch" in str(e).lower()
                   for e in result.errors)

    def test_inherit_unknown_field(self):
        """inherit 包含未知字段"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "unknown_field": {"value": 123}
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("unknown" in str(e).lower() or "unexpected" in str(e).lower()
                   for e in result.errors)


class TestErrorStrategyValidation:
    """error_strategy 验证测试"""

    def test_error_strategy_valid(self):
        """有效的 error_strategy"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "error_strategy": {
                    "retry": {
                        "max_attempts": 3,
                        "delay_seconds": 5.0,
                        "backoff_multiplier": 2.0
                    },
                    "on_failure": "abort"
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert result.is_valid

    def test_error_strategy_invalid_max_attempts(self):
        """retry.max_attempts 非正整数"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "error_strategy": {
                    "retry": {"max_attempts": -1}
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("max_attempts" in str(e).lower() for e in result.errors)

    def test_error_strategy_invalid_on_failure_enum(self):
        """on_failure 非法枚举值"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "error_strategy": {
                    "on_failure": "invalid_action"
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("on_failure" in str(e).lower() for e in result.errors)


class TestResourcesValidation:
    """resources 资源限制验证测试"""

    def test_resources_valid(self):
        """有效的资源限制"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "resources": {
                    "cpu": "2",
                    "memory": "4g"
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert result.is_valid

    def test_resources_invalid_memory_format(self):
        """memory 格式非法"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "resources": {
                    "memory": "invalid_format"
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("memory" in str(e).lower() for e in result.errors)

    def test_resources_invalid_cpu_format(self):
        """cpu 格式非法"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            "inherit": {
                "resources": {
                    "cpu": "invalid"
                }
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("cpu" in str(e).lower() for e in result.errors)


class TestChildrenValidation:
    """children 子节点列表验证测试"""

    def test_children_valid(self):
        """有效的子节点列表"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "parallel",
            "children": [
                {"ref": "node.extract", "alias": "extract"},
                {"ref": "node.transform", "alias": "transform"}
            ]
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert result.is_valid

    def test_children_missing_ref(self):
        """children 缺少 ref"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "parallel",
            "children": [
                {"alias": "extract"}  # 缺少 ref
            ]
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("ref" in str(e).lower() for e in result.errors)

    def test_children_duplicate_alias(self):
        """children alias 重复"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "parallel",
            "children": [
                {"ref": "node.extract", "alias": "step1"},
                {"ref": "node.transform", "alias": "step1"}  # 重复
            ]
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("alias" in str(e).lower() or "duplicate" in str(e).lower()
                   for e in result.errors)

    def test_children_with_override(self):
        """children 带 override"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "parallel",
            "children": [
                {
                    "ref": "node.extract",
                    "alias": "extract",
                    "override": {
                        "resources": {"memory": "8g"}
                    }
                }
            ]
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert result.is_valid

    def test_parallel_workflow_requires_children(self):
        """并行工作流必须有 children"""
        schema = {
            "name": "test_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "parallel",
            "nested": {"parallel": True}
            # 缺少 children
        }
        validator = ParentNodeValidator()
        result = validator.validate(schema)
        assert not result.is_valid
        assert any("children" in str(e).lower() for e in result.errors)


class TestInheritanceMerger:
    """继承合并器测试"""

    def test_merge_single_source(self):
        """单源继承合并"""
        base = {
            "parameters": {
                "input_path": {"type": "string", "required": True}
            },
            "resources": {"cpu": "1", "memory": "2g"},
            "tags": ["base"]
        }
        child = {
            "resources": {"cpu": "2"},
            "tags": ["child"]
        }
        merger = InheritanceMerger()
        result = merger.merge([base], child)

        assert result["parameters"]["input_path"]["type"] == "string"
        assert result["resources"]["cpu"] == "2"  # 覆盖
        assert result["resources"]["memory"] == "2g"  # 继承
        assert "base" in result["tags"]
        assert "child" in result["tags"]

    def test_merge_multiple_sources(self):
        """多源继承合并（后者覆盖前者）"""
        source1 = {
            "resources": {"cpu": "1", "memory": "1g"},
            "tags": ["source1"]
        }
        source2 = {
            "resources": {"cpu": "2"},
            "tags": ["source2"]
        }
        child = {}
        merger = InheritanceMerger()
        result = merger.merge([source1, source2], child)

        assert result["resources"]["cpu"] == "2"  # source2 覆盖 source1
        assert result["resources"]["memory"] == "1g"  # 只有 source1 有
        assert "source1" in result["tags"]
        assert "source2" in result["tags"]

    def test_override_explicit(self):
        """显式 override 覆盖继承"""
        base = {
            "resources": {"cpu": "1", "memory": "2g"},
            "tags": ["base", "inherited"]
        }
        child = {}
        override = {
            "resources": {"cpu": "4"},
            "tags": ["explicit_only"]  # 完全覆盖数组
        }
        merger = InheritanceMerger()
        result = merger.merge([base], child, override)

        assert result["resources"]["cpu"] == "4"  # override
        assert result["resources"]["memory"] == "2g"  # 继承
        assert result["tags"] == ["explicit_only"]  # 完全覆盖

    def test_deep_merge_error_strategy(self):
        """深层合并 error_strategy"""
        base = {
            "error_strategy": {
                "retry": {"max_attempts": 3, "delay_seconds": 5.0},
                "on_failure": "abort"
            }
        }
        child = {
            "error_strategy": {
                "retry": {"max_attempts": 5}
            }
        }
        merger = InheritanceMerger()
        result = merger.merge([base], child)

        assert result["error_strategy"]["retry"]["max_attempts"] == 5  # 覆盖
        assert result["error_strategy"]["retry"]["delay_seconds"] == 5.0  # 继承
        assert result["error_strategy"]["on_failure"] == "abort"  # 继承

    def test_tags_deduplication(self):
        """tags 去重合并"""
        base = {"tags": ["a", "b", "c"]}
        child = {"tags": ["b", "c", "d"]}
        merger = InheritanceMerger()
        result = merger.merge([base], child)

        assert sorted(result["tags"]) == ["a", "b", "c", "d"]


class TestCyclicInheritanceDetection:
    """循环继承检测测试"""

    def test_detect_direct_cycle(self):
        """检测直接循环 A -> A"""
        registry = {
            "node.a": {"inherit_from": "node.a"}
        }
        validator = ParentNodeValidator(registry=registry)

        with pytest.raises(CyclicInheritanceError) as exc_info:
            validator.resolve_inheritance("node.a")

        assert "node.a" in str(exc_info.value)

    def test_detect_indirect_cycle(self):
        """检测间接循环 A -> B -> C -> A"""
        registry = {
            "node.a": {"inherit_from": "node.b"},
            "node.b": {"inherit_from": "node.c"},
            "node.c": {"inherit_from": "node.a"}
        }
        validator = ParentNodeValidator(registry=registry)

        with pytest.raises(CyclicInheritanceError) as exc_info:
            validator.resolve_inheritance("node.a")

        # 应包含循环链路信息
        error_msg = str(exc_info.value)
        assert "node.a" in error_msg
        assert "node.b" in error_msg
        assert "node.c" in error_msg


class TestConflictDetection:
    """继承冲突检测测试"""

    def test_detect_conflict_without_override(self):
        """检测多源冲突且无显式 override"""
        source1 = {"resources": {"cpu": "1"}}
        source2 = {"resources": {"cpu": "2"}}
        child = {}  # 无 override

        merger = InheritanceMerger(strict_conflict=True)

        with pytest.raises(ConflictingInheritanceError) as exc_info:
            merger.merge([source1, source2], child)

        assert "cpu" in str(exc_info.value)

    def test_no_conflict_with_override(self):
        """有显式 override 时无冲突"""
        source1 = {"resources": {"cpu": "1"}}
        source2 = {"resources": {"cpu": "2"}}
        override = {"resources": {"cpu": "4"}}

        merger = InheritanceMerger(strict_conflict=True)
        result = merger.merge([source1, source2], {}, override)

        assert result["resources"]["cpu"] == "4"


class TestReferenceResolution:
    """引用解析测试"""

    def test_resolve_existing_reference(self):
        """解析存在的引用"""
        registry = {
            "tpl.base": {
                "resources": {"cpu": "1", "memory": "1g"}
            }
        }
        validator = ParentNodeValidator(registry=registry)
        resolved = validator.resolve_reference("tpl.base")

        assert resolved["resources"]["cpu"] == "1"

    def test_resolve_nonexistent_reference(self):
        """解析不存在的引用"""
        registry = {}
        validator = ParentNodeValidator(registry=registry)

        with pytest.raises(InvalidSchemaError) as exc_info:
            validator.resolve_reference("nonexistent.tpl")

        assert "nonexistent" in str(exc_info.value)


class TestInheritanceDepth:
    """继承深度限制测试"""

    def test_max_inheritance_depth(self):
        """继承深度超限"""
        # 创建深度为 10 的继承链
        registry = {}
        for i in range(10):
            parent_key = f"node.level{i+1}" if i < 9 else None
            registry[f"node.level{i}"] = {
                "inherit_from": parent_key
            } if parent_key else {}

        validator = ParentNodeValidator(registry=registry, max_depth=5)

        with pytest.raises(InheritanceError) as exc_info:
            validator.resolve_inheritance("node.level0")

        assert "depth" in str(exc_info.value).lower()


class TestParentNodeSchemaFromYaml:
    """从 YAML 加载父节点 schema 测试"""

    def test_load_valid_yaml(self, tmp_path):
        """加载有效 YAML"""
        yaml_content = """
name: data_pipeline
kind: workflow
version: "1.0.0"
executor_type: sequential
inherit:
  parameters:
    input_path:
      type: string
      required: true
  resources:
    cpu: "2"
    memory: "4g"
children:
  - ref: node.extract
    alias: extract
"""
        yaml_file = tmp_path / "test_parent.yaml"
        yaml_file.write_text(yaml_content)

        schema = ParentNodeSchema.from_yaml(yaml_file)
        assert schema.name == "data_pipeline"
        assert schema.kind == "workflow"
        assert len(schema.children) == 1

    def test_load_invalid_yaml_syntax(self, tmp_path):
        """加载语法错误的 YAML"""
        yaml_content = """
name: test
kind: workflow
  invalid_indent: true
"""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text(yaml_content)

        with pytest.raises(InvalidSchemaError):
            ParentNodeSchema.from_yaml(yaml_file)


class TestParentNodeSchemaToYaml:
    """父节点 schema 序列化为 YAML 测试"""

    def test_serialize_to_yaml(self, tmp_path):
        """序列化为 YAML"""
        schema = ParentNodeSchema(
            name="test_workflow",
            kind="workflow",
            version="1.0.0",
            executor_type="sequential",
            inherit={
                "parameters": {"input": {"type": "string", "required": True}},
                "resources": {"cpu": "1"}
            },
            children=[{"ref": "node.step1", "alias": "step1"}]
        )

        yaml_file = tmp_path / "output.yaml"
        schema.to_yaml(yaml_file)

        assert yaml_file.exists()
        loaded = ParentNodeSchema.from_yaml(yaml_file)
        assert loaded.name == "test_workflow"
        assert loaded.inherit["resources"]["cpu"] == "1"


class TestIntegrationWithExistingSchema:
    """与现有 node_definition_schema.json 集成测试"""

    def test_backward_compatible_with_existing_nodes(self):
        """与现有节点定义向后兼容"""
        # 现有节点定义格式
        existing_node = {
            "name": "http_request",
            "kind": "node",
            "version": "1.0.0",
            "executor_type": "http",
            "parameters": [
                {"name": "url", "type": "string", "required": True}
            ],
            "returns": {
                "type": "object",
                "properties": {"response": {"type": "object"}}
            }
        }
        validator = ParentNodeValidator()
        result = validator.validate(existing_node)
        assert result.is_valid

    def test_parent_node_extends_existing_schema(self):
        """父节点扩展现有 schema"""
        parent_node = {
            "name": "etl_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "executor_type": "sequential",
            # 继承相关字段（新增）
            "inherit_from": "tpl.base",
            "inherit": {
                "error_strategy": {"retry": {"max_attempts": 3}}
            },
            # 现有字段
            "parameters": [
                {"name": "source", "type": "string", "required": True}
            ],
            "children": [
                {"ref": "node.extract", "alias": "extract"}
            ]
        }
        validator = ParentNodeValidator()
        result = validator.validate(parent_node)
        # 应能通过基础验证
        assert result.is_valid or all(
            "inherit_from" in str(e).lower() and "reference" in str(e).lower()
            for e in result.errors
        )
