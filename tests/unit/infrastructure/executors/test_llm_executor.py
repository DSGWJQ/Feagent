"""LlmExecutor 单元测试（P2-Infrastructure）

目标:
- 覆盖率：18.5% → 100.0% (P0 测试完成)
- 纯离线：不允许真实网络/真实 OpenAI/Anthropic 调用

测试范围（按实现分支）:
1) Prompt resolution:
   - prompt 来自 node.config["prompt"]
   - prompt 来自 inputs（当 config prompt 为空）
   - prompt 缺失 -> DomainError("LLM 节点缺少 prompt")（注意：该错误不在 try/except 内，不会被包装）
   - prompt 冲突：config 优先于 inputs
2) Model parsing:
   - "openai/gpt-4" -> provider=openai, model_name="gpt-4"
   - "gpt-4"（无斜杠）-> provider 默认 openai, model_name="gpt-4"
3) Provider dispatch:
   - openai -> _call_openai
   - anthropic -> _call_anthropic
   - google -> _call_google（未实现，DomainError 会被 execute 包装为 "LLM 调用失败: ..."）
   - unsupported -> DomainError 会被 execute 包装为 "LLM 调用失败: 不支持的 LLM 提供商: ..."
4) OpenAI structured output:
   - structuredOutput=True 且 schema 为合法 JSON -> request kwargs 包含 response_format
   - schema 非法 JSON -> 先抛 DomainError("LLM 节点 schema 格式错误: ...")，再被 execute 包装为 "LLM 调用失败: ..."
   - structuredOutput=True 且 content 是 JSON 字符串 -> json.loads(content) 返回 dict
   - structuredOutput=True 且 content 非 JSON -> 返回 raw string（fallback）
5) Import errors:
   - openai/anthropic 模块缺失 -> _call_* 抛 DomainError("未安装 ...")，再被 execute 包装为 "LLM 调用失败: ..."
6) API errors:
   - fake client 在 create() 抛异常 -> execute 统一包装为 DomainError("LLM 调用失败: ...")
7) 参数透传:
   - temperature/maxTokens 透传到 OpenAI/Anthropic 调用参数

实现策略:
- monkeypatch `sys.modules["openai"]` / `sys.modules["anthropic"]`，提供 Fake 模块对象
- FakeOpenAIAsyncClient: 暴露 `chat.completions.create(**kwargs)`（async）
- FakeAnthropicAsyncClient: 暴露 `messages.create(...)`（async）
- FakeOpenAIResponse: `choices[0].message.content`
- FakeAnthropicResponse: `content[0].text`

测试结果:
- 28 tests, 100.0% coverage (65/65 statements)
- 所有测试通过，完全离线运行
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors.llm_executor import LlmExecutor

# ====================
# Fake Objects
# ====================


@dataclass
class FakeLlmState:
    """记录 fake LLM 客户端调用状态（用于断言）。"""

    openai_api_keys: list[str | None] = field(default_factory=list)
    anthropic_api_keys: list[str | None] = field(default_factory=list)

    openai_create_calls: list[dict[str, Any]] = field(default_factory=list)
    anthropic_create_calls: list[dict[str, Any]] = field(default_factory=list)

    openai_create_error: Exception | None = None
    anthropic_create_error: Exception | None = None

    openai_content: str | None = "ok"
    anthropic_text: str = "ok"


@dataclass
class FakeOpenAIMessage:
    content: str | None


@dataclass
class FakeOpenAIChoice:
    message: FakeOpenAIMessage


@dataclass
class FakeOpenAIResponse:
    choices: list[FakeOpenAIChoice]


@dataclass
class FakeAnthropicContentBlock:
    text: str


@dataclass
class FakeAnthropicResponse:
    content: list[FakeAnthropicContentBlock]


def _make_openai_module(state: FakeLlmState) -> ModuleType:
    """构造 fake openai 模块，满足 `from openai import AsyncOpenAI`。"""

    module = ModuleType("openai")

    class _FakeChatCompletions:
        def __init__(self, _state: FakeLlmState):
            self._state = _state

        async def create(self, **kwargs: Any) -> FakeOpenAIResponse:
            self._state.openai_create_calls.append(kwargs)
            if self._state.openai_create_error is not None:
                raise self._state.openai_create_error
            return FakeOpenAIResponse(
                choices=[
                    FakeOpenAIChoice(message=FakeOpenAIMessage(content=self._state.openai_content))
                ]
            )

    class _FakeChat:
        def __init__(self, _state: FakeLlmState):
            self.completions = _FakeChatCompletions(_state)

    class AsyncOpenAI:  # noqa: N801 (匹配第三方类名)
        def __init__(self, api_key: str | None = None):
            state.openai_api_keys.append(api_key)
            self.chat = _FakeChat(state)

    module.AsyncOpenAI = AsyncOpenAI
    return module


def _make_anthropic_module(state: FakeLlmState) -> ModuleType:
    """构造 fake anthropic 模块，满足 `from anthropic import AsyncAnthropic`。"""

    module = ModuleType("anthropic")

    class _FakeMessages:
        def __init__(self, _state: FakeLlmState):
            self._state = _state

        async def create(self, **kwargs: Any) -> FakeAnthropicResponse:
            self._state.anthropic_create_calls.append(kwargs)
            if self._state.anthropic_create_error is not None:
                raise self._state.anthropic_create_error
            return FakeAnthropicResponse(
                content=[FakeAnthropicContentBlock(text=self._state.anthropic_text)]
            )

    class AsyncAnthropic:  # noqa: N801 (匹配第三方类名)
        def __init__(self, api_key: str | None = None):
            state.anthropic_api_keys.append(api_key)
            self.messages = _FakeMessages(state)

    module.AsyncAnthropic = AsyncAnthropic
    return module


# ====================
# Fixtures
# ====================


@pytest.fixture
def position() -> Position:
    """Given: 统一 Position
    When: Node.create 需要 position
    Then: 用固定值确保一致性
    """

    return Position(x=0.0, y=0.0)


@pytest.fixture
def node_factory(position: Position) -> Callable[[dict[str, Any]], Node]:
    """Given: Node.create 参数较多
    When: 传入 config 字典
    Then: 返回 LLM 节点 Node
    """

    def _factory(config: dict[str, Any]) -> Node:
        return Node.create(type=NodeType.LLM, name="TestLLMNode", config=config, position=position)

    return _factory


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLlmState:
    """Given: LlmExecutor 在方法内 import openai/anthropic
    When: monkeypatch sys.modules
    Then: 所有测试默认使用 fake SDK（离线）
    """

    state = FakeLlmState()
    monkeypatch.setitem(sys.modules, "openai", _make_openai_module(state))
    monkeypatch.setitem(sys.modules, "anthropic", _make_anthropic_module(state))
    return state


# ====================
# Tests
# ====================


class TestLlmExecutorInit:
    """测试构造函数行为。"""

    def test_init_stores_api_key(self):
        """Given: api_key 参数
        When: 初始化 LlmExecutor
        Then: api_key 被保存
        """
        executor = LlmExecutor(api_key="k")
        assert executor.api_key == "k"


class TestLlmExecutorPromptResolution:
    """测试 prompt 获取策略。"""

    @pytest.mark.asyncio
    async def test_execute_uses_prompt_from_config(self, node_factory, fake_llm: FakeLlmState):
        """Given: config 中有 prompt
        When: execute
        Then: prompt 使用 config 值，且调用 openai
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hello", "model": "openai/gpt-4"})

        result = await executor.execute(node, inputs={"ignored": "x"}, context={})

        assert result == "ok"
        assert fake_llm.openai_create_calls, "应调用 openai create()"
        kwargs = fake_llm.openai_create_calls[-1]
        assert kwargs["messages"] == [{"role": "user", "content": "hello"}]

    @pytest.mark.asyncio
    async def test_execute_uses_prompt_from_inputs_when_config_prompt_empty(
        self, node_factory, fake_llm
    ):
        """Given: config prompt 为空，inputs 非空
        When: execute
        Then: prompt 来自 inputs 的第一个值（按插入顺序）
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "", "model": "openai/gpt-4"})

        result = await executor.execute(node, inputs={"p": "from-inputs"}, context={})

        assert result == "ok"
        kwargs = fake_llm.openai_create_calls[-1]
        assert kwargs["messages"] == [{"role": "user", "content": "from-inputs"}]

    @pytest.mark.asyncio
    async def test_execute_missing_prompt_raises_domain_error(self, node_factory, fake_llm):
        """Given: config prompt 为空且 inputs 为空
        When: execute
        Then: 直接抛 DomainError（不会被包装）
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "", "model": "openai/gpt-4"})

        with pytest.raises(DomainError, match="LLM 节点缺少 prompt"):
            await executor.execute(node, inputs={}, context={})

    @pytest.mark.asyncio
    async def test_execute_config_prompt_wins_over_inputs(self, node_factory, fake_llm):
        """Given: config prompt 与 inputs 同时存在
        When: execute
        Then: config prompt 优先
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "from-config", "model": "openai/gpt-4"})

        await executor.execute(node, inputs={"p": "from-inputs"}, context={})

        kwargs = fake_llm.openai_create_calls[-1]
        assert kwargs["messages"] == [{"role": "user", "content": "from-config"}]


class TestLlmExecutorModelParsing:
    """测试 model 字符串解析逻辑。"""

    @pytest.mark.asyncio
    async def test_execute_model_with_slash_splits_provider_and_model_name(
        self, node_factory, fake_llm
    ):
        """Given: model 含 provider/model_name
        When: execute
        Then: OpenAI 调用收到 model_name（不含 provider 前缀）
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "openai/gpt-4o-mini"})

        await executor.execute(node, inputs={}, context={})

        kwargs = fake_llm.openai_create_calls[-1]
        assert kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_execute_model_without_slash_defaults_provider_openai(
        self, node_factory, fake_llm
    ):
        """Given: model 不含斜杠
        When: execute
        Then: 默认走 openai provider，model 原样传入
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "gpt-4"})

        await executor.execute(node, inputs={}, context={})

        kwargs = fake_llm.openai_create_calls[-1]
        assert kwargs["model"] == "gpt-4"


class TestLlmExecutorProviderDispatchOpenAI:
    """测试 OpenAI provider 分发与返回。"""

    @pytest.mark.asyncio
    async def test_execute_openai_returns_text_content(self, node_factory, fake_llm: FakeLlmState):
        """Given: openai 返回文本 content
        When: execute
        Then: 返回该 content
        """
        fake_llm.openai_content = "hello"
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "openai/gpt-4"})

        result = await executor.execute(node, inputs={}, context={})

        assert result == "hello"

    @pytest.mark.asyncio
    async def test_execute_openai_client_receives_api_key(
        self, node_factory, fake_llm: FakeLlmState
    ):
        """Given: executor api_key
        When: openai client 初始化
        Then: AsyncOpenAI(api_key=...) 收到相同 key
        """
        executor = LlmExecutor(api_key="k-openai")
        node = node_factory({"prompt": "hi", "model": "openai/gpt-4"})

        await executor.execute(node, inputs={}, context={})

        assert fake_llm.openai_api_keys == ["k-openai"]

    @pytest.mark.asyncio
    async def test_execute_openai_builds_messages_from_prompt(self, node_factory, fake_llm):
        """Given: prompt
        When: execute
        Then: messages = [{'role':'user','content':prompt}]
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "PROMPT", "model": "openai/gpt-4"})

        await executor.execute(node, inputs={}, context={})

        kwargs = fake_llm.openai_create_calls[-1]
        assert kwargs["messages"] == [{"role": "user", "content": "PROMPT"}]


class TestLlmExecutorProviderDispatchAnthropic:
    """测试 Anthropic provider 分发与返回。"""

    @pytest.mark.asyncio
    async def test_execute_anthropic_returns_text(self, node_factory, fake_llm: FakeLlmState):
        """Given: anthropic 返回 content[0].text
        When: execute
        Then: 返回该 text
        """
        fake_llm.anthropic_text = "claude"
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "anthropic/claude-3-5-sonnet"})

        result = await executor.execute(node, inputs={}, context={})

        assert result == "claude"
        assert fake_llm.anthropic_create_calls, "应调用 anthropic messages.create()"

    @pytest.mark.asyncio
    async def test_execute_anthropic_client_receives_api_key(
        self, node_factory, fake_llm: FakeLlmState
    ):
        """Given: executor api_key
        When: anthropic client 初始化
        Then: AsyncAnthropic(api_key=...) 收到相同 key
        """
        executor = LlmExecutor(api_key="k-anthropic")
        node = node_factory({"prompt": "hi", "model": "anthropic/claude"})

        await executor.execute(node, inputs={}, context={})

        assert fake_llm.anthropic_api_keys == ["k-anthropic"]


class TestLlmExecutorProviderDispatchGoogle:
    """测试 Google provider 的未实现行为。"""

    @pytest.mark.asyncio
    async def test_execute_google_is_wrapped_as_llm_call_failed(self, node_factory, fake_llm):
        """Given: provider=google
        When: execute
        Then: _call_google 抛 DomainError，最终被 execute 包装为 "LLM 调用失败: ..."
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "google/gemini"})

        with pytest.raises(DomainError, match=r"LLM 调用失败: Google Gemini API 暂未实现"):
            await executor.execute(node, inputs={}, context={})


class TestLlmExecutorProviderDispatchUnsupported:
    """测试不支持 provider 的行为。"""

    @pytest.mark.asyncio
    async def test_execute_unsupported_provider_is_wrapped(self, node_factory, fake_llm):
        """Given: provider=foo
        When: execute
        Then: DomainError 被包装为 "LLM 调用失败: 不支持的 LLM 提供商: foo"
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "foo/bar"})

        with pytest.raises(DomainError, match=r"LLM 调用失败: 不支持的 LLM 提供商: foo"):
            await executor.execute(node, inputs={}, context={})


class TestLlmExecutorOpenAIStructuredOutputSchema:
    """测试 OpenAI structured output + schema 解析与请求参数构建。"""

    @pytest.mark.asyncio
    async def test_openai_structured_output_valid_schema_sets_response_format(
        self, node_factory, fake_llm
    ):
        """Given: structuredOutput=True 且 schema 为合法 JSON
        When: execute
        Then: openai kwargs 包含 response_format.json_schema
        """
        executor = LlmExecutor(api_key="k")
        schema = {
            "name": "t",
            "schema": {"type": "object", "properties": {"a": {"type": "number"}}},
        }
        node = node_factory(
            {
                "prompt": "hi",
                "model": "openai/gpt-4",
                "structuredOutput": True,
                "schema": json.dumps(schema),
            }
        )

        await executor.execute(node, inputs={}, context={})

        kwargs = fake_llm.openai_create_calls[-1]
        assert "response_format" in kwargs
        assert kwargs["response_format"]["type"] == "json_schema"
        assert kwargs["response_format"]["json_schema"] == schema

    @pytest.mark.asyncio
    async def test_openai_structured_output_true_but_empty_schema_does_not_set_response_format(
        self, node_factory, fake_llm
    ):
        """Given: structuredOutput=True 但 schema 为空字符串
        When: execute
        Then: 不应设置 response_format
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory(
            {
                "prompt": "hi",
                "model": "openai/gpt-4",
                "structuredOutput": True,
                "schema": "",
            }
        )

        await executor.execute(node, inputs={}, context={})

        kwargs = fake_llm.openai_create_calls[-1]
        assert "response_format" not in kwargs

    @pytest.mark.asyncio
    async def test_openai_structured_output_invalid_schema_is_wrapped(self, node_factory, fake_llm):
        """Given: schema 非法 JSON
        When: execute
        Then: schema 格式错误 DomainError 会被 execute 包装为 "LLM 调用失败: ..."
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory(
            {
                "prompt": "hi",
                "model": "openai/gpt-4",
                "structuredOutput": True,
                "schema": "{invalid",
            }
        )

        with pytest.raises(DomainError, match=r"LLM 调用失败: LLM 节点 schema 格式错误:"):
            await executor.execute(node, inputs={}, context={})


class TestLlmExecutorOpenAIStructuredOutputParsing:
    """测试 structured output 的返回解析（JSON -> dict；非 JSON -> raw）。"""

    @pytest.mark.asyncio
    async def test_openai_structured_output_parses_json_content_to_dict(
        self, node_factory, fake_llm: FakeLlmState
    ):
        """Given: structuredOutput=True 且返回 content 是 JSON 字符串
        When: execute
        Then: 返回 dict（json.loads(content)）
        """
        fake_llm.openai_content = '{"a": 1, "b": "x"}'
        executor = LlmExecutor(api_key="k")
        node = node_factory(
            {
                "prompt": "hi",
                "model": "openai/gpt-4",
                "structuredOutput": True,
                "schema": '{"type":"object"}',
            }
        )

        result = await executor.execute(node, inputs={}, context={})

        assert result == {"a": 1, "b": "x"}

    @pytest.mark.asyncio
    async def test_openai_structured_output_invalid_json_content_returns_raw_string(
        self, node_factory, fake_llm: FakeLlmState
    ):
        """Given: structuredOutput=True 但 content 不是 JSON
        When: execute
        Then: 返回 raw string（fallback）
        """
        fake_llm.openai_content = "not-json"
        executor = LlmExecutor(api_key="k")
        node = node_factory(
            {
                "prompt": "hi",
                "model": "openai/gpt-4",
                "structuredOutput": True,
                "schema": '{"type":"object"}',
            }
        )

        result = await executor.execute(node, inputs={}, context={})

        assert result == "not-json"

    @pytest.mark.asyncio
    async def test_openai_structured_output_content_none_returns_none(
        self, node_factory, fake_llm: FakeLlmState
    ):
        """Given: structuredOutput=True 且 content=None
        When: execute
        Then: content 为 falsy，不进入 json.loads(content)，返回 None
        """
        fake_llm.openai_content = None
        executor = LlmExecutor(api_key="k")
        node = node_factory(
            {
                "prompt": "hi",
                "model": "openai/gpt-4",
                "structuredOutput": True,
                "schema": '{"type":"object"}',
            }
        )

        result = await executor.execute(node, inputs={}, context={})

        assert result is None


class TestLlmExecutorOpenAIImportAndApiErrors:
    """测试 OpenAI import error 与 API error 的包装。"""

    @pytest.mark.asyncio
    async def test_openai_import_error_is_wrapped(
        self, node_factory, monkeypatch: pytest.MonkeyPatch
    ):
        """Given: sys.modules 中没有 openai
        When: 执行 openai provider
        Then: _call_openai 抛 DomainError("未安装 openai ...")，被 execute 包装为 "LLM 调用失败: ..."
        """
        # Mock __import__ to truly block openai import
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "openai" or name.startswith("openai."):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        monkeypatch.delitem(sys.modules, "openai", raising=False)
        monkeypatch.delitem(sys.modules, "anthropic", raising=False)

        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "openai/gpt-4"})

        with pytest.raises(DomainError, match=r"LLM 调用失败: 未安装 openai 库"):
            await executor.execute(node, inputs={}, context={})

    @pytest.mark.asyncio
    async def test_openai_api_error_is_wrapped(self, node_factory, fake_llm: FakeLlmState):
        """Given: openai chat.completions.create 抛异常（如 rate limit）
        When: execute
        Then: 被包装为 DomainError("LLM 调用失败: ...")
        """
        fake_llm.openai_create_error = RuntimeError("rate limit")
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "openai/gpt-4"})

        with pytest.raises(DomainError, match=r"LLM 调用失败: rate limit"):
            await executor.execute(node, inputs={}, context={})


class TestLlmExecutorAnthropicImportAndApiErrors:
    """测试 Anthropic import error 与 API error 的包装。"""

    @pytest.mark.asyncio
    async def test_anthropic_import_error_is_wrapped(
        self, node_factory, monkeypatch: pytest.MonkeyPatch
    ):
        """Given: sys.modules 中没有 anthropic
        When: 执行 anthropic provider
        Then: _call_anthropic 抛 DomainError("未安装 anthropic ...")，被 execute 包装为 "LLM 调用失败: ..."
        """
        # Mock __import__ to truly block anthropic import
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "anthropic" or name.startswith("anthropic."):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        monkeypatch.delitem(sys.modules, "openai", raising=False)
        monkeypatch.delitem(sys.modules, "anthropic", raising=False)

        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "anthropic/claude"})

        with pytest.raises(DomainError, match=r"LLM 调用失败: 未安装 anthropic 库"):
            await executor.execute(node, inputs={}, context={})

    @pytest.mark.asyncio
    async def test_anthropic_api_error_is_wrapped(self, node_factory, fake_llm: FakeLlmState):
        """Given: anthropic messages.create 抛异常（如 timeout）
        When: execute
        Then: 被包装为 DomainError("LLM 调用失败: ...")
        """
        fake_llm.anthropic_create_error = TimeoutError("timeout")
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "anthropic/claude"})

        with pytest.raises(DomainError, match=r"LLM 调用失败: timeout"):
            await executor.execute(node, inputs={}, context={})


class TestLlmExecutorParameterPropagation:
    """测试 temperature/maxTokens 参数透传（OpenAI/Anthropic）。"""

    @pytest.mark.asyncio
    async def test_openai_temperature_and_max_tokens_are_propagated(self, node_factory, fake_llm):
        """Given: 自定义 temperature/maxTokens
        When: openai 调用
        Then: kwargs 中 temperature/max_tokens 等于配置值
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory(
            {
                "prompt": "hi",
                "model": "openai/gpt-4",
                "temperature": 0.12,
                "maxTokens": 123,
            }
        )

        await executor.execute(node, inputs={}, context={})

        kwargs = fake_llm.openai_create_calls[-1]
        assert kwargs["temperature"] == 0.12
        assert kwargs["max_tokens"] == 123

    @pytest.mark.asyncio
    async def test_openai_defaults_are_used_when_missing(self, node_factory, fake_llm):
        """Given: 未提供 temperature/maxTokens
        When: openai 调用
        Then: 使用默认值 0.7 / 2000
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "hi", "model": "openai/gpt-4"})

        await executor.execute(node, inputs={}, context={})

        kwargs = fake_llm.openai_create_calls[-1]
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_anthropic_temperature_and_max_tokens_are_propagated(
        self, node_factory, fake_llm
    ):
        """Given: 自定义 temperature/maxTokens
        When: anthropic 调用
        Then: create() 收到对应参数
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory(
            {
                "prompt": "hi",
                "model": "anthropic/claude",
                "temperature": 0.33,
                "maxTokens": 777,
            }
        )

        await executor.execute(node, inputs={}, context={})

        kwargs = fake_llm.anthropic_create_calls[-1]
        assert kwargs["temperature"] == 0.33
        assert kwargs["max_tokens"] == 777

    @pytest.mark.asyncio
    async def test_prompt_from_inputs_is_stringified(self, node_factory, fake_llm):
        """Given: inputs 中的 prompt 值不是字符串（例如 dict）
        When: config prompt 为空时取 inputs 第一个值并 str() 化
        Then: messages content 等于 str(value)
        """
        executor = LlmExecutor(api_key="k")
        node = node_factory({"prompt": "", "model": "openai/gpt-4"})

        value = {"a": 1}
        await executor.execute(node, inputs={"x": value}, context={})

        kwargs = fake_llm.openai_create_calls[-1]
        assert kwargs["messages"] == [{"role": "user", "content": str(value)}]
