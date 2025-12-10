"""
测试 WorkflowAgent 反馈驱动更新API

Priority 4: WorkflowAgent 反馈驱动更新API
- update_edge_condition() - 修改边条件表达式
- update_loop_config() - 修改循环配置
"""

import pytest

from src.domain.agents.node_definition import NodeDefinition, NodeType
from src.domain.agents.workflow_agent import WorkflowAgent
from src.domain.agents.workflow_plan import EdgeDefinition, WorkflowPlan
from src.domain.services.context_manager import GlobalContext, SessionContext, WorkflowContext
from src.domain.services.event_bus import EventBus


class TestUpdateEdgeCondition:
    """测试 update_edge_condition 方法"""

    @pytest.fixture
    def workflow_agent(self):
        """创建 WorkflowAgent 实例"""
        event_bus = EventBus()
        agent = WorkflowAgent(event_bus=event_bus)
        return agent

    @pytest.fixture
    def sample_workflow_plan(self):
        """创建示例工作流计划"""
        nodes = [
            NodeDefinition(
                node_type=NodeType.CONDITION,
                name="quality_check",
                config={"expression": "quality_score > 0.8"},
            ),
            NodeDefinition(
                node_type=NodeType.GENERIC,
                name="analyze_task",
                config={},
            ),
            NodeDefinition(
                node_type=NodeType.GENERIC,
                name="clean_task",
                config={},
            ),
        ]

        edges = [
            EdgeDefinition(
                source_node="quality_check",
                target_node="analyze_task",
                condition="True",
            ),
            EdgeDefinition(
                source_node="quality_check",
                target_node="clean_task",
                condition="False",
            ),
        ]

        plan = WorkflowPlan(
            name="test_workflow",
            goal="test goal",
            nodes=nodes,
            edges=edges,
        )

        return plan

    def test_update_edge_condition_modifies_expression(self, workflow_agent, sample_workflow_plan):
        """测试 update_edge_condition 修改条件表达式"""
        # 设置工作流计划
        workflow_agent._current_plan = sample_workflow_plan

        # 获取原始边
        original_edge = sample_workflow_plan.edges[0]
        assert original_edge.condition == "True"

        # 更新边条件
        workflow_agent.update_edge_condition(
            source_node="quality_check",
            target_node="analyze_task",
            expression="quality_score > 0.9",  # 提高阈值
        )

        # 验证修改成功
        updated_edge = sample_workflow_plan.edges[0]
        assert updated_edge.condition == "quality_score > 0.9"

    def test_update_edge_condition_edge_not_found(self, workflow_agent, sample_workflow_plan):
        """测试 update_edge_condition 处理不存在的边"""
        workflow_agent._current_plan = sample_workflow_plan

        with pytest.raises(ValueError, match="边不存在|Edge not found"):
            workflow_agent.update_edge_condition(
                source_node="nonexistent",
                target_node="analyze_task",
                expression="new_expression",
            )

    def test_update_edge_condition_no_current_plan(self, workflow_agent):
        """测试 update_edge_condition 处理无当前计划"""
        with pytest.raises(ValueError, match="工作流计划|workflow plan"):
            workflow_agent.update_edge_condition(
                source_node="quality_check",
                target_node="analyze_task",
                expression="new_expression",
            )


class TestUpdateLoopConfig:
    """测试 update_loop_config 方法"""

    @pytest.fixture
    def workflow_agent(self):
        """创建 WorkflowAgent 实例"""
        event_bus = EventBus()
        agent = WorkflowAgent(event_bus=event_bus)
        return agent

    @pytest.fixture
    def sample_workflow_with_loop(self):
        """创建包含循环节点的工作流"""
        nodes = [
            NodeDefinition(
                node_type=NodeType.LOOP,
                name="process_datasets",
                config={
                    "loop_type": "for_each",
                    "collection_field": "datasets",
                    "loop_variable": "dataset",
                },
            ),
            NodeDefinition(
                node_type=NodeType.GENERIC,
                name="validate_task",
                config={},
            ),
        ]

        edges = [
            EdgeDefinition(
                source_node="process_datasets",
                target_node="validate_task",
            ),
        ]

        plan = WorkflowPlan(
            name="loop_workflow",
            goal="loop test goal",
            nodes=nodes,
            edges=edges,
        )

        return plan

    def test_update_loop_config_modifies_loop_type(self, workflow_agent, sample_workflow_with_loop):
        """测试 update_loop_config 修改循环类型"""
        workflow_agent._current_plan = sample_workflow_with_loop

        # 获取原始循环节点
        loop_node = sample_workflow_with_loop.nodes[0]
        assert loop_node.config["loop_type"] == "for_each"

        # 更新循环配置
        workflow_agent.update_loop_config(
            node_name="process_datasets",
            loop_type="map",
            transform_expression="dataset['value'] * 2",
        )

        # 验证修改成功
        assert loop_node.config["loop_type"] == "map"
        assert loop_node.config["transform_expression"] == "dataset['value'] * 2"

    def test_update_loop_config_modifies_collection_field(self, workflow_agent, sample_workflow_with_loop):
        """测试 update_loop_config 修改集合字段"""
        workflow_agent._current_plan = sample_workflow_with_loop

        loop_node = sample_workflow_with_loop.nodes[0]
        assert loop_node.config["collection_field"] == "datasets"

        # 更新集合字段
        workflow_agent.update_loop_config(
            node_name="process_datasets",
            collection_field="new_datasets",
        )

        # 验证修改成功
        assert loop_node.config["collection_field"] == "new_datasets"
        assert loop_node.config["loop_type"] == "for_each"  # 其他字段保持不变

    def test_update_loop_config_modifies_filter_condition(self, workflow_agent, sample_workflow_with_loop):
        """测试 update_loop_config 修改过滤条件"""
        workflow_agent._current_plan = sample_workflow_with_loop

        loop_node = sample_workflow_with_loop.nodes[0]

        # 更新为 filter 类型
        workflow_agent.update_loop_config(
            node_name="process_datasets",
            loop_type="filter",
            filter_condition="dataset['size'] > 1000",
        )

        # 验证修改成功
        assert loop_node.config["loop_type"] == "filter"
        assert loop_node.config["filter_condition"] == "dataset['size'] > 1000"

    def test_update_loop_config_node_not_found(self, workflow_agent, sample_workflow_with_loop):
        """测试 update_loop_config 处理不存在的节点"""
        workflow_agent._current_plan = sample_workflow_with_loop

        with pytest.raises(ValueError, match="节点不存在|Node not found"):
            workflow_agent.update_loop_config(
                node_name="nonexistent",
                loop_type="map",
            )

    def test_update_loop_config_not_loop_node(self, workflow_agent):
        """测试 update_loop_config 处理非循环节点"""
        nodes = [
            NodeDefinition(
                node_type=NodeType.GENERIC,
                name="not_a_loop",
                config={},
            ),
        ]

        plan = WorkflowPlan(name="test", goal="test", nodes=nodes, edges=[])
        workflow_agent._current_plan = plan

        with pytest.raises(ValueError, match="不是循环节点|not a LOOP node"):
            workflow_agent.update_loop_config(
                node_name="not_a_loop",
                loop_type="map",
            )

    def test_update_loop_config_no_current_plan(self, workflow_agent):
        """测试 update_loop_config 处理无当前计划"""
        with pytest.raises(ValueError, match="工作流计划|workflow plan"):
            workflow_agent.update_loop_config(
                node_name="process_datasets",
                loop_type="map",
            )


class TestUpdatedConfigEffective:
    """测试更新后的配置在下次执行时生效"""

    @pytest.fixture
    def workflow_agent(self):
        """创建 WorkflowAgent 实例"""
        event_bus = EventBus()
        agent = WorkflowAgent(event_bus=event_bus)
        return agent

    def test_updated_edge_condition_effective_in_next_execution(self, workflow_agent):
        """测试更新的边条件在下次执行时生效"""
        # 创建带条件边的工作流
        nodes = [
            NodeDefinition(
                node_type=NodeType.CONDITION,
                name="check",
                config={"expression": "value > 10"},
            ),
            NodeDefinition(node_type=NodeType.GENERIC, name="task_a", config={}),
            NodeDefinition(node_type=NodeType.GENERIC, name="task_b", config={}),
        ]

        edges = [
            EdgeDefinition(source_node="check", target_node="task_a", condition="True"),
            EdgeDefinition(source_node="check", target_node="task_b", condition="False"),
        ]

        plan = WorkflowPlan(name="test", goal="test", nodes=nodes, edges=edges)
        workflow_agent._current_plan = plan

        # 更新条件
        workflow_agent.update_edge_condition(
            source_node="check",
            target_node="task_a",
            expression="value > 20",  # 提高阈值
        )

        # 验证配置已更新
        updated_edge = [e for e in plan.edges if e.target_node == "task_a"][0]
        assert updated_edge.condition == "value > 20"

    def test_updated_loop_config_effective_in_next_execution(self, workflow_agent):
        """测试更新的循环配置在下次执行时生效"""
        # 创建循环工作流
        nodes = [
            NodeDefinition(
                node_type=NodeType.LOOP,
                name="loop",
                config={
                    "loop_type": "for_each",
                    "collection_field": "items",
                },
            ),
            NodeDefinition(node_type=NodeType.GENERIC, name="process", config={}),
        ]

        edges = [EdgeDefinition(source_node="loop", target_node="process")]

        plan = WorkflowPlan(name="test", goal="test", nodes=nodes, edges=edges)
        workflow_agent._current_plan = plan

        # 更新循环配置
        workflow_agent.update_loop_config(
            node_name="loop",
            loop_type="filter",
            filter_condition="item['active'] == True",
        )

        # 验证配置已更新
        loop_node = plan.nodes[0]
        assert loop_node.config["loop_type"] == "filter"
        assert loop_node.config["filter_condition"] == "item['active'] == True"
