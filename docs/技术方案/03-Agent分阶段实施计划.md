# Agent分阶段实施计划（V1-V4）

> **技术方案文档**
> 项目名称：Feagent
> 文档说明：本文档描述Agent功能的分阶段演进路线（V1→V4）

---

## 📋 版本演进总览

| 版本 | 核心能力 | 交互模式 | 技术重点 | 目标用户 |
|------|---------|---------|---------|---------|
| **V1** | 基础执行 | 一次性任务 | SSE流式输出、线性执行 | 技术用户 |
| **V2** | 智能识别 | 任务分类路由 | FSM状态机、任务识别 | 进阶用户 |
| **V3** | 对话式Agent | 持续对话介入（COS） | 多轮对话、上下文管理 | 小白用户 |
| **V4** | MCP驱动自循环 | 自主规划执行 | MCP集成、自我迭代 | 高级场景 |

---

## 🎯 V1: 基础执行引擎（已完成）

### V1.1 核心功能
- **输入**：用户提供起点（start）+ 目标（goal）
- **处理**：
  1. 系统自动生成线性任务计划（3-7步）
  2. 依次执行每个任务节点
  3. 通过SSE实时推送执行状态
- **输出**：任务执行结果 + 完整日志
- **状态机**：`PENDING → RUNNING → SUCCEEDED/FAILED/CANCELLED`

### V1.2 技术实现要点
```python
# Domain层：Run和Task实体
class Run:
    id: str
    agent_id: str
    status: RunStatus  # PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED
    tasks: List[Task]

class Task:
    id: str
    run_id: str
    type: TaskType  # HTTP/LLM/JAVASCRIPT/PROMPT
    status: TaskStatus
    input_data: dict
    output_data: dict | None
```

### V1.3 SSE事件流规范
```json
// 任务开始事件
{"event": "task_started", "data": {"task_id": "xxx", "type": "HTTP"}, "seq": 1}

// 日志事件
{"event": "log", "data": {"level": "INFO", "msg": "正在执行HTTP请求..."}, "seq": 2}

// 任务完成事件
{"event": "task_completed", "data": {"task_id": "xxx", "result": {...}}, "seq": 3}

// 执行完成标志
{"event": "done", "data": {"status": "SUCCEEDED"}, "seq": 4}
```

### V1.4 验收标准
- [x] 创建Agent成功（POST /agents）
- [x] 触发Run成功（POST /agents/{id}/runs）
- [x] SSE流式输出完整事件序列
- [x] 状态机转换正确（PENDING→RUNNING→终态）
- [x] 测试覆盖率：Domain≥80%，Application≥70%

---

## 🔄 V2: 智能任务识别（当前阶段）

### V2.1 核心能力升级
- **智能分类**：AI识别用户意图，将任务分为3类
  1. **简单任务（Simple）**：直接执行，无需复杂规划
  2. **工作流任务（Workflow）**：需要多步骤编排
  3. **对话任务（Chat）**：需要持续交互澄清

- **FSM状态机**：引入更细粒度的状态管理
  ```
  PENDING → CLASSIFYING → PLANNING → EXECUTING → COMPLETED
                       ↓
                   NEED_CLARIFICATION → (用户补充) → PLANNING
  ```

### V2.2 任务分类逻辑
```python
# Application层：任务分类用例
class ClassifyTaskUseCase:
    def execute(self, start: str, goal: str) -> TaskCategory:
        prompt = f"""
        分析用户需求并分类：
        起点：{start}
        目标：{goal}

        类别：
        - SIMPLE: 单次API调用、简单查询
        - WORKFLOW: 需要3+步骤的复杂流程
        - CHAT: 信息不足，需要多轮对话澄清

        返回JSON: {{"category": "...", "confidence": 0.9, "reason": "..."}}
        """
        result = llm.invoke(prompt)
        return parse_category(result)
```

### V2.3 技术实现要点
- **LLM集成**：使用LangChain调用分类模型
- **配置管理**：支持用户选择LLM提供商（OpenAI/DeepSeek/Qwen等）
- **降级策略**：分类失败时默认为WORKFLOW模式
- **审计日志**：记录分类决策过程供调试

### V2.4 验收标准
- [ ] 实现任务分类用例（ClassifyTaskUseCase）
- [ ] 集成至少2个LLM提供商
- [ ] FSM状态转换测试通过
- [ ] 分类准确率≥85%（通过人工标注样本验证）

---

## 💬 V3: 对话式Agent（COS模式）

### V3.1 核心概念：持续介入式对话（COS）
**COS = Continuous Oversight**：用户可在执行过程中随时介入、调整、确认

#### 传统模式 vs COS模式对比
| 维度 | 传统一次性模式 | COS模式 |
|------|--------------|---------|
| **交互** | 提交后等待结果 | 执行中可随时介入 |
| **控制** | 无法中途调整 | 可暂停、修改、继续 |
| **澄清** | 失败后重试 | 执行前/中主动询问 |
| **适用** | 明确需求 | 需求模糊/高风险操作 |

### V3.2 技术架构变化

#### 引入对话上下文管理
```python
# Domain层：对话会话实体
@dataclass
class ChatSession:
    id: str
    agent_id: str
    run_id: str | None
    messages: List[ChatMessage]
    context: dict  # 上下文变量

@dataclass
class ChatMessage:
    role: str  # user/assistant/system
    content: str
    timestamp: datetime
    metadata: dict  # 工具调用、中间结果等
```

#### SSE双向通信扩展
```json
// Agent主动提问事件
{
  "event": "agent_question",
  "data": {
    "question": "我发现有3个相似API，请选择：",
    "options": ["option1", "option2", "option3"],
    "default": "option1"
  },
  "seq": 5
}

// 用户介入事件
{
  "event": "user_intervention",
  "data": {
    "action": "pause",  // pause/resume/modify/approve
    "message": "暂停执行，我需要检查当前结果"
  },
  "seq": 6
}
```

### V3.3 对话流程示例

```
用户：帮我每天早上9点抓取GitHub Trending并发送到钉钉

Agent：[分析中...] 我将创建一个工作流：
      1. 定时触发（cron: 0 9 * * *）
      2. 抓取GitHub Trending API
      3. 格式化为Markdown
      4. 发送到钉钉

      ❓ 问题1：需要抓取哪个语言的Trending？
      选项：[All] [Python] [JavaScript] [Go]

用户：Python

Agent：✅ 好的，使用Python语言筛选
      ❓ 问题2：我需要你的钉钉Webhook地址

用户：https://oapi.dingtalk.com/robot/send?access_token=xxx

Agent：✅ 配置已保存，开始执行首次测试...
      [执行中...]
      ✅ 测试成功！已发送1条消息到钉钉

      是否保存此工作流并启用定时任务？[确认/取消]
```

### V3.4 实现要点
- **Memory管理**：使用LangChain的ConversationBufferMemory
- **澄清策略**：
  - 主动澄清：执行前检测缺失参数/二义性配置
  - 被动澄清：执行失败时回退并询问
- **会话持久化**：对话历史存入数据库
- **上下文窗口**：限制最近N轮对话（避免超出Token限制）

### V3.5 验收标准
- [ ] 实现ChatSession实体和Repository
- [ ] 支持多轮对话的SSE事件扩展
- [ ] 主动澄清机制（至少3个典型场景）
- [ ] 对话历史可回溯查看
- [ ] 用户介入操作（暂停/恢复/修改）

---

## 🚀 V4: MCP驱动的自循环Agent

### V4.1 MCP（Model Context Protocol）简介
**MCP** 是一个开放标准，用于连接AI系统与外部工具/数据源。

#### MCP核心概念
- **Server**：提供工具/资源/提示词的服务端
- **Client**：调用MCP服务的AI应用
- **Tools**：可执行的函数（API调用、数据库查询等）
- **Resources**：可访问的数据源（文件、数据库等）
- **Prompts**：预定义的提示词模板

### V4.2 Feagent的MCP集成策略

#### 作为MCP Client
```python
# 调用外部MCP服务器（如Coze工具）
from mcp import Client

mcp_client = Client()
mcp_client.connect("https://mcp.coze.com")

# 发现可用工具
tools = mcp_client.list_tools()
# => [{"name": "search_web", "description": "..."}, ...]

# 调用工具
result = mcp_client.call_tool("search_web", {"query": "AI Agent"})
```

#### 作为MCP Server
```python
# 将Feagent的能力暴露为MCP服务
from mcp import Server

server = Server("feagent-mcp")

@server.tool("create_workflow")
def create_workflow(start: str, goal: str) -> dict:
    """创建并执行工作流"""
    agent = Agent.create(start=start, goal=goal)
    run = trigger_run(agent.id)
    return {"run_id": run.id, "status": run.status}

server.start()
```

### V4.3 自循环机制

#### 自我规划-执行-反思循环
```
1. 规划（Plan）
   ↓ Agent分析任务，生成执行计划

2. 执行（Act）
   ↓ 调用MCP工具执行任务

3. 观察（Observe）
   ↓ 收集执行结果和环境反馈

4. 反思（Reflect）
   ↓ 评估结果是否满足目标

5. 决策（Decide）
   ├→ 成功：结束循环
   └→ 失败：调整计划，返回步骤1（最多N次）
```

#### 示例：自我修复的数据抓取任务
```
用户：抓取某网站最新文章

Agent规划：
  Plan 1: 使用HTTP工具GET请求网站

执行：HTTP GET https://example.com
观察：返回403 Forbidden
反思：直接请求被拒绝，可能需要headers

Agent调整：
  Plan 2: 添加User-Agent和Referer headers

执行：HTTP GET with headers
观察：返回200 OK，但HTML结构与预期不符
反思：网站可能更新了结构，需要调整解析规则

Agent调整：
  Plan 3: 使用MCP工具"web_scraper"智能提取

执行：调用MCP工具
观察：成功提取文章列表
反思：✅ 满足目标
结果：任务完成
```

### V4.4 技术实现要点

#### ReAct Agent模式
```python
# Application层：自循环执行器
class SelfLoopingAgent:
    def __init__(
        self,
        llm: BaseLLM,
        mcp_client: MCPClient,
        max_iterations: int = 10
    ):
        self.llm = llm
        self.tools = mcp_client.list_tools()
        self.max_iterations = max_iterations

    def run(self, start: str, goal: str) -> dict:
        context = {"start": start, "goal": goal, "history": []}

        for i in range(self.max_iterations):
            # 1. 规划下一步
            action = self.plan(context)

            # 2. 执行动作
            observation = self.act(action)

            # 3. 反思
            reflection = self.reflect(context, observation)

            # 4. 决策
            if reflection["should_stop"]:
                return {"status": "SUCCEEDED", "result": observation}

            # 5. 更新上下文
            context["history"].append({
                "action": action,
                "observation": observation,
                "reflection": reflection
            })

        return {"status": "FAILED", "reason": "Max iterations reached"}
```

#### 预算与早停机制
- **Token预算**：限制单次循环最大Token消耗
- **成本预算**：限制调用外部API的费用上限
- **时间预算**：超时自动终止
- **质量检查**：每次迭代评估结果质量，连续下降则早停

### V4.5 验收标准
- [ ] 集成MCP Client（调用外部工具）
- [ ] 实现MCP Server（暴露Feagent能力）
- [ ] 实现ReAct自循环逻辑
- [ ] 预算与早停机制
- [ ] 自我修复案例验证（至少3个场景）
- [ ] 循环次数、Token消耗等指标监控

---

## 📊 版本对比总结

| 能力维度 | V1 | V2 | V3 | V4 |
|---------|----|----|----|----|
| **任务执行** | 线性执行 | 智能分类 | 对话式执行 | 自主规划执行 |
| **用户交互** | 一次性提交 | 分类提示 | 多轮对话 | 最小交互 |
| **错误处理** | 失败即终止 | 重试机制 | 主动澄清 | 自我修复 |
| **工具调用** | 预定义节点 | 预定义节点 | 预定义节点 | 动态MCP工具 |
| **适用场景** | 简单任务 | 中等复杂度 | 需求模糊 | 复杂长尾任务 |
| **开发难度** | ⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **用户门槛** | 中 | 中 | 低 | 低 |

---

## 🗓️ 实施时间线

- **V1**：已完成（2024 Q4）
- **V2**：当前阶段（2025 Q1）
- **V3**：计划开始（2025 Q2）
- **V4**：预研阶段（2025 Q3-Q4）

---

## ⚠️ 风险与对策

### V2风险
- **风险**：LLM分类不准确
- **对策**：人工标注样本训练、多模型投票、降级机制

### V3风险
- **风险**：对话循环过长，用户体验差
- **对策**：限制澄清轮次（最多3次）、提供快捷选项

### V4风险
- **风险**：自循环不收敛，Token/成本失控
- **对策**：严格预算限制、早停策略、人在回路确认

---

> **文档维护**：
> - 每个版本完成后更新验收标准
> - 遇到架构调整及时同步本文档
> - 定期回顾演进路线，评估是否需要调整优先级
