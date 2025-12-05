"""ToolParameterValidator 测试 - 阶段 3

测试目标：
1. 验证必填参数缺失检测
2. 验证类型不符检测
3. 验证枚举值检测
4. 验证多余参数检测
5. 验证默认值处理
6. 验证结构化错误返回
"""

import pytest

from src.domain.entities.tool import Tool, ToolParameter
from src.domain.services.tool_parameter_validator import (
    ToolParameterValidator,
    ToolValidationError,
    ValidationErrorDetail,
    ValidationErrorType,
    ValidationResult,
)
from src.domain.value_objects.tool_category import ToolCategory

# =============================================================================
# 第一部分：ValidationErrorType 和 ValidationErrorDetail 测试
# =============================================================================


class TestValidationErrorType:
    """验证错误类型测试"""

    def test_error_type_values(self):
        """测试：错误类型枚举值"""
        assert ValidationErrorType.MISSING_REQUIRED.value == "missing_required"
        assert ValidationErrorType.TYPE_MISMATCH.value == "type_mismatch"
        assert ValidationErrorType.INVALID_ENUM.value == "invalid_enum"
        assert ValidationErrorType.EXTRA_PARAMETER.value == "extra_parameter"
        assert ValidationErrorType.CONSTRAINT_VIOLATION.value == "constraint_violation"


class TestValidationErrorDetail:
    """验证错误详情测试"""

    def test_create_error_detail(self):
        """测试：创建错误详情"""
        detail = ValidationErrorDetail(
            error_type=ValidationErrorType.MISSING_REQUIRED,
            parameter_name="url",
            message="缺少必填参数: url",
            expected=None,
            actual=None,
        )

        assert detail.error_type == ValidationErrorType.MISSING_REQUIRED
        assert detail.parameter_name == "url"
        assert "url" in detail.message

    def test_error_detail_with_expected_actual(self):
        """测试：包含期望值和实际值的错误详情"""
        detail = ValidationErrorDetail(
            error_type=ValidationErrorType.TYPE_MISMATCH,
            parameter_name="timeout",
            message="类型不匹配",
            expected="number",
            actual="string",
        )

        assert detail.expected == "number"
        assert detail.actual == "string"

    def test_error_detail_to_dict(self):
        """测试：错误详情转换为字典"""
        detail = ValidationErrorDetail(
            error_type=ValidationErrorType.INVALID_ENUM,
            parameter_name="method",
            message="枚举值无效",
            expected=["GET", "POST"],
            actual="PATCH",
        )

        d = detail.to_dict()

        assert d["error_type"] == "invalid_enum"
        assert d["parameter_name"] == "method"
        assert d["message"] == "枚举值无效"
        assert d["expected"] == ["GET", "POST"]
        assert d["actual"] == "PATCH"


# =============================================================================
# 第二部分：ValidationResult 测试
# =============================================================================


class TestValidationResult:
    """验证结果测试"""

    def test_valid_result(self):
        """测试：有效结果"""
        result = ValidationResult(is_valid=True, errors=[], validated_params={})

        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_result(self):
        """测试：无效结果"""
        error = ValidationErrorDetail(
            error_type=ValidationErrorType.MISSING_REQUIRED,
            parameter_name="url",
            message="缺少必填参数",
        )
        result = ValidationResult(is_valid=False, errors=[error], validated_params={})

        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_result_to_dict(self):
        """测试：结果转换为字典"""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            validated_params={"url": "http://example.com"},
        )

        d = result.to_dict()

        assert d["is_valid"] is True
        assert d["errors"] == []
        assert d["validated_params"]["url"] == "http://example.com"


# =============================================================================
# 第三部分：ToolValidationError 异常测试
# =============================================================================


class TestToolValidationError:
    """工具验证异常测试"""

    def test_create_validation_error(self):
        """测试：创建验证异常"""
        errors = [
            ValidationErrorDetail(
                error_type=ValidationErrorType.MISSING_REQUIRED,
                parameter_name="url",
                message="缺少必填参数: url",
            )
        ]
        error = ToolValidationError(
            tool_name="http_request",
            errors=errors,
        )

        assert error.tool_name == "http_request"
        assert len(error.errors) == 1
        assert "http_request" in str(error)

    def test_validation_error_to_dict(self):
        """测试：验证异常转换为字典"""
        errors = [
            ValidationErrorDetail(
                error_type=ValidationErrorType.TYPE_MISMATCH,
                parameter_name="timeout",
                message="类型不匹配",
                expected="number",
                actual="string",
            )
        ]
        error = ToolValidationError(
            tool_name="http_request",
            errors=errors,
        )

        d = error.to_dict()

        assert d["tool_name"] == "http_request"
        assert len(d["errors"]) == 1
        assert d["errors"][0]["parameter_name"] == "timeout"


# =============================================================================
# 第四部分：必填参数验证测试
# =============================================================================


class TestRequiredParameterValidation:
    """必填参数验证测试"""

    @pytest.fixture
    def tool_with_required_params(self):
        """创建有必填参数的工具"""
        return Tool(
            id="tool_test",
            name="test_tool",
            description="测试工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="请求URL",
                    required=True,
                ),
                ToolParameter(
                    name="method",
                    type="string",
                    description="HTTP方法",
                    required=True,
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="超时时间",
                    required=False,
                    default=30,
                ),
            ],
        )

    def test_validate_with_all_required_params(self, tool_with_required_params):
        """测试：提供所有必填参数时验证通过"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_required_params,
            {"url": "http://example.com", "method": "GET"},
        )

        assert result.is_valid is True
        assert result.errors == []

    def test_validate_missing_one_required_param(self, tool_with_required_params):
        """测试：缺少一个必填参数时验证失败"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_required_params,
            {"url": "http://example.com"},  # 缺少 method
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type == ValidationErrorType.MISSING_REQUIRED
        assert result.errors[0].parameter_name == "method"

    def test_validate_missing_all_required_params(self, tool_with_required_params):
        """测试：缺少所有必填参数时验证失败"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_required_params,
            {},  # 缺少所有参数
        )

        assert result.is_valid is False
        assert len(result.errors) == 2
        error_params = {e.parameter_name for e in result.errors}
        assert "url" in error_params
        assert "method" in error_params

    def test_validate_optional_param_not_required(self, tool_with_required_params):
        """测试：可选参数不提供时验证通过"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_required_params,
            {"url": "http://example.com", "method": "POST"},
            # 不提供可选的 timeout
        )

        assert result.is_valid is True


# =============================================================================
# 第五部分：类型验证测试
# =============================================================================


class TestTypeValidation:
    """类型验证测试"""

    @pytest.fixture
    def tool_with_various_types(self):
        """创建有多种类型参数的工具"""
        return Tool(
            id="tool_types",
            name="types_tool",
            description="类型测试工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="str_param",
                    type="string",
                    description="字符串参数",
                    required=True,
                ),
                ToolParameter(
                    name="num_param",
                    type="number",
                    description="数字参数",
                    required=True,
                ),
                ToolParameter(
                    name="bool_param",
                    type="boolean",
                    description="布尔参数",
                    required=True,
                ),
                ToolParameter(
                    name="obj_param",
                    type="object",
                    description="对象参数",
                    required=True,
                ),
                ToolParameter(
                    name="arr_param",
                    type="array",
                    description="数组参数",
                    required=True,
                ),
                ToolParameter(
                    name="any_param",
                    type="any",
                    description="任意类型参数",
                    required=True,
                ),
            ],
        )

    def test_validate_correct_types(self, tool_with_various_types):
        """测试：正确类型验证通过"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_various_types,
            {
                "str_param": "hello",
                "num_param": 42,
                "bool_param": True,
                "obj_param": {"key": "value"},
                "arr_param": [1, 2, 3],
                "any_param": "anything",
            },
        )

        assert result.is_valid is True

    def test_validate_string_type_mismatch(self, tool_with_various_types):
        """测试：字符串类型不匹配"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_various_types,
            {
                "str_param": 123,  # 应该是 string
                "num_param": 42,
                "bool_param": True,
                "obj_param": {},
                "arr_param": [],
                "any_param": "valid",
            },
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type == ValidationErrorType.TYPE_MISMATCH
        assert result.errors[0].parameter_name == "str_param"
        assert result.errors[0].expected == "string"

    def test_validate_number_type_mismatch(self, tool_with_various_types):
        """测试：数字类型不匹配"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_various_types,
            {
                "str_param": "hello",
                "num_param": "not_a_number",  # 应该是 number
                "bool_param": True,
                "obj_param": {},
                "arr_param": [],
                "any_param": "valid",
            },
        )

        assert result.is_valid is False
        assert result.errors[0].parameter_name == "num_param"

    def test_validate_boolean_type_mismatch(self, tool_with_various_types):
        """测试：布尔类型不匹配"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_various_types,
            {
                "str_param": "hello",
                "num_param": 42,
                "bool_param": "yes",  # 应该是 boolean
                "obj_param": {},
                "arr_param": [],
                "any_param": "valid",
            },
        )

        assert result.is_valid is False
        assert result.errors[0].parameter_name == "bool_param"

    def test_validate_object_type_mismatch(self, tool_with_various_types):
        """测试：对象类型不匹配"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_various_types,
            {
                "str_param": "hello",
                "num_param": 42,
                "bool_param": True,
                "obj_param": "not_object",  # 应该是 object
                "arr_param": [],
                "any_param": "valid",
            },
        )

        assert result.is_valid is False
        assert result.errors[0].parameter_name == "obj_param"

    def test_validate_array_type_mismatch(self, tool_with_various_types):
        """测试：数组类型不匹配"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_various_types,
            {
                "str_param": "hello",
                "num_param": 42,
                "bool_param": True,
                "obj_param": {},
                "arr_param": "not_array",  # 应该是 array
                "any_param": "valid",
            },
        )

        assert result.is_valid is False
        assert result.errors[0].parameter_name == "arr_param"

    def test_validate_any_type_accepts_all(self, tool_with_various_types):
        """测试：any 类型接受任何值"""
        validator = ToolParameterValidator()

        # 测试各种类型（不包括 None，因为 any_param 是必填的）
        for value in ["string", 123, True, {"key": "value"}, [1, 2]]:
            result = validator.validate(
                tool_with_various_types,
                {
                    "str_param": "hello",
                    "num_param": 42,
                    "bool_param": True,
                    "obj_param": {},
                    "arr_param": [],
                    "any_param": value,
                },
            )
            assert result.is_valid is True

    def test_validate_number_accepts_float(self, tool_with_various_types):
        """测试：number 类型接受浮点数"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_various_types,
            {
                "str_param": "hello",
                "num_param": 3.14,  # 浮点数
                "bool_param": True,
                "obj_param": {},
                "arr_param": [],
                "any_param": "valid",
            },
        )

        assert result.is_valid is True


# =============================================================================
# 第六部分：枚举值验证测试
# =============================================================================


class TestEnumValidation:
    """枚举值验证测试"""

    @pytest.fixture
    def tool_with_enum_param(self):
        """创建有枚举参数的工具"""
        return Tool(
            id="tool_enum",
            name="enum_tool",
            description="枚举测试工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="method",
                    type="string",
                    description="HTTP方法",
                    required=True,
                    enum=["GET", "POST", "PUT", "DELETE"],
                ),
                ToolParameter(
                    name="priority",
                    type="number",
                    description="优先级",
                    required=False,
                    enum=["1", "2", "3"],  # 字符串枚举用于数字
                ),
            ],
        )

    def test_validate_valid_enum_value(self, tool_with_enum_param):
        """测试：有效枚举值验证通过"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_enum_param,
            {"method": "GET"},
        )

        assert result.is_valid is True

    def test_validate_invalid_enum_value(self, tool_with_enum_param):
        """测试：无效枚举值验证失败"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_enum_param,
            {"method": "PATCH"},  # 不在枚举中
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type == ValidationErrorType.INVALID_ENUM
        assert result.errors[0].parameter_name == "method"
        assert result.errors[0].expected == ["GET", "POST", "PUT", "DELETE"]
        assert result.errors[0].actual == "PATCH"

    def test_validate_enum_case_sensitive(self, tool_with_enum_param):
        """测试：枚举值大小写敏感"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_enum_param,
            {"method": "get"},  # 小写
        )

        assert result.is_valid is False
        assert result.errors[0].error_type == ValidationErrorType.INVALID_ENUM


# =============================================================================
# 第七部分：多余参数验证测试
# =============================================================================


class TestExtraParameterValidation:
    """多余参数验证测试"""

    @pytest.fixture
    def tool_with_defined_params(self):
        """创建有定义参数的工具"""
        return Tool(
            id="tool_defined",
            name="defined_tool",
            description="定义参数测试工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="name",
                    type="string",
                    description="名称",
                    required=True,
                ),
            ],
        )

    def test_validate_extra_params_strict_mode(self, tool_with_defined_params):
        """测试：严格模式下多余参数验证失败"""
        validator = ToolParameterValidator(strict_mode=True)
        result = validator.validate(
            tool_with_defined_params,
            {
                "name": "test",
                "extra_param": "should_fail",  # 多余参数
            },
        )

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type == ValidationErrorType.EXTRA_PARAMETER
        assert result.errors[0].parameter_name == "extra_param"

    def test_validate_extra_params_lenient_mode(self, tool_with_defined_params):
        """测试：宽松模式下多余参数被忽略"""
        validator = ToolParameterValidator(strict_mode=False)
        result = validator.validate(
            tool_with_defined_params,
            {
                "name": "test",
                "extra_param": "ignored",  # 多余参数被忽略
            },
        )

        assert result.is_valid is True

    def test_validate_multiple_extra_params(self, tool_with_defined_params):
        """测试：多个多余参数"""
        validator = ToolParameterValidator(strict_mode=True)
        result = validator.validate(
            tool_with_defined_params,
            {
                "name": "test",
                "extra1": "value1",
                "extra2": "value2",
            },
        )

        assert result.is_valid is False
        assert len(result.errors) == 2
        extra_params = {e.parameter_name for e in result.errors}
        assert "extra1" in extra_params
        assert "extra2" in extra_params


# =============================================================================
# 第八部分：默认值处理测试
# =============================================================================


class TestDefaultValueHandling:
    """默认值处理测试"""

    @pytest.fixture
    def tool_with_defaults(self):
        """创建有默认值的工具"""
        return Tool(
            id="tool_defaults",
            name="defaults_tool",
            description="默认值测试工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="required_param",
                    type="string",
                    description="必填参数",
                    required=True,
                ),
                ToolParameter(
                    name="optional_with_default",
                    type="number",
                    description="有默认值的可选参数",
                    required=False,
                    default=100,
                ),
                ToolParameter(
                    name="optional_without_default",
                    type="string",
                    description="无默认值的可选参数",
                    required=False,
                ),
            ],
        )

    def test_default_value_applied(self, tool_with_defaults):
        """测试：默认值被应用"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_defaults,
            {"required_param": "test"},
        )

        assert result.is_valid is True
        assert result.validated_params["optional_with_default"] == 100

    def test_default_value_overridden(self, tool_with_defaults):
        """测试：默认值被覆盖"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_defaults,
            {
                "required_param": "test",
                "optional_with_default": 200,
            },
        )

        assert result.is_valid is True
        assert result.validated_params["optional_with_default"] == 200

    def test_optional_without_default_not_in_result(self, tool_with_defaults):
        """测试：无默认值的可选参数不在结果中"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_defaults,
            {"required_param": "test"},
        )

        assert result.is_valid is True
        assert "optional_without_default" not in result.validated_params


# =============================================================================
# 第九部分：复合错误测试
# =============================================================================


class TestMultipleValidationErrors:
    """复合错误测试"""

    @pytest.fixture
    def complex_tool(self):
        """创建复杂工具"""
        return Tool(
            id="tool_complex",
            name="complex_tool",
            description="复杂测试工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL",
                    required=True,
                ),
                ToolParameter(
                    name="method",
                    type="string",
                    description="方法",
                    required=True,
                    enum=["GET", "POST"],
                ),
                ToolParameter(
                    name="timeout",
                    type="number",
                    description="超时",
                    required=True,
                ),
            ],
        )

    def test_multiple_errors(self, complex_tool):
        """测试：多个错误同时返回"""
        validator = ToolParameterValidator()
        result = validator.validate(
            complex_tool,
            {
                # 缺少 url (MISSING_REQUIRED)
                "method": "PATCH",  # 无效枚举 (INVALID_ENUM)
                "timeout": "slow",  # 类型错误 (TYPE_MISMATCH)
            },
        )

        assert result.is_valid is False
        assert len(result.errors) == 3

        error_types = {e.error_type for e in result.errors}
        assert ValidationErrorType.MISSING_REQUIRED in error_types
        assert ValidationErrorType.INVALID_ENUM in error_types
        assert ValidationErrorType.TYPE_MISMATCH in error_types

    def test_errors_in_deterministic_order(self, complex_tool):
        """测试：错误按参数顺序返回"""
        validator = ToolParameterValidator()
        result = validator.validate(
            complex_tool,
            {},  # 缺少所有必填参数
        )

        assert result.is_valid is False
        # 按参数定义顺序返回
        assert result.errors[0].parameter_name == "url"
        assert result.errors[1].parameter_name == "method"
        assert result.errors[2].parameter_name == "timeout"


# =============================================================================
# 第十部分：validate_or_raise 测试
# =============================================================================


class TestValidateOrRaise:
    """validate_or_raise 方法测试"""

    @pytest.fixture
    def simple_tool(self):
        """创建简单工具"""
        return Tool(
            id="tool_simple",
            name="simple_tool",
            description="简单工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="input",
                    type="string",
                    description="输入",
                    required=True,
                ),
            ],
        )

    def test_validate_or_raise_valid(self, simple_tool):
        """测试：有效参数不抛出异常"""
        validator = ToolParameterValidator()
        validated = validator.validate_or_raise(
            simple_tool,
            {"input": "test"},
        )

        assert validated["input"] == "test"

    def test_validate_or_raise_invalid(self, simple_tool):
        """测试：无效参数抛出异常"""
        validator = ToolParameterValidator()

        with pytest.raises(ToolValidationError) as exc_info:
            validator.validate_or_raise(simple_tool, {})

        error = exc_info.value
        assert error.tool_name == "simple_tool"
        assert len(error.errors) == 1


# =============================================================================
# 第十一部分：工具无参数测试
# =============================================================================


class TestToolWithNoParameters:
    """无参数工具测试"""

    @pytest.fixture
    def tool_no_params(self):
        """创建无参数工具"""
        return Tool(
            id="tool_no_params",
            name="no_params_tool",
            description="无参数工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
            parameters=[],
        )

    def test_validate_empty_input(self, tool_no_params):
        """测试：空输入验证通过"""
        validator = ToolParameterValidator()
        result = validator.validate(tool_no_params, {})

        assert result.is_valid is True

    def test_validate_extra_params_for_no_param_tool(self, tool_no_params):
        """测试：无参数工具的多余参数（严格模式）"""
        validator = ToolParameterValidator(strict_mode=True)
        result = validator.validate(
            tool_no_params,
            {"unexpected": "value"},
        )

        assert result.is_valid is False
        assert result.errors[0].error_type == ValidationErrorType.EXTRA_PARAMETER


# =============================================================================
# 第十二部分：Null/None 值处理测试
# =============================================================================


class TestNullValueHandling:
    """Null/None 值处理测试"""

    @pytest.fixture
    def tool_with_optional(self):
        """创建有可选参数的工具"""
        return Tool(
            id="tool_optional",
            name="optional_tool",
            description="可选参数工具",
            category=ToolCategory.CUSTOM,
            status="draft",
            version="1.0.0",
            parameters=[
                ToolParameter(
                    name="required_str",
                    type="string",
                    description="必填字符串",
                    required=True,
                ),
                ToolParameter(
                    name="optional_str",
                    type="string",
                    description="可选字符串",
                    required=False,
                ),
            ],
        )

    def test_null_for_required_param(self, tool_with_optional):
        """测试：必填参数为 None 验证失败"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_optional,
            {"required_str": None, "optional_str": "test"},
        )

        assert result.is_valid is False
        assert result.errors[0].parameter_name == "required_str"

    def test_null_for_optional_param(self, tool_with_optional):
        """测试：可选参数为 None 验证通过"""
        validator = ToolParameterValidator()
        result = validator.validate(
            tool_with_optional,
            {"required_str": "test", "optional_str": None},
        )

        assert result.is_valid is True
