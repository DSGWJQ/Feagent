"""Phase 4: ConversationAgent七种节点类型规划能力测试

测试目标：
1. decision_payload.NodeType枚举扩展（FILE/DATA_PROCESS/HUMAN/GENERIC）
2. CreateWorkflowPlanPayload接受新类型并校验必填字段
3. ConversationAgent.create_workflow_plan识别新类型
4. DecisionMadeEvent正确透传新类型
5. 字段名兼容性（node_type vs type）
"""

import pytest

from src.domain.agents.decision_payload import (
    CreateWorkflowPlanPayload,
    NodeType,
    WorkflowNode,
)


class TestDecisionPayloadNodeTypeExtension:
    """测试decision_payload.NodeType枚举扩展"""

    def test_node_type_enum_includes_file(self):
        """NodeType枚举包含FILE"""
        assert hasattr(NodeType, "FILE")
        assert NodeType.FILE.value == "FILE"

    def test_node_type_enum_includes_data_process(self):
        """NodeType枚举包含DATA_PROCESS"""
        assert hasattr(NodeType, "DATA_PROCESS")
        assert NodeType.DATA_PROCESS.value == "DATA_PROCESS"

    def test_node_type_enum_includes_human(self):
        """NodeType枚举包含HUMAN"""
        assert hasattr(NodeType, "HUMAN")
        assert NodeType.HUMAN.value == "HUMAN"

    def test_node_type_enum_includes_generic(self):
        """NodeType枚举包含GENERIC"""
        assert hasattr(NodeType, "GENERIC")
        assert NodeType.GENERIC.value == "GENERIC"


class TestWorkflowNodeAcceptsNewTypes:
    """测试WorkflowNode接受新节点类型"""

    def test_workflow_node_accepts_file_type(self):
        """WorkflowNode接受FILE类型"""
        node = WorkflowNode(
            node_id="file_1",
            type=NodeType.FILE,
            name="Read Config",
            config={"operation": "read", "path": "/tmp/config.json"},
        )
        assert node.type == NodeType.FILE
        assert node.config["operation"] == "read"

    def test_workflow_node_accepts_data_process_type(self):
        """WorkflowNode接受DATA_PROCESS类型"""
        node = WorkflowNode(
            node_id="transform_1",
            type=NodeType.DATA_PROCESS,
            name="Transform Data",
            config={"type": "field_mapping", "mapping": {"old": "new"}},
        )
        assert node.type == NodeType.DATA_PROCESS
        assert node.config["type"] == "field_mapping"

    def test_workflow_node_accepts_human_type(self):
        """WorkflowNode接受HUMAN类型"""
        node = WorkflowNode(
            node_id="human_1",
            type=NodeType.HUMAN,
            name="Approve Request",
            config={
                "prompt": "Please approve this request",
                "expected_inputs": ["approved", "rejected"],
                "timeout_seconds": 300,
            },
        )
        assert node.type == NodeType.HUMAN
        assert node.config["prompt"] == "Please approve this request"

    def test_workflow_node_accepts_generic_type(self):
        """WorkflowNode接受GENERIC类型"""
        node = WorkflowNode(
            node_id="generic_1",
            type=NodeType.GENERIC,
            name="Custom Node",
            config={"custom_field": "value"},
        )
        assert node.type == NodeType.GENERIC


class TestCreateWorkflowPlanPayloadValidation:
    """测试CreateWorkflowPlanPayload对新类型的校验"""

    def test_payload_accepts_plan_with_file_nodes(self):
        """Payload接受包含FILE节点的plan"""
        payload = CreateWorkflowPlanPayload(
            action_type="create_workflow_plan",
            name="File Processing Workflow",
            description="Process files",
            nodes=[
                {
                    "node_id": "file_1",
                    "type": "FILE",
                    "name": "Read File",
                    "config": {"operation": "read", "path": "/tmp/data.csv"},
                }
            ],
            edges=[],
        )
        assert len(payload.nodes) == 1
        assert payload.nodes[0].type == NodeType.FILE

    def test_payload_accepts_plan_with_data_process_nodes(self):
        """Payload接受包含DATA_PROCESS节点的plan"""
        payload = CreateWorkflowPlanPayload(
            action_type="create_workflow_plan",
            name="Data Transform Workflow",
            description="Transform data",
            nodes=[
                {
                    "node_id": "transform_1",
                    "type": "DATA_PROCESS",
                    "name": "Map Fields",
                    "config": {"type": "field_mapping", "mapping": {"a": "b"}},
                }
            ],
            edges=[],
        )
        assert len(payload.nodes) == 1
        assert payload.nodes[0].type == NodeType.DATA_PROCESS

    def test_payload_accepts_plan_with_human_nodes(self):
        """Payload接受包含HUMAN节点的plan"""
        payload = CreateWorkflowPlanPayload(
            action_type="create_workflow_plan",
            name="Approval Workflow",
            description="Require human approval",
            nodes=[
                {
                    "node_id": "human_1",
                    "type": "HUMAN",
                    "name": "Approve",
                    "config": {"prompt": "Approve?", "expected_inputs": ["yes", "no"]},
                }
            ],
            edges=[],
        )
        assert len(payload.nodes) == 1
        assert payload.nodes[0].type == NodeType.HUMAN

    def test_payload_accepts_mixed_node_types(self):
        """Payload接受混合节点类型的plan"""
        payload = CreateWorkflowPlanPayload(
            action_type="create_workflow_plan",
            name="Complex Workflow",
            description="Mix of node types",
            nodes=[
                {
                    "node_id": "llm_1",
                    "type": "LLM",
                    "name": "Analyze",
                    "config": {"prompt": "Analyze this"},
                },
                {
                    "node_id": "file_1",
                    "type": "FILE",
                    "name": "Save Result",
                    "config": {"operation": "write", "path": "/tmp/result.txt", "content": "data"},
                },
                {
                    "node_id": "human_1",
                    "type": "HUMAN",
                    "name": "Review",
                    "config": {"prompt": "Review the result"},
                },
            ],
            edges=[
                {"source": "llm_1", "target": "file_1"},
                {"source": "file_1", "target": "human_1"},
            ],
        )
        assert len(payload.nodes) == 3
        assert payload.nodes[0].type == NodeType.LLM
        assert payload.nodes[1].type == NodeType.FILE
        assert payload.nodes[2].type == NodeType.HUMAN


class TestBackwardCompatibility:
    """测试向后兼容性 - 现有节点类型不受影响"""

    def test_existing_llm_node_still_works(self):
        """现有LLM节点仍然工作"""
        node = WorkflowNode(
            node_id="llm_1",
            type=NodeType.LLM,
            name="Generate Text",
            config={"prompt": "Generate a summary", "model": "gpt-4"},
        )
        assert node.type == NodeType.LLM

    def test_existing_http_node_still_works(self):
        """现有HTTP节点仍然工作"""
        node = WorkflowNode(
            node_id="http_1",
            type=NodeType.HTTP,
            name="API Call",
            config={"url": "https://api.example.com", "method": "GET"},
        )
        assert node.type == NodeType.HTTP

    def test_existing_condition_node_still_works(self):
        """现有CONDITION节点仍然工作"""
        node = WorkflowNode(
            node_id="cond_1",
            type=NodeType.CONDITION,
            name="Check Status",
            config={"expression": "status == 'success'"},
        )
        assert node.type == NodeType.CONDITION


class TestExecutePlanFromDictFieldCompatibility:
    """测试execute_plan_from_dict的字段兼容性 - Phase 4第二部分

    注意：这些测试需要完整的WorkflowAgent设置（包括node_factory, node_executor等），
    属于集成测试范围。暂时skip，将在Phase 7端到端集成测试中覆盖。
    """

    @pytest.mark.skip(reason="需要完整的WorkflowAgent设置，属于集成测试，将在Phase 7覆盖")
    @pytest.mark.asyncio
    async def test_execute_plan_accepts_node_type_field(self):
        """execute_plan_from_dict接受node_type字段（plan.to_dict()格式）"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        agent = WorkflowAgent()

        plan_dict = {
            "name": "Test Plan",
            "goal": "Test node_type field",
            "nodes": [
                {
                    "name": "File Node",
                    "node_type": "file",  # 使用 node_type 而非 type
                    "config": {"operation": "read", "path": "/tmp/test.txt"},
                }
            ],
            "edges": [],
        }

        # 不应该抛出异常，应该能正确解析
        result = await agent.execute_plan_from_dict(plan_dict)
        assert result["status"] in ["completed", "pending_human_input"]

    @pytest.mark.skip(reason="需要完整的WorkflowAgent设置，属于集成测试，将在Phase 7覆盖")
    @pytest.mark.asyncio
    async def test_execute_plan_accepts_type_field_backward_compat(self):
        """execute_plan_from_dict接受type字段（向后兼容）"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        agent = WorkflowAgent()

        plan_dict = {
            "name": "Test Plan",
            "goal": "Test type field",
            "nodes": [
                {
                    "name": "Human Node",
                    "type": "human",  # 使用 type
                    "config": {"prompt": "Approve?"},
                }
            ],
            "edges": [],
        }

        result = await agent.execute_plan_from_dict(plan_dict)
        # HUMAN节点应该返回pending状态
        assert result.get("status") == "pending_human_input"

    @pytest.mark.skip(reason="需要完整的WorkflowAgent设置，属于集成测试，将在Phase 7覆盖")
    @pytest.mark.asyncio
    async def test_execute_plan_preserves_config(self):
        """execute_plan_from_dict正确透传config"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        agent = WorkflowAgent()

        plan_dict = {
            "name": "Test Plan",
            "goal": "Test config preservation",
            "nodes": [
                {
                    "name": "Data Process Node",
                    "node_type": "data_process",
                    "config": {
                        "type": "field_mapping",
                        "mapping": {"field1": "field2"},
                    },
                }
            ],
            "edges": [],
        }

        # 应该能正确解析并保留config
        result = await agent.execute_plan_from_dict(plan_dict)
        assert result is not None

    @pytest.mark.skip(reason="需要完整的WorkflowAgent设置，属于集成测试，将在Phase 7覆盖")
    @pytest.mark.asyncio
    async def test_execute_plan_handles_mixed_case_types(self):
        """execute_plan_from_dict处理混合大小写的类型"""
        from src.domain.agents.workflow_agent import WorkflowAgent

        agent = WorkflowAgent()

        plan_dict = {
            "name": "Test Plan",
            "goal": "Test case sensitivity",
            "nodes": [
                {
                    "name": "Node1",
                    "type": "FILE",
                    "config": {"operation": "read", "path": "/tmp/a"},
                },
                {
                    "name": "Node2",
                    "node_type": "file",
                    "config": {"operation": "write", "path": "/tmp/b", "content": "test"},
                },
                {
                    "name": "Node3",
                    "type": "File",
                    "config": {"operation": "read", "path": "/tmp/c"},
                },
            ],
            "edges": [],
        }

        result = await agent.execute_plan_from_dict(plan_dict)
        assert result["status"] in ["completed", "pending_human_input", "failed"]


# 注意：ConversationAgent相关的完整集成测试需要mock LLM和其他依赖
# 这些测试将在Phase 5中添加
