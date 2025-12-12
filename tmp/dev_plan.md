# Development Plan: RuleEngineFacade Integration into CoordinatorAgent

**Date**: 2025-12-13
**Phase**: P1-1 Step 3 - Gradual Migration
**Status**: In Progress

---

## Requirements Summary

Integrate RuleEngineFacade into CoordinatorAgent by creating proxy methods that delegate to the facade, deprecating the old direct rule engine methods. This achieves cleaner separation of concerns while maintaining backward compatibility.

---

## Test Strategy

### Red Phase (Write Failing Tests)
1. **test_rule_engine_facade_extraction** - Verify facade is extracted from wiring
2. **test_deprecated_add_rule_emits_warning** - Verify add_rule() emits deprecation warning
3. **test_deprecated_remove_rule_emits_warning** - Verify remove_rule() emits deprecation warning
4. **test_deprecated_validate_decision_emits_warning** - Verify validate_decision() emits deprecation warning
5. **test_deprecated_get_statistics_emits_warning** - Verify get_statistics() emits deprecation warning
6. **test_deprecated_is_rejection_rate_high_emits_warning** - Verify is_rejection_rate_high() emits deprecation warning
7. **test_deprecated_methods_proxy_to_facade** - Verify methods delegate to facade correctly

### Green Phase (Implement Minimal Code)
1. Extract `_rule_engine_facade` from wiring in `__init__`
2. Add `_deprecated()` decorator utility
3. Wrap each method with `@_deprecated()` and proxy to facade
4. Update `rules` property to use facade

### Refactor Phase
- Clean up any redundant code
- Ensure thread safety
- Verify performance impact is minimal

---

## Implementation Plan

### Step 1: Extract RuleEngineFacade from Wiring
**File**: `src/domain/agents/coordinator_agent.py`
**Location**: After line 515 in `__init__`
```python
self._rule_engine_facade = wiring.orchestrators["rule_engine_facade"]
```

### Step 2: Add Deprecation Decorator
**File**: `src/domain/agents/coordinator_agent.py`
**Location**: Top of file (after imports)
```python
import warnings
from functools import wraps

def _deprecated(message: str):
    """Decorator for deprecated methods"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

### Step 3: Deprecate Methods (Proxy Pattern)
**Methods to Update** (lines 1857-2186):
- `add_rule()` → proxy to `facade.add_decision_rule()`
- `remove_rule()` → proxy to `facade.remove_decision_rule()`
- `validate_decision()` → proxy to `facade.validate_decision()`
- `get_statistics()` → proxy to `facade.get_decision_statistics()`
- `is_rejection_rate_high()` → proxy to `facade.is_rejection_rate_high()`

### Step 4: Update Rules Property
**File**: `src/domain/agents/coordinator_agent.py`
```python
@property
def rules(self) -> list[Rule]:
    """获取所有规则（按优先级排序）"""
    return self._rule_engine_facade.list_decision_rules()
```

---

## Test Files

### Primary Test File
- `tests/unit/domain/agents/test_coordinator_agent.py` - Add integration tests

### Test Coverage Targets
- **Deprecation Warnings**: 100% coverage (all 5 methods)
- **Proxy Behavior**: 100% coverage (verify facade methods called)
- **Backward Compatibility**: Existing tests must pass

---

## Progress Tracking

- [x] Phase 1: Exploration & Analysis
- [x] Phase 2: Development Plan Created
- [ ] Phase 3: TDD Red Phase (Write Failing Tests)
- [ ] Phase 4: TDD Green Phase (Implement Code)
- [ ] Phase 5: Code Review (Codex)
- [ ] Phase 6: Full Test Suite
- [ ] Phase 7: Commit & Cleanup

---

## Key Risks & Mitigations

### Risk 1: Breaking Existing Tests
**Mitigation**: Use proxy pattern to maintain exact same behavior. Existing tests should pass without modification.

### Risk 2: State Sharing Issues
**Mitigation**: RuleEngineFacade already uses `rules_ref` and `statistics_ref` to share state with CoordinatorAgent. No changes needed.

### Risk 3: Session ID Missing
**Mitigation**: Extract `session_id` from decision dict if available: `decision.get("session_id")`

### Risk 4: Thread Safety
**Mitigation**: RuleEngineFacade uses `threading.RLock()`. Direct `_rules/_statistics` access is NOT thread-safe. Integration improves safety.

---

## Files Modified (Tracking)

- [x] `src/domain/agents/coordinator_agent.py`
- [x] `tests/unit/domain/agents/test_coordinator_agent.py`

---

## Known Issues

### CRITICAL: Priority Order Incompatibility
**Issue**: RuleEngineFacade sorts rules in **descending** priority order (reverse=True on line 255 of rule_engine_facade.py), while CoordinatorAgent originally sorted in **ascending** order. This causes `test_rules_checked_by_priority` to fail.

**Impact**: Rules with priority=10 now execute BEFORE rules with priority=1 (opposite of original behavior).

**Root Cause**:
- Old: `sorted(self._rules, key=lambda r: r.priority)` → ascending (1, 2, 3...)
- Facade: `sorted(self._rules, key=lambda r: r.priority, reverse=True)` → descending (10, 9, 8...)

**Resolution Options**:
1. **Fix the Facade** (recommended): Remove `reverse=True` from line 255 & 184 of `rule_engine_facade.py`
2. **Update the Test**: Change test expectations to match new behavior (loses backward compatibility)
3. **Workaround in Proxy**: Override validate_decision to re-sort rules (adds overhead)

**Temporary Status**: Test failure documented. Follow-up task required to fix facade.

**Action Item**: Create issue to fix RuleEngineFacade priority order to match CoordinatorAgent convention.

---

## Notes

- **Backward Compatibility**: 62 files use these methods. Must maintain exact behavior.
- **Performance**: Deprecation warnings have minimal overhead (one warning per call).
- **Thread Safety**: Integration improves thread safety by routing through facade's RLock.
- **Correction Handling**: Facade merges all corrections (better than agent's first-only approach).
- **Priority Convention**: Original convention is lower number = higher priority (1 > 10)

---

**Last Updated**: 2025-12-13
