"""HttpExecutor 单元测试（P2-Infrastructure）

测试范围:
1. Config Validation: URL必填验证
2. Headers Parsing: valid/invalid/empty/None/non-dict JSON
3. Body Parsing: POST/PUT/PATCH解析、GET/DELETE忽略body、invalid JSON处理
4. Response Handling: JSON response成功、text fallback
5. Error Handling: HTTPStatusError、RequestError、状态码变体
6. Method Variants: GET/POST/DELETE、method大小写转换
7. Timeout Configuration: timeout传递到httpx
8. Request Shape: 完整参数验证
9. Regression Guards: 默认值、边界情况
10. P0 Count Sanity: 烟雾测试

测试原则:
- 使用 monkeypatch 隔离 httpx.AsyncClient（不依赖真实网络）
- Fake objects pattern: _FakeResponse、_FakeAsyncClient、_FakeHTTPXState
- Given/When/Then 中文 docstring
- pytest.mark.asyncio 覆盖所有 async 测试

测试结果:
- 28 tests, 100.0% coverage (36/36 statements)
- 所有测试通过，完全离线运行
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from src.domain.entities.node import Node
from src.domain.exceptions import DomainError
from src.domain.value_objects.node_type import NodeType
from src.domain.value_objects.position import Position
from src.infrastructure.executors.http_executor import HttpExecutor

# ====================
# Fake Objects
# ====================


@dataclass
class _FakeHTTPXState:
    """记录 httpx 调用状态"""

    init_timeouts: list[Any] = field(default_factory=list)
    request_calls: list[dict[str, Any]] = field(default_factory=list)


class _FakeResponse:
    """模拟 httpx.Response 对象"""

    def __init__(
        self,
        *,
        status_code: int = 200,
        text: str = "",
        json_value: Any = None,
        json_raises_decode_error: bool = False,
    ):
        self.status_code = status_code
        self.text = text
        self._json_value = json_value
        self._json_raises_decode_error = json_raises_decode_error

    def raise_for_status(self) -> None:
        """模拟 httpx.Response.raise_for_status()"""
        if self.status_code >= 400:
            # 模拟 HTTPStatusError
            import httpx

            request = httpx.Request("GET", "https://example.com")
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=request, response=self)

    def json(self) -> Any:
        """模拟 httpx.Response.json()"""
        if self._json_raises_decode_error:
            raise json.JSONDecodeError("Expecting value", "", 0)
        return self._json_value


class _FakeAsyncClient:
    """模拟 httpx.AsyncClient"""

    def __init__(
        self,
        *,
        state: _FakeHTTPXState,
        response: _FakeResponse | None = None,
        raises_request_error: bool = False,
        raises_invalid_url: bool = False,
        timeout: Any = None,
    ):
        self.state = state
        self.response = response or _FakeResponse()
        self.raises_request_error = raises_request_error
        self.raises_invalid_url = raises_invalid_url

        # 记录 timeout 参数
        self.state.init_timeouts.append(timeout)

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def request(
        self, method: str, url: str, headers: dict | None = None, json: Any = None
    ) -> _FakeResponse:
        """模拟 httpx.AsyncClient.request()"""
        # 记录调用参数
        self.state.request_calls.append(
            {"method": method, "url": url, "headers": headers, "json": json}
        )

        # 模拟 InvalidURL（不是RequestError的子类，直接抛出）
        if self.raises_invalid_url:
            import httpx

            raise httpx.InvalidURL("Invalid URL format")

        # 模拟 RequestError
        if self.raises_request_error:
            import httpx

            raise httpx.RequestError("Network error")

        return self.response


# ====================
# Fixtures
# ====================


@pytest.fixture
def position() -> Position:
    """共享的Position对象"""
    return Position(x=0.0, y=0.0)


@pytest.fixture
def node_factory(position: Position):
    """Node工厂函数，简化节点创建"""

    def _factory(config: dict[str, Any]) -> Node:
        node = Node.create(
            type=NodeType.HTTP, name="TestHTTPNode", config=config, position=position
        )
        return node

    return _factory


@pytest.fixture
def fake_httpx(monkeypatch: pytest.MonkeyPatch):
    """monkeypatch httpx.AsyncClient，返回状态记录器"""

    def _fake_httpx(
        response: _FakeResponse | None = None,
        raises_request_error: bool = False,
        raises_invalid_url: bool = False,
    ) -> _FakeHTTPXState:
        state = _FakeHTTPXState()

        def _fake_async_client_factory(timeout: Any = None):
            return _FakeAsyncClient(
                state=state,
                response=response,
                raises_request_error=raises_request_error,
                raises_invalid_url=raises_invalid_url,
                timeout=timeout,
            )

        import httpx

        monkeypatch.setattr(httpx, "AsyncClient", _fake_async_client_factory)
        return state

    return _fake_httpx


# ====================
# 测试类：Config Validation（配置验证）
# ====================


class TestHttpExecutorConfigValidation:
    """测试配置验证功能"""

    @pytest.mark.asyncio
    async def test_execute_missing_url_raises_domain_error(self, node_factory, fake_httpx):
        """
        测试：未配置 url 应抛出 DomainError

        Given: 节点配置中缺少 url 字段
        When: 执行 HttpExecutor.execute
        Then: 抛出 DomainError，消息为 "HTTP 节点缺少 URL 配置"
        """
        # Given
        fake_httpx()
        executor = HttpExecutor()
        node = node_factory({"method": "GET"})

        # When & Then
        with pytest.raises(DomainError, match="HTTP 节点缺少 URL 配置"):
            await executor.execute(node, {}, {})

    @pytest.mark.asyncio
    async def test_execute_valid_config_passes(self, node_factory, fake_httpx):
        """
        测试：有效配置应成功执行

        Given: 节点配置包含必填字段 url
        When: 执行 HttpExecutor.execute
        Then: 不抛出异常，成功发起 HTTP 请求
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When
        result = await executor.execute(node, {}, {})

        # Then
        assert result == {"ok": True}
        assert len(state.request_calls) == 1
        assert state.request_calls[0]["url"] == "https://example.com/api"


# ====================
# 测试类：Headers Parsing（Headers解析）
# ====================


class TestHttpExecutorHeadersParsing:
    """测试 headers 解析功能"""

    @pytest.mark.asyncio
    async def test_execute_valid_headers_json(self, node_factory, fake_httpx):
        """
        测试：有效的 headers JSON 应被正确解析

        Given: headers 为合法 JSON 字符串
        When: 执行 HttpExecutor.execute
        Then: headers 应被正确解析并传递给 httpx
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory(
            {
                "url": "https://example.com/api",
                "method": "GET",
                "headers": '{"Authorization": "Bearer token123"}',
            }
        )

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["headers"] == {"Authorization": "Bearer token123"}

    @pytest.mark.asyncio
    async def test_execute_invalid_headers_json_raises_domain_error(self, node_factory, fake_httpx):
        """
        测试：无效的 headers JSON 应抛出 DomainError

        Given: headers 为无效 JSON 字符串
        When: 执行 HttpExecutor.execute
        Then: 抛出 DomainError，消息包含 "headers 格式错误"
        """
        # Given
        fake_httpx()
        executor = HttpExecutor()
        node = node_factory(
            {"url": "https://example.com/api", "method": "GET", "headers": "{invalid"}
        )

        # When & Then
        with pytest.raises(DomainError, match=r"HTTP 节点 headers 格式错误"):
            await executor.execute(node, {}, {})

    @pytest.mark.asyncio
    async def test_execute_empty_headers_string_uses_empty_dict(self, node_factory, fake_httpx):
        """
        测试：空 headers 字符串应使用空字典

        Given: headers 为空字符串 ""
        When: 执行 HttpExecutor.execute
        Then: headers 应为空字典 {}
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET", "headers": ""})

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["headers"] == {}

    @pytest.mark.asyncio
    async def test_execute_missing_headers_defaults_to_empty_dict(self, node_factory, fake_httpx):
        """
        测试：缺失 headers 字段应默认为空字典

        Given: 配置中不包含 headers 字段
        When: 执行 HttpExecutor.execute
        Then: headers 应为空字典 {}
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["headers"] == {}

    @pytest.mark.asyncio
    async def test_execute_headers_non_dict_json_raises_domain_error(
        self, node_factory, fake_httpx
    ):
        """
        测试：headers JSON 为非字典类型应抛出 DomainError

        Given: headers 为合法 JSON 但不是字典（如数组）
        When: 执行 HttpExecutor.execute
        Then: 抛出 DomainError（不把非法 headers 透传给 httpx）
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory(
            {"url": "https://example.com/api", "method": "GET", "headers": '["not", "a", "dict"]'}
        )

        # When & Then
        with pytest.raises(DomainError, match=r"HTTP 节点 headers 必须是 JSON 对象"):
            await executor.execute(node, {}, {})

        # Then: 不应发出请求
        assert state.request_calls == []


# ====================
# 测试类：Body Parsing（Body解析）
# ====================


class TestHttpExecutorBodyParsing:
    """测试 body 解析功能（POST/PUT/PATCH vs GET/DELETE）"""

    @pytest.mark.asyncio
    async def test_execute_post_with_valid_body_json(self, node_factory, fake_httpx):
        """
        测试：POST 请求应解析 body JSON

        Given: method=POST，body 为合法 JSON 字符串
        When: 执行 HttpExecutor.execute
        Then: body 应被解析并传递给 httpx
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"created": True}))
        executor = HttpExecutor()
        node = node_factory(
            {
                "url": "https://example.com/api",
                "method": "POST",
                "body": '{"name": "test", "value": 42}',
            }
        )

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["json"] == {"name": "test", "value": 42}

    @pytest.mark.asyncio
    async def test_execute_patch_with_valid_body_json(self, node_factory, fake_httpx):
        """
        测试：PATCH 请求应解析 body JSON

        Given: method=PATCH，body 为合法 JSON 字符串
        When: 执行 HttpExecutor.execute
        Then: body 应被解析并传递给 httpx
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"updated": True}))
        executor = HttpExecutor()
        node = node_factory(
            {"url": "https://example.com/api", "method": "PATCH", "body": '{"status": "active"}'}
        )

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["json"] == {"status": "active"}

    @pytest.mark.asyncio
    async def test_execute_post_with_invalid_body_json_raises_domain_error(
        self, node_factory, fake_httpx
    ):
        """
        测试：POST 请求 body 无效 JSON 应抛出 DomainError

        Given: method=POST，body 为无效 JSON 字符串
        When: 执行 HttpExecutor.execute
        Then: 抛出 DomainError，消息包含 "body 格式错误"
        """
        # Given
        fake_httpx()
        executor = HttpExecutor()
        node = node_factory(
            {"url": "https://example.com/api", "method": "POST", "body": "{invalid"}
        )

        # When & Then
        with pytest.raises(DomainError, match=r"HTTP 节点 body 格式错误"):
            await executor.execute(node, {}, {})

    @pytest.mark.asyncio
    async def test_execute_get_ignores_body_even_if_invalid_json(self, node_factory, fake_httpx):
        """
        测试：GET 请求应忽略 body（即使 JSON 无效）

        Given: method=GET，body 为无效 JSON 字符串
        When: 执行 HttpExecutor.execute
        Then: 不抛出异常，body 应为 None
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET", "body": "{invalid"})

        # When
        result = await executor.execute(node, {}, {})

        # Then
        assert result == {"ok": True}
        assert state.request_calls[0]["json"] is None

    @pytest.mark.asyncio
    async def test_execute_delete_ignores_body(self, node_factory, fake_httpx):
        """
        测试：DELETE 请求应忽略 body

        Given: method=DELETE，body 为有效 JSON 字符串
        When: 执行 HttpExecutor.execute
        Then: body 应为 None（不传递给 httpx）
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=204, text=""))
        executor = HttpExecutor()
        node = node_factory(
            {"url": "https://example.com/api", "method": "DELETE", "body": '{"id": "123"}'}
        )

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["json"] is None


# ====================
# 测试类：Response Handling（响应处理）
# ====================


class TestHttpExecutorResponseHandling:
    """测试 HTTP 响应处理（JSON vs text fallback）"""

    @pytest.mark.asyncio
    async def test_execute_json_response_returns_parsed_json(self, node_factory, fake_httpx):
        """
        测试：JSON 响应应返回解析后的 JSON 对象

        Given: httpx 返回可解析的 JSON 响应
        When: 执行 HttpExecutor.execute
        Then: 返回解析后的 JSON 对象
        """
        # Given
        fake_httpx(response=_FakeResponse(status_code=200, json_value={"result": "success"}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When
        result = await executor.execute(node, {}, {})

        # Then
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_execute_json_decode_error_falls_back_to_text(self, node_factory, fake_httpx):
        """
        测试：JSON 解析失败应返回 text

        Given: httpx 返回无法解析为 JSON 的响应
        When: 执行 HttpExecutor.execute
        Then: 返回 response.text
        """
        # Given
        fake_httpx(
            response=_FakeResponse(
                status_code=200, text="<html>Not JSON</html>", json_raises_decode_error=True
            )
        )
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When
        result = await executor.execute(node, {}, {})

        # Then
        assert result == "<html>Not JSON</html>"


# ====================
# 测试类：Error Handling（错误处理）
# ====================


class TestHttpExecutorErrorHandling:
    """测试 HTTP 错误处理（HTTPStatusError、RequestError）"""

    @pytest.mark.asyncio
    async def test_execute_http_status_error_raises_domain_error(self, node_factory, fake_httpx):
        """
        测试：HTTP 4xx/5xx 应抛出 DomainError

        Given: httpx 返回 404 状态码
        When: 执行 HttpExecutor.execute
        Then: 抛出 DomainError，消息包含 "HTTP 请求失败"
        """
        # Given
        fake_httpx(response=_FakeResponse(status_code=404, text="Not Found"))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When & Then
        with pytest.raises(DomainError, match=r"HTTP 请求失败: 404"):
            await executor.execute(node, {}, {})

    @pytest.mark.asyncio
    async def test_execute_request_error_raises_domain_error(self, node_factory, fake_httpx):
        """
        测试：网络错误应抛出 DomainError

        Given: httpx 抛出 RequestError（如网络不可达）
        When: 执行 HttpExecutor.execute
        Then: 抛出 DomainError，消息包含 "HTTP 请求错误"
        """
        # Given
        fake_httpx(raises_request_error=True)
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When & Then
        with pytest.raises(DomainError, match=r"HTTP 请求错误"):
            await executor.execute(node, {}, {})

    @pytest.mark.asyncio
    async def test_execute_500_error_raises_domain_error(self, node_factory, fake_httpx):
        """
        测试：HTTP 500 应抛出 DomainError

        Given: httpx 返回 500 状态码
        When: 执行 HttpExecutor.execute
        Then: 抛出 DomainError，消息包含 "HTTP 请求失败: 500"
        """
        # Given
        fake_httpx(response=_FakeResponse(status_code=500, text="Internal Server Error"))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When & Then
        with pytest.raises(DomainError, match=r"HTTP 请求失败: 500"):
            await executor.execute(node, {}, {})

    @pytest.mark.asyncio
    async def test_execute_invalid_url_raises_domain_error(self, node_factory, fake_httpx):
        """
        测试：httpx.InvalidURL 应被转换为 DomainError

        Given: httpx 抛出 InvalidURL（不是 RequestError 的子类）
        When: 执行 HttpExecutor.execute
        Then: 抛出 DomainError（不泄漏 httpx 异常类型）
        """
        # Given
        fake_httpx(raises_invalid_url=True)
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When & Then
        with pytest.raises(DomainError, match=r"HTTP 节点 URL 格式错误"):
            await executor.execute(node, {}, {})


# ====================
# 测试类：Method Variants（方法变体）
# ====================


class TestHttpExecutorMethodVariants:
    """测试不同 HTTP 方法（GET/POST/DELETE/...）"""

    @pytest.mark.asyncio
    async def test_execute_get_method(self, node_factory, fake_httpx):
        """
        测试：GET 方法应成功执行

        Given: method=GET
        When: 执行 HttpExecutor.execute
        Then: httpx 应使用 GET 方法
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"data": []}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["method"] == "GET"

    @pytest.mark.asyncio
    async def test_execute_post_method(self, node_factory, fake_httpx):
        """
        测试：POST 方法应成功执行

        Given: method=POST
        When: 执行 HttpExecutor.execute
        Then: httpx 应使用 POST 方法
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=201, json_value={"id": "123"}))
        executor = HttpExecutor()
        node = node_factory(
            {"url": "https://example.com/api", "method": "POST", "body": '{"name": "test"}'}
        )

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["method"] == "POST"

    @pytest.mark.asyncio
    async def test_execute_delete_method(self, node_factory, fake_httpx):
        """
        测试：DELETE 方法应成功执行

        Given: method=DELETE
        When: 执行 HttpExecutor.execute
        Then: httpx 应使用 DELETE 方法
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=204, text=""))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api/item/123", "method": "DELETE"})

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["method"] == "DELETE"

    @pytest.mark.asyncio
    async def test_execute_method_lowercase_is_uppercased(self, node_factory, fake_httpx):
        """
        测试：小写 method 应转换为大写

        Given: method="get"（小写）
        When: 执行 HttpExecutor.execute
        Then: httpx 应收到 "GET"（大写）
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "get"})

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["method"] == "GET"


# ====================
# 测试类：Timeout Configuration（超时配置）
# ====================


class TestHttpExecutorTimeoutConfiguration:
    """测试 timeout 配置传递"""

    @pytest.mark.asyncio
    async def test_execute_timeout_passed_to_httpx(self, node_factory, fake_httpx):
        """
        测试：timeout 应传递给 httpx.AsyncClient

        Given: HttpExecutor 初始化时设置 timeout=60.0
        When: 执行 HttpExecutor.execute
        Then: httpx.AsyncClient 应收到 timeout=60.0
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor(timeout=60.0)
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When
        await executor.execute(node, {}, {})

        # Then
        assert len(state.init_timeouts) == 1
        assert state.init_timeouts[0] == 60.0


# ====================
# 测试类：Request Shape（请求形状）
# ====================


class TestHttpExecutorRequestShape:
    """测试完整的请求参数传递"""

    @pytest.mark.asyncio
    async def test_execute_comprehensive_request_parameters(self, node_factory, fake_httpx):
        """
        测试：完整请求参数应正确传递

        Given: 配置包含 url、method、headers、body
        When: 执行 HttpExecutor.execute
        Then: httpx 应收到所有参数
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory(
            {
                "url": "https://example.com/api/resource",
                "method": "POST",
                "headers": '{"Authorization": "Bearer token", "Content-Type": "application/json"}',
                "body": '{"key": "value", "number": 123}',
            }
        )

        # When
        await executor.execute(node, {}, {})

        # Then
        call = state.request_calls[0]
        assert call["method"] == "POST"
        assert call["url"] == "https://example.com/api/resource"
        assert call["headers"] == {
            "Authorization": "Bearer token",
            "Content-Type": "application/json",
        }
        assert call["json"] == {"key": "value", "number": 123}


# ====================
# 测试类：Regression Guards（回归守卫）
# ====================


class TestHttpExecutorRegressionGuards:
    """测试边界情况和回归守卫"""

    @pytest.mark.asyncio
    async def test_execute_default_method_is_get(self, node_factory, fake_httpx):
        """
        测试：未指定 method 应默认为 GET

        Given: 配置中不包含 method 字段
        When: 执行 HttpExecutor.execute
        Then: 应使用 GET 方法
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api"})

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["method"] == "GET"

    @pytest.mark.asyncio
    async def test_execute_empty_body_string_for_post_passes_none(self, node_factory, fake_httpx):
        """
        测试：POST 请求 body 为空字符串应传递 None

        Given: method=POST，body=""
        When: 执行 HttpExecutor.execute
        Then: httpx 应收到 json=None
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "POST", "body": ""})

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.request_calls[0]["json"] is None

    @pytest.mark.asyncio
    async def test_execute_default_timeout_is_30(self, node_factory, fake_httpx):
        """
        测试：默认 timeout 应为 30.0

        Given: HttpExecutor 初始化时未指定 timeout
        When: 执行 HttpExecutor.execute
        Then: httpx.AsyncClient 应收到 timeout=30.0
        """
        # Given
        state = fake_httpx(response=_FakeResponse(status_code=200, json_value={"ok": True}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/api", "method": "GET"})

        # When
        await executor.execute(node, {}, {})

        # Then
        assert state.init_timeouts[0] == 30.0


# ====================
# 测试类：P0 Count Sanity（烟雾测试）
# ====================


class TestHttpExecutorP0CountSanity:
    """P0 烟雾测试"""

    @pytest.mark.asyncio
    async def test_execute_smoke_test(self, node_factory, fake_httpx):
        """
        测试：基本功能烟雾测试

        Given: 配置完整的 HTTP 请求
        When: 执行 HttpExecutor.execute
        Then: 成功返回响应，不抛出异常
        """
        # Given
        fake_httpx(response=_FakeResponse(status_code=200, json_value={"status": "ok"}))
        executor = HttpExecutor()
        node = node_factory({"url": "https://example.com/health", "method": "GET"})

        # When
        result = await executor.execute(node, {}, {})

        # Then
        assert result == {"status": "ok"}
