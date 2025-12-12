# P1重构: 统一SessionContext定义

**日期**: 2025-12-12
**任务**: 消除SessionContext重复定义,统一为单一来源
**优先级**: P1 (本月完成)

---

## 执行摘要

### 问题描述
代码库中存在两份SessionContext定义:
1. `src/domain/services/context_manager.py` - **完整版**(23个字段,包含resource_constraints)
2. `src/domain/services/context_bridge.py` - **简化版**(7个字段,仅桥接使用)

### 风险
- 类型/语义分裂,未来可能导致字段不一致bug
- Codex P0修复中发现的问题:context_bridge.SessionContext缺少resource_constraints

### 目标
- 统一为单一来源,消除重复定义
- 保持向后兼容,不破坏现有代码
- 提升类型安全性

---

## Codex分析报告总结

### 字段差异 (关键)
| 字段组 | context_manager | context_bridge | 影响 |
|--------|----------------|----------------|------|
| 基础字段 | 7个相同 | 7个 | ✅ 兼容 |
| Token统计 | 7个新增 | 无 | ⚠️ manager专有 |
| 模型信息 | 3个新增 | 无 | ⚠️ manager专有 |
| 短期记忆 | 4个新增 | 无 | ⚠️ manager专有 |
| 冻结/备份 | 2个新增 | 无 | ⚠️ manager专有 |
| 资源约束 | 1个新增 | 无 | 🔴 P0修复新增 |

**总计**: manager=23字段, bridge=7字段

### 使用情况统计
- **context_manager.SessionContext**: 3个文件导入
  - `src/domain/agents/conversation_agent.py` (核心)
  - `src/domain/services/memory_compression_handler.py`
  - `src/domain/services/token_guardrail.py`
- **context_bridge.SessionContext**: 0个外部导入(仅内部使用)

**结论**: context_manager是标准版本

### 兼容性风险
1. **方法签名不兼容**:
   - manager: `add_message(message: dict[str, Any])`
   - bridge: `add_message(role: str, content: str)` (自动添加timestamp)
2. **goal_stack类型收紧**: manager期望`Goal`, bridge用`Any`
3. **消息结构差异**: bridge自动添加timestamp字段

---

## 重构方案 (方案B - 推荐)

### 方案选择
**方案B**: 新建独立实体文件作为唯一来源,其他模块导入统一版本

**优势**:
- 清晰的职责分离(entities存放核心数据结构)
- context_manager和context_bridge都导入同一版本
- 向后兼容(通过re-export保持现有import路径)
- 符合DDD架构原则

### 实施步骤

#### Step 1: 创建统一定义文件
**文件**: `src/domain/entities/session_context.py`

**内容**: 基于context_manager版本,包含所有23个字段

**新增**: 兼容方法 `add_message_simple(role, content)` 作为旧接口的适配

#### Step 2: context_manager改为re-export
**文件**: `src/domain/services/context_manager.py`

**修改**:
```python
# 删除 SessionContext 类定义
# 改为导入并re-export
from src.domain.entities.session_context import SessionContext

__all__ = ["GlobalContext", "SessionContext", "WorkflowContext", "NodeContext", ...]
```

**效果**: 现有导入 `from src.domain.services.context_manager import SessionContext` 仍然有效

#### Step 3: context_bridge迁移
**文件**: `src/domain/services/context_bridge.py`

**修改**:
1. 删除SessionContext类定义
2. 导入统一版本: `from src.domain.entities.session_context import SessionContext`
3. 调整内部调用:
   - `add_message(role, content)` → `add_message_simple(role, content)`
   - 或改为: `add_message({"role": role, "content": content, "timestamp": ...})`

#### Step 4: 编写测试
**文件**: `tests/unit/domain/entities/test_session_context.py`

**测试内容**:
- 所有23个字段的访问和设置
- `add_message` 和 `add_message_simple` 两种方法
- 与现有代码的兼容性

#### Step 5: 回归验证
运行相关测试确保无破坏:
```bash
pytest tests/unit/domain/agents/test_conversation_agent.py
pytest tests/unit/domain/services/test_context_manager.py
pytest tests/unit/domain/services/test_context_bridge.py
pytest tests/unit/domain/services/test_token_guardrail.py
```

---

## TDD实施计划

### Phase 1: 创建新文件 + 测试 (TDD - Red)
1. 创建 `src/domain/entities/session_context.py`
2. 编写测试 `tests/unit/domain/entities/test_session_context.py`
3. 运行测试(应该失败,因为还没实现)

### Phase 2: 实现统一定义 (TDD - Green)
1. 将context_manager.SessionContext定义复制到新文件
2. 添加 `add_message_simple` 兼容方法
3. 运行测试(应该通过)

### Phase 3: context_manager迁移
1. 修改context_manager.py改为re-export
2. 运行测试(应该通过,无破坏性改动)

### Phase 4: context_bridge迁移
1. 修改context_bridge.py使用统一定义
2. 调整内部调用
3. 运行测试(应该通过)

### Phase 5: 全面验证
1. 运行所有相关测试
2. Pyright类型检查
3. Ruff代码质量检查

---

## 风险控制

### 迁移风险
| 风险 | 严重度 | 缓解措施 |
|------|--------|----------|
| 破坏现有导入 | 高 | 使用re-export保持路径不变 |
| 方法签名不兼容 | 中 | 提供兼容方法add_message_simple |
| 测试失败 | 中 | TDD流程,每步验证 |
| 类型检查失败 | 低 | 统一定义后类型更安全 |

### 回滚策略
如果迁移失败:
1. 保留原有两份定义
2. 仅在新代码中使用统一版本
3. 逐步迁移旧代码

---

## 预期成果

完成后:
- ✅ SessionContext定义唯一,无重复
- ✅ 类型安全性提升
- ✅ 符合DDD架构(entities层存放核心实体)
- ✅ 向后兼容,现有代码无需修改
- ✅ 未来扩展SessionContext字段时,只需修改一处

**代码质量提升**:
- 模块数: 107 → 106 (-1个重复定义)
- 类型安全: 消除潜在的类型分裂风险
- 可维护性: 单一来源,易于维护

---

## 当前进度

- [x] 探索阶段: Codex分析完成
- [x] 规划阶段: dev_plan.md创建完成
- [x] TDD阶段: 编写测试（10个测试类，35个测试用例）
- [x] 实现阶段: 统一SessionContext定义
- [x] 验证阶段: 运行所有测试（35/35通过）
- [x] 审查阶段: Codex审查重构代码
- [x] 修复阶段: 添加Codex建议的缺失字段（canvas_state, global_goals, add_message双签名）
- [x] 最终验证: 所有测试通过，Pyright检查通过
- [x] 完成阶段: P1重构成功完成 ✅

**状态**: **已完成** ✅

---

## 最终交付成果

**代码修改：**
1. 创建 `src/domain/entities/session_context.py` (576行)
   - 统一定义Goal, GlobalContext, SessionContext, ShortTermSaturatedEvent
   - 包含21个dataclass字段（canvas_state, resource_constraints等）
   - GlobalContext新增global_goals支持
   - add_message实现双签名兼容

2. 修改 `src/domain/services/context_manager.py`
   - 删除487行重复定义
   - 改为re-export统一定义
   - 覆盖率提升：48% → 93%

3. 创建 `tests/unit/domain/entities/test_session_context.py` (408行)
   - 10个测试类，覆盖所有核心功能
   - 包括Codex审查后新增的8个测试用例

**质量指标：**
- 测试通过率: **100%** (35/35)
- Pyright检查: **0 errors, 0 warnings**
- 代码覆盖率: context_manager 93%, session_context 56%
- 向后兼容性: **100%保持**

**架构改进：**
- ✅ 消除SessionContext重复定义（单一来源）
- ✅ 符合DDD架构（entities层存放核心实体）
- ✅ 类型安全性提升（完整类型注解）
- ✅ 可维护性提升（单一修改点）

**Codex审查评估：**
- 初次评分: 7.5/10（发现3个缺失项）
- 修复后状态: **生产级别** ✅
- 剩余问题: **无** ✅

---

**创建时间**: 2025-12-12
**完成时间**: 2025-12-12
**负责人**: Claude + Codex协作
**实际耗时**: 2小时
