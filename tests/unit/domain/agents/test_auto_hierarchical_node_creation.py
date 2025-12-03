"""测试：自动生成层次化节点结构

测试目标：
1. 当创建"数据处理"类型节点时，自动生成父+容器子结构
2. HierarchicalNodeFactory 服务
3. 识别需要容器执行的节点类型
4. 正确设置父子关系

完成标准：
- 数据处理节点自动变为父+容器子
- 父节点为 GENERIC 类型
- 子节点为 CONTAINER 类型
- 父子关系正确设置
"""

from src.domain.agents.node_definition import NodeDefinition, NodeType

# ==================== 测试1：识别需要容器执行的节点 ====================


class TestContainerNodeDetection:
    """测试识别需要容器执行的节点"""

    def test_data_processing_needs_container(self):
        """数据处理节点需要容器执行"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        assert factory.needs_container_execution("数据处理") is True
        assert factory.needs_container_execution("data_processing") is True

    def test_ml_node_needs_container(self):
        """机器学习节点需要容器执行"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        assert factory.needs_container_execution("机器学习") is True
        assert factory.needs_container_execution("ML模型训练") is True

    def test_simple_python_does_not_need_container(self):
        """简单 Python 代码不需要容器"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        assert factory.needs_container_execution("简单计算") is False
        assert factory.needs_container_execution("字符串处理") is False

    def test_custom_container_keywords(self):
        """支持自定义容器关键词"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory(container_keywords=["自定义任务", "特殊处理"])

        assert factory.needs_container_execution("自定义任务") is True
        assert factory.needs_container_execution("特殊处理") is True


# ==================== 测试2：创建层次化节点结构 ====================


class TestHierarchicalNodeCreation:
    """测试创建层次化节点结构"""

    def test_create_hierarchical_data_processing_node(self):
        """创建数据处理节点时自动生成层次结构"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        result = factory.create_node(
            name="数据处理",
            code="import pandas; df = pandas.read_csv('data.csv')",
        )

        # 返回的应该是父节点
        assert result.node_type == NodeType.GENERIC
        assert result.name == "数据处理"
        assert len(result.children) == 1

    def test_container_child_has_correct_type(self):
        """容器子节点类型正确"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="数据处理",
            code="import pandas; print('Processing')",
        )

        child = parent.children[0]
        assert child.node_type == NodeType.CONTAINER
        assert child.is_container is True

    def test_container_child_has_code(self):
        """容器子节点包含代码"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="数据处理",
            code="print('Hello')",
        )

        child = parent.children[0]
        assert child.code == "print('Hello')"

    def test_parent_child_relationship_set(self):
        """父子关系正确设置"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="ML训练",
            code="from sklearn import svm",
        )

        child = parent.children[0]
        assert child.parent_id == parent.id

    def test_simple_node_not_hierarchical(self):
        """简单节点不创建层次结构"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        node = factory.create_node(
            name="简单计算",
            code="result = 1 + 1",
        )

        # 简单节点应该是 PYTHON 类型，没有子节点
        assert node.node_type == NodeType.PYTHON
        assert len(node.children) == 0


# ==================== 测试3：容器配置 ====================


class TestContainerConfiguration:
    """测试容器配置"""

    def test_default_container_config(self):
        """默认容器配置"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="数据处理",
            code="import pandas",
        )

        child = parent.children[0]
        assert "image" in child.container_config
        assert child.container_config["image"] == "python:3.11-slim"

    def test_custom_container_config(self):
        """自定义容器配置"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="数据处理",
            code="import pandas",
            container_config={
                "image": "python:3.10",
                "timeout": 120,
                "memory_limit": "1g",
            },
        )

        child = parent.children[0]
        assert child.container_config["image"] == "python:3.10"
        assert child.container_config["timeout"] == 120
        assert child.container_config["memory_limit"] == "1g"

    def test_auto_detect_dependencies(self):
        """自动检测代码依赖"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="数据处理",
            code="import pandas\nimport numpy\nfrom sklearn import svm",
        )

        child = parent.children[0]
        pip_packages = child.container_config.get("pip_packages", [])

        assert "pandas" in pip_packages
        assert "numpy" in pip_packages
        assert "scikit-learn" in pip_packages


# ==================== 测试4：子节点命名 ====================


class TestChildNodeNaming:
    """测试子节点命名"""

    def test_child_node_name_format(self):
        """子节点命名格式"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="数据处理",
            code="print('test')",
        )

        child = parent.children[0]
        # 子节点名称应包含父节点名称 + 容器标识
        assert "数据处理" in child.name or "Container" in child.name

    def test_child_node_description(self):
        """子节点描述"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="ML训练",
            code="model.fit(X, y)",
            description="训练机器学习模型",
        )

        child = parent.children[0]
        # 子节点描述应说明是容器执行
        assert "容器" in child.description or "container" in child.description.lower()


# ==================== 测试5：多子节点场景 ====================


class TestMultipleChildNodes:
    """测试多子节点场景"""

    def test_can_add_multiple_container_children(self):
        """可以添加多个容器子节点"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="数据处理流水线",
            code="step1()",
        )

        # 手动添加更多子节点
        child2 = NodeDefinition(
            node_type=NodeType.CONTAINER,
            name="步骤2",
            code="step2()",
            is_container=True,
        )
        parent.add_child(child2)

        assert len(parent.children) == 2

    def test_create_with_multiple_steps(self):
        """创建多步骤数据处理"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        # 创建包含多个步骤的节点
        parent = factory.create_multi_step_node(
            name="ETL流程",
            steps=[
                {"name": "提取", "code": "data = extract()"},
                {"name": "转换", "code": "data = transform(data)"},
                {"name": "加载", "code": "load(data)"},
            ],
        )

        assert parent.node_type == NodeType.GENERIC
        assert len(parent.children) == 3
        assert parent.children[0].name == "提取"
        assert parent.children[1].name == "转换"
        assert parent.children[2].name == "加载"


# ==================== 测试6：序列化支持 ====================


class TestHierarchicalSerialization:
    """测试层次化结构序列化"""

    def test_hierarchical_node_to_dict(self):
        """层次化节点可序列化"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        parent = factory.create_node(
            name="数据处理",
            code="print('test')",
        )

        data = parent.to_dict()

        assert "children" in data
        assert len(data["children"]) == 1
        assert data["children"][0]["node_type"] == "container"

    def test_hierarchical_node_from_dict(self):
        """可从字典恢复层次化节点"""
        from src.domain.agents.hierarchical_node_factory import (
            HierarchicalNodeFactory,
        )

        factory = HierarchicalNodeFactory()

        original = factory.create_node(
            name="数据处理",
            code="print('test')",
        )

        data = original.to_dict()
        restored = NodeDefinition.from_dict(data)

        assert restored.name == "数据处理"
        assert len(restored.children) == 1
        assert restored.children[0].parent_id == restored.id


# 导出
__all__ = [
    "TestContainerNodeDetection",
    "TestHierarchicalNodeCreation",
    "TestContainerConfiguration",
    "TestChildNodeNaming",
    "TestMultipleChildNodes",
    "TestHierarchicalSerialization",
]
