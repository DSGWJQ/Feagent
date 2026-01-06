# 三种测试模式切换机制（A/B/C 模式）

> 目标：通过环境变量 + 依赖注入实现 Deterministic/Hybrid/Full-real 三种测试模式的无缝切换，无需修改业务代码。

---

## 1. 模式定义与职责

| 模式 | LLM | 外部 HTTP/工具 | DB | 适用场景 | 稳定性 |
|---|---|---|---|---|---|
| **A. Deterministic (CI)** | Stub/固定输出 | Mock/本地 stub | 隔离（每次重置） | PR 回归、冒烟测试 | 高 |
| **B. Hybrid (PR/每日)** | 受控（回放/固定 seed） | Mock server | 可共享但可清理 | 集成回归 | 中高 |
| **C. Full-real (nightly)** | 真实 API 调用 | 真实外部服务 | 隔离环境 | 真实波动探测 | 中低 |

---

## 2. 架构设计原则

### 2.1 SOLID 映射
- **单一职责**：业务逻辑不关心 LLM 是真实还是 stub
- **依赖倒置**：依赖抽象（Protocol），不依赖具体实现（OpenAI/Mock）
- **开放封闭**：新增模式只需新增 Adapter，不修改 UseCase

### 2.2 依赖注入层级
```
Interface (API) → Application (UseCase) → Domain (Port)
                                              ↑
                         Infrastructure (Adapters: Real/Stub/Mock)
```

---

## 3. 核心接口定义（Domain Layer）

### 3.1 LLM Port (Protocol)

```python
# src/domain/ports/llm_port.py
from typing import Protocol, Any, AsyncIterator


class LLMPort(Protocol):
    """LLM 抽象接口（Domain Port）

    职责：隔离 Domain 与具体 LLM 实现（OpenAI/Anthropic/Mock）
    """

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """生成文本响应

        参数：
            prompt: 提示词
            temperature: 温度参数（0.0-1.0）
            max_tokens: 最大 token 数

        返回：
            生成的文本
        """
        ...

    async def generate_streaming(
        self,
        prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式生成文本响应

        参数：同 generate

        生成：
            文本片段（delta）
        """
        ...
```

### 3.2 HTTP Client Port

```python
# src/domain/ports/http_client_port.py
from typing import Protocol, Any


class HTTPClientPort(Protocol):
    """HTTP 客户端抽象接口"""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """执行 HTTP 请求

        参数：
            method: HTTP 方法（GET/POST/等）
            url: 请求 URL
            headers: 请求头
            json_body: JSON 请求体
            timeout: 超时时间（秒）

        返回：
            响应 JSON
        """
        ...
```

---

## 4. 实现层（Infrastructure Layer）

### 4.1 模式 A: Deterministic Adapters

```python
# src/infrastructure/adapters/llm_stub_adapter.py
class LLMStubAdapter:
    """LLM Stub 实现（确定性输出）"""

    def __init__(self, fixed_responses: dict[str, str] | None = None):
        """
        参数：
            fixed_responses: 固定响应映射（prompt_hash → response）
        """
        self.fixed_responses = fixed_responses or {}
        self.default_response = '{"result": "stubbed_output"}'

    async def generate(self, prompt: str, **kwargs) -> str:
        # 根据 prompt 的 hash 返回预定义响应
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        return self.fixed_responses.get(prompt_hash, self.default_response)

    async def generate_streaming(self, prompt: str, **kwargs):
        response = await self.generate(prompt, **kwargs)
        yield response  # 一次性返回


# src/infrastructure/adapters/http_mock_adapter.py
class HTTPMockAdapter:
    """HTTP Mock 实现（本地 mock 响应）"""

    def __init__(self, mock_responses: dict[str, dict] | None = None):
        """
        参数：
            mock_responses: URL pattern → 响应映射
        """
        self.mock_responses = mock_responses or {
            r"https://httpbin\.org/.*": {"mock": True, "status": "ok"},
        }

    async def request(self, method: str, url: str, **kwargs) -> dict:
        for pattern, response in self.mock_responses.items():
            if re.match(pattern, url):
                return response
        return {"error": "unmocked_url", "url": url}
```

### 4.2 模式 B: Hybrid Adapters

```python
# src/infrastructure/adapters/llm_replay_adapter.py
class LLMReplayAdapter:
    """LLM Replay 实现（回放录制响应）"""

    def __init__(self, replay_file: str):
        """
        参数：
            replay_file: 录制文件路径（JSON）
        """
        with open(replay_file) as f:
            self.recordings = json.load(f)

    async def generate(self, prompt: str, **kwargs) -> str:
        # 根据 prompt 查找录制响应
        for record in self.recordings:
            if record["prompt"] == prompt:
                return record["response"]
        raise ValueError(f"No recording for prompt: {prompt[:50]}...")


# src/infrastructure/adapters/http_wiremock_adapter.py
class HTTPWireMockAdapter:
    """HTTP WireMock 实现（通过 WireMock 服务器）"""

    def __init__(self, wiremock_url: str = "http://localhost:8080"):
        self.wiremock_url = wiremock_url

    async def request(self, method: str, url: str, **kwargs) -> dict:
        # 转发请求到 WireMock 服务器
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method,
                f"{self.wiremock_url}/__admin/mappings",
                json={"request": {"url": url, "method": method}},
            )
            return resp.json()
```

### 4.3 模式 C: Full-real Adapters

```python
# src/infrastructure/adapters/llm_openai_adapter.py
class LLMOpenAIAdapter:
    """真实 OpenAI LLM 实现"""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    async def generate(self, prompt: str, **kwargs) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 1000),
        )
        return response.choices[0].message.content

    async def generate_streaming(self, prompt: str, **kwargs):
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# src/infrastructure/adapters/http_httpx_adapter.py
class HTTPHttpxAdapter:
    """真实 HTTP 客户端实现"""

    async def request(self, method: str, url: str, **kwargs) -> dict:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.request(method, url, **kwargs)
            return resp.json()
```

---

## 5. 依赖注入配置（Application Layer）

### 5.1 环境变量定义

```bash
# .env.test (模式 A: Deterministic)
E2E_TEST_MODE=deterministic
LLM_ADAPTER=stub
HTTP_ADAPTER=mock
DATABASE_URL=sqlite:///./test.db  # 隔离 DB

# .env.hybrid (模式 B: Hybrid)
E2E_TEST_MODE=hybrid
LLM_ADAPTER=replay
LLM_REPLAY_FILE=tests/fixtures/llm_recordings.json
HTTP_ADAPTER=wiremock
WIREMOCK_URL=http://localhost:8080

# .env.fullreal (模式 C: Full-real)
E2E_TEST_MODE=fullreal
LLM_ADAPTER=openai
OPENAI_API_KEY=CHANGE_ME
HTTP_ADAPTER=httpx
```

### 5.2 DI 容器配置

```python
# src/interfaces/api/container.py
from src.config import settings


class AdapterFactory:
    """Adapter 工厂（根据环境变量选择实现）"""

    @staticmethod
    def create_llm_adapter() -> LLMPort:
        adapter_type = settings.llm_adapter

        if adapter_type == "stub":
            from src.infrastructure.adapters.llm_stub_adapter import LLMStubAdapter
            return LLMStubAdapter()

        elif adapter_type == "replay":
            from src.infrastructure.adapters.llm_replay_adapter import LLMReplayAdapter
            return LLMReplayAdapter(replay_file=settings.llm_replay_file)

        elif adapter_type == "openai":
            from src.infrastructure.adapters.llm_openai_adapter import LLMOpenAIAdapter
            return LLMOpenAIAdapter(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )

        else:
            raise ValueError(f"Unknown llm_adapter: {adapter_type}")

    @staticmethod
    def create_http_adapter() -> HTTPClientPort:
        adapter_type = settings.http_adapter

        if adapter_type == "mock":
            from src.infrastructure.adapters.http_mock_adapter import HTTPMockAdapter
            return HTTPMockAdapter()

        elif adapter_type == "wiremock":
            from src.infrastructure.adapters.http_wiremock_adapter import HTTPWireMockAdapter
            return HTTPWireMockAdapter(wiremock_url=settings.wiremock_url)

        elif adapter_type == "httpx":
            from src.infrastructure.adapters.http_httpx_adapter import HTTPHttpxAdapter
            return HTTPHttpxAdapter()

        else:
            raise ValueError(f"Unknown http_adapter: {adapter_type}")


# 依赖注入函数
def get_llm_client() -> LLMPort:
    return AdapterFactory.create_llm_adapter()


def get_http_client() -> HTTPClientPort:
    return AdapterFactory.create_http_adapter()
```

### 5.3 UseCase 注入

```python
# src/application/use_cases/update_workflow_by_chat.py
class UpdateWorkflowByChatUseCase:
    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        llm_client: LLMPort,  # 注入 Port，不依赖具体实现
    ):
        self.workflow_repository = workflow_repository
        self.llm_client = llm_client

    async def execute(self, input_data: UpdateWorkflowByChatInput):
        # 使用 llm_client，不关心是 stub/replay/real
        response = await self.llm_client.generate(prompt="...")
        # ...
```

---

## 6. Playwright 集成

### 6.1 测试配置文件

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  projects: [
    {
      name: 'deterministic',  // 模式 A
      use: {
        baseURL: 'http://localhost:8000',
      },
      testDir: './tests/e2e/deterministic',
    },
    {
      name: 'hybrid',  // 模式 B
      use: {
        baseURL: 'http://localhost:8000',
      },
      testDir: './tests/e2e/hybrid',
    },
    {
      name: 'fullreal',  // 模式 C
      use: {
        baseURL: 'http://localhost:8000',
      },
      testDir: './tests/e2e/fullreal',
      timeout: 120000,  // 真实 LLM 调用可能较慢
    },
  ],
});
```

### 6.2 测试启动脚本

```bash
# tests/e2e/run-mode-a.sh
#!/bin/bash
export E2E_TEST_MODE=deterministic
export LLM_ADAPTER=stub
export HTTP_ADAPTER=mock

# 启动后端（使用测试配置）
uvicorn src.interfaces.api.main:app --env-file .env.test &
BACKEND_PID=$!

# 运行 Playwright 测试
npx playwright test --project=deterministic

# 清理
kill $BACKEND_PID
```

---

## 7. 验证与回归策略

### 7.1 CI Pipeline 配置

```yaml
# .github/workflows/e2e.yml
name: E2E Tests

on: [pull_request]

jobs:
  e2e-deterministic:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run Mode A (Deterministic)
        run: ./tests/e2e/run-mode-a.sh
        env:
          E2E_TEST_MODE: deterministic
          LLM_ADAPTER: stub
          HTTP_ADAPTER: mock

  e2e-hybrid:
    runs-on: ubuntu-latest
    steps:
      # ... 类似配置，使用 Mode B

  e2e-fullreal:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule'  # 仅 nightly
    steps:
      # ... 类似配置，使用 Mode C
      - name: Run Mode C (Full-real)
        run: ./tests/e2e/run-mode-c.sh
        env:
          E2E_TEST_MODE: fullreal
          LLM_ADAPTER: openai
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

---

## 8. 故障排查清单

| 现象 | 可能原因 | 排查步骤 |
|---|---|---|
| LLM 返回 stub 响应但测试预期真实输出 | 环境变量未生效 | 检查 `E2E_TEST_MODE` 和 `LLM_ADAPTER` |
| HTTP 请求失败（unmocked_url） | Mock 规则缺失 | 检查 `http_mock_adapter.py` 的 `mock_responses` |
| Replay 失败（No recording for prompt） | 录制文件不匹配 | 重新录制或检查 prompt 完全一致性 |
| 真实 LLM 调用超时 | 网络问题/配额耗尽 | 检查 API Key、网络连接、调用次数 |

---

## 9. 里程碑

| 里程碑 | 任务 | 工作量 |
|---|---|---|
| M0 | 定义 LLMPort/HTTPClientPort (Domain) | 0.5 天 |
| M1 | 实现 3 种 LLM Adapters (Infrastructure) | 1 天 |
| M2 | 实现 3 种 HTTP Adapters (Infrastructure) | 1 天 |
| M3 | 实现 AdapterFactory + DI 配置 | 0.5 天 |
| M4 | Playwright 集成 + CI 配置 | 1 天 |

**总计**：4 天

---

## 10. 验收标准

- [ ] 使用 `.env.test` 启动后端，LLM 返回 stub 响应
- [ ] 使用 `.env.hybrid` 启动后端，LLM 返回录制响应
- [ ] 使用 `.env.fullreal` 启动后端，LLM 调用真实 OpenAI API
- [ ] HTTP Mock Adapter 能正确拦截 httpbin.org 请求
- [ ] Playwright 能在三种模式下运行同一套用例
- [ ] CI Pipeline 能自动执行模式 A（每次 PR）和模式 C（nightly）
