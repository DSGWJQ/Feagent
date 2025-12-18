# 测试计划快速参考表

> 生成时间: 2025-12-14
> 用途: 快速查询和任务分配

---

## 📊 优先级矩阵速查

### P0: 测试基础设施修复 (1-2天)

| 任务 | 文件 | 预计工作量 | 优先级 | 难度 |
|------|------|----------|--------|------|
| 配置pytest忽略manual | `pyproject.toml` | 15min | 🔴 CRITICAL | ⭐ |
| 添加通用Mock Fixture | `tests/conftest.py` | 1h | 🔴 CRITICAL | ⭐⭐ |
| 修复FastAPI依赖注入 | `tests/integration/api/scheduler/` | 2h | 🔴 CRITICAL | ⭐⭐⭐ |
| 标记TDD Red测试 | `tests/unit/domain/services/test_*.py` | 30min | 🔴 CRITICAL | ⭐ |
| 修复SQLite并行隔离 | `tests/conftest.py` | 2h | 🔴 CRITICAL | ⭐⭐ |

**里程碑**: M1 - CI绿灯 ✅
**目标**: 消除所有测试失败(58-239个) → 绿灯

---

### P1: Application层 (1周)

| 模块 | 行数 | 用例数 | 工作量 | 难度 | 状态 |
|------|------|--------|--------|------|------|
| `execute_run.py` | 297 | 18-20 | 2h | ⭐⭐⭐ | 待做 |
| `classify_task.py` | 303 | 12-15 | 1.5h | ⭐⭐⭐ | 待做 |
| `update_workflow_by_chat.py` | 285 | 15-18 | 2h | ⭐⭐⭐ | 待做 |
| `create_agent.py` | 260 | 10-12 | 1.5h | ⭐⭐ | 待做 |
| `create_tool.py` | 123 | 8-10 | 1h | ⭐⭐ | 待做 |
| `import_workflow.py` | 147 | 6-8 | 1h | ⭐⭐ | 待做 |
| `github_auth.py` | 159 | 6-8 | 1h | ⭐ | 待做 |

**总计**: 81-101个测试用例，预计周期1周
**里程碑**: M2 - Application ≥70% ✅
**目标**: 应用层测试覆盖率从27.4% → 70%+

---

### P2: Domain/Services (2周)

#### 规则引擎系统 (4模块)

| 模块 | 关键测试场景 | 用例数 | 工作量 | 优先 |
|------|------------|--------|--------|------|
| `configurable_rule_engine.py` | 规则加载/执行/表达式求值 | 25-30 | 2h | P2-1 |
| `rule_engine_facade.py` | 门面接口统一入口 | 15-20 | 1.5h | P2-1 |
| `supervision_module.py` | 监督分析器/规则引擎链 | 20-25 | 1.5h | P2-1 |
| `supervision_facade.py` | 监督模块统一入口 | 15-20 | 1h | P2-2 |

#### 节点验证系统 (3模块)

| 模块 | 关键测试场景 | 用例数 | 工作量 | 优先 |
|------|------------|--------|--------|------|
| `self_describing_node_validator.py` | 节点验证/自描述 | 20-25 | 2h | P2-1 |
| `self_describing_node.py` | 元数据验证/JSON Schema | 25-30 | 2h | P2-1 |
| `node_yaml_validator.py` | YAML验证/类型检查 | 20-25 | 1.5h | P2-1 |

#### 执行监控系统 (4模块)

| 模块 | 关键测试场景 | 用例数 | 工作量 | 优先 |
|------|------------|--------|--------|------|
| `execution_monitor.py` | 执行跟踪/指标收集 | 18-20 | 1.5h | P2-2 |
| `dynamic_node_monitoring.py` | 异常检测/自愈/健康检查 | 25-30 | 2h | P2-2 |
| `container_execution_monitor.py` | 容器事件监控 | 20-25 | 1.5h | P2-2 |
| `logging_metrics.py` | 日志/指标聚合 | 15-20 | 1.5h | P2-2 |

#### 工具和依赖 (3模块)

| 模块 | 关键测试场景 | 用例数 | 工作量 | 优先 |
|------|------------|--------|--------|------|
| `tool_engine.py` | 工具加载/执行/参数验证 | 18-20 | 1.5h | P2-3 |
| `workflow_dependency_graph.py` | DAG构建/拓扑排序 | 12-18 | 1.5h | P2-3 |
| `management_modules.py` | 管理模块集合 | 20-25 | 2h | P2-3 |

**总计**: 170-220个测试用例，预计周期2周
**里程碑**: M3 - Core Services ≥50% ✅

---

### P3: Domain/Agents (2周)

| 模块 | 行数 | 关键测试场景 | 用例数 | 工作量 | 优先 |
|------|------|-----------|--------|--------|------|
| `error_handling.py` | 904 | 错误分类/恢复/用户消息 | 35-40 | 2h | P3-1 |
| `conversation_agent_react_core.py` | 645 | ReAct循环/终止/token | 28-30 | 2h | P3-1 |
| `conversation_agent_state.py` | 566 | 状态转换/并发/回滚 | 22-25 | 1.5h | P3-1 |
| `node_definition.py` | 671 | 创建/验证/序列化 | 25-30 | 2h | P3-1 |
| `agent_channel.py` | 517 | WebSocket/连接/消息 | 18-20 | 1.5h | P3-2 |
| `conversation_agent_recovery.py` | 440 | 恢复逻辑/重试/降级 | 20-25 | 1.5h | P3-2 |
| 其他12个模块 | 4000+ | 辅助功能 | 150+ | 8h | P3-3 |

**总计**: 250-300个测试用例，预计周期2周
**里程碑**: M4/M5 - Agents ≥60%, 总体 ≥50% ✅

---

## 🎯 按测试类型分类

### 单元测试 (Domain + Application)

```python
# 特点: 快速、隔离、mock所有依赖
# 位置: tests/unit/

# Domain单元测试模板
def test_domain_entity_validate():
    """纯业务逻辑测试"""
    entity = Entity(name="test")
    errors = entity.validate()
    assert len(errors) == 0

# Application单元测试模板
def test_use_case_success():
    """UseCase测试 - mock所有Repository"""
    use_case = CreateAgentUseCase(repository=Mock())
    result = use_case.execute(CreateAgentInput(name="test"))
    assert result.success
```

### 集成测试 (多层交互)

```python
# 特点: 验证多层协作、mock外部服务
# 位置: tests/integration/

# API集成测试
@pytest.fixture
def test_client():
    """正确配置的FastAPI TestClient"""
    # 覆盖数据库依赖
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

def test_create_workflow_api(test_client):
    response = test_client.post("/api/workflows", json={...})
    assert response.status_code == 201
```

### 契约测试 (端口/协议)

```python
# 特点: 验证port protocol实现一致性
# 位置: tests/unit/domain/ports/

class TestRepositoryContract:
    """Repository契约验证"""
    def test_find_by_id_returns_entity_or_none(self, repository):
        # 定义contract: 返回Entity或None，不抛异常
        result = repository.find_by_id("123")
        assert isinstance(result, (Entity, type(None)))
```

---

## 📋 测试模板库

### 1. Domain实体单元测试模板

```python
class TestAgentEntity:
    """Agent实体测试"""

    def test_create_with_valid_data(self):
        """成功创建"""
        agent = Agent.create(name="test", description="desc")
        assert agent.id is not None
        assert agent.name == "test"

    def test_create_with_empty_name_raises_error(self):
        """验证：名称必填"""
        with pytest.raises(ValidationError):
            Agent.create(name="", description="desc")

    def test_update_preserves_id(self):
        """更新不改变ID"""
        agent = Agent.create(name="old")
        original_id = agent.id
        agent.update(name="new")
        assert agent.id == original_id

    @pytest.mark.parametrize("name", ["", None, "   "])
    def test_invalid_names(self, name):
        """参数化测试多个无效输入"""
        with pytest.raises(ValidationError):
            Agent.create(name=name)
```

### 2. UseCase单元测试模板

```python
class TestExecuteWorkflowUseCase:
    """ExecuteWorkflow UseCase测试"""

    @pytest.fixture
    def use_case(self):
        mock_repo = Mock(spec=WorkflowRepository)
        mock_executor = Mock()
        return ExecuteWorkflowUseCase(
            repository=mock_repo,
            executor=mock_executor
        )

    async def test_execute_success(self, use_case):
        """成功执行路径"""
        result = await use_case.execute(ExecuteWorkflowInput(id="wf_123"))
        assert result.success is True

    async def test_workflow_not_found_raises_error(self, use_case):
        """异常路径：工作流不存在"""
        use_case.repository.find_by_id.return_value = None
        with pytest.raises(WorkflowNotFoundError):
            await use_case.execute(ExecuteWorkflowInput(id="not_exist"))

    async def test_executor_failure_recorded(self, use_case):
        """异常路径：执行器失败"""
        use_case.executor.execute.side_effect = RuntimeError("failed")
        result = await use_case.execute(ExecuteWorkflowInput(id="wf_123"))
        assert result.success is False
        assert "failed" in result.error_message
```

### 3. API集成测试模板

```python
@pytest.fixture
def test_client():
    """覆盖FastAPI依赖"""
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    def get_db_override():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = get_db_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

def test_create_workflow_api(test_client):
    """API端点测试"""
    response = test_client.post("/api/workflows", json={
        "name": "Test Workflow",
        "description": "Test"
    })
    assert response.status_code == 201
    assert response.json()["name"] == "Test Workflow"

def test_workflow_not_found_api(test_client):
    """API错误处理测试"""
    response = test_client.get("/api/workflows/not_exist")
    assert response.status_code == 404
```

### 4. 异步代码测试模板

```python
@pytest.mark.asyncio
async def test_async_operation():
    """异步操作测试"""
    result = await async_function()
    assert result is not None

@pytest.mark.asyncio
async def test_concurrent_operations():
    """并发操作测试"""
    results = await asyncio.gather(
        async_function(),
        async_function(),
        async_function(),
    )
    assert len(results) == 3

@pytest.mark.asyncio
async def test_async_with_mock():
    """异步mock测试"""
    mock_service = AsyncMock()
    mock_service.fetch.return_value = {"data": "test"}
    result = await mock_service.fetch()
    assert result["data"] == "test"
```

### 5. 参数化测试模板

```python
@pytest.mark.parametrize("input,expected,should_raise", [
    ("valid_name", True, False),
    ("", False, True),
    (None, False, True),
    ("x" * 1000, False, True),
])
def test_name_validation(input, expected, should_raise):
    """参数化验证多个场景"""
    if should_raise:
        with pytest.raises(ValidationError):
            validate_name(input)
    else:
        assert validate_name(input) == expected

@pytest.mark.parametrize("agent_type,config", [
    ("conversation", ConversationAgentConfig()),
    ("workflow", WorkflowAgentConfig()),
    ("coordinator", CoordinatorAgentConfig()),
])
def test_agent_creation(agent_type, config):
    """不同类型Agent创建"""
    agent = AgentFactory.create(agent_type, config)
    assert agent is not None
```

---

## 🔍 常见问题排查

### ❌ 问题1: "ImportError: No module named 'xxx'"

**原因**: PYTHONPATH未包含`src/`
**解决**:
```bash
# 方法1: 使用pytest-root-dir插件
pip install pytest-root-dir

# 方法2: 在conftest.py添加
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
```

### ❌ 问题2: "dependency injection fails, TestClient uses real DB"

**原因**: FastAPI依赖未覆盖
**解决**:
```python
# conftest.py中添加
@pytest.fixture
def test_client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()  # 必须清除!
```

### ❌ 问题3: "tests/manual/test_xxx.py collected but should be ignored"

**原因**: pytest.ini未配置ignore
**解决**:
```toml
# pyproject.toml
[tool.pytest.ini_options]
ignore = ["tests/manual"]
```

### ❌ 问题4: "AssertionError: assert mock_obj.method.called"

**原因**: Mock未被正确创建或调用
**解决**:
```python
# 正确的Mock使用
from unittest.mock import Mock, AsyncMock, patch

# 同步mock
mock_repo = Mock(spec=Repository)
mock_repo.find_by_id.return_value = entity
result = mock_repo.find_by_id("123")
mock_repo.find_by_id.assert_called_once_with("123")

# 异步mock
mock_service = AsyncMock()
await mock_service.fetch()
mock_service.fetch.assert_called_once()
```

### ❌ 问题5: "sqlite3.OperationalError: database is locked"

**原因**: SQLite并发访问
**解决**:
```python
# 使用事务隔离
@pytest.fixture
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    transaction.rollback()  # 每个测试自动回滚
    connection.close()
```

---

## 📈 进度追踪

### 里程碑检查清单

- [ ] **M1**: CI绿灯 (P0完成)
  - [ ] pytest忽略manual目录
  - [ ] Mock外部服务工作
  - [ ] FastAPI依赖覆盖
  - [ ] SQLite隔离修复
  - [ ] 0个失败测试

- [ ] **M2**: Application ≥70% (P1完成)
  - [ ] execute_run 测试完成
  - [ ] classify_task 测试完成
  - [ ] update_workflow_by_chat 测试完成
  - [ ] create_agent/tool/workflow 测试完成
  - [ ] Application覆盖率验证

- [ ] **M3**: Core Services ≥50% (P2-1完成)
  - [ ] ConfigurableRuleEngine 测试完成
  - [ ] SelfDescribingNodeValidator 测试完成
  - [ ] Services覆盖率验证

- [ ] **M4**: Agents ≥60% (P3-1完成)
  - [ ] ErrorHandling 测试完成
  - [ ] ReActCore 测试完成
  - [ ] ConversationAgentState 测试完成
  - [ ] Agents覆盖率验证

- [ ] **M5**: 总体 ≥50% (全部完成)
  - [ ] 所有P0/P1/P2/P3任务完成
  - [ ] 总体覆盖率检查
  - [ ] CI/CD集成

---

## 🚀 快速启动命令

```bash
# 1. 初始化开发环境
pip install -e ".[dev]"
pytest --version

# 2. 运行P0阶段验证
pytest -x --ignore=tests/manual

# 3. 创建新测试文件
touch tests/unit/application/use_cases/test_execute_run.py

# 4. 运行特定测试并看覆盖率
pytest tests/unit/application/use_cases/test_execute_run.py \
  --cov=src.application.use_cases \
  --cov-report=term-missing

# 5. 生成HTML覆盖率报告
pytest --cov=src --cov-report=html
# 打开: htmlcov/index.html

# 6. 运行上次失败的测试
pytest --lf

# 7. 并行运行测试 (需要pytest-xdist)
pip install pytest-xdist
pytest -n auto
```

---

**更新时间**: 2025-12-14
**下次更新**: P0完成后更新进度追踪
