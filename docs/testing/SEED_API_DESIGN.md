# Seed API 设计方案（E2E 测试专用）

> 目标：为 Playwright E2E 测试提供确定性数据准备能力，支持快速创建预定义 workflow fixtures。

---

## 1. API 端点设计

### 1.1 创建测试 Workflow (Seed Workflow)

```http
POST /api/test/workflows/seed
```

**请求头**：
```
Content-Type: application/json
X-Test-Mode: true  # 必需，防止误用于生产环境
```

**请求体**：
```json
{
  "fixture_type": "main_subgraph_only" | "with_isolated_nodes" | "side_effect_workflow" | "invalid_config",
  "project_id": "e2e_project",  # 可选，默认为 "e2e_test_project"
  "custom_metadata": {  # 可选
    "test_case_id": "UX-WF-001",
    "description": "主子图用例"
  },
  "custom_nodes": [  # 可选：覆盖默认节点定义
    {
      "id": "node_1",
      "type": "HTTP",
      "config": {...}
    }
  ]
}
```

**响应体** (201 Created):
```json
{
  "workflow_id": "wf_seed_abc123",
  "project_id": "e2e_project",
  "fixture_type": "main_subgraph_only",
  "metadata": {
    "node_count": 3,
    "edge_count": 2,
    "has_isolated_nodes": false,
    "side_effect_nodes": []
  },
  "cleanup_token": "cleanup_xyz789"  # 用于清理
}
```

**错误响应**：
```json
// 400 Bad Request
{
  "code": "INVALID_FIXTURE_TYPE",
  "message": "Unknown fixture_type: unknown_type",
  "valid_types": ["main_subgraph_only", "with_isolated_nodes", ...]
}

// 403 Forbidden
{
  "code": "TEST_MODE_REQUIRED",
  "message": "Seed API requires X-Test-Mode header"
}
```

---

## 2. Fixture 类型定义

### 2.1 `main_subgraph_only` (P0 必需)
**用途**：测试正常的主连通子图执行流程
```python
Workflow:
  Nodes:
    - start (START)
    - process_data (PYTHON): 简单计算
    - end (END)
  Edges:
    - start → process_data
    - process_data → end
```

### 2.2 `with_isolated_nodes` (P1 必需)
**用途**：测试主子图约束防御（UX-WF-101）
```python
Workflow:
  Main Subgraph:
    - start → node_A → end
  Isolated Nodes:
    - isolated_node_1 (无入边)
    - isolated_node_2 (无出边)
  Isolated Edges:
    - orphan_edge (连接不存在的节点)
```

### 2.3 `side_effect_workflow` (P0 必需)
**用途**：测试副作用确认流程（UX-WF-004）
```python
Workflow:
  Nodes:
    - start
    - http_call (HTTP): URL=https://httpbin.org/post  # 触发 side effect
    - end
  Edges:
    - start → http_call → end

  副作用节点识别：
    - node.type in [HTTP, DATABASE, TOOL]
```

### 2.4 `invalid_config` (P1 必需)
**用途**：测试保存校验失败场景（UX-WF-102）
```python
Workflow:
  Nodes:
    - start
    - broken_node (PYTHON):
        code: None  # 缺少必填字段
        config: { "invalid_key": ... }
    - end
  预期：PATCH /workflows/{id} 返回 400 + 结构化错误
```

---

## 3. 后端实现方案

### 3.1 目录结构
```
src/
├── application/use_cases/
│   └── seed_test_workflow.py  # SeedTestWorkflowUseCase
├── interfaces/api/routes/
│   └── test_seeds.py  # Seed API 路由
├── domain/services/
│   └── workflow_fixtures.py  # Fixture 模板定义
└── tests/
    └── integration/api/
        └── test_seed_api.py  # Seed API 测试
```

### 3.2 UseCase 设计

```python
# src/application/use_cases/seed_test_workflow.py
from dataclasses import dataclass
from src.domain.entities.workflow import Workflow
from src.domain.ports.workflow_repository import WorkflowRepository


@dataclass
class SeedTestWorkflowInput:
    fixture_type: str
    project_id: str = "e2e_test_project"
    custom_metadata: dict | None = None
    custom_nodes: list[dict] | None = None


@dataclass
class SeedTestWorkflowOutput:
    workflow_id: str
    project_id: str
    fixture_type: str
    metadata: dict
    cleanup_token: str


class SeedTestWorkflowUseCase:
    """创建测试 Workflow 用例（仅测试环境）"""

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        fixture_factory: WorkflowFixtureFactory,
    ):
        self.workflow_repository = workflow_repository
        self.fixture_factory = fixture_factory

    def execute(self, input_data: SeedTestWorkflowInput) -> SeedTestWorkflowOutput:
        # 1. 根据 fixture_type 生成 workflow
        workflow = self.fixture_factory.create_fixture(
            fixture_type=input_data.fixture_type,
            project_id=input_data.project_id,
            custom_nodes=input_data.custom_nodes,
        )

        # 2. 添加测试元数据标记
        workflow.metadata = {
            **workflow.metadata,
            "test_seed": True,
            "fixture_type": input_data.fixture_type,
            **(input_data.custom_metadata or {}),
        }

        # 3. 持久化
        self.workflow_repository.save(workflow)

        # 4. 生成清理 token
        cleanup_token = f"cleanup_{workflow.id}"

        return SeedTestWorkflowOutput(
            workflow_id=workflow.id,
            project_id=workflow.project_id or input_data.project_id,
            fixture_type=input_data.fixture_type,
            metadata={
                "node_count": len(workflow.nodes),
                "edge_count": len(workflow.edges),
                "has_isolated_nodes": self._has_isolated_nodes(workflow),
                "side_effect_nodes": self._find_side_effect_nodes(workflow),
            },
            cleanup_token=cleanup_token,
        )
```

### 3.3 Fixture Factory 设计

```python
# src/domain/services/workflow_fixtures.py
from src.domain.entities.workflow import Workflow, Node, Edge
from src.domain.value_objects.node_type import NodeType


class WorkflowFixtureFactory:
    """Workflow Fixture 工厂（测试专用）"""

    FIXTURES: dict[str, Callable[[], Workflow]] = {}

    @classmethod
    def register(cls, fixture_type: str):
        """装饰器：注册 fixture 生成函数"""
        def decorator(func):
            cls.FIXTURES[fixture_type] = func
            return func
        return decorator

    def create_fixture(
        self,
        fixture_type: str,
        project_id: str,
        custom_nodes: list[dict] | None = None,
    ) -> Workflow:
        if fixture_type not in self.FIXTURES:
            raise ValueError(f"Unknown fixture_type: {fixture_type}")

        workflow = self.FIXTURES[fixture_type]()
        workflow.project_id = project_id

        # 可选：应用自定义节点覆盖
        if custom_nodes:
            self._apply_custom_nodes(workflow, custom_nodes)

        return workflow


@WorkflowFixtureFactory.register("main_subgraph_only")
def _create_main_subgraph() -> Workflow:
    workflow = Workflow.create(name="[TEST] Main Subgraph Only")

    start = Node.create(id="start", type=NodeType.START, name="Start")
    process = Node.create(
        id="process_data",
        type=NodeType.PYTHON,
        name="Process Data",
        config={"code": "result = {'output': input_data.get('value', 0) * 2}"},
    )
    end = Node.create(id="end", type=NodeType.END, name="End")

    workflow.add_node(start)
    workflow.add_node(process)
    workflow.add_node(end)

    workflow.add_edge(Edge.create(source_node_id="start", target_node_id="process_data"))
    workflow.add_edge(Edge.create(source_node_id="process_data", target_node_id="end"))

    return workflow


@WorkflowFixtureFactory.register("with_isolated_nodes")
def _create_with_isolated() -> Workflow:
    workflow = _create_main_subgraph()
    workflow.name = "[TEST] With Isolated Nodes"

    # 添加孤立节点（无入边/出边）
    isolated_1 = Node.create(
        id="isolated_no_in",
        type=NodeType.PYTHON,
        name="Isolated (No Incoming)",
    )
    isolated_2 = Node.create(
        id="isolated_no_out",
        type=NodeType.PYTHON,
        name="Isolated (No Outgoing)",
    )

    workflow.add_node(isolated_1)
    workflow.add_node(isolated_2)

    # 孤立边（目标节点不存在）
    # 注意：实际可能被校验拦截，需要特殊处理

    return workflow


@WorkflowFixtureFactory.register("side_effect_workflow")
def _create_side_effect() -> Workflow:
    workflow = Workflow.create(name="[TEST] Side Effect Workflow")

    start = Node.create(id="start", type=NodeType.START, name="Start")
    http_node = Node.create(
        id="http_call",
        type=NodeType.HTTP,  # 副作用类型
        name="HTTP Call",
        config={
            "url": "https://httpbin.org/post",
            "method": "POST",
            "body": {"test": True},
        },
    )
    end = Node.create(id="end", type=NodeType.END, name="End")

    workflow.add_node(start)
    workflow.add_node(http_node)
    workflow.add_node(end)

    workflow.add_edge(Edge.create(source_node_id="start", target_node_id="http_call"))
    workflow.add_edge(Edge.create(source_node_id="http_call", target_node_id="end"))

    return workflow


@WorkflowFixtureFactory.register("invalid_config")
def _create_invalid() -> Workflow:
    workflow = Workflow.create(name="[TEST] Invalid Config")

    start = Node.create(id="start", type=NodeType.START, name="Start")
    # 故意创建无效节点（缺少必填字段）
    broken = Node.create(
        id="broken_node",
        type=NodeType.PYTHON,
        name="Broken Node",
        config={"code": None},  # code 为空
    )
    end = Node.create(id="end", type=NodeType.END, name="End")

    workflow.add_node(start)
    workflow.add_node(broken)
    workflow.add_node(end)

    workflow.add_edge(Edge.create(source_node_id="start", target_node_id="broken_node"))
    workflow.add_edge(Edge.create(source_node_id="broken_node", target_node_id="end"))

    return workflow
```

### 3.4 路由实现

```python
# src/interfaces/api/routes/test_seeds.py
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel

router = APIRouter(prefix="/test", tags=["Test Seeds"])


class SeedWorkflowRequest(BaseModel):
    fixture_type: str
    project_id: str = "e2e_test_project"
    custom_metadata: dict | None = None
    custom_nodes: list[dict] | None = None


class SeedWorkflowResponse(BaseModel):
    workflow_id: str
    project_id: str
    fixture_type: str
    metadata: dict
    cleanup_token: str


@router.post("/workflows/seed", response_model=SeedWorkflowResponse)
def seed_test_workflow(
    request: SeedWorkflowRequest,
    x_test_mode: str | None = Header(None, alias="X-Test-Mode"),
    use_case: SeedTestWorkflowUseCase = Depends(get_seed_use_case),
) -> SeedWorkflowResponse:
    """创建测试 Workflow（仅测试环境）

    安全控制：
    - 必须携带 X-Test-Mode: true 请求头
    - 仅在测试/开发环境启用（生产环境 404）
    """
    # 1. 验证测试模式
    if x_test_mode != "true":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "TEST_MODE_REQUIRED",
                "message": "Seed API requires X-Test-Mode: true header",
            },
        )

    # 2. 执行用例
    try:
        output = use_case.execute(
            SeedTestWorkflowInput(
                fixture_type=request.fixture_type,
                project_id=request.project_id,
                custom_metadata=request.custom_metadata,
                custom_nodes=request.custom_nodes,
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_FIXTURE_TYPE",
                "message": str(e),
                "valid_types": list(WorkflowFixtureFactory.FIXTURES.keys()),
            },
        )

    return SeedWorkflowResponse(**output.__dict__)
```

---

## 4. 清理策略

### 4.1 自动清理端点

```http
DELETE /api/test/workflows/cleanup
```

**请求体**：
```json
{
  "cleanup_tokens": ["cleanup_xyz789", "cleanup_abc123"],
  "delete_by_metadata": {  # 可选：按元数据批量删除
    "test_seed": true,
    "fixture_type": "main_subgraph_only"
  }
}
```

**响应体** (200 OK):
```json
{
  "deleted_count": 2,
  "failed": []
}
```

### 4.2 Pytest Fixture 集成

```python
# tests/e2e/conftest.py
import pytest
import requests

@pytest.fixture(scope="function")
def seed_workflow(api_base_url):
    """创建测试 workflow 并自动清理"""
    workflows = []

    def _seed(fixture_type: str, **kwargs):
        resp = requests.post(
            f"{api_base_url}/test/workflows/seed",
            headers={"X-Test-Mode": "true"},
            json={"fixture_type": fixture_type, **kwargs},
        )
        resp.raise_for_status()
        data = resp.json()
        workflows.append(data["cleanup_token"])
        return data

    yield _seed

    # 清理
    if workflows:
        requests.delete(
            f"{api_base_url}/test/workflows/cleanup",
            headers={"X-Test-Mode": "true"},
            json={"cleanup_tokens": workflows},
        )


# 使用示例
def test_workflow_execution(seed_workflow):
    wf = seed_workflow("main_subgraph_only", project_id="e2e_project")
    workflow_id = wf["workflow_id"]

    # 执行测试...
    # cleanup 自动触发
```

---

## 5. 环境隔离

### 5.1 配置开关

```python
# src/config.py
class Settings(BaseSettings):
    # ... 其他配置 ...

    enable_test_seed_api: bool = Field(
        default=False,
        description="是否启用测试 Seed API（仅开发/测试环境）",
    )
```

### 5.2 路由注册控制

```python
# src/interfaces/api/main.py
def create_app() -> FastAPI:
    app = FastAPI()

    # ... 其他路由 ...

    # 仅在测试模式启用
    if settings.enable_test_seed_api:
        from src.interfaces.api.routes import test_seeds
        app.include_router(test_seeds.router, prefix="/api")

    return app
```

---

## 6. Playwright 使用示例

```typescript
// tests/e2e/fixtures/workflowFixtures.ts
import { test as base, expect } from '@playwright/test';

type WorkflowFixtures = {
  seedWorkflow: (fixtureType: string) => Promise<{
    workflow_id: string;
    project_id: string;
  }>;
};

export const test = base.extend<WorkflowFixtures>({
  seedWorkflow: async ({}, use) => {
    const cleanupTokens: string[] = [];

    const seed = async (fixtureType: string) => {
      const resp = await fetch('http://localhost:8000/api/test/workflows/seed', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Test-Mode': 'true',
        },
        body: JSON.stringify({
          fixture_type: fixtureType,
          project_id: 'e2e_project',
        }),
      });

      if (!resp.ok) throw new Error(`Seed failed: ${resp.statusText}`);

      const data = await resp.json();
      cleanupTokens.push(data.cleanup_token);
      return data;
    };

    await use(seed);

    // 清理
    if (cleanupTokens.length > 0) {
      await fetch('http://localhost:8000/api/test/workflows/cleanup', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', 'X-Test-Mode': 'true' },
        body: JSON.stringify({ cleanup_tokens: cleanupTokens }),
      });
    }
  },
});

// 使用示例
test('UX-WF-003: Run workflow with SSE', async ({ page, seedWorkflow }) => {
  const { workflow_id, project_id } = await seedWorkflow('main_subgraph_only');

  await page.goto(`/workflows/${workflow_id}/edit?projectId=${project_id}`);
  await page.getByTestId('run-button').click();

  await expect(page.getByTestId('workflow-status')).toContainText('completed');
});
```

---

## 7. 里程碑与交付

| 里程碑 | 任务 | 工作量 |
|---|---|---|
| M0 | 设计 Seed API 接口规范（本文档） | 0.5 天 |
| M1 | 实现 WorkflowFixtureFactory + 4 种 fixture | 1 天 |
| M2 | 实现 SeedTestWorkflowUseCase + API 路由 | 1 天 |
| M3 | 实现清理端点 + Pytest fixture 集成 | 0.5 天 |
| M4 | Playwright fixture 封装 + 示例用例 | 0.5 天 |

**总计**：3.5 天

---

## 8. 验收标准

- [ ] POST /api/test/workflows/seed 返回 201 + workflow_id
- [ ] 缺少 X-Test-Mode 返回 403
- [ ] 4 种 fixture_type 都能正确生成
- [ ] side_effect_workflow 执行时触发 workflow_confirm_required
- [ ] invalid_config 保存时返回 400 + 结构化错误
- [ ] DELETE /api/test/workflows/cleanup 成功删除测试数据
- [ ] Playwright 用例能通过 seedWorkflow fixture 创建并清理数据
