"""
SelfDescribingNodeValidator 单元测试

测试覆盖：
1. NodeValidationResult - 数据类与merge方法
2. SemanticResult - 数据类与to_dict/get_summary方法
3. SelfDescribingNodeValidator - 各验证方法
4. ResultSemanticParser - 结果解析逻辑

测试策略：
- P0测试：核心验证逻辑、错误检测、数据方法
- P1测试：边缘cases、类型验证、可选参数处理
"""


# ==================== P0 Tests: NodeValidationResult ====================


class TestNodeValidationResult:
    """NodeValidationResult 数据类测试"""

    def test_node_validation_result_merge_both_valid(self):
        """测试合并两个有效结果"""
        from src.domain.services.self_describing_node_validator import NodeValidationResult

        result1 = NodeValidationResult(is_valid=True, errors=[], warnings=["warn1"])
        result2 = NodeValidationResult(is_valid=True, errors=[], warnings=["warn2"])

        merged = result1.merge(result2)

        assert merged.is_valid is True
        assert len(merged.warnings) == 2
        assert "warn1" in merged.warnings
        assert "warn2" in merged.warnings

    def test_node_validation_result_merge_one_invalid(self):
        """测试合并一个有效和一个无效结果"""
        from src.domain.services.self_describing_node_validator import NodeValidationResult

        result1 = NodeValidationResult(is_valid=True, errors=[])
        result2 = NodeValidationResult(is_valid=False, errors=["error1"])

        merged = result1.merge(result2)

        assert merged.is_valid is False
        assert "error1" in merged.errors

    def test_node_validation_result_merge_combines_error_lists(self):
        """测试合并时错误列表正确组合"""
        from src.domain.services.self_describing_node_validator import NodeValidationResult

        result1 = NodeValidationResult(is_valid=False, errors=["error1", "error2"])
        result2 = NodeValidationResult(is_valid=False, errors=["error3"])

        merged = result1.merge(result2)

        assert len(merged.errors) == 3
        assert set(merged.errors) == {"error1", "error2", "error3"}

    def test_node_validation_result_merge_combines_warning_lists(self):
        """测试合并时警告列表正确组合"""
        from src.domain.services.self_describing_node_validator import NodeValidationResult

        result1 = NodeValidationResult(is_valid=True, warnings=["warn1"])
        result2 = NodeValidationResult(is_valid=True, warnings=["warn2", "warn3"])

        merged = result1.merge(result2)

        assert len(merged.warnings) == 3
        assert set(merged.warnings) == {"warn1", "warn2", "warn3"}

    def test_node_validation_result_merge_left_empty_right_has_messages(self):
        """P1: 测试左侧空结果与右侧有消息的合并"""
        from src.domain.services.self_describing_node_validator import NodeValidationResult

        result1 = NodeValidationResult(is_valid=True)
        result2 = NodeValidationResult(is_valid=False, errors=["error1"], warnings=["warn1"])

        merged = result1.merge(result2)

        assert merged.is_valid is False
        assert len(merged.errors) == 1
        assert len(merged.warnings) == 1

    def test_node_validation_result_merge_preserves_valid_false_when_any_invalid(self):
        """P1: 测试任一结果无效时，合并结果为无效"""
        from src.domain.services.self_describing_node_validator import NodeValidationResult

        result1 = NodeValidationResult(is_valid=True)
        result2 = NodeValidationResult(is_valid=False, errors=["critical_error"])
        result3 = NodeValidationResult(is_valid=True)

        merged = result1.merge(result2).merge(result3)

        assert merged.is_valid is False


# ==================== P0 Tests: SemanticResult ====================


class TestSemanticResult:
    """SemanticResult 数据类测试"""

    def test_semantic_result_to_dict_includes_expected_keys(self):
        """测试to_dict包含所有预期字段"""
        from src.domain.services.self_describing_node_validator import SemanticResult

        result = SemanticResult(
            status="success",
            data={"output": "test"},
            error_message="test_error",
            execution_time_ms=150.5,
            children_status={"child1": "success"},
            aggregated_data={"sum": 100},
            metadata={"key": "value"},
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "success"
        assert result_dict["data"] == {"output": "test"}
        assert result_dict["error_message"] == "test_error"
        assert result_dict["execution_time_ms"] == 150.5
        assert result_dict["children_status"] == {"child1": "success"}
        assert result_dict["aggregated_data"] == {"sum": 100}
        assert result_dict["metadata"] == {"key": "value"}

    def test_semantic_result_get_summary_success_status(self):
        """测试get_summary生成成功状态摘要"""
        from src.domain.services.self_describing_node_validator import SemanticResult

        result = SemanticResult(status="success", data={}, execution_time_ms=250.0)

        summary = result.get_summary()

        assert "执行成功" in summary
        assert "250.0ms" in summary

    def test_semantic_result_get_summary_failure_status(self):
        """测试get_summary生成失败状态摘要"""
        from src.domain.services.self_describing_node_validator import SemanticResult

        result = SemanticResult(status="failure", data={}, error_message="Connection timeout")

        summary = result.get_summary()

        assert "执行失败" in summary
        assert "错误" in summary
        assert "Connection timeout" in summary

    def test_semantic_result_to_dict_handles_none_fields(self):
        """P1: 测试to_dict处理None字段"""
        from src.domain.services.self_describing_node_validator import SemanticResult

        result = SemanticResult(
            status="success",
            data={"value": 1},
            error_message=None,
            execution_time_ms=None,
        )

        result_dict = result.to_dict()

        assert "status" in result_dict
        assert "data" in result_dict
        # None字段不应出现在字典中
        assert "error_message" not in result_dict
        assert "execution_time_ms" not in result_dict

    def test_semantic_result_get_summary_includes_error_count_when_present(self):
        """P1: 测试get_summary包含子节点状态统计"""
        from src.domain.services.self_describing_node_validator import SemanticResult

        result = SemanticResult(
            status="partial",
            data={},
            children_status={"c1": "success", "c2": "failure", "c3": "success"},
        )

        summary = result.get_summary()

        assert "子节点" in summary
        assert "2/3" in summary


# ==================== P0 Tests: SelfDescribingNodeValidator.validate_required_fields ====================


class TestSelfDescribingNodeValidatorRequiredFields:
    """SelfDescribingNodeValidator.validate_required_fields 测试"""

    def test_self_describing_node_validator_validate_required_fields_none_node_def(self):
        """测试None节点定义"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        result = validator.validate_required_fields(None)

        assert result.is_valid is False
        assert any("None" in e for e in result.errors)

    def test_self_describing_node_validator_validate_required_fields_empty_dict(self):
        """测试空字典"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        result = validator.validate_required_fields({})

        assert result.is_valid is False
        assert any("空" in e for e in result.errors)

    def test_self_describing_node_validator_validate_required_fields_missing_name(self):
        """测试缺少name字段"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {"executor_type": "code"}
        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("name" in e.lower() for e in result.errors)

    def test_self_describing_node_validator_validate_required_fields_missing_executor_type(
        self,
    ):
        """测试缺少executor_type字段"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {"name": "test_node"}
        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("executor_type" in e for e in result.errors)

    def test_self_describing_node_validator_validate_required_fields_missing_parameters(
        self,
    ):
        """测试parameters字段不是列表类型"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": "not_a_list",  # 错误类型
        }
        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("parameters" in e and "列表" in e for e in result.errors)

    def test_self_describing_node_validator_validate_required_fields_name_blank_string(
        self,
    ):
        """测试name字段为空白字符串"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {"name": "   ", "executor_type": "code"}
        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("name" in e for e in result.errors)

    def test_self_describing_node_validator_validate_required_fields_parameters_wrong_type(
        self,
    ):
        """P1: 测试parameters列表中元素类型错误"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": [{"name": "p1"}, "string_param", {"name": "p3"}],  # 中间元素错误
        }
        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("parameters[1]" in e and "字典" in e for e in result.errors)

    def test_self_describing_node_validator_validate_required_fields_executor_type_blank_string(
        self,
    ):
        """P1: 测试executor_type为无效值"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {"name": "test_node", "executor_type": "invalid_type"}
        result = validator.validate_required_fields(node_def)

        assert result.is_valid is False
        assert any("executor_type" in e and "无效" in e for e in result.errors)


# ==================== P0 Tests: SelfDescribingNodeValidator.validate_input_alignment ====================


class TestSelfDescribingNodeValidatorInputAlignment:
    """SelfDescribingNodeValidator.validate_input_alignment 测试"""

    def test_self_describing_node_validator_validate_input_alignment_missing_required_param(
        self,
    ):
        """测试缺少必需参数"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": [{"name": "required_param", "type": "string", "required": True}],
        }
        inputs = {}  # 缺少required_param
        result = validator.validate_input_alignment(node_def, inputs)

        assert result.is_valid is False
        assert any("required_param" in e for e in result.errors)

    def test_self_describing_node_validator_validate_input_alignment_type_mismatch(
        self,
    ):
        """测试参数类型不匹配"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": [{"name": "count", "type": "integer", "required": True}],
        }
        inputs = {"count": "not_an_integer"}  # 类型错误
        result = validator.validate_input_alignment(node_def, inputs)

        assert result.is_valid is False
        assert any("count" in e and "类型" in e for e in result.errors)

    def test_self_describing_node_validator_validate_input_alignment_all_required_present(
        self,
    ):
        """测试所有必需参数都提供"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": [
                {"name": "param1", "type": "string", "required": True},
                {"name": "param2", "type": "integer", "required": True},
            ],
        }
        inputs = {"param1": "value1", "param2": 42}
        result = validator.validate_input_alignment(node_def, inputs)

        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_self_describing_node_validator_validate_input_alignment_inputs_none(
        self,
    ):
        """P1: 测试inputs为空字典时跳过验证"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": "not_a_list",  # 参数定义无效
        }
        inputs = {}
        result = validator.validate_input_alignment(node_def, inputs)

        # parameters不是列表时应跳过验证
        assert result.is_valid is True

    def test_self_describing_node_validator_validate_input_alignment_allows_extra_inputs_without_error(
        self,
    ):
        """P1: 测试额外的输入参数不会导致错误"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": [{"name": "param1", "type": "string", "required": True}],
        }
        inputs = {"param1": "value1", "extra_param": "extra_value"}
        result = validator.validate_input_alignment(node_def, inputs)

        assert result.is_valid is True

    def test_self_describing_node_validator_validate_input_alignment_optional_param_missing_ok(
        self,
    ):
        """P1: 测试可选参数缺失时验证通过"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "parameters": [{"name": "optional_param", "type": "string", "required": False}],
        }
        inputs = {}  # 可选参数缺失
        result = validator.validate_input_alignment(node_def, inputs)

        assert result.is_valid is True


# ==================== P0 Tests: SelfDescribingNodeValidator.validate_output_alignment ====================


class TestSelfDescribingNodeValidatorOutputAlignment:
    """SelfDescribingNodeValidator.validate_output_alignment 测试"""

    def test_self_describing_node_validator_validate_output_alignment_missing_required_output_field(
        self,
    ):
        """测试输出缺少必需字段"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "output_schema": {"required": ["result", "status"]},
        }
        output = {"result": "value1"}  # 缺少status
        result = validator.validate_output_alignment(node_def, output)

        assert result.is_valid is False
        assert any("status" in e for e in result.errors)

    def test_self_describing_node_validator_validate_output_alignment_valid_output(
        self,
    ):
        """测试输出包含所有必需字段"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "output_schema": {"required": ["result", "status"]},
        }
        output = {"result": "value1", "status": "success", "extra_field": "extra"}
        result = validator.validate_output_alignment(node_def, output)

        assert result.is_valid is True


# ==================== P0 Tests: SelfDescribingNodeValidator.validate_sandbox_permission ====================


class TestSelfDescribingNodeValidatorSandboxPermission:
    """SelfDescribingNodeValidator.validate_sandbox_permission 测试"""

    def test_self_describing_node_validator_validate_sandbox_permission_require_sandbox_dangerous_import_detected(
        self,
    ):
        """测试检测到危险导入"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "execution": {"sandbox": True, "allowed_imports": ["os", "subprocess"]},
        }
        result = validator.validate_sandbox_permission(node_def)

        assert result.is_valid is False
        assert any("危险" in e for e in result.errors)
        assert any("os" in e or "subprocess" in e for e in result.errors)

    def test_self_describing_node_validator_validate_sandbox_permission_require_sandbox_no_dangerous_imports(
        self,
    ):
        """测试无危险导入时验证通过"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "execution": {"sandbox": True, "allowed_imports": ["json", "math"]},
        }
        result = validator.validate_sandbox_permission(node_def)

        assert result.is_valid is True

    def test_self_describing_node_validator_validate_sandbox_permission_require_sandbox_false_skips_check(
        self,
    ):
        """P1: 测试require_sandbox=False时对非沙箱节点跳过检查"""
        from src.domain.services.self_describing_node_validator import (
            SelfDescribingNodeValidator,
        )

        validator = SelfDescribingNodeValidator()
        node_def = {
            "name": "test_node",
            "executor_type": "code",
            "execution": {"sandbox": False},
        }
        result = validator.validate_sandbox_permission(node_def, require_sandbox=False)

        # 不强制要求沙箱时，未启用沙箱也应通过
        assert result.is_valid is True


# ==================== P0 Tests: ResultSemanticParser ====================


class TestResultSemanticParser:
    """ResultSemanticParser 测试"""

    def test_result_semantic_parser_parse_success_dict_status(self):
        """测试解析成功状态结果"""
        from src.domain.services.self_describing_node_validator import (
            ResultSemanticParser,
        )

        parser = ResultSemanticParser()
        raw_result = {
            "success": True,
            "output": {"value": 42},
            "execution_time_ms": 100.5,
        }

        semantic_result = parser.parse(raw_result)

        assert semantic_result.status == "success"
        assert semantic_result.data == {"value": 42}
        assert semantic_result.execution_time_ms == 100.5

    def test_result_semantic_parser_determine_status_from_exception_like_input(self):
        """测试从异常类输入确定失败状态"""
        from src.domain.services.self_describing_node_validator import (
            ResultSemanticParser,
        )

        parser = ResultSemanticParser()
        raw_result = {
            "success": False,
            "error": "Connection failed",
            "output": None,
        }

        semantic_result = parser.parse(raw_result)

        assert semantic_result.status == "failure"
        assert semantic_result.error_message == "Connection failed"
