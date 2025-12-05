"""
TDD 测试：自描述节点验证与结果语义化

测试范围：
1. SelfDescribingNodeValidator - 验证自描述节点定义
2. ResultSemanticParser - 解析 WorkflowAgent 返回结果
3. CoordinatorAgent 集成 - 规则审批与日志记录
"""

import logging

import pytest

# ==================== 1. 必需字段验证测试 ====================


class TestRequiredFieldValidation:
    """测试：必需字段验证"""

    @pytest.fixture
    def validator(self):
        """创建验证器实例"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        return SelfDescribingNodeValidator()

    def test_valid_node_definition_passes(self, validator):
        """测试：有效的节点定义应该通过验证"""
        node_def = {
            "name": "data_processor",
            "kind": "node",
            "executor_type": "code",
            "parameters": [{"name": "input_data", "type": "string", "required": True}],
        }

        result = validator.validate_required_fields(node_def)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_missing_name_fails(self, validator):
        """测试：缺少 name 字段应该失败"""
        node_def = {
            "kind": "node",
            "executor_type": "code",
        }

        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("name" in error.lower() for error in result.errors)

    def test_missing_executor_type_fails(self, validator):
        """测试：缺少 executor_type 字段应该失败"""
        node_def = {
            "name": "test_node",
            "kind": "node",
        }

        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("executor_type" in error.lower() for error in result.errors)

    def test_invalid_executor_type_fails(self, validator):
        """测试：无效的 executor_type 应该失败"""
        node_def = {
            "name": "test_node",
            "kind": "node",
            "executor_type": "invalid_type",
        }

        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("executor_type" in error.lower() for error in result.errors)

    def test_nested_children_require_name(self, validator):
        """测试：嵌套子节点必须有 name 字段"""
        node_def = {
            "name": "parent_node",
            "kind": "node",
            "executor_type": "parallel",
            "nested": {
                "children": [
                    {"executor_type": "code"},  # 缺少 name
                ]
            },
        }

        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("child" in error.lower() or "name" in error.lower() for error in result.errors)


# ==================== 2. 输入输出对齐验证测试 ====================


class TestInputOutputAlignment:
    """测试：输入输出对齐验证"""

    @pytest.fixture
    def validator(self):
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        return SelfDescribingNodeValidator()

    def test_parameter_type_alignment_passes(self, validator):
        """测试：参数类型与实际输入对齐应该通过"""
        node_def = {
            "name": "test_node",
            "parameters": [
                {"name": "count", "type": "integer", "required": True},
                {"name": "name", "type": "string", "required": True},
            ],
        }
        inputs = {"count": 10, "name": "test"}

        result = validator.validate_input_alignment(node_def, inputs)

        assert result.is_valid is True

    def test_missing_required_input_fails(self, validator):
        """测试：缺少必需输入应该失败"""
        node_def = {
            "name": "test_node",
            "parameters": [
                {"name": "required_param", "type": "string", "required": True},
            ],
        }
        inputs = {}  # 缺少必需参数

        result = validator.validate_input_alignment(node_def, inputs)

        assert result.is_valid is False
        assert any("required_param" in error for error in result.errors)

    def test_type_mismatch_fails(self, validator):
        """测试：类型不匹配应该失败"""
        node_def = {
            "name": "test_node",
            "parameters": [
                {"name": "count", "type": "integer", "required": True},
            ],
        }
        inputs = {"count": "not_a_number"}  # 类型错误

        result = validator.validate_input_alignment(node_def, inputs)

        assert result.is_valid is False
        assert any("type" in error.lower() or "count" in error for error in result.errors)

    def test_optional_parameter_can_be_missing(self, validator):
        """测试：可选参数可以缺失"""
        node_def = {
            "name": "test_node",
            "parameters": [
                {"name": "optional_param", "type": "string", "required": False},
            ],
        }
        inputs = {}  # 不提供可选参数

        result = validator.validate_input_alignment(node_def, inputs)

        assert result.is_valid is True

    def test_output_schema_validation(self, validator):
        """测试：输出模式验证"""
        node_def = {
            "name": "test_node",
            "output_schema": {
                "type": "object",
                "required": ["result", "status"],
            },
        }
        output = {"result": "success", "status": "completed"}

        result = validator.validate_output_alignment(node_def, output)

        assert result.is_valid is True

    def test_output_missing_required_field_fails(self, validator):
        """测试：输出缺少必需字段应该失败"""
        node_def = {
            "name": "test_node",
            "output_schema": {
                "type": "object",
                "required": ["result", "status"],
            },
        }
        output = {"result": "success"}  # 缺少 status

        result = validator.validate_output_alignment(node_def, output)

        assert result.is_valid is False


# ==================== 3. 沙箱许可验证测试 ====================


class TestSandboxPermissionValidation:
    """测试：沙箱许可验证"""

    @pytest.fixture
    def validator(self):
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        return SelfDescribingNodeValidator()

    def test_sandbox_enabled_node_passes(self, validator):
        """测试：启用沙箱的节点应该通过"""
        node_def = {
            "name": "safe_node",
            "executor_type": "code",
            "execution": {"sandbox": True},
        }

        result = validator.validate_sandbox_permission(node_def)

        assert result.is_valid is True

    def test_code_node_without_sandbox_fails(self, validator):
        """测试：代码节点未启用沙箱应该失败（默认策略）"""
        node_def = {
            "name": "unsafe_node",
            "executor_type": "code",
            "execution": {"sandbox": False},
        }

        result = validator.validate_sandbox_permission(node_def, require_sandbox=True)

        assert result.is_valid is False
        assert any("sandbox" in error.lower() for error in result.errors)

    def test_llm_node_does_not_require_sandbox(self, validator):
        """测试：LLM 节点不需要沙箱"""
        node_def = {
            "name": "llm_node",
            "executor_type": "llm",
        }

        result = validator.validate_sandbox_permission(node_def, require_sandbox=True)

        assert result.is_valid is True

    def test_dangerous_operations_blocked(self, validator):
        """测试：危险操作应该被阻止"""
        node_def = {
            "name": "dangerous_node",
            "executor_type": "code",
            "execution": {
                "sandbox": True,
                "allowed_imports": ["os", "subprocess"],  # 危险导入
            },
        }

        result = validator.validate_sandbox_permission(node_def)

        assert result.is_valid is False
        assert any("dangerous" in error.lower() or "os" in error.lower() for error in result.errors)

    def test_safe_imports_allowed(self, validator):
        """测试：安全导入应该被允许"""
        node_def = {
            "name": "safe_node",
            "executor_type": "code",
            "execution": {
                "sandbox": True,
                "allowed_imports": ["json", "math", "datetime"],
            },
        }

        result = validator.validate_sandbox_permission(node_def)

        assert result.is_valid is True


# ==================== 4. 结果语义化解析测试 ====================


class TestResultSemanticParser:
    """测试：结果语义化解析"""

    @pytest.fixture
    def parser(self):
        from src.domain.services.self_describing_node_validator import (
            ResultSemanticParser,
        )

        return ResultSemanticParser()

    def test_parse_success_result(self, parser):
        """测试：解析成功结果"""
        raw_result = {
            "success": True,
            "output": {"data": [1, 2, 3], "count": 3},
            "execution_time_ms": 150.5,
        }

        semantic_result = parser.parse(raw_result)

        assert semantic_result.status == "success"
        assert semantic_result.data == {"data": [1, 2, 3], "count": 3}
        assert semantic_result.execution_time_ms == 150.5

    def test_parse_failure_result(self, parser):
        """测试：解析失败结果"""
        raw_result = {
            "success": False,
            "error": "Division by zero",
            "output": {},
        }

        semantic_result = parser.parse(raw_result)

        assert semantic_result.status == "failure"
        assert semantic_result.error_message == "Division by zero"

    def test_parse_partial_result(self, parser):
        """测试：解析部分结果（子节点部分成功）"""
        raw_result = {
            "success": True,
            "output": {},
            "children_results": {
                "child_1": {"success": True, "output": {"value": 1}},
                "child_2": {"success": False, "error": "timeout"},
            },
        }

        semantic_result = parser.parse(raw_result)

        assert semantic_result.status == "partial"
        assert len(semantic_result.children_status) == 2
        assert semantic_result.children_status["child_1"] == "success"
        assert semantic_result.children_status["child_2"] == "failure"

    def test_parse_aggregated_output(self, parser):
        """测试：解析聚合输出"""
        raw_result = {
            "success": True,
            "output": {},
            "aggregated_output": {
                "fetch_data": {"records": 100},
                "transform_data": {"transformed": 95},
            },
        }

        semantic_result = parser.parse(raw_result)

        assert semantic_result.aggregated_data is not None
        assert "fetch_data" in semantic_result.aggregated_data
        assert "transform_data" in semantic_result.aggregated_data

    def test_semantic_result_to_dict(self, parser):
        """测试：语义结果转换为字典"""
        raw_result = {
            "success": True,
            "output": {"result": "ok"},
        }

        semantic_result = parser.parse(raw_result)
        result_dict = semantic_result.to_dict()

        assert isinstance(result_dict, dict)
        assert "status" in result_dict
        assert "data" in result_dict

    def test_semantic_result_human_readable_summary(self, parser):
        """测试：生成人类可读摘要"""
        raw_result = {
            "success": True,
            "output": {"processed": 100, "failed": 5},
            "execution_time_ms": 2500,
        }

        semantic_result = parser.parse(raw_result)
        summary = semantic_result.get_summary()

        assert isinstance(summary, str)
        assert len(summary) > 0
        # 摘要应该包含关键信息（中文或英文）
        assert "success" in summary.lower() or "成功" in summary or "完成" in summary


# ==================== 5. Coordinator 规则集成测试 ====================


class TestCoordinatorRuleIntegration:
    """测试：Coordinator 规则集成"""

    @pytest.fixture
    def coordinator(self):
        from src.domain.agents.coordinator_agent import CoordinatorAgent

        return CoordinatorAgent()

    def test_register_self_describing_node_rules(self, coordinator):
        """测试：注册自描述节点验证规则"""
        from src.domain.services.self_describing_node_validator import (
            register_self_describing_rules,
        )

        initial_rule_count = len(coordinator.rules)
        register_self_describing_rules(coordinator)

        assert len(coordinator.rules) > initial_rule_count

    def test_validate_decision_with_self_describing_node(self, coordinator):
        """测试：验证包含自描述节点的决策"""
        from src.domain.services.self_describing_node_validator import (
            register_self_describing_rules,
        )

        register_self_describing_rules(coordinator)

        decision = {
            "action": "execute_self_describing_node",
            "node_definition": {
                "name": "test_node",
                "kind": "node",
                "executor_type": "code",
                "execution": {"sandbox": True},
            },
            "inputs": {},
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is True

    def test_reject_invalid_self_describing_node(self, coordinator):
        """测试：拒绝无效的自描述节点"""
        from src.domain.services.self_describing_node_validator import (
            register_self_describing_rules,
        )

        register_self_describing_rules(coordinator)

        decision = {
            "action": "execute_self_describing_node",
            "node_definition": {
                # 缺少 name
                "kind": "node",
                "executor_type": "invalid_type",
            },
            "inputs": {},
        }

        result = coordinator.validate_decision(decision)

        assert result.is_valid is False


# ==================== 6. 审批日志测试 ====================


class TestApprovalLogging:
    """测试：审批日志记录"""

    @pytest.fixture
    def validator(self):
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        return SelfDescribingNodeValidator()

    def test_approval_log_on_success(self, validator, caplog):
        """测试：通过时记录审批日志"""
        node_def = {
            "name": "approved_node",
            "kind": "node",
            "executor_type": "code",
            "execution": {"sandbox": True},
        }

        with caplog.at_level(logging.INFO):
            result = validator.validate_with_logging(node_def)

        assert result.is_valid is True
        assert any(
            "approved" in record.message.lower() or "通过" in record.message
            for record in caplog.records
        )

    def test_rejection_log_on_failure(self, validator, caplog):
        """测试：拒绝时记录审批日志"""
        node_def = {
            "name": "rejected_node",
            "executor_type": "invalid",
        }

        with caplog.at_level(logging.WARNING):
            result = validator.validate_with_logging(node_def)

        assert result.is_valid is False
        assert any(
            "rejected" in record.message.lower() or "拒绝" in record.message
            for record in caplog.records
        )

    def test_log_includes_node_name(self, validator, caplog):
        """测试：日志包含节点名称"""
        node_def = {
            "name": "my_special_node",
            "kind": "node",
            "executor_type": "code",
            "execution": {"sandbox": True},
        }

        with caplog.at_level(logging.INFO):
            validator.validate_with_logging(node_def)

        assert any("my_special_node" in record.message for record in caplog.records)

    def test_log_includes_validation_details(self, validator, caplog):
        """测试：日志包含验证详情"""
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "execution": {"sandbox": False},  # 这会触发沙箱警告
        }

        with caplog.at_level(logging.WARNING):
            validator.validate_with_logging(node_def, require_sandbox=True)

        # 应该有关于沙箱的日志
        log_messages = " ".join(record.message for record in caplog.records)
        assert "sandbox" in log_messages.lower() or "沙箱" in log_messages


# ==================== 7. 异常处理测试 ====================


class TestExceptionHandling:
    """测试：异常处理"""

    @pytest.fixture
    def validator(self):
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        return SelfDescribingNodeValidator()

    def test_handle_none_node_definition(self, validator):
        """测试：处理 None 节点定义"""
        result = validator.validate_required_fields(None)

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_handle_empty_node_definition(self, validator):
        """测试：处理空节点定义"""
        result = validator.validate_required_fields({})

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_handle_malformed_parameters(self, validator):
        """测试：处理格式错误的参数"""
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": "not_a_list",  # 应该是列表
        }

        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False

    def test_handle_condition_function_exception(self, validator):
        """测试：处理条件函数异常"""
        # 这应该不会抛出异常，而是返回验证失败
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": [
                {"name": "param", "type": "custom_type"}  # 未知类型
            ],
        }
        inputs = {"param": object()}  # 复杂对象

        # 应该优雅地处理，而不是抛出异常
        result = validator.validate_input_alignment(node_def, inputs)

        # 结果应该是有效的（未知类型默认通过）或者是明确的失败
        assert isinstance(result.is_valid, bool)


# ==================== 8. 完整验证流程测试 ====================


class TestFullValidationFlow:
    """测试：完整验证流程"""

    @pytest.fixture
    def validator(self):
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        return SelfDescribingNodeValidator()

    def test_full_validation_all_pass(self, validator):
        """测试：完整验证全部通过"""
        node_def = {
            "name": "complete_node",
            "kind": "node",
            "description": "A complete node definition",
            "version": "1.0.0",
            "executor_type": "code",
            "language": "python",
            "parameters": [
                {"name": "input_data", "type": "string", "required": True},
                {"name": "format", "type": "string", "default": "json"},
            ],
            "execution": {
                "sandbox": True,
                "timeout_seconds": 30,
                "allowed_imports": ["json", "math"],
            },
            "output_schema": {
                "type": "object",
                "required": ["result"],
            },
        }
        inputs = {"input_data": "test data"}

        result = validator.validate_all(node_def, inputs)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_full_validation_collects_all_errors(self, validator):
        """测试：完整验证收集所有错误"""
        node_def = {
            # 缺少 name
            "executor_type": "invalid_type",  # 无效类型
            "execution": {
                "sandbox": False,  # 未启用沙箱
                "allowed_imports": ["os"],  # 危险导入
            },
            "parameters": [
                {"name": "required_param", "type": "integer", "required": True},
            ],
        }
        inputs = {}  # 缺少必需参数

        result = validator.validate_all(node_def, inputs, require_sandbox=True)

        assert result.is_valid is False
        # 应该收集多个错误
        assert len(result.errors) >= 2
