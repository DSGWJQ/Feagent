"""WorkflowAgent 集合操作测试 (Loop/Map/Filter)

业务场景：
- Loop节点：遍历集合，对每个元素执行子工作流
- Map节点：转换集合元素，映射为新集合
- Filter节点：过滤集合元素，保留满足条件的元素
- 结果聚合：将所有子执行结果汇总为统一输出

测试策略：
- 测试Loop节点遍历列表执行子节点
- 测试Map节点转换每个元素
- 测试Filter节点过滤元素
- 测试嵌套集合操作（Loop中嵌套Filter）
- 测试结果聚合机制
- 测试边界情况（空集合、单元素集合）
"""

import pytest

from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.services.context_manager import WorkflowContext
from src.domain.services.event_bus import EventBus
from src.domain.services.node_registry import NodeFactory, NodeType


class MockNodeExecutor:
    """模拟节点执行器

    支持集合操作节点的执行模拟。
    """

    def __init__(self):
        self.executed_nodes = []
        self.node_outputs = {}
        self.execution_count = {}  # 跟踪每个节点被执行的次数

    def set_node_output(self, node_id: str, output: dict):
        """设置节点的输出"""
        self.node_outputs[node_id] = output

    async def execute(self, node_id: str, config: dict, inputs: dict):
        """执行节点"""
        self.executed_nodes.append(node_id)

        # 跟踪执行次数
        self.execution_count[node_id] = self.execution_count.get(node_id, 0) + 1

        # 如果有预设输出，返回预设输出
        if node_id in self.node_outputs:
            output = self.node_outputs[node_id]
            # 如果输出是函数，调用函数生成输出（支持动态输出）
            if callable(output):
                return output(inputs)
            return output

        # 默认输出
        return {"status": "success", "executed": True}


class TestLoopNodeExecution:
    """Loop节点执行测试"""

    def setup_method(self):
        """测试前设置"""
        from src.domain.services.context_manager import GlobalContext, SessionContext
        from src.domain.services.node_registry import NodeRegistry

        self.event_bus = EventBus()

        # 创建上下文层次结构
        self.global_context = GlobalContext(user_id="test_user")
        self.session_context = SessionContext(
            session_id="test_session", global_context=self.global_context
        )
        self.workflow_context = WorkflowContext(
            workflow_id="test_wf", session_context=self.session_context
        )

        # 创建NodeFactory和Executor
        self.node_registry = NodeRegistry()
        self.node_factory = NodeFactory(self.node_registry)
        self.node_executor = MockNodeExecutor()

        self.agent = WorkflowAgent(
            workflow_context=self.workflow_context,
            node_factory=self.node_factory,
            node_executor=self.node_executor,
            event_bus=self.event_bus,
        )

    # ==================== Loop节点基础测试 ====================

    @pytest.mark.asyncio
    async def test_loop_node_iterates_over_collection(self):
        """测试Loop节点遍历集合

        场景：
        node_source (collection=[1,2,3]) -> loop_node -> node_process
        预期：node_process被执行3次，每次处理一个元素
        """
        # 创建节点
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        loop_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "for_each",
                "collection_field": "items",  # 从输入中提取items字段作为集合
            },
        )
        node_process = self.node_factory.create(NodeType.GENERIC, {"name": "process"})

        self.agent.add_node(node_source)
        self.agent.add_node(loop_node)
        self.agent.add_node(node_process)

        # 设置source节点输出（包含集合）
        self.node_executor.set_node_output(node_source.id, {"items": [1, 2, 3]})

        # 连接节点
        self.agent.connect_nodes(node_source.id, loop_node.id)
        self.agent.connect_nodes(loop_node.id, node_process.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：node_process应该被执行3次
        assert self.node_executor.execution_count.get(node_process.id, 0) == 3
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_loop_node_passes_current_item_to_child(self):
        """测试Loop节点将当前元素传递给子节点

        场景：Loop节点遍历集合时，应将当前元素作为输入传递给子节点
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        loop_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "for_each",
                "collection_field": "items",
                "item_variable": "current_item",  # 当前元素的变量名
            },
        )
        node_process = self.node_factory.create(NodeType.GENERIC, {"name": "process"})

        self.agent.add_node(node_source)
        self.agent.add_node(loop_node)
        self.agent.add_node(node_process)

        # 设置source输出
        self.node_executor.set_node_output(node_source.id, {"items": [10, 20, 30]})

        # 设置process节点，记录接收到的输入
        received_inputs = []

        def process_fn(inputs):
            received_inputs.append(inputs.get("current_item"))
            return {"status": "success"}

        self.node_executor.set_node_output(node_process.id, process_fn)

        # 连接节点
        self.agent.connect_nodes(node_source.id, loop_node.id)
        self.agent.connect_nodes(loop_node.id, node_process.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：工作流执行成功
        assert result["status"] == "completed"
        # 验证：process节点应该接收到3个不同的元素
        assert received_inputs == [10, 20, 30]

    @pytest.mark.asyncio
    async def test_loop_node_aggregates_results(self):
        """测试Loop节点聚合子节点的执行结果

        场景：Loop节点执行完所有迭代后，应聚合所有子执行结果
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        loop_node = self.node_factory.create(
            NodeType.LOOP, {"loop_type": "for_each", "collection_field": "items"}
        )
        node_double = self.node_factory.create(NodeType.GENERIC, {"name": "double"})

        self.agent.add_node(node_source)
        self.agent.add_node(loop_node)
        self.agent.add_node(node_double)

        # 设置source输出
        self.node_executor.set_node_output(node_source.id, {"items": [1, 2, 3]})

        # 设置double节点，将输入翻倍
        def double_fn(inputs):
            item = inputs.get("current_item", 0)
            return {"result": item * 2}

        self.node_executor.set_node_output(node_double.id, double_fn)

        # 连接节点
        self.agent.connect_nodes(node_source.id, loop_node.id)
        self.agent.connect_nodes(loop_node.id, node_double.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：loop节点的输出应该包含所有迭代的结果
        loop_output = result.get("results", {}).get(loop_node.id, {})
        assert "output" in loop_output
        assert "collection" in loop_output["output"]
        aggregated = loop_output["output"]["collection"]
        assert len(aggregated) == 3
        # 结果应该是[2, 4, 6]
        assert [r["result"] for r in aggregated] == [2, 4, 6]

    # ==================== Map节点测试 ====================

    @pytest.mark.asyncio
    async def test_map_node_transforms_collection(self):
        """测试Map节点转换集合

        场景：
        node_source (items=[{x:1},{x:2}]) -> map_node(transform: x*10) -> output
        预期：输出为[{x:10},{x:20}]
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        map_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "map",
                "collection_field": "items",
                "transform_expression": "x * 10",  # 转换表达式
            },
        )

        self.agent.add_node(node_source)
        self.agent.add_node(map_node)

        # 设置source输出
        self.node_executor.set_node_output(
            node_source.id, {"items": [{"x": 1}, {"x": 2}, {"x": 3}]}
        )

        # 连接节点
        self.agent.connect_nodes(node_source.id, map_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：map节点输出应该包含转换后的集合
        map_output = result.get("results", {}).get(map_node.id, {})
        assert "output" in map_output
        assert "collection" in map_output["output"]
        transformed = map_output["output"]["collection"]
        assert len(transformed) == 3
        assert [item["x"] for item in transformed] == [10, 20, 30]

    # ==================== Filter节点测试 ====================

    @pytest.mark.asyncio
    async def test_filter_node_filters_collection(self):
        """测试Filter节点过滤集合

        场景：
        node_source (items=[1,2,3,4,5]) -> filter_node(condition: x > 2) -> output
        预期：输出为[3,4,5]
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        filter_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "filter",
                "collection_field": "items",
                "filter_condition": "x > 2",  # 过滤条件
            },
        )

        self.agent.add_node(node_source)
        self.agent.add_node(filter_node)

        # 设置source输出
        self.node_executor.set_node_output(node_source.id, {"items": [1, 2, 3, 4, 5]})

        # 连接节点
        self.agent.connect_nodes(node_source.id, filter_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：filter节点输出应该只包含满足条件的元素
        filter_output = result.get("results", {}).get(filter_node.id, {})
        assert "output" in filter_output
        assert "collection" in filter_output["output"]
        filtered = filter_output["output"]["collection"]
        assert filtered == [3, 4, 5]

    @pytest.mark.asyncio
    async def test_filter_node_with_object_collection(self):
        """测试Filter节点过滤对象集合

        场景：过滤对象列表，基于对象属性
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        filter_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "filter",
                "collection_field": "users",
                "filter_condition": "age >= 18",  # 过滤成年用户
            },
        )

        self.agent.add_node(node_source)
        self.agent.add_node(filter_node)

        # 设置source输出
        self.node_executor.set_node_output(
            node_source.id,
            {
                "users": [
                    {"name": "Alice", "age": 25},
                    {"name": "Bob", "age": 17},
                    {"name": "Charlie", "age": 30},
                    {"name": "David", "age": 16},
                ]
            },
        )

        # 连接节点
        self.agent.connect_nodes(node_source.id, filter_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：只有成年用户被保留
        filter_output = result.get("results", {}).get(filter_node.id, {})
        filtered = filter_output["output"]["collection"]
        assert len(filtered) == 2
        assert [u["name"] for u in filtered] == ["Alice", "Charlie"]

    # ==================== 边界情况测试 ====================

    @pytest.mark.asyncio
    async def test_loop_with_empty_collection(self):
        """测试Loop节点处理空集合

        场景：集合为空时，Loop节点不应执行子节点
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        loop_node = self.node_factory.create(
            NodeType.LOOP, {"loop_type": "for_each", "collection_field": "items"}
        )
        node_process = self.node_factory.create(NodeType.GENERIC, {"name": "process"})

        self.agent.add_node(node_source)
        self.agent.add_node(loop_node)
        self.agent.add_node(node_process)

        # 设置空集合
        self.node_executor.set_node_output(node_source.id, {"items": []})

        # 连接节点
        self.agent.connect_nodes(node_source.id, loop_node.id)
        self.agent.connect_nodes(loop_node.id, node_process.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：process节点不应该被执行
        assert self.node_executor.execution_count.get(node_process.id, 0) == 0
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_loop_with_single_item_collection(self):
        """测试Loop节点处理单元素集合"""
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        loop_node = self.node_factory.create(
            NodeType.LOOP, {"loop_type": "for_each", "collection_field": "items"}
        )
        node_process = self.node_factory.create(NodeType.GENERIC, {"name": "process"})

        self.agent.add_node(node_source)
        self.agent.add_node(loop_node)
        self.agent.add_node(node_process)

        # 设置单元素集合
        self.node_executor.set_node_output(node_source.id, {"items": [42]})

        # 连接节点
        self.agent.connect_nodes(node_source.id, loop_node.id)
        self.agent.connect_nodes(loop_node.id, node_process.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：工作流执行成功
        assert result["status"] == "completed"
        # 验证：process节点应该被执行1次
        assert self.node_executor.execution_count.get(node_process.id, 0) == 1

    @pytest.mark.asyncio
    async def test_filter_returns_empty_when_no_match(self):
        """测试Filter节点在没有匹配项时返回空集合"""
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        filter_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "filter",
                "collection_field": "items",
                "filter_condition": "x > 100",  # 没有元素满足
            },
        )

        self.agent.add_node(node_source)
        self.agent.add_node(filter_node)

        # 设置source输出
        self.node_executor.set_node_output(node_source.id, {"items": [1, 2, 3, 4, 5]})

        # 连接节点
        self.agent.connect_nodes(node_source.id, filter_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：filter节点输出应该是空列表
        filter_output = result.get("results", {}).get(filter_node.id, {})
        filtered = filter_output["output"]["collection"]
        assert filtered == []

    # ==================== 嵌套集合操作测试 ====================

    @pytest.mark.asyncio
    async def test_nested_loop_and_filter(self):
        """测试嵌套的Loop和Filter操作

        场景：
        source -> loop(遍历用户列表) -> filter(过滤订单) -> aggregate
        对每个用户，过滤其订单列表，保留金额>100的订单
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        loop_users = self.node_factory.create(
            NodeType.LOOP, {"loop_type": "for_each", "collection_field": "users"}
        )
        filter_orders = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "filter",
                "collection_field": "orders",
                "filter_condition": "amount > 100",
            },
        )

        self.agent.add_node(node_source)
        self.agent.add_node(loop_users)
        self.agent.add_node(filter_orders)

        # 设置source输出
        self.node_executor.set_node_output(
            node_source.id,
            {
                "users": [
                    {
                        "name": "Alice",
                        "orders": [
                            {"id": 1, "amount": 50},
                            {"id": 2, "amount": 150},
                            {"id": 3, "amount": 200},
                        ],
                    },
                    {"name": "Bob", "orders": [{"id": 4, "amount": 80}, {"id": 5, "amount": 120}]},
                ]
            },
        )

        # 连接节点
        self.agent.connect_nodes(node_source.id, loop_users.id)
        self.agent.connect_nodes(loop_users.id, filter_orders.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：filter应该被执行2次（每个用户一次）
        assert self.node_executor.execution_count.get(filter_orders.id, 0) == 2

        # 验证：loop聚合结果应该包含两个用户的过滤结果
        loop_output = result.get("results", {}).get(loop_users.id, {})
        assert "output" in loop_output
        assert "collection" in loop_output["output"]

    # ==================== 复杂场景测试 ====================

    @pytest.mark.asyncio
    async def test_complex_collection_pipeline(self):
        """测试复杂的集合操作流水线

        场景：
        source -> filter(score>80) -> map(transform) -> loop(process) -> aggregate
        先过滤高分数据，再转换，最后批量处理
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        filter_high_score = self.node_factory.create(
            NodeType.LOOP,
            {"loop_type": "filter", "collection_field": "items", "filter_condition": "score > 80"},
        )
        map_transform = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "map",
                "collection_field": "collection",  # 现在使用标准化字段名
                "transform_expression": "score * 1.1",  # 加成10%
            },
        )
        loop_process = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "for_each",
                "collection_field": "collection",  # 现在使用标准化字段名
            },
        )
        node_save = self.node_factory.create(NodeType.GENERIC, {"name": "save"})

        for node in [node_source, filter_high_score, map_transform, loop_process, node_save]:
            self.agent.add_node(node)

        # 设置source输出
        self.node_executor.set_node_output(
            node_source.id,
            {
                "items": [
                    {"id": 1, "score": 75},
                    {"id": 2, "score": 85},
                    {"id": 3, "score": 92},
                    {"id": 4, "score": 70},
                    {"id": 5, "score": 88},
                ]
            },
        )

        # 连接节点
        self.agent.connect_nodes(node_source.id, filter_high_score.id)
        self.agent.connect_nodes(filter_high_score.id, map_transform.id)
        self.agent.connect_nodes(map_transform.id, loop_process.id)
        self.agent.connect_nodes(loop_process.id, node_save.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：save节点应该被执行3次（id=2,3,5的数据）
        assert self.node_executor.execution_count.get(node_save.id, 0) == 3
        assert result["status"] == "completed"


# ==================== Phase 3: 集合操作增强测试 ====================


class TestCollectionOperationEnhancements:
    """Phase 3: 集合操作增强测试

    测试范围：
    - Map操作使用安全求值器（ExpressionEvaluator）
    - 集合操作结果写回WorkflowContext
    - 标准化输出结构
    - 错误处理与部分失败标记
    """

    def setup_method(self):
        """测试前设置"""
        from src.domain.services.context_manager import GlobalContext, SessionContext

        self.event_bus = EventBus()

        # 创建上下文
        self.global_context = GlobalContext(user_id="test_user")
        self.session_context = SessionContext(
            session_id="test_session", global_context=self.global_context
        )
        self.workflow_context = WorkflowContext(
            workflow_id="test_wf", session_context=self.session_context
        )

        # 创建NodeFactory和Executor
        from src.domain.services.node_registry import NodeRegistry

        self.node_registry = NodeRegistry()
        self.node_factory = NodeFactory(self.node_registry)
        self.node_executor = MockNodeExecutor()

        self.agent = WorkflowAgent(
            workflow_context=self.workflow_context,
            node_factory=self.node_factory,
            node_executor=self.node_executor,
            event_bus=self.event_bus,
        )

    # ==================== Map安全求值器测试 ====================

    @pytest.mark.asyncio
    async def test_map_uses_expression_evaluator(self):
        """测试Map操作使用ExpressionEvaluator（不再使用裸eval）

        场景：Map转换应通过ExpressionEvaluator，受安全限制
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        map_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "map",
                "collection_field": "items",
                "transform_expression": "price * 0.9",  # 安全的算术表达式
            },
        )

        self.agent.add_node(node_source)
        self.agent.add_node(map_node)

        # 设置source输出
        self.node_executor.set_node_output(
            node_source.id, {"items": [{"price": 100}, {"price": 200}]}
        )

        # 连接节点
        self.agent.connect_nodes(node_source.id, map_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：Map操作应该成功执行
        assert result["status"] == "completed"
        map_output = result["results"].get(map_node.id, {})
        assert "transformed_collection" in map_output or "output" in map_output

    @pytest.mark.asyncio
    async def test_map_blocks_unsafe_expression(self):
        """测试Map操作阻止不安全表达式

        场景：尝试在Map中使用危险操作应被ExpressionEvaluator阻止
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        map_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "map",
                "collection_field": "items",
                "transform_expression": "__import__('os').system('ls')",  # 危险表达式
            },
        )

        self.agent.add_node(node_source)
        self.agent.add_node(map_node)

        # 设置source输出
        self.node_executor.set_node_output(node_source.id, {"items": [1, 2, 3]})

        # 连接节点
        self.agent.connect_nodes(node_source.id, map_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：应该失败或者有错误标记
        map_output = result["results"].get(map_node.id, {})
        # 应该有错误标记或者status != "success"
        assert (
            map_output.get("status") == "error"
            or "error" in map_output
            or map_output.get("success") is False
        )

    # ==================== 结果写回WorkflowContext测试 ====================

    @pytest.mark.asyncio
    async def test_loop_result_written_to_workflow_context(self):
        """测试Loop操作结果写回WorkflowContext

        场景：Loop节点执行后，结果应该写入workflow_context.node_data
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        loop_node = self.node_factory.create(
            NodeType.LOOP,
            {"loop_type": "for_each", "collection_field": "items"},
        )

        self.agent.add_node(node_source)
        self.agent.add_node(loop_node)

        # 设置source输出
        self.node_executor.set_node_output(node_source.id, {"items": [1, 2, 3]})

        # 连接节点
        self.agent.connect_nodes(node_source.id, loop_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：loop节点的输出应该在workflow_context中
        assert result["status"] == "completed"
        loop_output_from_context = self.workflow_context.get_node_output(loop_node.id)
        assert loop_output_from_context is not None
        # 应该包含集合操作的结果
        assert (
            "aggregated_results" in loop_output_from_context or "output" in loop_output_from_context
        )

    @pytest.mark.asyncio
    async def test_map_result_written_to_workflow_context(self):
        """测试Map操作结果写回WorkflowContext"""
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        map_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "map",
                "collection_field": "items",
                "transform_expression": "x * 2",
            },
        )

        self.agent.add_node(node_source)
        self.agent.add_node(map_node)

        # 设置source输出
        self.node_executor.set_node_output(node_source.id, {"items": [1, 2, 3]})

        # 连接节点
        self.agent.connect_nodes(node_source.id, map_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：map节点的输出应该在workflow_context中
        assert result["status"] == "completed"
        map_output_from_context = self.workflow_context.get_node_output(map_node.id)
        assert map_output_from_context is not None
        assert (
            "transformed_collection" in map_output_from_context
            or "output" in map_output_from_context
        )

    @pytest.mark.asyncio
    async def test_filter_result_written_to_workflow_context(self):
        """测试Filter操作结果写回WorkflowContext"""
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        filter_node = self.node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "filter",
                "collection_field": "items",
                "filter_condition": "x > 2",
            },
        )

        self.agent.add_node(node_source)
        self.agent.add_node(filter_node)

        # 设置source输出
        self.node_executor.set_node_output(node_source.id, {"items": [1, 2, 3, 4, 5]})

        # 连接节点
        self.agent.connect_nodes(node_source.id, filter_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：filter节点的输出应该在workflow_context中
        assert result["status"] == "completed"
        filter_output_from_context = self.workflow_context.get_node_output(filter_node.id)
        assert filter_output_from_context is not None
        assert (
            "filtered_collection" in filter_output_from_context
            or "output" in filter_output_from_context
        )

    # ==================== 标准化输出结构测试 ====================

    @pytest.mark.asyncio
    async def test_collection_operations_return_standardized_structure(self):
        """测试集合操作返回标准化输出结构

        标准结构应包含：
        - success: bool
        - output: {...}（包含实际数据）
        - metadata: {...}（包含loop_type, counts等）
        """
        node_source = self.node_factory.create(NodeType.GENERIC, {"name": "source"})
        loop_node = self.node_factory.create(
            NodeType.LOOP,
            {"loop_type": "for_each", "collection_field": "items"},
        )

        self.agent.add_node(node_source)
        self.agent.add_node(loop_node)

        # 设置source输出
        self.node_executor.set_node_output(node_source.id, {"items": [1, 2]})

        # 连接节点
        self.agent.connect_nodes(node_source.id, loop_node.id)

        # 执行工作流
        result = await self.agent.execute_workflow_with_collection_operations()

        # 验证：输出结构应该标准化
        loop_output = result["results"].get(loop_node.id, {})
        # 至少应该有success标识
        assert "success" in loop_output or "status" in loop_output
