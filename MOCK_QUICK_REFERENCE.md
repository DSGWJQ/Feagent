# Mock External Services - Quick Reference Guide

## Problem Statement

**2 failing tests** in `tests/unit/lc/test_task_executor.py`:
- `test_execute_simple_task` (line 43)
- `test_execute_task_with_http_tool` (line 62)

**Root Cause**: Tests call real OpenAI API instead of using mocks

```
Current Flow (BROKEN):
test_execute_simple_task()
  → execute_task()
    → create_task_executor_agent()
      → get_llm_for_execution() ❌ NOT MOCKED
        → ChatOpenAI(api_key=sk-...) ❌ REAL API CALL
          → OpenAI API ❌ FAILS (missing key or rate limited)

Expected Flow (FIXED):
test_execute_simple_task(patch_get_llm)  ← fixture injected
  → execute_task()
    → create_task_executor_agent()
      → get_llm_for_execution() ✅ RETURNS MOCK
        → MagicMock() ✅ INSTANT RESPONSE
          → Test passes in <10ms ✅
```

---

## Solution at a Glance

### What Needs to be Mocked?

```
┌─────────────────────────────────────────────────────────┐
│                    Unit Test Layer                       │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  Tests should NOT call:                                  │
│  ┌──────────────────────────────────────────────┐       │
│  │ 1. Real LLM API (OpenAI, KIMI, Claude)       │  ←    │
│  │    Location: src/lc/llm_client.py            │  mock │
│  │    Factory: get_llm*() functions             │  here │
│  │                                               │       │
│  │ 2. Real HTTP Requests (external APIs)        │  ←    │
│  │    Location: src/lc/tools/http_tool.py       │  mock │
│  │    Library: requests.request()                │  here │
│  │                                               │       │
│  │ 3. Real File System (in unit tests)          │  ←    │
│  │    Location: src/lc/tools/file_tool.py       │  mock │
│  │    Function: open(), Path.read()             │  here │
│  │                                               │       │
│  └──────────────────────────────────────────────┘       │
│                                                           │
│  Tests SHOULD use (mocked versions):                     │
│  ✅ Mocked LLM returning test data                       │
│  ✅ Mocked HTTP responses from responses lib             │
│  ✅ Mocked file content from tempfile or MagicMock      │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Where to Mock?

```
conftest.py (Global)
├── Session-level autouse fixtures
│   └── setup_test_env()  [OPENAI_API_KEY=test-key]
│
├── Function-level fixtures (opt-in)
│   ├── mock_llm()  [returns MagicMock()]
│   ├── patch_get_llm()  [@patch decorator wrapper]
│   ├── mock_http_requests()  [responses.RequestsMock()]
│   └── mock_file_io()  [MagicMock for file operations]
│
test_task_executor.py (Specific)
├── test_execute_simple_task(patch_get_llm)  ← USE FIXTURE
├── test_execute_task_with_http_tool(patch_get_llm, mock_http_requests)
└── test_execute_task_with_file_tool(mock_file_io)
```

---

## Implementation Steps (Quick Start)

### Step 1: Add Fixtures to conftest.py (5 minutes)

```python
# File: tests/conftest.py
# Add these imports at top:
import os
from unittest.mock import MagicMock, patch

# Add these fixtures at end:

@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Auto-run for all tests - set test environment"""
    os.environ["OPENAI_API_KEY"] = "test-key-12345"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

@pytest.fixture
def mock_llm():
    """Create a mock LLM instance"""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Mocked LLM response")
    return llm

@pytest.fixture
def patch_get_llm(mock_llm):
    """Patch ALL LLM factory functions in one go"""
    with patch("src.lc.llm_client.get_llm", return_value=mock_llm), \
         patch("src.lc.llm_client.get_llm_for_execution", return_value=mock_llm), \
         patch("src.lc.llm_client.get_llm_for_planning", return_value=mock_llm), \
         patch("src.lc.llm_client.get_llm_for_classification", return_value=mock_llm):
        yield mock_llm
```

**Lines of Code Added**: ~30 lines
**Time Investment**: ~5 minutes

### Step 2: Update Test File (5 minutes)

```python
# File: tests/unit/lc/test_task_executor.py
# Change lines like this:

# BEFORE (broken):
def test_execute_simple_task(self):
    result = execute_task(...)

# AFTER (fixed):
def test_execute_simple_task(self, patch_get_llm):  # ← ADD THIS PARAMETER
    result = execute_task(...)
```

**Changes**: Add parameter name to test methods
**Time Investment**: ~5 minutes

### Step 3: Run Tests (1 minute)

```bash
pytest tests/unit/lc/test_task_executor.py -v

# Expected output:
# test_execute_simple_task PASSED
# test_execute_task_with_http_tool PASSED
```

**Total Time**: 10-15 minutes

---

## Detailed Examples

### Example 1: Mock LLM for Simple Test

```python
def test_my_agent_logic(patch_get_llm):
    """Test that uses mocked LLM"""
    # patch_get_llm automatically patches:
    # - get_llm()
    # - get_llm_for_execution()
    # - get_llm_for_planning()
    # - get_llm_for_classification()

    from src.lc.agents.task_executor import execute_task

    result = execute_task(
        task_name="Test",
        task_description="Do something",
    )

    # LLM was mocked, so this is instant and deterministic
    assert isinstance(result, str)
    assert "Mocked LLM response" in result or len(result) > 0
```

### Example 2: Mock HTTP Responses

```python
def test_http_tool_with_mock(mock_http_requests):
    """Test HTTP tool with mocked responses"""
    import responses

    # Pre-add mock response
    mock_http_requests.add(
        responses.GET,
        "https://api.example.com/data",
        json={"status": "ok", "data": [1, 2, 3]},
        status=200,
    )

    from src.lc.tools.http_tool import http_request

    result = http_request(
        url="https://api.example.com/data",
        method="GET",
    )

    assert "ok" in result or "200" in result
```

### Example 3: Mock File I/O

```python
def test_file_tool_with_mock(mock_file_io):
    """Test file tool with mocked file operations"""
    from unittest.mock import patch

    with patch("builtins.open", mock_file_io):
        from src.lc.tools.file_tool import read_file

        result = read_file(path="/fake/path.txt")
        # No actual file system access occurs
        assert isinstance(result, str)
```

### Example 4: Custom Mock Behavior

```python
def test_llm_error_handling(patch_get_llm):
    """Test error handling with custom mock behavior"""
    # patch_get_llm returns the mocked LLM, modify it for this test:

    patch_get_llm.invoke.side_effect = ValueError("API Key Invalid")

    from src.lc.agents.task_executor import execute_task

    with pytest.raises(ValueError, match="API Key"):
        execute_task(task_name="Test", task_description="Test")
```

---

## Mocking Cheat Sheet

### LLM Mocking

```python
# Option 1: Use global fixture (recommended)
def test_something(patch_get_llm):
    # All LLM calls return mock_llm
    pass

# Option 2: Manual patch (for complex scenarios)
from unittest.mock import patch, MagicMock

with patch("src.lc.llm_client.get_llm") as mock_get:
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Custom response")
    mock_get.return_value = mock_llm

    # Your test code here
```

### HTTP Mocking

```python
# Option 1: Use responses library (best)
import responses

@responses.activate  # Decorator approach
def test_http():
    responses.add(responses.GET, "https://api.com/", json={"ok": True})
    # HTTP calls are now mocked

# Option 2: Use fixture
def test_http(mock_http_requests):
    mock_http_requests.add(...)
    # Requests are mocked
```

### Async Mocking

```python
from unittest.mock import AsyncMock, MagicMock

mock_llm = MagicMock()
mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="response"))

# Now async code can call mock_llm.ainvoke()
```

---

## Decision Tree: Which Mock to Use?

```
Does your test need to call...?

├─ OpenAI / LangChain LLM?
│  └─→ Use: @pytest.fixture patch_get_llm
│         in test function signature
│
├─ HTTP requests (requests library)?
│  └─→ Use: @pytest.fixture mock_http_requests
│         in test function signature
│         Add responses library: pip install responses
│
├─ File I/O?
│  └─→ Use: tempfile (real) OR @pytest.fixture mock_file_io (mock)
│
├─ Async operations?
│  └─→ Use: AsyncMock instead of MagicMock
│         from unittest.mock import AsyncMock
│
└─ Multiple mocks together?
   └─→ Stack fixtures in function signature:
       def test_something(patch_get_llm, mock_http_requests, mock_file_io):
           # All mocked
```

---

## Before & After Comparison

### BEFORE (Broken)

```python
def test_execute_simple_task(self):
    result = execute_task(
        task_name="计算 1 + 1",
        task_description="计算 1 加 1 的结果",
    )

# ❌ FAILS with:
# - OpenAI API error (missing key)
# - Network timeout
# - Rate limiting
# Unpredictable, non-deterministic
# Takes 30+ seconds (API latency)
```

### AFTER (Fixed)

```python
def test_execute_simple_task(self, patch_get_llm):  # ← fixture
    result = execute_task(
        task_name="计算 1 + 1",
        task_description="计算 1 加 1 的结果",
    )

# ✅ PASSES consistently
# - No API calls
# - Deterministic
# - Instant (<10ms)
# - 100% reliable
```

---

## Common Pitfalls & Solutions

| Pitfall | Problem | Solution |
|---------|---------|----------|
| Forgetting fixture parameter | `TypeError: test_xxx() missing required argument` | Add `patch_get_llm` to function signature |
| Mocking wrong path | Mock doesn't work, test still fails | Check exact import path: `src.lc.llm_client.get_llm` |
| Mock not configured | Mock returns wrong value | Use `.return_value` or `side_effect` |
| Async mock issues | `TypeError: object is not awaitable` | Use `AsyncMock()` not `MagicMock()` |
| Multiple test dependencies | Fixture conflicts | List all fixtures in function signature: `def test_x(mock1, mock2, mock3):` |

---

## Testing Strategy Going Forward

```
Unit Tests (Fast - Mocked)
├─ Run: Always, part of git commit hook
├─ Duration: 1-2 seconds total
├─ Mocking: 100% external dependencies mocked
└─ Goal: Fast feedback loop, catch logic bugs

Integration Tests (Slow - Real APIs)
├─ Run: Pre-deployment, weekly CI
├─ Duration: 30-60 seconds total
├─ Mocking: NONE, use real APIs
└─ Goal: Verify real API contracts, catch integration bugs
```

---

## Reference Files

| File | Purpose | Status |
|------|---------|--------|
| `tests/conftest.py` | Global fixtures (mock setup) | Need to update |
| `tests/unit/lc/test_task_executor.py` | Failing tests (need fixtures) | Need to update |
| `tests/unit/domain/services/test_task_executor.py` | Reference (already has mocks) | ✅ Good pattern |
| `MOCK_EXTERNAL_SERVICES_ANALYSIS.md` | Full technical analysis | Complete |
| `MOCK_EXTERNAL_SERVICES_SUMMARY.md` | Executive summary | Complete |

---

## Next Actions

1. ✅ **Read this document** (you are here)
2. 📋 **Read full analysis**: `MOCK_EXTERNAL_SERVICES_ANALYSIS.md` (sections 1-5)
3. 💻 **Implement Phase 1**: Copy-paste fixtures from conftest.py example
4. 🧪 **Run tests**: `pytest tests/unit/lc/test_task_executor.py -v`
5. ✨ **Verify**: Both tests should pass
6. 📚 **Document**: Add comment to test file explaining fixtures
7. 🚀 **Deploy**: Commit changes to main branch

---

## FAQ

**Q: Why pytest.fixture and not just @patch?**
A: Fixtures are more reusable and testable. `@patch` is better for one-off mocks.

**Q: Should I mock the entire LangChain library?**
A: No, only the entry points (factory functions). Let the rest run unmocked.

**Q: What if mocked test passes but real API fails?**
A: That's why we have integration tests. Run integration tests pre-deployment.

**Q: Can I use fixtures from other test files?**
A: Yes, put them in `conftest.py` (shared) or import them explicitly.

**Q: Is this the pytest standard way?**
A: Yes, fixtures are the official pytest approach. See: pytest.org/en/stable/how-to/fixtures.html

---

**Created**: 2025-12-14
**Format**: Quick Reference (this document)
**For**: Developers implementing mocks
**Next**: Implementation should take 10-15 minutes

