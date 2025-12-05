"""
ReAct Prompt 模板 - 支持依赖关系和资源约束

本模块定义了增强版的 ReAct prompt 模板，用于 ConversationAgent 进行：
1. 依赖关系识别：理解任务之间的先后顺序和数据依赖
2. 资源约束感知：考虑时间、成本、并发等资源限制
3. 结构化决策生成：输出符合 Pydantic schema 的决策载荷

用法：
    from src.domain.agents.react_prompts import (
        REACT_SYSTEM_PROMPT,
        WORKFLOW_PLANNING_PROMPT,
        format_planning_context
    )

    # 在 ConversationAgent 中使用
    prompt = WORKFLOW_PLANNING_PROMPT.format(
        user_request="分析销售数据",
        context=format_planning_context(session_context)
    )
"""

from typing import Any

# ========================================
# 系统提示词
# ========================================

REACT_SYSTEM_PROMPT = """你是一个智能任务规划助手，擅长将复杂任务分解为可执行的工作流。

你的核心能力：
1. **依赖关系识别**：理解任务之间的先后顺序和数据流
2. **资源约束感知**：考虑时间、成本、API限制等约束
3. **结构化决策**：生成符合规范的 JSON 格式决策

工作原则：
- 先理解用户需求，识别核心目标
- 分解任务时考虑依赖关系（哪些任务必须先完成）
- 考虑资源约束（API调用次数、执行时间、并发限制）
- 生成的决策必须符合 payload schema 规范
- 如果需求不明确，请求澄清而不是猜测

决策类型：
- create_node: 创建单个工具节点
- create_workflow_plan: 创建完整工作流（多个节点+依赖关系）
- execute_workflow: 执行已有工作流
- modify_node: 修改节点配置
- request_clarification: 请求用户澄清
- respond: 直接回复
- continue: 继续推理
"""

# ========================================
# 工作流规划提示词
# ========================================

WORKFLOW_PLANNING_PROMPT = """# 任务规划

## 用户请求
{user_request}

## 当前上下文
{context}

## 规划要求

### 1. 依赖关系分析
识别任务之间的依赖关系：
- **数据依赖**：任务 B 需要任务 A 的输出数据
- **顺序依赖**：任务 B 必须在任务 A 完成后执行
- **条件依赖**：任务 B 的执行取决于任务 A 的结果

示例：
```
任务1: 获取销售数据 (数据库查询)
任务2: 分析趋势 (依赖任务1的输出)
任务3: 生成图表 (依赖任务2的输出)
任务4: 发送报告 (依赖任务3的输出)

依赖链: 任务1 → 任务2 → 任务3 → 任务4
```

### 2. 资源约束考虑
评估以下资源约束：
- **时间约束**：任务总执行时间限制（默认5分钟）
- **API限制**：外部API调用次数限制
- **并发限制**：同时执行的任务数量限制（默认3个）
- **成本约束**：LLM token 使用成本估算

### 3. 工作流结构
生成工作流时必须包含：
- `name`: 工作流名称（简短描述）
- `description`: 详细说明（包含目标和预期结果）
- `nodes`: 节点列表
  - 每个节点必须有唯一的 `node_id`
  - 节点类型：DATABASE, HTTP, LLM, PYTHON, CONDITION
  - 节点配置必须完整（url, query, prompt等）
- `edges`: 边列表（定义依赖关系）
  - `source`: 源节点ID
  - `target`: 目标节点ID
  - `condition`: 可选的条件表达式

### 4. 错误处理
为关键节点添加错误处理：
- **重试配置**：max_retries, retry_delay
- **超时设置**：timeout（秒）
- **失败回退**：alternative_node（可选）

### 5. 输出格式
生成符合以下 schema 的 JSON：

```json
{{
  "action_type": "create_workflow_plan",
  "name": "工作流名称",
  "description": "详细描述",
  "nodes": [
    {{
      "node_id": "node_1",
      "type": "DATABASE",
      "name": "节点名称",
      "config": {{
        "query": "SQL查询语句",
        "connection": "数据库连接"
      }},
      "input_mapping": {{}},
      "output_mapping": {{}}
    }}
  ],
  "edges": [
    {{
      "source": "node_1",
      "target": "node_2"
    }}
  ],
  "global_config": {{
    "timeout": 300,
    "max_parallel": 3
  }}
}}
```

## 思考过程

请按以下步骤思考：

1. **理解需求**：用户想要什么？核心目标是什么？
2. **识别任务**：需要哪些步骤才能完成目标？
3. **分析依赖**：这些步骤之间有什么依赖关系？
4. **评估资源**：需要调用哪些API？预计耗时多久？
5. **设计工作流**：将任务映射为节点，定义边表示依赖
6. **验证完整性**：所有必填字段都包含了吗？依赖关系正确吗？

现在，请根据以上要求生成工作流规划。
"""

# ========================================
# 依赖关系提示词
# ========================================

DEPENDENCY_ANALYSIS_PROMPT = """# 依赖关系分析

## 任务列表
{tasks}

## 分析指导

### 1. 识别数据依赖
- 哪些任务需要其他任务的输出数据？
- 数据如何在任务之间流转？

### 2. 识别顺序依赖
- 哪些任务必须按特定顺序执行？
- 为什么必须按这个顺序？

### 3. 识别条件依赖
- 哪些任务的执行取决于其他任务的结果？
- 条件是什么？（成功/失败/特定值）

### 4. 并行机会
- 哪些任务可以并行执行（没有依赖关系）？
- 并行执行能节省多少时间？

## 输出格式
请以 JSON 格式输出依赖关系：

```json
{{
  "dependencies": [
    {{
      "target": "任务B",
      "depends_on": ["任务A"],
      "type": "data",
      "description": "任务B需要任务A的输出数据"
    }}
  ],
  "parallel_groups": [
    ["任务C", "任务D"],
    ["任务E"]
  ],
  "critical_path": ["任务A", "任务B", "任务F"],
  "estimated_time": {{
    "sequential": "15分钟",
    "parallel": "8分钟"
  }}
}}
```
"""

# ========================================
# 资源约束提示词
# ========================================

RESOURCE_CONSTRAINT_PROMPT = """# 资源约束评估

## 任务列表
{tasks}

## 评估维度

### 1. 时间约束
- 每个任务预计执行时间
- 总执行时间是否在限制内（{time_limit}秒）
- 如何优化执行时间？

### 2. API调用限制
- 需要调用哪些外部API？
- 每个API的调用次数限制是多少？
- 是否超过限制？如何优化？

### 3. 并发限制
- 最多同时执行几个任务？（默认{max_parallel}个）
- 如何分组任务以最大化并发？

### 4. 成本约束
- LLM调用的token使用量估算
- API调用的成本估算
- 总成本是否可接受？

## 输出格式
```json
{{
  "time_estimate": {{
    "total": "10分钟",
    "breakdown": [
      {{"task": "任务A", "time": "2分钟"}},
      {{"task": "任务B", "time": "3分钟"}}
    ]
  }},
  "api_calls": {{
    "total": 15,
    "breakdown": [
      {{"api": "Weather API", "calls": 5}},
      {{"api": "OpenAI API", "calls": 10}}
    ]
  }},
  "parallelization": {{
    "max_parallel": 3,
    "groups": [["任务A", "任务B", "任务C"], ["任务D"]]
  }},
  "cost_estimate": {{
    "llm_tokens": 5000,
    "api_cost": "$0.50",
    "total": "$0.75"
  }},
  "constraints_met": true,
  "warnings": []
}}
```
"""

# ========================================
# 澄清请求提示词
# ========================================

CLARIFICATION_REQUEST_PROMPT = """# 需求澄清

## 用户输入
{user_input}

## 缺失信息
{missing_info}

## 澄清策略

### 1. 识别模糊点
- 哪些关键信息缺失？
- 哪些假设需要验证？

### 2. 设计问题
- 问题要具体、明确
- 提供选项降低回答难度
- 一次不要问太多问题（最多3个）

### 3. 输出格式
```json
{{
  "action_type": "request_clarification",
  "question": "具体问题",
  "options": ["选项1", "选项2", "选项3"],
  "required_fields": ["字段名1", "字段名2"],
  "context": {{
    "partial_intent": "部分理解的意图",
    "missing_info": ["缺失的信息1", "缺失的信息2"]
  }}
}}
```
"""

# ========================================
# 上下文格式化函数
# ========================================


def format_planning_context(context: dict[str, Any]) -> str:
    """格式化规划上下文

    Args:
        context: 包含会话历史、目标栈等信息的上下文字典

    Returns:
        格式化的上下文字符串
    """
    lines = []

    # 当前目标
    if current_goal := context.get("current_goal"):
        lines.append(f"**当前目标**: {current_goal.get('description', 'N/A')}")

    # 目标栈
    if goal_stack := context.get("goal_stack"):
        lines.append("\n**目标栈**:")
        for i, goal in enumerate(goal_stack, 1):
            lines.append(f"  {i}. {goal.get('description', 'N/A')}")

    # 对话历史（最近5轮）
    if history := context.get("conversation_history"):
        lines.append("\n**对话历史** (最近5轮):")
        for msg in history[-5:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]  # 限制长度
            lines.append(f"  - {role}: {content}")

    # 已执行的决策
    if decisions := context.get("decisions"):
        lines.append("\n**已执行决策**:")
        for decision in decisions[-3:]:  # 最近3个决策
            dtype = decision.get("type", "unknown")
            lines.append(f"  - {dtype}")

    # 资源约束
    if constraints := context.get("resource_constraints"):
        lines.append("\n**资源约束**:")
        if time_limit := constraints.get("time_limit"):
            lines.append(f"  - 时间限制: {time_limit}秒")
        if max_parallel := constraints.get("max_parallel"):
            lines.append(f"  - 最大并发: {max_parallel}个任务")
        if api_limits := constraints.get("api_limits"):
            lines.append(f"  - API限制: {api_limits}")

    return "\n".join(lines) if lines else "无上下文信息"


def format_dependency_tasks(tasks: list[dict[str, Any]]) -> str:
    """格式化任务列表用于依赖分析

    Args:
        tasks: 任务列表

    Returns:
        格式化的任务字符串
    """
    lines = []
    for i, task in enumerate(tasks, 1):
        name = task.get("name", f"任务{i}")
        desc = task.get("description", "")
        node_type = task.get("type", "unknown")
        lines.append(f"{i}. **{name}** ({node_type})")
        if desc:
            lines.append(f"   描述: {desc}")
        lines.append("")

    return "\n".join(lines)


def format_resource_constraints(time_limit: int = 300, max_parallel: int = 3) -> dict[str, Any]:
    """格式化资源约束

    Args:
        time_limit: 时间限制（秒）
        max_parallel: 最大并发数

    Returns:
        资源约束字典
    """
    return {"time_limit": time_limit, "max_parallel": max_parallel, "api_limits": {}}


# ========================================
# Prompt 模板选择器
# ========================================


def get_prompt_for_action_type(action_type: str) -> str:
    """根据动作类型获取对应的 prompt 模板

    Args:
        action_type: 动作类型

    Returns:
        prompt 模板字符串
    """
    prompt_map = {
        "create_workflow_plan": WORKFLOW_PLANNING_PROMPT,
        "request_clarification": CLARIFICATION_REQUEST_PROMPT,
        "analyze_dependencies": DEPENDENCY_ANALYSIS_PROMPT,
        "assess_resources": RESOURCE_CONSTRAINT_PROMPT,
    }

    return prompt_map.get(action_type, WORKFLOW_PLANNING_PROMPT)
