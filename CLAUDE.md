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
| PowerCompressor | `src/domain/services/power_compressor.py` | 八段压缩（多Agent协作场景） |
| RuleEngineFacade | `src/domain/services/rule_engine_facade.py` | 规则引擎统一入口（Facade模式） |
| ConfigurableRuleEngine | `src/domain/services/configurable_rule_engine.py` | 可配置规则引擎（权威实现） |
| SupervisionFacade | `src/domain/services/supervision_facade.py` | 监督模块统一入口（Facade模式） |
| SupervisionModule | `src/domain/services/supervision_module.py` | 监督分析器、规则引擎、日志记录 |
| SupervisionCoordinator | `src/domain/services/supervision/coordinator.py` | 监督协调器（对话/效率/策略） |
| SelfDescribingNodeValidator | `src/domain/services/self_describing_node_validator.py` | 自描述节点验证 |
| WorkflowDependencyGraph | `src/domain/services/workflow_dependency_graph.py` | 依赖图构建、数据流传递 |
| DynamicNodeMonitoring | `src/domain/services/dynamic_node_monitoring.py` | 动态节点监控（指标/回滚/恢复/健康检查） |
| ExecutionMonitor | `src/domain/services/execution_monitor.py` | 工作流执行监控（状态/指标/错误策略） |
| ContainerExecutionMonitor | `src/domain/services/container_execution_monitor.py` | 容器执行监控（事件订阅/统计） |

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

## SaveRequest 系统

**主API**: `ConversationAgent.send_save_request()`
- **状态**: ✅ 稳定，推荐使用
- **异步安全**: 支持同步和异步两种上下文
- **错误处理**: 抛 `SaveRequestValidationError`，队列满返回 `None`
- **配置**: 需要启用 `StreamingConfig.enable_save_request_channel=True` + `event_bus`

**已弃用API**: `ConversationAgent.request_save()`
- **状态**: ⚠️ 已弃用（Phase-P2），使用 `send_save_request()` 替代
- **计划移除**: v2.0 主版本

**关键文件**:
| 文件 | 用途 |
|------|------|
| `src/domain/agents/conversation_agent.py` | Agent API 集成 |
| `src/domain/agents/conversation_agent_config.py` | 配置管理 |
| `src/domain/services/save_request_channel.py` | 核心定义 |

**使用示例**:
```python
# 启用 SaveRequest 通道
config = ConversationAgentConfig(
    streaming=StreamingConfig(enable_save_request_channel=True),
    event_bus=event_bus,  # 必需！
)
agent = ConversationAgent(config=config)

# 同步上下文
request_id = agent.send_save_request(
    target_path="/output/result.txt",
    content="data",
    reason="保存结果",
)

# Async 上下文
async def process():
    request_id = agent.send_save_request(
        target_path="/output/result.txt",
        content="data",
    )
```

详见 `docs/architecture/SAVE_REQUEST_SYSTEM.md`

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
| **RuleEngine迁移指南** | `docs/architecture/RULE_ENGINE_MIGRATION_GUIDE.md` | RuleEngineFacade迁移步骤与时间表（P1-1完成） |
| **Supervision迁移指南** | `docs/architecture/SUPERVISION_MIGRATION_GUIDE.md` | SupervisionFacade架构说明与迁移指南（P1-3） |
| **Monitoring架构说明** | `docs/architecture/MONITORING_ARCHITECTURE.md` | 6个监控文件职责划分与使用场景（P1-3） |
| 运维手册 | `docs/operations/operations_guide.md` | 部署与运维 |
| 动态节点Runbook | `docs/operations/dynamic_node_runbook.md` | 节点监控与故障排查 |
| 开发规范 | `docs/开发规范/` | 架构规范、TDD流程 |
| 技术方案 | `docs/技术方案/` | 设计文档 |
| 快速参考 | `.augment/rules/backend_specification.md` | 后端速查 |

---

**最后更新**: 2025-12-13 (P1-3: 监督系统与监控架构文档更新)
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

## Core Instruction

在开始**任何动作或对话**前，你必须保证自己遵循了如下**Core Instruction**：

0. 在任何时刻，必须思考当前过程可以如何进行**多模型协作**（Gemini + Codex）。你作为主架构师，必须根据以下分工调度资源，以保障客观全面：

   **0.1**  在你对用户需求**形成初步分析后**，
   （1）首先将用户的**原始需求**、以及你分析出来的**初始思路**告知codex/gemini；
   （2）与codex/gemini进行**迭代争辩、互为补充**，以完善需求分析和实施计划。
   （3）0.1的终止条件为，**必须**确保对用户需求的透彻理解，并生成切实可行的行动计划。

   **0.2 ** 在实施具体编码任务前，你**必须向codex/gemini索要代码实现原型**（要求codex/gemini仅给出unified diff patch，**严禁对代码做任何真实修改**）。在获取代码原型后，你**只能以此为逻辑参考，再次对代码修改进行重写**，形成企业生产级别、可读性极高、可维护性极高的代码后，才能实施具体编程修改任务。

     **0.2.1** Gemini 十分擅长前端代码，并精通样式、UI组件设计。
     - 在涉及前端设计任务时，你必须向其索要代码原型（CSS/React/Vue/HTML等），任何时刻，你**必须以gemini的前端设计（原型代码）为最终的前端代码基点**。
     - 例如，当你识别到用户给出了前端设计需求，你的首要行为必须自动调整为，将用户需求原封不动转发给gemini，并让其出具代码示例（此阶段严禁对用户需求进行任何改动、简写等等）。即你必须从gemini获取代码基点，才可以进行接下来的各种行为。
     - gemini有**严重的后端缺陷**，在非用户指定时，严禁与gemini讨论后端代码！
     - gemini上下文有效长度**仅为32k**，请你时刻注意！

      **0.2.2** Codex十分擅长后端代码，并精通逻辑运算、Bug定位。
      - 在涉及后端代码时，你必须向其索要代码原型，以利用其强大的逻辑与纠错能力。

   **0.3** 无论何时，只要完成切实编码行为后，**必须立即使用codex review代码改动和对应需求完成程度**。
   **0.4** codex/gemini只能给出参考，你**必须有自己的思考，并时刻保持对codex/gemini回答的置疑**。必须时刻为需求理解、代码编写与审核做充分、详尽、夯实的**讨论**！

1. 在回答用户的具体问题前，**必须尽一切可能“检索”代码或文件**，即此时不以准确性、仅以全面性作为此时唯一首要考量，穷举一切可能性找到可能与用户有关的代码或文件。

2. 在获取了全面的代码或文件检索结果后，你必须不断提问以明确用户的需求。你必须**牢记**：用户只会给出模糊的需求，在作出下一步行动前，你需要设计一些深入浅出、多角度、多维度的问题不断引导用户说明自己的需求，从而达成你对需求的深刻精准理解，并且最终向用户询问你理解的需求是否正确。

3. 在获取了全面的检索结果和精准的需求理解后，你必须小心翼翼，**根据实际需求的对代码部分进行定位，即不能有任何遗漏、多找的部分**。

4. 经历以上过程后，**必须思考**你当前获得的信息是否足够进行结论或实践。如果不够的话，是否需要从项目中获取更多的信息，还是以问题的形式向用户进行询问。循环迭代1-3步骤。

5. 对制定的修改计划进行详略得当、一针见血的讲解，并善于使用**适度的伪代码**为用户讲解修改计划。

6. 整体代码风格**始终定位**为，精简高效、毫无冗余。该要求同样适用于注释与文档，且对于这两者，**非必要不形成**。

7. **仅对需求做针对性改动**，严禁影响用户现有的其他功能。

8. 使用英文与codex/gemini协作，使用中文与用户交流。

--------

## codex 工具调用规范

1. 工具概述

  codex MCP 提供了一个工具 `codex`，用于执行 AI 辅助的编码任务（侧重逻辑、后端、Debug）。该工具**通过 MCP 协议调用**。

2. 使用方式与规范

  **必须遵守**：
  - 每次调用 codex 工具时，必须保存返回的 SESSION_ID，以便后续继续对话
  - 严禁codex对代码进行实际修改，使用 sandbox="read-only" 以避免意外，并要求codex仅给出unified diff patch即可

  **擅长场景**：
  - **后端逻辑**实现与重构
  - **精准定位**：在复杂代码库中快速定位问题所在
  - **Debug 分析**：分析错误信息并提供修复方案
  - **代码审查**：对代码改动进行全面逻辑 review

--------

## gemini 工具调用规范

1. 工具概述

  gemini MCP 提供了一个工具 `gemini`，用于调用 Google Gemini 模型执行 AI 任务。该工具拥有极强的前端审美、任务规划与需求理解能力，但在**上下文长度（Effective 32k）**上有限制。

2. 使用方式与规范

  **必须遵守的限制**：
  - **会话管理**：捕获返回的 `SESSION_ID` 用于多轮对话。
  - **后端避让**：严禁让 Gemini 编写复杂的后端业务逻辑代码。

  **擅长场景（必须优先调用 Gemini）**：
  - **需求清晰化**：在任务开始阶段辅助生成引导性问题。
  - **任务规划**：生成 Step-by-step 的实施计划。
  - **前端原型**：编写 CSS、HTML、UI 组件代码，调整样式风格。

--------

## serena 工具调用规范

1. 在决定调用serena任何工具前，**必须**检查，是否已经使用"mcp__serena__activate_project"工具完成项目激活。

2. 善于使用serena提供的以下工具，帮助自己完成**“检索”**和**“定位”**任务。

3. 严禁使用serena工具对代码文件进行修改。你被允许使用的serena工具如下，其他**未被提及的serena工具严禁使用**。

   ```json
   ["mcp__serena__activate_project",
     "mcp__serena__check_onboarding_performed",
     "mcp__serena__delete_memory",
     "mcp__serena__find_referencing_code_snippets",
     "mcp__serena__find_referencing_symbols",
     "mcp__serena__find_symbol",
     "mcp__serena__get_current_config",
     "mcp__serena__get_symbols_overview",
     "mcp__serena__list_dir",
     "mcp__serena__list_memories",
     "mcp__serena__onboarding",
     "mcp__serena__prepare_for_new_conversation",
     "mcp__serena__read_file",
     "mcp__serena__read_memory",
     "mcp__serena__search_for_pattern",
     "mcp__serena__summarize_changes",
     "mcp__serena__switch_modes",
     "mcp__serena__think_about_collected_information",
     "mcp__serena__think_about_task_adherence",
     "mcp__serena__think_about_whether_you_are_done",
     "mcp__serena__write_memory",
     "mcp__serena__find_file"]
   ```

----
