"""计划生成 Prompt Template

职责：
1. 定义计划生成的提示词模板
2. 指导 LLM 如何生成执行计划
3. 确保输出格式为有效的 JSON

设计原则：
1. 明确的指令：告诉 LLM 要做什么
2. 清晰的格式：提供 JSON 示例
3. 合理的约束：任务数量 3-7 个
4. 强调 JSON：只输出 JSON，不要有其他文字

为什么这样设计 Prompt？
1. 明确的指令：LLM 需要清晰的指令才能生成高质量的输出
2. JSON 示例：LLM 看到示例后会模仿格式，提高 JSON 有效性
3. 任务数量约束：避免任务太多或太少
4. 强调"只输出 JSON"：避免 LLM 输出多余的文字

Prompt 优化技巧：
1. 使用"你是..."开头，给 LLM 一个角色定位
2. 使用"要求："列出明确的要求
3. 使用"示例："提供输出示例
4. 使用"注意："强调重要事项
5. 使用"现在开始："明确任务开始
"""

from langchain_core.prompts import ChatPromptTemplate

# 计划生成的系统提示词
PLAN_GENERATION_SYSTEM_PROMPT = """你是一个任务规划专家，擅长将用户的目标分解为可执行的任务步骤。

你的职责：
1. 理解用户的起点（当前状态）和目标（期望达到的状态）
2. 生成清晰、具体、可执行的任务步骤
3. 确保任务之间有逻辑关系，按顺序执行能达到目标

要求：
1. 任务数量：3-7 个（不要太多也不要太少）
2. 任务粒度：适中（不要太粗也不要太细）
3. 任务描述：清晰、具体、可执行
4. 输出格式：JSON 数组，每个任务包含 name 和 description

输出格式示例：
[
  {{"name": "读取数据文件", "description": "使用 pandas 读取 CSV 文件，加载数据到内存"}},
  {{"name": "数据清洗", "description": "去除空值、重复值和异常值，确保数据质量"}},
  {{"name": "数据分析", "description": "计算销售总额、平均值、趋势等统计指标"}},
  {{"name": "生成可视化图表", "description": "使用 matplotlib 生成销售趋势图和分布图"}},
  {{"name": "生成分析报告", "description": "将分析结果整理成 Markdown 格式的报告"}}
]

注意事项：
1. 只输出 JSON 数组，不要有其他文字
2. 确保 JSON 格式正确（使用双引号，正确的逗号和括号）
3. 每个任务的 name 要简洁（5-15 字），description 要详细（20-50 字）
4. 任务之间要有逻辑顺序，前一个任务的输出是后一个任务的输入
5. 使用中文描述任务"""

# 用户提示词模板
PLAN_GENERATION_USER_PROMPT = """起点：{start}
目标：{goal}

请生成执行计划（JSON 格式）："""


def get_plan_generation_prompt() -> ChatPromptTemplate:
    """获取计划生成的 Prompt Template

    为什么使用 ChatPromptTemplate？
    - 支持多轮对话（system + user）
    - 自动处理消息格式
    - 与 LCEL 兼容

    为什么分离 system 和 user prompt？
    - system prompt：定义 LLM 的角色和规则（不变）
    - user prompt：提供具体的输入（变化）
    - 符合 OpenAI/KIMI 的最佳实践

    返回：
        ChatPromptTemplate: Prompt 模板

    示例：
    >>> prompt = get_plan_generation_prompt()
    >>> messages = prompt.invoke({"start": "CSV 文件", "goal": "分析数据"})
    >>> print(messages)
    """
    return ChatPromptTemplate.from_messages(
        [
            ("system", PLAN_GENERATION_SYSTEM_PROMPT),
            ("user", PLAN_GENERATION_USER_PROMPT),
        ]
    )


# 为什么不直接使用字符串模板？
# 1. ChatPromptTemplate 支持多轮对话（system + user + assistant）
# 2. 自动处理消息格式（OpenAI/KIMI 需要特定的消息格式）
# 3. 与 LCEL 兼容（可以直接用 | 连接）
# 4. 支持更多高级功能（如 few-shot examples、partial variables）

# 为什么使用双大括号 {{}}？
# 在 Python f-string 或 format() 中，{} 是占位符
# 在 Prompt 中，我们想输出 {}（JSON 格式）
# 所以使用 {{}} 转义，输出时会变成 {}

# 为什么强调"只输出 JSON"？
# LLM 有时会输出多余的文字，如：
# "好的，这是执行计划：[...]"
# "希望对你有帮助！"
# 这些文字会导致 JSON 解析失败
# 强调"只输出 JSON"可以减少这种情况

# 为什么要求任务数量 3-7 个？
# - 太少（1-2 个）：任务太粗粒度，不够具体
# - 太多（10+ 个）：任务太细粒度，过于复杂
# - 3-7 个：粒度适中，清晰、可执行

# 为什么要求任务有逻辑顺序？
# - 任务之间有依赖关系（如：先读取数据，再分析数据）
# - 按顺序执行能达到目标
# - 符合用户的思维习惯
