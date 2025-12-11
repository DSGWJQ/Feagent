"""NodeDefinition 父节点加载与继承能力单元测试

第三步：NodeDefinition 扩展
- 父节点加载：从 ParentNodeSchema 创建 NodeDefinition
- 子节点展开：根据 children 引用展开为 NodeDefinition DAG
- 策略继承：继承 error_strategy、resources 等配置
- API 查询：供 ConversationAgent/WorkflowAgent 查询节点配置

TDD Red 阶段：先编写测试，预期全部失败
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from src.domain.agents.node_definition import (
    MAX_NODE_DEFINITION_DEPTH,
    NodeDefinition,
    NodeType,
)
from src.domain.services.parent_node_schema import (
    ParentNodeSchema,
    ParentNodeValidator,
)


# ============================================================================
# Fixtures: 测试数据
# ============================================================================


@pytest.fixture
def child_node_registry() -> dict[str, NodeDefinition]:
    """构造一个简易子节点注册表，模拟 ref -> NodeDefinition 映射"""
    return {
        "node.api": NodeDefinition(
            node_type=NodeType.HTTP,
            name="接口调用",
            url="https://example.com/api",
            method="POST",
            config={"resources": {"cpu": "0.5", "memory": "512m"}},
        ),
        "node.calc": NodeDefinition(
            node_type=NodeType.PYTHON,
            name="计算步骤",
            code="return x + 1",
            config={"resources": {"cpu": "1", "memory": "256m"}},
            error_strategy={"retry": {"max_attempts": 1}, "on_failure": "abort"},
        ),
        "node.llm": NodeDefinition(
            node_type=NodeType.LLM,
            name="问答",
            prompt="{question}",
            config={"resources": {"cpu": "0.2", "memory": "128m"}},
        ),
        "node.db": NodeDefinition(
            node_type=NodeType.DATABASE,
            name="数据库查询",
            query="SELECT * FROM users",
            config={"resources": {"cpu": "0.3", "memory": "256m"}},
        ),
    }


@pytest.fixture
def parent_schema_dict() -> dict[str, Any]:
    """构造父节点 schema，用于 from_parent_schema 测试"""
    return {
        "name": "data_pipeline",
        "kind": "workflow",
        "version": "1.0.0",
        "executor_type": "sequential",
        "description": "数据处理流水线",
        "inherit": {
            "parameters": {
                "input_path": {"type": "string", "required": True},
            },
            "returns": {
                "output_path": {"type": "string"},
            },
            "error_strategy": {
                "retry": {"max_attempts": 3, "delay_seconds": 5.0},
                "on_failure": "retry",
            },
            "resources": {"cpu": "2", "memory": "4g"},
            "tags": ["workflow", "parent"],
        },
        "children": [
            {"ref": "node.api", "alias": "extract"},
            {
                "ref": "node.calc",
                "alias": "transform",
                "override": {"resources": {"memory": "1g"}},
            },
        ],
    }


@pytest.fixture
def template_registry() -> dict[str, dict[str, Any]]:
    """构造模板注册表，用于继承测试"""
    return {
        "tpl.base": {
            "name": "base_template",
            "kind": "template",
            "version": "1.0.0",
            "error_strategy": {
                "retry": {"max_attempts": 1},
                "on_failure": "abort",
            },
            "resources": {"cpu": "1", "memory": "512Mi"},
        },
        "tpl.advanced": {
            "name": "advanced_template",
            "kind": "template",
            "version": "1.0.0",
            "inherit_from": "tpl.base",
            "error_strategy": {
                "retry": {"max_attempts": 5},
            },
        },
    }


# ============================================================================
# 测试类：父节点加载
# ============================================================================


class TestParentNodeLoading:
    """父节点加载测试

    测试 NodeDefinition.from_parent_schema 方法
    """

    def test_from_parent_schema_basic(
        self, parent_schema_dict: dict[str, Any], child_node_registry: dict[str, NodeDefinition]
    ):
        """from_parent_schema 应能将父节点 schema 转为 NodeDefinition"""
        validator = ParentNodeValidator()

        # 调用被测方法
        parent = NodeDefinition.from_parent_schema(
            parent_schema_dict, child_node_registry, validator
        )

        # 验证基本属性
        assert parent.name == "data_pipeline"
        assert parent.node_type == NodeType.GENERIC  # 父节点默认为 GENERIC
        assert parent.description == "数据处理流水线"

        # 验证 inherit 块被正确解析
        assert parent.input_schema.get("input_path") == "string"
        assert parent.output_schema.get("output_path") == "string"

        # 验证错误策略
        assert parent.error_strategy is not None
        assert parent.error_strategy["retry"]["max_attempts"] == 3

        # 验证资源配置
        assert parent.config.get("resources", {}).get("cpu") == "2"

    def test_from_parent_schema_invalid_schema_raises(
        self, child_node_registry: dict[str, NodeDefinition]
    ):
        """无效 schema 应抛出异常，防止加载不合规父节点"""
        invalid_schema = {"kind": "workflow", "version": "1.0.0"}  # 缺少 name
        validator = ParentNodeValidator()

        with pytest.raises(ValueError):
            NodeDefinition.from_parent_schema(invalid_schema, child_node_registry, validator)

    def test_from_parent_schema_with_inherit_from(
        self,
        child_node_registry: dict[str, NodeDefinition],
        template_registry: dict[str, dict[str, Any]],
    ):
        """from_parent_schema 应支持 inherit_from 继承"""
        schema = {
            "name": "inheriting_workflow",
            "kind": "workflow",
            "version": "1.0.0",
            "inherit_from": "tpl.base",
            "children": [{"ref": "node.api", "alias": "step1"}],
        }
        validator = ParentNodeValidator(registry=template_registry)

        parent = NodeDefinition.from_parent_schema(schema, child_node_registry, validator)

        # 验证继承了模板的错误策略
        assert parent.error_strategy is not None
        assert parent.error_strategy["on_failure"] == "abort"

        # 验证继承了模板的资源配置
        assert parent.config.get("resources", {}).get("cpu") == "1"


# ============================================================================
# 测试类：子节点展开
# ============================================================================


class TestChildExpansion:
    """子节点展开测试

    测试 NodeDefinition.expand_children 方法
    """

    def test_expand_children_basic(self, child_node_registry: dict[str, NodeDefinition]):
        """expand_children 应从注册表拉取子节点并设置 parent_id"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={
                "children": [
                    {"ref": "node.api", "alias": "api_call"},
                    {"ref": "node.calc", "alias": "calc"},
                ]
            },
        )

        # 调用被测方法
        expanded = parent.expand_children(child_node_registry)

        # 验证展开结果
        assert len(expanded) == 2
        assert len(parent.children) == 2

        # 验证 parent_id 设置
        for child in parent.children:
            assert child.parent_id == parent.id

    def test_expand_children_applies_override(self, child_node_registry: dict[str, NodeDefinition]):
        """expand_children 应正确应用子节点 override"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={
                "children": [
                    {
                        "ref": "node.calc",
                        "alias": "calc",
                        "override": {
                            "resources": {"memory": "2g"},
                            "error_strategy": {"on_failure": "skip"},
                        },
                    },
                ]
            },
        )

        parent.expand_children(child_node_registry)

        calc_child = parent.children[0]

        # 验证 override 生效
        assert calc_child.config["resources"]["memory"] == "2g"
        # 注意：on_failure 应该被 override 覆盖
        assert calc_child.error_strategy["on_failure"] == "skip"

    def test_expand_children_preserves_node_type(
        self, child_node_registry: dict[str, NodeDefinition]
    ):
        """展开后应保留子节点的原始类型和属性"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.api", "alias": "api_step"}]},
        )

        parent.expand_children(child_node_registry)

        api_child = parent.children[0]
        assert api_child.node_type == NodeType.HTTP
        assert api_child.url == "https://example.com/api"
        assert api_child.method == "POST"

    def test_expand_children_missing_ref_raises(
        self, child_node_registry: dict[str, NodeDefinition]
    ):
        """引用不存在的子节点应抛出异常"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.not_exist", "alias": "missing"}]},
        )

        with pytest.raises(KeyError):
            parent.expand_children(child_node_registry)

    def test_expand_children_empty_list(self, child_node_registry: dict[str, NodeDefinition]):
        """空 children 列表应正常处理"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": []},
        )

        expanded = parent.expand_children(child_node_registry)

        assert len(expanded) == 0
        assert len(parent.children) == 0

    def test_expand_children_no_children_key(self, child_node_registry: dict[str, NodeDefinition]):
        """没有 children 键时应返回空列表"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={},
        )

        expanded = parent.expand_children(child_node_registry)

        assert len(expanded) == 0


# ============================================================================
# 测试类：策略继承
# ============================================================================


class TestStrategyInheritance:
    """策略继承测试

    测试 apply_inherited_strategy 和 get_inherited_* 方法
    """

    def test_apply_inherited_strategy_merges_parent_and_child(self):
        """子节点应继承父级策略并允许局部覆盖"""
        parent_strategy = {
            "retry": {"max_attempts": 3, "delay_seconds": 1.0},
            "on_failure": "retry",
        }
        parent_resources = {"cpu": "2", "memory": "2g"}

        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点",
            code="pass",
            error_strategy={"on_failure": "skip"},
            config={"resources": {"memory": "4g"}},
        )

        # 调用被测方法
        child.apply_inherited_strategy(parent_strategy, parent_resources)

        # 验证合并后的策略
        merged_strategy = child.get_inherited_error_strategy()
        merged_resources = child.get_inherited_resources()

        # 继承重试策略
        assert merged_strategy["retry"]["max_attempts"] == 3
        # 子节点覆盖 on_failure
        assert merged_strategy["on_failure"] == "skip"
        # 继承 cpu
        assert merged_resources["cpu"] == "2"
        # 子节点覆盖 memory
        assert merged_resources["memory"] == "4g"

    def test_apply_inherited_strategy_when_child_missing_fields(self):
        """未设置策略时应完全继承父级"""
        parent_strategy = {"retry": {"max_attempts": 2}, "on_failure": "abort"}
        parent_resources = {"cpu": "1", "memory": "1g"}

        child = NodeDefinition(
            node_type=NodeType.HTTP,
            name="HTTP 子节点",
            url="https://example.com",
        )

        child.apply_inherited_strategy(parent_strategy, parent_resources)

        assert child.get_inherited_error_strategy()["on_failure"] == "abort"
        assert child.get_inherited_resources()["cpu"] == "1"

    def test_apply_inherited_strategy_none_parent_strategy(self):
        """父级策略为 None 时应保持子节点原有策略"""
        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点",
            code="pass",
            error_strategy={"on_failure": "skip"},
            config={"resources": {"memory": "1g"}},
        )

        child.apply_inherited_strategy(None, None)

        assert child.get_inherited_error_strategy()["on_failure"] == "skip"
        assert child.get_inherited_resources()["memory"] == "1g"

    def test_get_inherited_error_strategy_empty(self):
        """没有错误策略时应返回空字典"""
        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点",
            code="pass",
        )

        assert child.get_inherited_error_strategy() == {}

    def test_get_inherited_resources_empty(self):
        """没有资源配置时应返回空字典"""
        child = NodeDefinition(
            node_type=NodeType.PYTHON,
            name="子节点",
            code="pass",
        )

        assert child.get_inherited_resources() == {}


# ============================================================================
# 测试类：API 查询
# ============================================================================


class TestApiQueries:
    """API 查询测试

    测试 get_child_by_name, get_child_by_alias 等方法
    """

    def test_get_child_by_name(self, child_node_registry: dict[str, NodeDefinition]):
        """按名称获取子节点"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.api", "alias": "api_step"}]},
        )
        parent.expand_children(child_node_registry)

        # 按原始名称查询
        api_child = parent.get_child_by_name("接口调用")
        assert api_child is not None
        assert api_child.node_type == NodeType.HTTP

    def test_get_child_by_name_not_found(self, child_node_registry: dict[str, NodeDefinition]):
        """按名称查询不存在的子节点应返回 None"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.api", "alias": "api_step"}]},
        )
        parent.expand_children(child_node_registry)

        assert parent.get_child_by_name("不存在") is None

    def test_get_child_by_alias(self, child_node_registry: dict[str, NodeDefinition]):
        """按别名获取子节点"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={
                "children": [
                    {"ref": "node.api", "alias": "api_step"},
                    {"ref": "node.calc", "alias": "calc_step"},
                ]
            },
        )
        parent.expand_children(child_node_registry)

        api_child = parent.get_child_by_alias("api_step")
        calc_child = parent.get_child_by_alias("calc_step")

        assert api_child is not None
        assert api_child.url == "https://example.com/api"
        assert calc_child is not None
        assert calc_child.code == "return x + 1"

    def test_get_child_by_alias_not_found(self, child_node_registry: dict[str, NodeDefinition]):
        """按别名查询不存在的子节点应返回 None"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.api", "alias": "api_step"}]},
        )
        parent.expand_children(child_node_registry)

        assert parent.get_child_by_alias("missing") is None


# ============================================================================
# 测试类：折叠状态
# ============================================================================


class TestCollapsedState:
    """折叠状态测试"""

    def test_collapsed_state_controls_visible_children(
        self, child_node_registry: dict[str, NodeDefinition]
    ):
        """折叠时子节点不可见，展开后可见"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.api", "alias": "api_step"}]},
        )
        parent.expand_children(child_node_registry)

        # 默认折叠
        assert parent.collapsed is True
        assert parent.get_visible_children() == []

        # 展开
        parent.expand()
        assert len(parent.get_visible_children()) == len(parent.children)

        # 再次折叠
        parent.collapse()
        assert parent.get_visible_children() == []

    def test_toggle_collapsed(self, child_node_registry: dict[str, NodeDefinition]):
        """toggle_collapsed 应切换折叠状态"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.api", "alias": "api_step"}]},
        )
        parent.expand_children(child_node_registry)

        assert parent.collapsed is True
        parent.toggle_collapsed()
        assert parent.collapsed is False
        parent.toggle_collapsed()
        assert parent.collapsed is True


# ============================================================================
# 测试类：深度限制
# ============================================================================


class TestDepthLimit:
    """深度限制测试"""

    def test_expand_children_respects_max_depth(
        self, child_node_registry: dict[str, NodeDefinition]
    ):
        """超过最大深度时应抛出异常"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.api", "alias": "api_step"}]},
        )
        # 人为设置已达最大深度
        parent._depth = MAX_NODE_DEFINITION_DEPTH

        with pytest.raises(ValueError):
            parent.expand_children(child_node_registry)

    def test_expand_children_within_depth(self, child_node_registry: dict[str, NodeDefinition]):
        """未触达限制时可正常展开"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.api", "alias": "api_step"}]},
        )
        parent._depth = MAX_NODE_DEFINITION_DEPTH - 1

        children = parent.expand_children(child_node_registry)
        assert len(children) == 1
        assert parent.children[0].parent_id == parent.id

    def test_child_depth_incremented(self, child_node_registry: dict[str, NodeDefinition]):
        """展开后子节点深度应递增"""
        parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="父节点",
            config={"children": [{"ref": "node.api", "alias": "api_step"}]},
        )
        parent._depth = 2

        parent.expand_children(child_node_registry)

        assert parent.children[0]._depth == 3


# ============================================================================
# 测试类：集成测试
# ============================================================================


class TestIntegration:
    """集成测试：完整的父节点加载与展开流程"""

    def test_full_workflow_parent_to_expanded_children(
        self,
        parent_schema_dict: dict[str, Any],
        child_node_registry: dict[str, NodeDefinition],
    ):
        """完整流程：schema -> NodeDefinition -> 展开子节点 -> 策略继承"""
        validator = ParentNodeValidator()

        # Step 1: 从 schema 创建父节点
        parent = NodeDefinition.from_parent_schema(
            parent_schema_dict, child_node_registry, validator
        )

        # Step 2: 展开子节点
        parent.expand_children(child_node_registry)

        # Step 3: 应用策略继承
        parent_strategy = parent.error_strategy
        parent_resources = parent.config.get("resources", {})

        for child in parent.children:
            child.apply_inherited_strategy(parent_strategy, parent_resources)

        # 验证结果
        assert len(parent.children) == 2

        # 验证第一个子节点（没有 override）继承了父级策略
        extract_child = parent.get_child_by_alias("extract")
        assert extract_child is not None
        inherited_strategy = extract_child.get_inherited_error_strategy()
        assert inherited_strategy.get("retry", {}).get("max_attempts") == 3

        # 验证第二个子节点（有 override）
        transform_child = parent.get_child_by_alias("transform")
        assert transform_child is not None
        # override 的 memory 生效
        assert transform_child.config["resources"]["memory"] == "1g"

    def test_nested_parent_expansion(self, child_node_registry: dict[str, NodeDefinition]):
        """测试嵌套父节点的展开（父节点的子节点也是父节点）"""
        # 创建一个嵌套的子节点注册表
        inner_parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="内层父节点",
            config={
                "children": [
                    {"ref": "node.api", "alias": "inner_api"},
                ]
            },
        )

        nested_registry = copy.deepcopy(child_node_registry)
        nested_registry["node.inner_parent"] = inner_parent

        # 外层父节点
        outer_parent = NodeDefinition(
            node_type=NodeType.GENERIC,
            name="外层父节点",
            config={
                "children": [
                    {"ref": "node.inner_parent", "alias": "inner"},
                    {"ref": "node.calc", "alias": "calc"},
                ]
            },
        )

        # 展开外层
        outer_parent.expand_children(nested_registry)

        assert len(outer_parent.children) == 2

        # 获取内层父节点
        inner_child = outer_parent.get_child_by_alias("inner")
        assert inner_child is not None
        assert inner_child.node_type == NodeType.GENERIC

        # 展开内层
        inner_child.expand_children(child_node_registry)
        assert len(inner_child.children) == 1


# ============================================================================
# 导出
# ============================================================================


__all__ = [
    "TestParentNodeLoading",
    "TestChildExpansion",
    "TestStrategyInheritance",
    "TestApiQueries",
    "TestCollapsedState",
    "TestDepthLimit",
    "TestIntegration",
]
