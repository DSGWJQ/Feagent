# 多Agent协作系统架构设计

> 版本: 1.0
> 创建日期: 2025-12-01
> 状态: 已确认，待实施

---

## 目录

1. [概述](#1-概述)
2. [系统整体架构](#2-系统整体架构)
3. [对话Agent设计](#3-对话agent设计)
4. [工作流Agent设计](#4-工作流agent设计)
5. [协调者Agent设计](#5-协调者agent设计)
6. [节点系统设计](#6-节点系统设计)
7. [上下文管理策略](#7-上下文管理策略)
8. [同步与一致性机制](#8-同步与一致性机制)
9. [分阶段实施计划](#9-分阶段实施计划)
10. [关键设计决策](#10-关键设计决策)
11. [附录](#11-附录)

---

## 1. 概述

### 1.1 设计背景

本系统的核心挑战是**工作流Agent和对话Agent的分工协作**：
- **对话Agent** 作为核心大脑，使用ReAct循环进行推理和决策
- **工作流Agent** 负责将对话Agent的想法可视化呈现到画布上
- **协调者Agent** 负责规则管理、流量监控和方向纠偏

### 1.2 核心设计理念

```
思考-执行分离 (Think-Execute Separation)

对话Agent (大脑)          工作流Agent (手脚)
     │                         │
     │    ┌─────────────┐      │
     └───►│ 协调者Agent │◄─────┘
          │   (裁判)    │
          └─────────────┘
```

### 1.3 设计原则

| 原则 | 说明 | 约束 |
|------|------|------|
| **单一职责** | 每个Agent只做一件事 | 对话=思考，工作流=执行，协调者=验证 |
| **单一数据源** | 工作流状态只有一个真相来源 | Event Bus 是唯一的状态修改入口 |
| **显式通信** | Agent间通过明确的消息格式通信 | 禁止隐式状态共享 |
| **可观测性** | 所有决策过程可追溯 | 每个决策必须有理由记录 |
| **渐进式降级** | 失败时有明确的回退策略 | 定义每个环节的fallback |
| **MVP优先** | 先跑通核心流程，再迭代优化 | 每个Phase都有可运行的交付物 |

---

## 2. 系统整体架构

### 2.1 架构总览

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           用户交互层 (User Interface)                       │
│  ┌──────────────────────────────┐    ┌──────────────────────────────────┐  │
│  │      对话面板 (Chat Panel)    │    │     工作流画布 (Workflow Canvas)  │  │
│  │  • 自然语言输入               │◄──►│  • 节点拖拽/连接                  │  │
│  │  • ReAct过程展示             │    │  • 实时执行可视化                 │  │
│  │  • 思考链透明化              │    │  • 父子节点展开/折叠              │  │
│  └──────────────────────────────┘    └──────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                          Agent协作层 (Agent Collaboration)                  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                     协调者 Agent (Coordinator)                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │  │
│  │  │ 规则引擎    │  │ 状态监控    │  │ 方向纠偏    │  │ 验证器     │  │  │
│  │  │ Rule Engine │  │ Monitor     │  │ Corrector   │  │ Validator  │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │  │
│  └────────────────────────────┬────────────────────────────────────────┘  │
│                               │                                            │
│         ┌─────────────────────┼─────────────────────┐                     │
│         │                     │                     │                     │
│         ▼                     ▼                     ▼                     │
│  ┌─────────────────┐   ┌─────────────┐   ┌─────────────────────┐         │
│  │  对话 Agent     │   │  事件总线   │   │  工作流 Agent        │         │
│  │  (Conversation) │◄─►│  Event Bus  │◄─►│  (Workflow)         │         │
│  │                 │   │             │   │                     │         │
│  │  • ReAct循环    │   │  • 状态同步  │   │  • 节点执行          │         │
│  │  • 目标分解     │   │  • 事件广播  │   │  • 画布渲染          │         │
│  │  • 决策生成     │   │  • 冲突仲裁  │   │  • 动态创建          │         │
│  └─────────────────┘   └─────────────┘   └─────────────────────┘         │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           基础设施层 (Infrastructure)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ 上下文管理器  │  │ 节点注册中心 │  │ 执行引擎     │  │ 持久化存储   │   │
│  │ ContextMgr   │  │ NodeRegistry │  │ Executor     │  │ Storage      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
用户输入
    │
    ▼
对话Agent ──► 决策(Decision) ──► 协调者验证 ──► 工作流Agent
    │                                 │              │
    │                                 │              ▼
    │                                 │         执行结果
    │                                 │              │
    ◄────────────── 摘要后的反馈 ◄─────┴──────────────┘
```

### 2.3 目录结构规划

```
src/
├── domain/
│   ├── entities/
│   │   ├── decision.py          # 决策实体
│   │   ├── goal.py              # 目标实体
│   │   ├── context.py           # 上下文实体
│   │   ├── rule.py              # 规则实体
│   │   └── nodes/               # 节点类型定义
│   │       ├── base.py
│   │       ├── control_flow.py  # 条件/循环/并行
│   │       ├── ai_nodes.py      # LLM/知识库/分类
│   │       ├── execution.py     # API/Code/MCP
│   │       └── generic.py       # 通用节点
│   ├── events/
│   │   ├── base.py              # 基础事件
│   │   ├── decision_events.py   # 决策相关事件
│   │   ├── workflow_events.py   # 工作流相关事件
│   │   └── canvas_events.py     # 画布同步事件
│   ├── services/
│   │   ├── event_bus.py         # 事件总线
│   │   ├── context_manager.py   # 上下文管理
│   │   ├── node_registry.py     # 节点注册中心
│   │   ├── react_loop.py        # ReAct循环
│   │   ├── goal_manager.py      # 目标管理
│   │   ├── node_factory.py      # 节点工厂
│   │   ├── execution_engine.py  # 执行引擎
│   │   ├── rule_engine.py       # 规则引擎
│   │   ├── validators.py        # 验证器
│   │   ├── alignment_checker.py # 目标对齐检查
│   │   ├── state_synchronizer.py # 状态同步
│   │   └── executors/           # 节点执行器
│   │       ├── llm_executor.py
│   │       ├── api_executor.py
│   │       ├── code_executor.py
│   │       └── ...
│   └── ports/
│       ├── event_store.py       # 事件存储端口
│       └── context_store.py     # 上下文存储端口
├── application/
│   └── agents/
│       ├── conversation_agent.py  # 对话Agent
│       ├── workflow_agent.py      # 工作流Agent
│       └── coordinator_agent.py   # 协调者Agent
└── infrastructure/
    ├── websocket/
    │   └── canvas_sync.py       # 画布WebSocket同步
    └── persistence/
        ├── event_store_impl.py
        └── context_store_impl.py
```

---

## 3. 对话Agent设计

### 3.1 核心职责

对话Agent是系统的**"大脑"**，负责：
- 理解用户意图
- 通过ReAct循环进行推理
- 将全局目标分解为子目标
- 生成结构化决策供工作流Agent执行

### 3.2 ReAct循环设计

```
┌─────────────────────────────────────────────────────────────────┐
│                     ReAct 循环 (核心推理引擎)                    │
│                                                                 │
│   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐  │
│   │ Thought │ ──► │ Action  │ ──► │Observa- │ ──► │ Reflect │  │
│   │  思考   │     │  行动   │     │  tion   │     │  反思   │  │
│   │         │     │         │     │  观察   │     │         │  │
│   └─────────┘     └─────────┘     └─────────┘     └────┬────┘  │
│        ▲                                               │       │
│        │                                               │       │
│        └───────────────────────────────────────────────┘       │
│                          循环继续或终止                          │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 核心数据结构

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class DecisionType(Enum):
    """决策类型"""
    CREATE_NODE = "create_node"       # 请求创建节点
    MODIFY_NODE = "modify_node"       # 请求修改节点
    CONNECT_NODES = "connect_nodes"   # 请求连接节点
    EXECUTE_WORKFLOW = "execute"      # 请求执行工作流
    QUERY_STATE = "query_state"       # 查询当前状态
    DELEGATE = "delegate"             # 委托给子工作流
    TERMINATE = "terminate"           # 终止当前任务


@dataclass
class ThoughtStep:
    """思考链的单个步骤"""
    step_number: int
    thought: str           # 当前思考
    action: Optional[str]  # 采取的行动
    observation: Optional[str]  # 观察到的结果
    reflection: Optional[str]   # 反思


@dataclass
class Decision:
    """对话Agent的决策输出"""
    id: str
    timestamp: datetime

    # 思考过程（透明化）
    thought_chain: List[ThoughtStep]

    # 决策类型和内容
    type: DecisionType
    payload: Dict[str, Any]

    # 置信度和推理依据
    confidence: float  # 0.0 - 1.0
    reasoning: str

    # 关联的子目标
    sub_goal_id: Optional[str] = None


@dataclass
class Goal:
    """目标实体"""
    id: str
    description: str
    status: str  # pending | in_progress | completed | failed

    parent_id: Optional[str] = None  # 父目标
    children_ids: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

    # 完成条件
    success_criteria: List[str] = field(default_factory=list)

    # 关联的工作流
    workflow_id: Optional[str] = None
```

### 3.4 ReAct循环实现

```python
@dataclass
class ReActConfig:
    """ReAct循环配置"""
    max_iterations: int = 10          # 最大迭代次数
    max_thinking_time: float = 60.0   # 最大思考时间(秒)
    max_token_budget: int = 10000     # 最大token预算
    confidence_threshold: float = 0.7  # 置信度阈值
    early_stop_on_repeat: bool = True  # 检测到重复思考时停止


class CircuitBreaker:
    """熔断器 - 防止无限循环"""

    def __init__(self, config: ReActConfig):
        self.config = config
        self.iteration_count = 0
        self.start_time: Optional[float] = None
        self.token_used = 0
        self.thought_history: List[str] = []

    def start(self):
        """开始计时"""
        self.start_time = time.time()
        self.iteration_count = 0
        self.token_used = 0
        self.thought_history = []

    def tick(self, thought: str, tokens: int) -> None:
        """记录一次迭代"""
        self.iteration_count += 1
        self.token_used += tokens
        self.thought_history.append(thought)

    def should_break(self) -> tuple[bool, str]:
        """检查是否应该终止"""
        if self.iteration_count >= self.config.max_iterations:
            return True, "达到最大迭代次数"

        if time.time() - self.start_time > self.config.max_thinking_time:
            return True, "超过最大思考时间"

        if self.token_used >= self.config.max_token_budget:
            return True, "超过token预算"

        if self._detect_loop():
            return True, "检测到思考循环"

        return False, ""

    def _detect_loop(self) -> bool:
        """检测是否陷入循环"""
        if len(self.thought_history) < 3:
            return False
        # 简单的重复检测
        recent = self.thought_history[-3:]
        return len(set(recent)) == 1


class ReActLoop:
    """ReAct推理循环"""

    def __init__(
        self,
        llm_client: Any,
        config: ReActConfig = None
    ):
        self.llm = llm_client
        self.config = config or ReActConfig()
        self.circuit_breaker = CircuitBreaker(self.config)

    async def run(
        self,
        goal: Goal,
        context: 'SessionContext'
    ) -> Decision:
        """执行ReAct循环"""
        self.circuit_breaker.start()
        thought_chain: List[ThoughtStep] = []
        step_number = 0

        while True:
            # 检查熔断
            should_break, reason = self.circuit_breaker.should_break()
            if should_break:
                return self._create_termination_decision(
                    thought_chain, reason
                )

            # 1. Thought - 思考
            thought = await self._think(goal, context, thought_chain)

            # 2. Action - 决定行动
            action = await self._decide_action(thought, goal, context)

            # 3. 如果是最终决策，返回
            if action.is_final:
                return self._create_decision(
                    thought_chain, action, goal
                )

            # 4. Observation - 执行并观察
            observation = await self._execute_and_observe(action)

            # 5. Reflect - 反思
            reflection = await self._reflect(
                thought, action, observation, goal
            )

            # 记录步骤
            step_number += 1
            thought_chain.append(ThoughtStep(
                step_number=step_number,
                thought=thought,
                action=action.description,
                observation=observation,
                reflection=reflection
            ))

            # 更新熔断器
            self.circuit_breaker.tick(
                thought,
                self._estimate_tokens(thought)
            )
```

### 3.5 目标分解

```python
class GoalDecomposer:
    """目标分解器"""

    def __init__(self, llm_client: Any):
        self.llm = llm_client

    async def decompose(self, global_goal: Goal) -> List[Goal]:
        """将全局目标分解为子目标"""
        # MVP: 使用LLM进行分解
        prompt = f"""
        请将以下目标分解为可执行的子目标：

        目标: {global_goal.description}

        要求:
        1. 每个子目标应该是独立可执行的
        2. 明确子目标之间的依赖关系
        3. 子目标数量控制在3-7个

        输出格式 (JSON):
        {{
            "sub_goals": [
                {{
                    "description": "子目标描述",
                    "dependencies": ["依赖的子目标索引"],
                    "success_criteria": ["完成标准"]
                }}
            ]
        }}
        """

        response = await self.llm.generate(prompt)
        sub_goals_data = json.loads(response)

        # 创建子目标实体
        sub_goals = []
        for i, data in enumerate(sub_goals_data["sub_goals"]):
            sub_goal = Goal(
                id=f"{global_goal.id}_sub_{i}",
                description=data["description"],
                status="pending",
                parent_id=global_goal.id,
                success_criteria=data.get("success_criteria", [])
            )
            sub_goals.append(sub_goal)

        # 建立依赖关系
        for i, data in enumerate(sub_goals_data["sub_goals"]):
            for dep_idx in data.get("dependencies", []):
                if dep_idx < len(sub_goals):
                    sub_goals[i].dependencies.append(
                        sub_goals[dep_idx].id
                    )

        return sub_goals
```

---

## 4. 工作流Agent设计

### 4.1 核心职责

工作流Agent是系统的**"执行者"**，负责：
- 将对话Agent的决策转化为可视化节点
- 管理画布上的节点生命周期
- 执行工作流并返回结果
- 提供实时执行状态可视化

### 4.2 架构设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         工作流 Agent (Workflow Agent)                    │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    决策解释器 (Decision Interpreter)               │  │
│  │    Decision ──► 解析 ──► NodeOperation / EdgeOperation            │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    工作流管理器 (Workflow Manager)                  │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │  │
│  │  │ 节点工厂    │  │ 边管理器    │  │ 布局引擎 (自动布局)      │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    执行引擎 (Execution Engine)                     │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐   │  │
│  │  │ 调度器      │  │ 执行器池    │  │ 状态追踪器              │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    画布同步器 (Canvas Synchronizer)                │  │
│  │    内部状态 ──► Diff计算 ──► 最小化更新 ──► 前端画布                │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 节点工厂

```python
class NodeFactory:
    """节点工厂 - 负责动态创建节点"""

    def __init__(self, node_registry: 'NodeRegistry'):
        self.registry = node_registry

    def create_from_decision(self, decision: Decision) -> 'WorkflowNode':
        """根据决策创建节点"""
        payload = decision.payload

        # 1. 确定节点类型
        node_type = NodeType(payload.get("node_type"))

        # 2. 获取节点模板
        template = self.registry.get_template(node_type)

        # 3. 填充节点配置
        config = self._fill_config(template, payload)

        # 4. 创建节点实例
        node = WorkflowNode(
            id=str(uuid.uuid4()),
            type=node_type,
            config=config,
            lifecycle=NodeLifecycle.TEMPORARY,
            created_by="conversation_agent",
            created_at=datetime.now(),
        )

        return node

    def _fill_config(
        self,
        template: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """填充节点配置"""
        config = template.copy()

        # 用payload中的值覆盖模板默认值
        for key, value in payload.items():
            if key in config:
                config[key] = value

        return config
```

### 4.4 执行引擎

```python
class ExecutionEngine:
    """工作流执行引擎"""

    def __init__(self, executor_registry: Dict[NodeType, 'NodeExecutor']):
        self.executors = executor_registry

    async def execute(
        self,
        workflow: 'Workflow',
        context: 'WorkflowContext'
    ) -> 'ExecutionResult':
        """执行工作流"""

        # 1. 构建执行计划（拓扑排序）
        execution_order = self._topological_sort(workflow)

        # 2. 按顺序执行节点
        for node_id in execution_order:
            node = workflow.get_node(node_id)

            # 获取节点输入
            inputs = self._gather_inputs(node, workflow, context)

            # 执行节点
            try:
                executor = self.executors[node.type]
                result = await executor.execute(node, inputs, context)

                # 保存输出
                context.set_node_output(node_id, result.outputs)

                # 发布执行完成事件
                await self._emit_event(NodeExecutionCompletedEvent(
                    node_id=node_id,
                    outputs=result.outputs
                ))

            except Exception as e:
                await self._emit_event(NodeExecutionFailedEvent(
                    node_id=node_id,
                    error=str(e)
                ))
                return ExecutionResult(
                    status="failed",
                    error=str(e)
                )

        return ExecutionResult(
            status="success",
            outputs=context.collect_final_outputs()
        )

    def _topological_sort(self, workflow: 'Workflow') -> List[str]:
        """拓扑排序确定执行顺序"""
        # 实现Kahn算法
        in_degree = {n.id: 0 for n in workflow.nodes}
        for edge in workflow.edges:
            in_degree[edge.target_id] += 1

        queue = [n.id for n.id, d in in_degree.items() if d == 0]
        result = []

        while queue:
            node_id = queue.pop(0)
            result.append(node_id)

            for edge in workflow.edges:
                if edge.source_id == node_id:
                    in_degree[edge.target_id] -= 1
                    if in_degree[edge.target_id] == 0:
                        queue.append(edge.target_id)

        return result
```

### 4.5 画布同步

```python
class CanvasSynchronizer:
    """画布同步器"""

    def __init__(self, websocket_manager: Any):
        self.ws_manager = websocket_manager
        self.last_state: Optional[Dict] = None

    async def sync(self, workflow: 'Workflow'):
        """同步工作流状态到前端画布"""
        new_state = self._workflow_to_canvas_state(workflow)

        if self.last_state is None:
            # 首次同步，发送完整状态
            await self._send_full_state(new_state)
        else:
            # 增量同步
            diff = self._calculate_diff(self.last_state, new_state)
            if diff:
                await self._send_diff(diff)

        self.last_state = new_state

    def _workflow_to_canvas_state(self, workflow: 'Workflow') -> Dict:
        """转换为画布状态"""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type.value,
                    "position": n.position,
                    "data": n.config
                }
                for n in workflow.nodes
            ],
            "edges": [
                {
                    "id": e.id,
                    "source": e.source_id,
                    "target": e.target_id
                }
                for e in workflow.edges
            ]
        }
```

---

## 5. 协调者Agent设计

### 5.1 核心职责

协调者Agent是系统的**"裁判"**，负责：
- 规则管理：维护和执行系统规则
- 流量监控：监控Agent间的通信和资源使用
- 方向纠偏：确保对话Agent不偏离目标
- 状态验证：验证决策的合法性和一致性

### 5.2 架构设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        协调者 Agent (Coordinator Agent)                      │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                       规则引擎 (Rule Engine)                           │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐       │  │
│  │  │ 静态规则        │  │ 动态规则        │  │ 学习规则 (V2)   │       │  │
│  │  │ (配置文件)      │  │ (运行时生成)    │  │ (从历史学习)    │       │  │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │ 决策验证器      │    │ 目标对齐检查器  │    │ 资源监控器      │        │
│  │ • 格式验证      │    │ • 目标偏离检测  │    │ • Token计数     │        │
│  │ • 权限验证      │    │ • 进度评估      │    │ • 时间追踪      │        │
│  │ • 一致性验证    │    │ • 纠偏建议      │    │ • 成本统计      │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│                                    │                                        │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    干预策略 (Intervention Strategy)                    │  │
│  │   轻度: 警告日志 ──► 中度: 建议修正 ──► 重度: 强制终止                 │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 规则引擎

```python
class RuleType(Enum):
    STATIC = "static"      # 静态规则（配置文件）
    DYNAMIC = "dynamic"    # 动态规则（运行时生成）


class RuleAction(Enum):
    LOG_WARNING = "log_warning"
    SUGGEST_CORRECTION = "suggest"
    REJECT_DECISION = "reject"
    FORCE_TERMINATE = "terminate"


@dataclass
class Rule:
    """规则定义"""
    id: str
    name: str
    description: str
    type: RuleType
    priority: int  # 越小优先级越高
    condition: str  # 条件表达式
    action: RuleAction
    enabled: bool = True


class RuleEngine:
    """规则引擎"""

    def __init__(self):
        self.rules: List[Rule] = []

    def load_rules(self, config_path: str):
        """从配置文件加载规则"""
        with open(config_path) as f:
            rules_data = yaml.safe_load(f)

        for r in rules_data.get("rules", []):
            self.rules.append(Rule(**r))

        # 按优先级排序
        self.rules.sort(key=lambda r: r.priority)

    def evaluate(self, context: Dict[str, Any]) -> List['RuleViolation']:
        """评估所有规则"""
        violations = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            if self._check_condition(rule.condition, context):
                violations.append(RuleViolation(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    action=rule.action,
                    context=context
                ))

        return violations

    def _check_condition(self, condition: str, context: Dict) -> bool:
        """检查条件是否满足"""
        # MVP: 简单的表达式评估
        try:
            return eval(condition, {"__builtins__": {}}, context)
        except:
            return False
```

### 5.4 规则配置示例

```yaml
# config/rules/default_rules.yaml
rules:
  - id: "max_iterations"
    name: "最大迭代次数限制"
    description: "防止ReAct循环过多迭代"
    type: "static"
    priority: 1
    condition: "iteration_count > 10"
    action: "force_terminate"
    enabled: true

  - id: "token_budget"
    name: "Token预算限制"
    description: "防止单次任务消耗过多token"
    type: "static"
    priority: 1
    condition: "token_used > 10000"
    action: "force_terminate"
    enabled: true

  - id: "goal_deviation"
    name: "目标偏离检测"
    description: "检测对话Agent是否偏离目标"
    type: "static"
    priority: 2
    condition: "alignment_score < 0.5"
    action: "suggest"
    enabled: true

  - id: "low_confidence"
    name: "低置信度警告"
    description: "决策置信度过低时警告"
    type: "static"
    priority: 3
    condition: "decision_confidence < 0.5"
    action: "log_warning"
    enabled: true
```

### 5.5 目标对齐检查器

```python
class GoalAlignmentChecker:
    """目标对齐检查器"""

    def __init__(self, llm_client: Any):
        self.llm = llm_client

    async def check_alignment(
        self,
        goal: Goal,
        decision: Decision,
        history: List[Dict]
    ) -> 'AlignmentResult':
        """检查决策是否与目标对齐"""

        # MVP: 使用LLM进行语义对齐检查
        prompt = f"""
        请评估以下决策是否与目标对齐：

        目标: {goal.description}
        决策: {decision.reasoning}

        历史执行记录:
        {self._format_history(history[-5:])}  # 最近5条

        请给出对齐程度评分(0-1)和简要分析。

        输出格式 (JSON):
        {{
            "score": 0.8,
            "is_aligned": true,
            "analysis": "分析说明",
            "suggestion": "如果不对齐，给出建议"
        }}
        """

        response = await self.llm.generate(prompt)
        result = json.loads(response)

        return AlignmentResult(
            score=result["score"],
            is_aligned=result["is_aligned"],
            analysis=result["analysis"],
            suggestion=result.get("suggestion")
        )
```

### 5.6 干预策略

```python
class InterventionLevel(Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InterventionAction(Enum):
    PASS = "pass"
    WARN_AND_CONTINUE = "warn"
    SUGGEST_CORRECTION = "suggest"
    REJECT_AND_SUGGEST = "reject"
    FORCE_TERMINATE = "terminate"


@dataclass
class Intervention:
    level: InterventionLevel
    action: InterventionAction
    reason: str
    suggestion: Optional[str] = None


class InterventionStrategy:
    """干预策略"""

    def decide(
        self,
        rule_violations: List['RuleViolation'],
        alignment_result: 'AlignmentResult',
        resource_status: Dict
    ) -> Intervention:
        """决定干预级别和动作"""

        # 计算严重程度
        severity = self._calculate_severity(
            rule_violations,
            alignment_result,
            resource_status
        )

        if severity >= 0.9:
            return Intervention(
                level=InterventionLevel.CRITICAL,
                action=InterventionAction.FORCE_TERMINATE,
                reason="严重违规或资源耗尽"
            )
        elif severity >= 0.7:
            return Intervention(
                level=InterventionLevel.HIGH,
                action=InterventionAction.REJECT_AND_SUGGEST,
                reason="决策偏离目标，需要修正",
                suggestion=alignment_result.suggestion
            )
        elif severity >= 0.4:
            return Intervention(
                level=InterventionLevel.MEDIUM,
                action=InterventionAction.WARN_AND_CONTINUE,
                reason="检测到轻微偏离，建议注意"
            )
        else:
            return Intervention(
                level=InterventionLevel.NONE,
                action=InterventionAction.PASS,
                reason="一切正常"
            )

    def _calculate_severity(
        self,
        violations: List,
        alignment: 'AlignmentResult',
        resources: Dict
    ) -> float:
        """计算综合严重程度"""
        scores = []

        # 规则违反
        if violations:
            critical_count = sum(
                1 for v in violations
                if v.action == RuleAction.FORCE_TERMINATE
            )
            scores.append(min(1.0, critical_count * 0.5))

        # 目标对齐
        if alignment:
            scores.append(1.0 - alignment.score)

        # 资源使用
        token_ratio = resources.get("token_used", 0) / resources.get("token_limit", 10000)
        scores.append(token_ratio)

        return max(scores) if scores else 0.0
```

---

## 6. 节点系统设计

### 6.1 节点类型体系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           节点类型体系 (Node Type Hierarchy)                 │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         基础节点 (Base Nodes)                        │   │
│  │  ┌─────────┐  ┌─────────┐                                           │   │
│  │  │ START   │  │  END    │  触发和终止工作流                          │   │
│  │  └─────────┘  └─────────┘                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        控制流节点 (Control Flow)                     │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                              │   │
│  │  │CONDITION│  │  LOOP   │  │PARALLEL │  条件/循环/并行控制           │   │
│  │  └─────────┘  └─────────┘  └─────────┘                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        AI能力节点 (AI Capabilities)                  │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐               │   │
│  │  │   LLM   │  │KNOWLEDGE│  │CLASSIFY │  │ TEMPLATE │  AI推理/RAG   │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └──────────┘               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        执行节点 (Execution)                          │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                              │   │
│  │  │   API   │  │  CODE   │  │   MCP   │  外部调用/代码执行            │   │
│  │  └─────────┘  └─────────┘  └─────────┘                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        通用节点 (Generic Node)                       │   │
│  │  ┌────────────────────────────────────────────────────────────────┐ │   │
│  │  │  GENERIC  │  可包含子工作流，支持展开/折叠                      │ │   │
│  │  └────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.2 节点类型定义

```python
class NodeType(Enum):
    """节点类型枚举"""
    # 基础节点
    START = "start"
    END = "end"

    # 控制流节点
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"

    # AI能力节点
    LLM = "llm"
    KNOWLEDGE = "knowledge"
    CLASSIFY = "classify"
    TEMPLATE = "template"

    # 执行节点
    API = "api"
    CODE = "code"
    MCP = "mcp"

    # 通用节点
    GENERIC = "generic"
```

### 6.3 节点配置Schema

```python
# ========== 基础节点 ==========

@dataclass
class StartNodeConfig:
    """开始节点配置"""
    trigger_type: str = "manual"  # manual | webhook | schedule
    input_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EndNodeConfig:
    """结束节点配置"""
    output_schema: Dict[str, Any] = field(default_factory=dict)


# ========== 控制流节点 ==========

@dataclass
class ConditionNodeConfig:
    """条件判断节点配置"""
    condition_type: str = "expression"  # expression | llm_judge
    expression: Optional[str] = None    # e.g., "{{input.score}} > 80"
    llm_prompt: Optional[str] = None    # LLM判断时使用
    branches: List[Dict] = field(default_factory=list)
    default_branch: Optional[str] = None


@dataclass
class LoopNodeConfig:
    """循环节点配置"""
    loop_type: str = "for_each"  # for_each | while | count
    iterable_path: Optional[str] = None  # for_each模式
    while_condition: Optional[str] = None  # while模式
    count: Optional[int] = None  # count模式
    max_iterations: int = 100
    item_variable: str = "item"
    index_variable: str = "index"


@dataclass
class ParallelNodeConfig:
    """并行节点配置"""
    branches: List[str] = field(default_factory=list)  # 分支节点ID
    join_strategy: str = "wait_all"  # wait_all | wait_any | wait_n
    timeout_seconds: Optional[int] = None
    failure_strategy: str = "fail_fast"  # fail_fast | ignore


# ========== AI能力节点 ==========

@dataclass
class LLMNodeConfig:
    """LLM调用节点配置"""
    provider: str = "openai"
    model: str = "gpt-4"
    system_prompt: Optional[str] = None
    user_prompt: str = ""
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    output_parser: Optional[str] = None  # json | text
    max_retries: int = 3


@dataclass
class KnowledgeNodeConfig:
    """知识库检索节点配置"""
    knowledge_base_id: str = ""
    query_template: str = ""
    top_k: int = 5
    similarity_threshold: float = 0.7
    rerank_enabled: bool = False


@dataclass
class ClassifyNodeConfig:
    """问题分类节点配置"""
    classification_type: str = "llm"  # llm | rule
    categories: List[Dict] = field(default_factory=list)
    classification_prompt: Optional[str] = None
    multi_label: bool = False


@dataclass
class TemplateNodeConfig:
    """模板节点配置"""
    template_type: str = "jinja2"  # jinja2 | simple
    template: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)


# ========== 执行节点 ==========

@dataclass
class APINodeConfig:
    """API调用节点配置"""
    method: str = "GET"
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    body_type: str = "json"  # json | form | raw
    body: Optional[str] = None
    timeout_seconds: int = 30
    max_retries: int = 3


@dataclass
class CodeNodeConfig:
    """代码执行节点配置"""
    language: str = "python"  # python | javascript
    code: str = ""
    sandbox_enabled: bool = True
    timeout_seconds: int = 30
    input_variables: List[str] = field(default_factory=list)
    output_variable: str = "result"


@dataclass
class MCPNodeConfig:
    """MCP协议节点配置"""
    server_name: str = ""
    tool_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 60
```

### 6.4 通用节点（支持父子层级）

```python
@dataclass
class GenericNodeConfig:
    """通用节点配置"""
    name: str
    description: Optional[str] = None
    collapsed: bool = True
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_mapping: Dict[str, str] = field(default_factory=dict)


class GenericNode:
    """通用节点 - 支持父子层级"""

    def __init__(
        self,
        id: str,
        config: GenericNodeConfig,
        children: List['WorkflowNode'] = None
    ):
        self.id = id
        self.type = NodeType.GENERIC
        self.config = config
        self.children = children or []
        self.collapsed = config.collapsed
        self.lifecycle = NodeLifecycle.TEMPORARY

    def expand(self) -> 'GenericNode':
        """展开节点"""
        self.collapsed = False
        return self

    def collapse(self) -> 'GenericNode':
        """折叠节点"""
        self.collapsed = True
        return self

    def add_child(self, node: 'WorkflowNode'):
        """添加子节点"""
        self.children.append(node)

    def to_canvas_data(self) -> Dict:
        """转换为画布数据"""
        if self.collapsed:
            return {
                "id": self.id,
                "type": "generic",
                "data": {
                    "label": self.config.name,
                    "collapsed": True,
                    "childCount": len(self.children)
                }
            }
        else:
            return {
                "id": self.id,
                "type": "generic_expanded",
                "data": {
                    "label": self.config.name,
                    "collapsed": False,
                    "children": [c.to_canvas_data() for c in self.children]
                }
            }
```

### 6.5 节点生命周期

```python
class NodeLifecycle(Enum):
    """节点生命周期"""
    TEMPORARY = "temporary"   # 临时：仅当前会话有效
    PERSISTED = "persisted"   # 持久化：保存到当前工作流
    TEMPLATE = "template"     # 模板：可复用（用户级）
    GLOBAL = "global"         # 全局：系统级别可用


class NodeLifecycleManager:
    """节点生命周期管理器"""

    VALID_TRANSITIONS = {
        NodeLifecycle.TEMPORARY: [NodeLifecycle.PERSISTED],
        NodeLifecycle.PERSISTED: [NodeLifecycle.TEMPLATE, NodeLifecycle.TEMPORARY],
        NodeLifecycle.TEMPLATE: [NodeLifecycle.GLOBAL],
        NodeLifecycle.GLOBAL: [],
    }

    def promote(
        self,
        node: 'WorkflowNode',
        to: NodeLifecycle
    ) -> 'WorkflowNode':
        """提升节点生命周期"""
        current = node.lifecycle

        if to not in self.VALID_TRANSITIONS.get(current, []):
            raise ValueError(f"无效的生命周期转换: {current} -> {to}")

        node.lifecycle = to
        return node
```

---

## 7. 上下文管理策略

### 7.1 分层上下文架构

```
┌─────────────────────────────────────────────────────────────────┐
│                全局上下文 (Global Context) - 只读                │
│  用户偏好 | 系统配置 | 全局目标 | 共享知识                        │
│  生命周期: 整个会话                                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 继承
┌──────────────────────────▼──────────────────────────────────────┐
│                会话上下文 (Session Context) - 读写               │
│  对话历史 | 目标栈 | Agent交互记录 | 决策历史                     │
│  生命周期: 单次用户会话                                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 派生
┌──────────────────────────▼──────────────────────────────────────┐
│               工作流上下文 (Workflow Context) - 隔离              │
│  工作流状态 | 节点数据 | 执行历史 | 中间结果                      │
│  生命周期: 单个工作流执行                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 临时
┌──────────────────────────▼──────────────────────────────────────┐
│                节点上下文 (Node Context) - 临时                  │
│  输入数据 | 执行状态 | 输出数据                                   │
│  生命周期: 单个节点执行                                          │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 上下文数据结构

```python
@dataclass
class GlobalContext:
    """全局上下文 - 只读"""
    user_id: str
    user_preferences: Dict[str, Any]
    system_config: Dict[str, Any]
    global_goals: List[Goal]


@dataclass
class SessionContext:
    """会话上下文"""
    session_id: str
    global_context: GlobalContext

    conversation_history: List[Dict] = field(default_factory=list)
    goal_stack: List[Goal] = field(default_factory=list)
    decision_history: List[Decision] = field(default_factory=list)

    # 摘要缓存
    conversation_summary: Optional[str] = None

    def push_goal(self, goal: Goal):
        self.goal_stack.append(goal)

    def pop_goal(self) -> Optional[Goal]:
        return self.goal_stack.pop() if self.goal_stack else None

    def current_goal(self) -> Optional[Goal]:
        return self.goal_stack[-1] if self.goal_stack else None


@dataclass
class WorkflowContext:
    """工作流上下文"""
    workflow_id: str
    session_context: SessionContext  # 引用（只读）

    node_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    execution_history: List[Dict] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)

    def get_node_output(self, node_id: str, key: str = None):
        data = self.node_data.get(node_id, {})
        return data.get(key) if key else data

    def set_node_output(self, node_id: str, data: Dict):
        self.node_data[node_id] = data


@dataclass
class NodeContext:
    """节点上下文"""
    node_id: str
    workflow_context: WorkflowContext

    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    execution_state: str = "pending"
```

### 7.3 上下文桥接与摘要

```python
class ContextBridge:
    """上下文桥接器"""

    def __init__(self, summarizer: 'ContextSummarizer'):
        self.summarizer = summarizer

    async def transfer(
        self,
        source: WorkflowContext,
        target: WorkflowContext,
        summarize: bool = True,
        max_tokens: int = 1000
    ) -> Dict:
        """在工作流间传递上下文"""
        data = {
            "outputs": source.node_data,
            "variables": source.variables
        }

        if summarize:
            data = await self.summarizer.summarize(data, max_tokens)

        # 注入到目标上下文
        target.variables["__transferred__"] = data

        return data


class ContextSummarizer:
    """上下文摘要器"""

    def __init__(self, llm_client: Any):
        self.llm = llm_client

    async def summarize(
        self,
        data: Dict,
        max_tokens: int = 1000
    ) -> Dict:
        """摘要上下文数据"""
        prompt = f"""
        请对以下数据进行摘要，保留关键信息：

        数据: {json.dumps(data, ensure_ascii=False, indent=2)}

        要求:
        1. 保留关键的输入输出值
        2. 保留重要的中间结果
        3. 总结执行过程

        输出格式 (JSON):
        {{
            "summary": "执行摘要",
            "key_outputs": {{}},
            "important_values": {{}}
        }}
        """

        response = await self.llm.generate(prompt)
        return json.loads(response)
```

---

## 8. 同步与一致性机制

### 8.1 事件总线

```python
@dataclass
class Event:
    """基础事件"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    correlation_id: Optional[str] = None


# 决策事件
@dataclass
class DecisionMadeEvent(Event):
    decision: Decision = None
    goal_id: str = ""


@dataclass
class DecisionValidatedEvent(Event):
    decision_id: str = ""
    is_valid: bool = True
    corrections: List[str] = field(default_factory=list)


# 工作流事件
@dataclass
class NodeCreatedEvent(Event):
    node_id: str = ""
    node_type: str = ""
    workflow_id: str = ""
    created_by: str = ""


@dataclass
class NodeExecutionStartedEvent(Event):
    node_id: str = ""
    workflow_id: str = ""


@dataclass
class NodeExecutionCompletedEvent(Event):
    node_id: str = ""
    workflow_id: str = ""
    outputs: Dict = field(default_factory=dict)


@dataclass
class WorkflowExecutionCompletedEvent(Event):
    workflow_id: str = ""
    status: str = ""
    outputs: Dict = field(default_factory=dict)


# 画布事件
@dataclass
class CanvasUpdateEvent(Event):
    workflow_id: str = ""
    update_type: str = ""  # full | incremental
    changes: Dict = field(default_factory=dict)


class EventBus:
    """事件总线"""

    def __init__(self):
        self.subscribers: Dict[type, List[Callable]] = {}
        self.event_log: List[Event] = []
        self.middleware: List[Callable] = []

    def subscribe(self, event_type: type, handler: Callable):
        """订阅事件"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    async def publish(self, event: Event):
        """发布事件"""
        # 执行中间件
        for middleware in self.middleware:
            event = await middleware(event)
            if event is None:
                return

        # 记录日志
        self.event_log.append(event)

        # 分发给订阅者
        handlers = self.subscribers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    def add_middleware(self, middleware: Callable):
        """添加中间件"""
        self.middleware.append(middleware)
```

### 8.2 状态同步

```python
class StateSynchronizer:
    """状态同步器"""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.state: Dict = {}

        # 订阅事件
        self.event_bus.subscribe(NodeCreatedEvent, self._on_node_created)
        self.event_bus.subscribe(NodeExecutionCompletedEvent, self._on_node_completed)

    async def _on_node_created(self, event: NodeCreatedEvent):
        """处理节点创建"""
        workflow_id = event.workflow_id

        if workflow_id not in self.state:
            self.state[workflow_id] = {"nodes": {}, "edges": []}

        self.state[workflow_id]["nodes"][event.node_id] = {
            "type": event.node_type,
            "status": "created"
        }

        # 通知画布更新
        await self.event_bus.publish(CanvasUpdateEvent(
            workflow_id=workflow_id,
            update_type="incremental",
            changes={"added_nodes": [event.node_id]}
        ))

    async def _on_node_completed(self, event: NodeExecutionCompletedEvent):
        """处理节点执行完成"""
        workflow_id = event.workflow_id
        node_id = event.node_id

        if workflow_id in self.state:
            self.state[workflow_id]["nodes"][node_id]["status"] = "completed"
            self.state[workflow_id]["nodes"][node_id]["outputs"] = event.outputs
```

### 8.3 双向同步协议

```python
class BidirectionalSyncProtocol:
    """双向同步协议"""

    def __init__(
        self,
        event_bus: EventBus,
        conversation_agent: 'ConversationAgent',
        workflow_agent: 'WorkflowAgent'
    ):
        self.event_bus = event_bus
        self.conversation_agent = conversation_agent
        self.workflow_agent = workflow_agent

        self._setup()

    def _setup(self):
        """设置事件订阅"""
        # 对话Agent -> 工作流Agent
        self.event_bus.subscribe(
            DecisionValidatedEvent,
            self._forward_to_workflow
        )

        # 工作流Agent -> 对话Agent
        self.event_bus.subscribe(
            WorkflowExecutionCompletedEvent,
            self._forward_to_conversation
        )

    async def _forward_to_workflow(self, event: DecisionValidatedEvent):
        """将验证通过的决策转发给工作流Agent"""
        if event.is_valid:
            await self.workflow_agent.execute_decision(event.decision_id)

    async def _forward_to_conversation(self, event: WorkflowExecutionCompletedEvent):
        """将执行结果转发给对话Agent"""
        await self.conversation_agent.receive_result(
            workflow_id=event.workflow_id,
            status=event.status,
            outputs=event.outputs
        )
```

---

## 9. 分阶段实施计划

### 9.1 整体规划

```
Phase 0        Phase 1        Phase 2        Phase 3        Phase 4
─────────      ─────────      ─────────      ─────────      ─────────
基础设施       核心Agent      协作机制        高级特性       优化扩展

┌─────┐       ┌─────┐       ┌─────┐       ┌─────┐       ┌─────┐
│事件 │       │对话 │       │协调者│       │通用 │       │性能 │
│总线 │──────►│Agent│──────►│Agent│──────►│节点 │──────►│优化 │
└─────┘       └─────┘       └─────┘       └─────┘       └─────┘

════════════════════════════════════════════════════════════════
      MVP                              V1.0              V2.0
```

### 9.2 Phase 0: 基础设施

**目标**: 搭建核心基础设施

```yaml
任务列表:
  0.1 事件总线:
    - EventBus 核心实现
    - 事件发布/订阅
    - 事件日志持久化

    产出: src/domain/services/event_bus.py

  0.2 上下文管理器:
    - GlobalContext
    - SessionContext
    - WorkflowContext
    - NodeContext

    产出: src/domain/services/context_manager.py

  0.3 节点注册中心:
    - NodeRegistry
    - 节点Schema验证
    - 预定义节点注册

    产出: src/domain/services/node_registry.py

验收标准:
  - 事件总线可正常发布/订阅事件
  - 所有预定义节点类型可注册
  - 上下文层级继承正确
```

### 9.3 Phase 1: 核心Agent实现

**目标**: 实现对话Agent和工作流Agent核心功能

```yaml
任务列表:
  1.1 ReAct循环:
    - ReActLoop 类
    - CircuitBreaker 熔断器
    - 基础决策生成

    产出: src/domain/services/react_loop.py

  1.2 目标管理:
    - Goal 实体
    - GoalStack
    - 基础目标分解

    产出: src/domain/entities/goal.py

  1.3 节点工厂:
    - NodeFactory
    - 节点生命周期管理

    产出: src/domain/services/node_factory.py

  1.4 执行引擎:
    - ExecutionEngine
    - 基础执行器 (LLM, API, Code)

    产出: src/domain/services/execution_engine.py

  1.5 前端画布:
    - React Flow 集成
    - 节点组件

    产出: web/src/features/workflow-canvas/

验收标准:
  - 对话Agent可完成单轮ReAct推理
  - 工作流Agent可执行简单线性工作流
  - 前端画布可显示和编辑节点
```

### 9.4 Phase 2: 协作机制

**目标**: 实现Agent间协作和同步

```yaml
任务列表:
  2.1 规则引擎:
    - RuleEngine
    - 静态规则加载
    - 规则评估

    产出: src/domain/services/rule_engine.py

  2.2 验证器:
    - DecisionValidator
    - GoalAlignmentChecker
    - ResourceMonitor

    产出: src/domain/services/validators.py

  2.3 干预策略:
    - InterventionStrategy
    - 干预级别判定

    产出: src/domain/services/intervention_strategy.py

  2.4 同步协议:
    - StateSynchronizer
    - BidirectionalSyncProtocol

    产出: src/domain/services/sync_protocol.py

  2.5 画布同步:
    - CanvasSynchronizer
    - WebSocket通信

    产出: src/infrastructure/websocket/canvas_sync.py

验收标准:
  - 协调者可拦截和验证决策
  - 对话Agent和工作流Agent可双向同步
  - 画布实时反映后端状态
```

### 9.5 Phase 3: 高级特性

**目标**: 通用节点、智能目标分解

```yaml
任务列表:
  3.1 通用节点:
    - GenericNode
    - 子工作流封装
    - 展开/折叠

  3.2 智能目标分解:
    - LLM GoalDecomposer
    - 依赖关系分析

  3.3 高级上下文:
    - ContextBridge
    - 分层摘要

  3.4 完整执行器:
    - 条件/循环/并行
    - 知识库/分类/MCP
```

### 9.6 Phase 4: 优化与扩展

**目标**: 性能优化、监控、扩展API

```yaml
任务列表:
  4.1 性能优化:
    - 并行执行优化
    - 上下文缓存

  4.2 监控:
    - 指标收集
    - 链路追踪

  4.3 扩展API:
    - 插件系统
    - 自定义节点API
```

---

## 10. 关键设计决策

### 10.1 已确认的决策

| 决策点 | 决策 | 理由 |
|--------|------|------|
| 数据源 | Event Bus作为单一数据源 | 保证一致性 |
| 同步方向 | 对话Agent主导 | 符合"大脑"定位 |
| 用户修改 | 通知对话Agent决定是否采纳 | 保持核心决策权 |
| 上下文策略 | 分层继承+按需摘要 | 平衡完整性和效率 |
| 冲突解决 | Last-Write-Wins | 简化实现 |
| 节点生命周期 | 默认临时，显式提升 | 避免污染 |
| 协调者智能度 | 先规则，后LLM增强 | MVP优先 |
| 节点模板范围 | 先用户级，后共享 | 逐步扩展 |
| 工作流并发 | 先串行，后并发 | MVP优先 |

### 10.2 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| ReAct无限循环 | CircuitBreaker多重终止条件 |
| Agent间死锁 | 超时机制+异步解耦 |
| 上下文爆炸 | 分层摘要+Token预算 |
| 同步延迟 | 乐观更新+后台对账 |

---

## 11. 附录

### 11.1 技术栈

```yaml
后端:
  框架: FastAPI
  事件驱动: asyncio + Queue (内存), Redis Streams (生产)
  LLM: LangChain
  存储: SQLAlchemy + SQLite/PostgreSQL

前端:
  框架: React + TypeScript
  画布: React Flow
  状态: Zustand
  通信: WebSocket
```

### 11.2 参考项目

| 项目 | 用途 |
|------|------|
| LangGraph | 图结构状态机 |
| OpenAI Agents SDK | Handoff机制 |
| Dify | Agent节点+工作流 |
| React Flow | 前端画布 |
| MemGPT | 分层记忆 |

### 11.3 文档更新记录

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2025-12-01 | 1.0 | 初始版本，完整架构设计 |

---

**文档状态**: 已确认，待实施
**下一步**: 按照Phase 0开始实施基础设施
