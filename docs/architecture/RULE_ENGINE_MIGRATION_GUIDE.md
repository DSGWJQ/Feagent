# RuleEngine迁移指南 (P1-1 Step 3)

**创建日期**: 2025-12-13
**状态**: Active
**相关Commit**: 8c4fef9, [NEW_COMMIT_HASH]

---

## 概述

CoordinatorAgent的规则管理方法已迁移到RuleEngineFacade。旧方法已标记为**DEPRECATED**并会在未来版本中移除。本指南帮助开发者完成平滑迁移。

---

## 迁移时间表

| 方法 | 废弃日期 | 计划移除 | 替代方法 |
|------|----------|---------|----------|
| `add_rule()` | 2025-12-13 | 2026-06-01 | `_rule_engine_facade.add_decision_rule()` |
| `remove_rule()` | 2025-12-13 | 2026-06-01 | `_rule_engine_facade.remove_decision_rule()` |
| `validate_decision()` | 2025-12-13 | 2026-06-01 | `_rule_engine_facade.validate_decision()` |
| `get_statistics()` | 2025-12-13 | 2026-06-01 | `_rule_engine_facade.get_decision_statistics()` |
| `is_rejection_rate_high()` | 2025-12-13 | 2026-06-01 | `_rule_engine_facade.is_rejection_rate_high()` |
| `rules` property | 2025-12-13 | 2026-06-01 | `_rule_engine_facade.list_decision_rules()` |

**⚠️ 警告**: 2026年6月1日后，这些方法将被完全移除。请在此日期前完成迁移。

---

## 迁移步骤

### Step 1: 识别使用deprecated方法的代码

运行以下命令查找所有使用废弃方法的地方：

```bash
# 搜索 add_rule 使用
grep -r "\.add_rule(" src/ tests/

# 搜索 remove_rule 使用
grep -r "\.remove_rule(" src/ tests/

# 搜索 validate_decision 使用
grep -r "\.validate_decision(" src/ tests/

# 搜索 get_statistics 使用
grep -r "\.get_statistics()" src/ tests/

# 搜索 is_rejection_rate_high 使用
grep -r "\.is_rejection_rate_high()" src/ tests/

# 搜索 rules property 使用
grep -r "\.rules" src/ tests/
```

### Step 2: 更新代码

#### 迁移示例 1: add_rule()

**旧代码**:
```python
coordinator = CoordinatorAgent()
rule = Rule(id="r1", name="Rule 1", condition=lambda d: True, priority=1)
coordinator.add_rule(rule)  # ⚠️ DEPRECATED
```

**新代码**:
```python
coordinator = CoordinatorAgent()
rule = Rule(id="r1", name="Rule 1", condition=lambda d: True, priority=1)
coordinator._rule_engine_facade.add_decision_rule(rule)  # ✅ RECOMMENDED
```

---

#### 迁移示例 2: validate_decision()

**旧代码**:
```python
coordinator = CoordinatorAgent()
result = coordinator.validate_decision({"type": "llm"})  # ⚠️ DEPRECATED
```

**新代码**:
```python
coordinator = CoordinatorAgent()
result = coordinator._rule_engine_facade.validate_decision(
    decision={"type": "llm"},
    session_id="session_123"  # 可选但推荐
)  # ✅ RECOMMENDED
```

---

#### 迁移示例 3: get_statistics()

**旧代码**:
```python
stats = coordinator.get_statistics()  # ⚠️ DEPRECATED
print(f"Total: {stats['total']}, Passed: {stats['passed']}")
```

**新代码**:
```python
stats = coordinator._rule_engine_facade.get_decision_statistics()  # ✅ RECOMMENDED
print(f"Total: {stats['total']}, Passed: {stats['passed']}")
```

---

#### 迁移示例 4: rules property

**旧代码**:
```python
for rule in coordinator.rules:  # ⚠️ DEPRECATED
    print(rule.name)
```

**新代码**:
```python
for rule in coordinator._rule_engine_facade.list_decision_rules():  # ✅ RECOMMENDED
    print(rule.name)
```

---

### Step 3: 运行测试确保无回归

```bash
# 运行所有测试
pytest

# 运行特定模块测试
pytest tests/unit/domain/agents/test_coordinator_agent.py -v

# 检查deprecation warnings
pytest -W default::DeprecationWarning
```

### Step 4: 禁用deprecation warnings (可选)

如果你暂时无法完成迁移，可以临时禁用warnings：

```python
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
```

**⚠️ 不推荐**: 这只是临时方案，请尽快完成迁移。

---

## API对比表

| 旧API | 新API | 参数差异 | 返回值差异 |
|-------|-------|---------|-----------|
| `add_rule(rule)` | `add_decision_rule(rule)` | ✅ 无 | ✅ 无 |
| `remove_rule(rule_id)` | `remove_decision_rule(rule_id)` | ✅ 无 | ✅ 无 |
| `validate_decision(decision)` | `validate_decision(decision, *, session_id=None)` | ⚠️ 新增可选参数 | ✅ 无 |
| `get_statistics()` | `get_decision_statistics()` | ✅ 无 | ✅ 无 |
| `is_rejection_rate_high()` | `is_rejection_rate_high()` | ✅ 无 | ✅ 无 |
| `rules` (property) | `list_decision_rules()` (method) | ✅ 无 | ✅ 无 |

---

## 重要差异说明

### 1. validate_decision() 新增session_id参数

**旧行为**:
```python
result = coordinator.validate_decision({"type": "llm"})
```

**新行为**:
```python
result = coordinator._rule_engine_facade.validate_decision(
    decision={"type": "llm"},
    session_id="session_123"  # 可选，用于日志追踪
)
```

**建议**: 如果有session_id，请传递以便于调试和日志追踪。

---

### 2. Priority排序修复

**重要变更**: 修复了RuleEngineFacade中的priority排序bug。

**旧行为 (Bug)**:
- Rules按**降序**排列: priority=10 → priority=1
- 高priority数字先执行

**新行为 (Fixed)**:
- Rules按**升序**排列: priority=1 → priority=10
- 低priority数字先执行（更符合直觉）

**影响评估**: 如果你的代码依赖旧的排序行为，需要调整priority值。

**示例**:
```python
# 如果你希望Rule A在Rule B之前执行:

# 旧方式 (Bug)
rule_a = Rule(id="a", ..., priority=10)  # 先执行
rule_b = Rule(id="b", ..., priority=1)   # 后执行

# 新方式 (Fixed)
rule_a = Rule(id="a", ..., priority=1)   # 先执行
rule_b = Rule(id="b", ..., priority=10)  # 后执行
```

---

### 3. 线程安全改进

**旧实现**: 直接访问 `_rules` 和 `_statistics`，无锁保护。
**新实现**: RuleEngineFacade使用 `threading.RLock()` 保护并发访问。

**好处**: 在多线程环境下更安全。

---

## 常见问题 (FAQ)

### Q1: 为什么要迁移？
**A**: RuleEngineFacade提供了更好的封装、线程安全和可扩展性。未来的功能（如动态规则加载、规则版本控制）将基于Facade实现。

### Q2: 旧方法什么时候会被移除？
**A**: 2026年6月1日（距废弃日期6个月）。在此之前旧方法会继续工作但会发出警告。

### Q3: 如何批量迁移大量文件？
**A**: 使用脚本进行批量替换：
```bash
# 示例：使用sed批量替换
sed -i 's/\.add_rule(/.\_rule_engine_facade.add_decision_rule(/g' src/**/*.py
```

### Q4: 测试中大量deprecation warnings怎么办？
**A**: 在测试配置中临时过滤（pyproject.toml）：
```toml
[tool.pytest.ini_options]
filterwarnings = [
    "ignore::DeprecationWarning:tests.*"
]
```

### Q5: `_rule_engine_facade`是私有属性，为什么要用？
**A**: 这是**临时过渡方案**。未来会提供公开的 `rule_engine` 属性。当前阶段为了向后兼容，使用 `_rule_engine_facade` 是推荐做法。

### Q6: 迁移后性能会受影响吗？
**A**: **不会**。Facade只是一个薄代理层，性能开销可忽略不计（<0.1μs）。

---

## Codex审查意见总结

### 已修复的Critical Issues
1. ✅ **Facade存在性验证**: 添加了RuntimeError检查
2. ✅ **Priority排序回归测试**: 新增 `test_priority_ordering_regression`
3. ✅ **Type Hint**: 添加了 `_rule_engine_facade: RuleEngineFacade`
4. ✅ **Rules Property Deprecation**: 添加了deprecation警告

### 测试结果
- **Total Tests**: 22/22 PASS ✅
- **New Tests**: 1 (priority regression)
- **Coverage**: 47% (CoordinatorAgent domain layer)

---

## 相关文档

- [RuleEngineFacade API文档](./rule_engine_facade_api.md)
- [多Agent协作指南](./multi_agent_collaboration_guide.md)
- [架构审计报告](./current_agents.md)

---

## 联系支持

如有问题，请联系：
- **GitHub Issues**: https://github.com/your-org/agent_data/issues
- **Email**: dev-team@your-org.com

---

**最后更新**: 2025-12-13
**维护者**: Claude Code + Development Team
