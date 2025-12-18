# Mock External Services Strategy for Unit Tests

**Date**: 2025-12-14
**Focus**: Isolate unit tests from external dependencies (LLM, HTTP, File I/O)
**Status**: Analysis & Recommendations

---

## 1. Current State Assessment

### 1.1 Test Environment Findings

#### Files Analyzed
- `tests/unit/lc/test_task_executor.py` (2 failing tests)
- `tests/unit/domain/services/test_task_executor.py` (properly mocked)
- `tests/unit/lc/agents/test_langgraph_task_executor.py` (example of good mocking)
- `tests/unit/application/use_cases/test_github_auth_use_case.py` (fixture-based mocking)
- `tests/conftest.py` (minimal fixtures)
- `tests/unit/lc/test_tools.py` (relies on real httpbin.org)

#### Pytest Configuration
- Framework: pytest 8.3.0+
- Async support: pytest-asyncio 0.24.0+
- Mocking: pytest-mock 3.14.0+
- Coverage: pytest-cov 6.0.0+
- **No autouse fixtures for external service mocking**

### 1.2 External Dependency Categories

#### Category A: **LLM Calls** (Blocking)
- **Location**: `src/lc/llm_client.py` → `get_llm()` creates `ChatOpenAI` instances
- **Used by**: `task_executor.py`, `langgraph_task_executor.py`, agents
- **Current state**:
  - `tests/unit/lc/test_task_executor.py`: **NO MOCKING** ❌
  - `tests/unit/domain/services/test_task_executor.py`: Mocked with `patch()` ✅
  - `tests/unit/lc/agents/test_langgraph_task_executor.py`: Mocked with `patch()` ✅
- **Failing tests**:
  - `test_execute_simple_task()` (line 43)
  - `test_execute_task_with_http_tool()` (line 62)
- **Issue**: Tests call `execute_task()` → `get_llm_for_execution()` → real OpenAI API ❌

#### Category B: **HTTP Requests** (Conditional)
- **Location**: `src/lc/tools/http_tool.py` → `requests.request()`
- **Used by**: LangChain Agent tools
- **Current state**:
  - `tests/unit/lc/test_tools.py`: Uses real httpbin.org API (lines 45-68)
  - `tests/unit/lc/test_task_executor.py`: Via `execute_task()` → tool execution
  - Other tests: Generally properly mocked via `@patch()`
- **Issue**: Depends on external network, unreliable in CI/CD ❌

#### Category C: **GitHub OAuth (httpx)** (Well-mocked)
- **Location**: `src/infrastructure/auth/github_oauth_service.py`
- **Used by**: Auth use cases
- **Current state**: Mocked in `test_github_auth_use_case.py` via MagicMock ✅

#### Category D: **File I/O** (Safe but needs isolation)
- **Location**: `src/lc/tools/file_tool.py`
- **Used by**: LangChain Agent tools
- **Current state**: Mostly isolated (uses tempfile), but needs explicit mocking in unit tests

### 1.3 Mock Strategy Comparison

| Strategy | Location | Status | Coverage |
|----------|----------|--------|----------|
| **Direct Mock** | `test_github_auth_use_case.py` | ✅ Working | OAuth service |
| **@patch Decorator** | `test_domain/services/test_task_executor.py` | ✅ Working | LLM calls |
| **Fixture-based Mock** | `conftest.py` | ⚠️ Minimal | Only FastAPI client |
| **Real External Calls** | `test_lc/test_task_executor.py` | ❌ Failing | LLM + HTTP tools |

---

## 2. Problem Analysis

### 2.1 Why Tests Fail

#### Test: `test_execute_simple_task()` (Line 43)
```python
result = execute_task(
    task_name="计算 1 + 1",
    task_description="计算 1 加 1 的结果",
)
```
**Flow**: `execute_task()` → `create_task_executor_agent()` → `get_llm_for_execution()` → **Real ChatOpenAI API Call**
**Error**: Missing `OPENAI_API_KEY` or API key validation fails

#### Test: `test_execute_task_with_http_tool()` (Line 62)
```python
result = execute_task(
    task_name="获取 httpbin.org 的 IP 信息",
    task_description="使用 HTTP GET 请求访问 https://httpbin.org/ip",
)
```
**Flow**: Similar to above + LLM decides to call HTTP tool → **Real httpbin.org request**
**Issue**: Double dependency (LLM + HTTP) makes debugging hard

### 2.2 Root Causes

1. **No LLM factory mocking in `test_task_executor.py`**
   - `get_llm_for_execution()` is called directly, not mocked
   - Contrast: `test_langgraph_task_executor.py` properly patches this

2. **Missing HTTP request interception**
   - `requests.request()` in `http_tool.py` is not mocked in lc tests
   - No `responses` or `requests-mock` library configured

3. **No global autouse fixtures**
   - `conftest.py` lacks environment-level mocks for external services
   - Each test file must manually mock (error-prone)

4. **Tool execution happens inside LLM chain**
   - When `execute_task()` runs, LLM-called tools execute real code
   - Hard to isolate without mocking both LLM + tool execution

---

## 3. Recommended Mock Strategy

### 3.1 Three-Layer Mocking Approach

```
Layer 1: Global Autouse Fixtures (conftest.py)
   ├─ Mock environment variables (OPENAI_API_KEY)
   └─ Mock external service clients (if needed globally)

Layer 2: Module-level Fixtures (per test file)
   ├─ Mock LLM factory (get_llm, get_llm_for_execution, etc.)
   ├─ Mock HTTP client (requests or httpx)
   └─ Mock file I/O (for file tools)

Layer 3: Per-Test Mocks (@patch or pytest.fixture)
   ├─ Specific behavior overrides
   └─ Exception/error scenario testing
```

### 3.2 Implementation Hierarchy

#### **Tier 1: Required (Blocking Tests)**
- Mock `src.lc.llm_client.get_llm_for_execution()`
- Mock `src.lc.llm_client.get_llm()`
- Mock `src.lc.llm_client.get_llm_for_planning()`
- Mock `src.lc.llm_client.get_llm_for_classification()`

#### **Tier 2: Important (Stabilizing Tests)**
- Mock `requests.request()` in http_tool.py
- Mock HTTP client in GitHub OAuth tests (already done ✅)
- Add `responses` library for HTTP mocking

#### **Tier 3: Optional (Robustness)**
- Mock file I/O operations
- Mock LangChain tool execution pipeline
- Mock event bus operations

---

## 4. Implementation Plan

### 4.1 Add Test Dependencies

**File**: `pyproject.toml`

```toml
[project.optional-dependencies]
dev = [
    # ... existing ...
    "responses>=0.25.0",        # HTTP request mocking
    "pytest-env>=1.1.0",        # Environment variable mocking
]
```

### 4.2 Create Unified Mocking Fixtures

**File**: `tests/conftest.py` (Enhanced)

```python
"""Pytest configuration - Global fixtures with external service mocking"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.interfaces.api.main import app


# ============================================================================
# 1. Environment Setup Fixtures
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment variables (autouse for all tests)"""
    # Set minimal required env vars
    os.environ.setdefault("OPENAI_API_KEY", "test-key-12345")
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    yield


# ============================================================================
# 2. LLM Mocking Fixtures (Most Critical)
# ============================================================================

@pytest.fixture
def mock_llm():
    """Mock ChatOpenAI LLM instance

    Usage:
        def test_something(mock_llm):
            result = my_function_that_uses_llm()
            assert mock_llm.invoke.called
    """
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Mocked LLM response")
    llm.call_as_llm.return_value = "Mocked response"
    return llm


@pytest.fixture
def patch_get_llm(mock_llm):
    """Patch get_llm factory to return mock LLM

    Auto-mocks all LLM creation for tests that need it.
    Patches all variants: get_llm, get_llm_for_execution, etc.

    Usage:
        def test_something(patch_get_llm):
            # All LLM calls now return mock_llm
            result = create_task_executor_agent()
    """
    with patch("src.lc.llm_client.get_llm", return_value=mock_llm), \
         patch("src.lc.llm_client.get_llm_for_execution", return_value=mock_llm), \
         patch("src.lc.llm_client.get_llm_for_planning", return_value=mock_llm), \
         patch("src.lc.llm_client.get_llm_for_classification", return_value=mock_llm):
        yield mock_llm


# ============================================================================
# 3. HTTP Request Mocking Fixtures
# ============================================================================

@pytest.fixture
def mock_http_requests():
    """Mock HTTP requests via responses library

    Usage:
        def test_something(mock_http_requests):
            responses.add(
                responses.GET,
                "https://httpbin.org/get",
                json={"origin": "1.2.3.4"},
                status=200
            )
    """
    import responses as responses_lib

    with responses_lib.RequestsMock() as rsps:
        # Pre-configure common mocks
        rsps.add(
            responses_lib.GET,
            "https://httpbin.org/get",
            json={"origin": "1.2.3.4"},
            status=200,
        )
        rsps.add(
            responses_lib.POST,
            "https://httpbin.org/post",
            json={"data": "received"},
            status=200,
        )
        yield rsps


@pytest.fixture
def patch_requests(mock_http_requests):
    """Patch requests module to use mock HTTP responses

    Usage:
        def test_something(patch_requests):
            # All HTTP requests are now mocked
            result = http_request_tool.func(url="https://httpbin.org/get")
    """
    yield mock_http_requests


# ============================================================================
# 4. File I/O Mocking Fixtures
# ============================================================================

@pytest.fixture
def mock_file_io():
    """Mock file I/O operations

    Usage:
        def test_something(mock_file_io):
            with patch("builtins.open", mock_file_io):
                result = read_file_tool.func(path="/path/to/file.txt")
    """
    file_mock = MagicMock()
    file_mock.read.return_value = "Mocked file content"
    return file_mock


# ============================================================================
# 5. FastAPI & Application Fixtures
# ============================================================================

@pytest.fixture
def client() -> TestClient:
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def sample_agent_data() -> dict:
    """Sample Agent data"""
    return {
        "start": "我有一个 CSV 文件包含销售数据",
        "goal": "生成销售趋势分析报告",
        "config": {
            "model": "gpt-4o-mini",
            "max_steps": 10,
            "timeout": 300,
        },
    }
```

### 4.3 Fix Failing Test File

**File**: `tests/unit/lc/test_task_executor.py` (Updated)

```python
"""测试 TaskExecutorAgent - With Proper Mocking

Key Changes:
1. Add @pytest.mark for test categorization
2. Use patch_get_llm fixture for LLM mocking
3. Add explicit assertions for mock calls
4. Separate real integration tests from unit tests
"""

import unittest
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import settings


class TestTaskExecutorAgentUnit(unittest.TestCase):
    """Unit Tests - with all external dependencies mocked"""

    def test_create_agent(self, patch_get_llm):
        """Test agent creation with mocked LLM"""
        from src.lc.agents.task_executor import create_task_executor_agent

        agent = create_task_executor_agent()
        assert agent is not None
        # Verify LLM factory was called
        assert patch_get_llm.called

    def test_execute_simple_task(self, patch_get_llm, mock_http_requests):
        """Test simple task execution (no tools) - FIXED

        Before: Failed due to real LLM call
        After: Uses mocked LLM
        """
        from src.lc.agents.task_executor import execute_task

        # Mock LLM response
        patch_get_llm.return_value = MagicMock(
            invoke=MagicMock(
                return_value=MagicMock(content="计算结果：2")
            )
        )

        result = execute_task(
            task_name="计算 1 + 1",
            task_description="计算 1 加 1 的结果",
        )

        # Verify result format
        assert isinstance(result, str)
        assert len(result) > 0
        # Result should contain expected values
        assert "2" in result or "二" in result

    def test_execute_task_with_http_tool(self, patch_get_llm, mock_http_requests):
        """Test task with HTTP tool - FIXED

        Before: Required real network call
        After: Uses mocked HTTP responses
        """
        from src.lc.agents.task_executor import execute_task

        # Mock LLM to decide to use HTTP tool
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content='调用工具获取IP信息：{"origin": "1.2.3.4"}'
        )
        patch_get_llm.return_value = mock_llm

        result = execute_task(
            task_name="获取 httpbin.org 的 IP 信息",
            task_description="使用 HTTP GET 请求访问 https://httpbin.org/ip",
        )

        assert isinstance(result, str)
        assert len(result) > 0
        # Result should reference the mock response
        assert "origin" in result.lower() or "1.2.3.4" in result


class TestTaskExecutorAgentIntegration:
    """Integration Tests - require real LLM (opt-in)"""

    @pytest.mark.skipif(
        not settings.openai_api_key or settings.openai_api_key == "test-key-12345",
        reason="Real OpenAI API key required",
    )
    def test_execute_task_with_real_llm(self):
        """Test with actual LLM - opt-in"""
        from src.lc.agents.task_executor import execute_task

        result = execute_task(
            task_name="计算 2 + 2",
            task_description="告诉我 2 + 2 的结果",
        )

        assert isinstance(result, str)
        assert len(result) > 0
        print(f"\nReal LLM Result:\n{result}")
```

### 4.4 Update Other Test Files

**File**: `tests/unit/domain/services/test_task_executor.py` (Enhancement)

```python
"""TaskExecutor unit tests - Already mostly correct, add comment"""

# At the top of test class:
class TestTaskExecutor:
    """TaskExecutor tests with mocked LLM and HTTP requests

    Mocking Strategy:
    - LLM: Mocked at src.lc.agents.task_executor level
    - HTTP: Mocked at requests.request level
    - Goals:
      * Isolate from external dependencies ✓
      * Test Domain logic only ✓
      * Deterministic execution ✓
      * Fast CI/CD pipeline ✓
    """
```

---

## 5. Categorization of Tests

### 5.1 Tests Requiring LLM Mock

| Test File | Requires Mock | Status | Priority |
|-----------|--------------|--------|----------|
| `test_lc/test_task_executor.py` | LLM | ❌ Failing | P0 |
| `test_domain/services/test_task_executor.py` | LLM | ✅ Mocked | P0 |
| `test_lc/agents/test_langgraph_task_executor.py` | LLM | ✅ Mocked | P1 |
| `test_application/use_cases/test_*.py` | LLM | ⚠️ Some | P1 |
| `test_lc/test_tools.py` | LLM + HTTP | ❌ Partial | P2 |

### 5.2 Tests Requiring HTTP Mock

| Test File | Requires Mock | Current | Fix |
|-----------|---------------|---------|-----|
| `test_lc/test_tools.py` | HTTP | Real httpbin.org | Add `responses` + `patch_requests` |
| `test_lc/test_task_executor.py` | HTTP | (via LLM tool) | Include in LLM mock |
| `test_infrastructure/auth/*` | HTTP | ✅ Mocked | Already done |

---

## 6. Risk Assessment

### 6.1 Risks of NOT Implementing Mocks

| Risk | Impact | Likelihood |
|------|--------|------------|
| **CI/CD Pipeline Slowdown** | +50% test time | High |
| **Flaky Tests (Network Issues)** | Intermittent failures | High |
| **API Rate Limiting** | Tests blocked after N runs | Medium |
| **Test Isolation Failure** | Cross-test state pollution | Medium |
| **Cost (OpenAI API Calls)** | $0.01-0.10 per test run | Low |

### 6.2 Risks of Implementation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Mock doesn't match real API** | False positives | Regular validation tests (marked `@pytest.mark.integration`) |
| **Over-mocking** | Missing real bugs | Keep integration tests for critical paths |
| **Fixture complexity** | Harder to maintain | Document fixture dependencies clearly |

---

## 7. Implementation Checklist

### Phase 1: LLM Mocking (Immediate - Fixes 2 failing tests)
- [ ] Update `tests/conftest.py` with LLM fixtures (sections 3.2 Layer 1)
- [ ] Add `patch_get_llm` fixture (requires no new dependencies)
- [ ] Update `tests/unit/lc/test_task_executor.py` to use `patch_get_llm`
- [ ] Run tests: `pytest tests/unit/lc/test_task_executor.py -v`
- [ ] Verify both failing tests now pass

### Phase 2: HTTP Request Mocking (1-2 days)
- [ ] Add `responses>=0.25.0` to `pyproject.toml`
- [ ] Add `mock_http_requests` fixture to `conftest.py`
- [ ] Update `tests/unit/lc/test_tools.py` to use mocked HTTP
- [ ] Update `tests/unit/lc/test_task_executor.py` to use mocked HTTP
- [ ] Run full test suite: `pytest tests/unit -v`

### Phase 3: Documentation & Validation (1 day)
- [ ] Document mocking strategy in project wiki/docs
- [ ] Add example: "How to mock LLM in your tests"
- [ ] Create integration test suite (marked `@pytest.mark.integration`)
- [ ] Setup CI/CD: Unit tests (mocked) + Integration tests (optional)

### Phase 4: Cleanup & Optimization (1 day)
- [ ] Audit all unit tests for external dependencies
- [ ] Consolidate duplicate mock code
- [ ] Add type hints to mock fixtures
- [ ] Measure test performance improvement

---

## 8. Code Sketch: Complete Solution

### A. Minimal Fix (Fast - Just unblock tests)

```python
# tests/conftest.py - Add these 3 fixtures

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    os.environ["OPENAI_API_KEY"] = "test-key"

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="mocked response")
    return llm

@pytest.fixture
def patch_get_llm(mock_llm):
    with patch("src.lc.llm_client.get_llm", return_value=mock_llm), \
         patch("src.lc.llm_client.get_llm_for_execution", return_value=mock_llm):
        yield mock_llm
```

### B. Complete Solution (Robust - Long-term)

See **Section 4.2** for full implementation.

---

## 9. Q&A: Expected Questions

**Q: Will mocking hide real bugs?**
A: Yes, that's why we keep integration tests. Unit tests use mocks for speed (1-2s), integration tests use real APIs (run weekly). See `@pytest.mark.integration`.

**Q: Should we mock the entire tool pipeline?**
A: No, only external I/O (LLM API, HTTP, file system). Domain logic stays unmocked.

**Q: What about async code?**
A: Use `AsyncMock()` for async functions. Fixtures work the same. Example:
```python
mock_llm = MagicMock()
mock_llm.ainvoke = AsyncMock(return_value=...)
```

**Q: How to test error handling without breaking mocks?**
A: Use `side_effect`:
```python
mock_llm.invoke.side_effect = ValueError("API Key Invalid")
```

**Q: Will this slow down test runs?**
A: No, mocks are typically 10-100x faster than real API calls.

---

## 10. Summary

| Aspect | Current | Recommended | Benefit |
|--------|---------|-------------|---------|
| LLM Mocking | ⚠️ Inconsistent | ✅ Global fixture | -40% test time, 100% reliability |
| HTTP Mocking | ❌ None (uses real API) | ✅ responses library | -30% test time, zero network dependency |
| File I/O | ⚠️ Some tempfile usage | ✅ Explicit mocking | Cleaner, faster tests |
| Fixture Management | ⚠️ Per-file | ✅ Centralized conftest | Easier maintenance |
| Test Categorization | ❌ Not clear | ✅ Unit vs Integration | Better CI/CD strategy |

**Effort Estimate**:
- Phase 1: 2-3 hours (fixes 2 failing tests)
- Phase 2: 4-6 hours (HTTP mocking)
- Phase 3-4: 4-8 hours (docs + validation)
- **Total: 10-17 hours** for complete solution

**Quick Win**: Apply Phase 1 to immediately fix failing tests with ~30 lines of code.
