"""测试：节点注册中心 (Node Registry)

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- 节点注册中心管理所有可用的节点类型
- 对话Agent通过注册中心创建节点
- 支持预定义节点和动态注册节点
- 这是 Phase 0 基础设施的核心组件

真实场景：
1. 系统启动时注册所有预定义节点类型
2. 对话Agent决策创建LLM节点 → 从注册中心获取模板
3. 节点工厂根据模板和配置创建节点实例
4. 工作流Agent��行节点
"""

import pytest


class TestNodeTypeRegistration:
    """测试节点类型注册

    业务背景：
    - 系统需要支持多种节点类型
    - 每种节点有自己的配置Schema
    """

    def test_register_node_type_with_schema(self):
        """测试：注册节点类型及其配置Schema

        业务场景：
        - 定义LLM节点类型
        - 指定其配置Schema（model, temperature等）
        - 注册到中心

        验收标准：
        - 可以注册节点类型
        - Schema被正确保存
        """
        # Arrange
        from src.domain.services.node_registry import NodeRegistry, NodeType

        registry = NodeRegistry()

        llm_schema = {
            "type": "object",
            "properties": {
                "model": {"type": "string", "default": "gpt-4"},
                "temperature": {"type": "number", "default": 0.7},
                "max_tokens": {"type": "integer"},
                "system_prompt": {"type": "string"},
                "user_prompt": {"type": "string", "required": True},
            },
            "required": ["user_prompt"],
        }

        # Act
        registry.register(NodeType.LLM, schema=llm_schema)

        # Assert
        assert registry.is_registered(NodeType.LLM)
        schema = registry.get_schema(NodeType.LLM)
        assert schema["properties"]["model"]["default"] == "gpt-4"

    def test_get_all_registered_node_types(self):
        """测试：获取所有已注册的节点类型

        业务场景：
        - 前端需要展示可用的节点类型列表
        - 对话Agent需要知道可以创建哪些节点

        验收标准：
        - 可以获取所有已注册类型的列表
        - Registry初始化时已包含所有预定义类型（13种）
        """
        # Arrange
        from src.domain.services.node_registry import NodeRegistry, NodeType

        registry = NodeRegistry()

        # Act
        types = registry.get_all_types()

        # Assert - Registry初始化时已包含所有预定义类型
        assert NodeType.LLM in types
        assert NodeType.API in types
        assert NodeType.CODE in types
        assert NodeType.START in types
        assert NodeType.END in types
        assert NodeType.CONDITION in types
        assert NodeType.LOOP in types
        assert NodeType.GENERIC in types
        assert len(types) == 13  # 13种预定义类型


class TestPredefinedNodeTypes:
    """测试预定义节点类型

    业务背景：
    - 系统预定义10种核心节点类型
    - 每种类型有默认配置
    """

    def test_all_predefined_node_types_exist(self):
        """测试：所有预定义节点类型都存在

        业务需求：
        - START, END: 基础节点
        - CONDITION, LOOP, PARALLEL: 控制流节点
        - LLM, KNOWLEDGE, CLASSIFY, TEMPLATE: AI能力节点
        - API, CODE, MCP: 执行节点
        - GENERIC: 通用节点

        验收标准：
        - NodeType枚举包含所有预定义类型
        """
        # Arrange & Act
        from src.domain.services.node_registry import NodeType

        # Assert
        expected_types = [
            "START",
            "END",  # 基础
            "CONDITION",
            "LOOP",
            "PARALLEL",  # 控制流
            "LLM",
            "KNOWLEDGE",
            "CLASSIFY",
            "TEMPLATE",  # AI能力
            "API",
            "CODE",
            "MCP",  # 执行
            "GENERIC",  # 通用
        ]

        for type_name in expected_types:
            assert hasattr(NodeType, type_name), f"NodeType should have {type_name}"

    def test_registry_initializes_with_predefined_types(self):
        """测试：注册中心初始化时包含所有预定义类型

        业务场景：
        - 系统启动时，注册中心自动注册所有预定义类型
        - 无需手动注册即可使用

        验收标准：
        - 新创建的Registry已包含所有预定义类型
        """
        # Arrange & Act
        from src.domain.services.node_registry import NodeRegistry, NodeType

        registry = NodeRegistry()

        # Assert - 所有预定义类型都已注册
        assert registry.is_registered(NodeType.START)
        assert registry.is_registered(NodeType.END)
        assert registry.is_registered(NodeType.LLM)
        assert registry.is_registered(NodeType.CONDITION)
        assert registry.is_registered(NodeType.LOOP)
        assert registry.is_registered(NodeType.API)
        assert registry.is_registered(NodeType.CODE)
        assert registry.is_registered(NodeType.GENERIC)


class TestNodeTemplate:
    """测试节点模板

    业务背景：
    - 每种节点类型有默认配置模板
    - 对话Agent基于模板填充具体配置
    """

    def test_get_node_template_with_defaults(self):
        """测试：获取节点模板包含默认值

        业务场景：
        - 对话Agent决策创建LLM节点
        - 获取LLM模板，包含默认的model和temperature
        - 只需填写必要的user_prompt

        验收标准：
        - 模板包含所有字段的默认值
        - 可以基于模板创建配置
        """
        # Arrange
        from src.domain.services.node_registry import NodeRegistry, NodeType

        registry = NodeRegistry()

        # Act
        template = registry.get_template(NodeType.LLM)

        # Assert
        assert template is not None
        assert "model" in template
        assert "temperature" in template
        assert template["model"] == "gpt-4"  # 默认值
        assert template["temperature"] == 0.7  # 默认值

    def test_get_template_for_condition_node(self):
        """测试：获取条件节点模板

        业务场景：
        - 对话Agent需要创建条件分支
        - 条件节点有expression或llm_judge两种模式

        验收标准：
        - 条件节点模板包含condition_type
        - 包含branches字段
        """
        # Arrange
        from src.domain.services.node_registry import NodeRegistry, NodeType

        registry = NodeRegistry()

        # Act
        template = registry.get_template(NodeType.CONDITION)

        # Assert
        assert "condition_type" in template
        assert "branches" in template

    def test_get_template_for_loop_node(self):
        """测试：获取循环节点模板

        业务场景：
        - 对话Agent需要创建循环处理
        - 支持for_each, while, count三种模式

        验收标准：
        - 循环节点模板包含loop_type
        - 包含max_iterations安全限制
        """
        # Arrange
        from src.domain.services.node_registry import NodeRegistry, NodeType

        registry = NodeRegistry()

        # Act
        template = registry.get_template(NodeType.LOOP)

        # Assert
        assert "loop_type" in template
        assert "max_iterations" in template
        assert template["max_iterations"] == 100  # 安全限制


class TestNodeSchemaValidation:
    """测试节点配置Schema验证

    业务背景：
    - 对话Agent填写的配置需要验证
    - 确保配置符合节点类型的要求
    """

    def test_validate_valid_llm_config(self):
        """测试：验证有效的LLM节点配置

        业务场景：
        - 对话Agent填写了LLM节点配置
        - 配置包含必需的user_prompt
        - 验证通过

        验收标准：
        - 有效配置验证通过
        - 返回True或无异常
        """
        # Arrange
        from src.domain.services.node_registry import NodeRegistry, NodeType

        registry = NodeRegistry()
        config = {"model": "gpt-4", "temperature": 0.8, "user_prompt": "分析这段数据"}

        # Act
        is_valid, errors = registry.validate_config(NodeType.LLM, config)

        # Assert
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_invalid_config_missing_required(self):
        """测试：验证缺少必需字段的配置

        业务场景：
        - 对话Agent漏填了必需的user_prompt
        - 验证失败，返回错误信息

        验收标准：
        - 缺少必需字段时验证失败
        - 返回明确的错误信息
        """
        # Arrange
        from src.domain.services.node_registry import NodeRegistry, NodeType

        registry = NodeRegistry()
        config = {
            "model": "gpt-4",
            "temperature": 0.8,
            # 缺少 user_prompt
        }

        # Act
        is_valid, errors = registry.validate_config(NodeType.LLM, config)

        # Assert
        assert is_valid is False
        assert len(errors) > 0
        assert any("user_prompt" in str(e) for e in errors)

    def test_validate_invalid_config_wrong_type(self):
        """测试：验证字段类型错误的配置

        业务场景：
        - temperature应该是数字，但传入了字符串
        - 验证失败

        验收标准：
        - 类型错误时验证失败
        - 返回类型错误信息
        """
        # Arrange
        from src.domain.services.node_registry import NodeRegistry, NodeType

        registry = NodeRegistry()
        config = {
            "model": "gpt-4",
            "temperature": "very hot",  # 应该是数字
            "user_prompt": "test",
        }

        # Act
        is_valid, errors = registry.validate_config(NodeType.LLM, config)

        # Assert
        assert is_valid is False
        assert any("temperature" in str(e) for e in errors)


class TestNodeFactory:
    """测试节点工厂

    业务背景：
    - 对话Agent决策后，需要创建具体的节点实例
    - 节点工厂根据类型和配置创建节点
    """

    def test_create_node_from_type_and_config(self):
        """测试：根据类型和配置创建节点

        业务场景：
        - 对话Agent决策创建一个LLM节点
        - 提供节点类型和配置
        - 创建节点实例

        验收标准：
        - 可以创建节点实例
        - 节点有唯一ID
        - 节点类型正确
        - 配置被正确应用
        """
        # Arrange
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        config = {"model": "gpt-4", "temperature": 0.8, "user_prompt": "分析销售数据"}

        # Act
        node = factory.create(NodeType.LLM, config)

        # Assert
        assert node is not None
        assert node.id is not None
        assert node.type == NodeType.LLM
        assert node.config["model"] == "gpt-4"
        assert node.config["user_prompt"] == "分析销售数据"

    def test_create_node_with_default_values(self):
        """测试：创建节点时使用默认值

        业务场景：
        - 对话Agent只提供必需的配置
        - 其他字段使用默认值

        验收标准：
        - 未提供的字段使用默认值
        - 提供的字段覆盖默认值
        """
        # Arrange
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 只提供必需字段
        config = {"user_prompt": "测试提示词"}

        # Act
        node = factory.create(NodeType.LLM, config)

        # Assert
        assert node.config["model"] == "gpt-4"  # 默认值
        assert node.config["temperature"] == 0.7  # 默认值
        assert node.config["user_prompt"] == "测试提示词"  # 提供的值

    def test_create_node_fails_with_invalid_config(self):
        """测试：配置无效时创建失败

        业务场景：
        - 对话Agent提供了无效配置
        - 工厂验证失败，抛出异常

        验收标准：
        - 无效配置抛出异常
        - 异常包含验证错误信息
        """
        # Arrange
        from src.domain.services.node_registry import (
            NodeConfigError,
            NodeFactory,
            NodeRegistry,
            NodeType,
        )

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 缺少必需字段
        config = {
            "model": "gpt-4"
            # 缺少 user_prompt
        }

        # Act & Assert
        with pytest.raises(NodeConfigError) as exc_info:
            factory.create(NodeType.LLM, config)

        assert "user_prompt" in str(exc_info.value)


class TestNodeLifecycle:
    """测试节点生命周期

    业务背景：
    - 节点有生命周期：temporary → persisted → template → global
    - 对话Agent创建的节点默认是temporary
    """

    def test_node_created_with_temporary_lifecycle(self):
        """测试：创建的节点默认是temporary生命周期

        业务场景：
        - 对话Agent临时创建节点用于当前任务
        - 默认不持久化

        验收标准：
        - 新创建的节点lifecycle是temporary
        """
        # Arrange
        from src.domain.services.node_registry import (
            NodeFactory,
            NodeLifecycle,
            NodeRegistry,
            NodeType,
        )

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # Act
        node = factory.create(NodeType.LLM, {"user_prompt": "test"})

        # Assert
        assert node.lifecycle == NodeLifecycle.TEMPORARY

    def test_promote_node_lifecycle(self):
        """测试：提升节点生命周期

        业务场景：
        - 用户想保存一个临时节点
        - 从temporary提升到persisted

        验收标准：
        - 可以提升生命周期
        - 遵循有效的转换路径
        """
        # Arrange
        from src.domain.services.node_registry import (
            NodeFactory,
            NodeLifecycle,
            NodeRegistry,
            NodeType,
        )

        registry = NodeRegistry()
        factory = NodeFactory(registry)
        node = factory.create(NodeType.LLM, {"user_prompt": "test"})

        # Act
        node.promote(NodeLifecycle.PERSISTED)

        # Assert
        assert node.lifecycle == NodeLifecycle.PERSISTED

    def test_invalid_lifecycle_promotion_fails(self):
        """测试：无效的生命周期提升失败

        业务场景：
        - 尝试从temporary直接跳到global
        - 这是不允许的

        验收标准：
        - 无效转换抛出异常
        """
        # Arrange
        from src.domain.services.node_registry import (
            NodeFactory,
            NodeLifecycle,
            NodeRegistry,
            NodeType,
        )

        registry = NodeRegistry()
        factory = NodeFactory(registry)
        node = factory.create(NodeType.LLM, {"user_prompt": "test"})

        # Act & Assert - temporary不能直接到global
        with pytest.raises(ValueError):
            node.promote(NodeLifecycle.GLOBAL)


class TestGenericNode:
    """测试通用节点

    业务背景：
    - 通用节点可以包含子工作流
    - 支持展开/折叠
    """

    def test_create_generic_node_with_children(self):
        """测试：创建包含子节点的通用节点

        业务场景：
        - 对话Agent创建一个复杂任务
        - 封装为通用节点，包含多个子节点

        验收标准：
        - 可以创建GENERIC类型节点
        - 可以添加子节点
        """
        # Arrange
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        # 创建子节点
        child1 = factory.create(NodeType.LLM, {"user_prompt": "step 1"})
        child2 = factory.create(NodeType.API, {"url": "https://api.example.com"})

        # Act - 创建通用节点
        generic_config = {"name": "数据处理流程", "description": "包含LLM分析和API调用"}
        generic_node = factory.create(NodeType.GENERIC, generic_config)
        generic_node.add_child(child1)
        generic_node.add_child(child2)

        # Assert
        assert generic_node.type == NodeType.GENERIC
        assert len(generic_node.children) == 2
        assert generic_node.children[0].type == NodeType.LLM

    def test_generic_node_expand_collapse(self):
        """测试：通用节点展开和折叠

        业务场景：
        - 用户在画布上查看通用节点
        - 可以展开查看内部结构
        - 可以折叠简化视图

        验收标准：
        - 默认是折叠状态
        - 可以展开和折叠
        """
        # Arrange
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        registry = NodeRegistry()
        factory = NodeFactory(registry)

        generic_node = factory.create(NodeType.GENERIC, {"name": "test"})

        # Assert - 默认折叠
        assert generic_node.collapsed is True

        # Act - 展开
        generic_node.expand()
        assert generic_node.collapsed is False

        # Act - 折叠
        generic_node.collapse()
        assert generic_node.collapsed is True


class TestRealWorldScenario:
    """测试真实业务场景"""

    def test_conversation_agent_creates_workflow_nodes(self):
        """测试：对话Agent创建工作流节点的完整流程

        业务场景：
        1. 对话Agent决策创建一个数据分析工作流
        2. 包含：API获取数据 → LLM分析 → 条件判断 → 输出结果
        3. 所有节点从注册中心创建

        这是对话Agent与节点系统交互的核心流程！

        验收标准：
        - 可以创建完整的工作流节点序列
        - 每个节点配置正确
        - 节点间可以连接
        """
        # Arrange
        from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType

        registry = NodeRegistry()
        factory = NodeFactory(registry)
        created_nodes = []

        # Act - 模拟对话Agent的决策序列

        # 1. 创建开始节点
        start_node = factory.create(NodeType.START, {"trigger_type": "manual"})
        created_nodes.append(start_node)

        # 2. 创建API节点获取数据
        api_node = factory.create(
            NodeType.API, {"method": "GET", "url": "https://api.example.com/sales"}
        )
        created_nodes.append(api_node)

        # 3. 创建LLM节点分析数据
        llm_node = factory.create(
            NodeType.LLM, {"model": "gpt-4", "user_prompt": "分析以下销售数据：{{api_result}}"}
        )
        created_nodes.append(llm_node)

        # 4. 创建条件节点判断结果
        condition_node = factory.create(
            NodeType.CONDITION,
            {
                "condition_type": "expression",
                "expression": "{{analysis.sentiment}} == 'positive'",
                "branches": [
                    {"name": "positive", "target": "end"},
                    {"name": "negative", "target": "alert"},
                ],
            },
        )
        created_nodes.append(condition_node)

        # 5. 创建结束节点
        end_node = factory.create(NodeType.END, {})
        created_nodes.append(end_node)

        # Assert
        assert len(created_nodes) == 5
        assert created_nodes[0].type == NodeType.START
        assert created_nodes[1].type == NodeType.API
        assert created_nodes[2].type == NodeType.LLM
        assert created_nodes[3].type == NodeType.CONDITION
        assert created_nodes[4].type == NodeType.END

        # 所有节点都有唯一ID
        ids = [n.id for n in created_nodes]
        assert len(ids) == len(set(ids)), "所有节点ID应该唯一"

        # LLM节点配置正确
        assert created_nodes[2].config["model"] == "gpt-4"
