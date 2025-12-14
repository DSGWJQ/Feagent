"""测试：Coordinator Payload 完整性校验 - Phase 8.4 TDD Red 阶段

测试目标：
1. Coordinator 能够验证 payload 必填字段
2. Coordinator 能够验证 payload 字段类型
3. Coordinator 能够验证 payload 字段值范围
4. 验证失败时返回详细错误信息

完成标准：
- 所有测试初始失败（Red阶段）
- 实现代码后所有测试通过（Green阶段）
"""

import pytest

# Mark all tests in this file as expected to fail (TDD Red Phase)
pytestmark = pytest.mark.xfail(
    reason="TDD Red Phase 8.4: Implementation in progress. See BACKEND_TESTING_PLAN.md P0-Task2",
    strict=False,
)


class TestPayloadRequiredFields:
    """测试 payload 必填字段验证"""

    def test_create_node_payload_should_have_node_type(self):
        """创建节点决策的 payload 必须包含 node_type 字段

        场景：ConversationAgent 生成创建节点决策，但忘记包含 node_type
        期望：Coordinator 拒绝此决策，返回错误信息
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # 添加 payload 必填字段验证规则
        coordinator.add_payload_validation_rule(
            decision_type="create_node",
            required_fields=["node_type", "node_name", "config"],
        )

        # 创建缺少 node_type 的决策
        decision = {
            "action_type": "create_node",
            "node_name": "测试节点",
            "config": {"url": "http://example.com"},
        }

        # 验证应失败
        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("node_type" in error for error in result.errors)

    def test_create_workflow_plan_payload_should_have_nodes(self):
        """创建工作流规划的 payload 必须包含 nodes 字段

        场景：ConversationAgent 生成工作流规划，但 nodes 为空
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        coordinator.add_payload_validation_rule(
            decision_type="create_workflow_plan",
            required_fields=["name", "description", "nodes", "edges"],
        )

        decision = {
            "action_type": "create_workflow_plan",
            "name": "测试工作流",
            "description": "测试描述",
            "nodes": [],  # 空节点列表
            "edges": [],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("nodes" in error or "至少" in error for error in result.errors)

    def test_execute_workflow_payload_should_have_workflow_id(self):
        """执行工作流决策必须包含 workflow_id

        场景：ConversationAgent 请求执行工作流，但未指定 workflow_id
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        coordinator.add_payload_validation_rule(
            decision_type="execute_workflow",
            required_fields=["workflow_id"],
        )

        decision = {
            "action_type": "execute_workflow",
            "input_params": {"data": "test"},
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("workflow_id" in error for error in result.errors)


class TestPayloadFieldTypes:
    """测试 payload 字段类型验证"""

    def test_node_config_should_be_dict(self):
        """节点 config 字段必须是字典类型

        场景：payload 中的 config 字段是字符串而非字典
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        coordinator.add_payload_type_validation_rule(
            decision_type="create_node",
            field_types={"config": dict, "node_name": str},
        )

        decision = {
            "action_type": "create_node",
            "node_type": "HTTP",
            "node_name": "测试节点",
            "config": "invalid_type",  # 错误类型
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("config" in error and "dict" in error for error in result.errors)

    def test_workflow_nodes_should_be_list(self):
        """工作流 nodes 字段必须是列表类型

        场景：nodes 字段是字典而非列表
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        coordinator.add_payload_type_validation_rule(
            decision_type="create_workflow_plan",
            field_types={"nodes": list, "edges": list},
        )

        decision = {
            "action_type": "create_workflow_plan",
            "name": "测试工作流",
            "description": "测试",
            "nodes": {"node1": {}},  # 错误类型
            "edges": [],
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("nodes" in error and "list" in error for error in result.errors)

    def test_timeout_should_be_numeric(self):
        """timeout 字段必须是数字类型

        场景：timeout 字段是字符串
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        coordinator.add_payload_type_validation_rule(
            decision_type="create_node",
            field_types={"config": dict},
            nested_field_types={"config.timeout": (int, float)},
        )

        decision = {
            "action_type": "create_node",
            "node_type": "HTTP",
            "node_name": "测试节点",
            "config": {"url": "http://example.com", "timeout": "30"},  # 错误类型
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("timeout" in error for error in result.errors)


class TestPayloadValueRanges:
    """测试 payload 字段值范围验证"""

    def test_timeout_should_be_positive(self):
        """timeout 值必须为正数

        场景：timeout 设置为负数
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        coordinator.add_payload_range_validation_rule(
            decision_type="create_node",
            field_ranges={"config.timeout": {"min": 0, "max": 3600}},
        )

        decision = {
            "action_type": "create_node",
            "node_type": "HTTP",
            "node_name": "测试节点",
            "config": {"url": "http://example.com", "timeout": -10},
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any(
            "timeout" in error and ("负" in error or "0" in error) for error in result.errors
        )

    def test_max_retries_should_have_limit(self):
        """max_retries 应该有合理上限

        场景：max_retries 设置为过大的值
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        coordinator.add_payload_range_validation_rule(
            decision_type="create_node",
            field_ranges={"config.max_retries": {"min": 0, "max": 10}},
        )

        decision = {
            "action_type": "create_node",
            "node_type": "HTTP",
            "node_name": "测试节点",
            "config": {"url": "http://example.com", "max_retries": 100},
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("max_retries" in error and "10" in error for error in result.errors)

    def test_node_type_should_be_in_allowed_list(self):
        """node_type 必须在允许的类型列表中

        场景：node_type 是不支持的类型
        期望：Coordinator 拒绝此决策
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        coordinator.add_payload_enum_validation_rule(
            decision_type="create_node",
            field_enums={
                "node_type": ["HTTP", "LLM", "PYTHON", "DATABASE", "CONDITION", "CONTAINER"]
            },
        )

        decision = {
            "action_type": "create_node",
            "node_type": "INVALID_TYPE",
            "node_name": "测试节点",
            "config": {},
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert any("node_type" in error and "INVALID_TYPE" in error for error in result.errors)


class TestPayloadValidationIntegration:
    """测试 payload 验证集成"""

    def test_multiple_validation_rules_should_all_check(self):
        """多个验证规则应该都被检查

        场景：决策同时违反必填字段、类型、范围多个规则
        期望：所有错误都被报告
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        # 添加多个验证规则
        coordinator.add_payload_validation_rule(
            decision_type="create_node",
            required_fields=["node_type", "node_name", "config"],
        )

        coordinator.add_payload_type_validation_rule(
            decision_type="create_node",
            field_types={"config": dict},
        )

        coordinator.add_payload_range_validation_rule(
            decision_type="create_node",
            field_ranges={"config.timeout": {"min": 0, "max": 3600}},
        )

        # 创建违反多个规则的决策
        decision = {
            "action_type": "create_node",
            "node_type": "HTTP",
            # 缺少 node_name 和 config
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False
        assert len(result.errors) >= 2  # 至少有2个错误

    def test_valid_payload_should_pass_all_rules(self):
        """合法的 payload 应该通过所有规则

        场景：决策完全符合所有验证规则
        期望：验证通过
        """
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        coordinator = CoordinatorAgent()

        coordinator.add_payload_validation_rule(
            decision_type="create_node",
            required_fields=["node_type", "node_name", "config"],
        )

        coordinator.add_payload_type_validation_rule(
            decision_type="create_node",
            field_types={"config": dict, "node_name": str},
        )

        coordinator.add_payload_enum_validation_rule(
            decision_type="create_node",
            field_enums={"node_type": ["HTTP", "LLM", "PYTHON", "DATABASE"]},
        )

        # 创建合法的决策
        decision = {
            "action_type": "create_node",
            "node_type": "HTTP",
            "node_name": "测试节点",
            "config": {"url": "http://example.com", "timeout": 30},
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is True
        assert len(result.errors) == 0


# 导出
__all__ = [
    "TestPayloadRequiredFields",
    "TestPayloadFieldTypes",
    "TestPayloadValueRanges",
    "TestPayloadValidationIntegration",
]
