# P0 Critical Issues Fix Plan

> Created: 2025-12-11
> Target: Fix 12 Critical issues from review report
> Approach: Minimal changes, maximum reuse

---

## Issue Summary

| # | Issue | File | Lines | Severity |
|---|-------|------|-------|----------|
| 1-5 | F821 Type annotation errors | conversation_agent.py | 2157, 2191, 2293, 2358-59 | Critical |
| 6-7 | Race Condition (create_task) | conversation_agent.py | 589-598, 719-730 | Critical |
| 8-9 | Shallow copy bug | conversation_agent.py | 617, 632 | Critical |
| 10 | Ambiguous variable 'l' | control_flow_ir.py | 207 | Warning |

---

## Fix Strategy

### 1. Type Annotation Errors (F821)

**Root Cause**: Using forward references to types that are imported inside functions at runtime.

**Solution**: Add TYPE_CHECKING imports at file top.

```python
# Add to conversation_agent.py TYPE_CHECKING block
if TYPE_CHECKING:
    from src.domain.agents.control_flow_ir import ControlFlowIR
    from src.domain.agents.error_handling import (
        FormattedError,
        UserDecision,
        UserDecisionResult,
    )
    from src.domain.agents.workflow_plan import EdgeDefinition
```

**Impact**: Zero runtime change, only static type checking improvement.

---

### 2. Race Condition Fix

**Root Cause**: `asyncio.create_task()` creates detached tasks that may be garbage collected before completion.

**Solution A (Minimal - Recommended)**: Track tasks in a set, clean up on completion.

```python
# Add to __init__
self._pending_tasks: set[asyncio.Task] = set()

# Helper method
def _create_tracked_task(self, coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    self._pending_tasks.add(task)
    task.add_done_callback(self._pending_tasks.discard)
    return task
```

**Solution B (Alternative)**: Await immediately (changes semantics).

**Chosen**: Solution A - maintains async-fire-and-forget but ensures task completion.

---

### 3. Shallow Copy Fix

**Root Cause**: `dict.copy()` only copies top level, nested dicts/lists are shared.

**Solution**: Use `copy.deepcopy()`.

```python
# Line 617
suspended_context = copy.deepcopy(context)

# Line 632
context = copy.deepcopy(self.suspended_context) if self.suspended_context else {}
```

**Impact**: Slight performance cost, but prevents data corruption.

---

### 4. Variable Name Fix

**Root Cause**: Single letter variable `l` is ambiguous (looks like `1` or `I`).

**Solution**: Rename to `loop_data`.

```python
# control_flow_ir.py line 207
for loop_data in data.get("loops", [])
```

---

## Test Strategy

### Existing Tests to Run

```bash
# Type checking
ruff check src/domain/agents/conversation_agent.py
ruff check src/domain/agents/control_flow_ir.py

# Unit tests for affected code
pytest tests/unit/domain/agents/test_conversation_agent*.py -v
```

### New Tests to Add

```python
# tests/unit/domain/agents/test_conversation_agent_p0_fixes.py

@pytest.mark.asyncio
async def test_state_transition_task_tracked():
    """Verify event publish tasks are tracked, not detached."""
    # Test that tasks complete before agent cleanup

def test_context_deepcopy():
    """Verify nested context is properly isolated."""
    # Test modifying resumed context doesn't affect original

def test_control_flow_ir_from_dict():
    """Verify variable naming doesn't break parsing."""
    # Test ControlFlowIR.from_dict with loop data
```

---

## Execution Order

1. [x] Read and analyze issues
2. [ ] Create test file (Red)
3. [ ] Fix TYPE_CHECKING imports
4. [ ] Fix race condition (add task tracking)
5. [ ] Fix shallow copy
6. [ ] Fix variable name
7. [ ] Run ruff check (should pass)
8. [ ] Run tests (Green)
9. [ ] Codex review

---

## Progress Tracking

| Step | Status | Notes |
|------|--------|-------|
| Analysis | ✅ Done | All issues identified |
| Test Creation | ✅ Done | 14 regression tests |
| Type fixes | ✅ Done | 7 TYPE_CHECKING imports added |
| Race condition | ✅ Done | 2 locations fixed with task tracking |
| Shallow copy | ✅ Done | 2 locations fixed with deepcopy |
| Variable name | ✅ Done | `l` → `loop_data` |
| Verification | ✅ Done | 116 tests pass, ruff check pass |
| Codex Review | ✅ Done | Score 9.3/10, no overfitting |

---

## Final Summary

**Completed at**: 2025-12-11
**Total Changes**: 6 fixes across 2 files
**Tests Added**: 14 regression tests
**Tests Passed**: 116/116 (100%)

### Fixed Issues

1. **F821 Type Errors (7)** - Added TYPE_CHECKING imports
2. **Race Condition (2)** - Added task tracking with `_create_tracked_task()`
3. **Shallow Copy Bugs (2)** - Changed `dict.copy()` to `copy.deepcopy()`
4. **E741 Variable Name (1)** - Renamed `l` to `loop_data`

### Codex Review Summary

- **Correctness**: 10/10
- **Overfitting**: 0/10 (none detected)
- **Test Coverage**: 9/10
- **Overall**: 9.3/10 - Production Ready

---

## Files to Modify

1. `src/domain/agents/conversation_agent.py`
   - Add TYPE_CHECKING imports (lines 32-35)
   - Add task tracking (in `__init__` and helper)
   - Fix `context.copy()` → `copy.deepcopy(context)` (line 617, 632)

2. `src/domain/agents/control_flow_ir.py`
   - Rename `l` to `loop_data` (line 207)

3. `tests/unit/domain/agents/test_conversation_agent_p0_fixes.py` (NEW)
   - Add regression tests for all P0 fixes

---

## P1 High Priority Fixes

### Completed P1 Fixes

#### P1-1/2: Magic Number Extraction to Constants

**Files Modified**:

1. `src/domain/agents/conversation_agent.py`
   ```python
   # Added constants at module level
   DEFAULT_MAX_ITERATIONS = 10
   DEFAULT_INTENT_CONFIDENCE_THRESHOLD = 0.7
   RULE_BASED_EXTRACTION_CONFIDENCE = 0.6
   ```

2. `src/domain/agents/coordinator_agent.py`
   ```python
   # Added constants at module level
   DEFAULT_REJECTION_RATE_THRESHOLD = 0.5
   DEFAULT_MAX_RETRIES = 3
   DEFAULT_RETRY_DELAY = 1.0
   MAX_MESSAGE_LOG_SIZE = 1000
   MAX_CONTAINER_LOGS_SIZE = 500
   MAX_SUBAGENT_RESULTS_SIZE = 100
   ```

#### P1-6: Memory Leak Protection (Bounded Lists)

**File Modified**: `src/domain/agents/coordinator_agent.py`

```python
# Added helper method
def _add_to_bounded_list(self, target_list: list[Any], item: Any, max_size: int) -> None:
    target_list.append(item)
    while len(target_list) > max_size:
        target_list.pop(0)

# Modified _handle_simple_message_event() to use bounded list
self._add_to_bounded_list(self.message_log, {...}, MAX_MESSAGE_LOG_SIZE)

# Modified _handle_container_log() to use bounded list
self._add_to_bounded_list(self.container_logs[container_id], {...}, MAX_CONTAINER_LOGS_SIZE)
```

### P1 Progress Tracking

| Issue | Status | Notes |
|-------|--------|-------|
| P1-1/2: Magic numbers | ✅ Done | 9 constants extracted |
| P1-6: Memory leak protection | ✅ Done | Bounded lists implemented |
| P1-3: Decision type mapping | ✅ Done | Module-level constant with lazy init |
| P1-4: Decision metadata | ✅ Done | Self-managed `_decision_metadata` list |
| P1-5: SaveRequest event | ✅ Done | Using `_create_tracked_task()` |

### Verification Results

- **Ruff check**: ✅ All pass
- **Unit tests (coordinator)**: ✅ 56/56 pass
- **Unit tests (conversation)**: ✅ 112/116 pass (4 skipped)

---

## Summary

**Total P0 Issues Fixed**: 12/12 (100%)
**Total P1 Issues Fixed**: 6/46 (13%)

### All Modified Files

1. `src/domain/agents/conversation_agent.py` - P0 + P1 fixes
2. `src/domain/agents/coordinator_agent.py` - P1 fixes
3. `src/domain/agents/control_flow_ir.py` - P0 fix
4. `tests/unit/domain/agents/test_conversation_agent_p0_fixes.py` - New test file

### Commits

1. `175142d` - fix: P0 Critical + P1 High Priority Issues (P0 all, P1-1/2, P1-6)
2. `5187287` - fix(P1): Decision type mapping, metadata storage, SaveRequest event (P1-3/4/5)

---

## Phase 2: Code Refactoring (CoordinatorAgent Split)

> 开始时间: 2025-12-11
> 目标: 拆分 CoordinatorAgent 巨型类（5687行 → 多个独立服务）
> 策略: 渐进式拆分，保持向后兼容

### Codex 分析结论

**推荐拆分顺序**（风险从低到高）：

1. **提示词版本管理** (PromptVersionFacade)
   - 位置: coordinator_agent.py:2151-2462
   - 规模: ~200行，纯同步，无事件依赖
   - 测试覆盖: prompt_version_manager, context_protocol, prompt_stability_monitor_e2e

2. **A/B实验模块** (ExperimentOrchestrator)
   - 位置: coordinator_agent.py:5235-5688
   - 规模: ~230行，委托型，独立依赖
   - 测试覆盖: ab_testing_integration, ab_testing_system

3. **子Agent管理** (SubAgentOrchestrator)
   - 位置: coordinator_agent.py:3751-3942
   - 规模: ~200行，有异步/事件，边界清晰
   - 测试覆盖: coordinator_subagent_lifecycle, subagent_e2e, subagent_result_handling

### 重构计划 - 阶段1: PromptVersionFacade

**新文件**: `src/domain/services/prompt_version_facade.py`

**迁移方法**:
- `init_prompt_version_manager`
- `prompt_version_manager` (property)
- `register_prompt_version`
- `load_prompt_template`
- `switch_prompt_version`
- `rollback_prompt_version`
- `get_prompt_audit_logs`
- `get_prompt_version_history`
- `submit_prompt_change`
- `approve_prompt_change`
- `reject_prompt_change`
- `get_prompt_loading_logs`

**向后兼容策略**:
```python
# coordinator_agent.py 保留代理方法
def load_prompt_template(self, ...):
    return self._prompt_facade.load_prompt_template(...)
```

### 进度跟踪

| 阶段 | 状态 | 备注 |
|------|------|------|
| 分析需求 | ✅ Done | Codex 完成分析 |
| 创建测试 | ✅ Done | 23 个 TDD 测试 |
| 实现 Facade | ✅ Done | 401 行，8/10 评分 |
| Codex Review | ✅ Done | 无过拟合 (2/10) |
| 提交代码 | ✅ Done | commit f9e9133 |
| 集成到 Coordinator | ✅ Done | commit c417573 |

### Commits (Phase 2)

3. `f9e9133` - refactor: Extract PromptVersionFacade from CoordinatorAgent
4. `c417573` - refactor: Integrate PromptVersionFacade into CoordinatorAgent

---

## Phase 2 阶段2: ExperimentOrchestrator 提取与集成

### 进度跟踪

| 阶段 | 状态 | 备注 |
|------|------|------|
| Codex 分析 | ✅ Done | 识别 18 个方法 |
| 创建测试 | ✅ Done | 29 个 TDD 测试 |
| 实现 Orchestrator | ✅ Done | 430 行 |
| Codex Review | ✅ Done | 9/10 评分 |
| 集成到 Coordinator | ✅ Done | 减少 319 行 |

### Commits

5. `62a681f` - refactor: Extract ExperimentOrchestrator from CoordinatorAgent

---

## Phase 2 阶段3: SubAgentOrchestrator 提取与集成

### 进度跟踪

| 阶段 | 状态 | 备注 |
|------|------|------|
| Codex 分析 | ✅ Done | 识别 7 个方法，4 个状态变量 |
| 创建测试 | ✅ Done | 24 个 TDD 测试 |
| 实现 Orchestrator | ✅ Done | 280 行 |
| Codex Review | ✅ Done | 7.5/10 评分，已修复日志兜底 |
| 集成到 Coordinator | ✅ Done | 向后兼容属性已添加 |

### 修复项

1. **handler 返回值问题** - `_handle_spawn_event_wrapper` 不再返回值
2. **日志兜底** - 添加标准 logging 兜底
3. **向后兼容属性** - 添加 `subagent_registry`, `active_subagents`, `subagent_results` 只读属性

### 待提交

6. `pending` - refactor: Extract SubAgentOrchestrator from CoordinatorAgent

---

## 已完成模块总结

1. ✅ PromptVersionFacade (提示词版本管理)
2. ✅ ExperimentOrchestrator (A/B 实验管理)
3. ✅ SubAgentOrchestrator (子Agent管理)

### CoordinatorAgent 代码行数变化

| 模块 | 原行数 | 新行数 | 减少 |
|------|--------|--------|------|
| PromptVersionFacade | ~200 | ~30 (代理) | ~170 |
| ExperimentOrchestrator | ~230 | ~30 (代理) | ~200 |
| SubAgentOrchestrator | ~200 | ~45 (代理) | ~155 |
| **总计** | ~630 | ~105 | ~525 |

### 待集成模块

1. ✅ PromptVersionFacade (已完成)
2. ✅ ExperimentOrchestrator (已完成)
3. ✅ SubAgentOrchestrator (已完成)
