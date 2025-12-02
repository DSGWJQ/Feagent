"""增量同步测试

TDD 驱动：验证 _calculate_diff 方法的正确性

测试场景：
1. 节点增加
2. 节点删除
3. 节点修改（位置、配置）
4. 边增加
5. 边删除
6. 混合变更
7. 无变更
"""

import pytest

from src.infrastructure.websocket.canvas_sync import CanvasDiff, CanvasSyncService


class TestCalculateDiff:
    """_calculate_diff 方法测试"""

    def setup_method(self):
        """设置测试环境"""
        self.service = CanvasSyncService()

    def test_no_changes_returns_empty_diff(self):
        """测试：无变更应返回空 diff"""
        old_state = {
            "nodes": [
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "edge_1", "source": "node_1", "target": "node_2"},
            ],
        }
        new_state = {
            "nodes": [
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "edge_1", "source": "node_1", "target": "node_2"},
            ],
        }

        diff = self.service._calculate_diff(old_state, new_state)

        assert diff.added_nodes == []
        assert diff.removed_nodes == []
        assert diff.modified_nodes == []
        assert diff.added_edges == []
        assert diff.removed_edges == []
        assert diff.is_empty() is True

    def test_node_added_detected(self):
        """测试：检测节点新增"""
        old_state = {
            "nodes": [
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            ],
            "edges": [],
        }
        new_state = {
            "nodes": [
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
                {
                    "id": "node_2",
                    "type": "llm",
                    "position": {"x": 100, "y": 0},
                    "data": {"model": "gpt-4"},
                },
            ],
            "edges": [],
        }

        diff = self.service._calculate_diff(old_state, new_state)

        assert len(diff.added_nodes) == 1
        assert diff.added_nodes[0]["id"] == "node_2"
        assert diff.added_nodes[0]["type"] == "llm"
        assert diff.removed_nodes == []
        assert diff.modified_nodes == []
        assert diff.is_empty() is False

    def test_node_removed_detected(self):
        """测试：检测节点删除"""
        old_state = {
            "nodes": [
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "node_2", "type": "llm", "position": {"x": 100, "y": 0}, "data": {}},
            ],
            "edges": [],
        }
        new_state = {
            "nodes": [
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            ],
            "edges": [],
        }

        diff = self.service._calculate_diff(old_state, new_state)

        assert diff.added_nodes == []
        assert len(diff.removed_nodes) == 1
        assert diff.removed_nodes[0] == "node_2"
        assert diff.modified_nodes == []
        assert diff.is_empty() is False

    def test_node_position_modified_detected(self):
        """测试：检测节点位置修改"""
        old_state = {
            "nodes": [
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            ],
            "edges": [],
        }
        new_state = {
            "nodes": [
                {"id": "node_1", "type": "start", "position": {"x": 100, "y": 200}, "data": {}},
            ],
            "edges": [],
        }

        diff = self.service._calculate_diff(old_state, new_state)

        assert diff.added_nodes == []
        assert diff.removed_nodes == []
        assert len(diff.modified_nodes) == 1
        assert diff.modified_nodes[0]["id"] == "node_1"
        assert diff.modified_nodes[0]["changes"]["position"] == {"x": 100, "y": 200}
        assert diff.is_empty() is False

    def test_node_data_modified_detected(self):
        """测试：检测节点数据修改"""
        old_state = {
            "nodes": [
                {
                    "id": "node_1",
                    "type": "llm",
                    "position": {"x": 0, "y": 0},
                    "data": {"model": "gpt-3.5"},
                },
            ],
            "edges": [],
        }
        new_state = {
            "nodes": [
                {
                    "id": "node_1",
                    "type": "llm",
                    "position": {"x": 0, "y": 0},
                    "data": {"model": "gpt-4"},
                },
            ],
            "edges": [],
        }

        diff = self.service._calculate_diff(old_state, new_state)

        assert diff.added_nodes == []
        assert diff.removed_nodes == []
        assert len(diff.modified_nodes) == 1
        assert diff.modified_nodes[0]["id"] == "node_1"
        assert diff.modified_nodes[0]["changes"]["data"] == {"model": "gpt-4"}
        assert diff.is_empty() is False

    def test_edge_added_detected(self):
        """测试：检测边新增"""
        old_state = {
            "nodes": [],
            "edges": [],
        }
        new_state = {
            "nodes": [],
            "edges": [
                {"id": "edge_1", "source": "node_1", "target": "node_2"},
            ],
        }

        diff = self.service._calculate_diff(old_state, new_state)

        assert len(diff.added_edges) == 1
        assert diff.added_edges[0]["id"] == "edge_1"
        assert diff.added_edges[0]["source"] == "node_1"
        assert diff.added_edges[0]["target"] == "node_2"
        assert diff.removed_edges == []
        assert diff.is_empty() is False

    def test_edge_removed_detected(self):
        """测试：检测边删除"""
        old_state = {
            "nodes": [],
            "edges": [
                {"id": "edge_1", "source": "node_1", "target": "node_2"},
            ],
        }
        new_state = {
            "nodes": [],
            "edges": [],
        }

        diff = self.service._calculate_diff(old_state, new_state)

        assert diff.added_edges == []
        assert len(diff.removed_edges) == 1
        assert diff.removed_edges[0] == "edge_1"
        assert diff.is_empty() is False

    def test_mixed_changes_detected(self):
        """测试：检测混合变更"""
        old_state = {
            "nodes": [
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "node_2", "type": "llm", "position": {"x": 100, "y": 0}, "data": {}},
            ],
            "edges": [
                {"id": "edge_1", "source": "node_1", "target": "node_2"},
            ],
        }
        new_state = {
            "nodes": [
                {
                    "id": "node_1",
                    "type": "start",
                    "position": {"x": 50, "y": 50},
                    "data": {},
                },  # 修改位置
                # node_2 被删除
                {
                    "id": "node_3",
                    "type": "http",
                    "position": {"x": 200, "y": 0},
                    "data": {},
                },  # 新增
            ],
            "edges": [
                # edge_1 被删除
                {"id": "edge_2", "source": "node_1", "target": "node_3"},  # 新增
            ],
        }

        diff = self.service._calculate_diff(old_state, new_state)

        assert len(diff.added_nodes) == 1
        assert diff.added_nodes[0]["id"] == "node_3"

        assert len(diff.removed_nodes) == 1
        assert diff.removed_nodes[0] == "node_2"

        assert len(diff.modified_nodes) == 1
        assert diff.modified_nodes[0]["id"] == "node_1"

        assert len(diff.added_edges) == 1
        assert diff.added_edges[0]["id"] == "edge_2"

        assert len(diff.removed_edges) == 1
        assert diff.removed_edges[0] == "edge_1"

        assert diff.is_empty() is False


class TestCanvasDiff:
    """CanvasDiff 数据类测试"""

    def test_empty_diff_is_empty(self):
        """测试：空 diff 的 is_empty() 应返回 True"""
        diff = CanvasDiff(
            added_nodes=[],
            removed_nodes=[],
            modified_nodes=[],
            added_edges=[],
            removed_edges=[],
        )

        assert diff.is_empty() is True

    def test_non_empty_diff_is_not_empty(self):
        """测试：非空 diff 的 is_empty() 应返回 False"""
        diff = CanvasDiff(
            added_nodes=[{"id": "node_1"}],
            removed_nodes=[],
            modified_nodes=[],
            added_edges=[],
            removed_edges=[],
        )

        assert diff.is_empty() is False

    def test_diff_to_messages_empty(self):
        """测试：空 diff 转换为空消息列表"""
        diff = CanvasDiff(
            added_nodes=[],
            removed_nodes=[],
            modified_nodes=[],
            added_edges=[],
            removed_edges=[],
        )

        messages = diff.to_messages("wf_123")

        assert messages == []

    def test_diff_to_messages_with_changes(self):
        """测试：非空 diff 转换为消息列表"""
        diff = CanvasDiff(
            added_nodes=[
                {"id": "node_1", "type": "llm", "position": {"x": 0, "y": 0}, "data": {}},
            ],
            removed_nodes=["node_2"],
            modified_nodes=[
                {"id": "node_3", "changes": {"position": {"x": 100, "y": 100}}},
            ],
            added_edges=[
                {"id": "edge_1", "source": "node_1", "target": "node_3"},
            ],
            removed_edges=["edge_2"],
        )

        messages = diff.to_messages("wf_123")

        assert len(messages) == 5

        # 验证消息类型
        message_types = [m["type"] for m in messages]
        assert "node_created" in message_types
        assert "node_deleted" in message_types
        assert "node_updated" in message_types
        assert "edge_created" in message_types
        assert "edge_deleted" in message_types

        # 验证 workflow_id
        for msg in messages:
            assert msg["workflow_id"] == "wf_123"


class TestIncrementalSync:
    """增量同步集成测试"""

    @pytest.mark.asyncio
    async def test_sync_incremental_sends_only_changes(self):
        """测试：增量同步只发送变更部分"""
        service = CanvasSyncService()

        # 设置旧状态
        service.set_workflow_state(
            "wf_123",
            nodes=[
                {"id": "node_1", "type": "start", "position": {"x": 0, "y": 0}, "data": {}},
            ],
            edges=[],
        )

        # 新状态
        new_nodes = [
            {"id": "node_1", "type": "start", "position": {"x": 50, "y": 50}, "data": {}},
            {"id": "node_2", "type": "llm", "position": {"x": 100, "y": 0}, "data": {}},
        ]
        new_edges = [
            {"id": "edge_1", "source": "node_1", "target": "node_2"},
        ]

        # 计算增量
        old_state = service.get_canvas_snapshot("wf_123")
        new_state = {"nodes": new_nodes, "edges": new_edges}
        diff = service._calculate_diff(old_state, new_state)

        # 验证增量内容
        assert len(diff.added_nodes) == 1
        assert diff.added_nodes[0]["id"] == "node_2"

        assert len(diff.modified_nodes) == 1
        assert diff.modified_nodes[0]["id"] == "node_1"

        assert len(diff.added_edges) == 1
        assert diff.added_edges[0]["id"] == "edge_1"

        # 更新状态
        service.set_workflow_state("wf_123", new_nodes, new_edges)

        # 再次计算应该没有变更
        new_old_state = service.get_canvas_snapshot("wf_123")
        no_change_diff = service._calculate_diff(new_old_state, new_state)
        assert no_change_diff.is_empty() is True
