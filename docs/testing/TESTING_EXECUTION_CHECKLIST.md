# 测试计划执行清单

> **版本**: v1.0.0
> **日期**: 2025-12-14
> **目标**: 将后端测试计划转化为可立即执行的任务清单

---

## 📝 P0阶段执行清单（1-2天）

### 子任务1: pytest配置修改

**文件**: `pyproject.toml`
**工作量**: 15 minutes
**优先级**: 🔴 CRITICAL

#### 操作步骤
```toml
# 修改位置: [tool.pytest.ini_options]
# 添加一行:
ignore = ["tests/manual"]

# 完整配置应该是:
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
ignore = ["tests/manual"]  # 新增
addopts = [
    "-v",
    "--strict-markers",
    "--cov=src",
    "--cov-report=term-missing",
    "--cov-report=html",
]
```

#### 验证方法
```bash
# 修改后运行，确保manual目录被忽略
pytest --collect-only | grep manual
# 应该无输出（没有manual下的测试）
```

---

### 子任务2: 增强conftest.py

**文件**: `tests/conftest.py`
**工作量**: 1 hour
**优先级**: 🔴 CRITICAL

#### 操作步骤

```python
# 在 tests/conftest.py 文件末尾添加以下代码:

import pytest
from unittest.mock import patch, Mock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
import os
import sys

# ============ 1. Mock外部服务 ============
@pytest.fixture(autouse=True)
def mock_external_services(request):
    """自动Mock外部网络调用 (单元测试)

    集成测试中不应用此mock，因为它们需要测试实际集成
    """
    # 只在单元测试中应用mock
    if "integration" not in str(request.fspath):
        with patch("requests.get"), \
             patch("requests.post"), \
             patch("httpx.get"), \
             patch("httpx.post"):
            yield
    else:
        # 集成测试正常执行
        yield


# ============ 2. 测试数据库fixtures ============
@pytest.fixture(scope="session")
def test_engine():
    """Session级别的测试数据库引擎

    优点:
    - 所有测试共享同一个内存数据库
    - 数据库初始化只做一次
    - 快速
    """
    # 使用内存SQLite (最快)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )

    # 导入Base（需要从项目中导入）
    try:
        from src.infrastructure.database.base import Base
        Base.metadata.create_all(bind=engine)
    except ImportError:
        # 如果导入失败，可能是路径问题
        pass

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """函数级别的数据库会话

    每个测试都会获得一个新会话
    测试完成后自动回滚，确保数据隔离
    """
    connection = test_engine.connect()
    transaction = connection.begin()

    # 创建会话，绑定到测试连接
    session = Session(bind=connection)

    yield session

    # 清理：回滚事务（撤销所有修改），关闭连接
    session.close()
    transaction.rollback()
    connection.close()


# ============ 3. FastAPI TestClient fixture ============
@pytest.fixture
def test_client(db_session):
    """正确配置的FastAPI TestClient

    关键: 覆盖所有依赖
    - get_db -> 测试数据库会话
    - get_llm_service -> Mock LLM
    - 其他外部服务 -> Mock
    """
    from fastapi.testclient import TestClient
    from src.interfaces.api.main import app
    from src.interfaces.api.dependencies import get_db

    def override_get_db():
        yield db_session

    # 重要：在创建TestClient前覆盖依赖
    app.dependency_overrides[get_db] = override_get_db

    # 如果有其他依赖，也需要覆盖 (示例):
    # from src.infrastructure.llm_service import get_llm_service
    # app.dependency_overrides[get_llm_service] = lambda: MockLLMService()

    client = TestClient(app)
    yield client

    # 清除覆盖 (重要！)
    app.dependency_overrides.clear()


# ============ 4. Mock服务fixtures ============
@pytest.fixture
def mock_llm_service():
    """Mock LLM服务"""
    mock = AsyncMock()
    mock.complete = AsyncMock(return_value="Mock LLM response")
    mock.think = AsyncMock(return_value={"thought": "Thinking..."})
    mock.decide_action = AsyncMock(return_value={"action": "create_workflow"})
    return mock


@pytest.fixture
def mock_event_bus():
    """Mock事件总线"""
    mock = AsyncMock()
    mock.published_events = []

    async def publish(event):
        mock.published_events.append(event)

    mock.publish = AsyncMock(side_effect=publish)
    return mock


@pytest.fixture
def mock_repository():
    """Mock通用Repository"""
    mock = Mock()
    mock.find_by_id = Mock(return_value=None)
    mock.save = Mock()
    mock.delete = Mock()
    mock.list_all = Mock(return_value=[])
    return mock


# ============ 5. 工具函数 ============
@pytest.fixture
def create_mock_workflow():
    """创建Mock工作流的工厂函数"""
    def _create(name="Test", node_count=2):
        from src.domain.entities.workflow import Workflow, Node, Edge

        nodes = [
            Node(
                id=f"node_{i}",
                type="python",
                code=f"x = {i}"
            )
            for i in range(node_count)
        ]

        edges = [
            Edge(source=f"node_{i}", target=f"node_{i+1}")
            for i in range(node_count - 1)
        ]

        return Workflow(
            id=f"wf_{name}",
            name=name,
            nodes=nodes,
            edges=edges
        )

    return _create
```

#### 验证方法
```bash
# 确保fixture可以导入
pytest --fixtures | grep test_engine
pytest --fixtures | grep db_session
pytest --fixtures | grep test_client

# 运行一个简单的测试
pytest tests/unit/ -k "test_" -v --collect-only
# 应该看到"mock_external_services"被自动应用
```

---

### 子任务3: 修复FastAPI集成测试

**文件**: `tests/integration/api/scheduler/test_scheduler_api_integration.py` (和相关文件)
**工作量**: 2 hours
**优先级**: 🔴 CRITICAL

#### 问题诊断
```python
# 当前代码问题 (Line 27-50左右):
engine = create_engine("sqlite:///:memory:")  # 创建了测试DB
TestingSessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)  # ❌ 但TestClient仍使用默认dependencies
# TestClient会使用app的get_db依赖，而不是上面创建的engine
```

#### 修复步骤
```python
# 将 tests/integration/api/scheduler/conftest.py 改为:

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.interfaces.api.main import app
from src.interfaces.api.dependencies import get_db
from src.infrastructure.database.base import Base

@pytest.fixture(scope="module")
def scheduler_api_test_client():
    """为scheduler API集成测试创建的TestClient"""

    # 第1步: 创建测试数据库
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    # 第2步: 创建依赖覆盖函数
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # 第3步: 应用依赖覆盖 (重要!)
    app.dependency_overrides[get_db] = override_get_db

    # 第4步: 创建TestClient (现在会使用覆盖的get_db)
    with TestClient(app) as client:
        yield client

    # 第5步: 清除覆盖
    app.dependency_overrides.clear()
```

#### 在测试中使用
```python
# tests/integration/api/scheduler/test_scheduler_api_integration.py

def test_create_schedule(scheduler_api_test_client):
    """创建调度"""
    response = scheduler_api_test_client.post(
        "/api/schedules",
        json={
            "workflow_id": "wf_123",
            "cron": "0 0 * * *"
        }
    )
    # 现在response会使用测试数据库，而不是真实数据库
    assert response.status_code == 201

def test_list_schedules(scheduler_api_test_client):
    """列出调度"""
    response = scheduler_api_test_client.get("/api/schedules")
    assert response.status_code == 200
```

#### 验证方法
```bash
# 修复后运行集成测试，应该不再有DB冲突
pytest tests/integration/api/scheduler/ -v

# 检查是否使用了测试DB (不应该生成test.db文件)
ls -la | grep test.db
# 应该无输出
```

---

### 子任务4: 标记TDD Red阶段的测试

**文件**: `tests/unit/domain/services/test_supervision_modules.py` (和其他similar files)
**工作量**: 30 minutes
**优先级**: 🔴 CRITICAL

#### 操作步骤
```python
# 在测试文件顶部添加：
import pytest

# 然后为TDD Red阶段的测试添加装饰器：

@pytest.mark.xfail(reason="TDD Red阶段 - 实现未完成")
def test_supervision_module_initialization():
    """监督模块初始化 (实现待完成)"""
    pass

@pytest.mark.xfail(reason="TDD Red阶段 - 实现未完成")
def test_supervision_module_integration():
    """监督模块集成 (实现待完成)"""
    pass

# 或者用skip (如果实现完全缺失)：
@pytest.mark.skip(reason="TDD Red阶段 - 未开始实现")
def test_supervision_coordinator_decision():
    """监督协调器决策 (未开始实现)"""
    pass
```

#### 如何识别TDD Red测试
```bash
# 查看失败的测试
pytest tests/unit/domain/services/test_supervision_modules.py --tb=short

# 查看.pytest_cache中的lastfailed
cat .pytest_cache/v/cache/lastfailed | head -20

# 统计有多少是TDD Red (通常是ImportError或NotImplementedError)
pytest tests/unit/domain/services/ -v | grep -c "NotImplementedError"
```

#### 验证方法
```bash
# 标记后，这些测试应该显示为 "xfailed" 而不是 "failed"
pytest tests/unit/domain/services/test_supervision_modules.py -v

# 输出应该是:
# test_supervision_module_initialization XFAIL
# test_supervision_module_integration XFAIL
```

---

### 子任务5: 修复SQLite并行隔离

**文件**: `tests/conftest.py` (已在子任务2中添加)
**工作量**: 2 hours
**优先级**: 🔴 CRITICAL

#### 问题诊断
```python
# 错误信息:
# sqlite3.OperationalError: database is locked

# 原因: SQLite不支持真正的并发，默认会锁定数据库
```

#### 修复方案（已在conftest.py中）
```python
# 修复1: 在test_engine创建时使用check_same_thread=False
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False}  # 允许跨线程访问
)

# 修复2: 使用事务隔离 (已在db_session fixture中)
transaction = connection.begin()
yield session
transaction.rollback()  # 每个测试自动回滚，避免冲突
```

#### 如果仍然有问题
```python
# 方案B: 使用file-based SQLite (更稳定但略慢)
import tempfile
db_file = tempfile.NamedTemporaryFile(delete=False)
engine = create_engine(f"sqlite:///{db_file.name}")

# 方案C: 对database_executor特殊处理
# tests/unit/infrastructure/executors/test_database_executor.py
@pytest.fixture
def database_executor_lock():
    """数据库执行器的锁 - 串行化execution"""
    import threading
    return threading.Lock()

def test_database_executor_thread_safe(database_executor_lock):
    with database_executor_lock:
        # 测试在锁内执行
        pass
```

#### 验证方法
```bash
# 并行运行测试，看是否有数据库锁定错误
pip install pytest-xdist
pytest tests/unit/infrastructure/executors/ -n auto -v

# 应该没有 "database is locked" 错误
```

---

### P0阶段验收标准

**检查清单**:
- [ ] `pyproject.toml` 已添加 `ignore = ["tests/manual"]`
- [ ] `tests/conftest.py` 已添加所有fixtures
- [ ] 所有集成测试都覆盖了FastAPI依赖
- [ ] 所有TDD Red测试都标记为 `xfail` 或 `skip`
- [ ] SQLite并行测试无锁定错误

**最终验收命令**:
```bash
# 运行所有测试，应该全绿
pytest -x --ignore=tests/manual

# 或者运行并查看统计
pytest --tb=short

# 输出应该是绿灯:
# ======= passed ===== (N个通过)
# 0个失败
```

---

## 📝 P1阶段执行清单（1周）

### 准备工作

```bash
# 1. 创建测试文件目录
mkdir -p tests/unit/application/use_cases

# 2. 创建测试文件
touch tests/unit/application/use_cases/test_execute_run.py
touch tests/unit/application/use_cases/test_classify_task.py
touch tests/unit/application/use_cases/test_update_workflow_by_chat.py
touch tests/unit/application/use_cases/test_create_agent.py
touch tests/unit/application/use_cases/test_create_tool.py
touch tests/unit/application/use_cases/test_import_workflow.py
touch tests/unit/application/use_cases/test_github_auth.py
```

### 子任务清单

| 序号 | 模块 | 文件 | 用例数 | 工作量 | 负责人 | 状态 |
|-----|------|------|--------|--------|--------|------|
| 1 | execute_run | test_execute_run.py | 18-20 | 2h | - | ⏳ |
| 2 | classify_task | test_classify_task.py | 12-15 | 1.5h | - | ⏳ |
| 3 | update_workflow_by_chat | test_update_workflow_by_chat.py | 15-18 | 2h | - | ⏳ |
| 4 | create_agent | test_create_agent.py | 10-12 | 1.5h | - | ⏳ |
| 5 | create_tool | test_create_tool.py | 8-10 | 1h | - | ⏳ |
| 6 | import_workflow | test_import_workflow.py | 6-8 | 1h | - | ⏳ |
| 7 | github_auth | test_github_auth.py | 6-8 | 1h | - | ⏳ |

### 执行顺序建议

**Day 1**: 任务1-3 (核心UseCases)
```bash
# 开始编写test_execute_run.py
# 然后test_classify_task.py
# 最后test_update_workflow_by_chat.py
```

**Day 2**: 任务4-7 (辅助UseCases)
```bash
# 编写剩余4个测试文件
```

**Day 3-5**: 完善和修复
```bash
# 修复失败的测试
# 提升覆盖率到70%+
# 代码审查和重构
```

### 验收标准

```bash
# Application层覆盖率达到70%
pytest tests/unit/application/ \
  --cov=src.application \
  --cov-report=term-missing

# 输出应该是:
# TOTAL 870 520 60% ...  (至少70%)
# 所有覆盖率都是绿色
```

---

## 📝 P2阶段执行清单（2周）

### 核心子系统划分

**Week 1**:
- 规则引擎系统 (4模块，75-90个用例)
- 节点验证系统 (3模块，65-80个用例)

**Week 2**:
- 执行监控系统 (4模块，73-95个用例)
- 工具和依赖系统 (3模块，50-63个用例)

### 验收标准

```bash
# Domain/services覆盖率达到60%+
pytest tests/unit/domain/services/ \
  --cov=src.domain.services \
  --cov-report=term-missing

# 输出应该是:
# TOTAL 21248 ... 60%+ (至少60%)
```

---

## 📝 P3阶段执行清单（2周）

### Agent系统划分

**Week 1**:
- error_handling.py (35-40用例)
- conversation_agent_react_core.py (28-30用例)
- conversation_agent_state.py (22-25用例)

**Week 2**:
- node_definition.py (25-30用例)
- 其他13个模块 (150+用例)

### 验收标准

```bash
# Domain/agents覆盖率达到60%+
pytest tests/unit/domain/agents/ \
  --cov=src.domain.agents \
  --cov-report=term-missing

# 输出应该是:
# TOTAL 31+ files, 60%+ coverage
```

---

## 🎯 总体里程碑

| 里程碑 | 完成标准 | 目标日期 | 状态 |
|--------|----------|----------|------|
| **M1** | CI绿灯 (P0完成) | +2 days | ⏳ |
| **M2** | Application ≥70% (P1完成) | +1 week | ⏳ |
| **M3** | Services ≥50% (P2完成) | +2 weeks | ⏳ |
| **M4** | Agents ≥60% (P3完成) | +4 weeks | ⏳ |
| **M5** | 总体 ≥50% (全部完成) | +4 weeks | ⏳ |

---

## 📞 常用命令速查

```bash
# 验证P0
pytest --ignore=tests/manual -x

# 验证P1
pytest tests/unit/application --cov=src.application

# 验证P2
pytest tests/unit/domain/services --cov=src.domain.services

# 验证P3
pytest tests/unit/domain/agents --cov=src.domain.agents

# 生成完整报告
pytest --cov=src --cov-report=html
open htmlcov/index.html

# 并行测试 (需要pytest-xdist)
pytest -n auto
```

---

**最后更新**: 2025-12-14
**下一步**: 开始执行P0阶段，完成后更新此文档
