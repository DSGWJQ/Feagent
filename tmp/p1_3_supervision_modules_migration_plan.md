# supervision_modules.py 兼容层清理方案

**创建日期**: 2025-12-13
**预估工时**: 2小时（实际范围比预期小）
**风险等级**: Low

---

## 执行摘要

**影响范围**: 7个文件（3测试 + 4生产），65行导入语句

**迁移策略**: 批量替换 + 手动验证生产文件

**预估风险**: Low
- 仅修改导入路径，不改逻辑
- API完全兼容（supervision/__init__.py已导出所有组件）
- 测试覆盖充分（80+ 测试）

**预估工时**: 2小时
- 迁移执行：30分钟
- 测试验证：1小时
- Deprecation警告：30分钟

---

## 影响文件清单

### 测试文件（3个，61行导入）

#### 1. tests/unit/domain/services/test_supervision_modules.py
- **导入数量**: 50行
- **导入模式**: 内联导入（每个测试函数内部导入）
- **风险**: 无
- **示例**:
```python
# Line 32
from src.domain.services.supervision_modules import SupervisionCoordinator

# Line 40
from src.domain.services.supervision_modules import DetectionResult

# ... 48 more similar imports
```

#### 2. tests/regression/test_coordinator_regression.py
- **导入数量**: 9行
- **导入模式**: 内联导入
- **风险**: 无
- **组件**: ConversationSupervisionModule, WorkflowEfficiencyMonitor, StrategyRepository, SupervisionCoordinator, ComprehensiveCheckResult, DetectionResult, Alert, AlertKnowledgeHandler

#### 3. tests/unit/domain/services/test_supervision_facade.py
- **导入数量**: 2行
- **导入模式**: 内联导入
- **风险**: 无
- **组件**: ComprehensiveCheckResult, DetectionResult

---

### 生产文件（4个，4行导入）

#### 1. src/domain/services/coordinator_bootstrap.py ⚠️ 高优先级
- **导入数量**: 1行
- **导入位置**: Line 49 (模块顶部)
- **风险**: **中** - Bootstrap核心文件
- **代码**:
```python
from src.domain.services.supervision_modules import SupervisionCoordinator
```

#### 2. src/domain/services/supervision_facade.py
- **导入数量**: 1行
- **导入位置**: Line 265 (函数内部懒加载)
- **风险**: 低 - 内部实现细节
- **代码**:
```python
from src.domain.services.supervision_modules import ComprehensiveCheckResult
```

#### 3. src/domain/services/supervision_strategy.py
- **导入数量**: 1行（多行导入开始）
- **导入位置**: Line 39
- **风险**: 低
- **代码**:
```python
from src.domain.services.supervision_modules import (
    ContextInjectionEvent,
    TaskTerminationEvent,
    TerminationResult,
    WorkflowEfficiencyMonitor,
)
```

#### 4. src/domain/services/supervision_modules.py
- **导入数量**: 1行（文档示例，自引用）
- **导入位置**: Line 17
- **风险**: 无 - 仅文档
- **代码**:
```python
from src.domain.services.supervision_modules import SupervisionCoordinator  # 仍可用
```
**处理**: 修改为 `from src.domain.services.supervision import SupervisionCoordinator`

---

## 迁移策略

### 策略选择: 批量替换 + 手动验证（推荐）

**理由**:
- 仅7个文件，范围可控
- 导入模式统一（都是 `from X import Y`）
- API完全兼容
- 生产文件少（仅4个），可手动验证

**不选择Python脚本**: 过度工程化（仅7个文件）

---

## 详细迁移步骤

### Step 1: 备份当前状态
```bash
git status
git diff  # 确认无未提交改动
```

### Step 2: 批量替换（PowerShell）
```powershell
# 批量替换tests/和src/中所有.py文件
Get-ChildItem -Recurse -Include *.py tests/, src/domain/services/ | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $newContent = $content -replace
        'from src\.domain\.services\.supervision_modules import',
        'from src.domain.services.supervision import'

    if ($content -ne $newContent) {
        Set-Content $_.FullName -Value $newContent -NoNewline
        Write-Host "Updated: $($_.FullName)"
    }
}
```

**预期输出**:
```
Updated: tests/unit/domain/services/test_supervision_modules.py
Updated: tests/regression/test_coordinator_regression.py
Updated: tests/unit/domain/services/test_supervision_facade.py
Updated: src/domain/services/coordinator_bootstrap.py
Updated: src/domain/services/supervision_facade.py
Updated: src/domain/services/supervision_strategy.py
Updated: src/domain/services/supervision_modules.py
```

### Step 3: 验证替换结果
```bash
# 确认所有导入已替换
grep -r "from.*supervision_modules import" tests/ src/ --include="*.py"
# 预期输出：空（所有已替换）

# 确认新导入存在
grep -r "from.*supervision import" tests/unit/domain/services/test_supervision_modules.py | wc -l
# 预期输出：50

# 语法检查
ruff check tests/unit/domain/services/test_supervision_modules.py
ruff check src/domain/services/coordinator_bootstrap.py
```

### Step 4: 手动验证生产文件（关键！）

#### 4.1 coordinator_bootstrap.py
```bash
# 读取文件确认替换正确
grep "from.*supervision import" src/domain/services/coordinator_bootstrap.py
```
**预期**: `from src.domain.services.supervision import SupervisionCoordinator`

#### 4.2 supervision_facade.py
**预期**: `from src.domain.services.supervision import ComprehensiveCheckResult`

#### 4.3 supervision_strategy.py
**预期**: 多行导入完整保留，仅路径改变

#### 4.4 supervision_modules.py
**预期**: 文档示例已更新

### Step 5: 运行单元测试
```bash
# 测试supervision相关模块
pytest tests/unit/domain/services/test_supervision_module.py -v
pytest tests/unit/domain/services/test_supervision_modules.py -v
pytest tests/unit/domain/services/test_supervision_facade.py -v
```

**预期结果**: 所有测试通过（约60个测试）

### Step 6: 运行回归测试
```bash
pytest tests/regression/test_coordinator_regression.py -v
```

**预期结果**: 所有测试通过（约20个测试）

### Step 7: 运行集成测试（可选）
```bash
pytest tests/integration/test_coordinator_integration.py -v
```

### Step 8: 添加Deprecation警告

编辑 `src/domain/services/supervision_modules.py`，在导入语句之前添加：

```python
"""监督模块（向后兼容）

⚠️ DEPRECATED: 本模块已在 Phase 34.14 拆分为子包 `supervision/`
...
"""

from __future__ import annotations

# ==================== DEPRECATION WARNING ====================
import warnings

warnings.warn(
    "supervision_modules.py is deprecated (Phase 34.14). "
    "Use 'from src.domain.services.supervision import XXX' instead. "
    "This module will be removed in version 2.0 (2026-06-01).",
    DeprecationWarning,
    stacklevel=2
)

# ==================== 向后兼容导入 ====================
# 从新包导入所有组件并重新导出
from src.domain.services.supervision import (
    ...
)
```

**注意**: `stacklevel=2` 确保警告指向调用方而非本模块

### Step 9: 验证警告触发
```bash
# 创建测试脚本
echo "from src.domain.services.supervision_modules import SupervisionCoordinator" > test_warning.py
python test_warning.py
# 预期输出：DeprecationWarning
rm test_warning.py
```

### Step 10: 提交改动
```bash
git add tests/ src/domain/services/
git commit -m "refactor(P1-3): 迁移supervision_modules到supervision子包

清理supervision_modules.py兼容层（Phase 34.14）

## 改动范围

迁移7个文件的导入路径：
- 测试文件（3个）: test_supervision_modules.py (50行),
  test_coordinator_regression.py (9行), test_supervision_facade.py (2行)
- 生产文件（4个）: coordinator_bootstrap.py, supervision_facade.py,
  supervision_strategy.py, supervision_modules.py

从: from src.domain.services.supervision_modules import XXX
到: from src.domain.services.supervision import XXX

## 测试验证

- ✅ 单元测试通过（60+ 测试）
- ✅ 回归测试通过（20+ 测试）
- ✅ 语法检查通过

## Deprecation警告

在supervision_modules.py添加DeprecationWarning，计划移除日期：2026-06-01

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## 风险缓解措施

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 导入冲突（supervision vs supervision_modules） | 低 | 中 | 替换前检查无混合使用 |
| Bootstrap失败 | 低 | 高 | 手动验证coordinator_bootstrap.py |
| 测试失败 | 低 | 中 | 分阶段验证（单元→回归→集成） |
| 警告影响测试 | 中 | 低 | 使用stacklevel=2，测试框架通常过滤DeprecationWarning |

---

## 回滚计划

如果任何步骤失败：

```bash
# 方案1: Git回退
git reset --hard HEAD

# 方案2: 恢复特定文件
git checkout HEAD -- tests/unit/domain/services/test_supervision_modules.py
git checkout HEAD -- src/domain/services/coordinator_bootstrap.py

# 方案3: 手动反向替换（如需）
# 将 'from...supervision import' 替换回 'from...supervision_modules import'
```

---

## 迁移前后对比

### 示例1: test_supervision_modules.py

**迁移前**:
```python
def test_supervision_coordinator_initialization():
    from src.domain.services.supervision_modules import SupervisionCoordinator

    coordinator = SupervisionCoordinator(event_bus=None)
    assert coordinator is not None
```

**迁移后**:
```python
def test_supervision_coordinator_initialization():
    from src.domain.services.supervision import SupervisionCoordinator

    coordinator = SupervisionCoordinator(event_bus=None)
    assert coordinator is not None
```

### 示例2: coordinator_bootstrap.py

**迁移前**:
```python
# Line 49
from src.domain.services.supervision_modules import SupervisionCoordinator

# Line 890
supervision_coordinator = SupervisionCoordinator(
    event_bus=self.config.event_bus,
    ...
)
```

**迁移后**:
```python
# Line 49
from src.domain.services.supervision import SupervisionCoordinator

# Line 890 (no change)
supervision_coordinator = SupervisionCoordinator(
    event_bus=self.config.event_bus,
    ...
)
```

---

## 预期测试输出

### 单元测试
```
tests/unit/domain/services/test_supervision_module.py::test_... PASSED [100%]
tests/unit/domain/services/test_supervision_modules.py::test_... PASSED [100%]
tests/unit/domain/services/test_supervision_facade.py::test_... PASSED [100%]

========================= 60 passed in 5.23s =========================
```

### 回归测试
```
tests/regression/test_coordinator_regression.py::test_... PASSED [100%]

========================= 20 passed in 15.67s =========================
```

---

## 后续工作（未来版本）

### Phase 2: 删除兼容层（2026年6月1日后）

**前置条件**:
- 本次迁移完成
- 2个版本稳定期（6个月）
- 外部依赖确认无使用

**步骤**:
1. 删除 `supervision_modules.py`
2. 更新文档移除deprecated说明
3. 全量测试验证

---

**方案创建**: 2025-12-13
**方案状态**: Ready for Execution
**执行者**: Claude + User Approval
