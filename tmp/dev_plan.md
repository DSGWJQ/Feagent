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
7. ✅ WorkflowFailureOrchestrator (失败处理编排)
8. ✅ ExecutionSummaryManager (执行总结管理)
9. ✅ PowerCompressorFacade (强力压缩器包装)

### CoordinatorAgent 代码行数变化

| 模块 | 原行数 | 新行数 | 减少 |
|------|--------|--------|------|
| PromptVersionFacade | ~200 | ~30 (代理) | ~170 |
| ExperimentOrchestrator | ~230 | ~30 (代理) | ~200 |
| SubAgentOrchestrator | ~200 | ~45 (代理) | ~155 |
| SafetyGuard | ~270 | ~120 (代理) | ~150 |
| ContainerExecutionMonitor | ~158 | ~68 (代理 + 属性) | ~90 |
| SaveRequestOrchestrator | ~310 | ~152 (代理) | ~158 |
| WorkflowFailureOrchestrator | ~162 | ~50 (代理) | ~112 |
| ExecutionSummaryManager | ~110 | ~63 (代理) | ~47 |
| PowerCompressorFacade | ~183 | ~106 (代理) | ~77 |
| **总计** | ~1823 | ~664 | ~1159 |
| **CoordinatorAgent** | **5517 → 4320** | **减少 1197 lines (21.7%)** |

### 剩余候选模块

根据之前的分析，剩余待提取的模块（按优先级排序）：

1. 🎯 **KnowledgeRetrievalOrchestrator** (~480 lines, risk 3/10) - **下一个目标**
   - 位置：lines 3132-3611
   - 职责：知识检索、缓存、上下文增强（15个方法）
   - 依赖：`knowledge_retriever`, `_knowledge_cache`, `_compressed_contexts`
   - 挑战：中等复杂度，需要仔细处理缓存状态

### 待集成模块

1. ✅ PromptVersionFacade (已完成)
2. ✅ ExperimentOrchestrator (已完成)
3. ✅ SubAgentOrchestrator (已完成)
4. ✅ SafetyGuard (已完成)
5. ✅ ContainerExecutionMonitor (已完成)
6. ✅ SaveRequestOrchestrator (已完成)
7. ✅ WorkflowFailureOrchestrator (已完成)
8. ✅ ExecutionSummaryManager (已完成)
9. ✅ PowerCompressorFacade (已完成)

---

## Phase 34.1: WorkflowFailureOrchestrator 提取与集成

> 完成时间: 2025-12-11
> 目标: 从 CoordinatorAgent 提取失败处理逻辑到独立编排器
> 策略: TDD驱动 + 委托模式 + 向后兼容

### Codex 分析结论

**代码定位**：

| 方法/变量 | 行号 | 行数 | 职责 |
|----------|------|------|------|
| `failure_strategy_config` | 208 | 5 | 失败策略配置 |
| `_node_failure_strategies` | 259 | 1 | 节点级策略覆盖 |
| `_workflow_agents` | 260 | 1 | WorkflowAgent注册表 |
| `set_node_failure_strategy()` | 2546-2555 | 10 | 设置节点策略 |
| `get_node_failure_strategy()` | 2557-2568 | 12 | 获取节点策略 |
| `register_workflow_agent()` | 2570-2581 | 12 | 注册WorkflowAgent |
| `handle_node_failure()` | 2597-2629 | 33 | 失败处理主入口 |
| `_handle_retry()` | 2683-2769 | 87 | 重试策略实现 |
| `_handle_skip()` | 2771-2797 | 27 | 跳过策略实现 |
| `_handle_abort()` | 2799-2824 | 26 | 终止策略实现 |
| `_handle_replan()` | 2826-2844 | 19 | 重新规划策略 |
| `_update_context_after_success()` | 2846-2862 | 17 | 更新执行上下文 |
| **总计** | | **249** | |

**依赖关系**：
- EventBus（发布失败处理事件）
- workflow_states（状态管理，通过 lambda 访问）
- WorkflowAgent（重试执行，通过 resolver 获取）
- FailureHandlingStrategy、FailureHandlingResult、事件类（需统一定义）

**拆分风险**：**低**
- 逻辑边界清晰，职责单一
- 通过依赖注入解耦状态管理
- 事件驱动架构，无循环依赖
- 策略模式适合独立模块

**现有测试**：
- `tests/unit/domain/agents/test_coordinator_workflow_events.py` - 27个测试全覆盖

### 提取方案

**新文件**: `src/domain/services/workflow_failure_orchestrator.py`

**新类**: `WorkflowFailureOrchestrator`

**迁移内容**:
- 12个方法（3个public配置 + 1个主入口 + 4个策略处理 + 4个私有辅助）
- 3个状态变量（通过构造函数注入）
- 4个事件类定义（统一到orchestrator模块）
- FailureHandlingStrategy枚举和FailureHandlingResult数据类

**依赖注入设计**:
```python
WorkflowFailureOrchestrator(
    event_bus=EventBus,
    state_accessor=lambda wf_id: workflow_states.get(wf_id),
    state_mutator=lambda wf_id: workflow_states.setdefault(wf_id, {}),
    workflow_agent_resolver=lambda wf_id: _workflow_agents.get(wf_id),
    config=failure_strategy_config,
)
```

**向后兼容**:
- CoordinatorAgent 保留所有4个方法作为代理
- 方法签名完全一致
- 返回结构完全一致
- 暴露内部状态变量（_node_failure_strategies, _workflow_agents）
- 添加 _sync_config_to_orchestrator() 支持运行时配置修改

### 进度跟踪

| 阶段 | 状态 | 备注 |
|------|------|------|
| Codex 分析 | ✅ Done | 249行，低风险 |
| 创建 TDD 测试 | ✅ Done | 21 个测试（配置5 + RETRY4 + SKIP/ABORT/REPLAN5 + 边界7） |
| 实现 Orchestrator | ✅ Done | 603 行（含事件定义） |
| 首次 Codex Review | ✅ Done | 9.1/10 评分，3个低优先级建议 |
| 补充测试覆盖 | ✅ Done | 新增5个测试覆盖遗漏场景（异常处理、状态创建、配置规范化） |
| 二次 Codex Review | ✅ Done | 确认修复质量，无高/中优先级问题 |
| 集成到 Coordinator | ✅ Done | 委托模式 + 事件统一 + 配置同步 |
| 测试验证 | ✅ Done | 48/48 测试通过（21 orchestrator + 27 coordinator） |

### 集成实现细节

#### 1. 事件类型统一（关键修复）

**问题**: CoordinatorAgent 内部重复定义了 `NodeFailureHandledEvent`, `WorkflowAbortedEvent` 等事件类，导致 EventBus 类型匹配失败。

**解决方案**:
- 从 CoordinatorAgent 移除所有重复事件定义
- 从 `workflow_failure_orchestrator` 导入统一事件类
- 确保 EventBus 使用唯一类型进行事件分发

**代码修改** (coordinator_agent.py:146-153):
```python
# Phase 34.1: 从 WorkflowFailureOrchestrator 导入失败处理相关类
from src.domain.services.workflow_failure_orchestrator import (
    FailureHandlingResult,
    FailureHandlingStrategy,
    NodeFailureHandledEvent,
    WorkflowAbortedEvent,
    WorkflowAdjustmentRequestedEvent,
)
```

#### 2. 运行时配置同步（关键修复）

**问题**: 测试在运行时修改 `coordinator.failure_strategy_config`，但 orchestrator 配置在初始化时冻结，导致策略不生效。

**解决方案**:
- 添加 `_sync_config_to_orchestrator()` 方法
- 在每次 `handle_node_failure()` 调用前同步配置
- 支持测试和运行时动态修改策略

**代码添加** (coordinator_agent.py:2583-2595):
```python
def _sync_config_to_orchestrator(self) -> None:
    """同步 failure_strategy_config 到编排器

    当测试或运行时修改配置时，需要同步到编排器。
    """
    self._failure_orchestrator.config = {
        "default_strategy": self.failure_strategy_config.get(
            "default_strategy", FailureHandlingStrategy.RETRY
        ),
        "max_retries": self.failure_strategy_config.get("max_retries", 3),
        "retry_delay": self.failure_strategy_config.get("retry_delay", 1.0),
    }
```

#### 3. 委托模式实现

**初始化** (coordinator_agent.py:246-269):
```python
# 保留原配置以维持向后兼容性
self.failure_strategy_config: dict[str, Any] = failure_strategy_config or {
    "default_strategy": FailureHandlingStrategy.RETRY,
    "max_retries": 3,
    "retry_delay": 1.0,
}

# 内部状态变量（用于向后兼容属性暴露）
self._node_failure_strategies: dict[str, FailureHandlingStrategy] = {}
self._workflow_agents: dict[str, Any] = {}

# 创建失败编排器实例
self._failure_orchestrator = WorkflowFailureOrchestrator(
    event_bus=self.event_bus,
    state_accessor=lambda wf_id: self.workflow_states.get(wf_id),
    state_mutator=lambda wf_id: self.workflow_states.setdefault(wf_id, {}),
    workflow_agent_resolver=lambda wf_id: self._workflow_agents.get(wf_id),
    config=self.failure_strategy_config,
)
```

**方法委托** (coordinator_agent.py:2546-2629):
```python
def set_node_failure_strategy(self, node_id: str, strategy: FailureHandlingStrategy) -> None:
    # 同时更新本地状态和编排器（向后兼容）
    self._node_failure_strategies[node_id] = strategy
    self._failure_orchestrator.set_node_strategy(node_id, strategy)

def get_node_failure_strategy(self, node_id: str) -> FailureHandlingStrategy:
    return self._failure_orchestrator.get_node_strategy(node_id)

def register_workflow_agent(self, workflow_id: str, agent: Any) -> None:
    # 同时注册到本地和编排器（向后兼容）
    self._workflow_agents[workflow_id] = agent
    self._failure_orchestrator.register_workflow_agent(workflow_id, agent)

async def handle_node_failure(...) -> FailureHandlingResult:
    # 同步配置到编排器（支持运行时修改）
    self._sync_config_to_orchestrator()

    return await self._failure_orchestrator.handle_node_failure(
        workflow_id=workflow_id,
        node_id=node_id,
        error_code=error_code,
        error_message=error_message,
    )
```

#### 4. 代码行数减少

**删除的私有方法** (162 lines removed):
- `_handle_retry()` - 87 lines
- `_handle_skip()` - 27 lines
- `_handle_abort()` - 26 lines
- `_handle_replan()` - 19 lines
- `_update_context_after_success()` - 17 lines
- 删除重复事件类定义 - 约90 lines

**新增代码** (约100 lines):
- Orchestrator 初始化 - 24 lines
- 委托方法 - 50 lines
- 配置同步方法 - 13 lines
- 导入语句 - 13 lines

**净减少**: ~150 lines

### 修复项总结

| 问题 | 类型 | 解决方案 | 测试状态 |
|------|------|----------|---------|
| 事件类型不匹配 | Critical | 统一事件类定义，从orchestrator导入 | ✅ 通过 |
| 配置不同步 | High | 添加_sync_config_to_orchestrator()方法 | ✅ 通过 |
| 异常处理覆盖 | Medium | 补充测试：retry时Agent抛异常场景 | ✅ 新增 |
| 状态缺失处理 | Low | 补充测试：SKIP/ABORT时状态创建 | ✅ 新增 |
| 配置字符串规范化 | Low | 补充测试：字符串策略转换为枚举 | ✅ 新增 |

### 测试结果

**WorkflowFailureOrchestrator 单元测试** (21/21):
```bash
tests/unit/domain/services/test_workflow_failure_orchestrator.py
- test_orchestrator_initialization ✅
- test_set_node_strategy ✅
- test_get_node_strategy_with_override ✅
- test_get_node_strategy_default_fallback ✅
- test_register_workflow_agent ✅
- test_retry_success_on_first_attempt ✅
- test_retry_exhaustion_after_max_attempts ✅
- test_non_retryable_error_short_circuits ✅
- test_retry_without_workflow_agent_fails ✅
- test_skip_strategy_marks_node_skipped ✅
- test_skip_strategy_without_event_bus ✅
- test_abort_strategy_sets_workflow_aborted ✅
- test_replan_strategy_publishes_adjustment_event ✅
- test_replan_without_workflow_state ✅
- test_config_max_retries_override ✅
- test_unknown_strategy_returns_failure ✅
- test_retry_handles_execute_exception ✅ (补充)
- test_skip_creates_state_when_missing ✅ (补充)
- test_abort_creates_state_when_missing ✅ (补充)
- test_config_string_strategy_normalization ✅ (补充)
- test_config_invalid_strategy_fallback_to_retry ✅ (补充)
```

**CoordinatorAgent 集成测试** (27/27):
```bash
tests/unit/domain/agents/test_coordinator_workflow_events.py
- All failure strategy tests ✅
- All event publication tests ✅
- All real-world scenario tests ✅
- All context maintenance tests ✅
```

**总计**: 48/48 tests passing (100%)

### Commits

**预计提交信息**:
```
refactor: Extract WorkflowFailureOrchestrator from CoordinatorAgent

Phase 34.1: 工作流失败编排器提取与集成

创建独立编排器：
- WorkflowFailureOrchestrator (603 lines, 98% coverage)
- 支持四种策略：RETRY、SKIP、ABORT、REPLAN
- 依赖注入模式解耦状态管理
- 21个单元测试全部通过

集成到 CoordinatorAgent：
- 使用委托模式替换162行失败处理代码
- 统一事件类定义（修复EventBus类型匹配）
- 添加运行时配置同步机制
- 保持完全向后兼容

测试验证：
- 48/48 tests passing (21 orchestrator + 27 coordinator)
- 修复2个关键集成问题（事件类型、配置同步）
- 补充5个测试覆盖遗漏场景

代码质量：
- Codex Review: 9.1/10 (无高/中优先级问题)
- 代码净减少 ~150 lines
- 架构清晰，职责分离

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## Phase 34.7: ExecutionSummaryManager 提取

> **日期**: 2025-12-11
> **重构目标**: 提取执行总结管理功能，减少 CoordinatorAgent 职责

### 背景

在 Phase 34.1 (WorkflowFailureOrchestrator) 完成后，CoordinatorAgent 仍有 4444 行代码。识别出执行总结管理模块（~110 lines）作为下一个提取目标：
- 低耦合：仅依赖 EventBus
- 完整功能：存储、查询、事件发布、前端推送
- 低风险：独立功能边界清晰

### 实施步骤

#### 1. 模块提取

**创建 ExecutionSummaryManager** (`src/domain/services/execution_summary_manager.py`):
```python
class ExecutionSummaryManager:
    """执行总结管理器

    职责：
    - 存储与查询执行总结
    - 发布执行总结记录事件
    - 提供统计信息
    - 集成通道桥接器推送到前端
    """

    def __init__(self, event_bus: Any | None = None):
        self.event_bus = event_bus
        self._execution_summaries: dict[str, Any] = {}
        self._channel_bridge: Any | None = None

    # 7 个公共方法：
    def set_channel_bridge(self, bridge: Any) -> None
    def record_execution_summary(self, summary: Any) -> None
    async def record_execution_summary_async(self, summary: Any) -> None
    def get_execution_summary(self, workflow_id: str) -> Any | None
    def get_summary_statistics(self) -> dict[str, Any]
    async def record_and_push_summary(self, summary: Any) -> None
    def get_all_summaries(self) -> dict[str, Any]
```

**关键设计**:
- **懒加载移除**: 直接在 `__init__` 中初始化，简化逻辑
- **可选依赖**: EventBus 和 ChannelBridge 均为可选
- **数据隔离**: `get_all_summaries()` 返回副本防止外部修改
- **事件发布**: 异步方法发布 `ExecutionSummaryRecordedEvent`
- **前端集成**: `record_and_push_summary()` 同时记录和推送

#### 2. TDD 测试套件

**创建测试文件** (`tests/unit/domain/services/test_execution_summary_manager.py`):

**测试覆盖**:
1. **初始化与存储** (3 tests):
   - 初始化验证
   - 懒加载初始化
   - ChannelBridge 设置

2. **同步操作** (4 tests):
   - 记录总结（有 workflow_id）
   - 记录总结（无 workflow_id，应忽略）
   - 查询存在的总结
   - 查询不存在的总结

3. **异步操作** (2 tests):
   - 异步记录并发布事件
   - 无 EventBus 时异步记录

4. **统计功能** (4 tests):
   - 空统计
   - 带数据的统计（成功/失败/总数）
   - 获取所有总结
   - 验证返回副本（数据隔离）

5. **通道桥接** (3 tests):
   - 记录并推送（有 bridge 和 session_id）
   - 记录并推送（无 bridge）
   - 记录并推送（无 session_id）

6. **边界场景** (2 tests):
   - 重复 workflow_id 覆写
   - 缺失属性处理

7. **无 EventBus 场景** (2 tests):
   - 创建 manager 不传 EventBus
   - 异步操作不发布事件

**测试结果**: 20/20 tests passing, 100% coverage

#### 3. CoordinatorAgent 集成

**修改 CoordinatorAgent**:

**导入语句**:
```python
from src.domain.services.execution_summary_manager import ExecutionSummaryManager
```

**初始化** (line 321):
```python
# Phase 34.7: 执行总结管理器
self._summary_manager = ExecutionSummaryManager(event_bus=self.event_bus)
```

**委托方法替换** (lines 3619-3678):
```python
# ==================== Phase 34.7: 执行总结管理（委托到 ExecutionSummaryManager）====================

def set_channel_bridge(self, bridge: Any) -> None:
    self._summary_manager.set_channel_bridge(bridge)

def record_execution_summary(self, summary: Any) -> None:
    self._summary_manager.record_execution_summary(summary)

async def record_execution_summary_async(self, summary: Any) -> None:
    await self._summary_manager.record_execution_summary_async(summary)

def get_execution_summary(self, workflow_id: str) -> Any | None:
    return self._summary_manager.get_execution_summary(workflow_id)

def get_summary_statistics(self) -> dict[str, Any]:
    return self._summary_manager.get_summary_statistics()

async def record_and_push_summary(self, summary: Any) -> None:
    await self._summary_manager.record_and_push_summary(summary)

def get_all_summaries(self) -> dict[str, Any]:
    return self._summary_manager.get_all_summaries()
```

**删除代码**:
- `_init_summary_storage()` 方法
- 原 7 个方法的实现（110 lines）

#### 4. 代码行数减少

**删除的代码** (110 lines):
- `_init_summary_storage()` - 7 lines
- `set_channel_bridge()` - 8 lines
- `record_execution_summary()` - 10 lines
- `record_execution_summary_async()` - 27 lines
- `get_execution_summary()` - 11 lines
- `get_summary_statistics()` - 18 lines
- `record_and_push_summary()` - 16 lines
- `get_all_summaries()` - 8 lines
- 删除注释 - 5 lines

**新增代码** (约63 lines):
- Manager 初始化 - 2 lines
- 委托方法 - 56 lines
- 注释 - 5 lines
- 导入语句 - 1 line

**净减少**: 47 lines (4444 → 4397)

### 测试结果

**ExecutionSummaryManager 单元测试** (20/20):
```bash
tests/unit/domain/services/test_execution_summary_manager.py
- test_manager_initialization ✅
- test_lazy_storage_initialization ✅
- test_set_channel_bridge ✅
- test_record_execution_summary_sync ✅
- test_record_summary_without_workflow_id ✅
- test_get_execution_summary_exists ✅
- test_get_execution_summary_not_exists ✅
- test_record_execution_summary_async ✅
- test_record_async_without_event_bus ✅
- test_get_summary_statistics_empty ✅
- test_get_summary_statistics_with_data ✅
- test_get_all_summaries ✅
- test_get_all_summaries_returns_copy ✅
- test_record_and_push_summary_with_bridge ✅
- test_record_and_push_summary_without_bridge ✅
- test_record_and_push_summary_without_session_id ✅
- test_record_duplicate_workflow_id_overwrites ✅
- test_record_async_with_missing_attributes ✅
- test_manager_without_event_bus ✅
- test_manager_without_event_bus_async ✅
```

**ExecutionSummary 集成测试** (9/9):
```bash
tests/integration/test_execution_summary_e2e.py
- test_complete_summary_flow_success ✅
- test_complete_summary_flow_failure ✅
- test_summary_event_published ✅
- test_human_readable_summary_generation ✅
- test_multiple_workflows_summary_tracking ✅
- test_summary_includes_execution_timing ✅
- test_websocket_push_with_full_payload ✅
- test_summary_serialization_roundtrip ✅
- test_correct_order_task_summary_coordinator_push ✅
```

**代码质量检查**:
```bash
ruff check src/domain/agents/coordinator_agent.py src/domain/services/execution_summary_manager.py
✅ All checks passed!
```

**总计**: 29/29 tests passing (100%)

### 文件清单

**新增文件**:
- `src/domain/services/execution_summary_manager.py` (140 lines)
- `tests/unit/domain/services/test_execution_summary_manager.py` (331 lines)

**修改文件**:
- `src/domain/agents/coordinator_agent.py` (4444 → 4397 lines, -47)
- `tmp/dev_plan.md` (新增 Phase 34.7 文档)

### 成果总结

| 指标 | 数值 |
|------|------|
| 提取模块行数 | 140 lines |
| 测试文件行数 | 331 lines |
| CoordinatorAgent 减少 | 47 lines |
| 单元测试覆盖率 | 100% |
| 集成测试通过率 | 100% |
| Ruff 检查 | ✅ 通过 |

### Commits

**预计提交信息**:
```
refactor: Extract ExecutionSummaryManager from CoordinatorAgent

Phase 34.7: 执行总结管理器提取与集成

创建独立管理器：
- ExecutionSummaryManager (140 lines, 100% coverage)
- 支持同步/异步操作、统计、前端推送
- 可选 EventBus 和 ChannelBridge 依赖
- 20个单元测试全部通过

集成到 CoordinatorAgent：
- 使用委托模式替换110行总结管理代码
- 移除懒加载逻辑，简化初始化
- 保持完全向后兼容
- 代码净减少 47 lines

测试验证：
- 29/29 tests passing (20 manager + 9 e2e)
- 100% 测试覆盖率
- Ruff 检查通过

代码质量：
- 架构清晰，职责单一
- 数据隔离，返回副本防篡改
- 支持可选依赖，灵活配置

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

---

## Phase 34.8: PowerCompressorFacade 提取与集成

> 完成时间: 2025-12-11
> 目标: 从 CoordinatorAgent 提取 PowerCompressor 包装逻辑
> 策略: TDD驱动 + 简化包装 + 数据隔离

### 背景

在 Phase 34.7 完成后，CoordinatorAgent 包含约 183 行 PowerCompressor 集成代码（lines 3684-3863），包括：
- 懒加载初始化逻辑
- 压缩上下文存储与查询
- 八段数据查询接口
- 统计信息生成

**问题**：
- PowerCompressor 集成分散在多个方法中
- 懒加载逻辑增加复杂度
- 数据访问未做副本保护（可能被外部篡改）

**目标**：
- 提取为独立 PowerCompressorFacade
- 简化初始化（去除懒加载）
- 添加数据隔离保护（`copy.deepcopy()`）
- 保持完全向后兼容

### TDD 设计

#### 测试文件结构

**`tests/unit/domain/services/test_power_compressor_facade.py`**（20 tests, 96% coverage）

测试分类：
1. **初始化与配置** (2 tests)
   - 带 PowerCompressor 初始化
   - 无 PowerCompressor 懒加载

2. **压缩与存储** (3 tests)
   - 压缩并存储成功
   - 压缩无 workflow_id
   - 直接存储压缩上下文

3. **查询接口** (5 tests)
   - 查询压缩上下文（存在/不存在）
   - 查询子任务错误（存在/空）
   - 查询未解决问题
   - 查询后续计划

4. **对话上下文接口** (3 tests)
   - 获取对话上下文（存在/不存在）
   - 获取知识来源（存在/空）

5. **统计接口** (2 tests)
   - 空统计
   - 带数据统计

6. **边界场景** (3 tests)
   - 查询缺失字段
   - 获取缺失字段对话上下文
   - 重复 workflow_id 覆盖

#### 核心测试逻辑

```python
@pytest.fixture
def mock_power_compressor():
    """Mock PowerCompressor"""
    compressor = MagicMock()
    mock_compressed = MagicMock()
    mock_compressed.workflow_id = "wf_001"
    mock_compressed.to_dict.return_value = {
        "workflow_id": "wf_001",
        "task_goal": "Test task",
        "execution_status": {"status": "completed"},
        "node_summary": [{"node_id": "node1"}],
        "subtask_errors": [{"error": "test error"}],
        "unresolved_issues": [{"issue": "test issue"}],
        "decision_history": [{"decision": "test"}],
        "next_plan": [{"plan": "next step"}],
        "knowledge_sources": [{"source": "doc1"}],
    }
    compressor.compress_summary.return_value = mock_compressed
    return compressor

async def test_compress_and_store(facade, mock_execution_summary):
    result = await facade.compress_and_store(mock_execution_summary)

    assert result.workflow_id == "wf_001"
    assert "wf_001" in facade._compressed_contexts

def test_query_compressed_context_exists(facade):
    facade.store_compressed_context("wf_003", {"data": "test"})
    result = facade.query_compressed_context("wf_003")

    # 验证返回副本（数据隔离）
    assert result == {"data": "test"}
    result["data"] = "modified"
    # 原始数据不受影响
    assert facade.query_compressed_context("wf_003")["data"] == "test"
```

### 实现

#### PowerCompressorFacade 结构

**`src/domain/services/power_compressor_facade.py`**（206 lines）

```python
class PowerCompressorFacade:
    """PowerCompressor 包装器

    负责压缩上下文的存储、查询和统计。
    """

    def __init__(self, power_compressor: Any | None = None):
        """初始化（支持可选注入用于测试）"""
        self._power_compressor = power_compressor
        self._compressed_contexts: dict[str, dict[str, Any]] = {}

    @property
    def power_compressor(self) -> Any:
        """获取 PowerCompressor 实例（懒加载）"""
        if self._power_compressor is None:
            from src.domain.services.power_compressor import PowerCompressor
            self._power_compressor = PowerCompressor()
        return self._power_compressor

    async def compress_and_store(self, summary: Any) -> Any:
        """压缩执行总结并存储"""
        compressed = self.power_compressor.compress_summary(summary)
        workflow_id = getattr(compressed, "workflow_id", "")
        if workflow_id:
            self._compressed_contexts[workflow_id] = compressed.to_dict()
        return compressed

    def query_compressed_context(self, workflow_id: str) -> dict[str, Any] | None:
        """查询压缩上下文（返回副本保护内部状态）"""
        ctx = self._compressed_contexts.get(workflow_id)
        return copy.deepcopy(ctx) if ctx is not None else None

    # ... 9 more query/statistics methods
```

**设计亮点**：
1. **简化初始化**：直接在 `__init__` 中初始化存储字典，无懒加载逻辑
2. **可选注入**：支持传入 PowerCompressor 用于测试
3. **数据隔离**：`query_compressed_context()` 返回 `copy.deepcopy()` 保护内部状态
4. **懒加载压缩器**：仅对 PowerCompressor 实例使用懒加载（通过 `@property`）

#### CoordinatorAgent 集成

**修改位置**：
- Import: line 30
- 初始化: lines 324-325
- 委托方法: lines 3684-3785 (102 lines delegation)

**删除内容**：
- `_init_power_compressor_storage()` (11 lines)
- `_get_power_compressor()` (9 lines)
- 原有 11 个 PowerCompressor 集成方法 (183 lines)

**新增委托**：
```python
# Phase 34.8: PowerCompressor 包装器
self._power_compressor_facade = PowerCompressorFacade()

async def compress_and_store(self, summary: Any) -> Any:
    return await self._power_compressor_facade.compress_and_store(summary)

def query_compressed_context(self, workflow_id: str) -> dict[str, Any] | None:
    return self._power_compressor_facade.query_compressed_context(workflow_id)

# ... 7 more delegation methods
```

### 测试验证

#### 单元测试

```bash
pytest tests/unit/domain/services/test_power_compressor_facade.py -v
```

**结果**：
- ✅ 20/20 tests passing
- ✅ 96% coverage (缺失2行未达覆盖：lines 126, 140 - empty return 边界)

#### 代码质量检查

```bash
ruff check src/domain/services/power_compressor_facade.py src/domain/agents/coordinator_agent.py
```

**结果**：
- ✅ All checks passed

### 成果总结

| 指标 | 数值 |
|------|------|
| 提取模块行数 | 206 lines |
| 测试文件行数 | 449 lines |
| CoordinatorAgent 减少 | 77 lines (4397→4320) |
| 单元测试覆盖率 | 96% |
| 单元测试通过率 | 100% (20/20) |
| Ruff 检查 | ✅ 通过 |

### Commits

**预计提交信息**:
```
refactor: Extract PowerCompressorFacade from CoordinatorAgent

Phase 34.8: PowerCompressor 包装器提取与集成

创建独立包装器：
- PowerCompressorFacade (206 lines, 96% coverage)
- 支持压缩存储、八段查询、统计接口
- 数据隔离保护（copy.deepcopy）
- 可选 PowerCompressor 注入（测试友好）
- 20个单元测试全部通过

集成到 CoordinatorAgent：
- 使用委托模式替换 183 行 PowerCompressor 集成代码
- 移除懒加载初始化逻辑（简化）
- 新增 106 行委托方法
- 保持完全向后兼容
- 代码净减少 77 lines

测试验证：
- 20/20 tests passing
- 96% 测试覆盖率
- Ruff 检查通过

代码质量：
- 架构清晰，职责单一
- 数据隔离，防外部篡改
- 简化初始化，移除懒加载
- 支持可选依赖注入

累计进度：
- Phase 2 已完成 9 个模块
- CoordinatorAgent: 5517 → 4320 lines (-1197, 21.7%)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```


---

## Phase 34.9: KnowledgeRetrievalOrchestrator 提取与集成

> 完成时间: 2025-12-11
> 目标: 从 CoordinatorAgent 提取知识检索逻辑到独立编排器
> 策略: TDD驱动 + Context Gateway + 委托模式

### 背景

在 Phase 34.8 完成后，CoordinatorAgent 包含约 482 行知识检索相关代码（lines 3132-3611），包括：
- 知识检索方法（query/error/goal）
- 缓存管理（_knowledge_cache）
- 上下文增强与注入
- 自动触发机制
- 对话Agent上下文生成

**问题**：
- 知识检索逻辑与 CoordinatorAgent 紧耦合
- 直接访问 \ 内部状态
- 缺乏抽象层导致测试困难

**目标**：
- 提取为独立 KnowledgeRetrievalOrchestrator
- 使用 Context Gateway 解耦内部状态访问
- 保持完全向后兼容
- 通过 TDD 确保正确性

### Codex 分析结论

**代码定位**：

| 方法/变量 | 行号 | 行数 | 职责 |
|----------|------|------|------|
| \ | 425 | 1 | workflow_id → KnowledgeReferences |
| \ | 426 | 1 | 自动检索开关 |
| \ | 3269-3289 | 21 | 按查询检索知识 |
| \ | 3291-3311 | 21 | 按错误类型检索 |
| \ | 3313-3333 | 21 | 按目标检索知识 |
| \ | 3335-3344 | 10 | 获取缓存 |
| \ | 3346-3352 | 7 | 清除缓存 |
| \ | 3354-3376 | 23 | 丰富上下文 |
| \ | 3378-3395 | 18 | 注入知识到上下文 |
| \ | 3397-3408 | 12 | 获取知识增强摘要 |
| \ | 3410-3426 | 17 | 对话Agent上下文 |
| \ | 3428-3450 | 23 | 错误时自动丰富 |
| \ | 3452-3459 | 8 | 启用自动检索 |
| \ | 3461-3465 | 5 | 禁用自动检索 |
| \ | 3467-3493 | 27 | 处理失败含知识 |
| \ | 3495-3520 | 26 | 处理反思含知识 |
| **总计** | | **240** | |

**拆分风险**：**中等** - 直接访问 \ 需要抽象

**Codex 推荐方案**：创建 Context Gateway 提供受控访问接口

### TDD 设计

**测试文件**: \ (25 tests, 590+ lines, 96% coverage)

测试分类：
1. **初始化与配置** (2 tests) - 验证初始化参数和默认值
2. **知识检索** (4 tests) - query/error/goal 三种检索方式
3. **缓存管理** (4 tests) - 缓存读取、清除、不存在场景
4. **上下文增强与注入** (4 tests) - 丰富上下文、注入、去重验证
5. **自动触发机制** (3 tests) - 错误触发、节点失败、反思处理
6. **自动检索开关** (2 tests) - enable/disable 验证
7. **对话Agent上下文** (2 tests) - 上下文生成、不存在场景
8. **边界场景** (4 tests) - 无目标无错误、缺失上下文等

**核心 Mock**:
- \: 模拟 3 个异步检索方法
- \: 模拟上下文访问和修改，包含去重逻辑

### 实现

**\** (524 lines)

**核心方法**：
