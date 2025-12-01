"""测试：通用节点（GenericNode）

TDD 第一步：编写测试用例，明确需求和验收标准

业务背景：
- 用户创建复杂工作流时，常见模式可以封装成"通用节点"
- 通用节点相当于一个"子工作流"，可以包含多个内部节点
- 支持展开查看细节，折叠后简洁展示
- 可以保存为模板，在其他工作流中复用

真实场景举例：
1. "数据处理单元"：包含 API获取 → 数据清洗 → 格式转换
2. "智能回复单元"：包含 RAG检索 → LLM分析 → 回复生成
3. "审批流单元"：包含 条件判断 → 通知发送 → 状态更新

核心能力：
- 子节点管理：添加、移除、排序内部节点
- 展开/折叠：切换显示模式
- 输入输出映射：定义通用节点的对外接口
- 执行代理：执行时按内部拓扑顺序执行子节点
- 生命周期：临时 → 持久化 → 模板

"""

from unittest.mock import AsyncMock

import pytest


class TestGenericNodeCreation:
    """测试通用节点创建

    业务背景：
    - 用户选中多个节点后，点击"封装为通用节点"
    - 系统创建一个新的GenericNode，包含选中的节点
    """

    def test_create_empty_generic_node(self):
        """测试：创建空的通用节点

        业务场景：
        - 用户创建一个空的通用节点容器
        - 准备向其中添加子节点

        验收标准：
        - 节点正确创建
        - 类型为GENERIC
        - 初始状态为折叠
        """
        from src.domain.services.generic_node import GenericNode, NodeLifecycle

        node = GenericNode(
            id="generic_1", name="数据处理单元", description="包含数据获取和处理的标准流程"
        )

        assert node.id == "generic_1"
        assert node.name == "数据处理单元"
        assert node.is_collapsed is True  # 默认折叠
        assert len(node.children) == 0
        assert node.lifecycle == NodeLifecycle.TEMPORARY

    def test_create_generic_node_with_children(self):
        """测试：创建带子节点的通用节点

        业务场景：
        - 用户选中3个节点：API节点、代码节点、LLM节点
        - 封装为"智能分析单元"

        验收标准：
        - 通用节点包含所有子节点
        - 子节点顺序正确
        """
        from src.domain.services.generic_node import ChildNode, GenericNode, NodeType

        # 创建子节点
        child_1 = ChildNode(
            id="api_1", type=NodeType.API, config={"url": "https://api.example.com"}
        )
        child_2 = ChildNode(id="code_1", type=NodeType.CODE, config={"language": "python"})
        child_3 = ChildNode(id="llm_1", type=NodeType.LLM, config={"model": "gpt-4"})

        # 创建通用节点
        generic = GenericNode(
            id="generic_1", name="智能分析单元", children=[child_1, child_2, child_3]
        )

        assert len(generic.children) == 3
        assert generic.children[0].id == "api_1"
        assert generic.children[1].id == "code_1"
        assert generic.children[2].id == "llm_1"


class TestGenericNodeExpandCollapse:
    """测试展开/折叠功能

    业务背景：
    - 折叠状态：画布上显示为单个节点，简洁清晰
    - 展开状态：显示内部结构，可以查看和编辑子节点
    """

    def test_expand_generic_node(self):
        """测试：展开通用节点

        业务场景：
        - 用户双击通用节点
        - 节点展开，显示内部的3个子节点

        验收标准：
        - is_collapsed 变为 False
        - 可以访问子节点列表
        """
        from src.domain.services.generic_node import ChildNode, GenericNode, NodeType

        child = ChildNode(id="llm_1", type=NodeType.LLM, config={})
        generic = GenericNode(id="g1", name="测试", children=[child])

        assert generic.is_collapsed is True

        generic.expand()

        assert generic.is_collapsed is False

    def test_collapse_generic_node(self):
        """测试：折叠通用节点

        业务场景：
        - 用户完成编辑后，点击折叠按钮
        - 节点收缩为单个图标

        验收标准：
        - is_collapsed 变为 True
        - 子节点仍然保留
        """
        from src.domain.services.generic_node import ChildNode, GenericNode, NodeType

        child = ChildNode(id="llm_1", type=NodeType.LLM, config={})
        generic = GenericNode(id="g1", name="测试", children=[child])
        generic.expand()

        generic.collapse()

        assert generic.is_collapsed is True
        assert len(generic.children) == 1  # 子节点仍在

    def test_to_canvas_data_collapsed(self):
        """测试：折叠状态的画布数据

        业务场景：
        - 前端请求画布数据
        - 折叠的通用节点只返回摘要信息

        验收标准：
        - 返回数据包含节点ID、名称、子节点数量
        - 不包含子节点详细数据
        """
        from src.domain.services.generic_node import ChildNode, GenericNode, NodeType

        children = [ChildNode(id=f"child_{i}", type=NodeType.LLM, config={}) for i in range(3)]
        generic = GenericNode(id="g1", name="数据处理", children=children)

        canvas_data = generic.to_canvas_data()

        assert canvas_data["id"] == "g1"
        assert canvas_data["type"] == "generic"
        assert canvas_data["data"]["collapsed"] is True
        assert canvas_data["data"]["childCount"] == 3
        assert "children" not in canvas_data["data"]

    def test_to_canvas_data_expanded(self):
        """测试：展开状态的画布数据

        业务场景：
        - 用户展开通用节点查看详情
        - 前端需要子节点数据来渲染

        验收标准：
        - 返回数据包含完整的子节点列表
        """
        from src.domain.services.generic_node import ChildNode, GenericNode, NodeType

        children = [
            ChildNode(id="api_1", type=NodeType.API, config={"url": "test"}),
            ChildNode(id="llm_1", type=NodeType.LLM, config={"model": "gpt-4"}),
        ]
        generic = GenericNode(id="g1", name="处理单元", children=children)
        generic.expand()

        canvas_data = generic.to_canvas_data()

        assert canvas_data["data"]["collapsed"] is False
        assert "children" in canvas_data["data"]
        assert len(canvas_data["data"]["children"]) == 2


class TestChildNodeManagement:
    """测试子节点管理

    业务背景：
    - 用户可以向通用节点添加/移除子节点
    - 可以调整子节点顺序
    """

    def test_add_child_node(self):
        """测试：添加子节点

        业务场景：
        - 用户拖拽一个LLM节点到通用节点内部
        - 节点被添加到子节点列表末尾

        验收标准：
        - 子节点被添加
        - 添加到列表末尾
        """
        from src.domain.services.generic_node import ChildNode, GenericNode, NodeType

        generic = GenericNode(id="g1", name="测试")

        child = ChildNode(id="llm_1", type=NodeType.LLM, config={"model": "gpt-4"})
        generic.add_child(child)

        assert len(generic.children) == 1
        assert generic.children[0].id == "llm_1"

    def test_remove_child_node(self):
        """测试：移除子节点

        业务场景：
        - 用户将子节点拖出通用节点
        - 子节点从列表中移除

        验收标准：
        - 指定子节点被移除
        - 其他子节点不受影响
        """
        from src.domain.services.generic_node import ChildNode, GenericNode, NodeType

        children = [
            ChildNode(id="c1", type=NodeType.API, config={}),
            ChildNode(id="c2", type=NodeType.LLM, config={}),
            ChildNode(id="c3", type=NodeType.CODE, config={}),
        ]
        generic = GenericNode(id="g1", name="测试", children=children)

        generic.remove_child("c2")

        assert len(generic.children) == 2
        assert all(c.id != "c2" for c in generic.children)

    def test_reorder_children(self):
        """测试：调整子节点顺序

        业务场景：
        - 用户拖动子节点调整执行顺序
        - 从 [A, B, C] 变为 [B, A, C]

        验收标准：
        - 子节点顺序正确调整
        """
        from src.domain.services.generic_node import ChildNode, GenericNode, NodeType

        children = [
            ChildNode(id="A", type=NodeType.API, config={}),
            ChildNode(id="B", type=NodeType.LLM, config={}),
            ChildNode(id="C", type=NodeType.CODE, config={}),
        ]
        generic = GenericNode(id="g1", name="测试", children=children)

        generic.reorder_children(["B", "A", "C"])

        assert generic.children[0].id == "B"
        assert generic.children[1].id == "A"
        assert generic.children[2].id == "C"


class TestInputOutputMapping:
    """测试输入输出映射

    业务背景：
    - 通用节点对外暴露统一接口
    - 内部子节点的输入输出被映射到通用节点接口
    """

    def test_define_input_mapping(self):
        """测试：定义输入映射

        业务场景：
        - 通用节点接收 "query" 输入
        - 映射到内部RAG节点的 "search_query" 字段

        验收标准：
        - 输入映射正确定义
        """
        from src.domain.services.generic_node import GenericNode

        generic = GenericNode(id="g1", name="智能检索单元")

        generic.set_input_mapping({"query": "rag_node.search_query", "top_k": "rag_node.top_k"})

        mapping = generic.get_input_mapping()
        assert mapping["query"] == "rag_node.search_query"
        assert mapping["top_k"] == "rag_node.top_k"

    def test_define_output_mapping(self):
        """测试：定义输出映射

        业务场景：
        - 内部LLM节点输出 "response"
        - 映射为通用节点的 "result" 输出

        验收标准：
        - 输出映射正确定义
        """
        from src.domain.services.generic_node import GenericNode

        generic = GenericNode(id="g1", name="智能分析单元")

        generic.set_output_mapping(
            {"result": "llm_node.response", "confidence": "llm_node.confidence"}
        )

        mapping = generic.get_output_mapping()
        assert mapping["result"] == "llm_node.response"


class TestGenericNodeExecution:
    """测试通用节点执行

    业务背景：
    - 工作流执行到通用节点时
    - 按内部拓扑顺序执行子节点
    - 汇总结果作为通用节点输出
    """

    @pytest.mark.asyncio
    async def test_execute_generic_node_sequentially(self):
        """测试：顺序执行子节点

        业务场景：
        - 通用节点包含：API → 代码处理 → LLM分析
        - 执行时按顺序调用每个子节点
        - 前一个节点的输出作为后一个的输入

        验收标准：
        - 所有子节点按顺序执行
        - 输出正确传递
        - 最终结果正确返回
        """
        from src.domain.services.generic_node import (
            ChildNode,
            GenericNode,
            GenericNodeExecutor,
            NodeType,
        )

        # 创建子节点
        api_node = ChildNode(
            id="api_1", type=NodeType.API, config={"url": "https://api.example.com/data"}
        )
        code_node = ChildNode(
            id="code_1",
            type=NodeType.CODE,
            config={"code": "data = input['data']; result = len(data)"},
        )
        llm_node = ChildNode(
            id="llm_1", type=NodeType.LLM, config={"user_prompt": "分析数据数量: {{count}}"}
        )

        generic = GenericNode(
            id="g1", name="数据分析单元", children=[api_node, code_node, llm_node]
        )

        # 模拟节点执行器
        mock_executor = AsyncMock()
        execution_order = []

        async def mock_execute(node_id, config, inputs):
            execution_order.append(node_id)
            if node_id == "api_1":
                return {"data": [1, 2, 3, 4, 5]}
            elif node_id == "code_1":
                return {"count": 5}
            elif node_id == "llm_1":
                return {"analysis": "数据量为5条，属于小规模数据集"}

        mock_executor.execute.side_effect = mock_execute

        # 执行通用节点
        executor = GenericNodeExecutor(node_executor=mock_executor)
        result = await executor.execute(generic, inputs={})

        # 验证执行顺序
        assert execution_order == ["api_1", "code_1", "llm_1"]

        # 验证最终输出
        assert "analysis" in result

    @pytest.mark.asyncio
    async def test_execute_with_input_mapping(self):
        """测试：带输入映射的执行

        业务场景：
        - 通用节点接收外部 "user_query"
        - 映射到内部RAG节点的 "query" 字段
        - 执行RAG检索

        验收标准：
        - 输入正确映射到子节点
        """
        from src.domain.services.generic_node import (
            ChildNode,
            GenericNode,
            GenericNodeExecutor,
            NodeType,
        )

        rag_node = ChildNode(
            id="rag_1", type=NodeType.KNOWLEDGE, config={"knowledge_base_id": "kb_001"}
        )

        generic = GenericNode(id="g1", name="检索单元", children=[rag_node])
        generic.set_input_mapping({"user_query": "rag_1.query"})

        mock_executor = AsyncMock()
        received_inputs = {}

        async def capture_inputs(node_id, config, inputs):
            received_inputs[node_id] = inputs
            return {"results": ["doc1", "doc2"]}

        mock_executor.execute.side_effect = capture_inputs

        executor = GenericNodeExecutor(node_executor=mock_executor)
        await executor.execute(generic, inputs={"user_query": "什么是机器学习？"})

        # 验证输入映射
        assert received_inputs["rag_1"]["query"] == "什么是机器学习？"

    @pytest.mark.asyncio
    async def test_execute_with_output_mapping(self):
        """测试：带输出映射的执行

        业务场景：
        - 内部LLM节点输出 {"response": "...", "tokens": 100}
        - 通用节点只暴露 "answer" (映射自 response)

        验收标准：
        - 输出正确映射
        """
        from src.domain.services.generic_node import (
            ChildNode,
            GenericNode,
            GenericNodeExecutor,
            NodeType,
        )

        llm_node = ChildNode(id="llm_1", type=NodeType.LLM, config={"model": "gpt-4"})

        generic = GenericNode(id="g1", name="回复单元", children=[llm_node])
        generic.set_output_mapping({"answer": "llm_1.response"})

        mock_executor = AsyncMock()
        mock_executor.execute.return_value = {"response": "机器学习是一种AI技术", "tokens": 150}

        executor = GenericNodeExecutor(node_executor=mock_executor)
        result = await executor.execute(generic, inputs={})

        # 验证输出映射
        assert result["answer"] == "机器学习是一种AI技术"
        assert "tokens" not in result  # 未映射的字段不暴露


class TestNodeLifecycle:
    """测试节点生命周期

    业务背景：
    - TEMPORARY: 仅当前会话有效，关闭后消失
    - PERSISTED: 保存到当前工作流
    - TEMPLATE: 用户级模板，可在其他工作流复用
    - GLOBAL: 系统级模板，所有用户可用
    """

    def test_default_lifecycle_is_temporary(self):
        """测试：默认生命周期为临时"""
        from src.domain.services.generic_node import GenericNode, NodeLifecycle

        node = GenericNode(id="g1", name="测试")

        assert node.lifecycle == NodeLifecycle.TEMPORARY

    def test_promote_to_persisted(self):
        """测试：提升为持久化

        业务场景：
        - 用户点击"保存到工作流"
        - 节点生命周期变为 PERSISTED

        验收标准：
        - 生命周期正确转换
        """
        from src.domain.services.generic_node import GenericNode, NodeLifecycle

        node = GenericNode(id="g1", name="测试")

        node.promote(NodeLifecycle.PERSISTED)

        assert node.lifecycle == NodeLifecycle.PERSISTED

    def test_promote_to_template(self):
        """测试：提升为模板

        业务场景：
        - 用户点击"保存为模板"
        - 节点可以在其他工作流中复用

        验收标准：
        - 必须先是PERSISTED才能提升为TEMPLATE
        """
        from src.domain.services.generic_node import GenericNode, NodeLifecycle

        node = GenericNode(id="g1", name="可复用单元")
        node.promote(NodeLifecycle.PERSISTED)

        node.promote(NodeLifecycle.TEMPLATE)

        assert node.lifecycle == NodeLifecycle.TEMPLATE

    def test_invalid_lifecycle_transition(self):
        """测试：无效的生命周期转换

        业务场景：
        - 临时节点不能直接变成模板（跳过PERSISTED）

        验收标准：
        - 抛出异常
        """
        from src.domain.services.generic_node import GenericNode, NodeLifecycle

        node = GenericNode(id="g1", name="测试")

        with pytest.raises(ValueError, match="无效的生命周期转换"):
            node.promote(NodeLifecycle.TEMPLATE)  # TEMPORARY -> TEMPLATE 无效


class TestRealWorldScenario:
    """测试真实业务场景"""

    @pytest.mark.asyncio
    async def test_create_reusable_data_pipeline(self):
        """测试：创建可复用的数据处理管道

        真实业务场景：
        1. 用户经常需要：获取API数据 → 清洗 → 存储
        2. 封装为"数据管道"通用节点
        3. 保存为模板
        4. 在新工作流中复用

        验收标准：
        - 通用节点正确创建
        - 子节点按顺序执行
        - 可以保存为模板
        - 可以在其他工作流实例化
        """
        from src.domain.services.generic_node import (
            ChildNode,
            GenericNode,
            GenericNodeExecutor,
            NodeLifecycle,
            NodeType,
        )

        # Step 1: 创建数据管道通用节点
        api_node = ChildNode(
            id="fetch", type=NodeType.API, config={"url": "{{api_url}}", "method": "GET"}
        )
        transform_node = ChildNode(
            id="transform",
            type=NodeType.CODE,
            config={"code": "result = [x['value'] for x in data]"},
        )
        store_node = ChildNode(
            id="store", type=NodeType.CODE, config={"code": "database.save(result)"}
        )

        pipeline = GenericNode(
            id="data_pipeline_1",
            name="标准数据管道",
            description="获取API数据 → 转换 → 存储",
            children=[api_node, transform_node, store_node],
        )

        # 定义输入输出接口
        pipeline.set_input_mapping(
            {"api_url": "fetch.url", "auth_token": "fetch.headers.Authorization"}
        )
        pipeline.set_output_mapping({"processed_count": "store.count", "status": "store.status"})

        # Step 2: 验证初始状态
        assert pipeline.lifecycle == NodeLifecycle.TEMPORARY
        assert len(pipeline.children) == 3

        # Step 3: 保存到工作流
        pipeline.promote(NodeLifecycle.PERSISTED)
        assert pipeline.lifecycle == NodeLifecycle.PERSISTED

        # Step 4: 保存为模板
        pipeline.promote(NodeLifecycle.TEMPLATE)
        assert pipeline.lifecycle == NodeLifecycle.TEMPLATE

        # Step 5: 从模板创建实例
        instance = pipeline.create_instance(
            new_id="pipeline_instance_1", workflow_id="workflow_xyz"
        )

        assert instance.id == "pipeline_instance_1"
        assert instance.lifecycle == NodeLifecycle.TEMPORARY  # 实例从临时开始
        assert len(instance.children) == 3  # 复制了所有子节点

        # Step 6: 执行实例
        mock_executor = AsyncMock()
        # 注意：实例化后子节点ID带有前缀 "pipeline_instance_1_"
        execution_results = {
            "pipeline_instance_1_fetch": {"data": [{"value": 1}, {"value": 2}]},
            "pipeline_instance_1_transform": {"result": [1, 2]},
            "pipeline_instance_1_store": {"count": 2, "status": "success"},
        }

        async def mock_execute(node_id, config, inputs):
            return execution_results.get(node_id, {})

        mock_executor.execute.side_effect = mock_execute

        executor = GenericNodeExecutor(node_executor=mock_executor)
        result = await executor.execute(
            instance, inputs={"api_url": "https://api.example.com/data"}
        )

        # 验证输出映射
        assert result["processed_count"] == 2
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_nested_generic_nodes(self):
        """测试：嵌套通用节点

        真实业务场景：
        - "完整审批流程" 包含：
          - "申请处理单元"（通用节点）
          - "审批判断单元"（通用节点）
          - "通知发送单元"（通用节点）

        验收标准：
        - 支持通用节点嵌套
        - 执行时递归执行内部通用节点
        """
        from src.domain.services.generic_node import (
            ChildNode,
            GenericNode,
            NodeType,
        )

        # 创建内部通用节点1：申请处理
        apply_llm = ChildNode(id="parse_llm", type=NodeType.LLM, config={})
        apply_unit = GenericNode(id="apply_unit", name="申请处理单元", children=[apply_llm])

        # 创建内部通用节点2：审批判断
        judge_condition = ChildNode(id="judge", type=NodeType.CONDITION, config={})
        judge_unit = GenericNode(id="judge_unit", name="审批判断单元", children=[judge_condition])

        # 创建外层通用节点：完整审批流程
        approval_flow = GenericNode(
            id="approval_flow",
            name="完整审批流程",
            children=[],  # 通用节点也可以作为子节点
        )
        approval_flow.add_generic_child(apply_unit)
        approval_flow.add_generic_child(judge_unit)

        # 验证结构
        assert len(approval_flow.generic_children) == 2
        assert approval_flow.generic_children[0].name == "申请处理单元"

        # 获取画布数据（展开状态）
        approval_flow.expand()
        canvas_data = approval_flow.to_canvas_data()

        assert "genericChildren" in canvas_data["data"]
        assert len(canvas_data["data"]["genericChildren"]) == 2
