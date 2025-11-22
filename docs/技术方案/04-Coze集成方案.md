# Coze集成方案

> **技术方案文档**
> 项目名称：Feagent
> 文档说明：本文档描述Feagent与Coze平台的深度集成策略

---

## 🎯 集成目标

### 核心定位
Feagent作为Coze的"粘合剂"和补充工具，提供：
1. **工作流本地化**：导入Coze工作流到本地执行
2. **工具互通**：调用Coze工具库，反向暴露Feagent能力
3. **体验增强**：表格引导、模板库、可视化优化
4. **生态打通**：打通Coze与本地/第三方服务

### 与Coze的关系
```
┌─────────────────────────────────────────────┐
│           用户工作流程                       │
├─────────────────────────────────────────────┤
│                                             │
│  1. 在Coze快速搭建原型工作流                 │
│         ↓                                   │
│  2. 导出JSON到Feagent本地部署               │
│         ↓                                   │
│  3. 在Feagent中调整、测试、执行             │
│         ↓                                   │
│  4. 调用Coze工具 ←→ 暴露Feagent能力         │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 📥 工作流导入功能

### Coze工作流JSON格式分析

#### 示例：Coze导出的工作流
```json
{
  "workflow_id": "coze_wf_123",
  "name": "每日GitHub Trending推送",
  "description": "抓取GitHub Trending并发送到钉钉",
  "nodes": [
    {
      "id": "node_1",
      "type": "http_request",
      "name": "获取Trending",
      "config": {
        "url": "https://api.github.com/trending",
        "method": "GET",
        "headers": {
          "Accept": "application/json"
        }
      }
    },
    {
      "id": "node_2",
      "type": "llm",
      "name": "格式化为Markdown",
      "config": {
        "model": "gpt-4",
        "prompt": "将以下JSON格式化为Markdown: {{node_1.output}}"
      }
    },
    {
      "id": "node_3",
      "type": "webhook",
      "name": "发送到钉钉",
      "config": {
        "url": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
        "method": "POST",
        "body": {
          "msgtype": "markdown",
          "markdown": {
            "title": "GitHub Trending",
            "text": "{{node_2.output}}"
          }
        }
      }
    }
  ],
  "edges": [
    {"from": "node_1", "to": "node_2"},
    {"from": "node_2", "to": "node_3"}
  ],
  "trigger": {
    "type": "schedule",
    "cron": "0 9 * * *"
  }
}
```

### Feagent的Workflow实体映射

#### Domain层：Workflow实体
```python
# src/domain/entities/workflow.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any

@dataclass
class WorkflowNode:
    """工作流节点"""
    id: str
    type: str  # http_request, llm, webhook, script, etc.
    name: str
    config: Dict[str, Any]
    position: Dict[str, float] | None = None  # 画布位置 {x, y}

@dataclass
class WorkflowEdge:
    """工作流边（连接）"""
    id: str
    source: str  # 源节点ID
    target: str  # 目标节点ID
    source_handle: str | None = None
    target_handle: str | None = None

@dataclass
class WorkflowTrigger:
    """工作流触发器"""
    type: str  # manual, schedule, webhook
    config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Workflow:
    """工作流聚合根"""
    id: str
    name: str
    description: str | None
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    trigger: WorkflowTrigger | None
    source: str = "feagent"  # feagent/coze/user
    source_id: str | None = None  # 原始来源ID（如Coze workflow_id）
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None

    @staticmethod
    def from_coze_json(coze_data: Dict[str, Any]) -> "Workflow":
        """从Coze JSON创建Workflow"""
        from src.domain.value_objects import generate_id

        # 转换节点
        nodes = [
            WorkflowNode(
                id=node["id"],
                type=node["type"],
                name=node.get("name", node["type"]),
                config=node.get("config", {})
            )
            for node in coze_data.get("nodes", [])
        ]

        # 转换边
        edges = [
            WorkflowEdge(
                id=generate_id(),
                source=edge["from"],
                target=edge["to"]
            )
            for edge in coze_data.get("edges", [])
        ]

        # 转换触发器
        trigger_data = coze_data.get("trigger")
        trigger = None
        if trigger_data:
            trigger = WorkflowTrigger(
                type=trigger_data["type"],
                config=trigger_data
            )

        return Workflow(
            id=generate_id(),
            name=coze_data.get("name", "未命名工作流"),
            description=coze_data.get("description"),
            nodes=nodes,
            edges=edges,
            trigger=trigger,
            source="coze",
            source_id=coze_data.get("workflow_id")
        )
```

### 导入用例实现

#### Application层：导入Coze工作流
```python
# src/application/use_cases/import_coze_workflow_use_case.py
from dataclasses import dataclass
from typing import Dict, Any
from src.domain.entities.workflow import Workflow
from src.domain.ports.workflow_repository import WorkflowRepository

@dataclass
class ImportCozeWorkflowInput:
    coze_json: Dict[str, Any]

class ImportCozeWorkflowUseCase:
    def __init__(self, workflow_repository: WorkflowRepository):
        self.workflow_repository = workflow_repository

    def execute(self, input_data: ImportCozeWorkflowInput) -> Workflow:
        # 1. 解析Coze JSON
        workflow = Workflow.from_coze_json(input_data.coze_json)

        # 2. 验证工作流完整性
        self._validate_workflow(workflow)

        # 3. 保存到数据库
        self.workflow_repository.save(workflow)

        return workflow

    def _validate_workflow(self, workflow: Workflow) -> None:
        """验证工作流完整性"""
        # 检查节点是否为空
        if not workflow.nodes:
            raise ValueError("工作流至少需要1个节点")

        # 检查边的引用是否有效
        node_ids = {node.id for node in workflow.nodes}
        for edge in workflow.edges:
            if edge.source not in node_ids:
                raise ValueError(f"边引用了不存在的源节点: {edge.source}")
            if edge.target not in node_ids:
                raise ValueError(f"边引用了不存在的目标节点: {edge.target}")

        # 检查是否有环（简单检测）
        # TODO: 完整的DAG环检测
```

### API端点

#### Interface层：导入API
```python
# src/interfaces/api/routes/workflows.py
from fastapi import APIRouter, Depends, UploadFile, File
from src.application.use_cases.import_coze_workflow_use_case import (
    ImportCozeWorkflowUseCase,
    ImportCozeWorkflowInput
)
from src.interfaces.api.dto.workflow_dto import WorkflowResponse

router = APIRouter()

@router.post("/import/coze", response_model=WorkflowResponse)
async def import_coze_workflow(
    file: UploadFile = File(...),
    workflow_repo = Depends(get_workflow_repository)
):
    """导入Coze工作流JSON文件"""
    import json

    # 读取上传的JSON文件
    content = await file.read()
    coze_json = json.loads(content)

    # 执行导入用例
    use_case = ImportCozeWorkflowUseCase(workflow_repository=workflow_repo)
    workflow = use_case.execute(ImportCozeWorkflowInput(coze_json=coze_json))

    return WorkflowResponse.from_entity(workflow)
```

---

## 🔌 节点类型对齐

### Coze vs Feagent 节点映射表

| Coze节点类型 | Feagent节点类型 | 映射说明 | 支持状态 |
|-------------|----------------|---------|---------|
| `http_request` | `HTTP` | 直接映射 | ✅ V1已支持 |
| `llm` | `LLM` | 直接映射 | ✅ V1已支持 |
| `webhook` | `HTTP` | method=POST | ✅ V1已支持 |
| `script` | `JAVASCRIPT` | 执行JS代码 | ✅ V1已支持 |
| `knowledge_base` | `LLM` | 使用RAG prompt | ⚠️ V3计划 |
| `workflow_call` | `SUBWORKFLOW` | 调用子工作流 | ⏳ V2计划 |
| `condition` | `CONDITION` | 条件分支 | ⏳ V2计划 |
| `loop` | `LOOP` | 循环节点 | ⏳ V3计划 |

### 节点配置转换逻辑

#### 示例：LLM节点转换
```python
# Coze LLM节点
coze_node = {
    "type": "llm",
    "config": {
        "model": "gpt-4",
        "prompt": "Translate to English: {{input}}",
        "temperature": 0.7
    }
}

# Feagent LLM节点
feagent_node = {
    "type": "LLM",
    "config": {
        "provider": "openai",  # 需要映射
        "model": "gpt-4",
        "messages": [
            {
                "role": "user",
                "content": "Translate to English: {{input}}"
            }
        ],
        "temperature": 0.7
    }
}
```

**转换函数**：
```python
def convert_llm_node(coze_config: Dict) -> Dict:
    """转换LLM节点配置"""
    # 推断provider
    model = coze_config.get("model", "gpt-4")
    if model.startswith("gpt"):
        provider = "openai"
    elif model.startswith("claude"):
        provider = "anthropic"
    else:
        provider = "openai"  # 默认

    # 转换prompt为messages格式
    prompt = coze_config.get("prompt", "")
    messages = [{"role": "user", "content": prompt}]

    return {
        "provider": provider,
        "model": model,
        "messages": messages,
        "temperature": coze_config.get("temperature", 0.7),
        "max_tokens": coze_config.get("max_tokens", 1000)
    }
```

---

## 🛠️ 工具互通（双向调用）

### 方向1：Feagent调用Coze工具

#### Coze工具API示例
```bash
# Coze提供的工具API
POST https://api.coze.com/v1/tools/invoke
Authorization: Bearer YOUR_COZE_API_KEY
Content-Type: application/json

{
  "tool_id": "coze_tool_web_search",
  "parameters": {
    "query": "AI Agent最新进展",
    "num_results": 5
  }
}
```

#### Feagent适配器实现
```python
# src/infrastructure/external/coze_client.py
import httpx
from typing import Dict, Any

class CozeClient:
    """Coze API客户端"""

    def __init__(self, api_key: str, base_url: str = "https://api.coze.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}
        )

    async def invoke_tool(
        self,
        tool_id: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """调用Coze工具"""
        response = await self.client.post(
            f"{self.base_url}/tools/invoke",
            json={
                "tool_id": tool_id,
                "parameters": parameters
            }
        )
        response.raise_for_status()
        return response.json()

    async def list_tools(self) -> list[Dict[str, Any]]:
        """列出可用工具"""
        response = await self.client.get(f"{self.base_url}/tools")
        response.raise_for_status()
        return response.json()["tools"]
```

#### 在Workflow中使用Coze工具
```python
# 工作流节点配置
{
    "type": "COZE_TOOL",
    "config": {
        "tool_id": "coze_tool_web_search",
        "parameters": {
            "query": "{{previous_node.output}}",
            "num_results": 5
        }
    }
}
```

### 方向2：Coze调用Feagent能力

#### 通过MCP暴露Feagent工具（V4）
```python
# src/infrastructure/mcp/feagent_mcp_server.py
from mcp import Server

server = Server("feagent")

@server.tool("create_workflow")
async def create_workflow(name: str, description: str) -> dict:
    """创建Feagent工作流"""
    # 调用Feagent内部UseCase
    workflow = await create_workflow_use_case.execute(...)
    return {"workflow_id": workflow.id, "status": "created"}

@server.tool("execute_workflow")
async def execute_workflow(workflow_id: str, input_data: dict) -> dict:
    """执行Feagent工作流"""
    run = await execute_workflow_use_case.execute(...)
    return {"run_id": run.id, "status": run.status}

# 启动MCP服务器
server.start(port=8080)
```

#### Coze中配置Feagent MCP
```json
{
  "mcp_servers": [
    {
      "name": "feagent",
      "url": "http://localhost:8080",
      "tools": [
        "create_workflow",
        "execute_workflow"
      ]
    }
  ]
}
```

---

## 🎨 前端可视化增强

### 导入Coze工作流后的画布渲染

#### 自动布局算法（Dagre）
```typescript
// web/src/features/workflows/utils/autoLayout.ts
import dagre from 'dagre';
import type { Node, Edge } from 'reactflow';

export function autoLayout(
  nodes: Node[],
  edges: Edge[]
): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'TB', nodesep: 100, ranksep: 150 });
  g.setDefaultEdgeLabel(() => ({}));

  // 添加节点
  nodes.forEach(node => {
    g.setNode(node.id, { width: 200, height: 80 });
  });

  // 添加边
  edges.forEach(edge => {
    g.setEdge(edge.source, edge.target);
  });

  // 计算布局
  dagre.layout(g);

  // 更新节点位置
  return nodes.map(node => {
    const position = g.node(node.id);
    return {
      ...node,
      position: {
        x: position.x - 100,
        y: position.y - 40
      }
    };
  });
}
```

#### 导入流程
```typescript
// web/src/features/workflows/pages/ImportCozeWorkflow.tsx
import { useState } from 'react';
import { Upload, message } from 'antd';
import { autoLayout } from '../utils/autoLayout';

export function ImportCozeWorkflow() {
  const handleUpload = async (file: File) => {
    // 1. 读取JSON
    const text = await file.text();
    const cozeData = JSON.parse(text);

    // 2. 调用API导入
    const response = await fetch('/api/workflows/import/coze', {
      method: 'POST',
      body: file
    });
    const workflow = await response.json();

    // 3. 转换为React Flow格式
    const nodes = workflow.nodes.map(node => ({
      id: node.id,
      type: node.type,
      data: { label: node.name, config: node.config },
      position: { x: 0, y: 0 }
    }));

    const edges = workflow.edges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target
    }));

    // 4. 自动布局
    const layoutedNodes = autoLayout(nodes, edges);

    // 5. 跳转到编辑器
    navigate(`/workflows/${workflow.id}/edit`, {
      state: { nodes: layoutedNodes, edges }
    });
  };

  return (
    <Upload.Dragger
      accept=".json"
      beforeUpload={handleUpload}
      showUploadList={false}
    >
      <p>拖拽Coze工作流JSON文件到此处</p>
    </Upload.Dragger>
  );
}
```

---

## 🔄 数据同步策略

### 单向同步：Coze → Feagent（当前）
```
Coze工作流 ──导出JSON──→ Feagent导入 ──本地执行
```
**优点**：简单、无依赖
**缺点**：修改后无法同步回Coze

### 双向同步：未来规划（V3+）
```
Coze ←──API同步──→ Feagent
```

#### 同步策略
1. **变更检测**：记录最后同步时间，检测修改
2. **冲突解决**：
   - 时间戳优先：最新修改胜出
   - 用户选择：提示用户手动解决冲突
3. **增量同步**：仅同步变更的节点/边

#### 数据模型扩展
```python
@dataclass
class Workflow:
    # ... 现有字段
    sync_status: str  # not_synced, synced, conflict
    last_synced_at: datetime | None
    coze_version: int | None  # Coze端版本号
```

---

## 📊 集成效果评估

### 成功指标
- **导入成功率**：>95%（Coze工作流正确导入）
- **节点兼容性**：核心节点100%支持（HTTP/LLM/Webhook）
- **执行一致性**：Coze vs Feagent结果一致性>90%
- **用户采用率**：30%用户使用Coze导入功能

### 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| Coze格式变更 | 导入失败 | 版本兼容层、降级策略 |
| 节点不兼容 | 部分功能缺失 | 提示用户、提供替代方案 |
| API限流 | 工具调用失败 | 本地缓存、重试机制 |

---

## 🗓️ 实施路线图

### Phase 1（V2）：基础导入
- [x] Workflow实体设计
- [ ] Coze JSON解析
- [ ] 导入API实现
- [ ] 前端上传与可视化

### Phase 2（V3）：工具互通
- [ ] Coze工具API调用
- [ ] Feagent能力暴露（MCP）
- [ ] 工具市场对接

### Phase 3（V4+）：双向同步
- [ ] 变更检测机制
- [ ] 冲突解决策略
- [ ] 增量同步实现

---

> **文档更新**：
> - Coze API变更时及时更新映射规则
> - 新增节点类型时补充兼容性说明
> - 集成效果定期回顾并调整策略
