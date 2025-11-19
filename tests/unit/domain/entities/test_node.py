"""测试：Node 实体

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- Node 是工作流中的执行单元
- 每个 Node 有类型、名称、配置、位置等属性
"""

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position


class TestNodeCreation:
    """测试 Node 创建"""

    def test_create_node_with_valid_params_should_succeed(self):
        """测试：使用有效参数创建 Node 应该成功

        验收标准：
        - Node 必须有唯一 ID
        - type、name、config、position 必须被正确保存
        """
        # Arrange & Act
        node = Node.create(
            type=NodeType.HTTP,
            name="获取 GitHub Issue",
            config={"url": "https://api.github.com/repos/owner/repo/issues", "method": "GET"},
            position=Position(x=100, y=200),
        )

        # Assert
        assert node.id is not None, "Node 必须有唯一 ID"
        assert node.id.startswith("node_"), "Node ID 应该以 node_ 开头"
        assert node.type == NodeType.HTTP, "type 必须被正确保存"
        assert node.name == "获取 GitHub Issue", "name 必须被正确保存"
        assert node.config == {
            "url": "https://api.github.com/repos/owner/repo/issues",
            "method": "GET",
        }
        assert node.position == Position(x=100, y=200), "position 必须被正确保存"

    def test_create_node_with_empty_name_should_raise_error(self):
        """测试：使用空名称创建 Node 应该抛出错误

        业务规则：
        - name 是必需的，不能为空
        """
        # Act & Assert
        with pytest.raises(DomainError, match="name 不能为空"):
            Node.create(
                type=NodeType.HTTP,
                name="",
                config={},
                position=Position(x=100, y=200),
            )

    def test_create_node_with_whitespace_name_should_raise_error(self):
        """测试：使用纯空格名称创建 Node 应该抛出错误"""
        # Act & Assert
        with pytest.raises(DomainError, match="name 不能为空"):
            Node.create(
                type=NodeType.HTTP,
                name="   ",
                config={},
                position=Position(x=100, y=200),
            )

    def test_create_node_should_trim_name(self):
        """测试：创建 Node 时应该去除名称首尾空格"""
        # Arrange & Act
        node = Node.create(
            type=NodeType.HTTP,
            name="  获取数据  ",
            config={},
            position=Position(x=100, y=200),
        )

        # Assert
        assert node.name == "获取数据", "应该去除首尾空格"


class TestNodeUpdate:
    """测试 Node 更新"""

    def test_update_position_should_succeed(self):
        """测试：更新节点位置应该成功"""
        # Arrange
        node = Node.create(
            type=NodeType.HTTP,
            name="测试节点",
            config={},
            position=Position(x=100, y=200),
        )

        # Act
        node.update_position(Position(x=300, y=400))

        # Assert
        assert node.position == Position(x=300, y=400)

    def test_update_config_should_succeed(self):
        """测试：更新节点配置应该成功"""
        # Arrange
        node = Node.create(
            type=NodeType.HTTP,
            name="测试节点",
            config={"url": "https://example.com"},
            position=Position(x=100, y=200),
        )

        # Act
        new_config = {"url": "https://new-example.com", "method": "POST"}
        node.update_config(new_config)

        # Assert
        assert node.config == new_config
