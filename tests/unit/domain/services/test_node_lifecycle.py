"""节点生命周期与模板复用测试 - 阶段 4

TDD 驱动：先写测试定义期望行为，再实现功能

测试场景：
1. 节点 scope/promotion_status/version 字段
2. 创建草稿节点
3. 升级为模板
4. 在新 workflow 中实例化模板
5. 版本历史管理
6. 回滚到指定版本

完成标准：
- 单元测试覆盖：创建草稿节点、升级为模板、在新 workflow 中实例化模板
- 调用 API 能列出节点历史版本，并可回滚到指定版本
"""

import pytest


class TestNodeScopeAndVersion:
    """测试节点 scope 和 version 字段"""

    def test_node_has_scope_field(self):
        """测试：Node 应该有 scope 字段

        scope 定义节点的作用域：
        - workflow: 仅在当前工作流可用
        - template: 可被其他工作流复用
        - global: 系统级全局可用
        """
        from src.domain.services.node_registry import (
            Node,
            NodeScope,
            NodeType,
        )

        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={"user_prompt": "test"},
            scope=NodeScope.WORKFLOW,
        )

        assert node.scope == NodeScope.WORKFLOW

    def test_node_has_version_field(self):
        """测试：Node 应该有 version 字段

        version 用于版本控制和回滚
        """
        from src.domain.services.node_registry import Node, NodeType

        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={"user_prompt": "test"},
            version=1,
        )

        assert node.version == 1

    def test_node_has_promotion_status_field(self):
        """测试：Node 应该有 promotion_status 字段

        promotion_status 表示升级状态：
        - draft: 草稿
        - promoted: 已升级为模板
        - published: 已发布为全局
        """
        from src.domain.services.node_registry import (
            Node,
            NodeType,
            PromotionStatus,
        )

        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={"user_prompt": "test"},
            promotion_status=PromotionStatus.DRAFT,
        )

        assert node.promotion_status == PromotionStatus.DRAFT

    def test_node_default_values(self):
        """测试：Node 默认值"""
        from src.domain.services.node_registry import (
            Node,
            NodeScope,
            NodeType,
            PromotionStatus,
        )

        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={},
        )

        # 默认值
        assert node.scope == NodeScope.WORKFLOW
        assert node.version == 1
        assert node.promotion_status == PromotionStatus.DRAFT


class TestNodePromotion:
    """测试节点升级流程：临时 → 模板 → 全局"""

    def test_promote_workflow_to_template(self):
        """测试：将工作流节点升级为模板

        场景：
        1. 用户创建一个 LLM 节点配置
        2. 发现配置很好用，想复用
        3. 将节点升级为模板

        验收标准：
        - 节点 scope 从 workflow 变为 template
        - promotion_status 变为 promoted
        """
        from src.domain.services.node_registry import (
            Node,
            NodeScope,
            NodeType,
            PromotionStatus,
        )

        # 创建工作流节点
        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={"model": "gpt-4", "user_prompt": "分析数据"},
            scope=NodeScope.WORKFLOW,
            promotion_status=PromotionStatus.DRAFT,
        )

        # 升级为模板
        node.promote_to_template(template_name="数据分析模板")

        # 验证
        assert node.scope == NodeScope.TEMPLATE
        assert node.promotion_status == PromotionStatus.PROMOTED
        assert node.template_name == "数据分析模板"

    def test_promote_template_to_global(self):
        """测试：将模板升级为全局节点

        场景：
        - 模板经过验证，要发布为全局可用

        验收标准：
        - 节点 scope 变为 global
        - promotion_status 变为 published
        """
        from src.domain.services.node_registry import (
            Node,
            NodeScope,
            NodeType,
            PromotionStatus,
        )

        # 创建模板节点
        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={"model": "gpt-4", "user_prompt": "通用分析"},
            scope=NodeScope.TEMPLATE,
            promotion_status=PromotionStatus.PROMOTED,
            template_name="通用分析模板",
        )

        # 升级为全局
        node.promote_to_global()

        # 验证
        assert node.scope == NodeScope.GLOBAL
        assert node.promotion_status == PromotionStatus.PUBLISHED

    def test_cannot_promote_draft_directly_to_global(self):
        """测试：不能直接从草稿升级到全局

        必须先升级为模板，再升级为全局
        """
        from src.domain.services.node_registry import (
            Node,
            NodeScope,
            NodeType,
            PromotionStatus,
        )

        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={},
            scope=NodeScope.WORKFLOW,
            promotion_status=PromotionStatus.DRAFT,
        )

        with pytest.raises(ValueError, match="必须先升级为模板"):
            node.promote_to_global()


class TestTemplateInstantiation:
    """测试模板实例化"""

    def test_create_node_from_template(self):
        """测试：从模板创建新节点

        场景：
        1. 用户选择一个模板
        2. 在新工作流中实例化该模板
        3. 新节点继承模板配置，但是独立的实例

        验收标准：
        - 新节点有新的 ID
        - 新节点配置来自模板
        - 新节点 scope 是 workflow
        - 新节点可以独立修改
        """
        from src.domain.services.node_registry import (
            NodeScope,
            NodeType,
            PromotionStatus,
        )
        from src.domain.services.node_template_manager import NodeTemplateManager

        # 创建模板管理器
        manager = NodeTemplateManager()

        # 注册模板
        template_id = manager.register_template(
            name="数据分析模板",
            node_type=NodeType.LLM,
            config={"model": "gpt-4", "user_prompt": "分析数据"},
            description="通用数据分析模板",
        )

        # 从模板实例化
        node = manager.instantiate(template_id, workflow_id="wf_new")

        # 验证
        assert node.id != template_id
        assert node.type == NodeType.LLM
        assert node.config["model"] == "gpt-4"
        assert node.scope == NodeScope.WORKFLOW
        assert node.promotion_status == PromotionStatus.DRAFT
        assert node.source_template_id == template_id

    def test_list_available_templates(self):
        """测试：列出可用模板"""
        from src.domain.services.node_registry import NodeType
        from src.domain.services.node_template_manager import NodeTemplateManager

        manager = NodeTemplateManager()

        # 注册多个模板
        manager.register_template(
            name="模板A",
            node_type=NodeType.LLM,
            config={},
        )
        manager.register_template(
            name="模板B",
            node_type=NodeType.API,
            config={"url": "https://api.example.com"},
        )

        # 列出模板
        templates = manager.list_templates()

        assert len(templates) == 2
        assert any(t["name"] == "模板A" for t in templates)
        assert any(t["name"] == "模板B" for t in templates)

    def test_instantiate_template_in_multiple_workflows(self):
        """测试：在多个工作流中实例化同一模板

        验收标准：
        - 每个实例是独立的
        - 修改一个实例不影响其他实例和模板
        """
        from src.domain.services.node_registry import NodeType
        from src.domain.services.node_template_manager import NodeTemplateManager

        manager = NodeTemplateManager()

        template_id = manager.register_template(
            name="HTTP请求模板",
            node_type=NodeType.API,
            config={"url": "https://api.example.com", "method": "GET"},
        )

        # 在两个工作流中实例化
        node1 = manager.instantiate(template_id, workflow_id="wf_1")
        node2 = manager.instantiate(template_id, workflow_id="wf_2")

        # 修改 node1
        node1.config["url"] = "https://modified.example.com"

        # node2 不受影响
        assert node2.config["url"] == "https://api.example.com"

        # 模板也不受影响
        template = manager.get_template(template_id)
        assert template["config"]["url"] == "https://api.example.com"


class TestNodeVersionHistory:
    """测试节点版本历史"""

    def test_record_version_on_update(self):
        """测试：更新节点时记录版本

        每次修改节点配置，自动增加版本号并记录历史
        """
        from src.domain.services.node_registry import Node, NodeType
        from src.domain.services.node_version_manager import NodeVersionManager

        manager = NodeVersionManager()

        # 创建节点
        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={"model": "gpt-3.5", "user_prompt": "v1"},
            version=1,
        )

        # 记录初始版本
        manager.record_version(node)

        # 更新节点
        node.config["model"] = "gpt-4"
        node.config["user_prompt"] = "v2"
        node.version = 2

        # 记录新版本
        manager.record_version(node)

        # 验证版本历史
        history = manager.get_version_history(node.id)

        assert len(history) == 2
        assert history[0]["version"] == 1
        assert history[0]["config"]["model"] == "gpt-3.5"
        assert history[1]["version"] == 2
        assert history[1]["config"]["model"] == "gpt-4"

    def test_list_node_versions(self):
        """测试：列出节点所有历史版本

        调用 API 能列出节点历史版本
        """
        from src.domain.services.node_registry import Node, NodeType
        from src.domain.services.node_version_manager import NodeVersionManager

        manager = NodeVersionManager()

        node = Node(
            id="node_test",
            type=NodeType.API,
            config={"url": "https://v1.api.com"},
            version=1,
        )

        # 记录多个版本
        for i in range(1, 4):
            node.config["url"] = f"https://v{i}.api.com"
            node.version = i
            manager.record_version(node)

        # 列出版本
        versions = manager.list_versions(node.id)

        assert len(versions) == 3
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2
        assert versions[2]["version"] == 3

    def test_get_specific_version(self):
        """测试：获取指定版本的节点配置"""
        from src.domain.services.node_registry import Node, NodeType
        from src.domain.services.node_version_manager import NodeVersionManager

        manager = NodeVersionManager()

        node = Node(
            id="node_1",
            type=NodeType.LLM,
            config={"user_prompt": "original"},
            version=1,
        )

        manager.record_version(node)

        node.config["user_prompt"] = "modified"
        node.version = 2
        manager.record_version(node)

        # 获取版本 1
        v1 = manager.get_version(node.id, version=1)

        assert v1["config"]["user_prompt"] == "original"


class TestNodeRollback:
    """测试节点回滚"""

    def test_rollback_to_specific_version(self):
        """测试：回滚到指定版本

        调用 API 可回滚到指定版本
        """
        from src.domain.services.node_registry import Node, NodeType
        from src.domain.services.node_version_manager import NodeVersionManager

        manager = NodeVersionManager()

        node = Node(
            id="node_rollback",
            type=NodeType.LLM,
            config={"model": "gpt-3.5", "temperature": 0.5},
            version=1,
        )

        # 记录初始版本
        manager.record_version(node)

        # 修改多次
        node.config["model"] = "gpt-4"
        node.version = 2
        manager.record_version(node)

        node.config["temperature"] = 0.9
        node.version = 3
        manager.record_version(node)

        # 回滚到版本 1（会创建新版本 4，内容与 v1 相同）
        rolled_back = manager.rollback(node.id, target_version=1)

        # 回滚创建了新版本（版本4），配置内容来自版本1
        assert rolled_back["version"] == 4  # 新版本号
        assert rolled_back["rollback_from"] == 1  # 标记来源
        assert rolled_back["config"]["model"] == "gpt-3.5"
        assert rolled_back["config"]["temperature"] == 0.5

    def test_rollback_creates_new_version(self):
        """测试：回滚操作创建新版本

        回滚不是删除历史，而是基于旧版本创建新版本
        """
        from src.domain.services.node_registry import Node, NodeType
        from src.domain.services.node_version_manager import NodeVersionManager

        manager = NodeVersionManager()

        node = Node(
            id="node_rb",
            type=NodeType.CODE,
            config={"code": "print('v1')"},
            version=1,
        )

        manager.record_version(node)

        node.config["code"] = "print('v2')"
        node.version = 2
        manager.record_version(node)

        # 回滚到版本 1（这会创建版本 3）
        manager.rollback(node.id, target_version=1)

        # 应该有 3 个版本
        history = manager.get_version_history(node.id)
        assert len(history) == 3
        assert history[2]["version"] == 3
        assert history[2]["config"]["code"] == "print('v1')"  # 内容与 v1 相同
        assert history[2].get("rollback_from") == 1  # 标记回滚来源

    def test_rollback_to_nonexistent_version_fails(self):
        """测试：回滚到不存在的版本应该失败"""
        from src.domain.services.node_registry import Node, NodeType
        from src.domain.services.node_version_manager import NodeVersionManager

        manager = NodeVersionManager()

        node = Node(id="node_x", type=NodeType.LLM, config={}, version=1)
        manager.record_version(node)

        with pytest.raises(ValueError, match="版本不存在"):
            manager.rollback(node.id, target_version=999)


class TestVersionComparison:
    """测试版本比较"""

    def test_compare_two_versions(self):
        """测试：比较两个版本的差异"""
        from src.domain.services.node_registry import Node, NodeType
        from src.domain.services.node_version_manager import NodeVersionManager

        manager = NodeVersionManager()

        node = Node(
            id="node_cmp",
            type=NodeType.LLM,
            config={"model": "gpt-3.5", "temperature": 0.7, "max_tokens": 100},
            version=1,
        )
        manager.record_version(node)

        node.config["model"] = "gpt-4"
        node.config["temperature"] = 0.9
        node.version = 2
        manager.record_version(node)

        # 比较版本 1 和 2
        diff = manager.compare_versions(node.id, version1=1, version2=2)

        assert "model" in diff["changed"]
        assert diff["changed"]["model"]["old"] == "gpt-3.5"
        assert diff["changed"]["model"]["new"] == "gpt-4"
        assert "temperature" in diff["changed"]
        assert "max_tokens" not in diff["changed"]  # 未改变


class TestRealWorldScenario:
    """真实场景测试"""

    def test_complete_node_lifecycle(self):
        """测试：完整的节点生命周期

        场景：
        1. 用户在工作流中创建草稿节点
        2. 多次修改节点配置
        3. 将节点升级为模板
        4. 在新工作流中实例化模板
        5. 回滚到历史版本

        这是阶段 4 的完整验收场景！
        """
        from src.domain.services.node_registry import (
            NodeFactory,
            NodeRegistry,
            NodeScope,
            NodeType,
            PromotionStatus,
        )
        from src.domain.services.node_template_manager import NodeTemplateManager
        from src.domain.services.node_version_manager import NodeVersionManager

        # 初始化服务
        registry = NodeRegistry()
        factory = NodeFactory(registry)
        template_manager = NodeTemplateManager()
        version_manager = NodeVersionManager()

        # === 步骤 1：创建草稿节点 ===
        node = factory.create(
            NodeType.LLM,
            {"user_prompt": "分析销售数据"},
            node_id="node_sales_analysis",
        )

        assert node.scope == NodeScope.WORKFLOW
        assert node.promotion_status == PromotionStatus.DRAFT
        assert node.version == 1

        # 记录初始版本
        version_manager.record_version(node)

        # === 步骤 2：多次修改节点配置 ===
        # 修改 1
        node.config["model"] = "gpt-4"
        node.version = 2
        version_manager.record_version(node)

        # 修改 2
        node.config["temperature"] = 0.8
        node.config["user_prompt"] = "深入分析销售数据并生成报告"
        node.version = 3
        version_manager.record_version(node)

        # 验证版本历史
        history = version_manager.list_versions(node.id)
        assert len(history) == 3

        # === 步骤 3：升级为模板 ===
        node.promote_to_template(template_name="销售分析模板")

        assert node.scope == NodeScope.TEMPLATE
        assert node.promotion_status == PromotionStatus.PROMOTED

        # 注册到模板管理器
        template_id = template_manager.register_template(
            name="销售分析模板",
            node_type=node.type,
            config=node.config.copy(),
            description="用于销售数据深入分析",
        )

        # === 步骤 4：在新工作流中实例化模板 ===
        new_node = template_manager.instantiate(template_id, workflow_id="wf_q2_report")

        # 新节点验证
        assert new_node.id != node.id
        assert new_node.config["user_prompt"] == "深入分析销售数据并生成报告"
        assert new_node.scope == NodeScope.WORKFLOW  # 回到工作流作用域
        assert new_node.source_template_id == template_id

        # 修改新节点不影响模板
        new_node.config["user_prompt"] = "分析Q2销售数据"
        template = template_manager.get_template(template_id)
        assert template["config"]["user_prompt"] == "深入分析销售数据并生成报告"

        # === 步骤 5：回滚到历史版本 ===
        # 用户想回到版本 2 的配置
        rolled_back = version_manager.rollback(node.id, target_version=2)

        assert rolled_back["config"]["model"] == "gpt-4"
        # v2 有默认的 temperature 0.7（来自模板），v3 改为 0.8
        assert rolled_back["config"]["temperature"] == 0.7  # 回滚到 v2 的值
        assert rolled_back["config"]["user_prompt"] == "分析销售数据"  # v2 的 prompt

        # 回滚创建了新版本
        history = version_manager.list_versions(node.id)
        assert len(history) == 4  # 原来 3 个 + 回滚 1 个
        assert history[3]["rollback_from"] == 2

        print("✅ 验收通过：完整节点生命周期测试成功！")
        print("   - 创建草稿节点: ✓")
        print(f"   - 版本历史 ({len(history)} 个版本): ✓")
        print("   - 升级为模板: ✓")
        print("   - 模板实例化: ✓")
        print("   - 版本回滚: ✓")
