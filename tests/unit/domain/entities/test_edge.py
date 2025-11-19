"""测试：Edge 实体

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- Edge 表示工作流中节点之间的连接
- 定义了数据流向和执行顺序
"""

import pytest

from src.domain.entities.edge import Edge
from src.domain.exceptions import DomainError


class TestEdgeCreation:
    """测试 Edge 创建"""

    def test_create_edge_with_valid_params_should_succeed(self):
        """测试：使用有效参数创建 Edge 应该成功

        验收标准：
        - Edge 必须有唯一 ID
        - source_node_id 和 target_node_id 必须被正确保存
        """
        # Arrange & Act
        edge = Edge.create(
            source_node_id="node_1",
            target_node_id="node_2",
        )

        # Assert
        assert edge.id is not None, "Edge 必须有唯一 ID"
        assert edge.id.startswith("edge_"), "Edge ID 应该以 edge_ 开头"
        assert edge.source_node_id == "node_1"
        assert edge.target_node_id == "node_2"
        assert edge.condition is None, "默认没有条件"

    def test_create_edge_with_condition_should_succeed(self):
        """测试：创建带条件的 Edge 应该成功"""
        # Arrange & Act
        edge = Edge.create(
            source_node_id="node_1",
            target_node_id="node_2",
            condition="result.status == 'success'",
        )

        # Assert
        assert edge.condition == "result.status == 'success'"

    def test_create_edge_with_empty_source_should_raise_error(self):
        """测试：使用空 source_node_id 创建 Edge 应该抛出错误"""
        # Act & Assert
        with pytest.raises(DomainError, match="source_node_id 不能为空"):
            Edge.create(
                source_node_id="",
                target_node_id="node_2",
            )

    def test_create_edge_with_empty_target_should_raise_error(self):
        """测试：使用空 target_node_id 创建 Edge 应该抛出错误"""
        # Act & Assert
        with pytest.raises(DomainError, match="target_node_id 不能为空"):
            Edge.create(
                source_node_id="node_1",
                target_node_id="",
            )

    def test_create_edge_with_same_source_and_target_should_raise_error(self):
        """测试：source 和 target 相同应该抛出错误

        业务规则：
        - 不允许节点连接到自己（避免死循环）
        """
        # Act & Assert
        with pytest.raises(DomainError, match="不能连接到自己"):
            Edge.create(
                source_node_id="node_1",
                target_node_id="node_1",
            )
