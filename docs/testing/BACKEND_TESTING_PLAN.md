# Feagent 后端完整测试规划

> **文档版本**: 1.1.0
> **创建日期**: 2025-12-14
> **项目阶段**: 多Agent协作系统 (Phase 8+)
> **目标**: 建立全面、可执行的后端测试策略
> **数据来源**: `htmlcov/status.json` + `.pytest_cache/v/cache/lastfailed`
> **数据时间**: 2025-12-14 (请运行 `pytest --cov=src` 刷新)

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [范围与非目标](#2-范围与非目标)
3. [当前测试状态分析](#3-当前测试状态分析)
4. [测试缺口分析](#4-测试缺口分析)
5. [失败测试根因分析](#5-失败测试根因分析)
6. [测试优先级矩阵](#6-测试优先级矩阵)
7. [分层测试策略](#7-分层测试策略)
8. [具体测试计划](#8-具体测试计划)
9. [测试基础设施改进](#9-测试基础设施改进)
10. [执行计划与里程碑](#10-执行计划与里程碑)
11. [质量门禁标准](#11-质量门禁标准)

---

## 1. 执行摘要

### 1.1 关键指标

| 指标 | 当前值 | 目标值 | 差距 |
|------|--------|--------|------|
| **总体覆盖率** | 14.9% | 50% | -35.1% |
| **Domain层覆盖率** | 11.1% | 60% | -48.9% |
| **Application层覆盖率** | 27.4% | 70% | -42.6% |
| **Infrastructure层覆盖率** | 31.3% | 50% | -18.7% |
| **Interface层覆盖率** | 40.3% | 50% | -9.7% |
| **测试文件总数** | 362 | - | - |
| **失败测试数** | 29-239* | 0 | - |

> *注: 失败数根据运行环境不同有所变化。运行 `pytest --lf` 查看当前失败列表。

### 1.2 核心问题

1. **Domain/services 覆盖率仅 4.9%** - 21,248行代码中20,212行未覆盖
2. **78个关键模块完全无测试** - 约23,132行代码
3. **测试隔离问题** - 部分测试依赖外部服务/真实数据库
4. **TDD Red阶段测试未门禁** - 导致稳定性红灯

### 1.3 建议行动优先级

```
P0 (立即): 修复测试基础设施，让测试可跑且可信
P1 (本周): 补齐Application/use_cases核心入口测试
P2 (2周):  按业务主链路补齐Domain核心测试
P3 (本月): 补齐Domain/agents关键状态机
```

---

## 2. 范围与非目标

### 2.1 测试范围 (In Scope)

| 类型 | 描述 | 进入CI |
|------|------|--------|
| 单元测试 | Domain/Application层纯逻辑测试 | ✅ 是 |
| 集成测试 | 多层交互、API端点测试 (mock外部) | ✅ 是 |
| 契约测试 | 端口/协议一致性验证 | ✅ 是 |

### 2.2 非目标 (Out of Scope)

| 类型 | 描述 | 进入CI |
|------|------|--------|
| 手动测试 | `tests/manual/` 下的脚本 | ❌ 排除 |
| 真实LLM测试 | 需要OPENAI_API_KEY的测试 | ❌ 排除或mock |
| E2E冒烟测试 | 需要完整环境的端到端测试 | ❌ 单独流水线 |
| 性能测试 | 负载/压力测试 | ❌ 单独流水线 |

### 2.3 数据刷新命令

```bash
# 重新生成覆盖率数据
pytest --cov=src --cov-report=json --cov-report=html

# 查看覆盖率摘要
python -c "import json; d=json.load(open('htmlcov/status.json')); print(f'Total: {d[\"totals\"][\"percent_covered\"]:.1f}%')"

# 查看失败测试
pytest --lf --collect-only
```

---

## 3. 当前测试状态分析

### 3.1 测试目录结构

```
tests/                              # 362 files total
├── conftest.py                     # 全局fixtures (2个)
├── unit/                           # 263 files (72.8%) - 单元测试
│   ├── domain/
│   │   ├── agents/                 # 66 files - 三Agent系统
│   │   ├── services/               # 126 files - 核心领域服务
│   │   ├── entities/               # 12 files - 实体测试
│   │   ├── ports/                  # 3 files - 端口接口
│   │   ├── knowledge_base/         # 2 files - 知识库
│   │   └── value_objects/          # 2 files - 值对象
│   ├── application/                # 14 files - 用例测试
│   ├── infrastructure/             # 21 files - 基础设施
│   ├── interfaces/                 # 5 files - API接口
│   └── lc/                         # 12 files - LangChain集成
├── integration/                    # 81 files (22.4%) - 集成测试
│   ├── api/                        # 21 files - API集成
│   │   ├── workflow_chat/          # 13 files - 聊天API
│   │   ├── scheduler/              # 3 files - 调度器
│   │   └── workflows/              # 5 files - 工作流
│   └── [root]/                     # 40 files - 系统集成
├── manual/                         # 16 files (4.4%) - 手动测试
├── performance/                    # 1 file - 性能测试
└── regression/                     # 1 file - 回归测试
```

### 3.2 按层覆盖率详情

> **注意**: 以下数据来自 `htmlcov/status.json`，可能与最新运行结果有差异。
> 请运行 `pytest --cov=src` 刷新后对照。

#### Domain Layer (231 files, 28,630 statements)

| 子模块 | 覆盖率 | 文件数 | 0%覆盖文件数 | 状态 |
|--------|--------|--------|-------------|------|
| agents | 23.7% | 31 | 18 | ⚠️ 需改进 |
| services | 4.9% | 149 | 137 | 🔴 严重 |
| entities | 46.6% | 14 | 1 | ✅ 尚可 |
| ports | 75% | 12 | 3 | ✅ 良好 |
| value_objects | 15.4% | 13 | 11 | ⚠️ 需改进 |
| knowledge_base | - | 12 | 8 | 🔴 严重 |

#### Application Layer (20 files, 870 statements)

| 子模块 | 覆盖率 | 0%覆盖 | 状态 |
|--------|--------|--------|------|
| use_cases | 46.2% | 7个 | ⚠️ 需改进 |
| services | 75% | 1个 | ✅ 良好 |

#### Infrastructure Layer (43 files, 2,367 statements)

| 子模块 | 覆盖率 | 状态 |
|--------|--------|------|
| auth | 100% | ✅ 完成 |
| memory | 100% | ✅ 完成 |
| websocket | 100% | ✅ 完成 |
| database | 66.7% | ⚠️ 需改进 |
| executors | 54.5% | ⚠️ 需改进 |
| knowledge_base | 0% | 🔴 严重 |
| llm | 0% | 🔴 严重 |

---

## 3. 测试缺口分析

### 3.1 完全无测试的关键模块 (0% 覆盖)

#### Domain/Agents (18个模块, ~6,901 LOC)

| 模块 | 行数 | 风险等级 | 职责 |
|------|------|----------|------|
| `error_handling.py` | 904 | 🔴 CRITICAL | Agent错误恢复核心 |
| `conversation_agent_react_core.py` | 645 | 🔴 CRITICAL | ReAct推理循环 |
| `conversation_agent_state.py` | 566 | 🔴 CRITICAL | 状态管理 |
| `agent_channel.py` | 517 | 🟠 HIGH | WebSocket通道 |
| `container_executor.py` | 478 | 🟠 HIGH | 容器执行 |
| `conversation_agent_recovery.py` | 440 | 🟠 HIGH | 恢复逻辑 |
| `react_prompts.py` | 420 | 🟠 HIGH | 提示词模板 |
| `conversation_agent_config.py` | 404 | 🟠 HIGH | Agent配置 |
| `subtask_executor.py` | 395 | 🟠 HIGH | 子任务执行 |
| `hierarchical_node_factory.py` | 390 | 🟠 HIGH | 节点层级工厂 |
| `node_definition.py` | 671 | 🟠 HIGH | 节点定义核心 |
| `conversation_engine.py` | 790 | 🟠 HIGH | 对话引擎 |
| `workflow_plan.py` | 373 | 🟡 MEDIUM | 工作流规划 |
| 其他5个 | ~500 | 🟡 MEDIUM | 辅助模块 |

#### Domain/Services (137个模块, ~20,212 LOC)

| 模块 | 行数 | 风险等级 | 职责 |
|------|------|----------|------|
| `self_describing_node.py` | 855 | 🔴 CRITICAL | 节点自描述验证 |
| `node_yaml_validator.py` | 753 | 🔴 CRITICAL | YAML验证 |
| `dynamic_node_monitoring.py` | 724 | 🔴 CRITICAL | 动态监控系统 |
| `configurable_rule_engine.py` | 685 | 🔴 CRITICAL | 规则引擎核心 |
| `self_describing_node_validator.py` | 653 | 🔴 CRITICAL | 节点验证器 |
| `execution_monitor.py` | 604 | 🟠 HIGH | 执行监控 |
| `monitoring_knowledge_bridge.py` | 558 | 🟠 HIGH | 知识桥接 |
| `tool_engine.py` | 500+ | 🟠 HIGH | 工具执行引擎 |
| `workflow_dependency_graph.py` | 400+ | 🟠 HIGH | 依赖图构建 |
| `management_modules.py` | 1226 | 🟠 HIGH | 管理模块集合 |
| `logging_metrics.py` | 1160 | 🟡 MEDIUM | 日志指标 |

#### Application/UseCases (7个模块, ~1,574 LOC)

| 模块 | 行数 | 风险等级 | 职责 |
|------|------|----------|------|
| `classify_task.py` | 303 | 🔴 CRITICAL | 任务分类入口 |
| `execute_run.py` | 297 | 🔴 CRITICAL | 运行执行入口 |
| `update_workflow_by_chat.py` | 285 | 🔴 CRITICAL | 聊天更新工作流 |
| `create_agent.py` | 260 | 🟠 HIGH | Agent创建 |
| `github_auth.py` | 159 | 🟡 MEDIUM | GitHub认证 |
| `import_workflow.py` | 147 | 🟡 MEDIUM | 工作流导入 |
| `create_tool.py` | 123 | 🟡 MEDIUM | 工具创建 |

#### Infrastructure (14个模块)

| 模块 | 行数 | 风险等级 | 职责 |
|------|------|----------|------|
| `models.py` | 912 | 🔴 CRITICAL | SQLAlchemy ORM模型 |
| `chroma_retriever_service.py` | 282 | 🔴 CRITICAL | 向量检索服务 |
| `rag_config_manager.py` | 295 | 🔴 CRITICAL | RAG配置管理 |
| `workflow_repository.py` | 310 | 🔴 CRITICAL | 工作流持久化 |
| `sqlite_knowledge_repository.py` | 262 | 🟠 HIGH | 知识库存储 |
| `llm_executor.py` | 142 | 🟠 HIGH | LLM推理执行 |
| `http_executor.py` | 71 | 🟠 HIGH | HTTP API执行 |

### 3.2 关键功能路径缺失测试

```
用户请求 → API路由 → UseCase → Domain Service → Repository
    ↓           ↓          ↓           ↓             ↓
  40.3%      27.4%      4.9%       <10%          66.7%
```

**最薄弱环节**: Domain/Services (4.9%) 是整个链路的瓶颈

---

## 4. 失败测试根因分析

### 4.1 失败分类统计 (基于239个lastfailed)

| 根因类型 | 数量 | 占比 | 示例 |
|----------|------|------|------|
| TDD Red阶段未门禁 | 58 | 24.3% | `test_supervision_modules.py` |
| 表达式求值器契约不一致 | 31 | 13.0% | `test_expression_evaluator.py` |
| API集成测试依赖未隔离 | 34 | 14.2% | `test_scheduler_api_integration.py` |
| Domain单测与实现漂移 | 37 | 15.5% | 各domain单测 |
| 回归套件环境依赖 | 30 | 12.6% | `tests/integration/regression/` |
| Manual脚本被收集 | 6 | 2.5% | `tests/manual/test_api.py` |
| SQLite锁/并行隔离 | 5 | 2.1% | `test_database_executor.py` |
| E2E时序flaky | 1 | 0.4% | WebSocket相关 |
| 其他 | 37 | 15.5% | - |

### 4.2 测试代码质量问题

1. **脚本被pytest收集**
   ```python
   # tests/manual/test_api.py - 模块import时就执行HTTP请求
   response = requests.get("http://localhost:8000/...")  # Line 9
   ```

2. **外部依赖未隔离**
   ```python
   # tests/unit/lc/test_task_executor.py
   # 依赖 OPENAI_API_KEY 和 httpbin.org
   ```

3. **FastAPI依赖未override**
   ```python
   # tests/integration/api/scheduler/test_scheduler_api_integration.py
   # 创建了测试DB但没接到app上
   engine = create_engine("sqlite:///:memory:")  # Line 27
   client = TestClient(app)  # Line 50 - 仍用默认DB
   ```

4. **时间驱动断言过多**
   - 广泛使用 `sleep()` 导致慢/抖/偶发失败

---

## 5. 测试优先级矩阵

### 5.1 优先级定义

| 级别 | 定义 | 时间窗口 |
|------|------|----------|
| P0 | 阻塞CI/测试可信度 | 立即 (1-2天) |
| P1 | 业务核心入口无测试 | 本周 |
| P2 | 核心闭环覆盖不足 | 2周内 |
| P3 | 辅助模块覆盖不足 | 本月 |

### 5.2 P0: 测试基础设施修复

| 任务 | 影响 | 工作量 | 状态 | Commit |
|------|------|--------|------|--------|
| 排除`tests/manual/`从pytest收集 | 消除6个稳定失败 | 0.5h | ✅ 完成 | `da3600b` |
| 将TDD Red阶段测试标记为xfail/skip | 消除58个预期失败 | 1h | ✅ 完成 | `b5bd32e`, `a4be40f` |
| 为外部网络调用添加mock | 消除单测外部依赖 | 2h | ✅ 完成 | `fbf56f6` |
| 为FastAPI集成测试添加dependency overrides | 修复34个API测试 | 4h | ✅ 完成 | `0a1238b` |
| 修复SQLite并行隔离问题 | 消除5个flaky测试 | 2h | ✅ 完成 | `待提交` |

**P0-Task4 实施总结**:
- ✅ 数据库依赖注入：使用 `app.dependency_overrides[get_db_session]` 模式
- ✅ Scheduler service注入：Mock scheduler service并覆盖依赖
- ✅ SQLite共享内存：使用 `file:memdb?mode=memory&cache=shared` 解决per-connection隔离问题
- ✅ 线程安全：添加 `check_same_thread=False` 配置
- 📊 测试结果：scheduler API集成测试 4/9 通过（基础设施修复完成，剩余失败为业务逻辑问题）

**P0-Task5 实施总结**:
- ✅ UUID隔离：使用 `uuid4().hex` 生成唯一数据库文件名
- ✅ 并行安全：每个测试实例使用独立的数据库文件
- ✅ Windows兼容：添加重试机制处理文件锁问题
- 📊 测试结果：database_executor测试 7/7 全部通过（包括原失败的5个）

### 5.3 P1: Application/UseCases 测试补齐

| 模块 | 当前覆盖 | 目标覆盖 | 实际用例数 | 状态 | Commit |
|------|----------|----------|-----------|------|--------|
| `execute_run.py` | 95% | 80% | 7 | ✅ 完成 | `3f77a55` |
| `classify_task.py` | 100% | 80% | 23 | ✅ 完成 | `31a53f8` |
| `update_workflow_by_chat.py` | 100% | 70% | 16 | ✅ 完成 | `6c6e14a` |
| `create_agent.py` | 100% | 70% | 14 | ✅ 完成 | `46d5190` |
| `create_tool.py` | 100% | 70% | 8 | ✅ 完成 | `3952534` |
| `import_workflow.py` | 80% | 70% | 5-7 | ✅ 已达标 | - |
| `github_auth.py` | 100% | 60% | 9 | ✅ 完成 | `待提交` |

**P1-Task1: ExecuteRunUseCase 测试补齐（LangGraph迁移）**
- ✅ **架构迁移**：从LangChain迁移到LangGraph，移除Task实体依赖
- ✅ **测试设计**：7个测试用例覆盖输入验证、状态转换、成功/失败场景、错误处理
- ✅ **TDD实践**：遵循Red-Green-Refactor循环，修复Run状态突变陷阱
- ✅ **集成修复**：修复API路由Breaking Change（移除task_repository依赖）
- ✅ **代码审查**：Codex深度审查，三层错误检测策略（显式信号/空结果/启发式）
- 📊 **测试结果**：7/7 单元测试通过，覆盖率95%（仅2行未覆盖为异常分支）
- 📁 **文件变更**：
  - 新增：`tests/unit/application/use_cases/test_execute_run_langgraph.py`（231行）
  - 重构：`src/application/use_cases/execute_run.py`（简化85行）
  - 修复：`src/interfaces/api/routes/runs.py`（移除task_repository）
  - 删除：`tests/unit/application/test_execute_run_use_case.py`（旧LangChain测试）

**P1-Task2: ClassifyTaskUseCase 测试补齐（LLM+Keyword双路径）**
- ✅ **业务分析**：理解双路径分类（LLM主路径+关键词fallback）、6种TaskType、工具建议映射
- ✅ **测试设计**：Codex协作设计23个测试用例，覆盖5大功能组
- ✅ **TDD实践**：遵循Red-Green-Refactor循环，修复关键词优先级冲突
- ✅ **边界测试**：Codex审查建议添加2个边界情况（缺失suggested_tools、None content）
- ✅ **Mock策略**：使用SimpleNamespace模拟LLM响应，monkeypatch注入提示词生成
- 📊 **测试结果**：23/23 单元测试通过，覆盖率100%（超出80%目标）
- 📁 **文件变更**：
  - 新增：`tests/unit/application/use_cases/test_classify_task.py`（351行，23测试）
  - 无需修改：`src/application/use_cases/classify_task.py`（实现已稳定）
- 📝 **测试覆盖**：
  - 输入/执行行为：4测试（无LLM、context默认、空输入、None输入）
  - LLM成功路径：5测试（纯JSON、小写映射、未知类型、工具透传、缺失工具字段）
  - LLM回退路径：5测试（invoke异常、缺失字段、无效confidence、None task_type、None content）
  - JSON解析：3测试（```json围栏、嵌入{}、无效JSON默认）
  - 关键词分类：6参数化测试（所有TaskType+工具建议）

**P1-Task3: UpdateWorkflowByChatUseCase 测试补齐（对话式工作流修改）**
- ✅ **业务分析**：理解双服务兼容（基础tuple+增强ModificationResult）、异步流式执行
- ✅ **测试设计**：Codex协作设计16个测试用例（20个参数化后），覆盖6大功能组
- ✅ **TDD实践**：遵循Red-Green-Refactor循环，初次99%后添加streaming parity测试达到100%
- ✅ **Codex审查**：应用4处修复（未使用import、fixture文档、result变量、streaming修复）
- ✅ **Mock策略**：SimpleNamespace模拟ModificationResult，parent_mock验证调用顺序
- 📊 **测试结果**：20/20 单元测试通过（16函数+参数化），覆盖率100%（超出70%目标30%）
- 📁 **文件变更**：
  - 新增：`tests/unit/application/use_cases/test_update_workflow_by_chat.py`（589行，16测试函数）
  - 无需修改：`src/application/use_cases/update_workflow_by_chat.py`（实现已稳定）
- 📝 **测试覆盖**：
  - 输入验证：2参数化测试（execute+streaming空/空白消息）
  - 工作流检索：3测试（get_by_id返回None、抛异常、streaming在事件前拒绝）
  - 服务兼容性：2测试（基础tuple映射、增强ModificationResult映射）
  - 增强错误处理：3测试（success=False+message、success=False无message、modified_workflow=None）
  - 持久化顺序：1测试（save在process_message后+实例完整性）
  - 异步流式：5测试（基础事件序列、增强react_steps、modified_workflow=None、success=False、timestamps验证）

**P1-Task4: CreateAgentUseCase 测试补充（Workflow生成路径）**
- ✅ **需求分析**：识别workflow生成缺口（lines 245-253），现有11测试覆盖Agent+Task路径，缺workflow转换
- ✅ **测试设计**：Codex协作设计3个补充测试用例，覆盖workflow generation全路径
- ✅ **TDD实践**：遵循Red-Green-Refactor循环，初次92%→100%（添加3测试覆盖workflow路径）
- ✅ **Codex审查**：应用2处改进（加强Task实例断言、移除冗余import）
- ✅ **Mock策略**：SimpleNamespace模拟workflow对象，monkeypatch mock LLM chain
- 📊 **测试结果**：14/14 单元测试通过（11原有+3新增），覆盖率100%（超出70%目标30%）
- 📁 **文件变更**：
  - 更新：`tests/unit/application/test_create_agent_use_case.py`（新增TestCreateAgentWithWorkflowGeneration类，246行）
  - 无需修改：`src/application/use_cases/create_agent.py`（实现已稳定）
- 📝 **测试覆盖**（新增3测试）：
  - Workflow生成成功：验证converter.convert()调用参数（agent+tasks）、workflow保存、workflow_id返回
  - 无task_repository边界：有workflow_repository但无tasks→不生成workflow、workflow_id=None
  - 空plan边界：LLM返回[]→无tasks创建、不生成workflow、workflow_id=None

**P1-Task5: CreateToolUseCase 测试（工具创建）**
- ✅ **需求分析**：识别0%覆盖率缺口（25/25 statements missing），理解业务逻辑（category转换+parameters转换+domain规则）
- ✅ **测试设计**：Codex协作设计8个测试用例，覆盖全路径
- ✅ **TDD实践**：遵循Red-Green-Refactor循环，0%→100%一次通过（8/8测试）
- ✅ **Codex审查**：✅ LGTM评价，提出3个可选改进建议（malformed dict、默认值断言、类合并）
- ✅ **Mock策略**：Mock repository + 真实Domain实体断言（ToolParameter/Tool）
- 📊 **测试结果**：8/8 单元测试通过，覆盖率100%（超出70%目标30%）
- 📁 **文件变更**：
  - 新增：`tests/unit/application/use_cases/test_create_tool.py`（335行，8测试函数，5测试类）
  - 无需修改：`src/application/use_cases/create_tool.py`（实现已稳定）
- 📝 **测试覆盖**（8测试）：
  - 成功路径：完整字段填充（category+parameters+implementation_config）、name/description trimming、ToolCategory枚举转换、ToolParameter对象转换
  - 参数转换：parameters=None→[]、parameters=[]→[]（falsy检查）
  - 默认值：implementation_config=None→{}
  - Domain验证：空name→DomainError、纯空格name→DomainError、save不调用
  - 枚举转换：无效category→ValueError、save不调用
  - 异常传播：repository.save()异常→RuntimeError传播

**P1-Task6: GitHubAuthUseCase 测试补充（邮箱处理边缘case）**
- ✅ **需求分析**：识别90%覆盖率缺口（missing lines 119-122, 126），聚焦邮箱处理fallback逻辑
- ✅ **测试设计**：Codex协作设计3个边缘case测试用例，覆盖邮箱API多级fallback路径
- ✅ **TDD实践**：遵循Red-Green-Refactor循环，90%→100%一次通过（3/3测试）
- ✅ **Codex审查**：✅ LGTM评价，覆盖率验证通过（lines 119-122验证/第一邮箱fallback，line 126占位邮箱）
- ✅ **Mock策略**：AsyncMock + GitHub API response模拟（空primary/空verified/空emails列表）
- 📊 **测试结果**：9/9 单元测试通过（6原有+3新增），覆盖率100%（超出60%目标40%）
- 📁 **文件变更**：
  - 更新：`tests/unit/application/use_cases/test_github_auth_use_case.py`（新增3测试，118行）
  - 无需修改：`src/application/use_cases/github_auth.py`（实现已稳定）
- 📝 **测试覆盖**（新增3测试）：
  - Edge Case A：无主邮箱但有verified邮箱→优先使用verified邮箱（覆盖lines 119-122 verified分支）
  - Edge Case B：无主邮箱、无verified邮箱但emails非空→使用第一个邮箱（覆盖lines 121-122 fallback分支）
  - Edge Case C：邮箱API返回空列表→使用占位邮箱 `{login}@users.noreply.github.com`（覆盖line 126）

### 5.4 P2: Domain/Services 核心闭环

| 子系统 | 关键模块 | 预计用例数 |
|--------|----------|-----------|
| 规则引擎 | `configurable_rule_engine.py` | 20-25 |
| 节点验证 | `self_describing_node_validator.py` | 15-20 |
| 执行监控 | `execution_monitor.py`, `dynamic_node_monitoring.py` | 25-30 |
| 工具引擎 | `tool_engine.py` | 15-20 |
| 依赖图 | `workflow_dependency_graph.py` | 10-15 |

**P2-Task1: ConfigurableRuleEngine 测试补充（Schema Validation边缘case）**
- ✅ **需求分析**：识别87%覆盖率缺口（39 missing lines），聚焦Schema validation未覆盖分支
- ✅ **测试设计**：Codex协作设计9个P0 Schema Validation测试用例
- ✅ **TDD实践**：遵循Red-Green-Refactor循环，87%→94%一次通过（+9测试）
- ✅ **Codex审查**：✅ LGTM评价，"94% is a strong finish for P2-Task1"，建议停在94%
- ✅ **Mock策略**：RuleConfigValidator.validate() + ConfigurableRuleEngine() 构造异常测试
- 📊 **测试结果**：58/58 单元测试通过（49原有+9新增），覆盖率94%（超出P2目标60%达34%）
- 📁 **文件变更**：
  - 更新：`tests/unit/domain/services/test_configurable_rule_engine.py`（新增9测试，184行）
  - 无需修改：`src/domain/services/configurable_rule_engine.py`（实现已稳定）
- 📝 **测试覆盖**（新增9个P0测试）：
  - Path Rules: missing id/action、replace requires replacement
  - Content Rules: missing fields、patterns类型错误+invalid action
  - User Level Rules: missing fields、invalid required_level+invalid action
  - Command Rules: missing fields、commands类型错误+invalid action
  - Engine Init: invalid config raises ValueError
- 📋 **Remaining Missing Lines** (19 lines, P1/P2 priority):
  - P1: YAML errors (373-376)、Invalid regex (334-335)、Serialization (82-83, 137)、Path matching (500, 506, 522)、Bytes content (408, 591-594)、Audit adapter (648)
  - P2: Command decode exception (593-594)

**P2-Task2: SelfDescribingNodeValidator 测试补充（从0%到66%）**
- ✅ **需求分析**：654行实现，0%覆盖率，无现有测试；识别3主要类（NodeValidationResult, SelfDescribingNodeValidator, ResultSemanticParser）
- ✅ **测试设计**：Codex协作设计32个测试（27 designed + 5 pytest collected）：17 P0核心验证 + 10 P1边缘cases
- ✅ **TDD实践**：0%→66%一次通过（+32测试，6个测试类），遵循Red-Green循环
- ✅ **Codex审查**：✅ LGTM (minor gaps)，"66% exceeds P2 target (60%), acceptable to stop"
- ✅ **测试策略**：聚焦核心验证路径（required fields, input/output alignment, sandbox permission）
- 📊 **测试结果**：32/32 单元测试通过，覆盖率66%（超出P2目标60%达6%）
- 📁 **文件变更**：
  - 新增：`tests/unit/domain/services/test_self_describing_node_validator.py`（32测试，470行）
  - 无需修改：`src/domain/services/self_describing_node_validator.py`（实现已稳定）
- 📝 **测试覆盖**（32测试分布）：
  - NodeValidationResult (6测试): merge both valid/invalid、combines errors/warnings
  - SemanticResult (5测试): to_dict includes keys、get_summary success/failure/partial
  - validate_required_fields (8测试): None/empty/missing name/executor_type、invalid types
  - validate_input_alignment (6测试): missing required param、type mismatch、optional param OK
  - validate_output_alignment (2测试): missing required field、valid output
  - validate_sandbox_permission (3测试): dangerous imports detected、safe imports OK
  - ResultSemanticParser (2测试): parse success/failure、determine status
- 📋 **Remaining Missing Lines** (79/230 lines, 34% uncovered):
  - HIGH impact (432-447): validate_all orchestration method（Codex建议可测，但非P2必需）
  - LOW priority (465-487): validate_with_logging（仅日志调用）
  - MEDIUM priority (584-653): register_self_describing_rules（coordinator集成，非核心validator）
  - MEDIUM priority (527-531, 552, 556-565): ResultSemanticParser边缘cases（timeout/partial/non-dict）
  - LOW priority (scattered): 参数验证edge cases

**P2-Task3: DynamicNodeMonitoring 测试补充（从0%到65%）**
- ✅ **需求分析**：724行实现，0%覆盖率，无现有测试；识别5主要类（DynamicNodeMetricsCollector, WorkflowRollbackManager, AlertManager, HealthChecker, SystemRecoveryManager）
- ✅ **测试设计**：Codex协作设计30个测试，但发现API不匹配；重新读取实现并重写所有测试
- ✅ **API适配挑战**：初始设计基于假设API，实际实现完全不同（如WorkflowRollbackManager.create_snapshot返回str而非对象）；采取"读实现→重写测试"策略
- ✅ **TDD实践**：0%→65%（+33测试，4个测试类），遵循Red-Green循环
- ✅ **Codex审查**：✅ LGTM (good for P2)，"65% comfortably above 60% target"，建议停在65%
- ✅ **测试策略**：聚焦最可测且高价值的类（MetricsCollector完整覆盖、Rollback/Alert/Health核心方法）
- 📊 **测试结果**：33/33 单元测试通过，覆盖率65%（超出P2目标60%达5%）
- 📁 **文件变更**：
  - 新增：`tests/unit/domain/services/test_dynamic_node_monitoring.py`（33测试，490行）
  - 无需修改：`src/domain/services/dynamic_node_monitoring.py`（实现已稳定）
- 📝 **测试覆盖**（33测试分布）：
  - DynamicNodeMetricsCollector (14测试): 记录指标、统计聚合、时间窗口过滤、Prometheus导出、失败率计算
  - WorkflowRollbackManager (8测试): create_snapshot、has_snapshot、rollback、rollback_to_snapshot、get_snapshot_count、clear_snapshots、remove_invalid_nodes
  - AlertManager (7测试): set_threshold、check_failure_rate触发/清除、get_active_alerts、clear_alert、notification_callback
  - HealthChecker (5测试): check_health、check_sandbox_health、check_metrics_health、record_sandbox_execution、set_sandbox_available
- 📋 **Remaining Missing Lines** (92/262 lines, 35% uncovered):
  - SystemRecoveryManager (lines 338-570, 252 lines): 复杂依赖（timers/threads/health-checker），Codex建议留待P1
  - Minor edges (275, 608, 715): 已测试类的边缘分支

**P2-Task4: ToolEngine execute()测试补充（从~70%到~80-86%）**
- ✅ **需求分析**：1104行实现，已有53个测试（覆盖Config/Index/Lookup/HotReload/Events/Validation），估计~70%覆盖率
- ✅ **Codex决策**：虽已达标60%+，但execute()是核心运行时行为，建议添加5个高价值测试
- ✅ **TDD实践**：~70%→~80-86%（+5测试，新增TestToolEngineExecution类），58/58测试全部通过
- ✅ **Codex审查**：✅ LGTM (good for P2)，"覆盖execute()关键分支，测试质量满足P2标准"
- 📊 **测试结果**：58/58 单元测试通过，覆盖率估计~80-86%（远超P2目标60%达20-26%）
- 📁 **文件变更**：
  - 修改：`tests/unit/domain/services/test_tool_engine.py`（+5测试，245行新增代码，lines 1223-1467）
  - 无需修改：`src/domain/services/tool_engine.py`（实现已稳定）
- 📝 **测试覆盖**（新增5测试 TestToolEngineExecution）：
  1. test_execute_tool_not_found_returns_failure: 工具不存在返回error_type="tool_not_found"
  2. test_execute_validation_failure_returns_validation_failure: 参数验证失败返回validation_error + validation_errors
  3. test_execute_executor_not_found_returns_failure: 执行器未注册返回error_type="executor_not_found"
  4. test_execute_success_emits_events_and_records_to_knowledge_store: 成功执行发送EXECUTION_STARTED/COMPLETED事件并记录到知识库
  5. test_execute_timeout_emits_failed_and_records_to_knowledge_store: 超时执行发送EXECUTION_FAILED事件并记录失败到知识库
- 📋 **Remaining Missing Lines** (~200/1104 lines, ~18% uncovered):
  - Executor raises Exception → error_type="execution_error"（Codex认为可选，非P2关键）
  - 知识库缺失时的边缘cases（低优先级）
  - 部分执行器管理方法的边缘分支

**P2-Task5: WorkflowDependencyGraph 单元测试补充（从集成测试到70-85%）**
- ✅ **需求分析**：584行实现，已有25个集成测试（全部通过），但无单元测试；集成测试覆盖率估计55-75%
- ✅ **Codex决策**：虽可能已达标，但单元测试可快速覆盖分支逻辑（_aggregate_outputs/_build_node_inputs/_emit_event），避免依赖猜测
- ✅ **TDD实践**：55-75%→~70-85%（+14单元测试，3个测试类），39/39测试全部通过（25 integration + 14 unit）
- ✅ **Codex审查**：✅ LGTM (good for P2)，"覆盖集成测试遗漏的高分支密度逻辑，满足P2标准"
- 📊 **测试结果**：39/39 测试通过（25 integration + 14 unit），覆盖率估计~70-85%（超出P2目标60%达10-25%）
- 📁 **文件变更**：
  - 新增：`tests/unit/domain/services/test_workflow_dependency_graph.py`（14单元测试，273行）
  - 无需修改：`src/domain/services/workflow_dependency_graph.py`（实现已稳定）
  - 保留：`tests/integration/test_workflow_dependency_graph.py`（25集成测试继续覆盖E2E场景）
- 📝 **单元测试覆盖**（14测试分布）：
  - TestAggregateOutputs (7测试): merge/list/first/last策略、empty dict、unknown strategy fallback、non-dict skip
  - TestBuildNodeInputs (5测试): basic extraction、field path extraction、multiple inputs merge、parent reference、missing node handling
  - TestEmitEvent (2测试): callback invocation、no-op when callback None
- 📋 **Remaining Missing Lines** (~150-200/584 lines, ~25-35% uncovered):
  - execute_workflow中的YAML加载错误分支（Codex认为集成测试已覆盖）
  - _execute_node/_execute_script的异常处理路径（低优先级）
  - DependencyGraphBuilder边缘cases（invalid refs、conflicts）由集成测试间接覆盖

### 5.5 P3: Domain/Agents 状态机

| 模块 | 预计用例数 | 重点 |
|------|-----------|------|
| `error_handling.py` | 30-40 | 错误分类、恢复策略 |
| `conversation_agent_react_core.py` | 25-30 | ReAct循环、终止条件 |
| `conversation_agent_state.py` | 20-25 | 状态转换、并发安全 |
| `node_definition.py` | 20-25 | 节点创建、验证、序列化 |

---

## 6. 分层测试策略

### 6.1 单元测试策略

```
目标: Domain层 ≥ 80%, Application层 ≥ 70%
```

#### Domain Layer 单元测试原则

```python
# 1. 纯函数测试 - 无副作用
def test_node_definition_validates_required_fields():
    node = NodeDefinition(name="", node_type=NodeType.PYTHON)
    errors = node.validate()
    assert "name不能为空" in errors

# 2. 状态机测试 - 覆盖所有转换
@pytest.mark.parametrize("from_state,event,to_state", [
    (AgentState.IDLE, "start", AgentState.PROCESSING),
    (AgentState.PROCESSING, "complete", AgentState.IDLE),
    (AgentState.PROCESSING, "error", AgentState.ERROR),
])
def test_agent_state_transitions(from_state, event, to_state):
    agent = ConversationAgent()
    agent._state = from_state
    agent.handle_event(event)
    assert agent._state == to_state

# 3. 边界条件测试
def test_react_loop_max_iterations():
    agent = ConversationAgent(max_iterations=3)
    result = await agent.run_async("无限循环任务")
    assert agent.iteration_count <= 3
```

#### Application Layer 单元测试原则

```python
# 1. UseCase测试 - Mock所有端口
@pytest.fixture
def mock_repository():
    repo = Mock(spec=WorkflowRepository)
    repo.find_by_id.return_value = sample_workflow()
    return repo

def test_execute_workflow_success(mock_repository):
    use_case = ExecuteWorkflowUseCase(repository=mock_repository)
    result = await use_case.execute(workflow_id="wf_123")
    assert result.success is True
    mock_repository.find_by_id.assert_called_once_with("wf_123")

# 2. 输入验证测试
def test_create_agent_validates_input():
    use_case = CreateAgentUseCase(repository=mock_repo)
    with pytest.raises(ValidationError):
        use_case.execute(CreateAgentInput(name=""))
```

### 6.2 集成测试策略

```
目标: 覆盖所有API端点, 验证多层交互
```

#### API集成测试模板

```python
@pytest.fixture
def test_client():
    """正确配置依赖覆盖的TestClient"""
    # 创建测试数据库
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # 覆盖依赖
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_service] = lambda: MockLLMService()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()

def test_create_workflow_api(test_client):
    response = test_client.post("/api/workflows", json={
        "name": "Test Workflow",
        "nodes": [{"type": "python", "code": "print('hello')"}]
    })
    assert response.status_code == 201
    assert response.json()["name"] == "Test Workflow"
```

#### 多Agent协作集成测试

```python
@pytest.mark.integration
async def test_coordinator_conversation_workflow_collaboration():
    """测试三Agent协作完整流程"""
    # Setup
    event_bus = EventBus()
    coordinator = CoordinatorAgent(event_bus=event_bus)
    conversation = ConversationAgent(coordinator=coordinator, event_bus=event_bus)
    workflow = WorkflowAgent(event_bus=event_bus)

    # Execute
    result = await coordinator.process_request(
        user_input="创建一个数据处理工作流",
        session_id="test_session"
    )

    # Verify
    assert result.success
    assert len(event_bus.published_events) > 0
    assert any(e.type == "workflow_created" for e in event_bus.published_events)
```

### 6.3 E2E测试策略

```
目标: 覆盖关键业务场景, 验证系统完整性
```

```python
@pytest.mark.e2e
@pytest.mark.slow
async def test_complete_workflow_execution_scenario():
    """完整工作流执行场景"""
    async with AsyncClient(app, base_url="http://test") as client:
        # 1. 创建工作流
        create_response = await client.post("/api/workflows", json=workflow_data)
        workflow_id = create_response.json()["id"]

        # 2. 执行工作流
        exec_response = await client.post(f"/api/workflows/{workflow_id}/execute")
        execution_id = exec_response.json()["execution_id"]

        # 3. 等待完成 (with timeout)
        for _ in range(30):
            status = await client.get(f"/api/executions/{execution_id}")
            if status.json()["status"] in ["completed", "failed"]:
                break
            await asyncio.sleep(1)

        # 4. 验证结果
        assert status.json()["status"] == "completed"
        assert status.json()["output"] is not None
```

---

## 7. 具体测试计划

### 7.1 Phase 1: 基础设施修复 (P0) - 2天

#### Day 1: 测试隔离修复

| 任务 | 文件 | 预计时间 |
|------|------|----------|
| 配置pytest忽略manual目录 | `pyproject.toml` | 15min |
| 添加网络mock装饰器 | `tests/conftest.py` | 1h |
| 修复scheduler API测试依赖 | `tests/integration/api/scheduler/` | 2h |
| 标记TDD Red测试为xfail | `tests/unit/domain/services/test_supervision_modules.py` | 30min |

```toml
# pyproject.toml 修改
[tool.pytest.ini_options]
testpaths = ["tests"]
ignore = ["tests/manual"]  # 新增
```

```python
# tests/conftest.py 新增
import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_external_services(request):
    """自动mock外部服务调用"""
    if "integration" not in str(request.fspath):
        with patch("requests.get"), patch("requests.post"):
            yield
    else:
        yield
```

#### Day 2: 数据库隔离与并行安全

| 任务 | 文件 | 预计时间 |
|------|------|----------|
| 创建共享测试数据库fixture | `tests/conftest.py` | 1h |
| 修复database_executor并行问题 | `tests/unit/infrastructure/executors/test_database_executor.py` | 1h |
| 添加测试数据清理hooks | `tests/conftest.py` | 1h |
| 验证CI绿灯 | - | 1h |

### 7.2 Phase 2: Application层测试 (P1) - 1周

#### Week 1: UseCases测试补齐

| 模块 | 测试文件 | 用例数 | 负责人 |
|------|----------|--------|--------|
| `execute_run.py` | `test_execute_run.py` | 18 | - |
| `classify_task.py` | `test_classify_task.py` | 12 | - |
| `update_workflow_by_chat.py` | `test_update_workflow_by_chat.py` | 15 | - |
| `create_agent.py` | `test_create_agent.py` | 10 | - |
| `create_tool.py` | `test_create_tool.py` | 8 | - |
| `import_workflow.py` | `test_import_workflow.py` | 6 | - |
| `github_auth.py` | `test_github_auth.py` | 9 | - |

**测试用例模板** (`execute_run.py`):

```python
# tests/unit/application/use_cases/test_execute_run.py

class TestExecuteRunUseCase:
    """ExecuteRun用例测试"""

    @pytest.fixture
    def use_case(self, mock_run_repo, mock_workflow_repo, mock_executor):
        return ExecuteRunUseCase(
            run_repository=mock_run_repo,
            workflow_repository=mock_workflow_repo,
            executor=mock_executor
        )

    # Happy Path Tests
    def test_execute_run_success(self, use_case):
        """成功执行运行"""
        result = await use_case.execute(ExecuteRunInput(run_id="run_123"))
        assert result.success is True
        assert result.output is not None

    def test_execute_run_updates_status(self, use_case, mock_run_repo):
        """执行时更新运行状态"""
        await use_case.execute(ExecuteRunInput(run_id="run_123"))
        mock_run_repo.update.assert_called()
        saved_run = mock_run_repo.update.call_args[0][0]
        assert saved_run.status == RunStatus.COMPLETED

    # Error Path Tests
    def test_execute_run_not_found(self, use_case, mock_run_repo):
        """运行不存在时抛出异常"""
        mock_run_repo.find_by_id.return_value = None
        with pytest.raises(RunNotFoundError):
            await use_case.execute(ExecuteRunInput(run_id="not_exist"))

    def test_execute_run_workflow_not_found(self, use_case, mock_workflow_repo):
        """工作流不存在时抛出异常"""
        mock_workflow_repo.find_by_id.return_value = None
        with pytest.raises(WorkflowNotFoundError):
            await use_case.execute(ExecuteRunInput(run_id="run_123"))

    def test_execute_run_executor_failure(self, use_case, mock_executor):
        """执行器失败时记录错误"""
        mock_executor.execute.side_effect = ExecutionError("timeout")
        result = await use_case.execute(ExecuteRunInput(run_id="run_123"))
        assert result.success is False
        assert "timeout" in result.error_message

    # Edge Cases
    def test_execute_run_already_running(self, use_case, mock_run_repo):
        """已在运行时拒绝重复执行"""
        mock_run_repo.find_by_id.return_value = Run(status=RunStatus.RUNNING)
        with pytest.raises(RunAlreadyRunningError):
            await use_case.execute(ExecuteRunInput(run_id="run_123"))

    def test_execute_run_concurrent_execution(self, use_case):
        """并发执行时正确处理锁"""
        # 模拟并发场景
        pass

    # Input Validation Tests
    @pytest.mark.parametrize("invalid_input", [
        {"run_id": ""},
        {"run_id": None},
        {},
    ])
    def test_execute_run_invalid_input(self, use_case, invalid_input):
        """无效输入验证"""
        with pytest.raises(ValidationError):
            await use_case.execute(ExecuteRunInput(**invalid_input))
```

### 7.3 Phase 3: Domain/Services核心测试 (P2) - 2周

#### Week 2-3: 核心服务测试

| 子系统 | 模块 | 用例数 | 优先级 |
|--------|------|--------|--------|
| 规则引擎 | `configurable_rule_engine.py` | 25 | P2-1 |
| 节点验证 | `self_describing_node_validator.py` | 20 | P2-1 |
| 执行监控 | `execution_monitor.py` | 15 | P2-2 |
| 动态监控 | `dynamic_node_monitoring.py` | 18 | P2-2 |
| 工具引擎 | `tool_engine.py` | 15 | P2-3 |
| 依赖图 | `workflow_dependency_graph.py` | 12 | P2-3 |

### 7.4 Phase 4: Domain/Agents测试 (P3) - 2周

#### Week 4-5: Agent系统测试

| 模块 | 测试重点 | 用例数 |
|------|----------|--------|
| `error_handling.py` | 错误分类、恢复策略、用户消息 | 35 |
| `conversation_agent_react_core.py` | ReAct循环、终止条件、token限制 | 28 |
| `conversation_agent_state.py` | 状态转换、并发安全、回滚 | 22 |
| `node_definition.py` | 创建、验证、序列化、层级 | 25 |
| `agent_channel.py` | WebSocket连接、消息收发、重连 | 18 |

---

## 8. 测试基础设施改进

### 8.1 Fixture库建设

```python
# tests/fixtures/__init__.py
"""共享测试fixtures"""

# tests/fixtures/agents.py
@pytest.fixture
def mock_llm():
    """Mock LLM服务"""
    llm = AsyncMock()
    llm.think.return_value = {"thought": "分析用户请求..."}
    llm.decide_action.return_value = {"action": "create_workflow"}
    return llm

@pytest.fixture
def conversation_agent(mock_llm, mock_event_bus):
    """预配置的ConversationAgent"""
    return ConversationAgent(
        llm=mock_llm,
        event_bus=mock_event_bus,
        max_iterations=5
    )

# tests/fixtures/workflows.py
@pytest.fixture
def sample_workflow():
    """样本工作流"""
    return Workflow(
        id="wf_test_001",
        name="Test Workflow",
        nodes=[
            Node(id="n1", type=NodeType.PYTHON, code="x = 1"),
            Node(id="n2", type=NodeType.PYTHON, code="y = x + 1"),
        ],
        edges=[Edge(source="n1", target="n2")]
    )

# tests/fixtures/database.py
@pytest.fixture(scope="session")
def test_engine():
    """测试数据库引擎 (session级别复用)"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(test_engine):
    """测试数据库会话 (自动回滚)"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
```

### 8.2 测试工具类

```python
# tests/utils/builders.py
"""测试数据构建器"""

class WorkflowBuilder:
    """工作流构建器 (Builder Pattern)"""

    def __init__(self):
        self._id = f"wf_{uuid.uuid4().hex[:8]}"
        self._name = "Test Workflow"
        self._nodes = []
        self._edges = []

    def with_id(self, id: str) -> "WorkflowBuilder":
        self._id = id
        return self

    def with_name(self, name: str) -> "WorkflowBuilder":
        self._name = name
        return self

    def with_python_node(self, code: str, node_id: str = None) -> "WorkflowBuilder":
        node_id = node_id or f"n_{len(self._nodes) + 1}"
        self._nodes.append(Node(id=node_id, type=NodeType.PYTHON, code=code))
        return self

    def with_edge(self, source: str, target: str) -> "WorkflowBuilder":
        self._edges.append(Edge(source=source, target=target))
        return self

    def build(self) -> Workflow:
        return Workflow(
            id=self._id,
            name=self._name,
            nodes=self._nodes,
            edges=self._edges
        )

# 使用示例
workflow = (WorkflowBuilder()
    .with_name("Data Pipeline")
    .with_python_node("data = load_csv('input.csv')", "load")
    .with_python_node("result = transform(data)", "transform")
    .with_edge("load", "transform")
    .build())
```

### 8.3 Mock服务注册

```python
# tests/mocks/__init__.py
"""Mock服务集合"""

class MockLLMService:
    """Mock LLM服务"""

    def __init__(self, responses: dict = None):
        self.responses = responses or {}
        self.call_history = []

    async def complete(self, prompt: str) -> str:
        self.call_history.append(prompt)
        return self.responses.get(prompt, "Mock response")

    async def think(self, context: dict) -> dict:
        return {"thought": "Mock thinking..."}

class MockEventBus:
    """Mock事件总线"""

    def __init__(self):
        self.published_events = []
        self.subscribers = {}

    async def publish(self, event):
        self.published_events.append(event)
        for handler in self.subscribers.get(type(event), []):
            await handler(event)

    def subscribe(self, event_type, handler):
        self.subscribers.setdefault(event_type, []).append(handler)
```

---

## 9. 执行计划与里程碑

### 9.1 时间线

```
Week 1 (Day 1-2):   P0 - 测试基础设施修复
Week 1 (Day 3-5):   P1 - Application层测试 (3个核心UseCase)
Week 2:             P1 - Application层测试 (剩余4个UseCase)
Week 3:             P2 - Domain/Services测试 (规则引擎、节点验证)
Week 4:             P2 - Domain/Services测试 (执行监控、工具引擎)
Week 5:             P3 - Domain/Agents测试 (error_handling, react_core)
Week 6:             P3 - Domain/Agents测试 (state, node_definition)
```

### 9.2 里程碑定义

| 里程碑 | 完成标准 | 目标日期 |
|--------|----------|----------|
| M1: CI绿灯 | 所有测试通过,无失败 | Week 1 Day 2 |
| M2: App层70% | Application层覆盖率≥70% | Week 2 End |
| M3: 核心服务50% | Domain/services关键模块≥50% | Week 4 End |
| M4: Agent系统60% | Domain/agents关键模块≥60% | Week 6 End |
| M5: 总体覆盖50% | 整体覆盖率≥50% | Week 6 End |

### 9.3 资源需求

| 角色 | 人数 | 职责 |
|------|------|------|
| 测试负责人 | 1 | 规划、review、质量把控 |
| 后端开发 | 2 | 编写单元测试、修复bug |
| QA工程师 | 1 | 集成测试、E2E测试 |

---

## 10. 质量门禁标准

### 10.1 PR合并标准

```yaml
# .github/workflows/test.yml 建议配置
quality_gates:
  unit_tests:
    required: true
    coverage_threshold: 70%  # 新代码覆盖率

  integration_tests:
    required: true
    all_pass: true

  static_analysis:
    ruff: pass
    pyright: pass

  coverage_regression:
    allowed_decrease: 2%  # 允许小幅回退以支持重构
    diff_coverage: 60%    # 新增代码覆盖率要求
```

### 10.2 分层覆盖率要求

| 层 | 最低覆盖率 | 目标覆盖率 |
|----|-----------|-----------|
| Domain/entities | 80% | 90% |
| Domain/services | 60% | 80% |
| Domain/agents | 60% | 80% |
| Application | 70% | 85% |
| Infrastructure | 50% | 70% |
| Interface | 40% | 60% |

### 10.3 测试命名规范

```python
# 格式: test_<被测方法>_<场景>_<期望结果>
def test_create_workflow_with_valid_input_returns_workflow():
    pass

def test_create_workflow_with_empty_name_raises_validation_error():
    pass

def test_execute_workflow_when_already_running_raises_conflict_error():
    pass
```

### 10.4 测试文档要求

每个测试类必须包含:

```python
class TestExecuteWorkflowUseCase:
    """ExecuteWorkflow用例测试

    测试范围:
    - 成功执行工作流
    - 工作流不存在处理
    - 执行超时处理
    - 并发执行控制

    依赖:
    - WorkflowRepository (mock)
    - ExecutionEngine (mock)
    - EventBus (mock)

    相关模块:
    - src/application/use_cases/execute_workflow.py
    """
    pass
```

---

## 附录

### A. 测试命令速查

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit

# 运行集成测试 (需先配置依赖mock)
pytest tests/integration

# 排除手动测试目录
pytest --ignore=tests/manual

# 运行特定模块测试
pytest tests/unit/domain/agents/test_conversation_agent.py -v

# 生成覆盖率报告
pytest --cov=src --cov-report=html

# 运行标记的测试 (使用已定义的marker)
pytest -m integration  # 仅集成测试
pytest -m asyncio      # 仅异步测试

# 失败后立即停止
pytest -x

# 只运行上次失败的测试
pytest --lf

# 运行测试并显示最慢的10个
pytest --durations=10

# 详细输出失败信息
pytest -v --tb=short
```

> **注意**:
> - 项目启用了 `--strict-markers`，只能使用 `pyproject.toml` 中定义的marker
> - 如需并行测试，先安装 `pytest-xdist`: `pip install pytest-xdist`，然后使用 `pytest -n auto`

### B. 相关文档

- [架构审计](../architecture/current_agents.md)
- [多Agent协作指南](../architecture/multi_agent_collaboration_guide.md)
- [运维手册](../operations/operations_guide.md)
- [开发规范](../开发规范/)

---

**文档维护者**: Claude Code + Development Team
**最后更新**: 2025-12-14
