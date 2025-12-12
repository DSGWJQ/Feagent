# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目概述

**Feagent** 是企业级AI Agent编排与执行平台，基于 FastAPI + LangChain + DDD-lite 架构。

**当前阶段**: 多Agent协作系统（Phase 8+ - Unified Definition System）
- 三Agent架构：CoordinatorAgent、ConversationAgent、WorkflowAgent
- EventBus事件驱动通信
- 八段压缩器（PowerCompressor）
- WebSocket实时通道
- 可配置规则引擎与干预系统
- 自描述节点验证与依赖图

---

## Claude ↔ Codex 协作工作流（精简版）

1) 需求理解 → Claude 快速识别疑问 → Codex 深度推理  
2) 上下文收集 → Codex 全面检索 → 输出分析报告  
3) 任务规划 → Claude 基于分析制定计划  
4) 代码执行 → Claude 直接编码（遇复杂逻辑调用 Codex）  
5) 质量审查 → Codex 深度审查 → Claude 最终决策  

**角色分工 / 产出**  
- Claude：提炼问题、制定计划、落地代码与决策  
- Codex：深度推理/检索、给出代码原型（统一 diff 参考）、质量审查  
- 产出物：分析报告 → 计划 → 代码原型参考 → 落地实现 → Codex Review 意见 → Claude 采纳/决策

**与现有规则/架构的对齐**  
- 对应“架构顺序”：需求分析→Domain→Ports→Infrastructure→Application→Interface；在 Domain/Ports 阶段优先让 Codex 做深推与检索。  
- 代码执行阶段继续遵守“每次最多改 2 个文件 + TDD”与命名约定。  
- 前端/后端改动时保持原有项目结构；Codex 仅给出参考 patch，真实修改由 Claude 完成。  
- 关于 Codex 详细调用规范与合作要求，沿用文末《Core Instruction for CodeX MCP》与《Codex Tool Invocation Specification》。

---

## 关键规则（必读）

### 开发约束

1. **开发节奏**：每次最多修改2个文件，等待用户确认后继续

2. **TDD强制**：Red → Green → Refactor
   - Domain层覆盖率 ≥ 80%
   - Application层覆盖率 ≥ 70%

3. **架构顺序（严格）**：
   ```
   需求分析 → Domain → Ports → Infrastructure → Application → Interface
   ```

4. **依赖方向（单向）**：
   ```
   Interface → Application → Domain ← Infrastructure
   ```
   **Domain层禁止导入**: SQLAlchemy、FastAPI、LangChain 或任何框架

### 命名约定

| 模式 | 含义 | 示例 |
|------|------|------|
| `get_xxx` | 必须存在，否则抛异常 | `get_agent(id)` |
| `find_xxx` | 允许返回None | `find_agent(id)` |
| `XxxUseCase` | 应用层用例 | `CreateAgentUseCase` |
| `XxxInput/Request/Response` | DTO | `CreateAgentInput` |

---

## 开发命令

### 后端

```bash
# 安装依赖
pip install -e ".[dev]"

# 数据库迁移
alembic upgrade head
alembic revision --autogenerate -m "description"

# 启动服务器（Windows 必须使用 python -m）
python -m uvicorn src.interfaces.api.main:app --reload --port 8000

# 测试
pytest                                              # 全部测试
pytest tests/unit                                   # 单元测试
pytest tests/integration                            # 集成测试
pytest tests/unit/domain/entities/test_agent.py -v # 单个文件
pytest -k "test_create_agent"                       # 按名称

# 代码质量
ruff check .                             # Lint
ruff format .                            # Format
pyright src/                             # 类型检查
```

> **Windows 注意**：必须使用 `python -m uvicorn` 而非直接 `uvicorn`，以确保 watchfiles shim 正确加载，避免 Ctrl+C 信号问题。

### 前端

```bash
cd web
pnpm install
pnpm dev      # 开发服务器
pnpm build    # 构建
pnpm lint     # Lint
```

---

## 架构概览

### 四层架构

```
┌─────────────────────────────────────────────────┐
│              Interface Layer (接口层)            │
│  FastAPI Routes + DTO (Pydantic)                │
└────────────────────────┬────────────────────────┘
                         │
┌────────────────────────▼────────────────────────┐
│          Application Layer (应用层)              │
│  UseCases: 用例编排、事务边界                     │
└────────────────────────┬────────────────────────┘
                         │ Ports (Protocol)
┌────────────────────────▼────────────────────────┐
│            Domain Layer (领域层)                 │
│  Entities + Agents + Services                   │
│  ❌ 禁止导入任何框架                              │
└────────────────────────┬────────────────────────┘
                         │ Adapters
┌────────────────────────▼────────────────────────┐
│       Infrastructure Layer (基础设施层)          │
│  ORM + Repository + External Services           │
└─────────────────────────────────────────────────┘
```

### 多Agent协作架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户交互层                            │
│     对话面板 (Chat)  ◄──────►  工作流画布 (Canvas)           │
└───────────────────────────┬─────────────────────────────────┘
                            │ WebSocket
┌───────────────────────────▼─────────────────────────────────┐
│                      Agent 协作层                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              CoordinatorAgent (协调者)               │   │
│  │  规则引擎 │ 上下文服务 │ 压缩器服务 │ 子Agent调度    │   │
│  └─────────────────────────┬───────────────────────────┘   │
│                            │                                │
│     ┌──────────────────────┼──────────────────────┐        │
│     ▼                      ▼                      ▼        │
│  ConversationAgent     EventBus            WorkflowAgent   │
│  (意图分类/ReAct推理)  (事件总线)          (节点执行)       │
└─────────────────────────────────────────────────────────────┘
```

**核心组件位置**：
| 组件 | 路径 | 职责 |
|------|------|------|
| CoordinatorAgent | `src/domain/agents/coordinator_agent.py` | 规则验证、上下文管理、子Agent调度 |
| ConversationAgent | `src/domain/agents/conversation_agent.py` | 意图分类、ReAct推理、决策生成 |
| WorkflowAgent | `src/domain/agents/workflow_agent.py` | 节点执行、DAG拓扑排序、状态同步 |
| EventBus | `src/domain/services/event_bus.py` | 事件发布/订阅、中间件链 |
| PowerCompressor | `src/domain/services/power_compressor.py` | 八段压缩 |
| ConfigurableRuleEngine | `src/domain/services/configurable_rule_engine.py` | 可配置规则引擎 |
| SelfDescribingNodeValidator | `src/domain/services/self_describing_node_validator.py` | 自描述节点验证 |
| WorkflowDependencyGraph | `src/domain/services/workflow_dependency_graph.py` | 依赖图构建、数据流传递 |
| DynamicNodeMonitoring | `src/domain/services/dynamic_node_monitoring.py` | 监控指标、回滚、健康检查 |

---

## 目录结构

```
agent_data/
├── src/
│   ├── domain/                 # 领域层
│   │   ├── entities/          # 实体 (Agent, Run, Task, Workflow, Tool)
│   │   ├── agents/            # Agent系统
│   │   │   ├── coordinator_agent.py
│   │   │   ├── conversation_agent.py
│   │   │   ├── workflow_agent.py
│   │   │   └── agent_channel.py   # WebSocket通道
│   │   ├── services/          # 领域服务
│   │   │   ├── event_bus.py
│   │   │   ├── power_compressor.py
│   │   │   ├── configurable_rule_engine.py
│   │   │   ├── self_describing_node_validator.py
│   │   │   └── ...
│   │   ├── ports/             # 端口接口 (Protocol)
│   │   └── value_objects/     # 值对象
│   ├── application/           # 应用层
│   │   └── use_cases/         # 用例
│   ├── infrastructure/        # 基础设施层
│   │   ├── database/          # ORM + Repository
│   │   └── auth/              # 认证服务
│   ├── interfaces/            # 接口层
│   │   └── api/               # FastAPI路由 + DTO
│   └── lc/                    # LangChain集成
│       ├── chains/
│       ├── agents/
│       └── tools/
├── config/                    # 配置文件
│   └── save_rules.example.*   # 规则配置示例
├── definitions/               # 节点定义 (YAML规范)
│   ├── nodes/                 # 节点定义文件
│   └── schemas/               # JSON Schema校验
├── tests/
│   ├── unit/                  # 单元测试
│   ├── integration/           # 集成测试
│   │   └── regression/        # 回归测试套件
│   └── manual/                # 手动测试脚本
├── web/                       # 前端 (Vite + React)
└── docs/                      # 文档
```

---

## 节点定义系统

节点通过 YAML 定义，位于 `definitions/nodes/`：

```yaml
# definitions/nodes/http_node.yaml
metadata:
  name: http_request
  version: "1.0.0"
  category: integration

inputs:
  - name: url
    type: string
    required: true
  - name: method
    type: enum
    values: [GET, POST, PUT, DELETE]

outputs:
  - name: response
    type: object

execution:
  type: http
  timeout: 30000
```

校验脚本：`python -m scripts.validate_node_definitions`

---

## 开发模式示例

### 创建新功能流程

```python
# 1. Domain: 定义实体 (src/domain/entities/xxx.py)
@dataclass
class MyEntity:
    id: str
    name: str

    @staticmethod
    def create(name: str) -> "MyEntity":
        if not name:
            raise DomainError("name不能为空")
        return MyEntity(id=generate_id(), name=name)

# 2. Domain: 定义端口 (src/domain/ports/xxx_repository.py)
class MyEntityRepository(Protocol):
    def save(self, entity: MyEntity) -> None: ...
    def find_by_id(self, id: str) -> MyEntity | None: ...

# 3. Infrastructure: 实现Repository

# 4. Application: 创建UseCase
class CreateMyEntityUseCase:
    def __init__(self, repo: MyEntityRepository):
        self.repo = repo

    def execute(self, input: CreateMyEntityInput) -> MyEntity:
        entity = MyEntity.create(name=input.name)
        self.repo.save(entity)
        return entity

# 5. Interface: 添加API端点
```

### Agent协作模式

```python
# 初始化Agent系统
event_bus = EventBus()
coordinator = CoordinatorAgent(event_bus=event_bus)
conversation_agent = ConversationAgent(coordinator=coordinator, event_bus=event_bus)
workflow_agent = WorkflowAgent(event_bus=event_bus)

# 处理用户请求
async def handle_request(user_input: str, session_id: str):
    context = await coordinator.get_context_async(user_input=user_input)
    result = await conversation_agent.process_message(
        user_input=user_input,
        session_id=session_id,
        context=context
    )
    return result
```

---

## 环境变量

`.env` 文件配置：

```bash
DATABASE_URL=sqlite:///./agent_data.db
OPENAI_API_KEY=sk-...
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:5173"]
```

---

## 文档索引

| 文档 | 路径 | 用途 |
|------|------|------|
| 架构审计 | `docs/architecture/current_agents.md` | 三Agent系统最新架构审计 |
| 多Agent协作指南 | `docs/architecture/multi_agent_collaboration_guide.md` | 三Agent架构详解 |
| **RuleEngine迁移指南** | `docs/architecture/RULE_ENGINE_MIGRATION_GUIDE.md` | RuleEngineFacade迁移步骤与时间表 |
| 运维手册 | `docs/operations/operations_guide.md` | 部署与运维 |
| 动态节点Runbook | `docs/operations/dynamic_node_runbook.md` | 节点监控与故障排查 |
| 开发规范 | `docs/开发规范/` | 架构规范、TDD流程 |
| 技术方案 | `docs/技术方案/` | 设计文档 |
| 快速参考 | `.augment/rules/backend_specification.md` | 后端速查 |

---

**最后更新**: 2025-12-08
**项目阶段**: 多Agent协作系统 (Phase 8+ - Unified Definition System)

## Core Instruction for CodeX MCP

在任何时刻，你必须思考当前过程可以如何与codex进行协作，如何调用Codex 为你提供的MCP工具作为你客观全面分析的保障。
其中你**务必执行**以下几个步骤：
**1** 在你对用户需求形成初步分析后，将用户需求、初始思路告知codex，并要求其完善需求分析和实施计划。
**2** 在实施具体编码任务前，**必须向codex索要代码实现原型（要求codex仅给出unified diff patch，严禁对代码做任何真实修改）**。在获取代码原型后，你**只能以此为逻辑参考，再次对代码修改进行重写**，形成企业生产级别、可读性极高、可维护性极高的代码后，才能实施具体编程修改任务。
**3** 无论何时，只要完成切实编码行为后，**必须立即使用codex review代码改动和对应需求完成程度**。
**4** codex只能给出参考，你**必须有自己的思考，甚至需要对codex的回答提出置疑**。尽信书则不如无书，你与codex的最终使命都是达成统一、全面、精准的意见，所以你们必须不断争辩已找到通向真理的唯一途径。


## Codex Tool Invocation Specification

 1. 工具概述

  codex MCP 提供了一个工具 `codex`，用于执行 AI 辅助的编码任务。该工具**通过 MCP 协议调用**，无需使用命令行。

  2. 工具参数

  **必选**参数：
  - PROMPT (string): 发送给 codex 的任务指令
  - cd (Path): codex 执行任务的工作目录根路径

  可选参数：
  - sandbox (string): 沙箱策略，可选值：
    - "read-only" (默认): 只读模式，最安全
    - "workspace-write": 允许在工作区写入
    - "danger-full-access": 完全访问权限
  - SESSION_ID (UUID | null): 用于继续之前的会话以与codex进行多轮交互，默认为 None（开启新会话）
  - skip_git_repo_check (boolean): 是否允许在非 Git 仓库中运行，默认 False
  - return_all_messages (boolean): 是否返回所有消息（包括推理、工具调用等），默认 False

  返回值：
  {
    "success": true,
    "SESSION_ID": "uuid-string",
    "agent_messages": "agent回复的文本内容",
    "all_messages": []  // 仅当 return_all_messages=True 时包含
  }
  或失败时：
  {
    "success": false,
    "error": "错误信息"
  }

  3. 使用方式

  开启新对话：
  - 不传 SESSION_ID 参数（或传 None）
  - 工具会返回新的 SESSION_ID 用于后续对话

  继续之前的对话：
  - 将之前返回的 SESSION_ID 作为参数传入
  - 同一会话的上下文会被保留

  4. 调用规范

  **必须遵守**：
  - 每次调用 codex 工具时，必须保存返回的 SESSION_ID，以便后续继续对话
  - cd 参数必须指向存在的目录，否则工具会静默失败
  - 严禁codex对代码进行实际修改，使用 sandbox="read-only" 以避免意外，并要求codex仅给出unified diff patch即可

  推荐用法：
  - 如需详细追踪 codex 的推理过程和工具调用，设置 return_all_messages=True
  - 对于精准定位、debug、代码原型快速编写等任务，优先使用 codex 工具

  5. 注意事项

  - 会话管理：始终追踪 SESSION_ID，避免会话混乱
  - 工作目录：确保 cd 参数指向正确且存在的目录
  - 错误处理：检查返回值的 success 字段，处理可能的错误

