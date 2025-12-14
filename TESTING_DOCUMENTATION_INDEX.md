# Feagent 后端测试计划 - 文档导航

> **生成时间**: 2025-12-14
> **文档系列**: 分析摘要 + 快速参考 + 执行清单
> **项目阶段**: 多Agent协作系统 (Phase 8+)

---

## 📚 文档系列概览

本测试计划分为以下4个文档，按用途递进：

| 文档 | 路径 | 用途 | 读者 | 预计阅读时间 |
|------|------|------|------|------------|
| **📋 原始计划** | `docs/testing/BACKEND_TESTING_PLAN.md` | 完整规划和设计依据 | 测试管理/架构师 | 30min |
| **📊 分析摘要** | `TESTING_ANALYSIS_SUMMARY.md` | 需求分解、关键模块分析 | 项目经理/Lead | 20min |
| **⚡ 快速参考** | `TESTING_QUICK_REFERENCE.md` | 测试模板、常见问题、速查表 | 开发人员 | 15min |
| **✅ 执行清单** | `TESTING_EXECUTION_CHECKLIST.md` | 逐步操作指南、具体代码示例 | 执行人员 | 45min |

---

## 🎯 快速导航（按角色）

### 👨‍💼 项目经理 / 测试负责人

**第一步**: 阅读执行摘要
- 文档: `docs/testing/BACKEND_TESTING_PLAN.md` (Section 1.1-1.3)
- 内容: 核心指标、问题诊断、行动优先级
- 时间: 5 minutes

**第二步**: 理解总体计划
- 文档: `TESTING_ANALYSIS_SUMMARY.md` (Section 1-3)
- 内容: 需求摘要、关键模块、优先级矩阵
- 时间: 15 minutes

**第三步**: 追踪里程碑进度
- 文档: `TESTING_QUICK_REFERENCE.md` (Section "📈 进度追踪")
- 内容: 5个里程碑的检查清单
- 时间: 5 minutes

**建议**: 每周查看一次里程碑进度，根据 `TESTING_EXECUTION_CHECKLIST.md` 中的状态表进度。

---

### 👨‍💻 后端开发 / 测试工程师

**第一步**: 了解整体架构
- 文档: `TESTING_ANALYSIS_SUMMARY.md` (Section 4-6)
- 内容: 测试策略、测试模板、覆盖点
- 时间: 10 minutes

**第二步**: 查看P0/P1实施细节
- 文档: `TESTING_EXECUTION_CHECKLIST.md` (Section P0/P1)
- 内容: 具体代码修改、操作步骤、验证方法
- 时间: 30 minutes

**第三步**: 使用测试模板和快速参考
- 文档: `TESTING_QUICK_REFERENCE.md` (Section "📋 测试模板库")
- 内容: Domain/UseCase/API/异步/参数化的5个模板
- 时间: 15 minutes (参考)

**第四步**: 编写具体测试
- 参考: `TESTING_QUICK_REFERENCE.md` + `TESTING_EXECUTION_CHECKLIST.md`
- 工作: 选择相应的模板，填充具体的测试用例

---

### 🔍 QA / 测试验证

**建议流程**:
1. 阅读 `TESTING_ANALYSIS_SUMMARY.md` 了解测试类型和策略
2. 查看 `TESTING_QUICK_REFERENCE.md` 的"常见问题排查"部分
3. 运行验收命令 (`TESTING_EXECUTION_CHECKLIST.md` 末尾)

---

## 📖 分章节导航

### 需求和范围定义

**要了解**:
- 当前测试状态（覆盖率仅14.9%）
- 核心瓶颈（Domain/services仅4.9%）
- 优先级划分（P0-P3分别对应不同时间表）

**查看**:
- `TESTING_ANALYSIS_SUMMARY.md` - Section 1 (需求摘要)
- `docs/testing/BACKEND_TESTING_PLAN.md` - Section 1-2

---

### 关键模块分析

**要找**:
- P0/P1/P2/P3各阶段需要测试的模块清单
- 每个模块的风险等级和预计用例数
- 测试文件应该创建在哪个位置

**查看**:
- `TESTING_ANALYSIS_SUMMARY.md` - Section 2 (相关文件)
  - P0级别（配置修改）
  - P1级别（7个UseCase）
  - P2级别（18个Service模块）
  - P3级别（18个Agent模块）

---

### 测试策略和方法

**要学习**:
- 单元测试如何编写
- 集成测试如何隔离依赖
- 异步/参数化/Mock的最佳实践

**查看**:
- `TESTING_ANALYSIS_SUMMARY.md` - Section 4 (测试策略)
- `TESTING_QUICK_REFERENCE.md` - Section "📋 测试模板库"

---

### 具体实施指南

**要做**:
- 修改pyproject.toml
- 增强conftest.py
- 创建7个UseCase测试
- 一步步修复和验证

**查看**:
- `TESTING_EXECUTION_CHECKLIST.md` 中的每个子任务
- 每个子任务都包含：
  - 文件位置
  - 操作步骤
  - 验证方法

---

### 常见问题排查

**遇到**:
- ImportError / 依赖注入失败 / SQLite锁定 / Mock问题

**查看**:
- `TESTING_QUICK_REFERENCE.md` - Section "🔍 常见问题排查"

---

## 🚀 推荐工作流

### 开发人员日常工作流

```
Day 1 (P0):
├─ 阅读: TESTING_EXECUTION_CHECKLIST.md - P0部分 (30min)
├─ 实施: 5个P0子任务 (3h)
├─ 验证: pytest --ignore=tests/manual -x (30min)
└─ 结果: CI变绿 ✅

Day 2-5 (P1):
├─ 选择: 一个UseCase模块
├─ 查看: TESTING_QUICK_REFERENCE.md中的UseCase模板
├─ 编写: 12-20个测试用例 (2-3h)
├─ 验证: pytest tests/unit/application/ --cov=... (30min)
└─ 迭代: 直到覆盖率达到70%+

Week 2-4 (P2-P3):
├─ 重复: 上述工作流
├─ 参考: TESTING_ANALYSIS_SUMMARY.md中的模块清单
└─ 追踪: TESTING_QUICK_REFERENCE.md中的进度表
```

### 周期性检查（PM/Lead）

```
每周一：
├─ 查看: TESTING_EXECUTION_CHECKLIST.md中的状态表
├─ 检查: 上周完成多少个任务
└─ 调整: 下周计划

每个里程碑：
├─ 验证: 覆盖率是否达到目标
├─ 测试: pytest --cov=src --cov-report=html
└─ 更新: TESTING_QUICK_REFERENCE.md中的进度追踪
```

---

## 📊 关键指标一览

### 覆盖率目标

```
当前值  →  目标值  (时间表)
14.9%  →  50%  (Week 4 - M5)
├─ Domain:      11.1% → 60% (P2/P3完成)
├─ Application: 27.4% → 70% (P1完成)
└─ Infrastructure: 31.3% → 50% (P2完成)
```

### 测试用例统计

```
P0:  5个任务 (配置修改)
P1:  81-101个用例 (7个UseCase)
P2:  180-220个用例 (18个Service模块)
P3:  250-300个用例 (18个Agent模块)
───────────────────────────
总计: 511-626个新测试用例
工作量: ~60-80 engineer-days
```

### 里程碑时间表

```
Week 1:  P0 完成 (M1: CI绿灯)
Week 2:  P1 完成 (M2: Application ≥70%)
Week 3:  P2-1 完成 (M3部分: Core Services ≥50%)
Week 4:  P2-2/P3 完成 (M4/M5: Agents ≥60%, 总体 ≥50%)
```

---

## 🔗 交叉参考索引

### 按优先级

**P0 (Critical - 1-2 days)**
- 位置: `TESTING_EXECUTION_CHECKLIST.md` - P0部分
- 内容: pytest配置、conftest.py、FastAPI修复、TDD Red标记、SQLite隔离
- 关键模块: 无 (只是基础设施)

**P1 (High - 1 week)**
- 位置: `TESTING_ANALYSIS_SUMMARY.md` - Section 2.2 + Section 5.2
- 位置: `TESTING_EXECUTION_CHECKLIST.md` - P1部分
- 模块: `execute_run`, `classify_task`, `update_workflow_by_chat` 等7个UseCase
- 示例: `TESTING_QUICK_REFERENCE.md` - UseCase单元测试模板

**P2 (Medium - 2 weeks)**
- 位置: `TESTING_ANALYSIS_SUMMARY.md` - Section 2.3 + Section 5.3
- 模块: ConfigurableRuleEngine, SelfDescribingNodeValidator等18个
- 示例: `TESTING_QUICK_REFERENCE.md` - Domain实体/服务测试模板

**P3 (Low - 2 weeks)**
- 位置: `TESTING_ANALYSIS_SUMMARY.md` - Section 2.4 + Section 5.4
- 模块: ErrorHandling, ReActCore, ConversationAgentState等18个
- 示例: `TESTING_QUICK_REFERENCE.md` - Agent状态机/错误处理模板

---

### 按文件类型

**配置文件修改**
- pyproject.toml: `TESTING_EXECUTION_CHECKLIST.md` - 子任务1
- conftest.py: `TESTING_EXECUTION_CHECKLIST.md` - 子任务2-5

**新增测试文件**
- Application层: `TESTING_ANALYSIS_SUMMARY.md` - Section 3.2
- Domain层: `TESTING_ANALYSIS_SUMMARY.md` - Section 3.3-3.4

**测试代码示例**
- Domain: `TESTING_QUICK_REFERENCE.md` - 模板1
- Application: `TESTING_QUICK_REFERENCE.md` - 模板2
- Integration: `TESTING_QUICK_REFERENCE.md` - 模板3
- Async: `TESTING_QUICK_REFERENCE.md` - 模板4
- Parametrized: `TESTING_QUICK_REFERENCE.md` - 模板5

---

## ✅ 检查清单

### 在开始之前

- [ ] 已读 `docs/testing/BACKEND_TESTING_PLAN.md` 至少一遍
- [ ] 已了解当前覆盖率状态（14.9%）
- [ ] 已理解P0-P3四阶段划分
- [ ] 已准备好 `TESTING_QUICK_REFERENCE.md` 作为参考手册

### P0阶段开始前

- [ ] 已获得 `TESTING_EXECUTION_CHECKLIST.md` 的P0部分
- [ ] 已有修改pyproject.toml和conftest.py的计划
- [ ] 已确认FastAPI集成测试的位置
- [ ] 已标记所有TDD Red阶段的测试

### P1阶段开始前

- [ ] P0已完成，CI已变绿
- [ ] 已获得7个UseCase的清单 (`TESTING_ANALYSIS_SUMMARY.md` Section 2.2)
- [ ] 已选择开发顺序
- [ ] 已准备UseCase测试模板 (`TESTING_QUICK_REFERENCE.md`)

---

## 📞 常见问题快速查询

| 问题 | 查看 |
|------|------|
| 我应该从哪里开始? | 本文档的"推荐工作流" |
| 当前的问题有多严重? | `TESTING_ANALYSIS_SUMMARY.md` - Section 1.2 |
| 哪些模块最关键? | `TESTING_ANALYSIS_SUMMARY.md` - Section 2（按P0-P3级别） |
| 如何修改pyproject.toml? | `TESTING_EXECUTION_CHECKLIST.md` - 子任务1 |
| 如何写一个UseCase测试? | `TESTING_QUICK_REFERENCE.md` - 模板2 + `TESTING_EXECUTION_CHECKLIST.md` - P1 |
| pytest命令如何运行? | `TESTING_QUICK_REFERENCE.md` - "🚀 快速启动命令" |
| 遇到ImportError怎么办? | `TESTING_QUICK_REFERENCE.md` - "🔍 常见问题排查" |

---

## 🎓 学习路径

### 新人快速上手 (2小时)

```
1. 读本文档 (10min)
2. 读TESTING_ANALYSIS_SUMMARY.md的Section 1-2 (15min)
3. 看TESTING_QUICK_REFERENCE.md的5个模板 (30min)
4. 阅读TESTING_EXECUTION_CHECKLIST.md的P0部分 (30min)
5. 运行P0的第一个任务 (15min)
```

### 深度理解 (4小时)

```
1. 完整阅读docs/testing/BACKEND_TESTING_PLAN.md (1h)
2. 分析TESTING_ANALYSIS_SUMMARY.md的所有部分 (1h)
3. 研究TESTING_QUICK_REFERENCE.md的所有模板和问题 (1h)
4. 学习TESTING_EXECUTION_CHECKLIST.md的所有子任务 (1h)
```

### 实战应用 (每日)

```
每天选择一个模块:
1. 在TESTING_ANALYSIS_SUMMARY.md中找到模块信息
2. 从TESTING_QUICK_REFERENCE.md选择相应模板
3. 按TESTING_EXECUTION_CHECKLIST.md的步骤修改代码
4. 运行测试验证
5. 更新进度表
```

---

## 📝 文档维护

| 文档 | 维护人 | 更新频率 | 最后更新 |
|------|--------|----------|----------|
| `docs/testing/BACKEND_TESTING_PLAN.md` | Team | 每个阶段 | 2025-12-14 |
| `TESTING_ANALYSIS_SUMMARY.md` | Claude Code | 一次性 | 2025-12-14 |
| `TESTING_QUICK_REFERENCE.md` | Claude Code | 需要时 | 2025-12-14 |
| `TESTING_EXECUTION_CHECKLIST.md` | Claude Code | 每个任务后 | 2025-12-14 |
| **本索引文档** | Claude Code | 每个新版本 | 2025-12-14 |

---

## 📎 相关文档

- [架构审计](docs/architecture/current_agents.md)
- [多Agent协作指南](docs/architecture/multi_agent_collaboration_guide.md)
- [运维手册](docs/operations/operations_guide.md)
- [CLAUDE.md项目规范](CLAUDE.md)

---

**最后更新**: 2025-12-14
**下次审查**: P0完成后
**联系方式**: 查看git blame了解各部分维护人
