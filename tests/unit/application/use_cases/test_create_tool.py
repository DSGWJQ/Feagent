"""TDD RED: tests for CreateToolUseCase.

Coverage focus (target ~70%+ for src/application/use_cases/create_tool.py):
- execute() success path with all fields populated
- Parameters conversion (None, empty list, populated list)
- implementation_config default (None → {})
- Domain validation propagation (empty/whitespace name → DomainError)
- Enum conversion (valid/invalid category → ValueError)
- Repository exception propagation
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.application.use_cases.create_tool import CreateToolInput, CreateToolUseCase
from src.domain.entities.tool import ToolParameter
from src.domain.exceptions import DomainError
from src.domain.value_objects.tool_category import ToolCategory


@pytest.fixture()
def mock_tool_repository() -> Mock:
    return Mock()


@pytest.fixture()
def use_case(mock_tool_repository: Mock) -> CreateToolUseCase:
    return CreateToolUseCase(tool_repository=mock_tool_repository)


# --- Success Path --------------------------------------------------------


class TestCreateToolUseCaseSuccess:
    def test_create_tool_success_with_all_fields_populated_should_create_and_save_tool(
        self, use_case: CreateToolUseCase, mock_tool_repository: Mock
    ):
        """Full happy path: valid category + parameters + explicit implementation fields.

        验证点:
        - Tool entity created with correct fields
        - Name and description are trimmed
        - Category converted to ToolCategory enum
        - Parameters converted from dict to ToolParameter objects
        - implementation_config passed through
        - Repository.save() called with created Tool
        - Returned Tool is the same instance as saved

        覆盖目标: create_tool.py:90-123
        """
        # Arrange
        input_data = CreateToolInput(
            name=" My HTTP Tool ",  # Include whitespace to verify trimming
            description=" A tool for HTTP requests ",
            category="http",  # String, will be converted to ToolCategory.HTTP
            author="alice",
            parameters=[
                {
                    "name": "url",
                    "type": "string",
                    "description": "Target URL",
                    "required": True,
                    "default": None,
                    "enum": ["option_a", "option_b"],
                }
            ],
            implementation_type="http",
            implementation_config={"base_url": "https://example.com"},
        )

        # Act
        tool = use_case.execute(input_data)

        # Assert - Tool structure
        assert tool.id.startswith("tool_"), "Tool ID should have 'tool_' prefix"
        assert tool.name == "My HTTP Tool", "Name should be trimmed"
        assert tool.description == "A tool for HTTP requests", "Description should be trimmed"
        assert tool.category == ToolCategory.HTTP, "Category should be converted to enum"
        assert tool.author == "alice"

        # Assert - Parameters conversion
        assert len(tool.parameters) == 1, "Should have 1 parameter"
        param = tool.parameters[0]
        assert isinstance(param, ToolParameter), "Parameter should be ToolParameter instance"
        assert param.name == "url"
        assert param.type == "string"
        assert param.description == "Target URL"
        assert param.required is True
        assert param.default is None
        assert param.enum == ["option_a", "option_b"]

        # Assert - Implementation config
        assert tool.implementation_type == "http"
        assert tool.implementation_config == {"base_url": "https://example.com"}

        # Assert - Repository interaction
        mock_tool_repository.save.assert_called_once_with(tool)
        saved_tool = mock_tool_repository.save.call_args[0][0]
        assert saved_tool is tool, "Saved tool should be the same instance as returned"


# --- Parameters Conversion -----------------------------------------------


class TestCreateToolUseCaseParametersConversion:
    def test_create_tool_with_none_parameters_should_create_tool_with_empty_parameters_list(
        self, use_case: CreateToolUseCase, mock_tool_repository: Mock
    ):
        """Parameters=None should result in empty tool.parameters.

        验证点:
        - parameters=None → tool.parameters == []
        - Repository.save() called

        覆盖目标: create_tool.py:93-107 (skip list comprehension branch)
        """
        # Arrange
        input_data = CreateToolInput(
            name="Tool Without Params",
            description="No parameters",
            category="http",
            author="bob",
            parameters=None,  # Explicitly None
        )

        # Act
        tool = use_case.execute(input_data)

        # Assert
        assert tool.parameters == [], "Parameters should be empty list when None"
        mock_tool_repository.save.assert_called_once()

    def test_create_tool_with_empty_parameters_list_should_treat_as_no_parameters(
        self, use_case: CreateToolUseCase, mock_tool_repository: Mock
    ):
        """Parameters=[] should result in empty tool.parameters (falsy check).

        验证点:
        - parameters=[] → tool.parameters == []
        - if input_data.parameters: branch is False for empty list

        覆盖目标: create_tool.py:95 false branch
        """
        # Arrange
        input_data = CreateToolInput(
            name="Tool With Empty Params",
            description="Empty parameters list",
            category="database",
            author="charlie",
            parameters=[],  # Empty list (falsy)
        )

        # Act
        tool = use_case.execute(input_data)

        # Assert
        assert tool.parameters == [], "Parameters should be empty list when []"
        mock_tool_repository.save.assert_called_once()


# --- Default Values ------------------------------------------------------


class TestCreateToolUseCaseDefaults:
    def test_create_tool_implementation_config_none_defaults_to_empty_dict(
        self, use_case: CreateToolUseCase, mock_tool_repository: Mock
    ):
        """implementation_config=None should default to {}.

        验证点:
        - implementation_config=None → tool.implementation_config == {}
        - Covers 'implementation_config or {}' defaulting behavior

        覆盖目标: create_tool.py:116 (or {} path)
        """
        # Arrange
        input_data = CreateToolInput(
            name="Tool With Default Config",
            description="No implementation config",
            category="file",
            author="dave",
            implementation_config=None,  # Explicitly None
        )

        # Act
        tool = use_case.execute(input_data)

        # Assert
        assert tool.implementation_config == {}, "implementation_config should default to {}"
        mock_tool_repository.save.assert_called_once_with(tool)


# --- Domain Validation ---------------------------------------------------


class TestCreateToolUseCaseDomainValidation:
    def test_create_tool_with_empty_name_raises_domain_error_and_does_not_save(
        self, use_case: CreateToolUseCase, mock_tool_repository: Mock
    ):
        """Empty name should raise DomainError from Tool.create().

        验证点:
        - name="" → DomainError("工具名称不能为空")
        - Repository.save() not called

        覆盖目标: Domain validation propagation
        """
        # Arrange
        input_data = CreateToolInput(
            name="",  # Empty name
            description="Some description",
            category="ai",
            author="eve",
        )

        # Act & Assert
        with pytest.raises(DomainError, match="工具名称不能为空"):
            use_case.execute(input_data)

        mock_tool_repository.save.assert_not_called()

    def test_create_tool_with_whitespace_name_raises_domain_error_and_does_not_save(
        self, use_case: CreateToolUseCase, mock_tool_repository: Mock
    ):
        """Whitespace-only name should raise DomainError.

        验证点:
        - name="   " → DomainError("工具名称不能为空")
        - Repository.save() not called

        覆盖目标: Domain validation with .strip() behavior
        """
        # Arrange
        input_data = CreateToolInput(
            name="   ",  # Whitespace only
            description="Some description",
            category="notification",
            author="frank",
        )

        # Act & Assert
        with pytest.raises(DomainError, match="工具名称不能为空"):
            use_case.execute(input_data)

        mock_tool_repository.save.assert_not_called()


# --- Enum Conversion -----------------------------------------------------


class TestCreateToolUseCaseEnumConversion:
    def test_create_tool_invalid_category_raises_value_error_and_does_not_save(
        self, use_case: CreateToolUseCase, mock_tool_repository: Mock
    ):
        """Invalid category should raise ValueError during enum conversion.

        验证点:
        - category="not_a_category" → ValueError
        - Repository.save() not called

        覆盖目标: create_tool.py:91 error path
        """
        # Arrange
        input_data = CreateToolInput(
            name="Tool With Invalid Category",
            description="Bad category",
            category="not_a_category",  # Invalid enum value
            author="grace",
        )

        # Act & Assert
        with pytest.raises(ValueError):
            use_case.execute(input_data)

        mock_tool_repository.save.assert_not_called()


# --- Repository Exception Propagation -----------------------------------


class TestCreateToolUseCaseRepositoryException:
    def test_repository_save_exception_propagates(
        self, use_case: CreateToolUseCase, mock_tool_repository: Mock
    ):
        """Repository exceptions should propagate (use case does not catch).

        验证点:
        - Repository.save() raises RuntimeError → propagates to caller
        - Category/parameters conversion happened before exception

        覆盖目标: create_tool.py:119-123 exception propagation
        """
        # Arrange
        mock_tool_repository.save.side_effect = RuntimeError("Database connection failed")

        input_data = CreateToolInput(
            name="Tool That Fails To Save",
            description="Will trigger repository exception",
            category="custom",
            author="helen",
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="Database connection failed"):
            use_case.execute(input_data)

        # Verify save was attempted (conversion happened)
        assert mock_tool_repository.save.call_count == 1
