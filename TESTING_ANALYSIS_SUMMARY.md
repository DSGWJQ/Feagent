# Feagent 后端测试计划 - 结构化分析摘要

> **分析时间**: 2025-12-14
> **文档版本**: 1.1.0
> **分析范围**: BACKEND_TESTING_PLAN.md 全面解读

---

## 1. 需求摘要

### 1.1 核心测试目标（按优先级）

| 优先级 | 目标 | 目标覆盖率 | 时间窗口 |
|--------|------|----------|---------|
| **P0** | 修复测试基础设施，确保CI绿灯 | N/A | 1-2天 |
| **P1** | Application层UseCases入口覆盖 | 70% | 本周 |
| **P2** | Domain/Services核心模块 | 60-80% | 2周 |
| **P3** | Domain/Agents状态机 | 60-80% | 本月 |

### 1.2 当前严峻形势

```
总体覆盖率:        14.9%  (目标 50%)  ⚠️ 差距 -35.1%
├─ Domain层:      11.1%  (目标 60%)  🔴 差距 -48.9%
│  ├─ agents:     23.7%  (18模块0覆盖)
│  ├─ services:    4.9%  (137模块0覆盖)  ⚠️ 最严重
│  └─ entities:   46.6%
├─ Application:   27.4%  (目标 70%)  ⚠️ 差距 -42.6%
│  └─ 7个UseCase完全无测试
├─ Infrastructure: 31.3%  (目标 50%)  ⚠️ 差距 -18.7%
└─ Interface:     40.3%  (目标 50%)  ⚠️ 差距 -9.7%

失败测试数: 29-239个 (取决于环境)
├─ TDD Red未门禁:   58个 (24.3%)
├─ API隔离不足:     34个 (14.2%)
├─ 契约不一致:      31个 (13.0%)
└─ 其他根因:       116个 (48.5%)
```

### 1.3 关键瓶颈

1. **Domain/services仅4.9%覆盖** - 21,248行代码中20,212行未覆盖
2. **78个关键模块完全无测试** - 约23,132行代码
3. **测试隔离问题** - 依赖外部服务/真实数据库
4. **TDD Red阶段缺少门禁** - 稳定性红灯

---

## 2. 相关文件（关键模块列表）

### 2.1 P0级别（测试基础设施修复）

| 模块 | 文件路径 | 类型 | 工作量 |
|------|---------|------|--------|
| pytest配置 | `pyproject.toml` | 配置 | 0.5h |
| 全局fixtures | `tests/conftest.py` | 基础 | 2h |
| FastAPI依赖override | `tests/integration/api/scheduler/` | 集成 | 4h |
| TDD Red标记 | `tests/unit/domain/services/test_supervision_modules.py` | 标记 | 1h |
| SQLite隔离 | `tests/unit/infrastructure/executors/test_database_executor.py` | 修复 | 2h |

**影响**: 消除58-239个失败测试，让CI变绿

### 2.2 P1级别（Application/UseCases）- 7个模块0覆盖

| 模块 | 行数 | 当前覆盖 | 目标覆盖 | 用例数 | 风险等级 |
|------|------|---------|---------|--------|----------|
| `execute_run.py` | 297 | 0% | 80% | 18-20 | 🔴 CRITICAL |
| `classify_task.py` | 303 | 0% | 80% | 12-15 | 🔴 CRITICAL |
| `update_workflow_by_chat.py` | 285 | 0% | 70% | 15-18 | 🔴 CRITICAL |
| `create_agent.py` | 260 | 0% | 70% | 10-12 | 🟠 HIGH |
| `create_tool.py` | 123 | 0% | 70% | 8-10 | 🟡 MEDIUM |
| `import_workflow.py` | 147 | 0% | 70% | 6-8 | 🟡 MEDIUM |
| `github_auth.py` | 159 | 0% | 60% | 6-8 | 🟡 MEDIUM |

**位置**: `src/application/use_cases/`
**测试位置**: `tests/unit/application/use_cases/`

### 2.3 P2级别（Domain/Services）- 137个模块0-5%覆盖

#### 核心子系统（按优先级）

**规则引擎系统** (4模块)
| 模块 | 行数 | 风险 | 用例数 |
|------|------|------|--------|
| `configurable_rule_engine.py` | 685 | 🔴 CRITICAL | 25-30 |
| `rule_engine_facade.py` | 400+ | 🟠 HIGH | 15-20 |
| `supervision_module.py` | 500+ | 🟠 HIGH | 20-25 |
| `supervision_facade.py` | 350+ | 🟠 HIGH | 15-20 |

**节点验证系统** (3模块)
| 模块 | 行数 | 风险 | 用例数 |
|------|------|------|--------|
| `self_describing_node_validator.py` | 653 | 🔴 CRITICAL | 20-25 |
| `self_describing_node.py` | 855 | 🔴 CRITICAL | 25-30 |
| `node_yaml_validator.py` | 753 | 🔴 CRITICAL | 20-25 |

**执行监控系统** (4模块)
| 模块 | 行数 | 风险 | 用例数 |
|------|------|------|--------|
| `execution_monitor.py` | 604 | 🟠 HIGH | 18-20 |
| `dynamic_node_monitoring.py` | 724 | 🔴 CRITICAL | 25-30 |
| `container_execution_monitor.py` | 500+ | 🟠 HIGH | 20-25 |
| `logging_metrics.py` | 1160 | 🟡 MEDIUM | 15-20 |

**工具和依赖** (3模块)
| 模块 | 行数 | 风险 | 用例数 |
|------|------|------|--------|
| `tool_engine.py` | 500+ | 🟠 HIGH | 18-20 |
| `workflow_dependency_graph.py` | 400+ | 🟠 HIGH | 12-18 |
| `management_modules.py` | 1226 | 🟠 HIGH | 20-25 |

**位置**: `src/domain/services/`
**测试位置**: `tests/unit/domain/services/`

### 2.4 P3级别（Domain/Agents）- 18个模块0覆盖

| 模块 | 行数 | 风险 | 用例数 |
|------|------|------|--------|
| `error_handling.py` | 904 | 🔴 CRITICAL | 35-40 |
| `conversation_agent_react_core.py` | 645 | 🔴 CRITICAL | 28-30 |
| `conversation_agent_state.py` | 566 | 🔴 CRITICAL | 22-25 |
| `node_definition.py` | 671 | 🟠 HIGH | 25-30 |
| `agent_channel.py` | 517 | 🟠 HIGH | 18-20 |
| `container_executor.py` | 478 | 🟠 HIGH | 15-20 |
| `conversation_agent_recovery.py` | 440 | 🟠 HIGH | 20-25 |
| 其他10个 | ~4000 | 🟡 MEDIUM | 100+ |

**位置**: `src/domain/agents/`
**测试位置**: `tests/unit/domain/agents/`

### 2.5 基础设施层关键模块

| 模块 | 覆盖率 | 状态 | 优先级 |
|------|--------|------|--------|
| `models.py` (ORM) | 0% | 🔴 0覆盖 | P2 |
| `workflow_repository.py` | 0% | 🔴 0覆盖 | P2 |
| `chroma_retriever_service.py` | 0% | 🔴 0覆盖 | P2 |
| `rag_config_manager.py` | 0% | 🔴 0覆盖 | P2 |

---

## 3. 修改范围（需创建的测试文件）

### 3.1 P0阶段文件（配置+基础）

```
修改:
├── pyproject.toml                          (+5 lines)
└── tests/conftest.py                       (+80 lines)

新增:
└── tests/fixtures/                         (3个新文件)
    ├── agents.py       (Mock agents)
    ├── workflows.py    (Sample workflows)
    └── database.py     (Test DB fixtures)

修改集成测试:
├── tests/integration/api/scheduler/test_scheduler_api_integration.py
└── tests/integration/api/workflow_chat/    (多个文件)
```

### 3.2 P1阶段文件（应用层）- 7个新测试模块

```
新增:
tests/unit/application/use_cases/
├── test_execute_run.py                  (18-20个用例)
├── test_classify_task.py                (12-15个用例)
├── test_update_workflow_by_chat.py      (15-18个用例)
├── test_create_agent.py                 (10-12个用例)
├── test_create_tool.py                  (8-10个用例)
├── test_import_workflow.py              (6-8个用例)
└── test_github_auth.py                  (6-8个用例)

总计: 81-101个新的测试用例
```

### 3.3 P2阶段文件（服务层）- 18个新测试模块

```
新增核心服务测试:
tests/unit/domain/services/
├── test_configurable_rule_engine.py     (25-30个用例)
├── test_self_describing_node_validator.py (20-25个用例)
├── test_execution_monitor.py            (18-20个用例)
├── test_dynamic_node_monitoring.py      (25-30个用例)
├── test_tool_engine.py                  (18-20个用例)
├── test_workflow_dependency_graph.py    (12-18个用例)
└── ...其他12个模块                      (~120个用例)

总计: 180-220个新的测试用例
```

### 3.4 P3阶段文件（Agent层）- 18个新测试模块

```
新增Agent测试:
tests/unit/domain/agents/
├── test_error_handling.py               (35-40个用例)
├── test_conversation_agent_react_core.py (28-30个用例)
├── test_conversation_agent_state.py     (22-25个用例)
├── test_node_definition.py              (25-30个用例)
├── test_agent_channel.py                (18-20个用例)
└── ...其他13个模块                      (~150个用例)

总计: 250-300个新的测试用例
```

---

## 4. 如何修改（测试策略和方法）

### 4.1 P0阶段：测试基础设施修复

#### 目标
- 消除所有失败测试（58-239个）
- 让CI流水线变绿
- 建立可信的测试基础

#### 策略

**Step 1: 排除Manual测试目录**
```toml
# pyproject.toml - [tool.pytest.ini_options]
ignore = ["tests/manual"]
```

**Step 2: 添加通用Mock Fixture**
```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def mock_external_services(request):
    """自动mock外部网络调用"""
    if "integration" not in str(request.fspath):
        with patch("requests.get"), patch("requests.post"):
            yield
    else:
        yield

@pytest.fixture(scope="session")
def test_engine():
    """测试数据库引擎"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(test_engine):
    """自动回滚的会话"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

**Step 3: 修复API集成测试中的FastAPI依赖注入**
```python
# 问题: TestClient使用默认dependencies，不使用覆盖的mock数据库
# 解决: 在conftest中创建override fixture

@pytest.fixture
def test_client():
    """正确配置的TestClient"""
    # 创建测试DB
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # 应用覆盖
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_llm_service] = lambda: MockLLMService()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
```

**Step 4: 标记TDD Red测试为xfail**
```python
# tests/unit/domain/services/test_supervision_modules.py
@pytest.mark.xfail(reason="TDD Red阶段 - 实现未完成")
def test_supervision_module_integration():
    pass
```

#### 预期结果
- CI从红灯变绿灯
- 可信的test baseline
- 为P1做准备

### 4.2 P1阶段：Application层测试补齐

#### 目标
- Application层覆盖率≥70%
- 所有7个UseCase有完整测试

#### 策略

**测试结构模板** (以ExecuteRun为例)

```python
# tests/unit/application/use_cases/test_execute_run.py

class TestExecuteRunUseCase:
    """ExecuteRun用例测试

    测试范围:
    - 成功执行运行
    - 状态管理
    - 错误处理
    - 输入验证
    - 边界条件

    依赖Mock:
    - WorkflowRepository
    - RunRepository
    - Executor
    - EventBus
    """

    @pytest.fixture
    def use_case(self, mock_run_repo, mock_workflow_repo, mock_executor):
        return ExecuteRunUseCase(
            run_repository=mock_run_repo,
            workflow_repository=mock_workflow_repo,
            executor=mock_executor
        )

    # ===== Happy Path =====
    async def test_execute_run_success(self, use_case):
        """成功执行运行"""
        result = await use_case.execute(ExecuteRunInput(run_id="run_123"))
        assert result.success is True
        assert result.output is not None

    async def test_execute_run_updates_status(self, use_case, mock_run_repo):
        """执行时更新运行状态"""
        await use_case.execute(ExecuteRunInput(run_id="run_123"))
        mock_run_repo.update.assert_called()
        saved_run = mock_run_repo.update.call_args[0][0]
        assert saved_run.status == RunStatus.COMPLETED

    async def test_execute_run_publishes_events(self, use_case, mock_event_bus):
        """执行时发布事件"""
        await use_case.execute(ExecuteRunInput(run_id="run_123"))
        assert mock_event_bus.publish.called

    # ===== Error Path =====
    async def test_execute_run_not_found(self, use_case, mock_run_repo):
        """运行不存在时抛出异常"""
        mock_run_repo.find_by_id.return_value = None
        with pytest.raises(RunNotFoundError):
            await use_case.execute(ExecuteRunInput(run_id="not_exist"))

    async def test_execute_run_workflow_not_found(self, use_case, mock_workflow_repo):
        """工作流不存在时抛出异常"""
        mock_workflow_repo.find_by_id.return_value = None
        with pytest.raises(WorkflowNotFoundError):
            await use_case.execute(ExecuteRunInput(run_id="run_123"))

    async def test_execute_run_executor_failure(self, use_case, mock_executor):
        """执行器失败时处理错误"""
        mock_executor.execute.side_effect = ExecutionError("timeout")
        result = await use_case.execute(ExecuteRunInput(run_id="run_123"))
        assert result.success is False
        assert "timeout" in result.error_message

    # ===== Edge Cases =====
    async def test_execute_run_already_running(self, use_case, mock_run_repo):
        """已在运行时拒绝重复执行"""
        mock_run_repo.find_by_id.return_value = Run(status=RunStatus.RUNNING)
        with pytest.raises(RunAlreadyRunningError):
            await use_case.execute(ExecuteRunInput(run_id="run_123"))

    async def test_execute_run_concurrent_execution(self, use_case):
        """并发执行时正确处理锁"""
        # 使用asyncio.gather测试并发安全性
        results = await asyncio.gather(
            use_case.execute(ExecuteRunInput(run_id="run_123")),
            use_case.execute(ExecuteRunInput(run_id="run_123")),
        )
        # 应该只有一个成功
        assert sum(r.success for r in results) == 1

    # ===== Input Validation =====
    @pytest.mark.parametrize("invalid_input", [
        ExecuteRunInput(run_id=""),
        ExecuteRunInput(run_id=None),
    ])
    async def test_execute_run_invalid_input(self, use_case, invalid_input):
        """无效输入验证"""
        with pytest.raises(ValidationError):
            await use_case.execute(invalid_input)
```

**测试用例构成** (每个UseCase约12-20个用例)
- Happy Path: 3-5个
- Error Path: 3-5个
- Edge Cases: 2-4个
- Input Validation: 2-3个
- Integration: 2-3个

### 4.3 P2阶段：Domain/Services核心测试

#### 目标
- Domain/services覆盖率≥60%
- 核心子系统闭环测试

#### 策略

**例: ConfigurableRuleEngine测试**

```python
# tests/unit/domain/services/test_configurable_rule_engine.py

class TestConfigurableRuleEngine:
    """可配置规则引擎测试"""

    @pytest.fixture
    def engine(self):
        return ConfigurableRuleEngine()

    # ===== 规则加载 =====
    def test_load_rule_from_dict(self, engine):
        """从字典加载规则"""
        rule_dict = {
            "name": "check_agent_exists",
            "condition": "agent_id != null",
            "actions": [{"type": "allow"}]
        }
        rule = engine.load_rule(rule_dict)
        assert rule.name == "check_agent_exists"

    def test_load_rule_from_yaml(self, engine):
        """从YAML加载规则"""
        yaml_content = """
        name: check_agent_exists
        condition: agent_id != null
        actions:
          - type: allow
        """
        rule = engine.load_rule_from_yaml(yaml_content)
        assert rule.name == "check_agent_exists"

    # ===== 规则执行 =====
    def test_execute_rule_condition_true(self, engine):
        """条件为真时执行动作"""
        rule = Rule(
            name="test",
            condition="x > 5",
            actions=[Action(type="allow")]
        )
        context = {"x": 10}
        result = engine.execute(rule, context)
        assert result.allowed is True

    def test_execute_rule_condition_false(self, engine):
        """条件为假时不执行动作"""
        rule = Rule(
            name="test",
            condition="x > 5",
            actions=[Action(type="deny")]
        )
        context = {"x": 3}
        result = engine.execute(rule, context)
        assert result.allowed is False

    # ===== 规则集合 =====
    def test_load_rule_set(self, engine):
        """加载规则集合"""
        rules = [
            {"name": "rule1", "condition": "a > 0", "actions": [...]},
            {"name": "rule2", "condition": "b > 0", "actions": [...]},
        ]
        rule_set = engine.load_rule_set("test_set", rules)
        assert len(rule_set.rules) == 2

    def test_rule_set_execution_order(self, engine):
        """规则集合按顺序执行"""
        rule_set = RuleSet(
            rules=[
                Rule(name="r1", condition="True", actions=[...]),
                Rule(name="r2", condition="True", actions=[...]),
            ]
        )
        results = engine.execute_rule_set(rule_set, {})
        assert results[0].rule_name == "r1"
        assert results[1].rule_name == "r2"

    # ===== 表达式求值 =====
    def test_evaluate_simple_expression(self, engine):
        """求值简单表达式"""
        context = {"x": 10, "y": 5}
        result = engine.evaluate("x > y", context)
        assert result is True

    def test_evaluate_complex_expression(self, engine):
        """求值复杂表达式"""
        context = {"agent_id": "123", "status": "active"}
        result = engine.evaluate(
            "agent_id != null and status == 'active'",
            context
        )
        assert result is True

    # ===== 错误处理 =====
    def test_invalid_rule_syntax(self, engine):
        """无效规则语法抛出异常"""
        with pytest.raises(RuleSyntaxError):
            engine.load_rule({"name": "", "condition": ">>invalid"})

    def test_missing_context_variable(self, engine):
        """缺少上下文变量时抛出异常"""
        rule = Rule(condition="missing_var > 0", actions=[...])
        with pytest.raises(ContextError):
            engine.execute(rule, {})
```

### 4.4 P3阶段：Domain/Agents测试

#### 目标
- Domain/agents覆盖率≥60%
- 关键Agent状态机覆盖

#### 策略

**例: ConversationAgent错误处理测试**

```python
# tests/unit/domain/agents/test_error_handling.py

class TestErrorHandlingInConversationAgent:
    """ConversationAgent错误处理测试"""

    @pytest.fixture
    async def agent(self):
        return ConversationAgent(
            llm=AsyncMock(),
            event_bus=AsyncMock(),
            max_iterations=5
        )

    # ===== 错误分类 =====
    async def test_classify_timeout_error(self, agent):
        """识别超时错误"""
        error = TimeoutError("LLM请求超时")
        classification = agent.classify_error(error)
        assert classification.type == ErrorType.TIMEOUT
        assert classification.severity == ErrorSeverity.HIGH

    async def test_classify_rate_limit_error(self, agent):
        """识别限流错误"""
        error = RateLimitError("API限流")
        classification = agent.classify_error(error)
        assert classification.type == ErrorType.RATE_LIMIT
        assert classification.severity == ErrorSeverity.MEDIUM

    # ===== 恢复策略 =====
    async def test_retry_on_transient_error(self, agent):
        """瞬时错误自动重试"""
        agent.llm.think.side_effect = [
            ConnectionError("连接失败"),
            {"thought": "重试成功"}
        ]
        result = await agent.think("query", max_retries=2)
        assert result["thought"] == "重试成功"
        assert agent.llm.think.call_count == 2

    async def test_circuit_breaker_on_persistent_error(self, agent):
        """持续错误时打开熔断器"""
        agent.llm.think.side_effect = ConnectionError("连接失败")

        for _ in range(5):
            with pytest.raises(CircuitBreakerError):
                await agent.think("query")

        # 熔断器应该打开
        assert agent.circuit_breaker.is_open()

    # ===== 用户消息生成 =====
    async def test_user_friendly_timeout_message(self, agent):
        """超时错误生成用户友好消息"""
        error = TimeoutError("LLM timeout")
        message = agent.generate_user_message(error)
        assert "超时" in message
        assert "稍后重试" in message

    async def test_user_message_includes_recovery_action(self, agent):
        """用户消息包含恢复建议"""
        error = RateLimitError("API限流")
        message = agent.generate_user_message(error)
        assert "重新尝试" in message or "等待" in message
```

---

## 5. 改什么：具体测试场景和覆盖点

### 5.1 P0阶段：5个任务

| 任务 | 测试场景 | 覆盖点 | 工作量 |
|------|----------|--------|--------|
| 配置pytest | 忽略manual目录 | manual不被收集 | 15min |
| Mock外部服务 | 网络调用被拦截 | 无真实HTTP请求 | 1h |
| FastAPI依赖 | TestClient使用覆盖DB | 集成测试隔离 | 2h |
| TDD Red标记 | 标记为xfail/skip | 不计入失败 | 30min |
| 数据库并行 | SQLite事务隔离 | 无锁定冲突 | 2h |

### 5.2 P1阶段：7个UseCase，81-101个用例

**ExecuteRun (18-20个)**
- ✅ 成功执行：不同状态、异步、并发
- ✅ 状态转换：初始→运行→完成/失败
- ✅ 错误处理：未找到、超时、执行失败
- ✅ 边界条件：已在运行、并发竞态
- ✅ 输入验证：空ID、None值

**ClassifyTask (12-15个)**
- ✅ 任务分类准确性：不同业务类型
- ✅ 意图识别：关键词、上下文
- ✅ 优先级评估：紧急级别
- ✅ 工作流匹配：推荐工作流
- ✅ 边界情况：未知类型、歧义

**UpdateWorkflowByChat (15-18个)**
- ✅ 节点添加：新增、更新
- ✅ 边更新：连接、删除
- ✅ 节点属性修改：参数、代码
- ✅ 工作流验证：DAG检查、循环检测
- ✅ 版本管理：提交、回滚
- ✅ 并发更新：冲突处理

**创建Agent/Tool/Workflow (30-45个)**
- ✅ 实体创建：必填项、默认值
- ✅ 验证：命名、格式
- ✅ 持久化：数据库保存
- ✅ 关联：权限、所有者
- ✅ 重复检测：唯一性约束

### 5.3 P2阶段：Domain/Services核心，180-220个用例

**ConfigurableRuleEngine (25-30个)**
- ✅ 规则加载：YAML/JSON/Dict
- ✅ 表达式求值：简单/复杂/嵌套
- ✅ 条件评估：真/假/异常
- ✅ 动作执行：Allow/Deny/Log
- ✅ 规则集合：顺序/并行/短路
- ✅ 上下文变量：存在/缺失/类型错误
- ✅ 性能：大规则集、深表达式

**SelfDescribingNodeValidator (20-25个)**
- ✅ 节点验证：元数据、输入输出
- ✅ 类型检查：参数类型匹配
- ✅ 依赖验证：输入源检查
- ✅ 自描述验证：JSON Schema
- ✅ 版本兼容性：升级路径

**ExecutionMonitor (18-20个)**
- ✅ 执行跟踪：开始/进度/完成
- ✅ 指标收集：耗时、内存、错误
- ✅ 日志记录：不同级别
- ✅ 告警触发：超时、失败
- ✅ 报告生成：汇总数据

**DynamicNodeMonitoring (25-30个)**
- ✅ 节点监控：状态、性能
- ✅ 异常检测：异常值识别
- ✅ 自愈机制：自动重启
- ✅ 健康检查：心跳、探针
- ✅ 回滚机制：故障恢复

### 5.4 P3阶段：Domain/Agents，250-300个用例

**ErrorHandling (35-40个)**
- ✅ 错误分类：瞬时/永久/未知
- ✅ 恢复策略：重试/降级/熔断
- ✅ 用户消息：友好提示
- ✅ 日志记录：完整堆栈
- ✅ 监控告警：错误率告警

**ReActCore (28-30个)**
- ✅ 推理循环：Thought→Action→Observation
- ✅ 终止条件：达到目标/迭代限制
- ✅ 工具调用：正确参数、结果处理
- ✅ Token管理：限制/压缩
- ✅ 并发安全：锁机制

**AgentState (22-25个)**
- ✅ 状态转换：所有合法转换
- ✅ 非法转换：拒绝不合法
- ✅ 并发安全：锁/原子性
- ✅ 回滚：事务一致性
- ✅ 持久化：状态保存

**NodeDefinition (25-30个)**
- ✅ 创建：必填验证
- ✅ 验证：格式/类型
- ✅ 序列化：JSON/YAML
- ✅ 层级：父子关系
- ✅ 版本：兼容性检查

---

## 6. 执行路线图

### Phase 1: P0 (1-2天)
```
Day 1:
├── 修改pyproject.toml (15min)
├── 增强conftest.py (1h)
├── 修复scheduler API集成 (2h)
└── 标记TDD Red测试 (30min)

Day 2:
├── 修复数据库隔离 (2h)
├── 修复SQLite并行 (1h)
└── CI验证绿灯 (1h)

里程碑 M1: CI绿灯 ✅
```

### Phase 2: P1 (1周)
```
Week 1:
├── test_execute_run.py (2h)
├── test_classify_task.py (1.5h)
├── test_update_workflow_by_chat.py (1.5h)
├── test_create_agent.py (1.5h)
├── test_create_tool.py (1h)
├── test_import_workflow.py (1h)
└── test_github_auth.py (1h)

里程碑 M2: Application ≥70% ✅
```

### Phase 3: P2 (2周)
```
Week 2-3:
├── 规则引擎系统 (3h)
├── 节点验证系统 (3h)
├── 执行监控系统 (3h)
├── 工具和依赖 (3h)
└── 基础设施层 (2h)

里程碑 M3: Core services ≥50% ✅
```

### Phase 4: P3 (2周)
```
Week 4-5:
├── 错误处理系统 (2h)
├── ReAct推理核心 (2h)
├── Agent状态机 (2h)
└── 其他Agent模块 (4h)

里程碑 M4: Agents ≥60% ✅
里程碑 M5: 总体覆盖 ≥50% ✅
```

---

## 7. 质量标准

### 7.1 代码覆盖率要求

```
最低要求 → 目标值
Domain/entities:     80% → 90%
Domain/services:     60% → 80%
Domain/agents:       60% → 80%
Application:         70% → 85%
Infrastructure:      50% → 70%
Interface:           40% → 60%
```

### 7.2 测试命名规范

```python
# 格式: test_<method>_<scenario>_<expected>
✅ test_execute_run_with_valid_input_returns_success()
✅ test_execute_run_when_not_found_raises_error()
✅ test_execute_run_updates_status_to_completed()

❌ test_execute_run()
❌ test_run()
❌ test_1()
```

### 7.3 PR合并门禁

```yaml
required:
  - unit_tests: all pass
  - integration_tests: all pass
  - coverage_diff: ≥60%  # 新增代码
  - static_analysis: ruff + pyright pass
  - no_regression: 覆盖率 ≥-2%
```

---

## 8. 关键注意事项

### 8.1 测试隔离最佳实践

```python
# ❌ 错误: 依赖外部服务
def test_api_call():
    response = requests.get("https://api.example.com")
    assert response.status_code == 200

# ✅ 正确: Mock外部服务
@patch("requests.get")
def test_api_call(mock_get):
    mock_get.return_value.status_code = 200
    response = requests.get("https://api.example.com")
    assert response.status_code == 200
```

### 8.2 FastAPI集成测试

```python
# ❌ 错误: TestClient使用实际DB
engine = create_engine("sqlite:///test.db")
client = TestClient(app)

# ✅ 正确: 覆盖依赖
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)
app.dependency_overrides.clear()
```

### 8.3 异步测试

```python
# ✅ pytest-asyncio自动处理
async def test_async_function():
    result = await async_function()
    assert result is not None

# ✅ 使用AsyncMock
from unittest.mock import AsyncMock
mock_service = AsyncMock()
mock_service.method.return_value = "result"
```

### 8.4 参数化测试

```python
@pytest.mark.parametrize("input,expected", [
    ("valid", True),
    ("", False),
    (None, False),
])
def test_validate_input(input, expected):
    assert validate(input) == expected
```

---

## 9. 依赖和工具

### 已安装
- pytest >= 8.3.0
- pytest-asyncio >= 0.24.0
- pytest-cov >= 6.0.0
- pytest-mock >= 3.14.0

### 需要补充
- pytest-xdist (并行测试) - `pip install pytest-xdist`
- responses (HTTP mock) - `pip install responses`

---

## 10. 快速参考

### 运行测试

```bash
# P0阶段: 验证基础设施
pytest -x --ignore=tests/manual

# P1阶段: 检查Application覆盖率
pytest tests/unit/application --cov=src.application --cov-report=term-missing

# P2阶段: 检查services覆盖率
pytest tests/unit/domain/services --cov=src.domain.services --cov-report=html

# P3阶段: 检查agents覆盖率
pytest tests/unit/domain/agents --cov=src.domain.agents --cov-report=html

# 生成完整覆盖率报告
pytest --cov=src --cov-report=html --cov-report=term-missing

# 只运行上次失败的测试
pytest --lf

# 查看最慢的10个测试
pytest --durations=10
```

---

**文档生成时间**: 2025-12-14
**下一步**: 按P0→P1→P2→P3顺序执行，每个阶段完成后更新此文档
