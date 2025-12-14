"""TDD RED: tests for ClassifyTaskUseCase (LLM + keyword fallback).

Coverage focus (target ~80%+ for src/application/use_cases/classify_task.py):
- execute() fallback behavior
- _classify_by_llm_with_fallback() success + failure branches
- _parse_llm_response() formats (pure JSON, ```json, embedded {}, invalid)
- keyword classification (all TaskTypes) + tool suggestion mapping
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.application.use_cases.classify_task import (
    ClassifyTaskInput,
    ClassifyTaskUseCase,
)
from src.domain.value_objects.task_type import TaskType


@pytest.fixture()
def mock_llm_client() -> Mock:
    client = Mock()
    client.invoke = Mock()
    return client


@pytest.fixture()
def use_case(mock_llm_client: Mock) -> ClassifyTaskUseCase:
    return ClassifyTaskUseCase(llm_client=mock_llm_client)


# --- Execute / Input behavior -------------------------------------------------


class TestClassifyTaskUseCase:
    def test_execute_without_llm_client_uses_keyword_fallback(self):
        """No llm_client -> keyword fallback + tool suggestions."""
        uc = ClassifyTaskUseCase(llm_client=None)
        input_data = ClassifyTaskInput(start="我有销售数据", goal="分析趋势并生成报表")

        result = uc.execute(input_data)

        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.confidence == pytest.approx(0.85)
        assert "数据分析" in result.reasoning
        assert result.suggested_tools == ["database", "http", "python"]

    def test_execute_with_input_context_none_defaults_to_empty_dict_in_prompt(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """context=None should be passed to prompt builder as {}."""
        captured = {}

        def fake_prompt(payload: dict) -> str:
            captured["payload"] = payload
            return "PROMPT"

        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            fake_prompt,
        )

        mock_llm_client.invoke.return_value = SimpleNamespace(
            content='{"task_type":"RESEARCH","confidence":0.8,"reasoning":"ok","suggested_tools":["http"]}'
        )

        input_data = ClassifyTaskInput(start="需要了解竞品", goal="调研市场信息", context=None)
        result = use_case.execute(input_data)

        assert captured["payload"]["start"] == "需要了解竞品"
        assert captured["payload"]["goal"] == "调研市场信息"
        assert captured["payload"]["context"] == {}
        mock_llm_client.invoke.assert_called_once_with("PROMPT")
        assert result.task_type == TaskType.RESEARCH

    def test_execute_with_empty_start_and_goal_returns_unknown_via_keywords(self):
        """Empty input falls through keyword rules -> UNKNOWN."""
        uc = ClassifyTaskUseCase(llm_client=None)
        input_data = ClassifyTaskInput(start="", goal="")

        result = uc.execute(input_data)

        assert result.task_type == TaskType.UNKNOWN
        assert result.confidence == pytest.approx(0.50)
        assert "未能匹配到明确" in result.reasoning
        assert result.suggested_tools == []

    def test_execute_raises_when_input_data_is_none(self):
        """Document current behavior: no input validation; None leads to AttributeError."""
        uc = ClassifyTaskUseCase(llm_client=None)

        with pytest.raises(AttributeError):
            uc.execute(None)  # type: ignore[arg-type]


# --- LLM path: success mapping ------------------------------------------------


class TestClassifyTaskUseCaseLLMSuccess:
    def test_llm_success_pure_json_maps_task_type_and_fields(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """Pure JSON response should be parsed and mapped to TaskType."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.return_value = SimpleNamespace(
            content=(
                '{"task_type":"DATA_ANALYSIS","confidence":0.92,'
                '"reasoning":"分析销售数据并生成报表","suggested_tools":["database","python"]}'
            )
        )

        input_data = ClassifyTaskInput(start="我有销售数据文件", goal="分析数据趋势并生成月度报表")
        result = use_case.execute(input_data)

        mock_llm_client.invoke.assert_called_once_with("PROMPT")
        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.confidence == pytest.approx(0.92)
        assert "分析" in result.reasoning
        assert result.suggested_tools == ["database", "python"]

    def test_llm_success_accepts_lowercase_task_type_and_maps_correctly(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """LLM may return lowercase task_type; mapping uses .upper()."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.return_value = SimpleNamespace(
            content='{"task_type":"research","confidence":0.77,"reasoning":"需要调研","suggested_tools":[]}'
        )

        result = use_case.execute(ClassifyTaskInput(start="准备新产品", goal="调研竞品功能"))

        assert result.task_type == TaskType.RESEARCH
        assert result.confidence == pytest.approx(0.77)
        assert "调研" in result.reasoning

    def test_llm_unknown_task_type_string_maps_to_unknown(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """Unrecognized task_type should map to TaskType.UNKNOWN."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.return_value = SimpleNamespace(
            content='{"task_type":"WHATEVER","confidence":0.66,"reasoning":"unclear","suggested_tools":[]}'
        )

        result = use_case.execute(ClassifyTaskInput(start="随便", goal="看看"))

        assert result.task_type == TaskType.UNKNOWN
        assert result.confidence == pytest.approx(0.66)
        assert result.suggested_tools == []

    def test_llm_success_missing_suggested_tools_defaults_to_empty_list(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """LLM may omit suggested_tools field; should default to empty list."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.return_value = SimpleNamespace(
            content='{"task_type":"RESEARCH","confidence":0.8,"reasoning":"需要调研市场"}'
        )

        result = use_case.execute(ClassifyTaskInput(start="准备新产品", goal="调研竞品功能"))

        assert result.task_type == TaskType.RESEARCH
        assert result.confidence == pytest.approx(0.8)
        assert result.reasoning == "需要调研市场"
        assert result.suggested_tools == []

    def test_llm_success_does_not_override_suggested_tools_with_keyword_tools(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """LLM path should pass through suggested_tools (no keyword tool injection)."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.return_value = SimpleNamespace(
            content=(
                '{"task_type":"DATA_ANALYSIS","confidence":0.9,'
                '"reasoning":"LLM says data analysis","suggested_tools":["custom_tool"]}'
            )
        )

        # Contains keyword triggers; if fallback happened we'd get the keyword tool list instead.
        result = use_case.execute(ClassifyTaskInput(start="分析销售数据", goal="生成报表"))

        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.suggested_tools == ["custom_tool"]


# --- LLM path: failures -> keyword fallback ----------------------------------


class TestClassifyTaskUseCaseLLMFallback:
    def test_llm_invoke_raises_falls_back_to_keywords(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """invoke() exception -> keyword fallback result + tool suggestions."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.side_effect = RuntimeError("LLM down")

        result = use_case.execute(ClassifyTaskInput(start="分析销售数据", goal="生成报表"))

        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.confidence == pytest.approx(0.85)
        assert "检测到数据分析相关关键词" in result.reasoning
        assert result.suggested_tools == ["database", "http", "python"]

    def test_llm_missing_required_fields_falls_back_to_keywords(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """Missing confidence/reasoning triggers KeyError -> fallback."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.return_value = SimpleNamespace(
            content='{"task_type":"DATA_ANALYSIS"}'
        )

        result = use_case.execute(ClassifyTaskInput(start="分析销售数据", goal="生成报表"))

        assert result.task_type == TaskType.DATA_ANALYSIS
        assert "检测到数据分析相关关键词" in result.reasoning
        assert result.suggested_tools == ["database", "http", "python"]

    def test_llm_confidence_not_float_falls_back_to_keywords(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """Non-numeric confidence triggers ValueError in float() -> fallback."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.return_value = SimpleNamespace(
            content='{"task_type":"DATA_ANALYSIS","confidence":"high","reasoning":"x"}'
        )

        result = use_case.execute(ClassifyTaskInput(start="分析销售数据", goal="生成报表"))

        assert result.task_type == TaskType.DATA_ANALYSIS
        assert "检测到数据分析相关关键词" in result.reasoning

    def test_llm_response_content_none_falls_back_to_keywords(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """Non-string response.content should trigger fallback without crashing."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.return_value = SimpleNamespace(content=None)

        result = use_case.execute(ClassifyTaskInput(start="分析销售数据", goal="生成报表"))

        assert result.task_type == TaskType.DATA_ANALYSIS
        assert result.confidence == pytest.approx(0.85)
        assert "检测到数据分析相关关键词" in result.reasoning
        assert result.suggested_tools == ["database", "http", "python"]

    def test_llm_task_type_not_string_falls_back_to_keywords(
        self, use_case: ClassifyTaskUseCase, mock_llm_client: Mock, monkeypatch: pytest.MonkeyPatch
    ):
        """task_type=None triggers AttributeError on .upper() -> fallback."""
        monkeypatch.setattr(
            "src.application.use_cases.classify_task.get_classification_prompt",
            Mock(return_value="PROMPT"),
        )
        mock_llm_client.invoke.return_value = SimpleNamespace(
            content='{"task_type":null,"confidence":0.9,"reasoning":"x"}'
        )

        result = use_case.execute(ClassifyTaskInput(start="分析销售数据", goal="生成报表"))

        assert result.task_type == TaskType.DATA_ANALYSIS
        assert "检测到数据分析相关关键词" in result.reasoning


# --- JSON parsing edge cases --------------------------------------------------


class TestClassifyTaskUseCaseParseLLMResponse:
    def test_parse_llm_response_parses_json_fenced_block(self):
        uc = ClassifyTaskUseCase(llm_client=None)
        content = """
        Here is the result:
        ```json
        {"task_type":"RESEARCH","confidence":0.8,"reasoning":"ok","suggested_tools":["http"]}
        ```
        """

        parsed = uc._parse_llm_response(content)

        assert parsed["task_type"] == "RESEARCH"
        assert parsed["confidence"] == 0.8
        assert parsed["suggested_tools"] == ["http"]

    def test_parse_llm_response_parses_embedded_braced_object(self):
        uc = ClassifyTaskUseCase(llm_client=None)
        content = (
            'Some text before {"task_type":"CONTENT_CREATION","confidence":0.81,'
            '"reasoning":"写文案","suggested_tools":["llm"]} some text after'
        )

        parsed = uc._parse_llm_response(content)

        assert parsed["task_type"] == "CONTENT_CREATION"
        assert parsed["confidence"] == 0.81
        assert parsed["reasoning"] == "写文案"

    def test_parse_llm_response_invalid_json_returns_default_unknown_payload(self):
        uc = ClassifyTaskUseCase(llm_client=None)
        content = "{ not valid json ..."

        parsed = uc._parse_llm_response(content)

        assert parsed["task_type"] == "UNKNOWN"
        assert parsed["confidence"] == 0.5
        assert "格式错误" in parsed["reasoning"]
        assert parsed["suggested_tools"] == []


# --- Keyword path: all TaskTypes + tool suggestion logic ----------------------


@pytest.mark.parametrize(
    ("start", "goal", "expected_type", "expected_confidence", "expected_tools"),
    [
        (
            "我有销售数据",
            "分析趋势并生成报表",
            TaskType.DATA_ANALYSIS,
            0.85,
            ["database", "http", "python"],
        ),
        (
            "需要发布新产品",
            "写产品介绍文案和营销内容",
            TaskType.CONTENT_CREATION,
            0.80,
            ["llm", "http"],
        ),
        ("市场情况", "调查竞品信息", TaskType.RESEARCH, 0.80, ["http", "llm", "database"]),
        (
            "系统出现异常",
            "调试并修复bug",
            TaskType.PROBLEM_SOLVING,
            0.75,
            ["llm", "database", "file"],
        ),
        (
            "设置定时流程",
            "每周自动发送周报",
            TaskType.AUTOMATION,
            0.75,
            ["http", "database", "file"],
        ),
        ("随便看看", "没什么目标", TaskType.UNKNOWN, 0.50, []),
    ],
)
def test_keyword_classification_and_tool_suggestions_by_type(
    start: str,
    goal: str,
    expected_type: TaskType,
    expected_confidence: float,
    expected_tools: list[str],
):
    """Keyword rules should classify all TaskTypes and suggest matching tools."""
    uc = ClassifyTaskUseCase(llm_client=None)
    result = uc.execute(ClassifyTaskInput(start=start, goal=goal))

    assert result.task_type == expected_type
    assert result.confidence == pytest.approx(expected_confidence)
    assert isinstance(result.reasoning, str) and result.reasoning
    assert result.suggested_tools == expected_tools
