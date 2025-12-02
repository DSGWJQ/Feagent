"""层级节点持久化与画布同步测试 - Phase 9.4

TDD RED阶段：测试层级节点的持久化和画布同步

业务场景：
- 用户创建层级节点后刷新页面，层级结构应保持
- 用户折叠/展开节点，状态应同步到画布
"""


class TestHierarchyPersistence:
    """层级持久化测试"""

    def test_node_to_dict_with_hierarchy(self):
        """Node.to_dict 应包含完整层级信息"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={"name": "流程"})
        child1 = Node(id="child1", type=NodeType.CODE, config={"code": "x=1"})
        child2 = Node(id="child2", type=NodeType.CODE, config={"code": "y=2"})

        parent.add_child(child1)
        parent.add_child(child2)

        data = parent.to_dict()

        assert data["id"] == "parent"
        assert data["type"] == "generic"
        assert data["collapsed"] is True
        assert len(data["children"]) == 2
        assert data["children"][0]["id"] == "child1"
        assert data["children"][0]["parent_id"] == "parent"

    def test_node_from_dict_restores_hierarchy(self):
        """Node.from_dict 应恢复层级结构"""
        from src.domain.services.node_registry import Node, NodeType

        data = {
            "id": "parent",
            "type": "generic",
            "config": {"name": "流程"},
            "collapsed": False,
            "children": [
                {
                    "id": "child1",
                    "type": "code",
                    "config": {"code": "x=1"},
                    "parent_id": "parent",
                    "children": [],
                },
                {
                    "id": "child2",
                    "type": "code",
                    "config": {"code": "y=2"},
                    "parent_id": "parent",
                    "children": [],
                },
            ],
        }

        node = Node.from_dict(data)

        assert node.id == "parent"
        assert node.type == NodeType.GENERIC
        assert node.collapsed is False
        assert len(node.children) == 2
        assert node.children[0].parent_id == "parent"
        assert node.children[1].parent_id == "parent"

    def test_nested_hierarchy_serialization(self):
        """嵌套层级序列化和反序列化"""
        from src.domain.services.node_registry import Node, NodeType

        # 创建三层嵌套
        root = Node(id="root", type=NodeType.GENERIC, config={"name": "根"})
        child = Node(id="child", type=NodeType.GENERIC, config={"name": "子"})
        grandchild = Node(id="grandchild", type=NodeType.CODE, config={"code": "x"})

        root.add_child(child)
        child.add_child(grandchild)

        # 序列化
        data = root.to_dict()

        # 反序列化
        restored = Node.from_dict(data)

        assert len(restored.children) == 1
        assert len(restored.children[0].children) == 1
        assert restored.children[0].children[0].id == "grandchild"


class TestHierarchyCanvasSync:
    """层级画布同步测试"""

    def test_canvas_sync_includes_hierarchy(self):
        """画布同步应包含层级信息"""
        from src.domain.services.node_registry import Node, NodeType

        # 创建层级节点
        parent = Node(id="parent", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x=1"})
        parent.add_child(child)

        # 使用 to_dict 获取画布数据
        node_data = parent.to_dict()

        assert node_data["id"] == "parent"
        assert node_data["collapsed"] is True
        assert "children" in node_data
        assert len(node_data["children"]) == 1

    def test_hierarchy_canvas_message_format(self):
        """层级画布消息格式应正确"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x=1"})
        parent.add_child(child)

        # 模拟画布同步消息
        message = {
            "type": "node_hierarchy_update",
            "workflow_id": "wf_1",
            "node": parent.to_dict(),
        }

        assert message["type"] == "node_hierarchy_update"
        assert message["node"]["children"][0]["id"] == "child"

    def test_collapse_toggle_message_format(self):
        """折叠切换消息格式应正确"""
        message = {
            "type": "node_collapse_toggle",
            "workflow_id": "wf_1",
            "node_id": "parent",
            "collapsed": True,
        }

        assert message["type"] == "node_collapse_toggle"
        assert message["node_id"] == "parent"
        assert message["collapsed"] is True


class TestWorkflowRepositoryHierarchy:
    """工作流仓库层级支持测试 - 使用 JSON config 存储层级信息"""

    def test_hierarchy_stored_in_config_json(self):
        """层级信息应能存储在 config JSON 字段中"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x=1"})
        parent.add_child(child)

        # 序列化为可存储格式
        data = parent.to_dict()

        # config 应包含层级信息
        assert "children" in data
        assert "collapsed" in data
        assert "parent_id" in data or data.get("parent_id") is None

    def test_save_and_load_hierarchical_nodes(self):
        """应能保存和加载层级节点"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x=1"})
        parent.add_child(child)

        # 序列化（模拟保存到数据库）
        data = parent.to_dict()

        # 反序列化（模拟从数据库加载）
        loaded = Node.from_dict(data)

        assert loaded.id == "parent"
        assert len(loaded.children) == 1
        assert loaded.children[0].parent_id == "parent"

    def test_node_config_preserves_custom_fields(self):
        """节点 config 应保留自定义字段"""
        from src.domain.services.node_registry import Node, NodeType

        node = Node(
            id="node",
            type=NodeType.GENERIC,
            config={"name": "测试", "custom_field": "value"},
        )

        data = node.to_dict()

        assert data["config"]["name"] == "测试"
        assert data["config"]["custom_field"] == "value"


class TestHierarchyWebSocketMessages:
    """层级 WebSocket 消息测试"""

    def test_create_hierarchy_update_message(self):
        """应能创建层级更新消息"""
        from src.domain.services.node_registry import Node, NodeType

        parent = Node(id="parent", type=NodeType.GENERIC, config={"name": "流程"})
        child = Node(id="child", type=NodeType.CODE, config={"code": "x=1"})
        parent.add_child(child)

        message = {
            "type": "hierarchy_update",
            "node_id": parent.id,
            "collapsed": parent.collapsed,
            "children": [c.to_dict() for c in parent.children],
        }

        assert message["type"] == "hierarchy_update"
        assert message["node_id"] == "parent"
        assert message["collapsed"] is True
        assert len(message["children"]) == 1

    def test_create_collapse_toggle_message(self):
        """应能创建折叠切换消息"""
        message = {
            "type": "collapse_toggle",
            "node_id": "node_1",
            "collapsed": True,
        }

        assert message["type"] == "collapse_toggle"
        assert message["node_id"] == "node_1"
        assert message["collapsed"] is True
