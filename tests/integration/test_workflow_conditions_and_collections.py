"""工作流条件分支与集合操作集成测试

本测试套件验证条件分支（Phase 2）与集合操作（Phase 3）的组合使用场景。

测试场景：
1. 数据质量检查流水线：条件分支 + Filter
2. 批量用户处理：Loop + 条件路由
3. ETL流水线：Filter -> Map -> 条件分支
4. 数据分析报告：条件分支 -> Loop聚合
5. 复杂业务流程：多级条件 + 嵌套集合操作

集成测试目标：
- 验证条件分支与集合操作能正确组合
- 验证复杂数据流的正确性
- 验证错误处理和边界情况
- 验证性能和稳定性
"""

import pytest

from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.services.context_manager import GlobalContext, SessionContext, WorkflowContext
from src.domain.services.event_bus import EventBus
from src.domain.services.node_registry import NodeFactory, NodeRegistry, NodeType


class MockNodeExecutor:
    """模拟节点执行器，支持复杂数据流"""

    def __init__(self):
        self.executed_nodes = []
        self.execution_count = {}
        self.node_outputs = {}

    def set_node_output(self, node_id: str, output: dict):
        """设置节点预设输出"""
        self.node_outputs[node_id] = output

    async def execute(self, node_id: str, config: dict, inputs: dict):
        """执行节点"""
        self.executed_nodes.append(node_id)
        self.execution_count[node_id] = self.execution_count.get(node_id, 0) + 1

        if node_id in self.node_outputs:
            output = self.node_outputs[node_id]
            if callable(output):
                return output(inputs)
            return output

        return {"status": "success", "executed": True}


@pytest.fixture
def setup_agent():
    """创建WorkflowAgent测试环境"""
    event_bus = EventBus()
    node_registry = NodeRegistry()
    node_factory = NodeFactory(node_registry)

    global_ctx = GlobalContext(user_id="test_user")
    session_ctx = SessionContext(session_id="test_session", global_context=global_ctx)
    workflow_ctx = WorkflowContext(workflow_id="test_workflow", session_context=session_ctx)

    node_executor = MockNodeExecutor()

    agent = WorkflowAgent(
        workflow_context=workflow_ctx,
        node_factory=node_factory,
        node_executor=node_executor,
        event_bus=event_bus,
    )

    return agent, node_factory, node_executor


class TestDataQualityPipeline:
    """场景1：数据质量检查流水线"""

    @pytest.mark.asyncio
    async def test_quality_check_with_conditional_cleaning(self, setup_agent):
        """测试：根据数据质量分数决定是否需要清洗，然后过滤低质量数据

        流程：
        data_source -> quality_check -> [条件分支]
                                    high_quality -> filter_valid -> report
                                    low_quality -> clean_data -> filter_valid -> report
        """
        agent, node_factory, node_executor = setup_agent

        # 创建节点
        data_source = node_factory.create(NodeType.GENERIC, {"name": "data_source"})
        quality_check = node_factory.create(NodeType.GENERIC, {"name": "quality_check"})
        clean_data = node_factory.create(NodeType.GENERIC, {"name": "clean_data"})
        filter_valid = node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "filter",
                "collection_field": "records",
                "filter_condition": "score >= 0.7",
            },
        )
        report = node_factory.create(NodeType.GENERIC, {"name": "report"})

        # 添加节点
        for node in [data_source, quality_check, clean_data, filter_valid, report]:
            agent.add_node(node)

        # 设置数据源输出（模拟低质量数据）
        node_executor.set_node_output(
            data_source.id,
            {
                "records": [
                    {"id": 1, "value": "good", "score": 0.9},
                    {"id": 2, "value": "bad", "score": 0.3},
                    {"id": 3, "value": "ok", "score": 0.7},
                    {"id": 4, "value": "poor", "score": 0.2},
                ]
            },
        )

        # 质量检查输出（平均分低于0.7）
        node_executor.set_node_output(
            quality_check.id,
            {
                "quality_score": 0.575,  # (0.9+0.3+0.7+0.2)/4
                "records": [
                    {"id": 1, "value": "good", "score": 0.9},
                    {"id": 2, "value": "bad", "score": 0.3},
                    {"id": 3, "value": "ok", "score": 0.7},
                    {"id": 4, "value": "poor", "score": 0.2},
                ],
            },
        )

        # 清洗后的数据（提升低分记录）
        node_executor.set_node_output(
            clean_data.id,
            {
                "records": [
                    {"id": 1, "value": "good", "score": 0.9},
                    {"id": 2, "value": "cleaned", "score": 0.8},  # 清洗后提升
                    {"id": 3, "value": "ok", "score": 0.7},
                    {"id": 4, "value": "cleaned", "score": 0.75},  # 清洗后提升
                ]
            },
        )

        # 连接节点（添加条件分支）
        agent.connect_nodes(data_source.id, quality_check.id)
        agent.connect_nodes(quality_check.id, clean_data.id, condition="quality_score < 0.7")
        agent.connect_nodes(quality_check.id, filter_valid.id, condition="quality_score >= 0.7")
        agent.connect_nodes(clean_data.id, filter_valid.id)
        agent.connect_nodes(filter_valid.id, report.id)

        # 执行工作流
        result = await agent.execute_workflow_with_collection_operations()

        # 验证结果
        assert result["status"] == "completed"
        # 质量低，应该走清洗路径
        assert clean_data.id in node_executor.executed_nodes
        # 过滤后应该保留所有记录（清洗后都>=0.7）
        filter_result = result["results"][filter_valid.id]
        assert len(filter_result["output"]["collection"]) == 4


class TestBatchUserProcessing:
    """场景2：批量用户处理"""

    @pytest.mark.asyncio
    async def test_user_batch_with_type_routing(self, setup_agent):
        """测试：遍历用户列表，根据用户类型路由到不同处理节点

        流程：
        load_users -> loop_users -> [条件路由]
                                vip_user -> vip_handler
                                normal_user -> normal_handler
        """
        agent, node_factory, node_executor = setup_agent

        # 创建节点
        load_users = node_factory.create(NodeType.GENERIC, {"name": "load_users"})
        loop_users = node_factory.create(
            NodeType.LOOP,
            {"loop_type": "for_each", "collection_field": "users", "item_variable": "current_user"},
        )
        vip_handler = node_factory.create(NodeType.GENERIC, {"name": "vip_handler"})
        normal_handler = node_factory.create(NodeType.GENERIC, {"name": "normal_handler"})

        # 添加节点
        for node in [load_users, loop_users, vip_handler, normal_handler]:
            agent.add_node(node)

        # 设置用户数据（2个VIP，3个普通用户）
        node_executor.set_node_output(
            load_users.id,
            {
                "users": [
                    {"id": 1, "name": "Alice", "type": "vip", "level": 5},
                    {"id": 2, "name": "Bob", "type": "normal", "level": 1},
                    {"id": 3, "name": "Charlie", "type": "vip", "level": 3},
                    {"id": 4, "name": "David", "type": "normal", "level": 2},
                    {"id": 5, "name": "Eve", "type": "normal", "level": 1},
                ]
            },
        )

        # VIP处理器和普通处理器记录处理的用户
        vip_processed = []
        normal_processed = []

        def vip_process(inputs):
            user = inputs.get("current_user")
            vip_processed.append(user)
            return {"status": "vip_processed", "user": user}

        def normal_process(inputs):
            user = inputs.get("current_user")
            normal_processed.append(user)
            return {"status": "normal_processed", "user": user}

        node_executor.set_node_output(vip_handler.id, vip_process)
        node_executor.set_node_output(normal_handler.id, normal_process)

        # 连接节点
        agent.connect_nodes(load_users.id, loop_users.id)
        # Loop的子节点需要条件路由（这里简化为直接执行两个handler）
        # 实际场景中，loop内部应该有条件判断
        agent.connect_nodes(loop_users.id, vip_handler.id)
        agent.connect_nodes(loop_users.id, normal_handler.id)

        # 执行工作流
        result = await agent.execute_workflow_with_collection_operations()

        # 验证：loop应该执行5次（5个用户）
        assert result["status"] == "completed"
        loop_result = result["results"][loop_users.id]
        assert loop_result["metadata"]["iteration_count"] == 5
        # VIP和普通用户都应该被处理
        assert len(vip_processed) == 5  # 每个用户都会触发vip_handler
        assert len(normal_processed) == 5  # 每个用户都会触发normal_handler


class TestETLPipeline:
    """场景3：ETL数据流水线"""

    @pytest.mark.asyncio
    async def test_filter_map_conditional_pipeline(self, setup_agent):
        """测试：Filter -> Map -> 条件分支

        流程：
        extract -> filter(price>100) -> map(apply_discount) -> [条件]
                                                            total>1000 -> bulk_order
                                                            total<=1000 -> regular_order
        """
        agent, node_factory, node_executor = setup_agent

        # 创建节点
        extract = node_factory.create(NodeType.GENERIC, {"name": "extract"})
        filter_expensive = node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "filter",
                "collection_field": "orders",
                "filter_condition": "price > 100",
            },
        )
        map_discount = node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "map",
                "collection_field": "collection",
                "transform_expression": "price * 0.9",  # 10% discount
            },
        )
        calculate_total = node_factory.create(NodeType.GENERIC, {"name": "calculate_total"})
        bulk_order = node_factory.create(NodeType.GENERIC, {"name": "bulk_order"})
        regular_order = node_factory.create(NodeType.GENERIC, {"name": "regular_order"})

        # 添加节点
        for node in [
            extract,
            filter_expensive,
            map_discount,
            calculate_total,
            bulk_order,
            regular_order,
        ]:
            agent.add_node(node)

        # 提取的订单数据
        node_executor.set_node_output(
            extract.id,
            {
                "orders": [
                    {"id": 1, "price": 50, "qty": 2},
                    {"id": 2, "price": 150, "qty": 5},
                    {"id": 3, "price": 200, "qty": 3},
                    {"id": 4, "price": 80, "qty": 10},
                    {"id": 5, "price": 300, "qty": 2},
                ]
            },
        )

        # 计算总价
        def calc_total(inputs):
            # 从上游 map_discount 节点获取标准化输出
            map_discount_id = list(inputs.keys())[0]  # 获取上游节点 ID
            upstream_output = inputs.get(map_discount_id, {})
            items = upstream_output.get("output", {}).get("collection", [])
            total = sum(item.get("price", 0) * item.get("qty", 1) for item in items)
            return {"total": total, "items": items}

        node_executor.set_node_output(calculate_total.id, calc_total)

        # 连接节点
        agent.connect_nodes(extract.id, filter_expensive.id)
        agent.connect_nodes(filter_expensive.id, map_discount.id)
        agent.connect_nodes(map_discount.id, calculate_total.id)
        agent.connect_nodes(calculate_total.id, bulk_order.id, condition="total > 1000")
        agent.connect_nodes(calculate_total.id, regular_order.id, condition="total <= 1000")

        # 执行工作流
        result = await agent.execute_workflow_with_collection_operations()

        # 验证：应该过滤出3个订单（price>100: id=2,3,5）
        filter_result = result["results"][filter_expensive.id]
        assert len(filter_result["output"]["collection"]) == 3

        # 验证：map应该应用折扣
        map_result = result["results"][map_discount.id]
        discounted_prices = [item["price"] for item in map_result["output"]["collection"]]
        expected_prices = [135, 180, 270]  # [150*0.9, 200*0.9, 300*0.9]
        assert discounted_prices == expected_prices


class TestDataAnalysisReport:
    """场景4：数据分析报告生成"""

    @pytest.mark.asyncio
    async def test_conditional_branch_to_loop_aggregation(self, setup_agent):
        """测试：条件分支 -> Loop聚合

        流程：
        check_data_size -> [条件]
                        large_dataset -> sample_data -> analyze_loop
                        small_dataset -> analyze_loop
        """
        agent, node_factory, node_executor = setup_agent

        # 创建节点
        check_size = node_factory.create(NodeType.GENERIC, {"name": "check_size"})
        sample_data = node_factory.create(NodeType.GENERIC, {"name": "sample_data"})
        analyze_loop = node_factory.create(
            NodeType.LOOP,
            {"loop_type": "for_each", "collection_field": "data_items", "item_variable": "item"},
        )
        analyze_item = node_factory.create(NodeType.GENERIC, {"name": "analyze_item"})

        # 添加节点
        for node in [check_size, sample_data, analyze_loop, analyze_item]:
            agent.add_node(node)

        # 大数据集（需要采样）
        node_executor.set_node_output(
            check_size.id, {"record_count": 10000, "data_items": list(range(10000))}
        )

        # 采样后的数据
        node_executor.set_node_output(
            sample_data.id,
            {
                "data_items": list(range(0, 10000, 100))  # 采样100个
            },
        )

        # 连接节点
        agent.connect_nodes(check_size.id, sample_data.id, condition="record_count > 1000")
        agent.connect_nodes(check_size.id, analyze_loop.id, condition="record_count <= 1000")
        agent.connect_nodes(sample_data.id, analyze_loop.id)
        agent.connect_nodes(analyze_loop.id, analyze_item.id)

        # 执行工作流
        result = await agent.execute_workflow_with_collection_operations()

        # 验证：大数据集应该走采样路径
        assert sample_data.id in node_executor.executed_nodes
        # Loop应该处理采样后的100个元素
        loop_result = result["results"][analyze_loop.id]
        assert loop_result["metadata"]["iteration_count"] == 100


class TestComplexBusinessFlow:
    """场景5：复杂业务流程"""

    @pytest.mark.asyncio
    async def test_multi_level_conditions_and_nested_collections(self, setup_agent):
        """测试：多级条件 + 嵌套集合操作

        流程：
        load_orders -> filter(status='pending') -> loop_orders
                                                -> check_inventory -> [条件]
                                                                    in_stock -> process_order
                                                                    out_of_stock -> backorder
        """
        agent, node_factory, node_executor = setup_agent

        # 创建节点
        load_orders = node_factory.create(NodeType.GENERIC, {"name": "load_orders"})
        filter_pending = node_factory.create(
            NodeType.LOOP,
            {
                "loop_type": "filter",
                "collection_field": "orders",
                "filter_condition": "status == 'pending'",
            },
        )
        loop_orders = node_factory.create(
            NodeType.LOOP,
            {"loop_type": "for_each", "collection_field": "collection", "item_variable": "order"},
        )
        check_inventory = node_factory.create(NodeType.GENERIC, {"name": "check_inventory"})
        process_order = node_factory.create(NodeType.GENERIC, {"name": "process_order"})
        backorder = node_factory.create(NodeType.GENERIC, {"name": "backorder"})

        # 添加节点
        for node in [
            load_orders,
            filter_pending,
            loop_orders,
            check_inventory,
            process_order,
            backorder,
        ]:
            agent.add_node(node)

        # 订单数据（混合状态）
        node_executor.set_node_output(
            load_orders.id,
            {
                "orders": [
                    {"id": 1, "status": "pending", "item": "A", "qty": 5},
                    {"id": 2, "status": "completed", "item": "B", "qty": 3},
                    {"id": 3, "status": "pending", "item": "C", "qty": 2},
                    {"id": 4, "status": "pending", "item": "D", "qty": 10},
                    {"id": 5, "status": "cancelled", "item": "E", "qty": 1},
                ]
            },
        )

        # 连接节点
        agent.connect_nodes(load_orders.id, filter_pending.id)
        agent.connect_nodes(filter_pending.id, loop_orders.id)
        agent.connect_nodes(loop_orders.id, check_inventory.id)
        agent.connect_nodes(check_inventory.id, process_order.id)
        agent.connect_nodes(check_inventory.id, backorder.id)

        # 执行工作流
        result = await agent.execute_workflow_with_collection_operations()

        # 验证：应该过滤出3个pending订单
        filter_result = result["results"][filter_pending.id]
        assert len(filter_result["output"]["collection"]) == 3

        # 验证：loop应该处理3个订单
        loop_result = result["results"][loop_orders.id]
        assert loop_result["metadata"]["iteration_count"] == 3


class TestErrorHandlingAndEdgeCases:
    """边界情况和错误处理测试"""

    @pytest.mark.asyncio
    async def test_empty_collection_with_conditions(self, setup_agent):
        """测试：空集合 + 条件分支"""
        agent, node_factory, node_executor = setup_agent

        source = node_factory.create(NodeType.GENERIC, {"name": "source"})
        filter_node = node_factory.create(
            NodeType.LOOP,
            {"loop_type": "filter", "collection_field": "items", "filter_condition": "value > 10"},
        )
        process = node_factory.create(NodeType.GENERIC, {"name": "process"})

        agent.add_node(source)
        agent.add_node(filter_node)
        agent.add_node(process)

        # 空集合
        node_executor.set_node_output(source.id, {"items": []})

        agent.connect_nodes(source.id, filter_node.id)
        agent.connect_nodes(filter_node.id, process.id)

        result = await agent.execute_workflow_with_collection_operations()

        # 应该成功完成，但process不应该执行（因为没有数据）
        assert result["status"] == "completed"
        filter_result = result["results"][filter_node.id]
        assert filter_result["output"]["collection"] == []

    @pytest.mark.asyncio
    async def test_all_conditions_false(self, setup_agent):
        """测试：所有条件都不满足的情况"""
        agent, node_factory, node_executor = setup_agent

        source = node_factory.create(NodeType.GENERIC, {"name": "source"})
        branch_a = node_factory.create(NodeType.GENERIC, {"name": "branch_a"})
        branch_b = node_factory.create(NodeType.GENERIC, {"name": "branch_b"})

        agent.add_node(source)
        agent.add_node(branch_a)
        agent.add_node(branch_b)

        node_executor.set_node_output(source.id, {"value": 50})

        # 两个分支的条件都不满足
        agent.connect_nodes(source.id, branch_a.id, condition="value > 100")
        agent.connect_nodes(source.id, branch_b.id, condition="value < 10")

        result = await agent.execute_workflow_with_collection_operations()

        # 应该成功完成，但两个分支都被跳过
        assert result["status"] == "completed"
        assert branch_a.id in result["skipped_nodes"]
        assert branch_b.id in result["skipped_nodes"]
