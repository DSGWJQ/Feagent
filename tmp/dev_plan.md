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

### Commits

6. `a07a37f` - refactor: Extract SubAgentOrchestrator from CoordinatorAgent

---

## Phase 2 阶段4: SafetyGuard 提取与集成

### 进度跟踪

| 阶段 | 状态 | 备注 |
|------|------|------|
| Codex 分析 | ✅ Done | 识别 5 个方法 |
| 创建测试 | ✅ Done | 25 个 TDD 测试 |
| 实现 SafetyGuard | ✅ Done | 367 行 |
| Codex Review | ✅ Done | 7/10 评分，已修复依赖和大小写问题 |
| 集成到 Coordinator | ✅ Done | 向后兼容代理已添加 |

### 修复项

1. **循环依赖问题** - ValidationResult 从 CoordinatorAgent 迁移到 SafetyGuard
2. **DNS大小写敏感** - 域名比较改为不区分大小写
3. **向后兼容** - 保留所有公开接口，方法签名完全一致

### Commits

7. `1ec06e6` - refactor: Extract SafetyGuard from CoordinatorAgent

---

## Phase 2 阶段5: ContainerExecutionMonitor 提取计划

### Codex 分析结果

**代码定位**：

| 方法/变量 | 行号 | 行数 | 职责 |
|----------|------|------|------|
| `container_executions` | 345 | 1 | workflow→执行记录列表 |
| `container_logs` | 347 | 1 | container→日志列表 |
| `_is_listening_container_events` | 348 | 1 | 监听状态标记 |
| `start_container_execution_listening()` | 3426-3447 | 22 | 订阅容器事件 |
| `stop_container_execution_listening()` | 3449-3469 | 21 | 取消订阅 |
| `_handle_container_started()` | 3471-3487 | 17 | 处理容器开始 |
| `_handle_container_completed()` | 3488-3507 | 20 | 处理容器完成 |
| `_handle_container_log()` | 3509-3526 | 18 | 处理容器日志（有界） |
| `get_workflow_container_executions()` | 3528-3537 | 10 | 查询执行记录 |
| `get_container_logs()` | 3539-3548 | 10 | 查询日志 |
| `get_container_execution_statistics()` | 3550-3580 | 31 | 统计汇总 |
| **总计** | | **158** | |

**依赖关系**：
- EventBus（订阅/取消订阅）
- ContainerExecutionStartedEvent, ContainerExecutionCompletedEvent, ContainerLogEvent
- 辅助方法：`_add_to_bounded_list`（防内存泄漏）
- 常量：`MAX_CONTAINER_LOGS_SIZE`

**拆分风险**：**低**
- 同步操作，边界清晰
- 不与其他模块共享状态
- 事件懒加载，无循环依赖
- 已有完整测试覆盖

**现有测试**：
- `tests/unit/domain/agents/test_container_execution_feedback.py` - 覆盖所有功能点

### 提取方案

**新文件**: `src/domain/services/container_execution_monitor.py`

**新类**: `ContainerExecutionMonitor`

**迁移内容**:
- 11个方法（3个public + 3个event handler + 3个查询 + 2个监听控制）
- 3个状态变量
- 有界列表辅助方法（可内联或共享）

**向后兼容**:
- CoordinatorAgent 保留所有11个方法作为代理
- 方法签名完全一致
- 返回结构完全一致

### 进度跟踪

| 阶段 | 状态 | 备注 |
|------|------|------|
| Codex 分析 | ✅ Done | 158行，低风险 |
| 创建测试 | ✅ Done | 27 个 TDD 测试 |
| 实现 Monitor | ✅ Done | 331 行（含重置方法） |
| Codex Review | ✅ Done | 9/10 评分，已修复 2 个问题 |
| 集成到 Coordinator | ✅ Done | 向后兼容属性已添加 |

### 修复项

1. **统计逻辑 Bug** - `get_container_execution_statistics()` 现在正确处理只有 `status` 字段的旧数据
2. **向后兼容性** - 添加 `reset_executions()`, `reset_logs()`, `reset_all()` 方法
3. **CoordinatorAgent 集成** - 添加 3 个向后兼容属性和 11 个代理方法

### Commits

8. `[pending]` - refactor: Extract ContainerExecutionMonitor from CoordinatorAgent

---

## Phase 34: SaveRequestOrchestrator 提取计划

### Codex 分析结果

**代码定位**：

| 方法/变量 | 行号 | 行数 | 职责 |
|----------|------|------|------|
| `_save_request_queue` | 429 | 1 | 请求队列（PriorityQueue） |
| `_save_request_handler_enabled` | 434 | 1 | 处理器启用标记 |
| `_is_listening_save_requests` | 435 | 1 | 事件监听标记 |
| `_save_auditor` | 436 | 1 | 审核器实例 |
| `_save_executor` | 437 | 1 | 执行器实例 |
| `_save_audit_logger` | 438 | 1 | 审计日志记录器 |
| `enable_save_request_handler()` | 640-657 | 18 | 启用请求处理器 |
| `disable_save_request_handler()` | 658-671 | 14 | 禁用请求处理器 |
| `_handle_save_request()` | 673-684 | 12 | 处理请求事件 |
| `has_pending_save_requests()` | 686-694 | 9 | 检查待处理请求 |
| `get_pending_save_request_count()` | 696-704 | 9 | 获取待处理数量 |
| `get_save_request_queue()` | 706-714 | 9 | 获取队列 |
| `get_save_request_status()` | 716-729 | 14 | 获取请求状态 |
| `get_save_requests_by_session()` | 731-742 | 12 | 按会话查询 |
| `dequeue_save_request()` | 744-752 | 9 | 出队请求 |
| `configure_save_auditor()` | 756-787 | 32 | 配置审核器 |
| `process_next_save_request()` | 789-815 | 27 | 处理下一个请求 |
| `get_save_audit_logs()` | 817-825 | 9 | 获取审计日志 |
| `get_save_audit_logs_by_session()` | 827-838 | 12 | 按会话获取日志 |
| `send_save_result_receipt()` | 1252-1297 | 46 | 发送结果回执 |
| `process_save_request_with_receipt()` | 1299-1318 | 20 | 处理请求含回执 |
| `get_save_receipt_context()` | 1320-1333 | 14 | 获取回执上下文 |
| `get_save_receipt_chain_log()` | 1335-1346 | 12 | 获取回执链路日志 |
| `get_save_receipt_logs()` | 1348-1352 | 5 | 获取回执日志 |
| `get_session_save_statistics()` | 1354-1365 | 12 | 获取会话统计 |
| **总计** | | **310** | |

**依赖关系**：
- EventBus（订阅/取消订阅）
- SaveRequestEvent, SaveRequestCompletedEvent
- SaveRequestAuditor, SaveExecutor, AuditLogger (来自 save_request_audit.py)
- SaveResultReceiptSystem (来自 save_request_receipt.py)
- KnowledgeManager, UnifiedLogCollector

**拆分风险**：**低**
- 边界清晰，职责单一
- 不与其他模块共享状态
- 事件懒加载，无循环依赖
- 已有完整测试覆盖

**现有测试**：
- 无独立测试（将创建 TDD 测试）

### 提取方案

**新文件**: `src/domain/services/save_request_orchestrator.py`

**新类**: `SaveRequestOrchestrator`

**迁移内容**:
- 18个方法（13个public + 1个event handler + 4个receipt相关）
- 6个状态变量
- 完整的队列管理、审核、执行、回执逻辑

**向后兼容**:
- CoordinatorAgent 保留所有18个方法作为代理
- 方法签名完全一致
- 返回结构完全一致
- 暴露内部组件属性（_save_request_queue, _save_auditor, _save_executor, _save_audit_logger）

### 进度跟踪

| 阶段 | 状态 | 备注 |
|------|------|------|
| Codex 分析 | ✅ Done | 310行，低风险 |
| 创建 TDD 测试 | ✅ Done | 34 个测试 |
| 实现 Orchestrator | ✅ Done | 597 行，96% 覆盖率 |
| Codex Review | ✅ Done | 4.5/10 初评，修复后通过 |
| 修复 5 个关键问题 | ✅ Done | 全部修复并验证 |
| 集成到 Coordinator | ✅ Done | 18 方法委托 + 属性暴露 |
| 二次验证 | ✅ Done | 34/34 测试通过，pyright 通过 |

### 修复项

1. **类型注解错误** - `async_handle_save_request` 参数类型从 Event 改为 Any
2. **异步方法包装** - 3个async方法用 asyncio.run() 包装保持同步接口
3. **向后兼容性** - 暴露内部组件属性，保留所有公开方法
4. **Bug 修复** - `execute_intervention` 中移除不存在的 `_create_injection` 调用

### Commits

9. `19fdb5b` - refactor: Extract SaveRequestOrchestrator from CoordinatorAgent
10. `6347500` - feat: integrate SaveRequestOrchestrator into CoordinatorAgent

---

## 已完成模块总结

1. ✅ PromptVersionFacade (提示词版本管理)
2. ✅ ExperimentOrchestrator (A/B 实验管理)
3. ✅ SubAgentOrchestrator (子Agent管理)
4. ✅ SafetyGuard (安全校验服务)
5. ✅ ContainerExecutionMonitor (容器执行监控)
6. ✅ SaveRequestOrchestrator (保存请求编排)

### CoordinatorAgent 代码行数变化

| 模块 | 原行数 | 新行数 | 减少 |
|------|--------|--------|------|
| PromptVersionFacade | ~200 | ~30 (代理) | ~170 |
| ExperimentOrchestrator | ~230 | ~30 (代理) | ~200 |
| SubAgentOrchestrator | ~200 | ~45 (代理) | ~155 |
| SafetyGuard | ~270 | ~120 (代理) | ~150 |
| ContainerExecutionMonitor | ~158 | ~68 (代理 + 属性) | ~90 |
| SaveRequestOrchestrator | ~310 | ~152 (代理) | ~158 |
| **总计** | ~1368 | ~445 | ~923 |

### 待集成模块

1. ✅ PromptVersionFacade (已完成)
2. ✅ ExperimentOrchestrator (已完成)
3. ✅ SubAgentOrchestrator (已完成)
4. ✅ SafetyGuard (已完成)
5. ✅ ContainerExecutionMonitor (已完成)
6. ✅ SaveRequestOrchestrator (已完成)
